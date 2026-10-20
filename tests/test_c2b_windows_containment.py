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

from tool import c2b_windows_containment as containment


@unittest.skipUnless(os.name == "nt", "native Windows creation-time containment required")
class ContainmentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        (self.directory / "descendant").mkdir()
        self.boundary = containment.SyntheticBoundary(self.directory)
        self.addCleanup(self.boundary.close)

    def wait_for(self, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if predicate():
                return
            time.sleep(0.005)
        self.fail("bounded synthetic checkpoint not reached")

    def marker(self):
        return (self.directory / "first-instruction.marker").exists()

    def assert_clean(self, boundary=None):
        boundary = boundary or self.boundary
        cleanup = boundary.close()
        self.assertTrue(cleanup["root_exit_confirmed"], cleanup)
        self.assertTrue(cleanup["tree_exit_confirmed"], cleanup)
        self.assertTrue(cleanup["handles_closed"], cleanup)
        self.assertFalse(cleanup["uncertain"], cleanup)
        self.assertFalse(boundary.attribute_initialized)
        self.assertFalse(boundary.handles)

    def test_creation_membership_and_no_marker_before_checked_resume(self):
        b = self.boundary
        self.assertTrue(b.create(), b.report)
        self.assertTrue(b.report["membership_verified"])
        self.assertEqual(b.report["phase"], "contained_suspended")
        self.assertEqual(b.job.active(), 1)
        time.sleep(0.1)
        self.assertFalse(self.marker())
        self.assertTrue(b.resume(), b.report)
        self.assertEqual(b.report["resume_previous_count"], 1)
        self.assertNotIn("thread", b.handles)
        self.wait_for(self.marker)
        self.assert_clean()

    def test_eager_descendant_is_contained_and_tree_verified_empty(self):
        b = containment.SyntheticBoundary(self.directory, "eager")
        self.addCleanup(b.close)
        self.assertTrue(b.create(), b.report)
        self.assertFalse(self.marker())
        self.assertTrue(b.resume(), b.report)
        self.wait_for(lambda: (self.directory / "descendant/descendant.marker").exists())
        self.assertEqual(b.job.active(), 2)
        self.assert_clean(b)

    def test_root_exit_with_inherited_pipe_descendant(self):
        b = containment.SyntheticBoundary(self.directory, "inherited_pipe")
        self.addCleanup(b.close)
        self.assertTrue(b.create(), b.report)
        self.assertTrue(b.resume(), b.report)
        self.wait_for(lambda: not b._running("process"))
        self.wait_for(lambda: (self.directory / "descendant/descendant.marker").exists())
        self.assertEqual(b.job.active(), 1)
        self.assertFalse(b.read_available("stdout")[1])
        b.job.terminate()
        self.wait_for(lambda: b.job.active() == 0)
        # Drain only this tiny controlled diagnostic output, bounded iterations.
        self.wait_for(lambda: b.read_available("stdout")[1])
        self.assert_clean(b)

    def test_explicit_pipes_and_noninheritable_owned_handles(self):
        b = self.boundary
        self.assertTrue(b.create(), b.report)
        self.assertEqual(set(b.handles), {"process", "thread", "stdin", "stdout", "stderr"})
        for handle in (*b.handles.values(), b.job.handle):
            flags = w.DWORD()
            b.api.checked(b.api.GetHandleInformation(handle, ctypes.byref(flags)))
            self.assertFalse(flags.value & 1)
        self.assertTrue(b.resume())
        self.wait_for(self.marker)
        captured = {"stdout": b"", "stderr": b""}
        def read_both():
            for kind in captured:
                captured[kind] += b.read_available(kind)[0]
            return b"sentinel_open" in captured["stdout"] and b"synthetic stderr" in captured["stderr"]
        self.wait_for(read_both)
        self.assertEqual(json.loads(captured["stdout"])["sentinel_open"], False)
        self.assertTrue(json.loads(captured["stdout"])["standard_handles_are_pipes"])
        self.assertEqual(captured["stderr"], b"synthetic stderr\n")
        b.api.dll.WriteFile.argtypes = [w.HANDLE, ctypes.c_void_p, w.DWORD,
                                        ctypes.POINTER(w.DWORD), ctypes.c_void_p]
        b.api.dll.WriteFile.restype = w.BOOL
        written = w.DWORD()
        b.api.checked(b.api.dll.WriteFile(b.handles["stdin"], b"Q", 1, ctypes.byref(written), None))
        self.assertEqual(written.value, 1)
        self.wait_for(lambda: (self.directory / "stdin-received.marker").exists())
        self.assert_clean()

    def test_unlisted_inheritable_handle_not_in_child(self):
        # A live event is an inheritable sentinel; check it in the parent after
        # cleanup to ensure boundary never closes unrelated handles.
        api = self.boundary.api.dll
        api.CreateEventW.argtypes = [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
        api.CreateEventW.restype = w.HANDLE
        sentinel = api.CreateEventW(None, True, False, None)
        self.assertTrue(sentinel)
        self.addCleanup(lambda: self.boundary.api.CloseHandle(sentinel))
        self.boundary.api.checked(self.boundary.api.SetHandleInformation(sentinel, 1, 1))
        with patch.dict(os.environ, {"C2B_R6_SENTINEL": str(sentinel)}):
            self.assertTrue(self.boundary.create(), self.boundary.report)
        self.assertTrue(self.boundary.resume())
        data = bytearray()
        def output():
            data.extend(self.boundary.read_available("stdout")[0])
            return b"\n" in data
        self.wait_for(output)
        self.assertFalse(json.loads(data)["sentinel_open"])
        self.assert_clean()
        flags = w.DWORD()
        self.assertTrue(self.boundary.api.GetHandleInformation(sentinel, ctypes.byref(flags)))

    def test_creation_assignment_failure_has_no_fallback(self):
        b = self.boundary
        with patch.object(b.api, "CreateProcessW", return_value=0) as create:
            self.assertFalse(b.create())
        self.assertEqual(create.call_count, 1)
        self.assertFalse(self.marker())
        self.assertFalse(b.report["dispatched"])
        self.assert_clean()

    def test_failed_creation_with_nonzero_outputs_withholds_handle_certainty(self):
        b = self.boundary
        create = b.api.CreateProcessW
        owned_by_injector = []
        def partial_result(*args):
            self.assertTrue(create(*args))
            info = ctypes.cast(args[-1], ctypes.POINTER(b.api.ProcessInfo)).contents
            # Injector knows native creation succeeded; the boundary sees a
            # failure and cannot assume these numeric outputs are owned handles.
            owned_by_injector.extend((info.process, info.thread))
            ctypes.set_last_error(5)
            return 0  # Inject partial-return failure after real suspended creation.
        try:
            with patch.object(b.api, "CreateProcessW", side_effect=partial_result):
                self.assertFalse(b.create())
            self.assertFalse(self.marker())
            self.assertFalse(b.report["execution_may_have_started"])
            self.assertTrue(b.report["failed_creation_handles_unverified"])
            self.assertTrue(b.report["uncertain"])
            self.assertTrue(b.report["cleanup"]["tree_exit_confirmed"])
            self.assertFalse(b.report["cleanup"]["handles_closed"])
            self.assertEqual(b.api.WaitForSingleObject(owned_by_injector[0], 1000), 0)
        finally:
            for handle in owned_by_injector:
                b.api.checked(b.api.CloseHandle(handle))

    def test_failed_creation_outputs_never_close_unrelated_handles(self):
        b = self.boundary
        b.api.dll.CreateEventW.argtypes = [ctypes.c_void_p, w.BOOL, w.BOOL, w.LPCWSTR]
        b.api.dll.CreateEventW.restype = w.HANDLE
        sentinel = b.api.dll.CreateEventW(None, True, False, None)
        self.assertTrue(sentinel)
        self.addCleanup(lambda: b.api.checked(b.api.CloseHandle(sentinel)))
        def failed_with_unrelated_outputs(*args):
            info = ctypes.cast(args[-1], ctypes.POINTER(b.api.ProcessInfo)).contents
            info.process = info.thread = sentinel
            ctypes.set_last_error(5)
            return 0
        with patch.object(b.api, "CreateProcessW", side_effect=failed_with_unrelated_outputs):
            self.assertFalse(b.create())
        flags = w.DWORD()
        self.assertTrue(b.api.GetHandleInformation(sentinel, ctypes.byref(flags)))
        self.assertTrue(b.report["uncertain"])
        self.assertFalse(b.report["cleanup"]["handles_closed"])
        self.assertFalse(self.marker())

    def test_job_list_failure_never_calls_create_or_assign(self):
        b = self.boundary
        update = b.api.UpdateProcThreadAttribute
        def reject_job(*args):
            if args[2] == containment.JOB_LIST:
                ctypes.set_last_error(87)
                return 0
            return update(*args)
        with patch.object(b.api, "UpdateProcThreadAttribute", side_effect=reject_job), \
                patch.object(b.api, "CreateProcessW") as create:
            self.assertFalse(b.create())
        create.assert_not_called()
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_membership_verification_failure_kills_suspended_root(self):
        b = self.boundary
        with patch.object(b, "_membership", side_effect=OSError("injected verification failure")):
            self.assertFalse(b.create())
        self.assertFalse(b.report["membership_verified"])
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_resume_failure_zero_marker_and_closed_handles(self):
        b = self.boundary
        self.assertTrue(b.create())
        with patch.object(b.api, "ResumeThread", return_value=0xFFFFFFFF):
            self.assertFalse(b.resume())
        self.assertFalse(b.report["dispatched"])
        self.assertTrue(b.report["uncertain"])  # No promotion of injected API failure.
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_resume_exception_is_uncertain_even_if_native_call_was_not_made(self):
        b = self.boundary
        self.assertTrue(b.create())
        with patch.object(b.api, "ResumeThread", side_effect=OSError("injected resume exception")):
            self.assertFalse(b.resume())
        self.assertTrue(b.report["execution_may_have_started"])
        self.assertTrue(b.report["uncertain"])
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_thread_close_failure_after_real_resume_refuses_success(self):
        b = self.boundary
        self.assertTrue(b.create())
        close = b._close_handle
        def fail_once(name):
            if name == "thread":
                raise OSError("injected primary thread close failure")
            return close(name)
        with patch.object(b, "_close_handle", side_effect=fail_once):
            self.assertFalse(b.resume())
        self.assertEqual(b.report["resume_previous_count"], 1)
        self.assertTrue(b.report["membership_verified"])
        self.assertTrue(b.report["execution_may_have_started"])
        self.assertTrue(b.report["uncertain"])
        # The injected close refuses both cleanup attempts; close the exact owned
        # retained thread handle once, after restoring the functioning API.
        self.assertIn("thread", b.handles)
        close("thread")
        self.assertFalse(b.report["cleanup"]["handles_closed"])

    def test_second_membership_check_failure_prevents_native_resume(self):
        b = self.boundary
        self.assertTrue(b.create())
        with patch.object(b, "_membership", side_effect=OSError("injected second membership failure")), \
                patch.object(b.api, "ResumeThread") as resume:
            self.assertFalse(b.resume())
        resume.assert_not_called()
        self.assertFalse(self.marker())
        self.assertFalse(b.report["execution_may_have_started"])
        self.assert_clean()

    def test_unexpected_resume_counts_refuse(self):
        for count in (0, 2):
            with self.subTest(count=count):
                b = containment.SyntheticBoundary(self.directory)
                self.addCleanup(b.close)
                self.assertTrue(b.create())
                with patch.object(b.api, "ResumeThread", return_value=count):
                    self.assertFalse(b.resume())
                self.assertFalse(b.report["dispatched"])
                self.assertTrue(b.report["uncertain"])
                self.assertFalse(self.marker())
                self.assert_clean(b)

    def test_child_terminated_during_setup_runs_no_python_marker(self):
        b = self.boundary
        def kill_at_created(phase):
            if phase == "created":
                b.api.checked(b.api.TerminateProcess(b.handles["process"], 17))
                self.assertEqual(b.api.WaitForSingleObject(b.handles["process"], 1000), 0)
        with patch.object(b, "_checkpoint", side_effect=kill_at_created):
            self.assertFalse(b.create())
        self.assertFalse(self.marker())
        self.assertFalse(b.report["dispatched"])
        self.assert_clean()

    def test_child_exit_before_resume_refuses(self):
        b = self.boundary
        self.assertTrue(b.create())
        b.api.checked(b.api.TerminateProcess(b.handles["process"], 17))
        self.assertEqual(b.api.WaitForSingleObject(b.handles["process"], 1000), 0)
        self.assertFalse(b.resume())
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_natural_exit_after_resume(self):
        b = containment.SyntheticBoundary(self.directory, "exit")
        self.addCleanup(b.close)
        self.assertTrue(b.create())
        self.assertTrue(b.resume())
        self.wait_for(lambda: not b._running("process"))
        self.assertTrue(self.marker())
        self.assert_clean(b)

    def test_partial_pipe_creation_closes_prior_handles(self):
        b = self.boundary
        original = b.api.CreatePipe
        calls = 0
        def fail_second(*args):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("injected pipe creation failure")
            return original(*args)
        with patch.object(b.api, "CreatePipe", side_effect=fail_second):
            self.assertFalse(b.create())
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_attribute_initialization_failure_closes_pipes(self):
        b = self.boundary
        with patch.object(b.api, "InitializeProcThreadAttributeList", return_value=0):
            self.assertFalse(b.create())
        self.assertFalse(self.marker())
        self.assert_clean()

    def test_job_configuration_failure_no_child(self):
        b = self.boundary
        with patch.object(containment._CreationJob, "configure", side_effect=OSError("injected job setup")), \
                patch.object(b.api, "CreateProcessW") as create:
            self.assertFalse(b.create())
        create.assert_not_called()
        self.assert_clean()

    def test_close_handle_error_is_retained_as_uncertain(self):
        b = self.boundary
        self.assertTrue(b.create())
        close = b.api.CloseHandle
        def close_but_report_failure(handle):
            close(handle)  # No real resource is stranded by the injected report.
            return 0
        with patch.object(b.api, "CloseHandle", side_effect=close_but_report_failure):
            result = b.close()
        self.assertTrue(result["uncertain"])
        self.assertFalse(result["handles_closed"])
        self.assertTrue(result["tree_exit_confirmed"])
        self.assertFalse(self.marker())
        # Remove injected stale bookkeeping only; never close recycled values.
        b.handles.clear()

    def test_job_query_failure_never_claims_tree_exit(self):
        b = self.boundary
        self.assertTrue(b.create())
        with patch.object(b.job, "active", side_effect=OSError("injected accounting failure")):
            result = b.close()
        self.assertTrue(result["uncertain"])
        self.assertFalse(result["tree_exit_confirmed"])
        self.assertTrue(result["handles_closed"])
        self.assertFalse(self.marker())

    def test_termination_failure_uses_only_owned_root_handle_and_refuses_certainty(self):
        b = self.boundary
        self.assertTrue(b.create())
        with patch.object(b.job, "terminate", side_effect=OSError("injected termination failure")):
            result = b.close()
        self.assertTrue(result["uncertain"])
        self.assertTrue(result["root_exit_confirmed"])
        self.assertTrue(result["tree_exit_confirmed"])
        self.assertFalse(self.marker())

    def test_owned_handles_really_invalid_after_close(self):
        b = self.boundary
        self.assertTrue(b.create())
        handles = [*b.handles.values(), b.job.handle]
        self.assert_clean()
        for handle in handles:
            flags = w.DWORD()
            self.assertFalse(b.api.GetHandleInformation(handle, ctypes.byref(flags)))
            self.assertEqual(ctypes.get_last_error(), 6)

    def test_job_configuration_and_internal_close_failure_retains_ownership(self):
        b = self.boundary
        configure = containment._CreationJob.configure
        seen = []
        def allocate_then_fail(job):
            configure(job)
            seen.append(job.handle)
            raise OSError("injected post-allocation configuration/close failure")
        with patch.object(containment._CreationJob, "configure", side_effect=allocate_then_fail, autospec=True):
            self.assertFalse(b.create())
        self.assertEqual(len(seen), 1)
        self.assertFalse(self.marker())
        self.assert_clean()
        flags = w.DWORD()
        self.assertFalse(b.api.GetHandleInformation(seen[0], ctypes.byref(flags)))

    def test_watchdog_and_shutdown_race_is_serialized(self):
        b = self.boundary
        self.assertTrue(b.create())
        self.assertTrue(b.resume())
        results = []
        guard = threading.Timer(0.02, lambda: results.append(b.close()))
        guard.start()
        results.append(b.close())
        guard.join(timeout=2)
        self.assertFalse(guard.is_alive())
        self.assertEqual(len(results), 2)
        self.assertIs(results[0], results[1])
        self.assert_clean()

    def test_shutdown_before_resume_prevents_dispatch(self):
        b = self.boundary
        self.assertTrue(b.create())
        self.assert_clean()
        with self.assertRaises(ValueError):
            b.resume()
        self.assertFalse(self.marker())

    def test_shutdown_before_create_prevents_new_resource_ownership(self):
        b = self.boundary
        self.assert_clean()
        with patch.object(b.api, "CreateProcessW") as create:
            with self.assertRaises(ValueError):
                b.create()
        create.assert_not_called()
        self.assertFalse(b.handles)
        self.assertFalse(self.marker())

    def test_no_executable_argv_or_live_option(self):
        for scenario in ("StudioMCP.exe", "mcp.bat", "cmd.exe", "marker --live"):
            with self.assertRaises(ValueError):
                containment.SyntheticBoundary(self.directory, scenario)
        for key in ("executable", "argv", "command", "live"):
            with self.assertRaises(TypeError):
                containment.SyntheticBoundary(self.directory, **{key: "anything"})

    def controller(self, phase):
        helper = Path(__file__).parent / "fixtures/c2b_containment_controller.py"
        process = subprocess.Popen([sys.executable, "-I", "-S", "-u", str(helper),
                                    str(self.directory), phase], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   close_fds=True)
        def cleanup():
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=5)
        self.addCleanup(cleanup)
        return process

    def test_controller_death_at_creation_checkpoints(self):
        api = self.boundary.api
        api.dll.GetCurrentProcess.restype = w.HANDLE
        api.dll.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE,
                                           ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
        api.dll.DuplicateHandle.restype = w.BOOL
        for phase in ("before_create", "create_return_gap", "created", "verified", "resumed"):
            with self.subTest(phase=phase):
                for name in ("ready.json", "first-instruction.marker",
                             "descendant/first-instruction.marker", "descendant/descendant.marker",
                             "descendant-handle.json"):
                    (self.directory / name).unlink(missing_ok=True)
                controller = self.controller(phase)
                ready = self.directory / "ready.json"
                self.wait_for(lambda: ready.exists() and ready.stat().st_size > 2)
                handles = json.loads(ready.read_text())
                observer = w.HANDLE()
                descendant = w.HANDLE()
                if "process" in handles:
                    api.checked(api.dll.DuplicateHandle(int(controller._handle), handles["process"],
                        api.dll.GetCurrentProcess(), ctypes.byref(observer), 0x100040, False, 0))
                try:
                    if phase == "resumed":
                        self.wait_for(lambda: (self.directory / "descendant/descendant.marker").exists())
                        child_handles = self.directory / "descendant-handle.json"
                        self.wait_for(lambda: child_handles.exists() and child_handles.stat().st_size > 2)
                        child_handle = json.loads(child_handles.read_text())["process"]
                        api.checked(api.dll.DuplicateHandle(observer, child_handle,
                            api.dll.GetCurrentProcess(), ctypes.byref(descendant), 0x100000, False, 0))
                    else:
                        self.assertFalse(self.marker())
                    controller.kill()  # Exact Popen-owned controller, never a PID search.
                    controller.wait(timeout=5)
                    if observer.value:
                        self.assertEqual(api.WaitForSingleObject(observer, 5000), 0, phase)
                    if descendant.value:
                        self.assertEqual(api.WaitForSingleObject(descendant, 5000), 0, phase)
                    if phase != "resumed":
                        self.assertFalse(self.marker())
                    output, errors = controller.communicate(timeout=5)
                    self.assertEqual(controller.returncode, 1)
                    self.assertNotIn(b"Traceback", errors)
                finally:
                    if observer.value:
                        api.checked(api.CloseHandle(observer))
                    if descendant.value:
                        api.checked(api.CloseHandle(descendant))

    def test_incompatible_nested_job_refuses_without_execution(self):
        from tool.c2b_recording_supervisor import _WindowsJob
        class Basic(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", w.DWORD), ("min_ws", ctypes.c_size_t),
                        ("max_ws", ctypes.c_size_t), ("active_limit", w.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", w.DWORD),
                        ("scheduling", w.DWORD)]
        class Extended(ctypes.Structure):
            _fields_ = [("basic", Basic), ("io", ctypes.c_uint64 * 6),
                        ("memory", ctypes.c_size_t * 4)]
        outer = _WindowsJob()
        self.addCleanup(outer.close)
        retained_values = []  # Attribute values must live through CreateProcessW.
        def nested_list(boundary):
            update = boundary.api.UpdateProcThreadAttribute
            def nested(*args):
                if args[2] == containment.JOB_LIST:
                    jobs = (w.HANDLE * 2)(outer.handle, boundary.job.handle)
                    retained_values.append(jobs)
                    return update(args[0], args[1], args[2], jobs, ctypes.sizeof(jobs), None, None)
                return update(*args)
            return nested
        # Establish an actual nested hierarchy with a suspended owned seed, then
        # exhaust its enclosing active-process limit. No unrelated process used.
        seed = self.boundary
        with patch.object(seed.api, "UpdateProcThreadAttribute", side_effect=nested_list(seed)):
            self.assertTrue(seed.create(), seed.report)
        self.assertEqual(outer.active(), 1)
        limits = Extended()
        self.assertTrue(outer.api.QueryInformationJobObject(outer.handle, 9,
            ctypes.byref(limits), ctypes.sizeof(limits), None))
        limits.basic.flags |= 8  # JOB_OBJECT_LIMIT_ACTIVE_PROCESS
        limits.basic.active_limit = 1
        self.assertTrue(outer.api.SetInformationJobObject(outer.handle, 9,
            ctypes.byref(limits), ctypes.sizeof(limits)))
        candidate = containment.SyntheticBoundary(self.directory)
        self.addCleanup(candidate.close)
        native_create = candidate.api.CreateProcessW
        native_results = []
        def observed_create(*args):
            result = native_create(*args)
            native_results.append((result, ctypes.get_last_error()))
            return result
        with patch.object(candidate.api, "UpdateProcThreadAttribute", side_effect=nested_list(candidate)), \
                patch.object(candidate.api, "CreateProcessW", side_effect=observed_create):
            self.assertFalse(candidate.create(), candidate.report)
        self.assertEqual(len(native_results), 1)
        self.assertEqual(native_results[0][0], 0, native_results)
        self.assertNotEqual(native_results[0][1], 0, native_results)
        self.assertFalse(candidate.report["membership_verified"])
        self.assertFalse(candidate.report["dispatched"])
        self.assertTrue(candidate.report["errors"])
        self.assertFalse(self.marker())
        self.assert_clean(candidate)
        self.assertEqual(outer.active(), 1)  # Only the suspended seed remains.
        self.assert_clean()
        self.wait_for(lambda: outer.active() == 0)

    def test_enclosing_ui_job_is_supported_on_this_host(self):
        from tool.c2b_recording_supervisor import _WindowsJob
        outer = _WindowsJob()
        self.addCleanup(outer.close)
        restrictions = w.DWORD(0xFF)
        self.assertTrue(outer.api.SetInformationJobObject(outer.handle, 4,
            ctypes.byref(restrictions), ctypes.sizeof(restrictions)))
        controller = self.controller("nested")
        outer.assign(controller)
        controller.stdin.write(b"x")
        controller.stdin.flush()
        _, errors = controller.communicate(timeout=5)
        self.assertEqual(controller.returncode, 0, errors)
        result = json.loads((self.directory / "result.json").read_text())
        self.assertTrue(result["membership_verified"], result)
        self.assertFalse(result["dispatched"])
        self.assertFalse(result["cleanup"]["uncertain"], result)
        self.assertFalse(self.marker())
        self.wait_for(lambda: outer.active() == 0)


if __name__ == "__main__":
    unittest.main()
