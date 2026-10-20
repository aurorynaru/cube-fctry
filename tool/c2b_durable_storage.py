"""R12 disposable Windows/NTFS offline candidate. NOT protected production storage.

Cooperative namespace/process-death fault model only. No dispatch, authority,
network, stale-lock recovery, deletion, production mode or physical reservation.
See docs/C1E_C2B_R12_STORAGE_QUALIFICATION.md before interpreting acknowledgments.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
import ctypes
import json
import os
from pathlib import Path
import re
import stat

from tool.c2b_authorization_gate import Consumption, Denied, digest


CATEGORIES = ("checkpoint", "prerequisite", "original", "intent", "consumption",
              "candidate", "denial", "outcome", "partial")
FINAL = ("denial", "outcome", "partial")
DESCRIPTOR_MAX = 4096  # format/parser bounds, not approved D2 storage policy
SEAL_MAX = 1024


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def decode(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise Denied("duplicate_json_key")
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs)
        if encode(value) != raw:
            raise Denied("noncanonical_record")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise Denied("malformed_record") from exc


def text(value):
    if type(value) is not str or not value or len(value) > 256:
        raise Denied("bounded_identity_required")
    return value


@dataclass(frozen=True)
class Limits:
    """Every numeric policy is injected. No production defaults."""
    record_bytes: int
    category_bytes: tuple[tuple[str, int], ...]
    session_bytes: int
    campaign_bytes: int
    max_sessions: int
    max_records: int
    finalization_bytes: int

    def __post_init__(self):
        values = (self.record_bytes, self.session_bytes, self.campaign_bytes,
                  self.max_sessions, self.max_records, self.finalization_bytes)
        if (any(type(x) is not int or x <= 0 for x in values) or
                type(self.category_bytes) is not tuple or
                len(self.category_bytes) != len(CATEGORIES) or
                {k for k, _ in self.category_bytes} != set(CATEGORIES) or
                any(type(v) is not int or v <= 0 for _, v in self.category_bytes) or
                self.finalization_bytes >= self.session_bytes):
            raise ValueError("explicit_fixture_limits_required")


def _plain(path, directory):
    info = path.lstat()
    if (stat.S_ISLNK(info.st_mode) or
            getattr(info, "st_file_attributes", 0) & 0x400 or
            (not stat.S_ISDIR(info.st_mode) if directory else not stat.S_ISREG(info.st_mode)) or
            (not directory and info.st_nlink != 1)):
        raise Denied("unsupported_namespace_object")
    return info


def _namespace(root):
    # Point-in-time checks ONLY. These are not handle-relative race protection,
    # effective ACL checks or proof of exclusive control of ancestors.
    raw = str(root)
    if (os.name != "nt" or not root.is_absolute() or raw.startswith("\\\\") or
            ":" in raw[2:] or ".." in root.parts or
            any(part.endswith((" ", ".")) for part in root.parts) or
            not re.fullmatch(r"c2b-r12-[A-Za-z0-9_-]+", root.name)):
        raise Denied("disposable_local_windows_namespace_required")
    for node in (root, *root.parents):
        _plain(node, True)
    fs = ctypes.create_unicode_buffer(32)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    get_drive = kernel.GetDriveTypeW
    get_drive.argtypes = [ctypes.c_wchar_p]
    get_drive.restype = ctypes.c_uint32
    if get_drive(root.anchor) != 3:  # DRIVE_FIXED; mapped/network/removable refused
        raise Denied("local_fixed_volume_not_verified")
    get_volume = kernel.GetVolumeInformationW
    get_volume.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32,
                           ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                           ctypes.c_wchar_p, ctypes.c_uint32]
    get_volume.restype = ctypes.c_int
    if not get_volume(root.anchor, None, 0, None, None, None, fs, len(fs)) or fs.value != "NTFS":
        raise Denied("local_ntfs_not_verified")


class OfflineLedger:
    """One disposable campaign. Explicit initialize; missing stores never recreated.

    mkdir guard is the cross-process linearization/exclusion primitive under the
    stated cooperative local NTFS model. Any uncertain mutation retains the guard
    indefinitely. No method can release a stale guard or spend an existing key.
    """
    def __init__(self, root: Path, limits: Limits, *, namespace_token: str):
        self.root, self.limits = Path(root), limits
        self.token = text(namespace_token)
        _namespace(self.root)
        self.header = self._read("FORMAT.json", DESCRIPTOR_MAX)
        if decode(self.header) != self._header():
            raise Denied("namespace_or_policy_mismatch")

    def _header(self):
        return {"schema": "c2b-r12-disposable/1", "production": False,
                "namespace_token": self.token, "limits": json.loads(encode(asdict(self.limits)))}

    @classmethod
    def initialize(cls, root, limits, *, namespace_token):
        root = Path(root)
        _namespace(root)
        if any(root.iterdir()):
            raise Denied("initialize_requires_new_empty_fixture")
        obj = object.__new__(cls)
        obj.root, obj.limits, obj.token = root, limits, text(namespace_token)
        obj._write("FORMAT.json", encode(obj._header()))
        return cls(root, limits, namespace_token=namespace_token)

    def _read(self, name, limit):
        path = self.root / name
        before = _plain(path, False)
        if before.st_size > limit:
            raise Denied("record_read_limit")
        with path.open("rb") as stream:
            actual = os.fstat(stream.fileno())
            raw = stream.read(limit + 1)
        after = _plain(path, False)
        if (len(raw) > limit or len(raw) != after.st_size or
                (before.st_dev, before.st_ino) != (actual.st_dev, actual.st_ino) or
                (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)):
            raise Denied("record_read_uncertainty")
        return raw

    def _write(self, name, raw):
        with (self.root / name).open("xb", buffering=0) as stream:
            view = memoryview(raw)
            while view:
                n = stream.write(view)
                if type(n) is not int or not 0 < n <= len(view):
                    raise OSError("incomplete_write")
                view = view[n:]
            stream.flush()
            os.fsync(stream.fileno())
        if self._read(name, len(raw)) != raw:
            raise Denied("write_readback_mismatch")

    def _test_point(self, phase):
        """Private fixed fixture seam; never an external command/callback input."""

    @contextmanager
    def _guard(self):
        _namespace(self.root)
        guard = self.root / "WRITER"
        try:
            guard.mkdir()
        except FileExistsError as exc:
            raise Denied("busy_or_quarantined_campaign") from exc
        owner = _plain(guard, True)
        self._dirty = False
        self._healthy = False
        complete = False
        try:
            if self._read("FORMAT.json", DESCRIPTOR_MAX) != self.header:
                raise Denied("changed_header")
            rows = self._audit()
            self._healthy = True
            yield rows
            complete = True
        finally:
            # Clean validation refusals may release; interrupted/mutated attempts
            # retain guard. No timeout, PID test, automatic retry or recovery reset.
            if complete or (self._healthy and not self._dirty):
                now = _plain(guard, True)
                if (now.st_dev, now.st_ino) != (owner.st_dev, owner.st_ino):
                    raise Denied("guard_identity_changed")
                guard.rmdir()

    def _audit(self):
        names = {p.name for p in self.root.iterdir()}
        if len(names) > self.limits.max_records * 3 + 2:
            raise Denied("record_count_uncertain")
        reservations = sorted(n for n in names if re.fullmatch(r"[0-9]{8}\.reserve", n))
        expected = {"FORMAT.json", "WRITER"} if "WRITER" in names else {"FORMAT.json"}
        rows, seen, previous = [], set(), "0" * 64
        for index, name in enumerate(reservations):
            stem = f"{index:08d}"
            if name != stem + ".reserve":
                raise Denied("record_sequence_gap")
            descriptor_raw = self._read(name, DESCRIPTOR_MAX)
            row = decode(descriptor_raw)
            if (type(row) is not dict or set(row) !=
                    {"category", "identity", "session", "length", "digest", "previous", "charge"}):
                raise Denied("invalid_descriptor")
            category = row["category"]
            key = (category, text(row["identity"]))
            text(row["session"])
            if (category not in CATEGORIES or key in seen or row["previous"] != previous or
                    type(row["length"]) is not int or not 0 <= row["length"] <= self.limits.record_bytes or
                    type(row["charge"]) is not int or
                    row["charge"] != row["length"] + len(descriptor_raw) + SEAL_MAX):
                raise Denied("inconsistent_or_duplicate_record")
            seen.add(key)
            raw = self._read(stem + ".bin", self.limits.record_bytes)
            info = _plain(self.root / (stem + ".bin"), False)
            seal_raw = self._read(stem + ".seal", SEAL_MAX)
            seal = decode(seal_raw)
            if (len(raw) != row["length"] or digest(raw) != row["digest"] or seal !=
                    {"descriptor": digest(descriptor_raw), "data": digest(raw),
                     "device": info.st_dev, "inode": info.st_ino}):
                raise Denied("record_integrity_or_replacement")
            row = row | {"raw": raw, "seal_digest": digest(seal_raw)}
            rows.append(row)
            previous = row["seal_digest"]
            expected.update((name, stem + ".bin", stem + ".seal"))
        if names != expected:
            raise Denied("unknown_or_incomplete_records")
        self._capacity(rows)
        return rows

    def _capacity(self, rows):
        sessions = {r["session"] for r in rows}
        if len(rows) > self.limits.max_records or len(sessions) > self.limits.max_sessions:
            raise Denied("count_budget_exhausted")
        caps = dict(self.limits.category_bytes)
        for category in CATEGORIES:
            if sum(r["charge"] for r in rows if r["category"] == category) > caps[category]:
                raise Denied("category_budget_exhausted")
        total = len(self.header) + sum(r["charge"] for r in rows)
        # Reserve EACH admitted session's unspent finalization allowance, including
        # in the campaign aggregate. Final records consume their own allowance.
        for session in sessions:
            own = [r for r in rows if r["session"] == session]
            final = sum(r["charge"] for r in own if r["category"] in FINAL)
            reserved = max(0, self.limits.finalization_bytes - final)
            if sum(r["charge"] for r in own) + reserved > self.limits.session_bytes:
                raise Denied("session_budget_or_finalization_reserve")
            total += reserved
        if total > self.limits.campaign_bytes:
            raise Denied("campaign_budget_or_finalization_reserve")

    def _append(self, rows, category, identity, session, raw):
        if category not in CATEGORIES or type(raw) is not bytes or len(raw) > self.limits.record_bytes:
            raise Denied("record_category_or_size_limit")
        text(identity)
        text(session)
        if any(r["category"] == category and r["identity"] == identity for r in rows):
            raise Denied("new_only_identity_exists")
        row = {"category": category, "identity": identity, "session": session,
               "length": len(raw), "digest": digest(raw),
               "previous": rows[-1]["seal_digest"] if rows else "0" * 64, "charge": 0}
        while True:
            charge = len(raw) + len(encode(row)) + SEAL_MAX
            if charge == row["charge"]:
                break
            row["charge"] = charge
        descriptor = encode(row)
        if len(descriptor) > DESCRIPTOR_MAX:
            raise Denied("descriptor_limit")
        self._capacity(rows + [row])
        stem = f"{len(rows):08d}"
        self._dirty = True  # BEFORE any uncertain exclusive create/write
        self._write(stem + ".reserve", descriptor)
        self._test_point("after_reservation")
        self._write(stem + ".bin", raw)
        self._test_point("after_data")
        info = _plain(self.root / (stem + ".bin"), False)
        seal = encode({"descriptor": digest(descriptor), "data": digest(raw),
                       "device": info.st_dev, "inode": info.st_ino})
        if len(seal) > SEAL_MAX:
            raise Denied("seal_limit")
        self._write(stem + ".seal", seal)
        self._audit()  # all originals and exact acknowledgment re-read, not cache
        self._test_point("after_seal")
        return digest(raw)

    def append(self, category, identity, session, raw):
        """Explicit synthetic original/checkpoint/partial admission; no dispatch."""
        if category not in ("checkpoint", "prerequisite", "partial"):
            raise Denied("typed_adapter_required_for_transaction_records")
        with self._guard() as rows:
            return self._append(rows, category, identity, session, raw)

    def snapshot(self):
        with self._guard() as rows:
            return rows

    def inspect_recovery(self):
        """Read-only, never trusts success or repairs an interrupted transaction.

        With an active writer, even this inventory is only a point-in-time sample.
        Conservatively report full reservation charges or unknown accounting.
        """
        _namespace(self.root)
        result = {"trusted_success": False, "reusable_authority": False,
                  "quarantined": (self.root / "WRITER").exists(), "verified_records": 0}
        try:
            rows = self._audit()
            result.update(verified_records=len(rows),
                          logical_reserved_bytes=len(self.header) + sum(r["charge"] for r in rows))
        except (OSError, Denied, KeyError, TypeError):
            result["accounting"] = "unknown_preserve_all_files"
        return result

    def consume(self, approval, attempt):
        # Scope authentication remains the R11 verifier's responsibility. No
        # production approval is accepted/created by this disposable candidate.
        text(attempt)
        key = (text(approval.issuer), text(approval.approval_id))
        identity = digest(encode(key))
        raw = encode({"key": key, "binding": asdict(approval.binding),
                      "binding_digest": approval.binding.digest, "attempt": attempt,
                      "state": "spent_intent_never_dispatch_permission", "fake_only": True})
        with self._guard() as rows:
            self._append(rows, "consumption", identity, approval.binding.session, raw)
            self._test_point("before_consumption_ack")
            stored = decode(self._audit()[-1]["raw"])
            if stored != decode(raw):
                raise Denied("consumption_readback_uncertain")
            return Consumption(key, stored["binding_digest"], stored["attempt"])


class OfflineEvidenceStore:
    """R11 evidence interface adapter; action/checkpoint/policy supplied explicitly.

    Prerequisite originals must already be separately admitted under this session.
    Labels/digests establish local consistency, NOT independent approval/time/ACLs.
    """
    def __init__(self, ledger, action):
        self.ledger, self.binding = ledger, action.binding

    def _prerequisites(self, rows, action, digests):
        action.verify(self.binding)
        available = {r["digest"] for r in rows if r["category"] in ("checkpoint", "prerequisite")
                     and r["session"] == self.binding.session}
        checkpoints = {r["digest"] for r in rows if r["category"] == "checkpoint"
                       and r["session"] == self.binding.session}
        if (type(digests) not in (tuple, list) or not digests or
                any(type(d) is not str or d not in available for d in digests) or
                self.binding.checkpoint_digest not in checkpoints or
                self.binding.policy_digest not in available):
            raise Denied("missing_checkpoint_policy_or_prerequisite_originals")

    def prepare(self, attempt, action, evidence_digests):
        with self.ledger._guard() as rows:
            self._prerequisites(rows, action, evidence_digests)
            self.ledger._append(rows, "original", attempt, self.binding.session, action.raw)
            rows = self.ledger._audit()
            raw = encode({"attempt": attempt, "binding": asdict(self.binding),
                          "action_digest": digest(action.raw), "evidence": evidence_digests,
                          "decision": "validated_candidate_not_dispatch_permission"})
            return self.ledger._append(rows, "intent", attempt, self.binding.session, raw)

    def verify(self, attempt, action, intent_digest):
        with self.ledger._guard() as rows:
            intents = [r for r in rows if r["category"] == "intent" and r["identity"] == attempt]
            originals = [r for r in rows if r["category"] == "original" and r["identity"] == attempt]
            if len(intents) != 1 or len(originals) != 1 or intents[0]["digest"] != intent_digest:
                raise Denied("missing_or_changed_intent")
            intent = decode(intents[0]["raw"])
            self._prerequisites(rows, action, intent["evidence"])
            if (intent["binding"] != asdict(self.binding) or intent["attempt"] != attempt or
                    intent["action_digest"] != digest(action.raw) or originals[0]["raw"] != action.raw or
                    intent["decision"] != "validated_candidate_not_dispatch_permission"):
                raise Denied("intent_binding_or_original_mismatch")

    def record(self, attempt, decision):
        kinds = {"spent_candidate_not_dispatch_permission": "candidate",
                 "denied_or_uncertain": "denial", "simulated_dispatch_only": "outcome"}
        kind = kinds.get(decision.get("decision"))
        if (kind is None or decision.get("attempt") != attempt or
                decision.get("fake_only") is not True or
                decision.get("production_authorization") is not False or
                decision.get("utc_authenticated") is not False or
                decision.get("binding", self.binding.digest) != self.binding.digest):
            raise Denied("invalid_offline_decision")
        with self.ledger._guard() as rows:
            if kind in ("candidate", "outcome"):
                if (decision.get("binding") != self.binding.digest or
                        any(r["identity"] == attempt and r["category"] in ("denial", "outcome")
                            for r in rows)):
                    raise Denied("terminal_or_unbound_evidence_attempt")
                intents = [r for r in rows if r["category"] == "intent" and r["identity"] == attempt]
                spent = [decode(r["raw"]) for r in rows if r["category"] == "consumption"]
                if (len(intents) != 1 or decision.get("intent") != intents[0]["digest"] or
                        not any(r["attempt"] == attempt and r["binding_digest"] == self.binding.digest
                                for r in spent)):
                    raise Denied("candidate_without_exact_spent_intent")
            if kind == "outcome":
                candidates = [r for r in rows if r["category"] == "candidate" and r["identity"] == attempt]
                if len(candidates) != 1 or decision.get("candidate") != candidates[0]["digest"]:
                    raise Denied("outcome_without_candidate")
            return self.ledger._append(rows, kind, attempt, self.binding.session, encode(decision))


def retention_eligible(*, created_ns, now_ns, review_complete, minimum_days):
    """Pure advisory predicate; no deletion or authenticated-time claim."""
    if (any(type(x) is not int or x < 0 for x in (created_ns, now_ns, minimum_days)) or
            minimum_days < 30 or type(review_complete) is not bool or now_ns < created_ns):
        raise Denied("retention_inputs_unverified")
    return review_complete and now_ns - created_ns >= minimum_days * 86_400_000_000_000
