import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tool import c2b_recording_supervisor as recorder


class PolicyTests(unittest.TestCase):
    def test_only_exact_gate_a_sequence_and_explicit_review(self):
        policy = recorder.GateAPolicy()
        discovery = {"name": "list_roblox_studios", "arguments": {}}
        state = {"name": "get_studio_state", "arguments": {"studio_id": recorder.TARGET}}
        with self.assertRaises(recorder.Refusal):
            policy.check("tools/call", state)
        policy.check("tools/call", discovery)
        policy.recorded()
        for params in (discovery, state):
            with self.assertRaises(recorder.Refusal):
                policy.check("tools/call", params)
        policy.reviewed()
        policy.check("tools/call", state)
        policy.recorded()
        with self.assertRaises(recorder.Refusal):
            policy.check("tools/call", state)

    def test_prohibited_tools_and_methods(self):
        for name in ("execute_luau", "screen_capture", "multi_edit", "upload_image",
                     "insert_asset", "start_stop_play", "save", "publish", "subagent",
                     "roblox_studio_list_roblox_studios", "unexpected"):
            with self.subTest(name=name), self.assertRaises(recorder.Refusal):
                recorder.GateAPolicy().check("tools/call", {"name": name, "arguments": {}})
        for method in ("tools/list", "resources/list", "prompts/list", "initialize", "ping"):
            with self.subTest(method=method), self.assertRaises(recorder.Refusal):
                recorder.GateAPolicy().check(method, {})

    def test_extra_arguments_metadata_and_wrong_target(self):
        for params in ({"name": "list_roblox_studios"},
                       {"name": "list_roblox_studios", "arguments": {"code": "anything"}},
                       {"name": "list_roblox_studios", "arguments": {}, "_meta": {}},
                       {"name": "list_roblox_studios", "arguments": {}, "task": {}}):
            with self.assertRaises(recorder.Refusal):
                recorder.GateAPolicy().check("tools/call", params)
        p = recorder.GateAPolicy()
        p.recorded()
        p.reviewed()
        for args in ({}, {"studio_id": "other"}, {"studio_id": recorder.TARGET, "code": "x"}):
            with self.assertRaises(recorder.Refusal):
                p.check("tools/call", {"name": "get_studio_state", "arguments": args})

    def test_no_arbitrary_command_or_live_option(self):
        with tempfile.TemporaryDirectory() as temp:
            for scenario in ("StudioMCP.exe", "cmd.exe /c something", "normal --live"):
                with self.assertRaises(ValueError):
                    recorder.run_synthetic(Path(temp), "refuse", scenario)
            with self.assertRaises(TypeError):
                recorder.run_synthetic(Path(temp), "refuse", live=True)
            self.assertEqual(list(Path(temp).iterdir()), [])


@unittest.skipUnless(os.name == "nt", "real Windows synthetic child/process-tree tests")
class SupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)
        self.count = 0

    def record(self, scenario="normal", **kwargs):
        self.count += 1
        kwargs.setdefault("window_seconds", 1.5)
        dest = recorder.run_synthetic(self.parent, f"run-{self.count}", scenario, **kwargs)
        receipt = recorder.verify_recording(dest)
        self.assertTrue(receipt["synthetic"])
        self.assertFalse(receipt["studio_touched"])
        self.assertIsNone(receipt["authorization"])
        self.assertFalse(receipt["utc_verified"])
        self.assertFalse(receipt["compatibility_pass"])
        self.assertFalse(receipt["full_upstream_response_claim"])
        self.assertIsNone(receipt["total_upstream_response_bytes"])
        self.assertFalse(receipt["shutdown"]["uncertain"], receipt["shutdown"])
        self.assertTrue(receipt["shutdown"]["tree_exit_confirmed"])
        return dest, receipt

    def assert_refused(self, scenario, **kwargs):
        dest, receipt = self.record(scenario, **kwargs)
        self.assertFalse(receipt["status"].startswith("synthetic_"), receipt)
        self.assertTrue(receipt["retained_streams_are_incomplete_failure_evidence"])
        return dest, receipt

    def test_normal_initialize_discover_pause_without_state(self):
        dest, r = self.record()
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        requests = [json.loads((dest / f).read_bytes()) for f in r["files"] if f.startswith("stdin-")]
        self.assertEqual([x.get("method") for x in requests],
                         ["initialize", "notifications/initialized", "tools/call"])
        self.assertEqual(requests[-1]["params"], {"name": "list_roblox_studios", "arguments": {}})
        self.assertEqual(len(r["calls"]), 2)

    def test_explicit_synthetic_state_sequence(self):
        dest, r = self.record(synthetic_state_review=True)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        self.assertEqual(len(r["calls"]), 3)
        for write in r["writes"]:
            self.assertEqual(write["bytes_written"], write["intended_bytes"])
            self.assertIsNone(write["error"])
        for call in r["calls"]:
            self.assertTrue(call["accepted"])
            self.assertLess(call["validated_monotonic_ns"], call["deadline_monotonic_ns"])
        requests = [json.loads((dest / f).read_bytes()) for f in r["files"] if f.startswith("stdin-")]
        self.assertEqual(requests[-1]["params"], {"name": "get_studio_state",
                                                "arguments": {"studio_id": recorder.TARGET}})

    def test_original_bytes_saved_before_parsing(self):
        original = recorder._strict_json
        seen = []
        def parse(raw):
            if b'"jsonrpc"' in raw:
                saved = [f.read_bytes() for d in self.parent.iterdir()
                         for f in d.glob("stdout-*.bin") if f.name != "stdout-prefix.bin"]
                self.assertIn(raw, saved)
                seen.append(raw)
            return original(raw)
        with patch.object(recorder, "_strict_json", side_effect=parse):
            dest, r = self.record()
        combined = (dest / "stdout-prefix.bin").read_bytes()
        self.assertEqual(b"".join(seen), combined)
        self.assertIn("雪".encode(), combined)
        self.assertEqual(r["files"]["stdout-prefix.bin"]["sha256"], hashlib.sha256(combined).hexdigest())

    def test_partial_writes_and_split_utf8(self):
        dest, r = self.record("partial", synthetic_state_review=True)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        self.assertIn("雪".encode(), (dest / "stdout-prefix.bin").read_bytes())

    def test_ping_and_logging_are_separate_recorded_control_frames(self):
        dest, r = self.record("notifications", synthetic_state_review=True)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        frames = [json.loads((dest / f).read_bytes()) for f in r["files"] if f.startswith("stdin-")]
        pongs = [x for x in frames if "result" in x]
        self.assertEqual([x["id"] for x in pongs], ["server-ping-r4-2", "server-ping-r4-3"])
        self.assertIn(b"notifications/message", (dest / "stdout-prefix.bin").read_bytes())

    def test_short_outbound_pipe_writes_are_completed(self):
        write = recorder.os.write
        with patch.object(recorder.os, "write", side_effect=lambda fd, data: write(fd, data[:3])):
            _, r = self.record("notifications", synthetic_state_review=True)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        for observation in r["writes"]:
            self.assertEqual(observation["bytes_written"], observation["intended_bytes"])

    def test_unknown_notifications_requests_and_duplicate_ping(self):
        for scenario in ("bad_notification", "server_request", "progress_timeout", "ping_duplicate"):
            with self.subTest(scenario=scenario):
                self.assert_refused(scenario)

    def test_initialization_ping_and_timeout(self):
        dest, r = self.record("init_ping")
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        pongs = [json.loads((dest / f).read_bytes()) for f in r["files"] if f.startswith("stdin-")]
        self.assertIn({"jsonrpc": "2.0", "id": 7, "result": {}}, pongs)
        _, r = self.assert_refused("init_timeout", window_seconds=0.25)
        self.assertEqual(len(r["calls"]), 1)

    def test_logging_does_not_reset_absolute_watchdog(self):
        _, r = self.assert_refused("logging_timeout", window_seconds=0.25)
        self.assertEqual(r["status"], "timeout")
        call = r["calls"][-1]
        self.assertEqual(call["deadline_monotonic_ns"] - call["dispatch_monotonic_ns"], 250000000)

    def test_crlf_kept_exact_and_blank_line_rejected(self):
        dest, r = self.record("crlf")
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        self.assertTrue((dest / "stdout-prefix.bin").read_bytes().endswith(b"\r\n"))
        self.assert_refused("blank")

    def test_malformed_ambiguous_and_nonfinite_frames(self):
        for scenario in ("malformed", "duplicate_key", "invalid_utf8", "batch", "nonfinite", "ambiguous"):
            with self.subTest(scenario=scenario):
                self.assert_refused(scenario)

    def test_response_ids_and_duplicates_fail_closed(self):
        for scenario in ("wrong_id", "wrong_id_type", "duplicate_response"):
            with self.subTest(scenario=scenario):
                self.assert_refused(scenario, synthetic_state_review=True)

    def test_exact_65536_byte_frame_includes_newline(self):
        dest, r = self.record("exact_cap")
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        frames = [(dest / f).read_bytes() for f in r["files"]
                  if f.startswith("stdout-") and f != "stdout-prefix.bin"]
        self.assertEqual(max(map(len, frames)), 65536)
        self.assertTrue(frames[-1].endswith(b"\n"))

    def test_oversize_retains_only_incomplete_prefix(self):
        dest, r = self.assert_refused("oversize")
        self.assertEqual(r["status"], "oversized_prefix_only")
        stream = (dest / "stdout-prefix.bin").read_bytes()
        init, prefix = stream.split(b"\n", 1)
        self.assertEqual(len(prefix), 65536)
        self.assertFalse(prefix.endswith(b"\n"))
        self.assertLess(len(init), 65536)
        self.assertFalse(r["calls"][-1]["accepted"])

    def test_truncated_frame_and_crash(self):
        for scenario in ("truncated", "crash", "trailing", "after_response_crash"):
            with self.subTest(scenario=scenario):
                self.assert_refused(scenario)

    def test_rpc_tool_error_truncation_version(self):
        for scenario in ("rpc_error", "tool_error", "declared_truncation", "version"):
            with self.subTest(scenario=scenario):
                self.assert_refused(scenario)

    def test_bad_discovery_never_dispatches_state(self):
        dest, r = self.assert_refused("bad_discovery", synthetic_state_review=True)
        self.assertEqual(len(r["calls"]), 2)
        self.assertNotIn(b"get_studio_state", b"".join((dest / f).read_bytes()
                          for f in r["files"] if f.startswith("stdin-")))

    def test_missing_state_identity_never_backfilled(self):
        _, r = self.assert_refused("missing_identity", synthetic_state_review=True)
        self.assertEqual(r["status"], "state_identity_missing_or_mismatch")

    def test_stderr_noise_not_mcp_and_preserved_exactly(self):
        dest, r = self.record("stderr")
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        self.assertEqual((dest / "stderr-prefix.bin").read_bytes(), b"not MCP\r\n\xff")
        self.assertNotIn(b"not MCP", (dest / "stdout-prefix.bin").read_bytes())

    def test_stdout_stderr_and_notification_floods_bounded(self):
        for scenario in ("stdout_flood", "stderr_flood", "notification_flood", "session_flood"):
            with self.subTest(scenario=scenario):
                dest, r = self.assert_refused(scenario)
                self.assertLessEqual((dest / "stdout-prefix.bin").stat().st_size, recorder.SESSION_LIMIT)
                self.assertLessEqual((dest / "stderr-prefix.bin").stat().st_size, recorder.LIMIT)

    def test_real_monotonic_timeout_and_stop(self):
        start = time.monotonic()
        _, r = self.assert_refused("timeout", window_seconds=0.25)
        self.assertEqual(r["status"], "timeout")
        self.assertLess(time.monotonic() - start, 4)
        self.assertFalse(r["calls"][-1]["accepted"])

    def test_independent_watchdog_even_when_validation_stalls(self):
        original = recorder._discovery
        def stalled(*args):
            time.sleep(0.5)
            original(*args)
        with patch.object(recorder, "_discovery", side_effect=stalled):
            _, r = self.assert_refused(window_seconds=0.2, scenario="normal")
        call = r["calls"][-1]
        self.assertIsNotNone(call["watchdog_fired_ns"])
        self.assertGreaterEqual(call["watchdog_fired_ns"], call["deadline_monotonic_ns"])
        self.assertGreaterEqual(call["watchdog_lateness_ns"], 0)
        self.assertFalse(call["accepted"])

    def test_ignore_eof_requires_owned_job_termination(self):
        _, r = self.record("ignore_eof")
        self.assertTrue(r["shutdown"]["root_exit_confirmed"])
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])

    def test_descendant_in_owned_windows_job_is_stopped(self):
        _, r = self.assert_refused("descendant", window_seconds=0.35)
        self.assertEqual(r["status"], "timeout")
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])

    def test_stop_uncertainty_withholds_success(self):
        original = recorder._stop
        def uncertain(*args):
            result = original(*args)  # Actually stop fixture; only the report is fault-injected.
            result["uncertain"] = True
            result["errors"].append("synthetic exit verification unavailable")
            return result
        with patch.object(recorder, "_stop", side_effect=uncertain):
            dest = recorder.run_synthetic(self.parent, "uncertain", window_seconds=1)
        r = recorder.verify_recording(dest)
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertTrue(r["shutdown"]["uncertain"])
        self.assertTrue(r["retained_streams_are_incomplete_failure_evidence"])

    def test_wait_oserror_still_closes_job_and_withholds_success(self):
        stop = recorder._stop
        close = recorder._WindowsJob.close
        closed = []
        def failed_wait(process, job):
            with patch.object(process, "wait", side_effect=OSError("synthetic wait failure")):
                return stop(process, job)
        def tracked_close(job):
            close(job)
            closed.append(job.handle is None)
        with patch.object(recorder, "_stop", side_effect=failed_wait), \
                patch.object(recorder._WindowsJob, "close", tracked_close):
            dest = recorder.run_synthetic(self.parent, "wait-failure", window_seconds=1)
        r = recorder.verify_recording(dest)
        self.assertEqual(closed, [True])
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])
        self.assertIn("synthetic wait failure", r["shutdown"]["errors"])
        self.assertTrue(r["retained_streams_are_incomplete_failure_evidence"])

    def test_silent_upstream_shortening_never_claims_completeness(self):
        _, r = self.record("silent_shortening")
        self.assertEqual(r["status"], "synthetic_discovery_recorded_pause")
        self.assertEqual(r["upstream_completeness"], "unverified")

    def test_new_only_destination_and_tamper_detection(self):
        dest, r = self.record()
        before = {f.name: f.read_bytes() for f in dest.iterdir()}
        with self.assertRaises(FileExistsError):
            recorder.run_synthetic(self.parent, dest.name)
        self.assertEqual(before, {f.name: f.read_bytes() for f in dest.iterdir()})
        (dest / "stdout-prefix.bin").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            recorder.verify_recording(dest)

    def test_storage_failure_stops_child_and_leaves_no_marker(self):
        original = recorder._write_new
        def fail(path, data):
            if path.name.startswith("stdout-"):
                raise OSError("synthetic storage failure")
            return original(path, data)
        stops = []
        stop = recorder._stop
        def tracked_stop(*args):
            result = stop(*args)
            stops.append(result)
            return result
        with patch.object(recorder, "_write_new", side_effect=fail), \
                patch.object(recorder, "_stop", side_effect=tracked_stop):
            with self.assertRaises(recorder.StorageFailure):
                recorder.run_synthetic(self.parent, "storage-failure", window_seconds=1)
        self.assertFalse((self.parent / "storage-failure" / "COMMITTED.json").exists())
        self.assertTrue(stops[0]["tree_exit_confirmed"])

    def test_invalid_limits_and_names_do_not_launch(self):
        with patch.object(recorder.subprocess, "Popen") as spawn:
            for value in (0, -1, 31, float("inf"), float("nan"), True):
                with self.assertRaises(ValueError):
                    recorder.run_synthetic(self.parent, "limits", window_seconds=value)
            for name in ("../escape", "", "C:bad", "a/b"):
                with self.assertRaises(ValueError):
                    recorder.run_synthetic(self.parent, name)
            spawn.assert_not_called()

    def test_job_setup_failure_never_dispatches(self):
        with patch.object(recorder._WindowsJob, "assign", side_effect=OSError("synthetic denial")):
            dest = recorder.run_synthetic(self.parent, "containment-denied", window_seconds=1)
        r = recorder.verify_recording(dest)
        self.assertEqual(r["calls"], [])
        self.assertFalse(any(f.startswith("stdin-") for f in r["files"]))
        self.assertTrue(r["shutdown"]["uncertain"])
        self.assertTrue(r["shutdown"]["root_exit_confirmed"])


class StopTests(unittest.TestCase):
    def test_wait_oserror_preserves_uncertainty_and_tree_verification(self):
        class Process:
            def poll(self):
                return 0
            def wait(self, timeout):
                raise OSError("synthetic wait handle failure")
        class Job:
            assigned = True
            def terminate(self):
                pass
            def active(self):
                return 0
        result = recorder._stop(Process(), Job())
        self.assertTrue(result["uncertain"])
        self.assertTrue(result["root_exit_confirmed"])
        self.assertTrue(result["tree_exit_confirmed"])
        self.assertIn("synthetic wait handle failure", result["errors"])

    def test_failed_kill_and_wait_report_uncertainty(self):
        class Process:
            def poll(self):
                return None
            def kill(self):
                raise OSError("synthetic kill failure")
            def wait(self, timeout):
                raise subprocess.TimeoutExpired("synthetic", timeout)
        result = recorder._stop(Process(), None)
        self.assertTrue(result["uncertain"])
        self.assertFalse(result["root_exit_confirmed"])
        self.assertFalse(result["tree_exit_confirmed"])


if __name__ == "__main__":
    unittest.main()
