"""Offline synthetic transport evidence experiment. No network/process/MCP dispatch.

Frames are synthetic newline-delimited JSON-RPC bytes, NOT reconstructed tool
display text. This module cannot issue or consume an operator authorization.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

LIMIT = 64 * 1024
WINDOW_NS = 30_000_000_000


@dataclass(frozen=True)
class SyntheticEvent:
    offset_ns: int
    data: bytes = b""
    end: bool = False
    failure: bool = False


def _digest(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def _write_new(path: Path, data: bytes) -> dict:
    # Exclusive creation, checked full writes, flush, durable file sync, readback.
    with path.open("xb") as stream:
        view = memoryview(data)
        while view:
            n = stream.write(view)
            if n is None or n <= 0:
                raise OSError("incomplete write")
            view = view[n:]
        stream.flush()
        os.fsync(stream.fileno())
    actual = path.read_bytes()
    if actual != data:
        raise OSError("readback mismatch")
    return _digest(actual)


def _plain_directory(path: Path) -> None:
    # Fail on existing symlink/reparse ancestors, including Windows junctions.
    # Not race-proof against another writer replacing an ancestor; see report.
    for node in (path, *path.parents):
        info = node.lstat()
        if not stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode):
            raise ValueError("non-directory/symlink ancestor")
        if getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("reparse ancestor")


def _strict_json(raw: bytes):
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError("duplicate JSON key")
            out[key] = value
        return out

    def number(value):
        result = float(value)
        if not math.isfinite(result):
            raise ValueError("nonfinite number")
        return result

    def constant(value):
        raise ValueError("nonfinite constant")

    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_float=number, parse_constant=constant)


def _frame_status(raw: bytes, request_id: int | str) -> str:
    try:
        if not raw.endswith(b"\n") or b"\n" in raw[:-1]:
            return "incomplete_or_multiple_frames"
        envelope = _strict_json(raw)
        if not isinstance(envelope, dict):
            return "malformed_envelope"
        if (envelope.get("jsonrpc") != "2.0" or
                type(envelope.get("id")) is not type(request_id) or
                envelope.get("id") != request_id):
            return "malformed_envelope"
        if set(envelope) == {"jsonrpc", "id", "error"}:
            return "rpc_error"
        if set(envelope) != {"jsonrpc", "id", "result"}:
            return "malformed_envelope"
        result = envelope["result"]
        if not isinstance(result, dict) or not isinstance(result.get("content"), list):
            return "malformed_result"
        if result.get("isError", False) is not False:
            return "tool_error"
        # Explicit flags/markers always require offline review. Not a proof of
        # semantic completeness when an upstream server silently omits content.
        text = raw.lower()
        if (result.get("truncated", False) is not False or
                result.get("complete", True) is not True or
                b"truncat" in text or b"output capped" in text):
            return "declared_or_suspected_truncation"
        return "transport_complete_semantics_unverified"
    except (ValueError, UnicodeError, RecursionError, OverflowError):
        return "malformed_envelope"


def collect_synthetic(parent: Path, name: str, request: bytes,
                      events: tuple[SyntheticEvent, ...]) -> Path:
    """Record supplied synthetic events only, using a virtual monotonic timeline.

    A completion at exactly 30s is refused. Size includes the NDJSON newline.
    Oversize storage stops at 65536 bytes; hashes never claim the missing tail.
    No final receipt is created after a storage failure; preserve the directory.
    """
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", name):
        raise ValueError("unsafe observation name")
    if type(events) is not tuple or any(type(e) is not SyntheticEvent for e in events):
        raise TypeError("synthetic events only")
    previous = -1
    for event in events:
        if (type(event.offset_ns) is not int or event.offset_ns < previous or
                event.offset_ns < 0 or type(event.data) is not bytes or
                type(event.end) is not bool or type(event.failure) is not bool):
            raise ValueError("invalid synthetic timeline")
        previous = event.offset_ns
    req = _strict_json(request)
    if (not isinstance(req, dict) or req.get("jsonrpc") != "2.0" or
            type(req.get("id")) not in (str, int) or
            req.get("method") != "tools/call"):
        raise ValueError("invalid synthetic request")
    parent = Path(os.path.abspath(parent))
    _plain_directory(parent)
    destination = parent / name
    destination.mkdir(mode=0o700)  # Atomic new-only ownership between collectors.
    _plain_directory(destination)
    request_meta = _write_new(destination / "request.bin", request)
    raw = bytearray()
    received = 0
    elapsed = 0
    status = "incomplete_stream"
    complete = False
    for event in events:
        elapsed = min(event.offset_ns, WINDOW_NS)
        if event.offset_ns >= WINDOW_NS:
            status = "timeout"
            break
        received += len(event.data)
        remaining = LIMIT - len(raw)
        raw.extend(event.data[:remaining])
        if len(event.data) > remaining:
            status = "oversized_prefix_only"
            break
        if event.failure:
            status = "transport_failure"
            break
        if event.end:
            complete = True
            status = _frame_status(bytes(raw), req["id"])
            break
    response_meta = _write_new(destination / "response-prefix.bin", bytes(raw))
    receipt = {
        "schema": "c2b-synthetic-evidence/1", "synthetic": True,
        "studio_touched": False, "authorization": None,
        "status": status, "transport_end_observed": complete,
        "full_response_claim": complete and status == "transport_complete_semantics_unverified",
        "compatibility_pass": False, "elapsed_virtual_ns": elapsed,
        "limit_bytes": LIMIT, "window_ns": WINDOW_NS,
        "bytes_received_in_consumed_events": received,
        "total_upstream_response_bytes": len(raw) if complete else None,
        "request": request_meta, "retained_response": response_meta,
        "utc_verified": False,
    }
    encoded = (json.dumps(receipt, sort_keys=True, indent=2) + "\n").encode()
    receipt_meta = _write_new(destination / "receipt.json", encoded)
    # This is the final commit marker, not a signature or an immutable seal.
    _write_new(destination / "COMMITTED.json",
               (json.dumps(receipt_meta, sort_keys=True) + "\n").encode())
    return destination


def verify_synthetic(destination: Path) -> dict:
    """Verify final marker and actual retained files; reject partial runs/tampering."""
    destination = Path(os.path.abspath(destination))
    _plain_directory(destination)
    for name in ("COMMITTED.json", "receipt.json", "request.bin", "response-prefix.bin"):
        info = (destination / name).lstat()
        if not stat.S_ISREG(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("non-regular evidence file")
    marker = _strict_json((destination / "COMMITTED.json").read_bytes())
    raw = (destination / "receipt.json").read_bytes()
    if marker != _digest(raw):
        raise ValueError("receipt integrity failure")
    receipt = _strict_json(raw)
    for filename, key in (("request.bin", "request"),
                          ("response-prefix.bin", "retained_response")):
        if receipt[key] != _digest((destination / filename).read_bytes()):
            raise ValueError("evidence integrity failure")
    return receipt
