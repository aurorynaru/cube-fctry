"""R6 OFFLINE experiment: fixed synthetic fixture only; no launcher/proxy CLI.

CreateProcessW must accept JOB_LIST + HANDLE_LIST + CREATE_SUSPENDED together.
There is deliberately no suspended-then-assign or ordinary-spawn fallback.
The Windows API contract, not a Python marker, establishes pre-instruction order.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from tool.c2b_evidence import _plain_directory
from tool.c2b_recording_supervisor import _WindowsJob

SCENARIOS = frozenset({"marker", "eager", "inherited_pipe", "exit"})
JOB_LIST = 0x0002000D
HANDLE_LIST = 0x00020002
CREATE_SUSPENDED = 0x4
EXTENDED_STARTUPINFO_PRESENT = 0x80000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 258


class _CreationJob(_WindowsJob):
    """Register ownership before the reused R4 job initializer can allocate.

    If configuration AND its internal close fail, the seam still retains the
    job handle for checked cleanup. R4's original constructor is unchanged.
    """

    def __init__(self):
        self.handle = None
        self.assigned = False

    def configure(self):
        super().__init__()


class _API:
    def __init__(self):
        from ctypes import wintypes as w

        class Security(ctypes.Structure):
            _fields_ = [("length", w.DWORD), ("descriptor", ctypes.c_void_p),
                        ("inherit", w.BOOL)]

        class Startup(ctypes.Structure):
            _fields_ = [("cb", w.DWORD), ("reserved", w.LPWSTR),
                        ("desktop", w.LPWSTR), ("title", w.LPWSTR)] + [
                (name, w.DWORD) for name in ("x", "y", "xsize", "ysize", "xchars",
                                           "ychars", "fill", "flags")] + [
                ("show", w.WORD), ("reserved_size", w.WORD),
                ("reserved_bytes", ctypes.c_void_p), ("stdin", w.HANDLE),
                ("stdout", w.HANDLE), ("stderr", w.HANDLE)]

        class StartupEx(ctypes.Structure):
            _fields_ = [("startup", Startup), ("attributes", ctypes.c_void_p)]

        class ProcessInfo(ctypes.Structure):
            _fields_ = [("process", w.HANDLE), ("thread", w.HANDLE),
                        ("pid", w.DWORD), ("tid", w.DWORD)]

        self.Security, self.StartupEx, self.ProcessInfo = Security, StartupEx, ProcessInfo
        self.dll = ctypes.WinDLL("kernel32", use_last_error=True)
        definitions = {
            "CreatePipe": ([ctypes.POINTER(w.HANDLE), ctypes.POINTER(w.HANDLE),
                            ctypes.POINTER(Security), w.DWORD], w.BOOL),
            "SetHandleInformation": ([w.HANDLE, w.DWORD, w.DWORD], w.BOOL),
            "GetHandleInformation": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "InitializeProcThreadAttributeList": ([ctypes.c_void_p, w.DWORD, w.DWORD,
                                                    ctypes.POINTER(ctypes.c_size_t)], w.BOOL),
            "UpdateProcThreadAttribute": ([ctypes.c_void_p, w.DWORD, ctypes.c_size_t,
                                            ctypes.c_void_p, ctypes.c_size_t,
                                            ctypes.c_void_p, ctypes.c_void_p], w.BOOL),
            "DeleteProcThreadAttributeList": ([ctypes.c_void_p], None),
            "CreateProcessW": ([w.LPCWSTR, w.LPWSTR, ctypes.c_void_p, ctypes.c_void_p,
                                w.BOOL, w.DWORD, ctypes.c_void_p, w.LPCWSTR,
                                ctypes.POINTER(StartupEx), ctypes.POINTER(ProcessInfo)], w.BOOL),
            "IsProcessInJob": ([w.HANDLE, w.HANDLE, ctypes.POINTER(w.BOOL)], w.BOOL),
            "ResumeThread": ([w.HANDLE], w.DWORD),
            "WaitForSingleObject": ([w.HANDLE, w.DWORD], w.DWORD),
            "TerminateProcess": ([w.HANDLE, w.UINT], w.BOOL),
            "GetExitCodeProcess": ([w.HANDLE, ctypes.POINTER(w.DWORD)], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
            "PeekNamedPipe": ([w.HANDLE, ctypes.c_void_p, w.DWORD, ctypes.c_void_p,
                               ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
            "ReadFile": ([w.HANDLE, ctypes.c_void_p, w.DWORD,
                          ctypes.POINTER(w.DWORD), ctypes.c_void_p], w.BOOL),
        }
        for name, (args, result) in definitions.items():
            function = getattr(self.dll, name)
            function.argtypes, function.restype = args, result
            setattr(self, name, function)

    @staticmethod
    def checked(result):
        if not result:
            raise ctypes.WinError(ctypes.get_last_error())
        return result


class SyntheticBoundary:
    """One owned root/job, three explicit pipes; all outcomes in ``report``.

    Caller must close (or use ``with``). No implicit destructor success/cleanup.
    create() leaves the root suspended. resume() is the sole dispatch transition.
    No method accepts an executable, command line, environment, or child argv.
    Private checkpoints/API methods exist solely for local fault injection.
    """

    def __init__(self, directory: Path, scenario: str = "marker"):
        if scenario not in SCENARIOS:
            raise ValueError("fixed containment fixture scenario required")
        if os.name != "nt":
            raise OSError("Windows synthetic containment only")
        self.directory = Path(os.path.abspath(directory))
        _plain_directory(self.directory)
        self.scenario = scenario
        self.api = _API()
        self.job = None
        self.handles = {}
        self.pipe_leases = {}  # Explicit transfer authority, not numeric aliases.
        self.attributes = None
        self.attribute_initialized = False
        self.lock = threading.RLock()
        self.report = {"synthetic": True, "mechanism": "job_list+suspended+handle_list",
                       "membership_verified": False, "dispatched": False,
                       "execution_may_have_started": False,
                       "failed_creation_handles_unverified": False,
                       "resume_previous_count": None, "errors": [], "cleanup": None,
                       "uncertain": False, "phase": "new"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def _checkpoint(self, phase):
        """Overridden only by synthetic test helpers, never a command callback."""

    def _fixture_spec(self):
        return (Path(__file__).resolve().parents[1] / "tests/fixtures/c2b_containment_child.py",
                self.scenario)

    def take_pipe(self, kind, lease):
        """Explicit transfer to a pre-registered internal lease, while suspended.

        The receiver must be empty. No numeric-value ownership guessing and no
        native close after transfer. This is not a generic launch interface.
        """
        with self.lock:
            if (kind not in ("stdin", "stdout", "stderr") or
                    self.report["phase"] != "contained_suspended" or
                    self.report["cleanup"] is not None or lease.state != "empty" or
                    lease.retired):
                raise ValueError("pipe transfer requires empty lease and suspended root")
            # Install a receiver reference before committing transfer authority.
            # If interrupted before claimed=True, the boundary still closes it;
            # after that commit, _close_handle must never close the stale entry.
            self.pipe_leases[kind] = lease
            lease.native = self.handles[kind]
            lease.claimed = True
            del self.handles[kind]

    def _close_handle(self, name):
        lease = self.pipe_leases.get(name)
        if lease is not None and lease.claimed:
            self.handles.pop(name, None)  # Explicitly transferred, never close.
            return
        value = self.handles.get(name)
        if value:
            self.api.checked(self.api.CloseHandle(value))
            del self.handles[name]

    def _free_attributes(self):
        if self.attribute_initialized:
            self.api.DeleteProcThreadAttributeList(self.attributes)
            self.attribute_initialized = False
        self.attributes = None

    def _membership(self):
        from ctypes import wintypes as w
        member = w.BOOL()
        self.api.checked(self.api.IsProcessInJob(self.handles["process"], self.job.handle,
                                                ctypes.byref(member)))
        if not member.value:
            raise OSError("creation-time job membership not verified")

    def _running(self, name):
        value = self.api.WaitForSingleObject(self.handles[name], 0)
        if value not in (WAIT_OBJECT_0, WAIT_TIMEOUT):
            raise OSError("owned handle wait failed")
        return value == WAIT_TIMEOUT

    def _failure(self, exc):
        self.report["errors"].append(f"{self.report['phase']}: {exc}")
        if self.report["execution_may_have_started"] and not self.report["dispatched"]:
            self.report["uncertain"] = True
        self.report["phase"] = "refused"
        self.close()
        return False

    def create(self):
        from ctypes import wintypes as w
        with self.lock:
            if self.report["phase"] != "new" or self.report["cleanup"] is not None:
                raise ValueError("one creation attempt only")
            info = None
            created = None
            try:
                self.report["phase"] = "setup"
                self.job = _CreationJob()
                self.job.configure()  # Unnamed, noninheritable; no breakaway limits.
                security = self.api.Security(ctypes.sizeof(self.api.Security), None, True)
                child_names = []
                for kind in ("stdin", "stdout", "stderr"):
                    read, write = w.HANDLE(), w.HANDLE()
                    self.api.checked(self.api.CreatePipe(ctypes.byref(read), ctypes.byref(write),
                                                         ctypes.byref(security), 0))
                    # Register both immediately, before any next fallible operation.
                    child, parent = (read.value, write.value) if kind == "stdin" else (write.value, read.value)
                    self.handles[kind] = parent
                    self.handles["child_" + kind] = child
                    child_names.append("child_" + kind)
                    self.api.checked(self.api.SetHandleInformation(parent, 1, 0))
                # Explicitly verify flags, including noninheritable job/parent ends.
                for name, handle in {**self.handles, "job": self.job.handle}.items():
                    flags = w.DWORD()
                    self.api.checked(self.api.GetHandleInformation(handle, ctypes.byref(flags)))
                    if bool(flags.value & 1) != name.startswith("child_"):
                        raise OSError("unexpected handle inheritance")
                size = ctypes.c_size_t()
                ctypes.set_last_error(0)
                first = self.api.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
                if first or ctypes.get_last_error() != 122 or not size.value:
                    raise OSError("attribute sizing unsupported/unexpected")
                self.attributes = ctypes.create_string_buffer(size.value)
                self.api.checked(self.api.InitializeProcThreadAttributeList(
                    self.attributes, 2, 0, ctypes.byref(size)))
                self.attribute_initialized = True
                jobs = (w.HANDLE * 1)(self.job.handle)
                inherited = (w.HANDLE * 3)(*(self.handles[n] for n in child_names))
                for attribute, values in ((JOB_LIST, jobs), (HANDLE_LIST, inherited)):
                    self.api.checked(self.api.UpdateProcThreadAttribute(
                        self.attributes, 0, attribute, values, ctypes.sizeof(values), None, None))
                startup = self.api.StartupEx()
                startup.startup.cb = ctypes.sizeof(startup)
                startup.startup.flags = 0x100  # STARTF_USESTDHANDLES
                for kind in ("stdin", "stdout", "stderr"):
                    setattr(startup.startup, kind, self.handles["child_" + kind])
                startup.attributes = ctypes.cast(self.attributes, ctypes.c_void_p)
                info = self.api.ProcessInfo()
                fixture, scenario = self._fixture_spec()
                executable = str(Path(sys.executable).resolve())
                command = ctypes.create_unicode_buffer(subprocess.list2cmdline(
                    [executable, "-I", "-S", "-u", str(fixture), scenario]))
                self.report["phase"] = "creating"
                self._checkpoint("before_create")
                created = self.api.CreateProcessW(
                    executable, command, None, None, True,
                    CREATE_SUSPENDED | EXTENDED_STARTUPINFO_PRESENT, None,
                    str(self.directory), ctypes.byref(startup), ctypes.byref(info))
                # PROCESS_INFORMATION handles are documented as valid on SUCCESS
                # only. Never kill/close numeric outputs from a failed call: they
                # are not sufficient evidence of ownership of those handles.
                if not created:
                    if info.process or info.thread:
                        self.report["failed_creation_handles_unverified"] = True
                        self.report["uncertain"] = True
                    self.api.checked(created)
                if info.process:
                    self.handles["process"] = info.process
                if info.thread:
                    self.handles["thread"] = info.thread
                if not info.process or not info.thread:
                    self.report["uncertain"] = True
                    raise OSError("missing owned process/thread handle")
                self._checkpoint("created")
                for name in child_names:
                    self._close_handle(name)
                self._free_attributes()
                self._membership()
                self.job.assigned = True
                self.report["membership_verified"] = True
                if not self._running("process") or not self._running("thread"):
                    raise OSError("child exited during setup")
                self.report["phase"] = "contained_suspended"
                self._checkpoint("verified")
                return True
            except BaseException as exc:
                if info is not None:
                    for name, value in (("process", info.process), ("thread", info.thread)):
                        if value and name not in self.handles:
                            if created:
                                # A documented success was registered, but Python
                                # was interrupted before both handles were stored.
                                self.handles[name] = value
                            else:
                                # No observed success return: output numbers alone
                                # confer no authority, including interrupted calls.
                                self.report["failed_creation_handles_unverified"] = True
                                self.report["uncertain"] = True
                self._failure(exc)
                if not isinstance(exc, Exception):
                    raise
                return False

    def resume(self):
        with self.lock:
            if self.report["phase"] != "contained_suspended" or self.report["cleanup"] is not None:
                raise ValueError("resume requires verified suspended containment")
            try:
                self._membership()
                if not self._running("process") or not self._running("thread"):
                    raise OSError("child exited before resume")
                # From this point an exception or unexpected result cannot prove
                # zero executed instructions. Membership was checked above.
                self.report["execution_may_have_started"] = True
                previous = self.api.ResumeThread(self.handles["thread"])
                self.report["resume_previous_count"] = previous
                if previous != 1:
                    # 0 may mean execution already occurred; never assert zero instructions.
                    self.report["uncertain"] = True
                    raise OSError(f"unexpected ResumeThread count: {previous}")
                self._close_handle("thread")
                self.report["dispatched"] = True
                self.report["phase"] = "resumed"
                self._checkpoint("resumed")
                return True
            except BaseException as exc:
                self._failure(exc)
                if not isinstance(exc, Exception):
                    raise
                return False

    def read_available(self, kind):
        """Nonblocking, at most 4096 bytes; synthetic diagnostics, never MCP parsing."""
        from ctypes import wintypes as w
        if kind not in ("stdout", "stderr"):
            raise ValueError("output pipe required")
        available = w.DWORD()
        handle = self.handles[kind]
        if not self.api.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            if ctypes.get_last_error() == 109:  # Broken pipe / EOF.
                return b"", True
            self.api.checked(False)
        if not available.value:
            return b"", False
        buffer = ctypes.create_string_buffer(min(available.value, 4096))
        count = w.DWORD()
        self.api.checked(self.api.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None))
        return buffer.raw[:count.value], False

    def close(self):
        """Serialized shutdown, bounded root/job verification, checked closes.

        Closing a job is not itself proof the tree exited. Keep it open until
        active-process accounting reaches zero; no PID lookup or PID-based kill.
        """
        with self.lock:
            if self.report["cleanup"] is not None:
                return self.report["cleanup"]
            errors = []
            def attempt(function):
                try:
                    return function()
                except (OSError, ValueError) as exc:
                    errors.append(str(exc))
                    return None
            has_root = "process" in self.handles
            exit_code = None
            unknown_outputs = self.report["failed_creation_handles_unverified"]
            root = not has_root and not unknown_outputs
            has_job = self.job is not None and bool(self.job.handle)
            active = 0 if not has_job and root else None
            if has_job:
                attempt(self.job.terminate)
            if has_root:
                # TerminateJobObject is asynchronous. Wait before the root-only
                # fallback; TerminateProcess on an already-exiting process can
                # return ERROR_ACCESS_DENIED despite a valid owned handle.
                wait = attempt(lambda: self.api.WaitForSingleObject(self.handles["process"], 1000))
                if wait == WAIT_TIMEOUT:
                    attempt(lambda: self.api.checked(self.api.TerminateProcess(self.handles["process"], 1)))
                    wait = attempt(lambda: self.api.WaitForSingleObject(self.handles["process"], 1000))
                root = wait == WAIT_OBJECT_0
                if not root:
                    errors.append("owned root exit unconfirmed")
                else:
                    from ctypes import wintypes as w
                    code = w.DWORD()
                    queried = attempt(lambda: self.api.checked(self.api.GetExitCodeProcess(
                        self.handles["process"], ctypes.byref(code))))
                    if queried:
                        exit_code = code.value
            if has_job:
                until = time.monotonic() + 1
                active = attempt(self.job.active)
                while active and time.monotonic() < until:
                    time.sleep(0.005)
                    active = attempt(self.job.active)
                if active != 0:
                    errors.append("owned job empty unconfirmed")
            if unknown_outputs:
                errors.append("failed creation returned handles with unverified ownership")
            attempt(self._free_attributes)
            for name in list(self.handles):
                attempt(lambda name=name: self._close_handle(name))
            if self.job is not None:
                attempt(self.job.close)
            cleanup = {"root_exit_confirmed": root, "root_exit_code": exit_code,
                       "tree_exit_confirmed": active == 0,
                       "handles_closed": not unknown_outputs and not self.handles and
                       (self.job is None or self.job.handle is None), "errors": errors}
            cleanup["uncertain"] = bool(errors) or not all(cleanup[k] for k in
                ("root_exit_confirmed", "tree_exit_confirmed", "handles_closed"))
            self.report["cleanup"] = cleanup
            self.report["uncertain"] |= cleanup["uncertain"]
            return cleanup
