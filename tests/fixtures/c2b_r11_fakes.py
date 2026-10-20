"""R11 test doubles only. All values are invented fixtures, NOT human/UTC proof.

Fake authority/time tokens are opaque lookup keys supplied by tests. They are not
signatures, bearer approvals, TEST-ONLY R9 continuations, or production roots.
Memory stores survive only while this Python object survives; no durability claim.
"""
from contextlib import contextmanager
from dataclasses import replace
import threading

from tool.c2b_authorization_gate import (
    Consumption, Denied, SourceInterval, TimeSample, VerifiedApproval, digest, _json,
)


APPROVAL = b"fixture-independent-authority-event"
TIME_A = b"fixture-independent-clock-A"
TIME_B = b"fixture-independent-clock-B"


class FakeApprovalVerifier:
    def __init__(self, binding):
        self.lock = threading.RLock()
        self.claim = VerifiedApproval("fixture-issuer", "fixture-approval-1", "fixture-human",
                                      "fixture-out-of-model-channel", binding,
                                      0, 10, 1000, digest(APPROVAL))
        self.withdrawn = False
        self.channel_healthy = True
        self.validations = 0

    def validate(self, evidence, binding):
        with self.lock:
            self.validations += 1
            if evidence != APPROVAL:
                raise Denied("fake_approval_not_authenticated")
            if not self.channel_healthy:
                raise Denied("withdrawal_status_unknown")
            if self.withdrawn:
                raise Denied("withdrawn")
            if self.claim.binding != binding:
                raise Denied("fake_scope_mismatch")
            return self.claim

    def withdraw(self):
        with self.lock:
            self.withdrawn = True  # acknowledgment and final byte share this lock

    @contextmanager
    def dispatch_guard(self, approval):
        with self.lock:
            if self.withdrawn or not self.channel_healthy:
                raise Denied("withdrawn_or_channel_lost")
            yield


class FakeMonitor:
    def __init__(self):
        self.current = TimeSample(100, "fixture-boot-process-monitor-generation", True)

    def sample(self):
        return self.current


class FakeTimeEvidenceVerifier:
    def __init__(self, epoch):
        self.claims = {
            TIME_A: SourceInterval("fixture-A", "fixture-domain-A", digest(TIME_A), epoch,
                                   100, 100, 104),
            TIME_B: SourceInterval("fixture-B", "fixture-domain-B", digest(TIME_B), epoch,
                                   100, 102, 106),
        }

    def validate(self, evidence):
        if evidence not in self.claims:
            raise Denied("fake_time_not_authenticated")
        return self.claims[evidence]

    def change(self, key=TIME_B, **fields):
        self.claims[key] = replace(self.claims[key], **fields)


class FakeConsumptionStore:
    def __init__(self):
        self.lock = threading.Lock()
        self.spent = {}
        self.uncertain_after_commit = False
        self.crash_after_commit = False

    def consume(self, approval, attempt):
        with self.lock:
            if approval.key in self.spent:
                raise Denied("already_consumed_or_uncertain")
            receipt = Consumption(approval.key, approval.binding.digest, attempt)
            self.spent[approval.key] = receipt
            if self.crash_after_commit:
                raise SimulatedCrash("fixture crash after spend before any byte")
            if self.uncertain_after_commit:
                raise OSError("fixture ambiguous commit acknowledgment")
            return receipt


class SimulatedCrash(BaseException):
    """Skip normal exception handling; this is NOT an actual persistence test."""


class FakeEvidenceStore:
    def __init__(self, action):
        self.lock = threading.RLock()
        self.checkpoint = action.binding.checkpoint_digest
        self.binding = action.binding
        self.intents = {}
        self.records = []
        self.healthy = True
        self.fail_prepare = self.fail_record = False
        self.after_prepare = None  # deterministic test seam, never production input

    def _health(self, action):
        if not self.healthy:
            raise Denied("evidence_storage_uncertain")
        if self.binding != action.binding or self.checkpoint != action.binding.checkpoint_digest:
            raise Denied("checkpoint_or_storage_binding_mismatch")

    def prepare(self, attempt, action, evidence_digests):
        with self.lock:
            self._health(action)
            if self.fail_prepare:
                raise OSError("fixture intent persistence failure")
            if attempt in self.intents:
                raise Denied("intent_exists")
            raw = _json({"attempt": attempt, "binding": action.binding.digest,
                         "action": action.raw.decode("ascii"),
                         "evidence": evidence_digests,
                         "decision": "validated_candidate_not_dispatch_permission"})
            self.intents[attempt] = raw
            if self.after_prepare:
                self.after_prepare()
            return digest(raw)

    def verify(self, attempt, action, intent_digest):
        with self.lock:
            self._health(action)
            if digest(self.intents[attempt]) != intent_digest:
                raise Denied("intent_changed")

    def record(self, attempt, decision):
        with self.lock:
            if self.fail_record:
                raise OSError("fixture decision storage failure")
            raw = _json(decision)
            self.records.append((attempt, raw))
            return digest(raw)
