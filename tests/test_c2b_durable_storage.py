from dataclasses import replace
import errno
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import uuid

from tool import c2b_durable_storage as storage
from tool.c2b_authorization_gate import (
    Consumption, Denied, OfflineAuthorizationGate, TimeLimits, TwoSourceTimeVerifier, digest,
)
from tests.fixtures.c2b_r11_fakes import (
    APPROVAL, TIME_A, TIME_B, FakeApprovalVerifier, FakeMonitor, FakeTimeEvidenceVerifier,
)
from tests.fixtures.c2b_r12_worker import CHECKPOINT, POLICY, action, limits


@unittest.skipUnless(os.name == "nt", "R12 local Windows/NTFS candidate requires Windows")
class DurableStorageTests(unittest.TestCase):
    def setUp(self):
        self.parent = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "opencode"
        self.assertTrue(self.parent.is_dir())
        self.temp = tempfile.TemporaryDirectory(prefix="c2b-r12-", dir=self.parent)
        self.root = Path(self.temp.name)
        self.token = str(uuid.uuid4())
        self.policy = limits()
        self.ledger = storage.OfflineLedger.initialize(self.root, self.policy, namespace_token=self.token)
        self.prepared = action()
        self.approval = FakeApprovalVerifier(self.prepared.binding).claim
        self.workers = []
        self.addCleanup(self.cleanup_owned)

    def cleanup_owned(self):
        for worker in self.workers:
            if worker.poll() is None:
                worker.terminate()  # exact Popen-owned handle, never process search
            worker.communicate(timeout=5)
        # Verify fixture ownership before TemporaryDirectory removes synthetic data.
        self.assertEqual(self.root.parent, self.parent)
        self.assertTrue(self.root.name.startswith("c2b-r12-"))
        storage._namespace(self.root)
        header = storage.decode((self.root / "FORMAT.json").read_bytes())
        self.assertEqual(header["namespace_token"], self.token)
        self.temp.cleanup()

    def reopen(self):
        return storage.OfflineLedger(self.root, self.policy, namespace_token=self.token)

    def worker(self, operation):
        script = Path(__file__).parent / "fixtures" / "c2b_r12_worker.py"
        worker = subprocess.Popen([sys.executable, "-I", "-S", "-u", str(script),
                                   str(self.root), self.token, operation],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True)
        self.workers.append(worker)
        return worker

    def ready(self, worker):
        self.line(worker, "READY\n")

    def line(self, worker, expected):
        # Bounded OS pipe readiness on Windows via a reader future; main test owns
        # the exact worker and terminates it on timeout. No timing/race sleeps.
        import concurrent.futures
        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(worker.stdout.readline)
        try:
            self.assertEqual(future.result(timeout=5), expected)
        except BaseException:
            if worker.poll() is None:
                worker.terminate()
            raise
        finally:
            pool.shutdown(wait=True)

    def finish(self, worker):
        worker.stdin.write("GO\n")
        worker.stdin.flush()
        out, err = worker.communicate(timeout=5)
        self.assertEqual(err, "")
        return worker.returncode, out.strip()

    def seed(self):
        for category, identity, raw in (("checkpoint", "checkpoint", CHECKPOINT),
                                        ("prerequisite", "policy", POLICY),
                                        ("prerequisite", "approval", APPROVAL),
                                        ("prerequisite", "clock-a", TIME_A),
                                        ("prerequisite", "clock-b", TIME_B)):
            self.ledger.append(category, identity, self.prepared.binding.session, raw)
        return storage.OfflineEvidenceStore(self.ledger, self.prepared)

    def gate(self, evidence=None, consumption=None):
        monitor = FakeMonitor()
        return OfflineAuthorizationGate(
            approvals=FakeApprovalVerifier(self.prepared.binding),
            time_verifier=TwoSourceTimeVerifier(FakeTimeEvidenceVerifier(monitor.current.epoch),
                                               TimeLimits(200, 20, 1000000)),
            monitor=monitor, consumption=consumption or self.ledger,
            evidence=evidence or self.seed(), operation_budget_ns=30, margin_ns=2)

    def run_gate(self, gate):
        return gate.run(self.prepared, APPROVAL, (TIME_A, TIME_B))

    def change_policy(self, **changes):
        # A new empty fixture only; never rewrite an existing store's policy.
        child = tempfile.TemporaryDirectory(prefix="c2b-r12-", dir=self.parent)
        root = Path(child.name)
        policy = replace(self.policy, **changes)
        other = storage.OfflineLedger.initialize(root, policy, namespace_token=self.token)
        def cleanup():
            self.assertEqual(root.parent, self.parent)
            storage._namespace(root)
            self.assertEqual(storage.decode((root / "FORMAT.json").read_bytes())["namespace_token"], self.token)
            child.cleanup()
        self.addCleanup(cleanup)
        return other

    def test_exact_consumption_ack_and_new_object_readback(self):
        ack = self.ledger.consume(self.approval, "attempt-one")
        self.assertEqual(ack, Consumption(self.approval.key, self.prepared.binding.digest, "attempt-one"))
        self.assertEqual(self.reopen().snapshot()[0]["category"], "consumption")
        with self.assertRaises(Denied):
            self.reopen().consume(self.approval, "attempt-two")

    def test_actual_new_process_restart_refuses_spent(self):
        first = self.worker("consume")
        self.ready(first)
        self.assertEqual(self.finish(first), (0, "OK"))
        second = self.worker("consume")
        self.ready(second)
        self.assertEqual(self.finish(second), (0, "DENIED"))
        self.assertNotEqual(first.pid, second.pid)
        self.assertEqual(len(self.ledger.snapshot()), 1)

    def test_two_independent_ready_processes_exactly_one_winner(self):
        workers = [self.worker("consume"), self.worker("consume")]
        for worker in workers:
            self.ready(worker)
        for worker in workers:
            worker.stdin.write("GO\n")
            worker.stdin.flush()
        outputs = [worker.communicate(timeout=5) for worker in workers]
        self.assertEqual(sorted(out.strip() for out, _ in outputs), ["DENIED", "OK"])
        self.assertTrue(all(not err for _, err in outputs))
        self.assertTrue(all(w.returncode == 0 for w in workers))
        self.assertEqual(len(self.ledger.snapshot()), 1)

    def test_reuse_across_action_and_session_new_processes(self):
        self.ledger.consume(self.approval, "original")
        for operation in ("changed_action", "changed_session", "changed_target"):
            worker = self.worker(operation)
            self.ready(worker)
            self.assertEqual(self.finish(worker), (0, "DENIED"))

    def test_actual_process_crash_after_spend_before_ack_no_outcome(self):
        worker = self.worker("before_consumption_ack")
        self.ready(worker)
        self.assertEqual(self.finish(worker), (73, ""))
        self.assertTrue((self.root / "WRITER").is_dir())
        recovery = self.reopen().inspect_recovery()
        self.assertEqual(recovery["verified_records"], 1)
        self.assertFalse(recovery["trusted_success"])
        self.assertFalse(recovery["reusable_authority"])
        restart = self.worker("consume")
        self.ready(restart)
        self.assertEqual(self.finish(restart), (0, "DENIED"))
        self.assertFalse(any(b"simulated_dispatch_only" in p.read_bytes() for p in self.root.glob("*.bin")))

    def test_actual_crash_after_reservation_preserves_unknown_accounting(self):
        worker = self.worker("after_reservation")
        self.ready(worker)
        self.assertEqual(self.finish(worker), (73, ""))
        self.assertEqual(len(list(self.root.glob("*.reserve"))), 1)
        self.assertEqual(len(list(self.root.glob("*.bin"))), 0)
        self.assertEqual(self.reopen().inspect_recovery()["accounting"], "unknown_preserve_all_files")
        with self.assertRaises(Denied):
            self.reopen().consume(self.approval, "new")

    def test_actual_crash_during_binary_write_preserves_partial(self):
        worker = self.worker("during_data")
        self.ready(worker)
        self.assertEqual(self.finish(worker), (74, ""))
        self.assertEqual((self.root / "00000000.bin").stat().st_size, 7)
        self.assertFalse((self.root / "00000000.seal").exists())
        self.assertTrue(self.reopen().inspect_recovery()["quarantined"])
        restart = self.worker("consume")
        self.ready(restart)
        self.assertEqual(self.finish(restart), (0, "DENIED"))

    def test_complete_inert_r11_flow_with_durable_records(self):
        gate = self.gate()
        result = self.run_gate(gate)
        self.assertTrue(result.completed, result)
        rows = self.reopen().snapshot()
        self.assertEqual([r["category"] for r in rows][-5:],
                         ["original", "intent", "consumption", "candidate", "outcome"])
        self.assertEqual(next(r["raw"] for r in rows if r["category"] == "original"), self.prepared.raw)
        self.assertEqual(result.decision_digest, rows[-1]["digest"])
        self.assertEqual(gate.sink.bytes, self.prepared.raw)

    def test_candidate_is_distinct_and_never_recovery_success(self):
        evidence = self.seed()
        intent = evidence.prepare("a", self.prepared, (digest(APPROVAL), digest(TIME_A), digest(TIME_B)))
        self.ledger.consume(self.approval, "a")
        evidence.record("a", dict(attempt="a", binding=self.prepared.binding.digest, intent=intent,
                                   decision="spent_candidate_not_dispatch_permission", fake_only=True,
                                   production_authorization=False, utc_authenticated=False))
        rows = self.reopen().snapshot()
        self.assertEqual(rows[-1]["category"], "candidate")
        self.assertNotIn("outcome", [r["category"] for r in rows])
        self.assertFalse(self.reopen().inspect_recovery()["trusted_success"])

    def test_missing_checkpoint_and_prerequisite_originals_refuse(self):
        evidence = storage.OfflineEvidenceStore(self.ledger, self.prepared)
        with self.assertRaises(Denied):
            evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        self.assertEqual(self.ledger.snapshot(), [])

    def test_prepare_verify_and_duplicate_attempt(self):
        evidence = self.seed()
        ack = evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        evidence.verify("a", self.prepared, ack)
        with self.assertRaises(Denied):
            evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        with self.assertRaises(Denied):
            evidence.verify("a", self.prepared, "0" * 64)

    def test_checkpoint_tamper_blocks_verification(self):
        evidence = self.seed()
        ack = evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        path = self.root / "00000000.bin"
        path.write_bytes(b"altered-checkpoint")
        with self.assertRaises(Denied):
            evidence.verify("a", self.prepared, ack)

    def test_identical_byte_replacement_detected_by_file_identity(self):
        self.ledger.append("checkpoint", "id", "s", b"exact\r\n original")
        path = self.root / "00000000.bin"
        new = self.root / "replacement"
        new.write_bytes(path.read_bytes())
        os.replace(new, path)
        with self.assertRaises(Denied):
            self.reopen().snapshot()

    def test_truncated_corrupted_missing_and_unknown_records(self):
        # Separate fixtures avoid resetting a quarantined store between faults.
        for fault in ("truncate", "corrupt", "missing", "unknown", "seal"):
            with self.subTest(fault=fault):
                other = self.change_policy()
                other.append("checkpoint", "id", "s", b"abcdef")
                path = other.root / "00000000.bin"
                if fault == "truncate":
                    path.write_bytes(b"abc")
                elif fault == "corrupt":
                    path.write_bytes(b"ABCDEF")
                elif fault == "missing":
                    path.unlink()
                elif fault == "seal":
                    (other.root / "00000000.seal").write_bytes(b"{")
                else:
                    (other.root / "unledgered.partial").write_bytes(b"x")
                with self.assertRaises((Denied, OSError)):
                    other.snapshot()
                self.assertFalse(other.inspect_recovery()["trusted_success"])

    def test_duplicate_json_keys_and_malformed_descriptor(self):
        self.ledger.append("checkpoint", "id", "s", b"abc")
        (self.root / "00000000.reserve").write_bytes(b'{"category":"checkpoint","category":"outcome"}')
        with self.assertRaises(Denied):
            self.reopen().snapshot()

    def test_missing_consumption_ack_burns_actual_spent_state(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = self.ledger.consume
        def consume(approval, attempt):
            original(approval, attempt)
            return None
        with patch.object(self.ledger, "consume", side_effect=consume):
            result = self.run_gate(gate)
        self.assertFalse(result.completed)
        self.assertEqual(result.simulated_bytes, 0)
        self.assertEqual(result.reason, "uncertain_consumption_acknowledgment")
        with self.assertRaises(Denied):
            self.reopen().consume(self.approval, "replay")

    def test_wrong_consumption_ack_after_real_spend_zero_bytes(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = self.ledger.consume
        def consume(approval, attempt):
            return replace(original(approval, attempt), attempt="wrong-attempt")
        with patch.object(self.ledger, "consume", side_effect=consume):
            result = self.run_gate(gate)
        self.assertEqual(result.reason, "uncertain_consumption_acknowledgment")
        self.assertEqual(result.simulated_bytes, 0)
        self.assertEqual(sum(r["category"] == "consumption" for r in self.ledger.snapshot()), 1)

    def test_invalid_prepare_ack_zero_bytes(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = evidence.prepare
        with patch.object(evidence, "prepare", side_effect=lambda *a: (original(*a), None)[1]):
            result = self.run_gate(gate)
        self.assertFalse(result.completed)
        self.assertEqual(result.simulated_bytes, 0)
        self.assertNotIn("consumption", [r["category"] for r in self.ledger.snapshot()])

    def test_storage_failure_before_candidate_zero_bytes_spent(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = evidence.record
        def fail(attempt, decision):
            if decision["decision"] == "spent_candidate_not_dispatch_permission":
                raise OSError(errno.ENOSPC, "simulated disk full before candidate")
            return original(attempt, decision)
        with patch.object(evidence, "record", side_effect=fail):
            result = self.run_gate(gate)
        self.assertEqual(result.simulated_bytes, 0)
        self.assertFalse(result.completed)
        self.assertIn("consumption", [r["category"] for r in self.ledger.snapshot()])
        with self.assertRaises(Denied):
            self.reopen().consume(self.approval, "retry")

    def test_storage_failure_after_candidate_persistence_no_bytes(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = evidence.record
        def fail(attempt, decision):
            ack = original(attempt, decision)
            if decision["decision"] == "spent_candidate_not_dispatch_permission":
                raise OSError("simulated lost candidate acknowledgment")
            return ack
        with patch.object(evidence, "record", side_effect=fail):
            result = self.run_gate(gate)
        self.assertEqual(result.simulated_bytes, 0)
        self.assertFalse(result.completed)
        self.assertIn("candidate", [r["category"] for r in self.ledger.snapshot()])

    def test_outcome_ack_failure_keeps_factual_bytes_no_success(self):
        evidence = self.seed()
        gate = self.gate(evidence=evidence)
        original = evidence.record
        def fail(attempt, decision):
            ack = original(attempt, decision)
            return None if decision["decision"] == "simulated_dispatch_only" else ack
        with patch.object(evidence, "record", side_effect=fail):
            result = self.run_gate(gate)
        self.assertFalse(result.completed)
        self.assertEqual(result.simulated_bytes, len(self.prepared.raw))
        self.assertFalse(self.ledger.inspect_recovery()["trusted_success"])

    def test_per_record_exact_boundary_and_plus_one(self):
        other = self.change_policy(record_bytes=8)
        other.append("partial", "one", "s", b"12345678")
        with self.assertRaises(Denied):
            other.append("partial", "two", "s", b"123456789")
        self.assertEqual(len(other.snapshot()), 1)

    def test_duplicate_copies_charged_and_new_only_id_refusal(self):
        self.ledger.append("checkpoint", "one", "s", b"same")
        self.ledger.append("checkpoint", "two", "s", b"same")
        rows = self.ledger.snapshot()
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["digest"], rows[1]["digest"])
        self.assertGreater(sum(r["charge"] for r in rows), 2 * len(b"same"))
        with self.assertRaises(Denied):
            self.ledger.append("checkpoint", "one", "other", b"same")

    def test_category_quota_and_session_finalization_headroom(self):
        caps = tuple((c, 2000 if c == "checkpoint" else 300000) for c in storage.CATEGORIES)
        category = self.change_policy(category_bytes=caps)
        category.append("checkpoint", "one", "s", b"x")
        with self.assertRaises(Denied):
            category.append("checkpoint", "two", "s", b"x")
        session = self.change_policy(session_bytes=4000, finalization_bytes=2000)
        session.append("checkpoint", "one", "s", b"x")
        with self.assertRaises(Denied):
            session.append("checkpoint", "two", "s", b"x")
        with session._guard() as rows:
            session._append(rows, "denial", "final", "s", b"refused")
        self.assertEqual(len(session.snapshot()), 2)

    def test_campaign_aggregate_and_session_count_boundaries(self):
        campaign = self.change_policy(campaign_bytes=16000)
        campaign.append("checkpoint", "one", "s", b"x")
        with self.assertRaises(Denied):
            campaign.append("checkpoint", "two", "s2", b"x")
        count = self.change_policy(max_sessions=1)
        count.append("checkpoint", "one", "s", b"x")
        with self.assertRaises(Denied):
            count.append("checkpoint", "two", "s2", b"x")

    def test_finalization_cannot_steal_other_session_reserve(self):
        other = self.change_policy(campaign_bytes=29000)
        other.append("checkpoint", "one", "s1", b"x")
        other.append("checkpoint", "two", "s2", b"x")
        with self.assertRaises(Denied):
            with other._guard() as rows:
                other._append(rows, "denial", "huge-final", "s1", b"x" * 14000)
        with other._guard() as rows:
            other._append(rows, "denial", "small-final", "s2", b"refused")

    def test_partial_write_disk_full_retained_and_entire_store_quarantined(self):
        original = self.ledger._write
        def failure(name, raw):
            if name.endswith(".bin"):
                (self.root / name).write_bytes(raw[:2])
                raise OSError(errno.ENOSPC, "SIMULATED disk full")
            return original(name, raw)
        with patch.object(self.ledger, "_write", side_effect=failure):
            with self.assertRaises(OSError):
                self.ledger.append("partial", "id", "s", b"abcdef")
        self.assertEqual((self.root / "00000000.bin").read_bytes(), b"ab")
        self.assertEqual(len(list(self.root.glob("*.reserve"))), 1)
        with self.assertRaises(Denied):
            self.reopen().append("denial", "final", "s", b"cannot manufacture receipt")

    def test_fsync_and_readback_failures_are_uncertain(self):
        with patch.object(storage.os, "fsync", side_effect=OSError("SIMULATED flush failure")):
            with self.assertRaises(OSError):
                self.ledger.consume(self.approval, "a")
        self.assertTrue(self.ledger.inspect_recovery()["quarantined"])
        other = self.change_policy()
        original = other._read
        def mismatch(name, limit):
            raw = original(name, limit)
            return b"wrong" if name.endswith(".bin") else raw
        with patch.object(other, "_read", side_effect=mismatch):
            with self.assertRaises(Denied):
                other.append("checkpoint", "id", "s", b"abc")
        self.assertTrue(other.inspect_recovery()["quarantined"])

    def test_concurrent_independent_evidence_writer_reader(self):
        writer, reader = self.worker("evidence"), self.worker("read")
        for worker in (writer, reader):
            self.ready(worker)
        for worker in (writer, reader):
            worker.stdin.write("GO\n")
            worker.stdin.flush()
        outputs = [w.communicate(timeout=5) for w in (writer, reader)]
        self.assertTrue(all(w.returncode == 0 for w in (writer, reader)))
        self.assertTrue(all(out.strip() in ("OK", "DENIED") and not err for out, err in outputs))
        self.assertIn("OK", [out.strip() for out, _ in outputs])
        # Deterministic post-contention new process validates complete snapshot.
        fresh = self.worker("read")
        self.ready(fresh)
        self.assertEqual(self.finish(fresh), (0, "OK"))

    def test_held_writer_deterministically_excludes_reader_and_second_writer(self):
        held = self.worker("hold_evidence")
        self.ready(held)
        held.stdin.write("GO\n")
        held.stdin.flush()
        self.line(held, "HELD\n")
        for operation in ("read", "evidence"):
            contender = self.worker(operation)
            self.ready(contender)
            self.assertEqual(self.finish(contender), (0, "DENIED"))
        held.stdin.write("CONTINUE\n")
        held.stdin.flush()
        out, err = held.communicate(timeout=5)
        self.assertEqual((held.returncode, out.strip(), err), (0, "OK", ""))
        self.assertEqual(len(self.reopen().snapshot()), 1)

    def test_prepare_partial_original_survives_intent_quota_refusal(self):
        evidence = self.seed()
        # Enforce a fixture category quota at the admission seam without changing
        # the persisted policy: simulated quota service refusal on intent admission.
        original = self.ledger._capacity
        def quota(rows):
            original(rows)
            if rows and rows[-1]["category"] == "intent":
                raise OSError(errno.EDQUOT, "SIMULATED intent quota")
        with patch.object(self.ledger, "_capacity", side_effect=quota):
            with self.assertRaises(OSError):
                evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        recovery = self.reopen().inspect_recovery()
        self.assertTrue(recovery["quarantined"])
        self.assertEqual(recovery["verified_records"], 6)
        self.assertEqual((self.root / "00000005.bin").read_bytes(), self.prepared.raw)
        with self.assertRaises(Denied):
            self.reopen().consume(self.approval, "retry")

    def test_checked_short_writes_and_zero_write(self):
        original_open = Path.open
        mode = ["short"]
        class Writer:
            def __init__(self, stream):
                self.stream = stream
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def write(self, raw):
                return 0 if mode[0] == "zero" else self.stream.write(raw[:3])
            def flush(self):
                return self.stream.flush()
            def fileno(self):
                return self.stream.fileno()
        def opened(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            return Writer(stream) if args and args[0] == "xb" and path.suffix == ".bin" else stream
        with patch.object(Path, "open", opened):
            self.ledger.append("checkpoint", "short", "s", b"exact original\r\n  bytes")
            mode[0] = "zero"
            with self.assertRaises(OSError):
                self.ledger.append("partial", "zero", "s", b"not written")
        self.assertEqual((self.root / "00000000.bin").read_bytes(), b"exact original\r\n  bytes")
        self.assertEqual((self.root / "00000001.bin").stat().st_size, 0)
        self.assertTrue(self.ledger.inspect_recovery()["quarantined"])

    def test_public_append_cannot_mislabel_success_or_consumption(self):
        for category in ("consumption", "candidate", "outcome", "intent", "denial", "original"):
            with self.assertRaises(Denied):
                self.ledger.append(category, "forged", "s", b"success")
        self.assertEqual(self.ledger.snapshot(), [])

    def test_issuer_is_part_of_key_and_partial_has_no_success_semantics(self):
        self.ledger.consume(self.approval, "one")
        ack = self.ledger.consume(replace(self.approval, issuer="different-fixture-issuer"), "two")
        self.assertEqual(ack.approval_key, ("different-fixture-issuer", self.approval.approval_id))
        self.ledger.append("partial", "bounded-incomplete-prefix", "fixture-session", b"prefix only")
        rows = self.ledger.snapshot()
        self.assertEqual(rows[-1]["category"], "partial")
        self.assertFalse(self.ledger.inspect_recovery()["trusted_success"])

    def test_record_count_and_exact_category_budget_boundary(self):
        count = self.change_policy(max_records=1)
        count.append("checkpoint", "id", "s", b"x")
        charge = count.snapshot()[0]["charge"]
        with self.assertRaises(Denied):
            count.append("checkpoint", "two", "s", b"x")
        caps = tuple((c, charge if c == "checkpoint" else 300000) for c in storage.CATEGORIES)
        exact = self.change_policy(category_bytes=caps)
        exact.append("checkpoint", "id", "s", b"x")
        self.assertEqual(exact.snapshot()[0]["charge"], charge)
        with self.assertRaises(Denied):
            exact.append("checkpoint", "two", "s", b"")

    def test_denial_is_terminal_for_candidate_and_outcome(self):
        evidence = self.seed()
        intent = evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        self.ledger.consume(self.approval, "a")
        decision = dict(attempt="a", binding=self.prepared.binding.digest, intent=intent,
                        fake_only=True, production_authorization=False, utc_authenticated=False)
        evidence.record("a", decision | {"decision": "denied_or_uncertain"})
        for kind in ("spent_candidate_not_dispatch_permission", "simulated_dispatch_only"):
            with self.assertRaises(Denied):
                evidence.record("a", decision | {"decision": kind})
        self.assertEqual(self.ledger.snapshot()[-1]["category"], "denial")

    def test_missing_intent_after_prepare_and_changed_action_refuse(self):
        evidence = self.seed()
        intent = evidence.prepare("a", self.prepared, (digest(APPROVAL),))
        changed = action(target={"id": "changed"})
        with self.assertRaises(Denied):
            evidence.verify("a", changed, intent)
        (self.root / "00000006.bin").unlink()
        with self.assertRaises((Denied, OSError)):
            evidence.verify("a", self.prepared, intent)

    def test_no_production_or_physical_reservation_mode(self):
        with self.assertRaises(TypeError):
            storage.OfflineLedger(self.root, self.policy, namespace_token=self.token, production=True)
        self.assertFalse(hasattr(self.ledger, "reserve_physical_bytes"))
        with self.assertRaises(ValueError):
            replace(self.policy, finalization_bytes=0)

    def test_namespace_unsupported_inputs_and_policy_identity(self):
        for root in (Path("relative"), Path(r"\\server\share\c2b-r12-test"),
                     self.parent, self.root / "bad:stream"):
            with self.subTest(root=str(root)), self.assertRaises((Denied, OSError)):
                storage.OfflineLedger(root, self.policy, namespace_token=self.token)
        with self.assertRaises(Denied):
            storage.OfflineLedger(self.root, self.policy, namespace_token="wrong")
        with self.assertRaises(Denied):
            storage.OfflineLedger(self.root, replace(self.policy, max_sessions=2), namespace_token=self.token)
        with self.assertRaises(Denied):
            storage.OfflineLedger.initialize(self.root, self.policy, namespace_token=self.token)

    def test_simulated_reparse_and_non_ntfs_refusal(self):
        info = self.root.stat()
        class Reparse:
            st_mode = info.st_mode
            st_file_attributes = 0x400
        with patch.object(Path, "lstat", return_value=Reparse()):
            with self.assertRaises(Denied):
                storage._namespace(self.root)
        with patch.object(storage.ctypes, "WinDLL") as dll:
            dll.return_value.GetVolumeInformationW.return_value = 0
            with self.assertRaises(Denied):
                storage._namespace(self.root)

    def test_hardlink_leaf_is_rejected_actual_ntfs(self):
        self.ledger.append("checkpoint", "id", "s", b"abc")
        os.link(self.root / "00000000.bin", self.root / "duplicate-link")
        with self.assertRaises(Denied):
            self.ledger.snapshot()

    def test_retention_30_days_and_review_hold_boundaries(self):
        day = 86400000000000
        predicate = storage.retention_eligible
        self.assertFalse(predicate(created_ns=1, now_ns=30*day, review_complete=True, minimum_days=30))
        self.assertTrue(predicate(created_ns=1, now_ns=30*day+1, review_complete=True, minimum_days=30))
        self.assertFalse(predicate(created_ns=1, now_ns=90*day, review_complete=False, minimum_days=30))
        with self.assertRaises(Denied):
            predicate(created_ns=1, now_ns=90*day, review_complete=True, minimum_days=29)
        self.assertFalse(hasattr(self.ledger, "delete"))


if __name__ == "__main__":
    unittest.main()
