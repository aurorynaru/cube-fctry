"""R7 fixed-fixture bridge. No CLI, executable/argv/env or live-launch input.

Pipe ownership: boundary -> registered lease -> CRT descriptor. FileIO borrows
the descriptor (closefd=False). Tree stop never closes descriptors in active I/O.
"""
from __future__ import annotations

import ctypes
import io
import os
import subprocess
import threading
import time
from pathlib import Path

from tool.c2b_recording_supervisor import SCENARIOS
from tool.c2b_windows_containment import SyntheticBoundary, WAIT_OBJECT_0, WAIT_TIMEOUT


class _RecorderBoundary(SyntheticBoundary):
    def __init__(self, directory, scenario):
        if scenario not in SCENARIOS:
            raise ValueError("bundled MCP fixture scenario required")
        super().__init__(directory)
        self.scenario = scenario

    def _fixture_spec(self):
        if self.scenario not in SCENARIOS:
            raise ValueError("bundled MCP fixture scenario required")
        return (Path(__file__).resolve().parents[1] / "tests/fixtures/c2b_fake_mcp.py",
                self.scenario)


class _PipeLease:
    """Sole closer; states are explicit, values alone never imply ownership."""
    def __init__(self, boundary, kind):
        self.boundary, self.kind = boundary, kind
        self.native = self.fd = self.stream = None
        self.claimed = False
        self.pending_native = None
        self.state = "empty"
        self.events = []
        self.errors = []
        self.retired = False

    def convert(self):
        import msvcrt
        self.boundary.take_pipe(self.kind, self)
        self.state = "native"
        self.events.append("boundary_to_lease")
        flags = os.O_BINARY | os.O_NOINHERIT | (os.O_WRONLY if self.kind == "stdin" else os.O_RDONLY)
        # On failure open_osfhandle has not taken ownership. On success the CRT
        # owns the HANDLE: remove native authority before any next fallible call.
        self.pending_native = self.native
        self.native = None  # Surrender native-close authority before the C call.
        try:
            self.fd = msvcrt.open_osfhandle(self.pending_native, flags)
        except OSError:
            # Documented failed conversion leaves ownership with the caller.
            self.native = self.pending_native
            self.pending_native = None
            raise
        # An arbitrary interrupt with no registered return cannot establish which
        # side owns the pending value. close() quarantines it, never guesses.
        self.pending_native = None
        self.state = "crt"
        self.events.append("native_to_crt")
        self._checkpoint("crt")
        self.stream = io.FileIO(self.fd, "wb" if self.kind == "stdin" else "rb",
                                closefd=False)
        self.state = "stream_borrows_crt"
        self.events.append("stream_borrow")
        self._checkpoint("stream")

    def _checkpoint(self, phase):
        """Private deterministic fault/death checkpoint; no user callback."""

    def fileno(self):
        if self.retired or self.stream is None:
            raise ValueError("pipe is not available")
        return self.stream.fileno()

    def close(self):
        if self.retired:
            return
        self.retired = True  # Retire authority BEFORE close; never retry a value.
        stream, fd, native = self.stream, self.fd, self.native
        self.stream = self.fd = self.native = None
        if self.pending_native is not None and fd is None and native is None:
            self.errors.append(f"{self.kind}:native_to_crt_transfer_unverified_quarantined")
        operations = []
        if stream is not None:
            operations.append(("stream_close", stream.close))
        if fd is not None:
            operations.append(("crt_close", lambda: os.close(fd)))
        # A registered successful CRT return has already transferred authority,
        # even if interruption preceded clearing the old native bookkeeping.
        # Never close both representations of the same pipe.
        if self.claimed and native is not None and fd is None:
            operations.append(("native_close", lambda: self.boundary.api.checked(
                self.boundary.api.CloseHandle(native))))
        for event, operation in operations:
            try:
                operation()
                self.events.append(event)
            except (OSError, ValueError) as exc:
                self.errors.append(f"{self.kind}:{event}: {exc}")
        self.state = "close_uncertain" if self.errors else "closed"

    def report(self):
        return {"state": self.state, "events": list(self.events), "errors": list(self.errors),
                "closed": self.retired and not self.errors}


class SyntheticRecorderProcess:
    """Minimal recorder operations over R6; never subprocess.Popen fallback.

    Creation, transfer, resume and shutdown share the boundary lock. Workers
    borrow leases. stop_tree kills/verifies native resources only; finish joins
    every borrower before closing CRT resources. No destructor retries closes.
    """
    def __init__(self, directory: Path, scenario: str = "normal"):
        self.boundary = _RecorderBoundary(directory, scenario)
        self.pipes = {kind: _PipeLease(self.boundary, kind)
                      for kind in ("stdin", "stdout", "stderr")}
        self.stdin, self.stdout, self.stderr = (self.pipes[k] for k in self.pipes)
        self.stop_result = None
        self.finish_result = None
        self.lock = threading.RLock()
        self.synthetic_dispatch_check = None  # Internal R9 test-session seam.

    def start(self):
        with self.lock, self.boundary.lock:
            try:
                if self.synthetic_dispatch_check is not None:
                    self.synthetic_dispatch_check()
                if not self.boundary.create():
                    return False
                for pipe in self.pipes.values():
                    pipe.convert()
                if self.synthetic_dispatch_check is not None:
                    self.synthetic_dispatch_check()
                return self.boundary.resume()
            except BaseException as exc:
                self.boundary.report["errors"].append(f"bridge setup: {exc}")
                self.boundary.report["phase"] = "refused"
                if not isinstance(exc, Exception):
                    raise
                return False
            finally:
                if not self.boundary.report["dispatched"]:
                    self.stop_tree()
                    self.finish([])

    def poll(self):
        from ctypes import wintypes as w
        with self.boundary.lock:
            cleanup = self.boundary.report["cleanup"]
            if cleanup is not None:
                return cleanup["root_exit_code"]
            if "process" not in self.boundary.handles:
                return None
            handle = self.boundary.handles["process"]  # Borrow only under lock.
            result = self.boundary.api.WaitForSingleObject(handle, 0)
            if result == WAIT_TIMEOUT:
                return None
            if result != WAIT_OBJECT_0:
                raise OSError("owned root poll failed")
            code = w.DWORD()
            self.boundary.api.checked(self.boundary.api.GetExitCodeProcess(handle, ctypes.byref(code)))
            return code.value

    def wait(self, timeout):
        until = time.monotonic() + timeout
        while True:
            code = self.poll()
            if code is not None:
                return code
            if time.monotonic() >= until:
                raise subprocess.TimeoutExpired("fixed synthetic child", timeout)
            time.sleep(0.005)

    def stop_tree(self):
        with self.lock:
            if self.stop_result is None:
                cleanup = self.boundary.close()
                self.stop_result = dict(cleanup)
                self.stop_result["errors"] = list(cleanup["errors"])
                # A clean teardown cannot erase a prior ambiguous resume/setup.
                self.stop_result["uncertain"] |= self.boundary.report["uncertain"]
                self.stop_result["handles_closed"] = False  # CRT still owned.
            return self.stop_result

    def finish(self, workers):
        # Never hold the process lock across joins: a watchdog may be about to
        # acquire it for stop_tree. Native stop is independently idempotent.
        result = self.stop_tree()
        for worker in workers:
            if worker.ident is not None:
                worker.join(timeout=0.5)
        with self.lock:
            if self.finish_result is not None:
                return self.finish_result
            if any(worker.is_alive() or getattr(worker, "_c2b_start_unknown", False)
                   for worker in workers):
                result["uncertain"] = True
                result["errors"].append("pipe_worker_exit_unconfirmed_leases_quarantined")
            else:
                for pipe in self.pipes.values():
                    pipe.close()
                pipe_errors = [e for pipe in self.pipes.values() for e in pipe.errors]
                result["errors"].extend(pipe_errors)
                result["handles_closed"] = (self.boundary.report["cleanup"]["handles_closed"]
                                            and all(p.report()["closed"] for p in self.pipes.values()))
                result["uncertain"] |= bool(pipe_errors) or not result["handles_closed"]
            self.finish_result = result
            return result

    def ownership_report(self):
        return {kind: pipe.report() for kind, pipe in self.pipes.items()}
