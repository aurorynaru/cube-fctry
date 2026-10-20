"""R9 TEST ONLY review injection. No human authority, UTC, or protected storage.

One new-only observation directory burns the synthetic attempt across crashes.
Never resumes an existing directory, even if its checkpoint is intact.
"""
from __future__ import annotations

import json
import stat
import threading
import time
import uuid

from tool.c2b_evidence import LIMIT, _digest, _strict_json, _write_new
from tool.c2b_recording_supervisor import Refusal, TARGET, _json_frame

EXPECTATIONS = {"studio_id": TARGET, "name": "Place1", "mode": "Edit",
                "team_create": False, "is_unsaved": True, "place_id": 0,
                "game_id": 0, "creator_id": 0, "creator_type": "User",
                "user_id": 11822718311, "user_name": "aurory_naru"}


def _matches(value, expected):
    try:
        return type(value) is dict and _json_frame(value) == _json_frame(expected)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return False


class SyntheticReview:
    def __init__(self, observation: str, *, wait_seconds: float = 5.0):
        if type(wait_seconds) not in (float, int) or not 0 < wait_seconds <= 30:
            raise ValueError("bounded synthetic wait required")
        self.observation = observation
        self.session_id = str(uuid.uuid4())
        self.wait_seconds = wait_seconds
        self.lock = threading.RLock()
        self.ready = threading.Event()
        self.finished = threading.Event()
        self.wake = threading.Event()
        self.failure = None
        self.phase = "INERT"
        self.destination = self.checkpoint = self.checkpoint_meta = None
        self.discovery_result = self.state_result = self.receipt = None
        self.continuation = None
        self.state_requested = False
        self.session = None

    def launch_token(self):
        return {"test_only": True, "action": "synthetic_launch", "observation": self.observation,
                "session": self.session_id, "target": TARGET}

    def authorize(self, token):
        with self.lock:
            if self.phase != "INERT" or not _matches(token, self.launch_token()):
                self.abort("invalid_synthetic_launch")
                raise Refusal(self.failure)
            self.phase = "LAUNCH_AUTHORIZED"

    def bind(self, destination):
        with self.lock:
            self.check_dispatch()
            if self.phase != "LAUNCH_AUTHORIZED" or destination.name != self.observation:
                raise Refusal("synthetic_launch_required")
            self.destination = destination
            _write_new(destination / "synthetic-session.json", _json_frame(self.launch_token()))
            self.phase = "DISCOVERY"

    def abort(self, reason):
        with self.lock:
            self.failure = self.failure or reason
            self.phase = "TERMINAL"
            self.wake.set()
            if self.session is not None:
                self.session.capture.fail(self.failure)
                self.session.stop()

    def check_dispatch(self):
        with self.lock:
            if self.failure or self.phase == "TERMINAL":
                raise OSError(self.failure or "terminal_synthetic_session")
            if self.phase == "STATE_SPENT":
                try:
                    self.verify_checkpoint()
                    if (_digest(self._read("synthetic-session.json")) != self.checkpoint["launch"] or
                            time.monotonic() >= self.review_deadline):
                        raise Refusal("synthetic_session_or_review_deadline_failure")
                except (Refusal, OSError, ValueError, UnicodeError) as exc:
                    self.failure = "checkpoint_dispatch_verification_failure"
                    self.phase = "TERMINAL"
                    raise OSError(self.failure) from exc

    def continuation_token(self):
        if self.checkpoint_meta is None:
            raise Refusal("no_checkpoint")
        return {"test_only": True, "action": "continue_synthetic_state",
                "observation": self.observation, "session": self.session_id,
                "checkpoint": self.checkpoint_meta,
                "arguments": {"studio_id": TARGET}}

    def inject_continuation(self, token):
        with self.lock:
            if (self.phase != "WAIT_REVIEW" or self.continuation is not None or
                    not _matches(token, self.continuation_token())):
                self.abort("invalid_or_declined_synthetic_continuation")
                raise Refusal(self.failure)
            self.continuation = json.loads(json.dumps(token))
            self.wake.set()

    def request_state(self):
        with self.lock:
            if self.phase != "WAIT_REVIEW" or self.continuation is None or self.state_requested:
                self.abort("synthetic_continuation_required")
                raise Refusal(self.failure)
            self.state_requested = True
            self.wake.set()

    def _read(self, name):
        path = self.destination / name
        info = path.lstat()
        if (info.st_size > LIMIT or not stat.S_ISREG(info.st_mode) or stat.S_ISLNK(info.st_mode) or
                getattr(info, "st_file_attributes", 0) & 0x400):
            raise Refusal("checkpoint_nonregular_file")
        with path.open("rb") as stream:
            raw = stream.read(LIMIT + 1)
        if len(raw) > LIMIT:
            raise Refusal("checkpoint_read_limit")
        return raw

    def verify_checkpoint(self):
        raw = self._read("discovery-checkpoint.json")
        if _digest(raw) != self.checkpoint_meta or _strict_json(raw) != self.checkpoint:
            raise Refusal("checkpoint_integrity_failure")
        for name, meta in self.checkpoint["files"].items():
            if _digest(self._read(name)) != meta:
                raise Refusal("checkpoint_evidence_failure")

    def _test_checkpoint(self, phase, session):
        """Private deterministic test death seam, not a callback input."""

    def pause(self, session, result):
        self._test_checkpoint("before_checkpoint", session)
        with self.lock:
            self.check_dispatch()
            self.checkpoint = {"schema": "c2b-test-only-checkpoint/1", "test_only": True,
                               "observation": self.observation, "session": self.session_id,
                               "expectations": EXPECTATIONS, "result": result,
                               "files": dict(session.files), "calls": list(session.calls),
                               "launch": _digest(self._read("synthetic-session.json"))}
            session.save("discovery-checkpoint.json", _json_frame(self.checkpoint))
            self.checkpoint_meta = session.files["discovery-checkpoint.json"]
            self.verify_checkpoint()
            self.discovery_result = result
            self.phase = "WAIT_REVIEW"
            deadline = time.monotonic() + self.wait_seconds
            self.review_deadline = deadline
            self.ready.set()
        self._test_checkpoint("after_checkpoint", session)
        while True:
            with self.lock, session.capture.condition:
                self.check_dispatch()
                if (session.capture.failure or session.capture.stdout_eof or
                        session.capture.stderr_eof or session.offset != len(session.capture.stdout)):
                    raise Refusal("unexpected_upstream_while_paused")
                if time.monotonic() >= deadline:
                    raise Refusal("synthetic_review_timeout")
                if self.continuation is not None and self.state_requested:
                    self.verify_checkpoint()  # Re-read originals immediately before state intent.
                    if _digest(self._read("synthetic-session.json")) != self.checkpoint["launch"]:
                        raise Refusal("session_binding_failure")
                    session.save("state-attempt.json", _json_frame(self.continuation))
                    self.phase = "STATE_SPENT"
                    return
                self.wake.clear()
            self.wake.wait(0.01)
