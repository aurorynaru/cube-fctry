from dataclasses import FrozenInstanceError, replace
import json
import threading
import unittest
from unittest.mock import patch

from tool import c2b_authorization_gate as gate
from tests.fixtures.c2b_r11_fakes import (
    APPROVAL, TIME_A, TIME_B, FakeApprovalVerifier, FakeConsumptionStore,
    FakeEvidenceStore, FakeMonitor, FakeTimeEvidenceVerifier, SimulatedCrash,
)


class AuthorizationGateTests(unittest.TestCase):
    def setUp(self):
        self.target = {"id": "synthetic-target-only", "name": "Fixture", "mode": "ReadOnly"}
        self.details = {"query": "synthetic-summary"}
        self.action = self.prepare()
        self.approvals = FakeApprovalVerifier(self.action.binding)
        self.monitor = FakeMonitor()
        self.sources = FakeTimeEvidenceVerifier(self.monitor.current.epoch)
        self.time = gate.TwoSourceTimeVerifier(self.sources, gate.TimeLimits(200, 20, 1_000_000))
        self.spent = FakeConsumptionStore()
        self.evidence = FakeEvidenceStore(self.action)
        self.g = self.new_gate()

    def prepare(self, **changes):
        fields = dict(observation="fixture-observation", session="fixture-session",
                      target=self.target, details=self.details,
                      checkpoint_digest=gate.digest(b"fixture-discovery-checkpoint"),
                      policy_digest=gate.digest(b"fixture-policy-deployment-lifecycle-budgets"),
                      destination="fixture-private-store-reference")
        return gate.prepare_action(**(fields | changes))

    def new_gate(self):
        return gate.OfflineAuthorizationGate(approvals=self.approvals, time_verifier=self.time,
                                            monitor=self.monitor, consumption=self.spent,
                                            evidence=self.evidence, operation_budget_ns=30,
                                            margin_ns=2)

    def run_gate(self, g=None, action=None, approval=APPROVAL, times=(TIME_A, TIME_B)):
        return (g or self.g).run(action or self.action, approval, times)

    def denied(self, reason=None, **kwargs):
        g = kwargs.get("g", self.g)
        result = self.run_gate(**kwargs)
        self.assertFalse(result.completed, result)
        self.assertFalse(result.dispatched, result)
        self.assertEqual(result.simulated_bytes, 0, result)
        self.assertEqual(g.sink.bytes, b"")
        self.assertTrue(result.fake_only)
        if reason:
            self.assertEqual(result.reason, reason)
        return result

    def test_authorized_synthetic_vertical_slice_records_exact_bytes_and_digests(self):
        result = self.run_gate()
        self.assertTrue(result.completed, result)
        self.assertTrue(result.dispatched, result)
        self.assertTrue(result.fake_only)
        self.assertEqual(self.g.sink.bytes, self.action.raw)
        self.assertEqual(self.approvals.validations, 2)
        self.assertEqual(len(self.spent.spent), 1)
        intent = json.loads(next(iter(self.evidence.intents.values())))
        self.assertEqual(intent["evidence"], [gate.digest(x) for x in (APPROVAL, TIME_A, TIME_B)])
        self.assertEqual(intent["action"].encode("ascii"), self.action.raw)
        record = self.evidence.records[-1][1]
        self.assertEqual(result.decision_digest, gate.digest(record))
        decision = json.loads(record)
        self.assertEqual(decision["binding"], self.action.binding.digest)
        self.assertEqual(decision["final_interval"], [100, 106])
        self.assertFalse(decision["production_authorization"])
        self.assertFalse(decision["utc_authenticated"])

    def test_action_snapshots_mutable_inputs_and_is_frozen(self):
        original = self.action.raw
        self.target["id"] = "changed"
        self.details["query"] = "changed"
        self.assertEqual(self.action.raw, original)
        with self.assertRaises(FrozenInstanceError):
            self.action.raw = b"changed"
        self.assertTrue(self.run_gate().dispatched)

    def test_missing_approval(self):
        self.denied("independent_approval_required", approval=None)

    def test_agent_strings_booleans_and_r9_continuations_are_not_authority(self):
        for raw in ("approved", True, b"approved", {"test_only": True},
                    b'{"test_only":true,"action":"continue_synthetic_state"}'):
            with self.subTest(raw=raw):
                self.denied(g=self.new_gate(), approval=raw)
        self.assertEqual(self.spent.spent, {})

    def test_invalid_scope_binding_in_each_dimension(self):
        for field, value in (("observation", "other"), ("session", "other"),
                             ("target_digest", "0" * 64), ("action_digest", "0" * 64),
                             ("checkpoint_digest", "0" * 64), ("policy_digest", "0" * 64),
                             ("destination", "other")):
            with self.subTest(field=field):
                self.approvals.claim = replace(self.approvals.claim,
                                               binding=replace(self.action.binding, **{field: value}))
                self.denied("fake_scope_mismatch", g=self.new_gate())

    def test_invalid_actor_channel_evidence_or_time_claims(self):
        original = self.approvals.claim
        for changes in ({"actor": ""}, {"channel": ""}, {"issuer": ""}, {"approval_id": ""},
                        {"evidence_digest": "0" * 64}, {"approved_ns": True},
                        {"not_before_ns": 1001}, {"expires_ns": 10}):
            with self.subTest(changes=changes):
                self.approvals.claim = replace(original, **changes)
                self.denied("invalid_approval_binding", g=self.new_gate())

    def test_expired_and_exact_expiry_budget_margin_equality(self):
        self.approvals.claim = replace(self.approvals.claim, expires_ns=138)
        self.denied("expiry_or_insufficient_budget")  # 106 + 30 + 2 == 138

    def test_expired_approval(self):
        self.approvals.claim = replace(self.approvals.claim, expires_ns=100)
        self.denied("expiry_or_insufficient_budget")

    def test_whole_interval_must_be_after_not_before(self):
        self.approvals.claim = replace(self.approvals.claim, not_before_ns=101)
        self.denied("approval_not_yet_valid")  # lower bound 100, even though upper is 106

    def test_missing_duplicate_and_unauthenticated_time_evidence(self):
        for inputs in ((), (TIME_A,), (TIME_A, TIME_B, TIME_A), (TIME_A, TIME_A),
                       (TIME_A, b"agent-asserted-time"), (TIME_A, None), [TIME_A, TIME_B]):
            with self.subTest(inputs=inputs):
                self.denied(g=self.new_gate(), times=inputs)

    def test_time_source_disagreement(self):
        self.sources.change(lower_ns=105, upper_ns=107)
        self.denied("time_source_disagreement")

    def test_shared_independence_domain_is_refused(self):
        self.sources.change(independence_domain="fixture-domain-A")
        self.denied("time_sources_not_independent")

    def test_same_source_with_different_claimed_domain_is_refused(self):
        self.sources.change(source="fixture-A")
        self.denied("time_sources_not_independent")

    def test_bad_time_binding_bounds_anchor_epoch_and_width(self):
        original = self.sources.claims[TIME_B]
        for changes in ({"evidence_digest": "0" * 64}, {"source": ""},
                        {"independence_domain": ""}, {"epoch": "different-boot"},
                        {"anchor_ns": 101}, {"lower_ns": 107}, {"lower_ns": True},
                        {"upper_ns": 150}):
            with self.subTest(changes=changes):
                self.sources.claims[TIME_B] = replace(original, **changes)
                self.denied(g=self.new_gate())

    def test_stale_unhealthy_or_backward_monotonic_input(self):
        original = self.monitor.current
        for changes in ({"monotonic_ns": 301}, {"monotonic_ns": 99},
                        {"monotonic_ns": True}, {"healthy": False}, {"epoch": "reboot"}):
            with self.subTest(changes=changes):
                self.monitor.current = replace(original, **changes)
                self.denied(g=self.new_gate())

    def test_covering_interval_not_intersection_and_outward_drift_rounding(self):
        self.monitor.current = replace(self.monitor.current, monotonic_ns=101)
        window = self.time.verify((TIME_A, TIME_B), self.monitor.sample())
        self.assertEqual((window.lower_ns, window.upper_ns), (100, 108))
        # Cover [100,106] + elapsed 1 +/- ceil(.001) = [100,108], not [102,104].

    def test_withdrawn_approval(self):
        self.approvals.withdraw()
        self.denied("withdrawn")

    def test_withdrawal_channel_unknown(self):
        self.approvals.channel_healthy = False
        self.denied("withdrawal_status_unknown")

    def test_withdrawal_acknowledged_during_slow_intent_storage_prevents_first_byte(self):
        self.evidence.after_prepare = self.approvals.withdraw
        self.denied("withdrawn_or_channel_lost")
        self.assertEqual(len(self.spent.spent), 1)  # deliberately sacrifice availability

    def test_channel_loss_between_validation_and_dispatch(self):
        self.evidence.after_prepare = lambda: setattr(self.approvals, "channel_healthy", False)
        self.denied("withdrawn_or_channel_lost")

    def test_revalidation_detects_changed_approval(self):
        def change():
            self.approvals.claim = replace(self.approvals.claim, actor="different-fixture-actor")
        self.evidence.after_prepare = change
        self.denied("approval_changed")
        self.assertEqual(self.approvals.validations, 2)

    def test_slow_storage_cannot_reset_absolute_deadline_or_monitor_continuity(self):
        original = self.monitor.current
        for changes in ({"monotonic_ns": 130}, {"monotonic_ns": 99},
                        {"epoch": "resume-new-generation"}, {"healthy": False}):
            with self.subTest(changes=changes):
                self.spent = FakeConsumptionStore()
                self.monitor.current = original
                self.evidence.after_prepare = lambda: setattr(self.monitor, "current", replace(original, **changes))
                self.denied(g=self.new_gate())

    def test_expiry_rechecked_after_slow_storage(self):
        self.approvals.claim = replace(self.approvals.claim, expires_ns=140)
        self.evidence.after_prepare = lambda: setattr(self.monitor, "current", replace(self.monitor.current, monotonic_ns=102))
        self.denied("expiry_or_insufficient_budget")

    def test_time_freshness_rechecked_after_slow_storage(self):
        self.g.time_verifier = gate.TwoSourceTimeVerifier(self.sources, gate.TimeLimits(1, 20, 0))
        self.evidence.after_prepare = lambda: setattr(self.monitor, "current", replace(self.monitor.current, monotonic_ns=102))
        self.denied("time_stale_or_monotonic_step")

    def test_time_authentication_is_rechecked_at_dispatch(self):
        self.evidence.after_prepare = lambda: self.sources.claims.pop(TIME_B)
        self.denied("fake_time_not_authenticated")

    def test_changed_action_before_validation(self):
        action = replace(self.action, raw=self.action.raw + b" ")
        self.denied("changed_action", action=action)

    def test_changed_action_after_intent_persistence(self):
        self.evidence.after_prepare = lambda: object.__setattr__(self.action, "raw", b"changed")
        self.denied("changed_action")

    def test_reconstructed_changed_target_or_details_cannot_reuse_approval(self):
        for change in ({"target": self.target | {"id": "other"}},
                       {"details": {"query": "other"}}):
            with self.subTest(change=change):
                self.denied("fake_scope_mismatch", g=self.new_gate(), action=self.prepare(**change))

    def test_checkpoint_or_intent_tamper_during_storage(self):
        for what in ("checkpoint", "intent"):
            with self.subTest(what=what):
                self.spent = FakeConsumptionStore()
                self.evidence = FakeEvidenceStore(self.action)
                def change():
                    if what == "checkpoint":
                        self.evidence.checkpoint = "0" * 64
                    else:
                        key = next(iter(self.evidence.intents))
                        self.evidence.intents[key] += b"changed"
                self.evidence.after_prepare = change
                self.denied(g=self.new_gate())

    def test_missing_checkpoint_and_unhealthy_storage(self):
        self.evidence.checkpoint = None
        self.denied("checkpoint_or_storage_binding_mismatch")
        self.evidence.checkpoint = self.action.binding.checkpoint_digest
        self.evidence.healthy = False
        self.denied("evidence_storage_uncertain", g=self.new_gate())

    def test_evidence_prepare_failure_blocks_consume_and_dispatch(self):
        self.evidence.fail_prepare = True
        self.denied("dependency_uncertainty")
        self.assertEqual(self.spent.spent, {})

    def test_candidate_decision_storage_failure_blocks_all_bytes_and_burns_attempt(self):
        self.evidence.fail_record = True
        result = self.denied("evidence_record_uncertainty")
        self.assertIsNone(result.decision_digest)
        self.assertEqual(len(self.spent.spent), 1)
        self.evidence.fail_record = False
        self.denied("already_consumed_or_uncertain", g=self.new_gate())

    def test_missing_storage_digest_acknowledgment_is_not_success(self):
        for method in ("prepare", "record"):
            with self.subTest(method=method):
                self.spent = FakeConsumptionStore()
                with patch.object(self.evidence, method, return_value=None):
                    result = self.denied(g=self.new_gate())
                self.assertFalse(result.completed)

    def test_outcome_storage_failure_never_claims_success_or_retracts_sent_bytes(self):
        original = self.evidence.record
        def record(attempt, decision):
            if decision["decision"] == "simulated_dispatch_only":
                self.evidence.fail_record = True
            return original(attempt, decision)
        with patch.object(self.evidence, "record", side_effect=record):
            result = self.run_gate()
        self.assertFalse(result.completed)
        self.assertTrue(result.dispatched)  # factual bytes; never a success receipt
        self.assertEqual(result.reason, "evidence_record_uncertainty")
        self.assertIsNone(result.decision_digest)
        self.assertEqual(self.g.sink.bytes, self.action.raw)
        self.assertEqual(result.simulated_bytes, len(self.action.raw))
        self.evidence.fail_record = False
        self.denied("already_consumed_or_uncertain", g=self.new_gate())

    def test_health_loss_after_persistence_is_rechecked(self):
        self.evidence.after_prepare = lambda: setattr(self.evidence, "healthy", False)
        self.denied("evidence_storage_uncertain")

    def test_same_gate_replay_is_terminal_and_new_gate_replay_is_spent(self):
        self.assertTrue(self.run_gate().dispatched)
        original = self.g.sink.bytes
        replay = self.run_gate()
        self.assertFalse(replay.dispatched)
        self.assertEqual(replay.reason, "terminal_gate")
        self.assertEqual(replay.simulated_bytes, 0)
        self.assertEqual(self.g.sink.bytes, original)
        self.denied("already_consumed_or_uncertain", g=self.new_gate())

    def test_spent_key_cannot_be_reused_for_a_different_binding(self):
        self.assertTrue(self.run_gate().dispatched)
        changed = self.prepare(session="fixture-reconnect")
        self.approvals.claim = replace(self.approvals.claim, binding=changed.binding)
        self.evidence = FakeEvidenceStore(changed)
        self.denied("already_consumed_or_uncertain", g=self.new_gate(), action=changed)

    def test_ambiguous_consumption_is_spent_and_cannot_retry(self):
        self.spent.uncertain_after_commit = True
        self.denied("dependency_uncertainty")
        self.spent.uncertain_after_commit = False
        self.denied("already_consumed_or_uncertain", g=self.new_gate())

    def test_wrong_consumption_acknowledgment_is_refused(self):
        original = self.spent.consume
        with patch.object(self.spent, "consume", side_effect=lambda a, t: replace(original(a, t), attempt="wrong")):
            self.denied("uncertain_consumption_acknowledgment")

    def test_simulated_crash_after_spend_blocks_recreated_gate_with_same_fake_store(self):
        self.spent.crash_after_commit = True
        with self.assertRaises(SimulatedCrash):
            self.run_gate()
        self.assertEqual(self.g.sink.bytes, b"")
        self.assertEqual(self.evidence.records, [])  # no fabricated final decision
        self.spent.crash_after_commit = False
        self.denied("already_consumed_or_uncertain", g=self.new_gate())

    def test_two_controllers_race_consumption_exactly_one_winner(self):
        barrier = threading.Barrier(2)
        original = self.spent.consume
        def racing(approval, attempt):
            barrier.wait(timeout=2)
            return original(approval, attempt)
        gates = [self.g, self.new_gate()]
        results = []
        with patch.object(self.spent, "consume", side_effect=racing):
            threads = [threading.Thread(target=lambda g=g: results.append(self.run_gate(g=g))) for g in gates]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=3)
                self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 2)
        self.assertEqual(sum(r.dispatched for r in results), 1)
        self.assertEqual(sorted(len(g.sink.bytes) for g in gates), [0, len(self.action.raw)])
        self.assertEqual(len(self.spent.spent), 1)

    def test_same_controller_concurrent_attempt_refuses_without_queue(self):
        ready, release = threading.Event(), threading.Event()
        def wait():
            ready.set()
            if not release.wait(2):
                raise RuntimeError("test release missing")
        self.evidence.after_prepare = wait
        results = []
        thread = threading.Thread(target=lambda: results.append(self.run_gate()))
        thread.start()
        try:
            self.assertTrue(ready.wait(2))
            result = self.run_gate()
            self.assertEqual(result.reason, "concurrent_attempt")
            self.assertEqual(result.simulated_bytes, 0)
            self.assertEqual(self.g.sink.bytes, b"")
        finally:
            release.set()
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0].dispatched)

    def test_withdrawal_acknowledgment_cannot_cross_guarded_first_byte(self):
        # A withdrawal requested while final revalidation owns the guard cannot
        # acknowledge until that transition completes. No claim of unsending.
        requested, acknowledged = threading.Event(), threading.Event()
        original = self.approvals.validate
        original_record = self.evidence.record
        threads = []
        def withdraw():
            requested.set()
            self.approvals.withdraw()
            acknowledged.set()
        def validate(raw, binding):
            claim = original(raw, binding)
            if self.approvals.validations == 2:
                thread = threading.Thread(target=withdraw)
                threads.append(thread)
                thread.start()
                self.assertTrue(requested.wait(2))
                self.assertFalse(acknowledged.is_set())
                self.assertEqual(self.g.sink.bytes, b"")
            return claim
        def record(attempt, decision):
            if decision["decision"] == "simulated_dispatch_only":
                self.assertTrue(acknowledged.wait(2))
                self.assertEqual(self.g.sink.bytes, self.action.raw)
            return original_record(attempt, decision)
        with patch.object(self.approvals, "validate", side_effect=validate), \
                patch.object(self.evidence, "record", side_effect=record):
            result = self.run_gate()
        for thread in threads:
            thread.join(timeout=3)
            self.assertFalse(thread.is_alive())
        self.assertTrue(result.dispatched, result)

    def test_withdrawal_from_another_thread_is_acknowledged_before_dispatch(self):
        ready, withdrawn = threading.Event(), threading.Event()
        def withdraw():
            if ready.wait(2):
                self.approvals.withdraw()
                withdrawn.set()
        thread = threading.Thread(target=withdraw)
        thread.start()
        def wait():
            ready.set()
            if not withdrawn.wait(2):
                raise RuntimeError("test withdrawal missing")
        self.evidence.after_prepare = wait
        try:
            self.denied("withdrawn_or_channel_lost")
        finally:
            thread.join(timeout=3)
        self.assertFalse(thread.is_alive())

    def test_no_injected_transport_or_production_mode(self):
        with self.assertRaises(TypeError):
            gate.OfflineAuthorizationGate(sink=lambda raw: None)
        with self.assertRaises(TypeError):
            gate.OfflineAuthorizationGate(production=True)

    def test_invalid_test_limits_and_action_inputs(self):
        for limits in (gate.TimeLimits(0, 20, 0), gate.TimeLimits(200, 0, 0),
                       gate.TimeLimits(200, 20, -1), gate.TimeLimits(True, 20, 0)):
            with self.assertRaises(ValueError):
                gate.TwoSourceTimeVerifier(self.sources, limits)
        for changes in ({"target": {}}, {"details": []}, {"session": ""},
                        {"checkpoint_digest": "not-a-digest"},
                        {"details": {"x": "x" * 5000}}):
            with self.assertRaises(gate.Denied):
                self.prepare(**changes)


if __name__ == "__main__":
    unittest.main()
