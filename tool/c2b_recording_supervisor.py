"""Offline-only Gate A stdio recorder. No live command, config, or authorization API.

The only launchable child is the bundled synthetic fixture. Documented MCP wire
expectations are not observations of StudioMCP. See the R4 report before reuse.
"""
from __future__ import annotations

import ctypes
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

from tool.c2b_evidence import LIMIT, _digest, _plain_directory, _strict_json, _write_new

TARGET = "577768ad-49d8-42f5-ac96-8c66cd12a144"
PROTOCOL = "2025-11-25"
SESSION_LIMIT = 4 * LIMIT
MAX_FRAMES = 32
SCENARIOS = frozenset({
    "normal", "partial", "notifications", "bad_notification", "server_request",
    "malformed", "duplicate_key", "wrong_id", "wrong_id_type", "oversize",
    "exact_cap", "truncated", "timeout", "progress_timeout", "crash", "stderr",
    "stderr_flood", "stdout_flood", "duplicate_response", "trailing", "rpc_error",
    "tool_error", "declared_truncation", "silent_shortening", "bad_discovery",
    "missing_identity", "version", "ignore_eof", "descendant", "invalid_utf8",
    "batch", "nonfinite", "ambiguous", "notification_flood", "ping_duplicate",
    "init_timeout", "init_ping", "logging_timeout", "crlf", "blank",
    "after_response_crash", "session_flood",
    "blocked_stdin", "inherited_stdout", "eager_stdio",
})


class Refusal(Exception):
    pass


class StorageFailure(Exception):
    """No commit marker may follow an unverified write/readback."""


def _start_reader(reader, registry):
    """Register before start; retain hidden-start uncertainty for teardown."""
    registry.append(reader)
    try:
        reader.start()
    except BaseException as exc:
        # A returned RuntimeError with no start is the documented failed-start
        # case. An interrupted/hidden start cannot prove absence of a borrower.
        reader._c2b_start_unknown = not isinstance(exc, RuntimeError) and reader.ident is None
        raise


def _join_reader(reader):
    if reader.ident is not None:
        reader.join(timeout=0.5)
    return reader.is_alive() or getattr(reader, "_c2b_start_unknown", False)


def _json_frame(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


class GateAPolicy:
    """Exact short wire names; session-facing roblox_studio_ aliases are NOT accepted.

    This state machine is not an approval authority. Live dispatch is absent.
    A separate explicit review boundary is required between discovery and state.
    """

    def __init__(self):
        self.phase = "discovery"

    def check(self, method: str, params: dict) -> None:
        if method != "tools/call" or type(params) is not dict:
            raise Refusal("unapproved_method")
        allowed = {"name": "list_roblox_studios", "arguments": {}}
        if self.phase == "state":
            allowed = {"name": "get_studio_state", "arguments": {"studio_id": TARGET}}
        if self.phase not in ("discovery", "state") or params != allowed:
            raise Refusal("unapproved_tool_or_arguments_or_order")

    def recorded(self) -> None:
        self.phase = {"discovery": "review", "state": "done"}[self.phase]

    def reviewed(self) -> None:
        if self.phase != "review":
            raise Refusal("review_out_of_order")
        self.phase = "state"


class _WindowsJob:
    """Owned synthetic process tree, KILL_ON_JOB_CLOSE; no external process lookup."""

    def __init__(self):
        from ctypes import wintypes as w

        class Basic(ctypes.Structure):
            _fields_ = [("PerProcessUserTimeLimit", ctypes.c_int64),
                        ("PerJobUserTimeLimit", ctypes.c_int64), ("LimitFlags", w.DWORD),
                        ("MinimumWorkingSetSize", ctypes.c_size_t),
                        ("MaximumWorkingSetSize", ctypes.c_size_t),
                        ("ActiveProcessLimit", w.DWORD), ("Affinity", ctypes.c_size_t),
                        ("PriorityClass", w.DWORD), ("SchedulingClass", w.DWORD)]

        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("ReadOperationCount", "WriteOperationCount", "OtherOperationCount",
                         "ReadTransferCount", "WriteTransferCount", "OtherTransferCount")]

        class Extended(ctypes.Structure):
            _fields_ = [("BasicLimitInformation", Basic), ("IoInfo", IO),
                        ("ProcessMemoryLimit", ctypes.c_size_t),
                        ("JobMemoryLimit", ctypes.c_size_t),
                        ("PeakProcessMemoryUsed", ctypes.c_size_t),
                        ("PeakJobMemoryUsed", ctypes.c_size_t)]

        class Accounting(ctypes.Structure):
            _fields_ = [(name, ctypes.c_int64) for name in
                        ("TotalUserTime", "TotalKernelTime", "ThisPeriodTotalUserTime",
                         "ThisPeriodTotalKernelTime")] + [(name, w.DWORD) for name in
                        ("TotalPageFaultCount", "TotalProcesses", "ActiveProcesses",
                         "TotalTerminatedProcesses")]

        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateJobObjectW": ([ctypes.c_void_p, w.LPCWSTR], w.HANDLE),
            "SetInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL),
            "AssignProcessToJobObject": ([w.HANDLE, w.HANDLE], w.BOOL),
            "TerminateJobObject": ([w.HANDLE, w.UINT], w.BOOL),
            "QueryInformationJobObject": ([w.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                            w.DWORD, ctypes.c_void_p], w.BOOL),
            "CloseHandle": ([w.HANDLE], w.BOOL),
        }
        for name, (args, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes, function.restype = args, result
        self.accounting = Accounting
        self.assigned = False
        self.handle = self.api.CreateJobObjectW(None, None)
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.BasicLimitInformation.LimitFlags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not self.api.SetInformationJobObject(self.handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            self.close()
            raise OSError("cannot configure synthetic job")

    def assign(self, process):
        if not self.api.AssignProcessToJobObject(self.handle, int(process._handle)):
            raise OSError("cannot contain synthetic child")
        self.assigned = True

    def terminate(self):
        if not self.api.TerminateJobObject(self.handle, 1):
            raise OSError("job termination failed")

    def active(self):
        info = self.accounting()
        if not self.api.QueryInformationJobObject(self.handle, 1, ctypes.byref(info),
                                                  ctypes.sizeof(info), None):
            raise OSError("job termination verification failed")
        return info.ActiveProcesses

    def close(self):
        if self.handle:
            if not self.api.CloseHandle(self.handle):
                raise OSError("job handle close failed")
            self.handle = None


def _stop(process, job) -> dict:
    """Bounded verification; a kill request is not proof of exit."""
    from tool.c2b_native_recorder import SyntheticRecorderProcess
    if isinstance(process, SyntheticRecorderProcess):
        return process.stop_tree()
    errors = []
    try:
        if job is not None:
            job.terminate()
    except OSError as exc:
        errors.append(str(exc))
    # Also stop the exact owned root when containment assignment/termination
    # failed. Never search for or terminate a process by a reused external PID.
    try:
        if process.poll() is None:
            process.kill()
    except OSError as exc:
        errors.append(str(exc))
    try:
        process.wait(timeout=0.75)
    except subprocess.TimeoutExpired:
        errors.append("root_exit_unconfirmed")
    except OSError as exc:
        errors.append(str(exc))
    active = None
    if job is not None:
        until = time.monotonic() + 0.75
        try:
            active = job.active()
            while active and time.monotonic() < until:
                time.sleep(0.005)
                active = job.active()
        except OSError as exc:
            errors.append(str(exc))
    tree_confirmed = job is not None and job.assigned and active == 0
    return {"root_exit_confirmed": process.poll() is not None,
            "root_exit_code": process.poll(),
            "tree_exit_confirmed": tree_confirmed,
            "errors": errors,
            "uncertain": bool(errors) or process.poll() is None or not tree_confirmed}


class _Capture:
    """Pipe threads only do bounded byte retention; no JSON or disk work here."""

    def __init__(self):
        self.condition = threading.Condition()
        self.stdout = bytearray()
        self.stderr = bytearray()
        self.stdout_eof = self.stderr_eof = False
        self.failure = None
        self.received = {"stdout": 0, "stderr": 0}
        self.line_bytes = 0
        self.frames = 0

    def fail(self, reason):
        with self.condition:
            self.failure = self.failure or reason
            self.condition.notify_all()

    def read(self, pipe, kind):
        try:
            while True:
                data = os.read(pipe.fileno(), 4096)
                with self.condition:
                    if not data:
                        setattr(self, kind + "_eof", True)
                        self.condition.notify_all()
                        return
                    self.received[kind] += len(data)
                    if self.failure:
                        return  # Late/unretained data never enters acceptance.
                    if kind == "stderr":
                        remaining = LIMIT - len(self.stderr)
                        self.stderr.extend(data[:remaining])
                        if len(data) > remaining:
                            self.failure = "stderr_limit_prefix_only"
                    else:
                        # Delimit in bytes; retain no more than LIMIT per frame,
                        # SESSION_LIMIT total. Do not decode/repair line endings.
                        for byte in data:
                            if len(self.stdout) == SESSION_LIMIT:
                                self.failure = "stdout_session_limit_prefix_only"
                                break
                            if self.line_bytes == LIMIT:
                                self.failure = "oversized_prefix_only"
                                break
                            self.stdout.append(byte)
                            self.line_bytes += 1
                            if byte == 10:
                                self.line_bytes = 0
                                self.frames += 1
                                if self.frames > MAX_FRAMES:
                                    self.failure = "frame_count_limit"
                                    break
                    self.condition.notify_all()
                    if self.failure:
                        return
        except (OSError, ValueError):
            self.fail(kind + "_pipe_failure")


class _Session:
    def __init__(self, process, job, destination, capture, window):
        self.process, self.job, self.destination = process, job, destination
        self.capture, self.window = capture, window
        self.offset = self.sequence = self.file_sequence = 0
        self.files = {}
        self.calls = []
        self.writes = []
        self.worker_uncertainties = []
        self.ping_ids = set()
        self.write_lock = threading.Lock()
        self.stop_lock = threading.Lock()
        self.stop_result = None
        self.workers = []  # All writers/guards, including initialized/control.
        self.dispatch_check = None  # R9 synthetic seam, never client-supplied.

    def save(self, name, data):
        try:
            self.files[name] = _write_new(self.destination / name, data)
        except OSError as exc:
            raise StorageFailure(str(exc)) from exc

    def stop(self):
        with self.stop_lock:
            if self.stop_result is None:
                self.stop_result = _stop(self.process, self.job)
            return self.stop_result

    def write(self, value):
        raw = _json_frame(value)
        self.file_sequence += 1
        filename = f"stdin-{self.file_sequence:03d}.bin"
        self.save(filename, raw)
        observation = {"file": filename, "intended_bytes": len(raw), "bytes_written": 0,
                       "write_started_ns": None, "write_finished_ns": None, "error": None}
        self.writes.append(observation)
        # Writer may block. Its independent watchdog kills the child, unblocking
        # the pipe; controller does not wait indefinitely for the writer thread.
        errors = []
        def send():
            try:
                with self.write_lock:
                    observation["write_started_ns"] = time.monotonic_ns()
                    view = memoryview(raw)
                    while view:
                        if self.capture.failure:
                            raise OSError("session refused before write completion")
                        if self.dispatch_check is not None:
                            self.dispatch_check()
                            if time.monotonic_ns() >= self.write_deadline:
                                raise OSError("request deadline before write")
                        n = os.write(self.process.stdin.fileno(), view)
                        if n <= 0:
                            raise OSError("short pipe write")
                        view = view[n:]
                        observation["bytes_written"] += n
            except (OSError, ValueError):
                observation["error"] = "stdin_write_failure"
                errors.append(True)
                self.capture.fail("stdin_write_failure")
            finally:
                observation["write_finished_ns"] = time.monotonic_ns()
        thread = threading.Thread(target=send, daemon=True)
        self.workers.append(thread)
        try:
            thread.start()
        except RuntimeError:
            self.workers.remove(thread)  # Failed start has no running borrower.
            raise
        return thread, errors

    def next_frame(self, deadline):
        c = self.capture
        with c.condition:
            while True:
                if time.monotonic_ns() >= deadline:
                    raise Refusal("timeout")
                if c.failure:
                    raise Refusal(c.failure)
                end = c.stdout.find(b"\n", self.offset)
                if end >= 0:
                    raw = bytes(c.stdout[self.offset:end + 1])
                    self.offset = end + 1
                    break
                if c.stdout_eof:
                    raise Refusal("truncated_frame" if len(c.stdout) > self.offset else "child_eof")
                c.condition.wait(min(0.02, (deadline - time.monotonic_ns()) / 1e9))
        self.file_sequence += 1
        self.save(f"stdout-{self.file_sequence:03d}.bin", raw)  # BEFORE JSON parsing
        try:
            message = _strict_json(raw)
        except (ValueError, UnicodeError, RecursionError, OverflowError):
            raise Refusal("malformed_frame") from None
        if type(message) is not dict or message.get("jsonrpc") != "2.0":
            raise Refusal("malformed_envelope")
        return message, raw

    def request(self, method, params, validate):
        c = self.capture
        with c.condition:
            if c.failure or len(c.stdout) != self.offset:
                raise Refusal(c.failure or "unsolicited_output")
        self.sequence += 1
        request_id = f"r4-{self.sequence}"
        request = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        # Start immediately BEFORE write/storage, never reset by any message.
        started = time.monotonic_ns()
        deadline = started + int(self.window * 1e9)
        self.write_deadline = deadline
        done = threading.Event()
        timing = {"id": request_id, "method": method, "dispatch_monotonic_ns": started,
                  "deadline_monotonic_ns": deadline, "watchdog_fired_ns": None,
                  "accepted": False}
        self.calls.append(timing)
        def watchdog():
            while not done.wait(max(0, (deadline - time.monotonic_ns()) / 1e9)):
                if time.monotonic_ns() >= deadline:
                    timing["watchdog_fired_ns"] = time.monotonic_ns()
                    c.fail("timeout")
                    self.stop()
                    return
        guard = threading.Thread(target=watchdog, daemon=True)
        self.workers.append(guard)
        try:
            guard.start()
        except RuntimeError:
            self.workers.remove(guard)
            raise
        writers = []
        try:
            writers.append(self.write(request)[0])
            while True:
                message, raw = self.next_frame(deadline)
                if "method" in message:
                    self.control(message, writers)
                    continue
                if (type(message.get("id")) is not str or message.get("id") != request_id):
                    raise Refusal("response_id_mismatch")
                if set(message) == {"jsonrpc", "id", "error"}:
                    raise Refusal("rpc_error")
                if set(message) != {"jsonrpc", "id", "result"} or type(message["result"]) is not dict:
                    raise Refusal("ambiguous_response")
                validate(message["result"], raw)
                with c.condition:
                    validated = time.monotonic_ns()
                    if c.failure or validated >= deadline:
                        raise Refusal(c.failure or "timeout")
                    timing["accepted"] = True
                    timing["validated_monotonic_ns"] = validated
                return message["result"]
        except (Refusal, StorageFailure):
            # Do not disarm the watchdog and then grant a graceful-exit delay
            # after a refusal. Stop the owned child immediately and record it.
            self.stop()
            raise
        finally:
            # A reader can observe the absolute deadline just before the guard
            # is scheduled. Do not cancel an already-due independent watchdog
            # and erase its actual firing merely because the reader won that
            # race. Refusal has already stopped the owned tree above.
            if time.monotonic_ns() >= deadline and timing["watchdog_fired_ns"] is None:
                guard.join(timeout=0.5)
                if timing["watchdog_fired_ns"] is None:
                    self.worker_uncertainties.append("watchdog_deadline_delivery_uncertain")
                    c.fail("watchdog_deadline_delivery_uncertain")
            done.set()
            guard.join(timeout=2)
            if guard.is_alive():
                self.worker_uncertainties.append("watchdog_stop_uncertain")
                c.fail("watchdog_stop_uncertain")
            for writer in writers:
                writer.join(timeout=0.05)
                if writer.is_alive():
                    self.worker_uncertainties.append("writer_stop_uncertain")
                    c.fail("writer_stop_uncertain")
            timing["finished_monotonic_ns"] = time.monotonic_ns()
            fired = timing["watchdog_fired_ns"]
            timing["watchdog_lateness_ns"] = None if fired is None else max(0, fired - deadline)

    def control(self, message, writers):
        # No sampling/elicitation/roots/tasks/tool forwarding. Only server ping
        # and bounded logging; progress is unrequested and therefore a refusal.
        if message.get("method") == "ping":
            if (set(message) not in ({"jsonrpc", "id", "method"},
                                     {"jsonrpc", "id", "method", "params"}) or
                    message.get("params", {}) != {} or
                    type(message.get("id")) not in (int, str)):
                raise Refusal("malformed_ping")
            key = (type(message["id"]), message["id"])
            if key in self.ping_ids:
                raise Refusal("duplicate_server_request_id")
            self.ping_ids.add(key)
            writers.append(self.write({"jsonrpc": "2.0", "id": message["id"], "result": {}})[0])
            return
        if (set(message) == {"jsonrpc", "method", "params"} and
                message["method"] == "notifications/message"):
            p = message["params"]
            if (type(p) is dict and {"level", "data"} <= set(p) <= {"level", "data", "logger"}
                    and p["level"] in ("debug", "info", "notice", "warning", "error",
                                        "critical", "alert", "emergency")
                    and ("logger" not in p or type(p["logger"]) is str)):
                return  # Retained as a frame; never interpreted as a response.
        raise Refusal("unexpected_control_message")


def _initialize(result, raw):
    if (set(result) != {"protocolVersion", "capabilities", "serverInfo"} or
            result["protocolVersion"] != PROTOCOL or
            result["capabilities"] != {"tools": {}, "logging": {}} or
            type(result["serverInfo"]) is not dict or
            set(result["serverInfo"]) != {"name", "version"} or
            any(type(v) is not str or not v for v in result["serverInfo"].values())):
        raise Refusal("unsupported_initialize_result")


def _tool_payload(result, raw):
    if (not {"content"} <= set(result) <= {"content", "isError"} or
            result.get("isError", False) is not False or
            type(result["content"]) is not list or len(result["content"]) != 1):
        raise Refusal("tool_error_or_unknown_wrapper")
    block = result["content"][0]
    if (type(block) is not dict or set(block) != {"type", "text"} or
            block["type"] != "text" or type(block["text"]) is not str):
        raise Refusal("unknown_content")
    if b"truncat" in raw.lower() or b"output capped" in raw.lower():
        raise Refusal("suspected_truncation")
    try:
        return _strict_json(block["text"].encode("utf-8"))
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        raise Refusal("malformed_tool_payload") from None


def _discovery(result, raw):
    # Synthetic contract ONLY. New real envelopes require offline review.
    payload = _tool_payload(result, raw)
    if type(payload) is not dict or set(payload) != {"studios"}:
        raise Refusal("unknown_discovery_payload")
    studios = payload["studios"]
    if type(studios) is not list or not 1 <= len(studios) <= 16:
        raise Refusal("discovery_count")
    ids = set()
    for studio in studios:
        if (type(studio) is not dict or set(studio) != {"id", "name"} or
                type(studio["id"]) is not str or type(studio["name"]) is not str or
                not studio["id"] or not studio["name"] or studio["id"] in ids):
            raise Refusal("ambiguous_discovery")
        ids.add(studio["id"])
    if [s for s in studios if s["id"] == TARGET] != [{"id": TARGET, "name": "Place1"}]:
        raise Refusal("target_mismatch")


def _state(result, raw):
    payload = _tool_payload(result, raw)
    expected = {"studio_id": TARGET, "mode": "Edit", "team_create": False,
                "place": {"name": "Place1", "place_id": 0, "game_id": 0,
                          "creator_id": 0, "creator_type": "User", "is_unsaved": True},
                "user": {"id": 11822718311, "name": "aurory_naru"}}
    # Canonical JSON comparison preserves boolean-versus-integer distinctions.
    if _json_frame(payload) != _json_frame(expected):
        # Compare order-independently, still without Python's bool == int alias.
        if json.dumps(payload, sort_keys=True) != json.dumps(expected, sort_keys=True):
            raise Refusal("state_identity_missing_or_mismatch")


def run_synthetic(parent: Path, name: str, scenario: str = "normal", *,
                  synthetic_state_review: bool = False, window_seconds: float = 30.0) -> Path:
    """LEGACY synthetic-only Popen then assignment; NOT creation-time-contained.

    Preserved for R4/R5 regression comparison. No argv/live/approval escape hatch.
    """
    if scenario in {"blocked_stdin", "inherited_stdout", "eager_stdio"}:
        raise ValueError("R7 diagnostic scenario requires contained entrypoint")
    return _run_synthetic(parent, name, scenario, synthetic_state_review=synthetic_state_review,
                          window_seconds=window_seconds, contained=False)


def run_contained_synthetic(parent: Path, name: str, scenario: str = "normal", *,
                            synthetic_state_review: bool = False,
                            window_seconds: float = 30.0) -> Path:
    """R7 creation-time-contained bundled fixture only; no live launch capability."""
    return _run_synthetic(parent, name, scenario, synthetic_state_review=synthetic_state_review,
                           window_seconds=window_seconds, contained=True)


def run_paused_contained_synthetic(parent: Path, name: str, review, *,
                                   scenario: str = "normal", window_seconds: float = 30.0) -> Path:
    """R9 test-only blocking seam; continuation is never an MCP parameter."""
    from tool.c2b_synthetic_review import SyntheticReview
    if type(review) is not SyntheticReview:
        raise TypeError("synthetic review session required")
    return _run_synthetic(parent, name, scenario, synthetic_state_review=False,
                          window_seconds=window_seconds, contained=True, review=review)


def _run_synthetic(parent, name, scenario, *, synthetic_state_review, window_seconds, contained,
                   review=None):
    if scenario not in SCENARIOS or type(synthetic_state_review) is not bool:
        raise ValueError("synthetic scenario/review required")
    if (type(window_seconds) not in (int, float) or not math.isfinite(window_seconds)
            or not 0 < window_seconds <= 30):
        raise ValueError("invalid watchdog window")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ValueError("unsafe observation name")
    parent = Path(os.path.abspath(parent))
    _plain_directory(parent)
    destination = parent / name
    destination.mkdir(mode=0o700)
    _plain_directory(destination)
    fixture = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "c2b_fake_mcp.py"
    fixture_meta = _digest(fixture.read_bytes())
    job = process = session = None
    capture = _Capture()
    readers = []
    status = "launch_failure"
    shutdown = None
    teardown_errors = []
    try:
        if review is not None:
            review.bind(destination)
        if os.name != "nt":
            raise Refusal("windows_synthetic_only")
        if contained:
            from tool.c2b_native_recorder import SyntheticRecorderProcess
            process = SyntheticRecorderProcess(destination, scenario)
            if review is not None:
                process.synthetic_dispatch_check = review.check_dispatch
            if not process.start():
                raise Refusal("contained_setup_refused")
        else:
            job = _WindowsJob()
            process = subprocess.Popen([sys.executable, "-I", "-u", str(fixture), scenario],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, bufsize=0, shell=False,
                                       cwd=fixture.parent, close_fds=True)
            # LEGACY: post-Popen assignment, never creation-time containment.
            job.assign(process)
        session = _Session(process, job, destination, capture, float(window_seconds))
        if review is not None:
            session.dispatch_check = review.check_dispatch
            review.session = session
            session.files["synthetic-session.json"] = _digest(
                (destination / "synthetic-session.json").read_bytes())
        for kind in ("stdout", "stderr"):
            reader = threading.Thread(target=capture.read,
                                      args=(getattr(process, kind), kind), daemon=True)
            _start_reader(reader, readers)
        session.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                        "clientInfo": {"name": "c2b-offline-synthetic", "version": "1"}}, _initialize)
        # This notification has no response ID. Keep its writer bounded as well.
        writer, errors = session.write({"jsonrpc": "2.0", "method": "notifications/initialized"})
        writer.join(timeout=min(float(window_seconds), 0.5))
        if writer.is_alive() or errors:
            session.stop()
            writer.join(timeout=0.5)
            if writer.is_alive():
                session.stop_result["uncertain"] = True
                session.stop_result["errors"].append("initialized_writer_exit_unconfirmed")
            raise Refusal("initialized_write_failure")
        policy = GateAPolicy()
        params = {"name": "list_roblox_studios", "arguments": {}}
        policy.check("tools/call", params)
        discovery = session.request("tools/call", params, _discovery)
        policy.recorded()
        status = "synthetic_discovery_recorded_pause"
        if review is not None:
            review.pause(session, discovery)
        if synthetic_state_review or review is not None:
            policy.reviewed()  # Synthetic simulation, not a human approval claim.
            params = {"name": "get_studio_state", "arguments": {"studio_id": TARGET}}
            policy.check("tools/call", params)
            state = session.request("tools/call", params, _state)
            if review is not None:
                review.state_result = state
            policy.recorded()
            status = "synthetic_sequence_recorded"
    except Refusal as exc:
        status = str(exc)
    except (OSError, ValueError, TypeError, RecursionError, OverflowError) as exc:
        status = "supervisor_failure_" + type(exc).__name__
    except RuntimeError:
        status = "reader_or_worker_start_failure"
    finally:
        if process is not None:
            try:
                # Never close a CRT fd while a writer can still be using it.
                if not contained or session is None or not any(w.is_alive() for w in session.workers):
                    process.stdin.close()
                process.wait(timeout=0.15)
            except subprocess.TimeoutExpired:
                pass
            except OSError as exc:
                if contained:
                    teardown_errors.append(f"graceful_root_wait_failed: {exc}")
            try:
                root_before_stop = process.poll()
            except OSError:
                root_before_stop = None
                capture.fail("root_poll_failure")
                if contained:
                    teardown_errors.append("root_poll_failure")
            shutdown = session.stop() if session is not None else _stop(process, job)
            if session is not None and session.worker_uncertainties:
                shutdown["uncertain"] = True
                shutdown["errors"].extend(session.worker_uncertainties)
            if root_before_stop not in (None, 0) and status.startswith("synthetic_"):
                status = "child_crash_after_response"
            for reader in readers:
                _join_reader(reader)
            if any(r.is_alive() or getattr(r, "_c2b_start_unknown", False) for r in readers):
                shutdown["uncertain"] = True
                shutdown["errors"].append("pipe_reader_exit_unconfirmed")
            if session is not None and status.startswith("synthetic_"):
                if capture.failure or session.offset != len(capture.stdout):
                    status = capture.failure or "unexpected_trailing_output"
            if contained:
                shutdown = process.finish(readers + (session.workers if session else []))
                if teardown_errors:
                    shutdown["uncertain"] = True
                    shutdown["errors"].extend(teardown_errors)
                if status.startswith("synthetic_") and not (capture.stdout_eof and capture.stderr_eof):
                    status = "pipe_eof_unconfirmed"
        if job is not None:
            try:
                job.close()
            except OSError:
                if shutdown is not None:
                    shutdown["uncertain"] = True
                    shutdown["errors"].append("job_close_unconfirmed")
        if not contained and process is not None and not any(r.is_alive() for r in readers):
            process.stdout.close()
            process.stderr.close()
    if shutdown is None or shutdown["uncertain"]:
        status = "termination_uncertain:" + status
    files = session.files if session is not None else {}
    # Snapshot before disk finalization; no parsing of these combined raw streams.
    with capture.condition:
        # Freeze any unconfirmed late reader out of this evidence snapshot.
        capture.failure = capture.failure or "capture_finalized"
        received = dict(capture.received)
        stdout_eof, stderr_eof = capture.stdout_eof, capture.stderr_eof
        for filename, data in (("stdout-prefix.bin", bytes(capture.stdout)),
                               ("stderr-prefix.bin", bytes(capture.stderr))):
            files[filename] = _write_new(destination / filename, data)
    receipt = {
        "schema": "c2b-offline-supervisor/1", "synthetic": True,
        "studio_touched": False, "authorization": None, "utc_verified": False,
        "compatibility_pass": False, "upstream_completeness": "unverified",
        "full_upstream_response_claim": False, "status": status,
        "scenario": scenario, "fixture": fixture_meta, "files": files,
        "limit_bytes_per_frame": LIMIT, "stdout_session_limit": SESSION_LIMIT,
        "stderr_limit": LIMIT, "max_frames": MAX_FRAMES,
        "window_seconds": window_seconds,
        # Detach mutable worker bookkeeping even if a thread's exit is uncertain.
        "calls": json.loads(json.dumps(session.calls)) if session else [],
        "writes": json.loads(json.dumps(session.writes)) if session else [],
        "received_bytes_in_reads_at_least": received,
        "stdout_eof_observed": stdout_eof, "stderr_eof_observed": stderr_eof,
        "retained_streams_are_incomplete_failure_evidence": not status.startswith("synthetic_"),
        "total_upstream_response_bytes": None, "shutdown": shutdown,
        "synthetic_state_review": synthetic_state_review or review is not None,
        "launch_boundary": ("creation_time_contained_synthetic" if contained else
                            "legacy_synthetic_post_popen_assignment"),
    }
    if contained and process is not None:
        receipt["containment"] = json.loads(json.dumps(process.boundary.report))
        receipt["pipe_ownership"] = process.ownership_report()
    if review is not None:
        receipt["synthetic_session"] = review.session_id
        receipt["synthetic_review_mode"] = "external_checkpoint_bound_TEST_ONLY"
        receipt["synthetic_checkpoint"] = review.checkpoint_meta
    raw = (json.dumps(receipt, indent=2, sort_keys=True) + "\n").encode()
    meta = _write_new(destination / "receipt.json", raw)
    _write_new(destination / "COMMITTED.json", _json_frame(meta))
    verify_recording(destination)
    return destination


def verify_recording(destination: Path) -> dict:
    """Local consistency/readback verification, not authentication or ACL proof."""
    import stat
    destination = Path(os.path.abspath(destination))
    _plain_directory(destination)
    def read_regular(name):
        if not re.fullmatch(r"[A-Za-z0-9_-]+\.(bin|json)", name):
            raise ValueError("unsafe receipt filename")
        path = destination / name
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & 0x400):
            raise ValueError("non-regular evidence file")
        return path.read_bytes()
    raw = read_regular("receipt.json")
    if _strict_json(read_regular("COMMITTED.json")) != _digest(raw):
        raise ValueError("receipt integrity failure")
    receipt = _strict_json(raw)
    if receipt["schema"] != "c2b-offline-supervisor/1" or receipt["synthetic"] is not True:
        raise ValueError("not an offline recording")
    for name, meta in receipt["files"].items():
        if _digest(read_regular(name)) != meta:
            raise ValueError("evidence integrity failure")
    return receipt
