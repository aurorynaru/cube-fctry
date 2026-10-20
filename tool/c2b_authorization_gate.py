"""R11 offline-only authorization contracts and ONE inert synthetic dispatch.

No MCP, launcher, CLI, network, signing, time acquisition, or filesystem adapter.
Injected dependencies are trusted test doubles, NOT production trust roots. See
docs/C1E_C2B_R11_AUTHORIZATION_GATE.md for provisioning and durability blockers.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import hashlib
import json
import threading
from typing import Protocol
import uuid


class Denied(Exception):
    """Missing, invalid, spent, or uncertain prerequisite; never retry this gate."""


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _checked_digest(value) -> str:
    if (type(value) is not str or len(value) != 64 or
            any(c not in "0123456789abcdef" for c in value)):
        raise Denied("invalid_storage_digest_acknowledgment")
    return value


def _json(value) -> bytes:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=True, allow_nan=False).encode("ascii")
    if len(raw) > 4096:
        raise Denied("synthetic_action_limit")
    return raw


@dataclass(frozen=True)
class Binding:
    observation: str
    session: str
    target_digest: str
    action_digest: str
    checkpoint_digest: str
    policy_digest: str
    destination: str

    @property
    def digest(self) -> str:
        return digest(_json(self.__dict__))


@dataclass(frozen=True)
class PreparedAction:
    binding: Binding
    raw: bytes

    def verify(self, expected: Binding) -> None:
        if (self.binding != expected or type(self.raw) is not bytes or
                digest(self.raw) != expected.action_digest):
            raise Denied("changed_action")


def prepare_action(*, observation: str, session: str, target: dict, details: dict,
                   checkpoint_digest: str, policy_digest: str,
                   destination: str) -> PreparedAction:
    """Snapshot caller data. This is a synthetic envelope, NOT an MCP frame.

    Target identity is supplied explicitly; no live identity/default is inferred.
    Policy/checkpoint/destination references must be independently verified later.
    """
    if (type(target) is not dict or not target or type(details) is not dict or
            any(type(x) is not str or not x or len(x) > 256
                for x in (observation, session, destination))):
        raise Denied("invalid_synthetic_action")
    for value in (checkpoint_digest, policy_digest):
        if (type(value) is not str or len(value) != 64 or
                any(c not in "0123456789abcdef" for c in value)):
            raise Denied("invalid_reference_digest")
    target_raw = _json(target)
    raw = _json({"schema": "c2b-r11-inert-action/1", "fake_only": True,
                 "operation": "synthetic.read_only", "target": target,
                 "details": details})
    binding = Binding(observation, session, digest(target_raw), digest(raw),
                      checkpoint_digest, policy_digest, destination)
    return PreparedAction(binding, raw)


@dataclass(frozen=True)
class VerifiedApproval:
    issuer: str
    approval_id: str
    actor: str
    channel: str
    binding: Binding
    approved_ns: int
    not_before_ns: int
    expires_ns: int
    evidence_digest: str

    @property
    def key(self) -> tuple[str, str]:
        return self.issuer, self.approval_id


class ApprovalVerifier(Protocol):
    """Authenticate independently provisioned principal/channel/root, event and
    exact scope (including ordered single attempt, identity, policy, deployment,
    checkpoint, session, destination and lifecycle budgets). Reject missing,
    forged, stale/unknown status, channel loss, withdrawn or altered authority.

    Returned claims may be trusted ONLY under that independently deployed verifier.
    dispatch_guard serializes withdrawal acknowledgments with revalidation and the
    first-byte transition. No acknowledgment before that transition may be missed.
    It must refuse on unknown status, not cache an earlier active boolean.
    No arbitrary callback/agent argument is an approval or withdrawal event.
    """
    def validate(self, evidence: bytes | None, binding: Binding) -> VerifiedApproval: ...

    def dispatch_guard(self, approval: VerifiedApproval) -> AbstractContextManager[None]: ...


@dataclass(frozen=True)
class TimeSample:
    monotonic_ns: int
    epoch: str  # boot + process + uninterrupted monitor/calibration generation
    healthy: bool


class LocalMonitor(Protocol):
    """Report monotonic elapsed time and checked continuity, NOT trusted UTC.
    Steps, suspend/resume, reboot, sample loss or uncertain timer health refuse.
    """
    def sample(self) -> TimeSample: ...


@dataclass(frozen=True)
class SourceInterval:
    source: str
    independence_domain: str
    evidence_digest: str
    epoch: str
    anchor_ns: int
    lower_ns: int
    upper_ns: int


class TimeEvidenceVerifier(Protocol):
    """Authenticate each operator-acquired source, provenance, independence domain,
    capture brackets/generation/precision/error/transit/drift bounds. Return a
    conservative UTC interval at a COMMON local monotonic anchor, in this epoch.
    Reject unsigned copied times, unjustified bounds and shared-clock aliases.
    The R11 implementation is an injected fake lookup only; no sources are chosen.
    """
    def validate(self, evidence: bytes) -> SourceInterval: ...


@dataclass(frozen=True)
class TimeWindow:
    lower_ns: int
    upper_ns: int
    evidence_digests: tuple[str, str]


class TrustedTimeVerifier(Protocol):
    """Verify exactly two independent authenticated inputs, continuity, freshness,
    overlap, covering width and conservative elapsed drift. No average/intersection.
    Returned bounds are trusted only if acquisition/root/monitor are qualified.
    """
    def verify(self, evidence: tuple[bytes, bytes], sample: TimeSample) -> TimeWindow: ...


@dataclass(frozen=True)
class TimeLimits:
    max_age_ns: int
    max_width_ns: int
    drift_ppb: int


class TwoSourceTimeVerifier:
    """Pure interval arithmetic; limits are injected TEST values, not D4 approval."""
    def __init__(self, sources: TimeEvidenceVerifier, limits: TimeLimits):
        if (any(type(x) is not int or x < 0 for x in
                (limits.max_age_ns, limits.max_width_ns, limits.drift_ppb)) or
                limits.max_age_ns == 0 or limits.max_width_ns == 0):
            raise ValueError("explicit_nonnegative_time_bounds_required")
        self.sources, self.limits = sources, limits

    def verify(self, evidence: tuple[bytes, bytes], sample: TimeSample) -> TimeWindow:
        if (type(evidence) is not tuple or len(evidence) != 2 or
                any(type(x) is not bytes or not x or len(x) > 4096 for x in evidence)):
            raise Denied("two_time_sources_required")
        if (sample.healthy is not True or type(sample.monotonic_ns) is not int or
                sample.monotonic_ns < 0 or not sample.epoch):
            raise Denied("monitor_uncertainty")
        a, b = (self.sources.validate(x) for x in evidence)
        for source, raw in zip((a, b), evidence):
            if (not source.source or not source.independence_domain or
                    source.evidence_digest != digest(raw) or source.epoch != sample.epoch or
                    any(type(x) is not int for x in
                        (source.anchor_ns, source.lower_ns, source.upper_ns)) or
                    source.anchor_ns < 0 or source.lower_ns > source.upper_ns):
                raise Denied("invalid_time_binding_or_bounds")
        if a.source == b.source or a.independence_domain == b.independence_domain:
            raise Denied("time_sources_not_independent")
        if a.anchor_ns != b.anchor_ns:
            raise Denied("time_anchor_disagreement")
        elapsed = sample.monotonic_ns - a.anchor_ns
        if elapsed < 0 or elapsed > self.limits.max_age_ns:
            raise Denied("time_stale_or_monotonic_step")
        if max(a.lower_ns, b.lower_ns) > min(a.upper_ns, b.upper_ns):
            raise Denied("time_source_disagreement")
        # Outward integer rounding: never shorten the uncertainty interval.
        drift = (elapsed * self.limits.drift_ppb + 999_999_999) // 1_000_000_000
        lower = min(a.lower_ns, b.lower_ns) + elapsed - drift
        upper = max(a.upper_ns, b.upper_ns) + elapsed + drift
        if upper - lower > self.limits.max_width_ns:
            raise Denied("time_interval_too_wide")
        return TimeWindow(lower, upper, (digest(evidence[0]), digest(evidence[1])))


@dataclass(frozen=True)
class Consumption:
    approval_key: tuple[str, str]
    binding_digest: str
    attempt: str


class ConsumptionStore(Protocol):
    """Atomic new-only consume keyed by issuer + approval ID, across bindings,
    sessions, controllers and restarts. One winner only. Success means the spent
    intent is durably committed/readback-verified BEFORE any possible byte.
    Never release on failure; uncertain/crashed intents remain spent/quarantined.
    No automatic rollback, lease expiry, restore-to-unspent or retry is allowed.
    R11's lock-protected in-memory fake does NOT implement durable replay safety.
    """
    def consume(self, approval: VerifiedApproval, attempt: str) -> Consumption: ...


class ProtectedEvidenceStore(Protocol):
    """prepare: independently verify checkpoint originals/binding and storage
    policy; exclusively persist/read back exact action, prerequisite digests and
    attempt intent; return its digest. verify: recheck originals, intent and health.
    record: append new-only bound candidate/decision/outcome, read back, return its
    digest. Multiple records per attempt are append-only, never overwrites.

    Production requirements (UNIMPLEMENTED): operator-selected protected NTFS
    namespace/ancestors, effective ACLs, agent/child non-writability, exclusive
    trusted writer or handle-relative no-follow access, quota/category/aggregate/
    physical reservation with failure/finalization headroom, confidentiality,
    retention >=30 days AND review completion, approved backups/recovery owner,
    specified flush/readback durability. Torn/missing/replaced/unknown state refuses;
    no regenerated success or automatic resume. Hashes alone are not authenticity.
    """
    def prepare(self, attempt: str, action: PreparedAction, evidence_digests: tuple[str, ...]) -> str: ...

    def verify(self, attempt: str, action: PreparedAction, intent_digest: str) -> None: ...

    def record(self, attempt: str, decision: dict) -> str: ...


class InertSink:
    """Only a local byte collector, deliberately no transport/write callback."""
    def __init__(self):
        self._bytes = b""

    @property
    def bytes(self) -> bytes:
        return self._bytes


@dataclass(frozen=True)
class OfflineResult:
    fake_only: bool
    completed: bool
    reason: str
    decision_digest: str | None
    simulated_bytes: int

    @property
    def dispatched(self) -> bool:
        """Factual per-attempt bytes, even if outcome storage then failed."""
        return self.simulated_bytes > 0


class OfflineAuthorizationGate:
    """Disposable, dependency-injected, fake-only slice. No production mode.

    Slow storage/consumption precedes the final guarded revalidation/time check.
    The sink cannot be supplied/replaced through a constructor transport seam.
    This is NOT wired into R9's frontend or R7's contained child boundary.
    """
    def __init__(self, *, approvals: ApprovalVerifier, time_verifier: TrustedTimeVerifier,
                 monitor: LocalMonitor, consumption: ConsumptionStore,
                 evidence: ProtectedEvidenceStore, operation_budget_ns: int,
                 margin_ns: int):
        if (type(operation_budget_ns) is not int or operation_budget_ns <= 0 or
                type(margin_ns) is not int or margin_ns < 0):
            raise ValueError("explicit_synthetic_budget_required")
        self.approvals, self.time_verifier, self.monitor = approvals, time_verifier, monitor
        self.consumption, self.evidence = consumption, evidence
        self.budget, self.margin = operation_budget_ns, margin_ns
        self.sink = InertSink()
        self._lock = threading.Lock()
        self._terminal = False

    def _approval(self, raw, binding):
        if type(raw) is not bytes or not raw or len(raw) > 4096:
            raise Denied("independent_approval_required")
        approval = self.approvals.validate(raw, binding)
        if (approval.binding != binding or approval.evidence_digest != digest(raw) or
                any(type(x) is not str or not x for x in
                    (approval.issuer, approval.approval_id, approval.actor, approval.channel)) or
                any(type(x) is not int for x in
                    (approval.approved_ns, approval.not_before_ns, approval.expires_ns)) or
                not approval.approved_ns <= approval.not_before_ns < approval.expires_ns):
            raise Denied("invalid_approval_binding")
        return approval

    def _valid_time(self, approval, inputs, sample):
        window = self.time_verifier.verify(inputs, sample)
        if window.lower_ns < max(approval.approved_ns, approval.not_before_ns):
            raise Denied("approval_not_yet_valid")
        if window.upper_ns + self.budget + self.margin >= approval.expires_ns:
            raise Denied("expiry_or_insufficient_budget")
        return window

    def run(self, action: PreparedAction, approval_evidence: bytes | None,
            time_evidence: tuple[bytes, bytes]) -> OfflineResult:
        attempt = str(uuid.uuid4())  # correlation only; never authority
        if not self._lock.acquire(blocking=False):
            # Not admitted: do not queue on a store that the active attempt may
            # own. No persistent rejection receipt is claimed for this caller.
            return OfflineResult(True, False, "concurrent_attempt", None, 0)
        prior_bytes = len(self.sink.bytes)
        decision = {"schema": "c2b-r11-offline-decision/1", "fake_only": True,
                    "production_authorization": False, "utc_authenticated": False,
                    "attempt": attempt}
        try:
            if self._terminal:
                raise Denied("terminal_gate")
            self._terminal = True  # also terminal after exceptions/crash uncertainty
            binding = action.binding
            action.verify(binding)
            decision["binding"] = binding.digest
            approval = self._approval(approval_evidence, binding)
            initial_sample = self.monitor.sample()
            initial = self._valid_time(approval, time_evidence, initial_sample)
            decision["approval"] = approval.evidence_digest
            decision["time"] = initial.evidence_digests
            decision["initial_interval"] = (initial.lower_ns, initial.upper_ns)
            # Bound the whole attempt before any slow persistence. Never reset it.
            deadline = initial_sample.monotonic_ns + self.budget
            intent = _checked_digest(self.evidence.prepare(
                attempt, action, (approval.evidence_digest, *initial.evidence_digests)))
            decision["intent"] = intent
            consumed = self.consumption.consume(approval, attempt)
            if consumed != Consumption(approval.key, binding.digest, attempt):
                raise Denied("uncertain_consumption_acknowledgment")
            decision["spent"] = True
            # Record a spent candidate, NOT a dispatch success, before final
            # checks. Failure to record it blocks all bytes. The final outcome
            # is a separate append after the in-memory transition.
            decision["candidate"] = _checked_digest(self.evidence.record(
                attempt, decision | {"decision": "spent_candidate_not_dispatch_permission"}))
            # Persistence may be slow. Verify it BEFORE the final authority/time
            # checks. No disk I/O or unguarded dispatch queue follows those checks.
            with self.approvals.dispatch_guard(approval):
                self.evidence.verify(attempt, action, intent)
                action.verify(binding)
                if self._approval(approval_evidence, binding) != approval:
                    raise Denied("approval_changed")
                sample = self.monitor.sample()
                if (sample.epoch != initial_sample.epoch or
                        sample.monotonic_ns < initial_sample.monotonic_ns or
                        sample.monotonic_ns >= deadline):
                    raise Denied("attempt_deadline_or_continuity")
                final = self._valid_time(approval, time_evidence, sample)
                # Exact first-byte linearization point; no injectable transport.
                self.sink._bytes += action.raw
            decision["final_interval"] = (final.lower_ns, final.upper_ns)
            decision["decision"] = "simulated_dispatch_only"
            receipt = _checked_digest(self.evidence.record(attempt, decision))
            return OfflineResult(True, True, "simulated_dispatch_only", receipt,
                                 len(self.sink.bytes) - prior_bytes)
        except Exception as exc:
            # Even an adapter exception is terminal. Never return a success receipt
            # after uncertain storage; bytes already sent cannot be retracted.
            reason = str(exc) if isinstance(exc, Denied) else "dependency_uncertainty"
            decision.update(decision="denied_or_uncertain", reason=reason,
                            simulated_bytes=len(self.sink.bytes) - prior_bytes)
            try:
                receipt = _checked_digest(self.evidence.record(attempt, decision))
            except Exception:
                receipt = None
                reason = "evidence_record_uncertainty"
            return OfflineResult(True, False, reason, receipt, len(self.sink.bytes) - prior_bytes)
        finally:
            self._lock.release()
