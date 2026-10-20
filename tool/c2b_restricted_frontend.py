"""R9/R10 MCP stdio frontend. OFFLINE / FIXED SYNTHETIC CHILDREN ONLY.

Run inertly: python -m tool.c2b_restricted_frontend (no options).
Synthetic launch/review injection is a Python test seam, never an MCP method.
No installed OpenCode equivalence, human authority, UTC or live binding claim.
"""
from __future__ import annotations

import queue
import re
import sys
import threading
from pathlib import Path

from tool.c2b_evidence import _strict_json
from tool import c2b_recording_supervisor as recorder
from tool.c2b_synthetic_review import SyntheticReview

CLIENT_FRAME = 4096
CLIENT_TRAFFIC = 262144  # Combined input/output serialization, not a disk quota.
CLIENT_FRAMES = 64
# Front-facing release-source contract; distinct from the recorder's fake-child
# protocol. Attribution: R10 report §8, SDK src/types.ts:4 and OpenCode
# src/mcp/index.ts:39-80 at the commits recorded in docs/evidence/r10-source.
CLIENT_PROTOCOL = "2025-11-25"
RELEASE_CLIENT_INFO = {"name": "opencode", "version": "1.19.0"}
CATALOG = (
    {"name": "list_roblox_studios", "description": "TEST ONLY: one synthetic discovery.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "get_studio_state", "description": "TEST ONLY: reviewed synthetic state.",
     "inputSchema": {"type": "object", "properties": {
         "studio_id": {"type": "string", "const": recorder.TARGET}},
         "required": ["studio_id"], "additionalProperties": False}},
)


class Frontend:
    def __init__(self, parent: Path | None = None, observation: str = "synthetic", *,
                 scenario: str = "normal", window_seconds: float = 1.5,
                 review_seconds: float = 5.0):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", observation):
            raise ValueError("safe synthetic observation required")
        if scenario not in recorder.SCENARIOS:
            raise ValueError("bundled synthetic scenario required")
        if type(window_seconds) not in (int, float) or not 0 < window_seconds <= 30:
            raise ValueError("bounded synthetic request window required")
        self.parent, self.observation = parent, observation
        self.scenario, self.window = scenario, window_seconds
        self.review = SyntheticReview(observation, wait_seconds=review_seconds)
        self.lock = threading.Lock()
        self.lifecycle = "NEW"
        self.client_profile = None
        self.ids = set()
        self.frames = self.traffic = 0
        self.runner = None
        self.terminal = False
        self.completed = False
        self.reason = None

    def abort(self, reason):
        self.completed = False
        self.reason = self.reason or reason
        self.terminal = True
        self.review.abort(self.reason)

    def inject_launch(self, token):
        """TEST ONLY. Call from a fixture, never model/client protocol traffic."""
        if self.terminal or self.parent is None:
            self.abort("synthetic_store_required")
            raise recorder.Refusal(self.reason)
        self.review.authorize(token)

    def inject_continuation(self, token):
        self.review.inject_continuation(token)

    def _run(self):
        try:
            dest = recorder.run_paused_contained_synthetic(
                self.parent, self.observation, self.review, scenario=self.scenario,
                window_seconds=self.window)
            self.review.receipt = recorder.verify_recording(dest)
            if self.review.receipt["status"] != "synthetic_sequence_recorded":
                self.abort(self.review.receipt["status"])
        except BaseException as exc:
            self.abort("synthetic_runner_failure_" + type(exc).__name__)
        finally:
            self.review.finished.set()

    def _wait(self, event):
        while not event.wait(0.01):
            if self.review.finished.is_set() or self.terminal:
                raise recorder.Refusal(self.reason or "synthetic_session_ended")
        if self.terminal or self.review.failure:
            raise recorder.Refusal(self.reason or self.review.failure)

    def _call(self, params, request_id):
        if self.client_profile == "release-1.19.0":
            # OpenCode catalog.ts:54-66 installs onprogress; SDK protocol.ts:
            # 1128-1143 inserts the numeric request ID as progressToken. This is
            # inert client metadata, never authorization or upstream arguments.
            if type(params) is not dict or set(params) != {"name", "arguments", "_meta"}:
                raise recorder.Refusal("unsupported_release_call_metadata")
            meta = params["_meta"]
            if (type(meta) is not dict or set(meta) != {"progressToken"} or
                    type(meta["progressToken"]) is not int or
                    type(request_id) is not int or not 0 <= request_id < 2**53 or
                    meta["progressToken"] != request_id):
                raise recorder.Refusal("unsupported_release_call_metadata")
            params = {"name": params["name"], "arguments": params["arguments"]}
        if type(params) is not dict or set(params) != {"name", "arguments"}:
            raise recorder.Refusal("exact_tool_arguments_required")
        if type(params["arguments"]) is not dict:
            raise recorder.Refusal("exact_tool_arguments_required")
        if params == {"name": "list_roblox_studios", "arguments": {}}:
            if self.runner is not None or self.review.phase != "LAUNCH_AUTHORIZED":
                raise recorder.Refusal("synthetic_launch_required_or_discovery_spent")
            self.runner = threading.Thread(target=self._run, daemon=True)
            try:
                self.runner.start()
            except BaseException:
                self.abort("synthetic_runner_start_failure")
                raise
            self._wait(self.review.ready)
            return self.review.discovery_result
        if params == {"name": "get_studio_state", "arguments": {"studio_id": recorder.TARGET}}:
            self.review.request_state()
            self._wait(self.review.finished)
            self.terminal = True  # Success is also a one-shot terminal process.
            self.completed = True
            self.review.phase = "TERMINAL"
            return self.review.state_result
        raise recorder.Refusal("unapproved_tool_or_arguments")

    @staticmethod
    def _id(value):
        return ((type(value) is int and -(2**53) < value < 2**53) or
                (type(value) is str and 0 < len(value) <= 128))

    def handle(self, raw: bytes):
        """One bounded frame. Concurrent callers refuse, never queue dispatch."""
        if not self.lock.acquire(blocking=False):
            self.abort("concurrent_client_request")
            return recorder._json_frame({"jsonrpc": "2.0", "id": None,
                "error": {"code": -32000, "message": self.reason}})
        request_id = None
        try:
            if self.terminal:
                raise recorder.Refusal("terminal_frontend")
            self.frames += 1
            self.traffic += len(raw)
            if (type(raw) is not bytes or len(raw) > CLIENT_FRAME or
                    not raw.endswith(b"\n") or b"\n" in raw[:-1] or
                    self.frames > CLIENT_FRAMES or self.traffic > CLIENT_TRAFFIC):
                raise recorder.Refusal("client_frame_or_session_limit")
            message = _strict_json(raw)
            if type(message) is not dict or message.get("jsonrpc") != "2.0":
                raise recorder.Refusal("unexpected_client_envelope")
            if self._id(message.get("id")):
                request_id = message["id"]
            if (not {"jsonrpc", "method"} <= set(message) <= {"jsonrpc", "id", "method", "params"}
                    or type(message["method"]) is not str or
                    ("id" in message and request_id is None) or
                    type(message.get("params", {})) is not dict):
                raise recorder.Refusal("unexpected_client_envelope")
            method, params = message["method"], message.get("params", {})
            if "id" not in message:
                if method == "notifications/initialized" and params == {} and self.lifecycle == "INITIALIZING":
                    self.lifecycle = "READY"
                    return None
                if (method == "notifications/cancelled" and self.lifecycle == "READY" and
                        {"requestId"} <= set(params) <= {"requestId", "reason"} and
                        self._id(params["requestId"]) and
                        ("reason" not in params or type(params["reason"]) is str)):
                    self.abort("client_cancelled")
                    return None
                raise recorder.Refusal("unsupported_client_notification")
            key = (type(request_id), request_id)
            if key in self.ids:
                raise recorder.Refusal("duplicate_client_request_id")
            self.ids.add(key)
            if method == "initialize":
                if (self.lifecycle != "NEW" or set(params) != {"protocolVersion", "capabilities", "clientInfo"}
                        or params["protocolVersion"] != CLIENT_PROTOCOL
                        or not (params["capabilities"] == {} or
                                (params["capabilities"] == {"roots": {}} and
                                 params["clientInfo"] == RELEASE_CLIENT_INFO))
                        or type(params["clientInfo"]) is not dict
                        or set(params["clientInfo"]) != {"name", "version"}
                        or any(type(v) is not str or not 0 < len(v) <= 128
                               for v in params["clientInfo"].values())):
                    raise recorder.Refusal("unsupported_synthetic_initialize")
                self.lifecycle = "INITIALIZING"
                self.client_profile = "release-1.19.0" if params["capabilities"] == {"roots": {}} else "r9-candidate"
                result = {"protocolVersion": CLIENT_PROTOCOL, "capabilities": {"tools": {}},
                          "serverInfo": {"name": "c2b-restricted-TEST-ONLY", "version": "r9"}}
            elif self.lifecycle != "READY":
                raise recorder.Refusal("client_not_initialized")
            elif method == "ping" and params == {}:
                result = {}
            elif method == "tools/list" and params == {}:
                result = {"tools": list(CATALOG)}
            elif method == "tools/call":
                result = self._call(params, request_id)
            else:
                raise recorder.Refusal("unsupported_client_method_or_parameters")
            output = recorder._json_frame({"jsonrpc": "2.0", "id": request_id, "result": result})
            self.traffic += len(output)
            if self.traffic > CLIENT_TRAFFIC or len(output) > recorder.LIMIT:
                raise recorder.Refusal("client_output_limit")
            return output
        except (recorder.Refusal, ValueError, UnicodeError, RecursionError, OverflowError,
                OSError, TypeError, RuntimeError) as exc:
            self.abort(str(exc) if isinstance(exc, recorder.Refusal) else "malformed_or_failed_client_request")
            return recorder._json_frame({"jsonrpc": "2.0", "id": request_id,
                "error": {"code": -32000, "message": self.reason}})
        finally:
            self.lock.release()

    def close(self):
        if not self.completed:
            self.abort("client_disconnected")
        if self.runner is not None and self.runner.ident is not None:
            self.runner.join(timeout=4)
            if self.runner.is_alive():
                self.reason = "frontend_runner_exit_uncertain"
                self.completed = False


def serve(frontend, source, sink, diagnostics):
    """Disposable stdio process. No reconnect channel; EOF is terminal.

    Reader borrows stdin until process exit if a client holds it open. We do not
    close an active borrow or promise hard deadlines for blocked client stdout.
    """
    incoming, outgoing = queue.Queue(maxsize=2), queue.Queue(maxsize=1)
    stop = threading.Event()
    def read_client():
        try:
            while not stop.is_set():
                raw = source.readline(CLIENT_FRAME + 1)
                incoming.put(raw, timeout=0.05)
                if not raw or len(raw) > CLIENT_FRAME:
                    return
        except (OSError, ValueError, queue.Full):
            frontend.abort("client_reader_failure_or_flood")
    reader = threading.Thread(target=read_client, daemon=True)
    registered = []
    worker = None
    def emit(output):
        if output is not None:
            view = memoryview(output)
            while view:
                count = sink.write(view)
                if count is None or count <= 0:
                    raise OSError("client stdout incomplete write")
                view = view[count:]
            sink.flush()
    try:
        recorder._start_reader(reader, registered)
        while True:
            try:
                output = outgoing.get_nowait()
            except queue.Empty:
                output = False
            if output is not False:
                emit(output)
                worker.join(timeout=0.5)
                worker = None
            if frontend.terminal and worker is None:
                break
            try:
                raw = incoming.get(timeout=0.01)
            except queue.Empty:
                continue
            if not raw:
                frontend.abort("client_disconnected")
            elif worker is not None:
                frontend.abort("concurrent_client_request")
            else:
                try:
                    is_tool = _strict_json(raw).get("method") == "tools/call"
                except (ValueError, UnicodeError, AttributeError, RecursionError, OverflowError):
                    is_tool = False
                if is_tool:
                    worker = threading.Thread(target=lambda frame=raw: outgoing.put(frontend.handle(frame)), daemon=True)
                    worker.start()
                else:
                    emit(frontend.handle(raw))
    except BaseException as exc:
        frontend.abort("frontend_io_or_worker_failure_" + type(exc).__name__)
        if not isinstance(exc, Exception):
            raise
    finally:
        stop.set()
        frontend.close()
        if worker is not None and worker.ident is not None:
            worker.join(timeout=4)
        diagnostics.write("R9 TEST ONLY terminal: " + (frontend.reason or "closed") + "\n")
        diagnostics.flush()
    return 0 if frontend.completed else 1


def main():
    if len(sys.argv) != 1:
        sys.stderr.write("R9 inert frontend accepts no command-line options\n")
        return 2
    return serve(Frontend(), sys.stdin.buffer, sys.stdout.buffer, sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
