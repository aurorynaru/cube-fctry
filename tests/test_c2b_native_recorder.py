import ctypes
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

from tool import c2b_native_recorder as bridge
from tool import c2b_recording_supervisor as recorder
from tests import test_c2b_recording_supervisor as original_tests


@unittest.skipUnless(os.name == "nt", "actual native Windows synthetic recorder required")
class ContainedProtocolTests(unittest.TestCase):
    """Reuse original assertions against R7 as well as preserving all R4/R5 tests."""
    def setUp(self):
        original_tests.SupervisorTests.setUp(self)
        self.patch = patch.object(recorder, "run_synthetic", recorder.run_contained_synthetic)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    record = original_tests.SupervisorTests.record
    assert_refused = original_tests.SupervisorTests.assert_refused


# The two omitted cases inject the LEGACY assignment/wait implementation.
# R7 has separate actual native creation/accounting/closure tests below.
for _name in dir(original_tests.SupervisorTests):
    if _name.startswith("test_") and _name not in {
            "test_job_setup_failure_never_dispatches",
            "test_wait_oserror_still_closes_job_and_withholds_success"}:
        setattr(ContainedProtocolTests, _name, getattr(original_tests.SupervisorTests, _name))


@unittest.skipUnless(os.name == "nt", "actual native Windows synthetic recorder required")
class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def process(self, scenario="normal"):
        process = bridge.SyntheticRecorderProcess(self.directory, scenario)
        self.addCleanup(lambda: process.finish([]))
        return process

    def wait_for(self, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("synthetic checkpoint not reached")

    def assert_clean(self, process, workers=()):
        result = process.finish(list(workers))
        self.assertFalse(result["uncertain"], result)
        self.assertTrue(result["root_exit_confirmed"], result)
        self.assertTrue(result["tree_exit_confirmed"], result)
        self.assertTrue(result["handles_closed"], result)
        self.assertFalse(process.boundary.handles)
        self.assertTrue(all(p.report()["closed"] for p in process.pipes.values()))
        return result

    def record(self, name="record", scenario="normal", **kwargs):
        kwargs.setdefault("window_seconds", 1.5)
        dest = recorder.run_contained_synthetic(self.directory, name, scenario, **kwargs)
        return dest, recorder.verify_recording(dest)

    def test_native_entrypoint_never_uses_popen_or_assignment(self):
        with patch.object(recorder.subprocess, "Popen", side_effect=AssertionError("no fallback")), \
                patch.object(recorder._WindowsJob, "assign", side_effect=AssertionError("no late assign")):
            _, r = self.record(synthetic_state_review=True)
        self.assertEqual(r["status"], "synthetic_sequence_recorded")
        self.assertEqual(r["launch_boundary"], "creation_time_contained_synthetic")
        self.assertTrue(r["containment"]["membership_verified"])
        self.assertEqual(r["containment"]["resume_previous_count"], 1)
        self.assertTrue(r["shutdown"]["handles_closed"])
        for lease in r["pipe_ownership"].values():
            self.assertEqual(lease["events"], ["boundary_to_lease", "native_to_crt", "stream_borrow",
                                              "stream_close", "crt_close"])

    def test_legacy_receipt_is_explicitly_labeled(self):
        dest = recorder.run_synthetic(self.directory, "legacy", window_seconds=1.5)
        self.assertEqual(recorder.verify_recording(dest)["launch_boundary"],
                         "legacy_synthetic_post_popen_assignment")

    def test_closed_controller_before_create_never_calls_native(self):
        p = self.process()
        self.assert_clean(p)
        with patch.object(p.boundary.api, "CreateProcessW") as create:
            self.assertFalse(p.start())
        create.assert_not_called()
        self.assertFalse(p.boundary.report["dispatched"])

    def test_failure_after_create_before_resume_never_executes(self):
        p = self.process("blocked_stdin")
        def checkpoint(phase):
            if phase == "verified":
                raise OSError("injected pre-resume failure")
        with patch.object(p.boundary, "_checkpoint", side_effect=checkpoint), \
                patch.object(p.boundary.api, "ResumeThread") as resume:
            self.assertFalse(p.start())
        resume.assert_not_called()
        self.assertFalse((self.directory / "blocked-stdin.marker").exists())
        self.assert_clean(p)

    def test_crt_conversion_failure_at_each_pipe_retains_exact_owner(self):
        import msvcrt
        for fail_at in (1, 2, 3):
            with self.subTest(pipe=fail_at):
                p = self.process()
                convert = msvcrt.open_osfhandle
                calls = 0
                def injected(handle, flags):
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise OSError("injected conversion failure before transfer")
                    return convert(handle, flags)
                with patch.object(msvcrt, "open_osfhandle", side_effect=injected):
                    self.assertFalse(p.start())
                self.assertFalse(p.boundary.report["dispatched"])
                self.assert_clean(p)
                lease = list(p.pipes.values())[fail_at - 1]
                self.assertIn("native_close", lease.events)
                self.assertNotIn("crt_close", lease.events)

    def test_failure_after_crt_transfer_closes_fd_not_native(self):
        for kind in ("stdin", "stdout", "stderr"):
            with self.subTest(kind=kind):
                p = self.process()
                def fail(phase):
                    if phase == "crt":
                        raise OSError("injected after documented transfer")
                with patch.object(p.pipes[kind], "_checkpoint", side_effect=fail):
                    self.assertFalse(p.start())
                self.assert_clean(p)
                self.assertIn("crt_close", p.pipes[kind].events)
                self.assertNotIn("native_close", p.pipes[kind].events)

    def test_registered_crt_transfer_retires_stale_native_bookkeeping(self):
        import msvcrt
        p = self.process()
        convert = msvcrt.open_osfhandle
        def interrupted_after_registered_return(handle, flags):
            # Deterministic interruption between registered CRT ownership and
            # clearing native bookkeeping. Ownership comes from actual success.
            p.stdin.fd = convert(handle, flags)
            raise KeyboardInterrupt
        with patch.object(msvcrt, "open_osfhandle", side_effect=interrupted_after_registered_return):
            with self.assertRaises(KeyboardInterrupt):
                p.start()
        self.assert_clean(p)
        self.assertEqual(p.stdin.events, ["boundary_to_lease", "crt_close"])

    def test_unregistered_crt_return_is_blocked_not_guessed_or_double_closed(self):
        import msvcrt
        p = self.process("blocked_stdin")
        convert = msvcrt.open_osfhandle
        injector_fds = []
        def unknown_return(handle, flags):
            injector_fds.append(convert(handle, flags))
            raise KeyboardInterrupt  # Boundary never observes a documented return.
        try:
            with patch.object(msvcrt, "open_osfhandle", side_effect=unknown_return):
                with self.assertRaises(KeyboardInterrupt):
                    p.start()
            self.assertTrue(p.finish_result["uncertain"])
            self.assertFalse(p.finish_result["handles_closed"])
            self.assertTrue(p.finish_result["tree_exit_confirmed"])
            self.assertFalse(p.boundary.report["execution_may_have_started"])
            self.assertFalse((self.directory / "blocked-stdin.marker").exists())
            self.assertNotIn("native_close", p.stdin.events)
            self.assertNotIn("crt_close", p.stdin.events)
            for fd in injector_fds:
                os.fstat(fd)  # Unknown handle was not closed based on its value.
        finally:
            # Only the injector knows successful CRT ownership. Release that exact
            # descriptor; the bridge must keep its BLOCKED uncertainty forever.
            for fd in injector_fds:
                os.close(fd)

    def test_unobserved_native_creation_return_never_claims_handle_certainty(self):
        p = self.process("blocked_stdin")
        create = p.boundary.api.CreateProcessW
        injector_handles = []
        def unknown_return(*args):
            self.assertTrue(create(*args))
            info = ctypes.cast(args[-1], ctypes.POINTER(p.boundary.api.ProcessInfo)).contents
            injector_handles.extend((info.process, info.thread))
            raise OSError("injected interruption after native success, before observed return")
        try:
            with patch.object(p.boundary.api, "CreateProcessW", side_effect=unknown_return):
                self.assertFalse(p.start())
            result = p.finish([])
            self.assertTrue(result["uncertain"])
            self.assertFalse(result["handles_closed"])
            self.assertFalse(result["root_exit_confirmed"])
            self.assertTrue(result["tree_exit_confirmed"])
            self.assertFalse((self.directory / "blocked-stdin.marker").exists())
            self.assertEqual(p.boundary.api.WaitForSingleObject(injector_handles[0], 1000), 0)
        finally:
            for handle in injector_handles:
                p.boundary.api.checked(p.boundary.api.CloseHandle(handle))

    def test_stream_creation_failure_cannot_take_descriptor(self):
        real_file = bridge.io.FileIO
        for fail_at in (1, 2, 3):
            with self.subTest(pipe=fail_at):
                p = self.process()
                calls = 0
                def fail(fd, mode, *, closefd):
                    nonlocal calls
                    self.assertFalse(closefd)
                    calls += 1
                    if calls == fail_at:
                        raise OSError("injected FileIO constructor failure")
                    return real_file(fd, mode, closefd=closefd)
                with patch.object(bridge.io, "FileIO", side_effect=fail):
                    self.assertFalse(p.start())
                self.assert_clean(p)
                lease = list(p.pipes.values())[fail_at - 1]
                self.assertEqual(lease.events, ["boundary_to_lease", "native_to_crt", "crt_close"])

    def test_failure_after_stream_creation_closes_stream_and_fd_once(self):
        p = self.process()
        with patch.object(p.stdout, "_checkpoint", side_effect=OSError("after stream")):
            self.assertFalse(p.start())
        # This injection is at the earlier CRT checkpoint; explicitly test stream too.
        p = self.process()
        def fail(phase):
            if phase == "stream":
                raise OSError("after stream")
        with patch.object(p.stdout, "_checkpoint", side_effect=fail):
            self.assertFalse(p.start())
        self.assert_clean(p)
        self.assertEqual(p.stdout.events.count("stream_close"), 1)
        self.assertEqual(p.stdout.events.count("crt_close"), 1)

    def test_reader_failure_refuses_and_retains_verified_receipt(self):
        with patch.object(recorder.os, "read", side_effect=OSError("injected reader error")):
            _, r = self.record()
        self.assertIn("pipe_failure", r["status"])
        self.assertTrue(all(not call["accepted"] for call in r["calls"]))
        self.assertEqual(r["writes"], [])
        self.assertTrue(r["retained_streams_are_incomplete_failure_evidence"])
        self.assertFalse(r["shutdown"]["uncertain"])
        self.assertTrue(r["shutdown"]["handles_closed"])

    def test_actual_blocked_stdin_is_unblocked_by_watchdog_tree_stop(self):
        frame = recorder._json_frame
        def oversized_test_request(value):
            raw = frame(value)
            return raw[:-1] + b" " * (1024 * 1024) + b"\n" if value.get("method") == "initialize" else raw
        with patch.object(recorder, "_json_frame", side_effect=oversized_test_request):
            dest, r = self.record(scenario="blocked_stdin", window_seconds=0.35)
        self.assertTrue((dest / "blocked-stdin.marker").exists())
        self.assertEqual(r["status"], "timeout")
        self.assertIsNotNone(r["calls"][0]["watchdog_fired_ns"])
        self.assertIsNotNone(r["writes"][0]["write_finished_ns"])
        self.assertLess(r["writes"][0]["bytes_written"], r["writes"][0]["intended_bytes"])
        self.assertEqual(r["writes"][0]["error"], "stdin_write_failure")
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertFalse(r["shutdown"]["uncertain"], r["shutdown"])

    def test_root_exit_does_not_mean_descendant_or_pipe_exit(self):
        p = self.process("inherited_stdout")
        self.assertTrue(p.start(), p.boundary.report)
        capture = recorder._Capture()
        session = recorder._Session(p, None, self.directory, capture, 1.5)
        readers = [threading.Thread(target=capture.read, args=(p.pipes[k], k))
                   for k in ("stdout", "stderr")]
        for reader in readers:
            reader.start()
        try:
            session.request("initialize", {}, recorder._initialize)
            session.request("tools/call", {"name": "list_roblox_studios", "arguments": {}},
                            recorder._discovery)
            self.wait_for(lambda: p.poll() is not None)
            self.wait_for(lambda: (self.directory / "pipe-holder.marker").exists())
            self.assertEqual(p.poll(), 0)
            self.assertEqual(p.boundary.job.active(), 1)
            self.assertFalse(capture.stdout_eof)
            self.assertTrue(readers[0].is_alive())
        finally:
            self.assert_clean(p, readers + session.workers)
        self.assertTrue(capture.stdout_eof)
        self.assertTrue(capture.stderr_eof)

    def test_eager_descendant_runs_without_stdin(self):
        p = self.process("eager_stdio")
        self.assertTrue(p.start(), p.boundary.report)
        try:
            try:
                self.wait_for(lambda: (self.directory / "pipe-holder.marker").exists())
            except AssertionError:
                self.fail(f"eager fixture files={list(self.directory.iterdir())}, "
                          f"root={p.poll()}, active={p.boundary.job.active()}, "
                          f"metadata={(self.directory / 'pipe-holder-handle.json').read_text()}")
            self.assertEqual(p.boundary.job.active(), 2)
        finally:
            p.stop_tree()
            errors = p.stderr.stream.read()
            self.assert_clean(p)
            self.assertEqual(errors, b"")

    def test_shutdown_races_with_reader_writer_completion(self):
        for index in range(5):
            directory = self.directory / str(index)
            directory.mkdir()
            p = bridge.SyntheticRecorderProcess(directory)
            self.assertTrue(p.start())
            capture = recorder._Capture()
            session = recorder._Session(p, None, directory, capture, 1.5)
            readers = [threading.Thread(target=capture.read, args=(p.pipes[k], k))
                       for k in ("stdout", "stderr")]
            for reader in readers:
                reader.start()
            gate = threading.Barrier(2)
            def shutdown():
                gate.wait()
                session.stop()
            stopper = threading.Thread(target=shutdown)
            stopper.start()
            gate.wait()
            writer, _ = session.write({"jsonrpc": "2.0", "method": "notifications/initialized"})
            stopper.join(timeout=2)
            self.assertFalse(stopper.is_alive())
            self.assert_clean(p, readers + session.workers)
            self.assertFalse(writer.is_alive())

    def test_repeated_close_and_immediate_native_handle_invalidity(self):
        import msvcrt
        p = self.process()
        self.assertTrue(p.start())
        handles = [msvcrt.get_osfhandle(pipe.fileno()) for pipe in p.pipes.values()]
        handles += [p.boundary.handles["process"], p.boundary.job.handle]
        result = self.assert_clean(p)
        for handle in handles:
            flags = w.DWORD()
            self.assertFalse(p.boundary.api.GetHandleInformation(handle, ctypes.byref(flags)))
            self.assertEqual(ctypes.get_last_error(), 6)
        events = p.ownership_report()
        for _ in range(3):
            self.assertIs(p.finish([]), result)
            p.stdin.close()
        self.assertEqual(p.ownership_report(), events)

    def test_stream_is_borrowing_and_crt_handles_stay_noninheritable(self):
        p = self.process()
        self.assertTrue(p.start())
        import msvcrt
        for pipe in p.pipes.values():
            self.assertFalse(pipe.stream.closefd)
            flags = w.DWORD()
            p.boundary.api.checked(p.boundary.api.GetHandleInformation(
                msvcrt.get_osfhandle(pipe.fileno()), ctypes.byref(flags)))
            self.assertFalse(flags.value & 1)
        fd = p.stdin.fileno()
        p.stdin.stream.close()  # Borrowed stream closure must not close the fd.
        os.fstat(fd)
        self.assert_clean(p)
        with self.assertRaises(OSError):
            os.fstat(fd)

    def test_repeated_lease_close_never_closes_a_reused_descriptor(self):
        p = self.process()
        self.assertTrue(p.start())
        fd = p.stdin.fileno()
        self.assert_clean(p)
        sentinel = os.open(self.directory / "unrelated.bin", os.O_CREAT | os.O_RDWR | os.O_BINARY)
        # Reuse the retired descriptor deliberately using an independently owned
        # file. No stale native handle is queried or closed to infer ownership.
        target = sentinel if sentinel == fd else os.dup2(sentinel, fd)
        try:
            p.stdin.close()
            p.finish([])
            self.assertEqual(os.write(target, b"unrelated survives"), 18)
            os.fstat(target)
        finally:
            os.close(target)
            if sentinel != target:
                os.close(sentinel)

    def test_crt_close_failure_is_retired_not_retried_and_never_success(self):
        close = bridge.os.close
        calls = []
        def fail_after_close(fd):
            close(fd)
            calls.append(fd)
            raise OSError("synthetic close report failure after actual close")
        with patch.object(bridge.os, "close", side_effect=fail_after_close):
            _, r = self.record()
        self.assertEqual(len(calls), 3)
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertFalse(r["shutdown"]["handles_closed"])
        self.assertTrue(all(p["state"] == "close_uncertain" for p in r["pipe_ownership"].values()))

    def test_accounting_failure_is_propagated_even_after_root_and_handles_exit(self):
        with patch.object(bridge._RecorderBoundary, "_checkpoint"):
            with patch.object(recorder._WindowsJob, "active", side_effect=OSError("accounting unavailable")):
                _, r = self.record()
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertTrue(r["shutdown"]["root_exit_confirmed"])
        self.assertFalse(r["shutdown"]["tree_exit_confirmed"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertTrue(r["containment"]["uncertain"])
        self.assertTrue(r["retained_streams_are_incomplete_failure_evidence"])

    def test_pre_resume_conversion_failure_has_no_requests_and_clean_failure_receipt(self):
        import msvcrt
        with patch.object(msvcrt, "open_osfhandle", side_effect=OSError("CRT refused")):
            _, r = self.record()
        self.assertEqual(r["status"], "contained_setup_refused")
        self.assertEqual(r["calls"], [])
        self.assertEqual(r["writes"], [])
        self.assertFalse(r["containment"]["execution_may_have_started"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertFalse(r["shutdown"]["uncertain"])
        self.assertTrue(r["retained_streams_are_incomplete_failure_evidence"])

    def test_resume_anomaly_retains_uncertainty_in_receipt(self):
        resume = bridge.SyntheticRecorderProcess.start
        def anomalous(p):
            with patch.object(p.boundary.api, "ResumeThread", return_value=0):
                return resume(p)
        with patch.object(bridge.SyntheticRecorderProcess, "start", anomalous):
            _, r = self.record()
        self.assertEqual(r["status"], "termination_uncertain:contained_setup_refused")
        self.assertTrue(r["containment"]["membership_verified"])
        self.assertTrue(r["containment"]["execution_may_have_started"])
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertEqual(r["writes"], [])

    def test_native_handle_close_failure_cannot_be_promoted_by_crt_closure(self):
        start = bridge.SyntheticRecorderProcess.start
        instances = []
        def close_report_failure(p):
            instances.append(p)
            real_close = p.boundary.api.CloseHandle
            def close_but_fail(handle):
                real_close(handle)
                ctypes.set_last_error(6)
                return 0
            result = start(p)
            p.boundary.api.CloseHandle = close_but_fail
            return result
        with patch.object(bridge.SyntheticRecorderProcess, "start", close_report_failure):
            _, r = self.record()
        self.assertTrue(r["shutdown"]["uncertain"])
        self.assertFalse(r["shutdown"]["handles_closed"])
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        # Injector actually closed native handles. Never retry stale values.
        instances[0].boundary.handles.clear()

    def test_graceful_wait_error_is_not_erased_by_later_clean_stop(self):
        with patch.object(bridge.SyntheticRecorderProcess, "wait", side_effect=OSError("wait unavailable")):
            _, r = self.record()
        self.assertTrue(r["status"].startswith("termination_uncertain:"))
        self.assertTrue(r["shutdown"]["tree_exit_confirmed"])
        self.assertTrue(r["shutdown"]["handles_closed"])
        self.assertIn("graceful_root_wait_failed: wait unavailable", r["shutdown"]["errors"])

    def test_stream_close_failure_still_closes_crt_and_other_pipes(self):
        p = self.process()
        self.assertTrue(p.start())
        stream = p.stdout.stream
        class FailedClose:
            def close(self):
                stream.close()
                raise OSError("stream close uncertain")
        p.stdout.stream = FailedClose()
        result = p.finish([])
        self.assertTrue(result["uncertain"])
        self.assertFalse(result["handles_closed"])
        self.assertIn("crt_close", p.stdout.events)
        self.assertTrue(p.stdin.report()["closed"])
        self.assertTrue(p.stderr.report()["closed"])

    def test_keyboard_interrupt_after_transfer_cleans_suspended_root(self):
        p = self.process("blocked_stdin")
        with patch.object(p.stdout, "_checkpoint", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                p.start()
        self.assert_clean(p)
        self.assertFalse(p.boundary.report["execution_may_have_started"])
        self.assertFalse((self.directory / "blocked-stdin.marker").exists())

    def test_final_evidence_commit_failure_never_returns_success(self):
        write = recorder._write_new
        instances = []
        start = bridge.SyntheticRecorderProcess.start
        def track(p):
            instances.append(p)
            return start(p)
        def fail(path, data):
            if path.name == "COMMITTED.json":
                raise OSError("synthetic commit failure")
            return write(path, data)
        with patch.object(bridge.SyntheticRecorderProcess, "start", track), \
                patch.object(recorder, "_write_new", side_effect=fail):
            with self.assertRaises(OSError):
                self.record()
        self.assertFalse((self.directory / "record/COMMITTED.json").exists())
        self.assertTrue(instances[0].finish_result["handles_closed"])
        with self.assertRaises(FileNotFoundError):
            recorder.verify_recording(self.directory / "record")

    def test_unjoined_borrower_quarantines_descriptors(self):
        p = self.process()
        self.assertTrue(p.start())
        release = threading.Event()
        worker = threading.Thread(target=release.wait)
        worker.start()
        try:
            result = p.finish([worker])
            self.assertTrue(result["uncertain"])
            self.assertFalse(result["handles_closed"])
            self.assertTrue(all(pipe.fd is not None for pipe in p.pipes.values()))
        finally:
            release.set()
            worker.join(timeout=1)
            self.assertFalse(worker.is_alive())
            # Test owns the now-confirmed borrowers; release quarantined resources
            # without rewriting/promoting the original uncertain result.
            for pipe in p.pipes.values():
                pipe.close()
        self.assertTrue(p.finish([])["uncertain"])

    def test_no_arbitrary_executable_command_environment_or_live_paths(self):
        for value in ("StudioMCP.exe", "mcp.bat", "normal --live", "pipe_holder"):
            with self.assertRaises(ValueError):
                bridge.SyntheticRecorderProcess(self.directory, value)
        for key in ("executable", "command", "argv", "environment", "shell", "studio_path", "live"):
            with self.assertRaises(TypeError):
                bridge.SyntheticRecorderProcess(self.directory, **{key: "anything"})

    def test_abrupt_controller_death_after_crt_transfer_and_with_descendant(self):
        api = bridge.SyntheticBoundary(self.directory).api
        api.dll.GetCurrentProcess.restype = w.HANDLE
        api.dll.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE,
                                           ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
        api.dll.DuplicateHandle.restype = w.BOOL
        fixture = Path(__file__).parent / "fixtures/c2b_recorder_controller.py"
        for phase in ("crt", "resumed"):
            with self.subTest(phase=phase):
                directory = self.directory / phase
                directory.mkdir()
                controller = subprocess.Popen([sys.executable, "-I", "-S", "-u", str(fixture),
                                               str(directory), phase], stdin=subprocess.DEVNULL,
                                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                              close_fds=True)
                root, descendant = w.HANDLE(), w.HANDLE()
                try:
                    ready = directory / "ready.json"
                    def ready_or_failed():
                        if controller.poll() is not None:
                            self.fail(f"controller exited: {controller.communicate(timeout=5)!r}")
                        return ready.exists() and ready.stat().st_size > 2
                    self.wait_for(ready_or_failed)
                    handle = json.loads(ready.read_text())["process"]
                    api.checked(api.dll.DuplicateHandle(int(controller._handle), handle,
                        api.dll.GetCurrentProcess(), ctypes.byref(root), 0x100040, False, 0))
                    if phase == "resumed":
                        api.checked(api.dll.DuplicateHandle(int(controller._handle),
                            json.loads(ready.read_text())["descendant"], api.dll.GetCurrentProcess(),
                            ctypes.byref(descendant), 0x100000, False, 0))
                    else:
                        self.assertFalse((directory / "pipe-holder.marker").exists())
                    controller.kill()
                    controller.wait(timeout=5)
                    self.assertEqual(api.WaitForSingleObject(root, 5000), 0)
                    if descendant.value:
                        self.assertEqual(api.WaitForSingleObject(descendant, 5000), 0)
                    _, errors = controller.communicate(timeout=5)
                    self.assertNotIn(b"Traceback", errors)
                    self.assertFalse((directory / "COMMITTED.json").exists())
                finally:
                    if controller.poll() is None:
                        controller.kill()
                    controller.communicate(timeout=5)
                    for handle in (root, descendant):
                        if handle.value:
                            api.checked(api.CloseHandle(handle))


if __name__ == "__main__":
    unittest.main()
