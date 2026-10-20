"""Pinned-release, conditional-profile fake-only compatibility and safety checks."""
import hashlib
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tool import c2b_restricted_frontend as frontend
from tool import c2b_recording_supervisor as recorder
from tool import c2b_native_recorder as bridge
from tests.fixtures.c2b_r10_release_client import ReleaseClient, TARGET, frame
from tests.fixtures.c2b_synthetic_client import SyntheticStdio


class ReleaseContractTests(unittest.TestCase):
    def client(self):
        f = frontend.Frontend()
        self.addCleanup(f.close)
        return f, ReleaseClient(f.handle)

    def test_source_profile_initialize_catalog_and_ping_are_inert(self):
        f, c = self.client()
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            response = c.initialize()
            self.assertIn("result", response)
            self.assertEqual(response["result"]["protocolVersion"], "2025-11-25")
            self.assertEqual(c.sent[0]["id"], 0)
            self.assertEqual(c.sent[0]["params"]["capabilities"], {"roots": {}})
            self.assertNotIn("params", c.sent[1])
            self.assertEqual(len(c.catalog()["result"]["tools"]), 2)
            self.assertEqual(c.request("ping")["result"], {})
            self.assertFalse(f.terminal)
            spawn.assert_not_called()

    def test_source_serializer_shape_is_independent_of_recorder(self):
        f, c = self.client()
        c.initialize()
        self.assertEqual(frame(c.sent[0]),
            b'{"method":"initialize","params":{"protocolVersion":"2025-11-25",'
            b'"capabilities":{"roots":{}},"clientInfo":{"name":"opencode","version":"1.19.0"}},'
            b'"jsonrpc":"2.0","id":0}\n')
        self.assertEqual(f.lifecycle, "READY")

    def test_progress_metadata_is_not_launch_authority(self):
        f, c = self.client()
        c.initialize()
        c.catalog()
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            response = c.call("roblox_studio_list_roblox_studios")
            self.assertIn("error", response)
            self.assertEqual(c.sent[-1]["params"], {"name": "list_roblox_studios", "arguments": {},
                                                  "_meta": {"progressToken": 2}})
            self.assertEqual(response["error"]["message"], "synthetic_launch_required_or_discovery_spent")
            spawn.assert_not_called()

    def test_only_pinned_roots_profile_is_added(self):
        for changes in ({"capabilities": {"roots": {"listChanged": True}}},
                        {"capabilities": {"roots": {}, "sampling": {}}},
                        {"clientInfo": {"name": "opencode", "version": "other"}},
                        {"protocolVersion": "2025-06-18"}):
            with self.subTest(changes=changes):
                f, c = self.client()
                params = {"protocolVersion": "2025-11-25", "capabilities": {"roots": {}},
                          "clientInfo": {"name": "opencode", "version": "1.19.0"}}
                self.assertIn("error", c.request("initialize", params | changes))
                self.assertIsNone(f.runner)

    def test_progress_metadata_is_exact_bounded_and_request_correlated(self):
        for meta in ({}, {"progressToken": True}, {"progressToken": "1"},
                     {"progressToken": 0}, {"progressToken": 2**53},
                     {"progressToken": 1, "approve": True}, {"relatedTask": {}}, None):
            with self.subTest(meta=meta):
                f, c = self.client()
                c.initialize()
                with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
                    self.assertIn("error", c.request("tools/call", {
                        "name": "list_roblox_studios", "arguments": {}, "_meta": meta}))
                    self.assertTrue(f.terminal)
                    spawn.assert_not_called()

    def test_source_profile_does_not_accept_generic_metadata_or_missing_arguments(self):
        for params in ({"name": "list_roblox_studios", "arguments": {}},
                       {"name": "list_roblox_studios", "_meta": {"progressToken": 1}},
                       {"name": "list_roblox_studios", "arguments": {}, "_meta": {"progressToken": 1}, "task": {}},
                       {"name": "list_roblox_studios", "arguments": {"approve": True}, "_meta": {"progressToken": 1}}):
            f, c = self.client()
            c.initialize()
            self.assertIn("error", c.request("tools/call", params))
            self.assertIsNone(f.runner)

    def test_model_alias_is_reversed_not_sent_on_wire(self):
        f, c = self.client()
        c.initialize()
        c.catalog("roblox.studio")
        self.assertEqual(c.aliases["roblox_studio_get_studio_state"], "get_studio_state")
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            self.assertIn("error", c.request("tools/call", {
                "name": "roblox_studio_get_studio_state", "arguments": {"studio_id": TARGET}}, progress=True))
            spawn.assert_not_called()

    def test_source_result_error_and_structured_conversion_subset(self):
        self.assertEqual(ReleaseClient.text_result({"result": {"content": [{"type": "text", "text": "ok"}]}}), "ok")
        self.assertEqual(ReleaseClient.text_result({"result": {"structuredContent": {"x": 1}}}), '{"x":1}')
        with self.assertRaisesRegex(ValueError, "tool failed"):
            ReleaseClient.text_result({"result": {"isError": True, "content": [{"type": "text", "text": "tool failed"}]}})
        with self.assertRaisesRegex(ValueError, "JSON-RPC error"):
            ReleaseClient.text_result({"error": {"message": "terminal refusal"}})

    def test_catalog_schema_remains_exact_and_no_extra_capabilities(self):
        f, c = self.client()
        self.assertEqual(c.initialize()["result"]["capabilities"], {"tools": {}})
        tools = c.catalog()["result"]["tools"]
        self.assertEqual([t["name"] for t in tools], ["list_roblox_studios", "get_studio_state"])
        self.assertTrue(all(t["inputSchema"]["additionalProperties"] is False for t in tools))
        self.assertTrue(all("outputSchema" not in t for t in tools))
        self.assertEqual(tools[1]["inputSchema"]["properties"]["studio_id"]["const"], TARGET)


@unittest.skipUnless(os.name == "nt", "actual contained synthetic child required")
class ReleaseContainedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)

    def client(self, name="release", **kwargs):
        f = frontend.Frontend(self.parent, name, **kwargs)
        self.addCleanup(f.close)
        c = ReleaseClient(f.handle)
        self.assertIn("result", c.initialize())
        c.catalog()
        f.inject_launch(f.review.launch_token())
        return f, c

    def receipt(self, f):
        self.assertTrue(f.review.finished.wait(5), f.reason)
        f.close()
        r = recorder.verify_recording(self.parent / f.observation)
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertFalse(r["shutdown"]["uncertain"])
        self.assertFalse(r["studio_touched"])
        self.assertFalse(r["compatibility_pass"])
        return r

    def test_release_serial_discovery_review_state_and_raw_originals(self):
        f, c = self.client()
        response = c.call("roblox_studio_list_roblox_studios")
        self.assertEqual(json.loads(c.text_result(response))["studios"][0]["id"], TARGET)
        self.assertEqual(f.review.phase, "WAIT_REVIEW")
        f.review.verify_checkpoint()
        f.inject_continuation(f.review.continuation_token())
        result = c.call("roblox_studio_get_studio_state", {"studio_id": TARGET})
        self.assertEqual(json.loads(c.text_result(result))["studio_id"], TARGET)
        r = self.receipt(f)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        writes = [json.loads(p.read_bytes()) for p in (self.parent / "release").glob("stdin-*.bin")]
        calls = [m for m in writes if m.get("method") == "tools/call"]
        self.assertEqual([m["params"]["name"] for m in calls], ["list_roblox_studios", "get_studio_state"])
        self.assertTrue(all(set(m["params"]) == {"name", "arguments"} for m in calls))
        # The source SDK cannot correlate a post-terminal null-ID refusal; the
        # disposable connection is over, not a reusable successful tool response.
        with self.assertRaisesRegex(ValueError, "uncorrelated response"):
            c.call("roblox_studio_list_roblox_studios")

    def test_release_missing_continuation_wrong_target_and_retry_remain_terminal(self):
        for name, mode in (("missing", "missing"), ("wrong", "wrong"), ("retry", "retry")):
            f, c = self.client(name)
            self.assertIn("result", c.call("roblox_studio_list_roblox_studios"))
            if mode == "retry":
                response = c.call("roblox_studio_list_roblox_studios")
            else:
                if mode == "wrong":
                    f.inject_continuation(f.review.continuation_token())
                response = c.call("roblox_studio_get_studio_state", {"studio_id": "wrong" if mode == "wrong" else TARGET})
            self.assertIn("error", response)
            self.assertEqual(len(self.receipt(f)["calls"]), 2)

    def test_release_checkpoint_tamper_during_state_intent_still_writes_zero_state(self):
        f, c = self.client()
        c.call("roblox_studio_list_roblox_studios")
        f.inject_continuation(f.review.continuation_token())
        write = recorder._write_new
        def tamper(path, data):
            meta = write(path, data)
            if path.name == "state-attempt.json":
                (path.parent / "discovery-checkpoint.json").write_bytes(b"tampered")
            return meta
        with patch.object(recorder, "_write_new", side_effect=tamper):
            self.assertIn("error", c.call("roblox_studio_get_studio_state", {"studio_id": TARGET}))
        self.assertTrue(f.review.finished.wait(5))
        r = json.loads((self.parent / "release/receipt.json").read_bytes())
        state = [entry for entry in r["writes"] if b'"get_studio_state"' in
                 (self.parent / "release" / entry["file"]).read_bytes()]
        self.assertEqual(len(state), 1)
        self.assertEqual(state[0]["bytes_written"], 0)

    def test_release_stdio_handshake_and_tools_use_actual_frontend_loop(self):
        f = frontend.Frontend(self.parent, "stdio")
        self.addCleanup(f.close)
        f.inject_launch(f.review.launch_token())
        streams, outcome = SyntheticStdio(), []
        server = threading.Thread(target=lambda: outcome.append(frontend.serve(f, streams, streams, io.StringIO())))
        server.start()
        def exchange(raw):
            streams.input.put(raw, timeout=2)
            if "id" not in json.loads(raw):
                return None
            return frame(streams.receive())
        c = ReleaseClient(exchange)
        try:
            self.assertIn("result", c.initialize())
            c.catalog()
            self.assertIn("studios", json.loads(c.text_result(c.call("roblox_studio_list_roblox_studios"))))
            f.inject_continuation(f.review.continuation_token())
            self.assertEqual(json.loads(c.text_result(c.call("roblox_studio_get_studio_state", {"studio_id": TARGET})))["studio_id"], TARGET)
            server.join(5)
            self.assertFalse(server.is_alive())
            self.assertEqual(outcome, [0])
            self.assertEqual(self.receipt(f)["status"], "synthetic_sequence_recorded")
        finally:
            streams.input.put(b"")
            f.close()
            server.join(5)

    def test_release_inflight_cancel_and_concurrent_catalog_abort_without_queue(self):
        for name, control in (("cancel", "cancel"), ("concurrent", "catalog")):
            f, c = self.client(name, scenario="timeout", window_seconds=0.5)
            responses = []
            entered, release = threading.Event(), threading.Event()
            original = recorder._Session.request
            def held(session, method, *args):
                if method == "tools/call":
                    entered.set()
                    release.wait(3)
                return original(session, method, *args)
            with patch.object(recorder._Session, "request", held):
                worker = threading.Thread(target=lambda: responses.append(c.call("roblox_studio_list_roblox_studios")))
                worker.start()
                try:
                    self.assertTrue(entered.wait(3))
                    if control == "cancel":
                        c.notify("notifications/cancelled", {"requestId": 2, "reason": "synthetic timeout"})
                    else:
                        with self.assertRaisesRegex(ValueError, "uncorrelated response"):
                            c.request("tools/list")
                finally:
                    release.set()
                    worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertIn("error", responses[0])
            self.assertLessEqual(len(self.receipt(f)["calls"]), 2)


class SourcePacketTests(unittest.TestCase):
    def test_retrieved_response_bodies_match_acquisition_hashes(self):
        root = Path(__file__).resolve().parents[1] / "docs/evidence/r10-source"
        checked = 0
        for manifest in sorted(root.glob("acquisition-*.json")):
            for item in json.loads(manifest.read_bytes())["files"]:
                if "error" in item:
                    continue
                raw = (root / item["file"]).read_bytes()
                self.assertEqual(len(raw), item["length"], item["file"])
                self.assertEqual(hashlib.sha256(raw).hexdigest(), item["sha256"], item["file"])
                checked += 1
        self.assertGreaterEqual(checked, 37)

    def test_release_tag_attributions_are_exact(self):
        root = Path(__file__).resolve().parents[1] / "docs/evidence/r10-source"
        self.assertEqual(json.loads((root / "oc-tag.json").read_bytes())["object"]["sha"],
                         "733b2c627e5aec39cb33cc22373bdce33053ef2c")
        self.assertEqual(json.loads((root / "sdk-tag.json").read_bytes())["object"]["sha"],
                         "e12cbd7078db388152f6e839abdbe09ba01f3f32")


if __name__ == "__main__":
    unittest.main()
