import ctypes
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from ctypes import wintypes as w
from pathlib import Path
from unittest.mock import patch

from tool import c2b_restricted_frontend as frontend
from tool import c2b_recording_supervisor as recorder
from tool import c2b_native_recorder as bridge
from tests.fixtures.c2b_synthetic_client import SyntheticClient, SyntheticStdio


class ContractTests(unittest.TestCase):
    def client(self):
        f = frontend.Frontend()
        self.addCleanup(f.close)
        return f, SyntheticClient(f)

    def test_startup_initialize_catalog_and_ping_never_create_child(self):
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            f, c = self.client()
            self.assertIsNone(f.runner)
            init = c.initialize()["result"]
            self.assertEqual(init["capabilities"], {"tools": {}})
            tools = c.request("tools/list")["result"]["tools"]
            self.assertEqual([t["name"] for t in tools], ["list_roblox_studios", "get_studio_state"])
            self.assertEqual(c.request("ping")["result"], {})
            self.assertEqual(tools[1]["inputSchema"]["properties"]["studio_id"]["const"], recorder.TARGET)
            spawn.assert_not_called()

    def test_unauthorized_discovery_is_terminal_and_cannot_retry(self):
        f, c = self.client()
        c.initialize()
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            self.assertIn("error", c.discovery())
            self.assertIn("error", c.discovery())
            self.assertIn("error", c.request("tools/list"))
            spawn.assert_not_called()

    def test_every_other_method_is_refused(self):
        for method in ("resources/list", "prompts/list", "tasks/get", "sampling/createMessage",
                       "roots/list", "logging/setLevel", "synthetic/authorize", "synthetic/continue",
                       "shutdown", "exit", "unknown"):
            with self.subTest(method=method):
                f, c = self.client()
                c.initialize()
                self.assertIn("error", c.request(method, {}))
                self.assertTrue(f.terminal)

    def test_forbidden_aliases_tools_and_wrong_arguments(self):
        bad = [{"name": name, "arguments": {}} for name in (
            "execute_luau", "screen_capture", "multi_edit", "upload_image", "insert_asset",
            "start_stop_play", "save", "publish", "subagent", "roblox_studio_list_roblox_studios")]
        bad += [{"name": "list_roblox_studios", "arguments": {"approve": True}},
                {"name": "list_roblox_studios"},
                {"name": "list_roblox_studios", "arguments": {}, "_meta": {}},
                {"name": "get_studio_state", "arguments": {"studio_id": "wrong"}},
                {"name": "get_studio_state", "arguments": {}},
                {"name": "get_studio_state", "arguments": {"studio_id": recorder.TARGET, "extra": 1}}]
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            for params in bad:
                with self.subTest(params=params):
                    f, c = self.client()
                    c.initialize()
                    self.assertIn("error", c.request("tools/call", params))
            spawn.assert_not_called()

    def test_initialize_exact_version_capabilities_and_lifecycle(self):
        base = {"protocolVersion": recorder.PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "fixture", "version": "1"}}
        for changes in ({"protocolVersion": "2024-11-05"}, {"capabilities": {"roots": {}}},
                        {"extra": True}, {"clientInfo": {"name": "fixture"}}):
            f, c = self.client()
            self.assertIn("error", c.request("initialize", base | changes))
        f, c = self.client()
        self.assertIn("error", c.request("tools/list"))
        f, c = self.client()
        c.initialize()
        self.assertIn("error", c.request("initialize", base))

    def test_notification_controls_and_unknown_envelopes(self):
        for message in ({"jsonrpc": "2.0", "id": 1, "result": {}},
                        {"jsonrpc": "2.0", "id": True, "method": "ping"},
                        {"jsonrpc": "2.0", "id": None, "method": "ping"},
                        {"jsonrpc": "2.0", "id": 1, "method": "ping", "result": {}},
                        {"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}):
            f, c = self.client()
            c.initialize()
            self.assertIn("error", json.loads(f.handle(recorder._json_frame(message))))
        f, c = self.client()
        c.initialize()
        self.assertIsNone(c.notify("notifications/cancelled", {"requestId": 42, "reason": "test"}))
        self.assertTrue(f.terminal)

    def test_malformed_oversized_and_unexpected_frames(self):
        for raw in (b"\xff\n", b"\n", b"{}", b"[]\n", b"null\n", b"{}\n{}\n",
                    b'{"a":1,"a":2}\n', b'{"x":NaN}\n', b'{"x":1e999}\n',
                    b"[" * 2000 + b"\n", b"x" * 4096 + b"\n"):
            f, _ = self.client()
            self.assertIn("error", json.loads(f.handle(raw)))
            self.assertTrue(f.terminal)

    def test_exact_client_frame_crlf_and_typed_ids(self):
        f, c = self.client()
        c.initialize()
        frame = recorder._json_frame({"jsonrpc": "2.0", "id": "9", "method": "ping"})
        frame = frame[:-1] + b" " * (4096 - len(frame) - 1) + b"\r\n"
        self.assertEqual(len(frame), 4096)
        self.assertEqual(json.loads(f.handle(frame))["result"], {})
        self.assertEqual(c.request("ping", request_id=9)["result"], {})
        self.assertIn("error", c.request("ping", request_id="9"))

    def test_duplicate_ids_and_bounded_catalog_traffic(self):
        f, c = self.client()
        c.initialize()
        c.request("ping", request_id="same")
        self.assertIn("error", c.request("tools/list", request_id="same"))
        f, c = self.client()
        c.initialize()
        for _ in range(64):
            response = c.request("tools/list")
            if "error" in response:
                break
        self.assertTrue(f.terminal)
        self.assertLessEqual(len(f.ids), frontend.CLIENT_FRAMES)

    def test_no_command_path_environment_or_live_interface(self):
        for key in ("executable", "argv", "environment", "shell", "studio_path", "live"):
            with self.assertRaises(TypeError):
                frontend.Frontend(**{key: "anything"})
        for value in ("StudioMCP.exe", "mcp.bat", "normal --live"):
            with self.assertRaises(ValueError):
                frontend.Frontend(scenario=value)

    def test_invalid_synthetic_launch_including_unserializable_input_refuses(self):
        with tempfile.TemporaryDirectory() as temp:
            for value in (None, False, {}, {"test_only": True}, {"not_json": object()}):
                f = frontend.Frontend(Path(temp))
                with self.assertRaises(recorder.Refusal):
                    f.inject_launch(value)
                self.assertEqual(f.review.phase, "TERMINAL")
                self.assertIsNone(f.runner)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_stdio_only_protocol_stdout_and_diagnostic_stderr(self):
        proc = subprocess.Popen([sys.executable, "-m", "tool.c2b_restricted_frontend"],
                                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        frames = b''.join(recorder._json_frame(x) for x in (
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": recorder.PROTOCOL, "capabilities": {},
                "clientInfo": {"name": "fixture", "version": "1"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}))
        # An orderly client sends each request after its predecessor response;
        # this finite pipeline exercises local controls only.
        out, err = proc.communicate(frames, timeout=5)
        self.assertEqual([json.loads(line)["id"] for line in out.splitlines()], [1, 2])
        self.assertIn(b"TEST ONLY terminal", err)
        self.assertNotIn(b"Traceback", err)
        self.assertEqual(proc.returncode, 1)  # EOF is never an observation success.

    def test_client_reader_start_failure_is_terminal(self):
        f, _ = self.client()
        with patch.object(recorder, "_start_reader", side_effect=RuntimeError("test start refusal")):
            self.assertEqual(frontend.serve(f, io.BytesIO(), io.BytesIO(), io.StringIO()), 1)
        self.assertTrue(f.terminal)
        self.assertIsNone(f.runner)


@unittest.skipUnless(os.name == "nt", "actual R7 contained synthetic children required")
class IntegratedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.counter = 0

    def client(self, scenario="normal", **kwargs):
        self.counter += 1
        f = frontend.Frontend(self.parent, "run-" + str(self.counter), scenario=scenario, **kwargs)
        self.addCleanup(f.close)
        c = SyntheticClient(f)
        c.initialize()
        f.inject_launch(f.review.launch_token())
        return f, c

    def receipt(self, f):
        self.assertTrue(f.review.finished.wait(5), f.reason)
        if f.runner:
            f.runner.join(timeout=1)
        r = recorder.verify_recording(self.parent / f.observation)
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"], r)
        self.assertTrue(r["shutdown"]["root_exit_confirmed"], r)
        self.assertTrue(r["shutdown"]["handles_closed"], r)
        self.assertFalse(r["shutdown"]["uncertain"], r)
        self.assertFalse(r["studio_touched"])
        self.assertFalse(r["utc_verified"])
        self.assertFalse(r["compatibility_pass"])
        return r

    def tool_names(self, f):
        dest = self.parent / f.observation
        return [json.loads(p.read_bytes())["params"]["name"] for p in sorted(dest.glob("stdin-*.bin"))
                if json.loads(p.read_bytes()).get("method") == "tools/call"]

    def test_true_pause_durable_checkpoint_then_explicit_state(self):
        f, c = self.client()
        with patch.object(recorder.subprocess, "Popen", side_effect=AssertionError("no fallback")):
            self.assertIn("result", c.discovery())
            self.assertEqual(f.review.phase, "WAIT_REVIEW")
            self.assertTrue(f.runner.is_alive())
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])
            f.review.verify_checkpoint()
            cp = f.review.checkpoint
            self.assertEqual(cp["session"], f.review.session_id)
            self.assertEqual(cp["expectations"]["studio_id"], recorder.TARGET)
            self.assertEqual(len(cp["files"]), 6)  # launch + init/notification/discovery + 2 responses
            time.sleep(0.06)
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])
            f.inject_continuation(f.review.continuation_token())
            time.sleep(0.03)
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])
            self.assertIn("result", c.state(recorder.TARGET))
        r = self.receipt(f)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        self.assertEqual(r["synthetic_session"], f.review.session_id)
        self.assertEqual(self.tool_names(f), ["list_roblox_studios", "get_studio_state"])
        self.assertEqual(len(r["calls"]), 3)
        self.assertIn("error", c.discovery())
        self.assertEqual(len(self.tool_names(f)), 2)

    def test_missing_continuation_prevents_state(self):
        f, c = self.client()
        c.discovery()
        self.assertIn("error", c.state(recorder.TARGET))
        self.assertEqual(len(self.receipt(f)["calls"]), 2)
        self.assertEqual(self.tool_names(f), ["list_roblox_studios"])

    def test_stdio_frontend_end_to_end_pause_and_terminal_exit(self):
        f, _ = self.client()
        # client() initialized the Python surface; this connection is now the
        # sole byte-stream client, using the same already-ready synthetic session.
        streams, diagnostics, result = SyntheticStdio(), io.StringIO(), []
        server = threading.Thread(target=lambda: result.append(
            frontend.serve(f, streams, streams, diagnostics)))
        server.start()
        try:
            streams.send("tools/list", request_id="catalog")
            self.assertEqual(len(streams.receive()["result"]["tools"]), 2)
            streams.send("tools/call", {"name": "list_roblox_studios", "arguments": {}}, request_id="discover")
            self.assertEqual(streams.receive()["id"], "discover")
            self.assertEqual(f.review.phase, "WAIT_REVIEW")
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])
            f.inject_continuation(f.review.continuation_token())
            streams.send("tools/call", {"name": "get_studio_state", "arguments": {"studio_id": recorder.TARGET}},
                         request_id="state")
            response = streams.receive()
            self.assertEqual(response["id"], "state")
            self.assertIn("result", response)
            server.join(timeout=5)
            self.assertFalse(server.is_alive())
            self.assertEqual(result, [0])
            self.assertTrue(f.completed)
            self.assertIn("TEST ONLY terminal", diagnostics.getvalue())
            self.assertEqual(self.receipt(f)["status"], "synthetic_sequence_recorded")
        finally:
            streams.input.put(b"")  # Release the borrowed client-reader stream.
            f.close()
            server.join(timeout=5)

    def test_stdio_disconnect_and_pipelined_tools_never_succeed(self):
        for pipelined in (False, True):
            f, _ = self.client("timeout", window_seconds=0.2)
            streams, result = SyntheticStdio(), []
            server = threading.Thread(target=lambda: result.append(
                frontend.serve(f, streams, streams, io.StringIO())))
            server.start()
            streams.send("tools/call", {"name": "list_roblox_studios", "arguments": {}}, request_id=10)
            if pipelined:
                streams.send("tools/call", {"name": "list_roblox_studios", "arguments": {}}, request_id=11)
            else:
                streams.input.put(b"")
            server.join(timeout=5)
            self.assertFalse(server.is_alive())
            self.assertEqual(result, [1])
            self.assertFalse(f.completed)
            streams.input.put(b"")
            self.assertLessEqual(len(self.tool_names(f)), 1)

    def test_client_output_failure_after_recording_is_not_frontend_success(self):
        f, _ = self.client()
        class BrokenOutput(SyntheticStdio):
            def write(self, data):
                if b'"id":"state"' in bytes(data):
                    raise OSError("synthetic disconnected output")
                return super().write(data)
        streams, result = BrokenOutput(), []
        server = threading.Thread(target=lambda: result.append(
            frontend.serve(f, streams, streams, io.StringIO())))
        server.start()
        try:
            streams.send("tools/call", {"name": "list_roblox_studios", "arguments": {}}, request_id="discovery")
            self.assertIn("result", streams.receive())
            f.inject_continuation(f.review.continuation_token())
            streams.send("tools/call", {"name": "get_studio_state", "arguments": {"studio_id": recorder.TARGET}},
                         request_id="state")
            server.join(timeout=5)
            self.assertFalse(server.is_alive())
            self.assertEqual(result, [1])
            self.assertFalse(f.completed)
            # An actual completed recording remains evidence, not proof that
            # this disconnected frontend delivered a successful client result.
            self.assertEqual(self.receipt(f)["status"], "synthetic_sequence_recorded")
            self.assertIn("error", SyntheticClient(f).discovery())
            self.assertEqual(len(self.tool_names(f)), 2)
        finally:
            streams.input.put(b"")
            f.close()
            server.join(timeout=5)

    def test_inflight_client_cancellation_stops_before_next_tool(self):
        f, c = self.client("timeout", window_seconds=1)
        responses = []
        worker = threading.Thread(target=lambda: responses.append(c.discovery()))
        worker.start()
        until = time.monotonic() + 3
        while not f.review.session or len(f.review.session.calls) < 2:
            self.assertLess(time.monotonic(), until)
            time.sleep(0.005)
        # No concurrent dispatch is allowed, including a cancellation envelope;
        # the connection aborts rather than queuing any operation.
        c.notify("notifications/cancelled", {"requestId": 2})
        worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertIn("error", responses[0])
        self.assertEqual(len(self.receipt(f)["calls"]), 2)
        self.assertIn("error", c.state(recorder.TARGET))

    def test_r9_original_stdout_is_persisted_before_json_decode(self):
        f, c = self.client("notifications")
        original = recorder._strict_json
        seen = []
        def parse(raw):
            if b'"jsonrpc"' in raw:
                saved = [p.read_bytes() for p in (self.parent / f.observation).glob("stdout-*.bin")]
                self.assertIn(raw, saved)
                seen.append(raw)
            return original(raw)
        with patch.object(recorder, "_strict_json", side_effect=parse):
            self.assertIn("result", c.discovery())
            f.inject_continuation(f.review.continuation_token())
            self.assertIn("result", c.state(recorder.TARGET))
        self.assertGreaterEqual(len(seen), 6)
        self.assertEqual(self.receipt(f)["status"], "synthetic_sequence_recorded")

    def test_uncertain_cleanup_never_returns_success_or_allows_restart(self):
        f, c = self.client()
        c.discovery()
        f.inject_continuation(f.review.continuation_token())
        finish = bridge.SyntheticRecorderProcess.finish
        def uncertain(process, workers):
            result = finish(process, workers)  # Real cleanup remains mandatory.
            result["uncertain"] = True
            result["errors"].append("synthetic verification uncertainty")
            return result
        with patch.object(bridge.SyntheticRecorderProcess, "finish", uncertain):
            self.assertIn("error", c.state(recorder.TARGET))
        r = recorder.verify_recording(self.parent / f.observation)
        self.assertTrue(r["shutdown"]["uncertain"])
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertFalse(f.completed)
        other = frontend.Frontend(self.parent, f.observation)
        self.addCleanup(other.close)
        new_client = SyntheticClient(other)
        new_client.initialize()
        other.inject_launch(other.review.launch_token())
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            self.assertIn("error", new_client.discovery())
            spawn.assert_not_called()

    def test_declined_invalid_and_replayed_continuations(self):
        for change in ({"action": "decline"}, {"test_only": False}, {"session": "other"},
                       {"observation": "other"}, {"checkpoint": {}},
                       {"arguments": {"studio_id": "wrong"}}):
            f, c = self.client()
            c.discovery()
            with self.assertRaises(recorder.Refusal):
                f.inject_continuation(f.review.continuation_token() | change)
            self.assertIn("error", c.state(recorder.TARGET))
            self.assertEqual(len(self.receipt(f)["calls"]), 2)
        f, c = self.client()
        c.discovery()
        token = f.review.continuation_token()
        f.inject_continuation(token)
        with self.assertRaises(recorder.Refusal):
            f.inject_continuation(token)
        self.assertIn("error", c.state(recorder.TARGET))
        self.assertEqual(len(self.receipt(f)["calls"]), 2)

    def test_wrong_target_after_valid_review_never_dispatches(self):
        f, c = self.client()
        c.discovery()
        f.inject_continuation(f.review.continuation_token())
        self.assertIn("error", c.state("wrong"))
        self.assertEqual(len(self.receipt(f)["calls"]), 2)

    def test_checkpoint_and_original_tampering_prevent_state(self):
        for name in ("discovery-checkpoint.json", "synthetic-session.json", "stdin-004.bin", "stdout-005.bin"):
            f, c = self.client()
            c.discovery()
            dest = self.parent / f.observation
            if not (dest / name).exists():
                self.fail(f"expected checkpoint input absent: {name}; {list(dest.iterdir())}")
            (dest / name).write_bytes(b"tampered")
            f.inject_continuation(f.review.continuation_token())
            self.assertIn("error", c.state(recorder.TARGET))
            self.assertTrue(f.review.finished.wait(5))
            self.assertEqual(self.tool_names_without_parsing_tamper(dest), 0)
            # Tampered originals also invalidate final verification, as intended.
            with self.assertRaises(ValueError):
                recorder.verify_recording(dest)

    def tool_names_without_parsing_tamper(self, dest):
        return sum(b'"get_studio_state"' in p.read_bytes() for p in dest.glob("stdin-*.bin"))

    def test_checkpoint_storage_failure_cannot_dispatch_state(self):
        write = recorder._write_new
        def fail(path, data):
            if path.name == "discovery-checkpoint.json":
                raise OSError("synthetic checkpoint disk failure")
            return write(path, data)
        f, c = self.client()
        with patch.object(recorder, "_write_new", side_effect=fail):
            self.assertIn("error", c.discovery())
            self.assertTrue(f.review.finished.wait(5))
        self.assertFalse(f.review.ready.is_set())
        self.assertEqual(self.tool_names(f), ["list_roblox_studios"])

    def test_checkpoint_rechecked_after_state_intent_storage_before_first_byte(self):
        f, c = self.client()
        c.discovery()
        f.inject_continuation(f.review.continuation_token())
        write = recorder._write_new
        def tamper_after_intent(path, data):
            meta = write(path, data)
            if path.name == "state-attempt.json":
                (path.parent / "discovery-checkpoint.json").write_bytes(b"tampered during storage")
            return meta
        with patch.object(recorder, "_write_new", side_effect=tamper_after_intent):
            self.assertIn("error", c.state(recorder.TARGET))
            self.assertTrue(f.review.finished.wait(5))
        # Intended state bytes are recorded but no state byte reached the pipe.
        raw = json.loads((self.parent / f.observation / "receipt.json").read_bytes())
        intended = [entry for entry in raw["writes"] if b'"get_studio_state"' in
                    (self.parent / f.observation / entry["file"]).read_bytes()]
        self.assertEqual(len(intended), 1)
        self.assertEqual(intended[0]["bytes_written"], 0)
        self.assertFalse(raw["calls"][-1]["accepted"])
        self.assertFalse(f.completed)

    def test_cancellation_during_pipe_setup_prevents_resume(self):
        f, c = self.client()
        checkpoint = bridge._PipeLease._checkpoint
        processes = []
        start = bridge.SyntheticRecorderProcess.start
        def tracked(process):
            processes.append(process)
            return start(process)
        def cancel(lease, phase):
            checkpoint(lease, phase)
            if lease.kind == "stderr" and phase == "stream":
                f.abort("synthetic_cancel_before_resume")
        with patch.object(bridge._PipeLease, "_checkpoint", cancel), \
                patch.object(bridge.SyntheticRecorderProcess, "start", tracked):
            self.assertIn("error", c.discovery())
            self.assertTrue(f.review.finished.wait(5))
        self.assertEqual(self.tool_names(f), [])
        self.assertFalse(processes[0].boundary.report["execution_may_have_started"])
        self.assertTrue(processes[0].finish_result["tree_exit_confirmed"])
        self.assertTrue(processes[0].finish_result["handles_closed"])

    def test_duplicate_discovery_new_id_does_not_retry(self):
        f, c = self.client()
        c.discovery()
        self.assertIn("error", c.discovery())
        self.assertEqual(len(self.receipt(f)["calls"]), 2)

    def test_concurrent_requests_refuse_instead_of_queue(self):
        f, c = self.client("timeout", window_seconds=0.3)
        entered, release = threading.Event(), threading.Event()
        original = recorder._Session.request
        def held(session, method, *args):
            if method == "tools/call":
                entered.set()
                release.wait(2)
            return original(session, method, *args)
        responses = []
        with patch.object(recorder._Session, "request", held):
            worker = threading.Thread(target=lambda: responses.append(c.discovery()))
            worker.start()
            try:
                self.assertTrue(entered.wait(3))
                self.assertIn("error", c.discovery())
            finally:
                release.set()
                worker.join(timeout=5)
        self.assertFalse(worker.is_alive())
        self.assertIn("error", responses[0])
        r = self.receipt(f)
        self.assertLessEqual(len(r["calls"]), 2)
        self.assertEqual(self.tool_names(f), [])

    def test_reconnection_while_paused_cannot_resume_or_erase_uncertainty(self):
        f, c = self.client()
        c.discovery()
        token = f.review.continuation_token()
        f.close()
        self.assertNotEqual(self.receipt(f)["status"], "synthetic_sequence_recorded")
        other = frontend.Frontend(self.parent, f.observation)
        self.addCleanup(other.close)
        client = SyntheticClient(other)
        client.initialize()
        other.inject_launch(other.review.launch_token())
        with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
            self.assertIn("error", client.discovery())
            spawn.assert_not_called()
        with self.assertRaises(recorder.Refusal):
            other.inject_continuation(token)
        self.assertEqual(self.tool_names(f), ["list_roblox_studios"])

    def test_review_timeout_and_cancellation_and_unexpected_client(self):
        for action in ("timeout", "cancel", "disconnect", "unknown"):
            f, c = self.client(review_seconds=0.12)
            c.discovery()
            if action == "cancel":
                c.notify("notifications/cancelled", {"requestId": 3})
            elif action == "disconnect":
                f.close()
            elif action == "unknown":
                c.notify("unknown")
            r = self.receipt(f)
            self.assertNotEqual(r["status"], "synthetic_sequence_recorded")
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])

    def test_request_timeout_and_unknown_server_envelopes(self):
        for scenario in ("timeout", "server_request", "bad_notification", "malformed", "oversize", "wrong_id"):
            f, c = self.client(scenario, window_seconds=0.2)
            self.assertIn("error", c.discovery())
            self.assertFalse(f.review.ready.is_set())
            r = self.receipt(f)
            self.assertEqual(len(r["calls"]), 2)
            self.assertEqual(self.tool_names(f), ["list_roblox_studios"])

    def test_reader_deadline_race_does_not_disarm_already_due_watchdog(self):
        wait = threading.Event.wait
        def delayed_guard(event, timeout=None):
            thread = threading.current_thread()
            target = getattr(thread, "_target", None)
            if getattr(target, "__name__", None) == "watchdog" and timeout is not None:
                return wait(event, timeout + 0.04)
            return wait(event, timeout)
        f, c = self.client("timeout", window_seconds=0.1)
        with patch.object(threading.Event, "wait", delayed_guard):
            self.assertIn("error", c.discovery())
            r = self.receipt(f)
        self.assertEqual(r["status"], "timeout")
        self.assertIsNotNone(r["calls"][-1]["watchdog_fired_ns"])
        self.assertFalse(r["calls"][-1]["accepted"])

    def test_unsolicited_output_during_pause_prevents_state(self):
        f, c = self.client("trailing")
        c.discovery()
        self.assertTrue(f.review.finished.wait(5))
        self.assertIn("error", c.state(recorder.TARGET))
        self.assertEqual(len(self.receipt(f)["calls"]), 2)

    def test_reader_registered_before_start_and_hidden_start_is_joined(self):
        original = recorder._start_reader
        seen = []
        def interrupted(reader, registry):
            start = reader.start
            def hidden():
                self.assertIn(reader, registry)
                start()
                seen.append(reader)
                raise RuntimeError("hidden successful start")
            with patch.object(reader, "start", side_effect=hidden):
                original(reader, registry)
        f, c = self.client()
        with patch.object(recorder, "_start_reader", side_effect=interrupted):
            self.assertIn("error", c.discovery())
            r = self.receipt(f)
        self.assertEqual(r["writes"], [])
        self.assertEqual(r["status"], "reader_or_worker_start_failure")
        self.assertTrue(seen)
        self.assertFalse(any(t.is_alive() for t in seen))

    def test_reader_documented_start_failure_has_no_borrower(self):
        original = recorder._start_reader
        def refused(reader, registry):
            with patch.object(reader, "start", side_effect=RuntimeError("start refused")):
                original(reader, registry)
            self.fail("start must raise")
        f, c = self.client()
        with patch.object(recorder, "_start_reader", side_effect=refused):
            self.assertIn("error", c.discovery())
            r = self.receipt(f)
        self.assertEqual(r["writes"], [])

    def test_commit_failure_never_returns_successful_state(self):
        f, c = self.client()
        c.discovery()
        f.inject_continuation(f.review.continuation_token())
        write = recorder._write_new
        def fail(path, data):
            if path.name == "COMMITTED.json":
                raise OSError("synthetic commit failure")
            return write(path, data)
        with patch.object(recorder, "_write_new", side_effect=fail):
            self.assertIn("error", c.state(recorder.TARGET))
        self.assertFalse((self.parent / f.observation / "COMMITTED.json").exists())
        self.assertIn("error", c.discovery())

    def test_controller_death_before_and_after_checkpoint_is_never_resumable(self):
        api = bridge.SyntheticBoundary(self.parent).api
        api.dll.GetCurrentProcess.restype = w.HANDLE
        api.dll.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE,
                                           ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
        api.dll.DuplicateHandle.restype = w.BOOL
        fixture = Path(__file__).parent / "fixtures/c2b_frontend_controller.py"
        for phase in ("before_checkpoint", "after_checkpoint"):
            directory = self.parent / phase
            directory.mkdir()
            proc = subprocess.Popen([sys.executable, "-I", "-S", "-u", str(fixture),
                                     str(directory), phase], stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            observer = w.HANDLE()
            try:
                ready = directory / "ready.json"
                until = time.monotonic() + 5
                while not (ready.exists() and ready.stat().st_size > 2):
                    self.assertIsNone(proc.poll(), proc.communicate() if proc.poll() is not None else "")
                    self.assertLess(time.monotonic(), until)
                    time.sleep(0.01)
                handle = json.loads(ready.read_text())["process"]
                api.checked(api.dll.DuplicateHandle(int(proc._handle), handle,
                    api.dll.GetCurrentProcess(), ctypes.byref(observer), 0x100000, False, 0))
                proc.kill()
                proc.wait(timeout=5)
                self.assertEqual(api.WaitForSingleObject(observer, 5000), 0)
                _, err = proc.communicate(timeout=5)
                self.assertNotIn(b"Traceback", err)
                dest = directory / "observation"
                self.assertEqual((dest / "discovery-checkpoint.json").exists(), phase == "after_checkpoint")
                self.assertFalse((dest / "COMMITTED.json").exists())
                self.assertEqual(self.tool_names_without_parsing_tamper(dest), 0)
                other = frontend.Frontend(directory, "observation")
                self.addCleanup(other.close)
                c = SyntheticClient(other)
                c.initialize()
                other.inject_launch(other.review.launch_token())
                with patch.object(bridge.SyntheticRecorderProcess, "start") as spawn:
                    self.assertIn("error", c.discovery())
                    spawn.assert_not_called()
            finally:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate(timeout=5)
                if observer.value:
                    api.checked(api.CloseHandle(observer))


class ReaderRegistrationTests(unittest.TestCase):
    def test_interruption_without_observed_start_keeps_quarantine(self):
        reader = threading.Thread(target=lambda: None)
        registry = []
        with patch.object(reader, "start", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                recorder._start_reader(reader, registry)
        self.assertEqual(registry, [reader])
        self.assertTrue(recorder._join_reader(reader))
        self.assertTrue(reader._c2b_start_unknown)


if __name__ == "__main__":
    unittest.main()
