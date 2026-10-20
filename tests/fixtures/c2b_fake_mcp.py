"""Controlled OFFLINE fixture; no Roblox import, network, dynamic code or argv command.

Original scenarios read stdin before descendants for the legacy R4/R5 runner.
R7-only eager/blocked/inherited-pipe cases require the contained entrypoint.
These payload schemas are fixtures, not observed Studio responses.
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

TARGET = "577768ad-49d8-42f5-ac96-8c66cd12a144"
scenario = sys.argv[1]
if scenario == "pipe_holder":  # Fixed internal descendant role, never public argv.
    Path("pipe-holder.marker").write_bytes(b"synthetic descendant holding stdio\n")
    time.sleep(60)
    sys.exit(0)
if scenario == "blocked_stdin":
    Path("blocked-stdin.marker").write_bytes(b"synthetic child does not read stdin\n")
    time.sleep(60)
    sys.exit(0)
if scenario == "eager_stdio":
    child = subprocess.Popen([sys.executable, "-I", "-S", "-u", __file__, "pipe_holder"],
                             stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,
                             close_fds=True)
    Path("pipe-holder-handle.json").write_text(json.dumps({"process": int(child._handle)}))


def wire(value):
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode()


def emit(raw):
    if scenario == "partial":
        for byte in raw:
            os.write(1, bytes([byte]))
            time.sleep(0.0001)
    else:
        os.write(1, raw)


for line in sys.stdin.buffer:
    request = json.loads(line)
    method = request.get("method")
    if method == "notifications/initialized" or method is None:
        continue
    if method == "initialize":
        if scenario == "init_timeout":
            time.sleep(60)
        if scenario == "init_ping":
            emit(wire({"jsonrpc": "2.0", "id": 7, "method": "ping", "params": {}}))
            json.loads(sys.stdin.buffer.readline())
        result = {"protocolVersion": "wrong" if scenario == "version" else "2025-11-25",
                  "capabilities": {"tools": {}, "logging": {}},
                  "serverInfo": {"name": "OFFLINE fixture — 雪", "version": "1"}}
        emit(wire({"jsonrpc": "2.0", "id": request["id"], "result": result}))
        continue
    if request["params"]["name"] == "get_studio_state":
        payload = {"studio_id": TARGET, "mode": "Edit", "team_create": False,
                   "place": {"name": "Place1", "place_id": 0, "game_id": 0,
                             "creator_id": 0, "creator_type": "User", "is_unsaved": True},
                   "user": {"id": 11822718311, "name": "aurory_naru"}}
        if scenario == "missing_identity":
            payload = {"mode": "Edit"}
    else:
        payload = {"studios": [{"id": TARGET, "name": "Place1"}]}
        if scenario == "bad_discovery":
            payload["studios"] *= 17
    result = {"content": [{"type": "text", "text": json.dumps(payload)}]}
    response = {"jsonrpc": "2.0", "id": request["id"], "result": result}
    if scenario in ("timeout", "progress_timeout"):
        if scenario == "progress_timeout":
            emit(wire({"jsonrpc": "2.0", "method": "notifications/progress",
                       "params": {"progressToken": "unrequested", "progress": 1}}))
        time.sleep(60)
    if scenario == "descendant":
        subprocess.Popen([sys.executable, "-I", "-c", "import time; time.sleep(60)"],
                         stdin=subprocess.DEVNULL)  # Inherits the owned job.
        time.sleep(60)
    if scenario == "logging_timeout":
        while True:
            emit(wire({"jsonrpc": "2.0", "method": "notifications/message",
                       "params": {"level": "info", "data": "still waiting"}}))
            time.sleep(0.03)
    if scenario == "crash":
        os.write(1, b'{"jsonrpc":')
        os._exit(7)
    if scenario in ("stderr", "stderr_flood"):
        os.write(2, b'not MCP\r\n\xff' if scenario == "stderr" else b"e" * 70000)
    if scenario == "stdout_flood":
        while True:
            os.write(1, b"x" * 4096)
    if scenario == "session_flood":
        for _ in range(6):
            emit(wire({"jsonrpc": "2.0", "method": "notifications/message",
                       "params": {"level": "info", "data": "x" * 60000}}))
    if scenario in ("notifications", "notification_flood", "ping_duplicate"):
        for _ in range(40 if scenario == "notification_flood" else 1):
            emit(wire({"jsonrpc": "2.0", "method": "notifications/message",
                       "params": {"level": "info", "data": {"text": "synthetic log"}}}))
        for _ in range(2 if scenario == "ping_duplicate" else 1):
            emit(wire({"jsonrpc": "2.0", "id": "server-ping-" + request["id"], "method": "ping"}))
            json.loads(sys.stdin.buffer.readline())  # Wait for recorded pong.
    if scenario in ("bad_notification", "server_request"):
        emit(wire({"jsonrpc": "2.0", "method": "notifications/tools/list_changed"}
                  if scenario == "bad_notification" else
                  {"jsonrpc": "2.0", "id": "unsafe", "method": "sampling/createMessage", "params": {}}))
        time.sleep(60)
    if scenario == "wrong_id":
        response["id"] = "unmatched"
    if scenario == "wrong_id_type":
        response["id"] = 2
    if scenario == "rpc_error":
        response = {"jsonrpc": "2.0", "id": request["id"],
                    "error": {"code": -32000, "message": "synthetic failure"}}
    if scenario == "tool_error":
        result["isError"] = True
    if scenario == "declared_truncation":
        result["truncated"] = True
    if scenario == "silent_shortening":
        # Valid plausible payload: the recorder cannot detect an omitted other Studio.
        pass
    if scenario == "ambiguous":
        response["error"] = {"code": -1, "message": "also result"}
    raw = wire(response)
    if scenario in ("exact_cap", "oversize"):
        # Legal whitespace still belongs to exact original frame bytes.
        raw = raw[:-1] + b" " * (65536 - len(raw) + (scenario == "oversize")) + b"\n"
    if scenario == "malformed":
        raw = b"not JSON\n"
    if scenario == "blank":
        raw = b"\n"
    if scenario == "crlf":
        raw = raw[:-1] + b"\r\n"
    if scenario == "duplicate_key":
        raw = raw.replace(b'"jsonrpc":"2.0"', b'"jsonrpc":"2.0","jsonrpc":"2.0"')
    if scenario == "invalid_utf8":
        raw = b"\xff\n"
    if scenario == "batch":
        raw = wire([response])
    if scenario == "nonfinite":
        raw = raw.replace(b'"result":', b'"extra":1e999,"result":')
    if scenario == "truncated":
        emit(raw[:-5])
        break
    emit(raw)
    if scenario == "inherited_stdout":
        child = subprocess.Popen([sys.executable, "-I", "-S", "-u", __file__, "pipe_holder"],
                                 stdin=sys.stdin, stdout=sys.stdout, stderr=sys.stderr,
                                 close_fds=True)
        Path("pipe-holder-handle.json").write_text(json.dumps({"process": int(child._handle)}))
        sys.exit(0)  # Descendant retains pipe; root exit does not establish EOF.
    if scenario == "after_response_crash":
        os._exit(7)
    if scenario == "duplicate_response":
        emit(raw)
    if scenario == "trailing":
        os.write(1, b"unterminated tail")
if scenario == "ignore_eof":
    time.sleep(60)
