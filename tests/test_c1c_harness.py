"""C1C harness tests: mocked lifecycle, safety, recovery and evidence limits.

No test connects to Roblox Studio, uploads an asset, writes the production
registry or claims a production approval. Every lifecycle test uses the
in-memory adapter and a temporary project root.
"""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
from c1c_harness import (  # noqa: E402
    AssetManifest,
    CaptureResult,
    EvidenceStore,
    Harness,
    HarnessError,
    InMemoryStudioAdapter,
    ManifestError,
    ProvenanceError,
    RUN_ATTR,
    TAG,
    TESTONLY_ATTR,
    build_rig,
    build_rig_plan,
    capture_baseline,
    import_capture_file,
    load_spec,
    recover,
    verify_b2_evidence,
    verify_ownership,
)


def _png_bytes(color=(90, 110, 130)):
    import io

    image = Image.new("RGB", (64, 64), color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class HarnessFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for folder in ("art/imports", "registry/evidence", "outputs", "scratch"):
            (self.root / folder).mkdir(parents=True, exist_ok=True)
        self.source = self.root / "outputs/tile.png"
        self.source.write_bytes(_png_bytes())
        self.digest = hashlib.sha256(self.source.read_bytes()).hexdigest()
        self.manifest = {
            "schema_version": "1.0",
            "assets": [{
                "source_path": "outputs/tile.png",
                "sha256": self.digest,
                "roblox_asset_id": "112705883084796",
                "asset_type": "image",
                "uploaded_by": "tester",
                "uploaded_on": "2026-10-17",
                "experience": "local-unsaved",
                "status": "test_only_unapproved",
            }],
        }
        self.write_manifest()
        self.b2 = {
            "source_sha256": self.digest,
            "overall_result": "REVIEW_REQUIRED",
            "registry_gate_claims": {
                name: {"result": "pending", "evidence": []}
                for name in ("originality", "rights", "style", "technical",
                             "performance", "tiling", "in_engine")
            },
        }
        self.write_b2()

    def write_manifest(self, document=None):
        path = self.root / "art/imports/roblox-assets.json"
        path.write_text(json.dumps(document or self.manifest, indent=2), encoding="utf-8")

    def write_b2(self):
        (self.root / "registry/evidence/b2.json").write_text(
            json.dumps(self.b2, indent=2), encoding="utf-8")

    def spec_dict(self, run_id="c1c-test-001", **overrides):
        raw = json.loads((ROOT / "tool/c1c/example-spec.json").read_text(encoding="utf-8"))
        raw["run_id"] = run_id
        raw["asset"]["source_path"] = "outputs/tile.png"
        raw["asset"]["source_sha256"] = self.digest
        raw["asset"]["manifest_path"] = "art/imports/roblox-assets.json"
        raw["evidence"]["require_durable_files"] = False
        raw["b2"]["evidence_path"] = "registry/evidence/b2.json"
        raw.update(overrides)
        return raw

    def write_spec(self, raw=None, name="spec.json"):
        raw = raw or self.spec_dict()
        (self.root / name).write_text(json.dumps(raw, indent=2), encoding="utf-8")
        return load_spec(self.root, name)

    def adapter(self, **kwargs):
        kwargs.setdefault("scratch_dir", self.root / "scratch")
        return InMemoryStudioAdapter(**kwargs)


class SuccessfulLifecycleTests(HarnessFixture):
    def test_successful_lifecycle_persists_real_hashed_captures_and_cleans_up(self):
        raw = self.spec_dict()
        raw["evidence"]["require_durable_files"] = True
        spec = self.write_spec(raw, "durable-spec.json")
        adapter = self.adapter(screenshot_mode="saved_file")
        report = Harness(self.root, spec, adapter).run()

        self.assertEqual("PASS", report["result"], report["failures"])
        self.assertTrue(report["adapter"]["simulates_studio"])
        self.assertFalse(report["adapter"]["studio_touched"])
        self.assertEqual("simulated_test_only", report["evidence"]["evidence_kind"])
        self.assertEqual(8, len(report["captures"]))
        self.assertTrue(all(item["valid"] for item in report["captures"]))
        self.assertTrue(all(item["simulated"] for item in report["captures"]))
        self.assertTrue(report["workspace_verification"]["result"] == "PASS")
        self.assertEqual("PASS", report["cleanup"]["result"])
        self.assertTrue(report["restoration"]["complete"])
        self.assertTrue(report["camera"]["restored"])
        self.assertTrue(report["viewport"]["restored"])
        self.assertTrue(report["evidence"]["complete"])
        self.assertEqual(8, report["evidence"]["durable_captures"])
        self.assertEqual(0, report["evidence"]["inline_only_captures"])
        self.assertEqual(0, adapter.upload_calls)
        self.assertEqual(6, len(adapter.preload_calls[0]))  # 4 scales + 2 seam textures
        for capture in report["captures"]:
            path = self.root / capture["evidence"]["evidence_path"]
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             capture["evidence"]["sha256"])
            self.assertEqual(64, capture["evidence"]["width"])
        self.assertFalse((self.root / "registry/events.jsonl").exists())
        self.assertTrue(report["b1"]["unchanged"])
        self.assertIsNone(report["b1"]["before"]["sha256"])
        report_path = self.root / report["evidence"]["report_path"]
        self.assertTrue(report_path.is_file())
        self.assertFalse(any(
            path.startswith(spec.folder_path)
            for path in adapter.snapshot()["objects"]
        ))

    def test_successful_lifecycle_with_inline_only_evidence_is_honest(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        self.assertTrue(report["evidence"]["complete"])
        self.assertEqual(0, report["evidence"]["durable_captures"])
        self.assertEqual(8, report["evidence"]["inline_only_captures"])
        for capture in report["captures"]:
            self.assertEqual("inline_only", capture["evidence"]["storage"])
            self.assertIsNone(capture["evidence"]["evidence_path"])
            self.assertIsNone(capture["evidence"]["sha256"])
        self.assertTrue(any("inline-only" in item.lower()
                            for item in report["evidence"]["limitations"]))
        self.assertTrue(report["cleanup"]["destroyed"])
        self.assertTrue(report["restoration"]["complete"])

    def test_camera_drift_is_detected_and_restored(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline", capture_mutates_camera=True)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        self.assertGreaterEqual(len(report["camera"]["drift_events"]), 1)
        self.assertTrue(report["camera"]["restored"])
        self.assertTrue(all(event["before"] != event["after"]
                            for event in report["camera"]["drift_events"]))
        self.assertTrue(all(capture["camera_restored_to_baseline"]
                            for capture in report["captures"] if capture["valid"]))

    def test_viewport_side_effect_is_disclosed_and_never_claimed_restored(self):
        raw = self.spec_dict()
        raw["evidence"]["require_durable_files"] = True
        spec = self.write_spec(raw, "viewport-spec.json")
        adapter = self.adapter(screenshot_mode="saved_file",
                               capture_changes_viewport=True,
                               supports_viewport_restore=False)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        self.assertFalse(report["viewport"]["restored"])
        self.assertFalse(report["restoration"]["complete"])
        self.assertTrue(any("viewport size changed" in item
                            for item in report["restoration"]["residual_effects"]))
        self.assertTrue(report["cleanup"]["destroyed"])
        self.assertTrue(report["workspace_verification"]["result"] == "PASS")

    def test_supported_viewport_restore_is_verified(self):
        raw = self.spec_dict()
        raw["evidence"]["require_durable_files"] = True
        spec = self.write_spec(raw, "viewport-restore-spec.json")
        adapter = self.adapter(screenshot_mode="saved_file",
                               capture_changes_viewport=True,
                               supports_viewport_restore=True)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS", report["result"], report["failures"])
        self.assertTrue(report["viewport"]["restored"])
        self.assertTrue(report["restoration"]["complete"])


class EvidenceFailureTests(HarnessFixture):
    def test_missing_or_invalid_screenshots_are_not_evidence(self):
        for mode in ("invalid_empty", "invalid_black", "invalid_corrupt"):
            with self.subTest(mode=mode):
                run_id = f"c1c-invalid-{mode.replace('_', '-')}"
                spec = self.write_spec(self.spec_dict(run_id=run_id),
                                       f"spec-{mode}.json")
                adapter = self.adapter(screenshot_mode=mode)
                report = Harness(self.root, spec, adapter).run()
                self.assertEqual("FAIL", report["result"])
                self.assertEqual(8, report["evidence"]["invalid_captures"])
                self.assertTrue(any(item["code"] == "required_capture_invalid"
                                    for item in report["failures"]))
                for capture in report["captures"]:
                    self.assertFalse(capture["valid"])
                    self.assertEqual("missing", capture["evidence"]["storage"])
                    self.assertIsNone(capture["evidence"]["evidence_path"])
                    self.assertIsNone(capture["evidence"]["sha256"])
                # Safety still cleans up the owned rig after an evidence failure.
                self.assertEqual("PASS", report["cleanup"]["result"])
                self.assertTrue(report["cleanup"]["destroyed"])

    def test_manual_capture_import_hashes_a_real_file_without_fabrication(self):
        run_id = "c1c-manual-001"
        raw = self.spec_dict(run_id=run_id)
        spec = self.write_spec(raw, "manual-spec.json")
        report = Harness(self.root, spec, self.adapter(screenshot_mode="inline")).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        run_dir = self.root / "registry/evidence/c1c" / run_id
        source = self.root / "scratch/operator.png"
        source.write_bytes(_png_bytes((20, 80, 40)))
        record = import_capture_file(self.root, "manual-spec.json", run_id,
                                     "C1C_baseline_1", str(source))
        saved = self.root / record["evidence_path"]
        self.assertTrue(saved.is_file())
        self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), record["sha256"])
        self.assertEqual("manual_import", record["storage"])
        self.assertEqual("pre_rig", record["capture_phase"])
        self.assertTrue((run_dir / "manual-capture-C1C_baseline_1.json").is_file())
        with self.assertRaises(Exception):
            import_capture_file(self.root, "manual-spec.json", run_id,
                                "C1C_baseline_1", str(source))
        missing = self.root / "scratch/missing.png"
        with self.assertRaises(Exception):
            import_capture_file(self.root, "manual-spec.json", run_id,
                                "C1C_rig_wide_1", str(missing))
        black = self.root / "scratch/black.png"
        black.write_bytes(_png_bytes((0, 0, 0)))
        with self.assertRaises(Exception):
            import_capture_file(self.root, "manual-spec.json", run_id,
                                "C1C_rig_wide_1", str(black))
        with self.assertRaises(Exception):
            import_capture_file(self.root, "manual-spec.json", run_id,
                                "C1C_not_in_spec", str(source))
        other = self.write_spec(self.spec_dict(run_id="c1c-other"), "other-spec.json")
        self.assertEqual("c1c-other", other.run_id)
        with self.assertRaises(Exception):
            import_capture_file(self.root, "other-spec.json", run_id,
                                "C1C_baseline_1", str(source))

    def test_report_is_new_only_and_duplicate_upload_is_impossible(self):
        raw = self.spec_dict()
        raw["evidence"]["require_durable_files"] = True
        spec = self.write_spec(raw, "durable-spec.json")
        adapter = self.adapter(screenshot_mode="saved_file")
        first = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS", first["result"])
        with self.assertRaises(Exception):
            Harness(self.root, spec, adapter).run()
        self.assertEqual(0, adapter.upload_calls)
        upload_spec = self.spec_dict()
        upload_spec["asset"]["upload"] = True
        with self.assertRaises(Exception):
            self.write_spec(upload_spec, "upload-spec.json")


class CleanupSafetyTests(HarnessFixture):
    def test_unrelated_object_inside_rig_refuses_deletion_and_preserves_evidence(self):
        class InjectingAdapter(InMemoryStudioAdapter):
            injected = False

            def screenshot(self, capture_id, camera):
                folder = "Workspace.C1C_TextureTest_c1c-test-001"
                if not self.injected and folder in self.nodes:
                    self.injected = True
                    self.inject_object(folder, "C1C_Unrelated", "Part")
                return super().screenshot(capture_id, camera)

        spec = self.write_spec()
        adapter = InjectingAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        self.assertTrue(any(item["code"] == "cleanup_ownership_violation"
                            for item in report["failures"]))
        self.assertIn("Workspace.C1C_TextureTest_c1c-test-001",
                      adapter.snapshot()["objects"])
        self.assertTrue(report["evidence"]["failure_evidence"])
        self.assertTrue((self.root / report["evidence"]["failure_evidence"]).is_file())

    def test_wrong_run_id_or_tag_refuses_deletion(self):
        for corruption in ("run_id", "tag"):
            with self.subTest(corruption=corruption):
                run_id = f"c1c-wrong-{corruption}"
                raw = self.spec_dict(run_id=run_id)
                spec = self.write_spec(raw, f"wrong-{corruption}.json")

                class CorruptingAdapter(InMemoryStudioAdapter):
                    corrupted = False

                    def screenshot(self, capture_id, camera):
                        folder = f"Workspace.C1C_TextureTest_{run_id}"
                        if not self.corrupted and folder in self.nodes:
                            self.corrupted = True
                            path = f"{folder}.C1C_Panel_4spt"
                            if corruption == "run_id":
                                self.set_attributes(path, {
                                    RUN_ATTR: "someone-else", TESTONLY_ATTR: True})
                            else:
                                self.set_tags(path, [])
                        return super().screenshot(capture_id, camera)

                adapter = CorruptingAdapter(scratch_dir=self.root / "scratch")
                report = Harness(self.root, spec, adapter).run()
                self.assertEqual("FAIL", report["result"])
                self.assertFalse(report["cleanup"]["destroyed"])
                self.assertTrue(any(item["code"] == "cleanup_ownership_violation"
                                    for item in report["failures"]))
                self.assertTrue(any(item["code"] in ("run_id", "tag")
                                    for item in report["cleanup"]["verification"]["violations"]))
                self.assertTrue((self.root / report["evidence"]["failure_evidence"]).is_file())

    def test_unexpected_workspace_object_fails_baseline_verification(self):
        class BaselineBreaker(InMemoryStudioAdapter):
            broken = False

            def screenshot(self, capture_id, camera):
                if not self.broken:
                    self.broken = True
                    self.inject_object("Workspace", "Unexpected", "Part")
                return super().screenshot(capture_id, camera)

        spec = self.write_spec()
        adapter = BaselineBreaker(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertEqual("FAIL", report["workspace_verification"]["result"])
        self.assertTrue(any(item["scope"] == "Workspace.Unexpected"
                            for item in report["workspace_verification"]["differences"]))
        self.assertTrue(report["cleanup"]["destroyed"])
        # An unrelated object is never deleted by cleanup.
        self.assertIn("Workspace.Unexpected", adapter.snapshot()["objects"])

    def test_new_rig_is_verified_before_any_rig_capture(self):
        class BadOwnershipAdapter(InMemoryStudioAdapter):
            def create_part(self, folder_path, name, attributes, tags, properties):
                if name.endswith("4spt"):
                    tags = []
                return super().create_part(folder_path, name, attributes, tags, properties)

        spec = self.write_spec()
        adapter = BadOwnershipAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertIn("rig_ownership_verification_failed",
                      [item["code"] for item in report["failures"]])
        self.assertEqual(["C1C_baseline_1"], adapter.screenshot_calls)
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertTrue(report["evidence"]["failure_evidence"])

    def test_cleanup_failure_preserves_failure_evidence(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline", fail_destroy=True)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertTrue(any(item["code"] == "cleanup_destroy_failed"
                            for item in report["failures"]))
        self.assertTrue((self.root / report["evidence"]["failure_evidence"]).is_file())

    def test_texture_child_naming_inconsistency_can_be_safely_repaired(self):
        raw = self.spec_dict()
        raw["cleanup"]["allow_safe_rename"] = True
        spec = self.write_spec(raw, "rename-spec.json")
        adapter = self.adapter(screenshot_mode="inline", naming_mode="raw")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        self.assertEqual([], report["cleanup"]["verification"]["naming_issues"])
        self.assertTrue(report["cleanup"]["renamed"])
        self.assertTrue(any(item["to"].endswith(".C1C_Texture")
                            for item in report["cleanup"]["renamed"]))
        self.assertTrue(adapter.rename_calls)
        self.assertTrue(report["cleanup"]["destroyed"])

    def test_texture_child_naming_inconsistency_refuses_deletion_by_default(self):
        raw = self.spec_dict()
        raw["cleanup"]["allow_safe_rename"] = False
        spec = self.write_spec(raw, "strict-spec.json")
        adapter = self.adapter(screenshot_mode="inline", naming_mode="raw")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        self.assertTrue(any(item["code"] == "cleanup_naming_inconsistency"
                            for item in report["failures"]))
        self.assertTrue((self.root / report["evidence"]["failure_evidence"]).is_file())


class RecoveryTests(HarnessFixture):
    def test_interrupted_run_recovers_without_repeating_captures(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline", interrupt_after_objects=7)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("INCOMPLETE", report["result"])
        self.assertTrue((self.root / "registry/evidence/c1c/c1c-test-001/state.json").is_file())
        self.assertIn(spec.folder_path, adapter.snapshot()["objects"])
        partial_calls = list(adapter.screenshot_calls)

        recovered = recover(self.root, spec, adapter)
        self.assertEqual("RECOVERED", recovered["result"], recovered["failures"])
        self.assertTrue(recovered["recovery"]["recovered"])
        self.assertFalse(recovered["recovery"]["captures_repeated"])
        self.assertEqual(partial_calls, adapter.screenshot_calls)
        self.assertNotIn(spec.folder_path, adapter.snapshot()["objects"])
        self.assertTrue(recovered["cleanup"]["destroyed"])
        self.assertTrue(recovered["workspace_verification"]["result"] == "PASS")
        self.assertTrue(recovered["restoration"]["complete"])
        report_files = list((self.root / "registry/evidence/c1c/c1c-test-001").glob("recovery-*.json"))
        self.assertEqual(1, len(report_files))


class ContractTests(HarnessFixture):
    def test_manifest_rejects_duplicate_ids_status_and_hash_mismatch(self):
        duplicate = copy.deepcopy(self.manifest)
        duplicate["assets"].append(copy.deepcopy(duplicate["assets"][0]))
        self.write_manifest(duplicate)
        with self.assertRaises(ManifestError):
            AssetManifest(self.root).load()
        self.write_manifest()

        missing = self.spec_dict()
        missing["asset"]["asset_id"] = "rbxassetid://999999999999"
        spec = self.write_spec(missing, "missing-asset.json")
        report = Harness(self.root, spec, self.adapter()).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(any("not recorded" in item["message"]
                            for item in report["failures"]))

        bad_hash = self.spec_dict(run_id="c1c-bad-hash")
        bad_hash["asset"]["source_sha256"] = "0" * 64
        spec = self.write_spec(bad_hash, "bad-hash.json")
        report = Harness(self.root, spec, self.adapter()).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(any("SHA-256" in item["message"] for item in report["failures"]))

    def test_b2_pending_gates_are_required_and_not_an_approval(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"], report["failures"])
        self.assertEqual("PASS", report["b2"]["result"])

        self.b2["registry_gate_claims"]["technical"] = {
            "result": "pass", "evidence": ["claimed"], "reviewer": "made-up"}
        self.write_b2()
        raw = self.spec_dict(run_id="c1c-b2-approved")
        spec = self.write_spec(raw, "b2-approved-spec.json")
        report = Harness(self.root, spec, self.adapter()).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(any("non-pending" in item["message"]
                            for item in report["failures"]))

    def test_b1_registry_change_during_run_fails_the_run(self):
        journal = self.root / "registry/events.jsonl"

        class RegistryWriter(InMemoryStudioAdapter):
            written = False

            def screenshot(self, capture_id, camera):
                folder = "Workspace.C1C_TextureTest_c1c-test-001"
                if not self.written and folder in self.nodes:
                    self.written = True
                    journal.write_text('{"fake":"event"}\n', encoding="utf-8")
                return super().screenshot(capture_id, camera)

        spec = self.write_spec()
        adapter = RegistryWriter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["b1"]["unchanged"])
        self.assertTrue(any(item["code"] == "b1_registry_modified"
                            for item in report["failures"]))
        self.assertTrue(journal.is_file())
        self.assertTrue(report["cleanup"]["destroyed"])

    def test_spec_rejects_unsafe_paths_and_traversal(self):
        raw = self.spec_dict()
        raw["run_id"] = "../escape"
        with self.assertRaises(Exception):
            self.write_spec(raw, "bad-run.json")
        raw = self.spec_dict()
        raw["evidence"]["out_dir"] = "outputs/elsewhere"
        with self.assertRaises(Exception):
            self.write_spec(raw, "bad-evidence.json")
        self.write_spec()
        with self.assertRaises(Exception):
            load_spec(self.root, "../outside.json")

    def test_planned_rig_reproduces_c1b_layout_and_ownership_metadata(self):
        spec = self.write_spec()
        plan = build_rig_plan(spec)
        panels = [item for item in plan.objects if item.class_name == "Part"
                  and item.name.startswith("C1C_Panel_")]
        seam = [item for item in plan.objects if item.class_name == "Part"
                and item.name.startswith("C1C_Seam")]
        self.assertEqual(4, len(panels))
        self.assertEqual(2, len(seam))
        positions = {tuple(item.properties["Position"]) for item in panels}
        self.assertEqual({(-18.0, 0.5, 47.0), (18.0, 0.5, 47.0),
                          (-18.0, 0.5, 83.0), (18.0, 0.5, 83.0)}, positions)
        right = next(item for item in seam if item.name == "C1C_SeamRight")
        texture = next(item for item in plan.objects
                       if item.parent == right.path and item.class_name == "Texture")
        self.assertEqual(16, texture.properties["OffsetStudsU"])
        for item in plan.objects:
            self.assertTrue(item.attributes[RUN_ATTR])
            self.assertIs(True, item.attributes[TESTONLY_ATTR])
            self.assertIn(TAG, item.tags)

    def test_cli_validate_and_plan_are_read_only(self):
        self.write_spec()
        validate = subprocess.run(
            [sys.executable, str(ROOT / "tool/c1c_verify.py"), "--root", str(self.root),
             "validate", "--spec", "spec.json"],
            text=True, capture_output=True,
        )
        self.assertEqual(0, validate.returncode, validate.stderr)
        payload = json.loads(validate.stdout)
        self.assertEqual("PASS", payload["result"])
        self.assertEqual("rbxassetid://112705883084796", payload["asset"]["asset_id"])
        self.assertEqual([], list((self.root / "registry/evidence/c1c").glob("*")))

        plan = subprocess.run(
            [sys.executable, str(ROOT / "tool/c1c_verify.py"), "--root", str(self.root),
             "plan", "--spec", "spec.json"],
            text=True, capture_output=True,
        )
        self.assertEqual(0, plan.returncode, plan.stderr)
        planned = json.loads(plan.stdout)
        self.assertEqual(4, len([item for item in planned["rig"]["objects"]
                                 if item["name"].startswith("C1C_Panel_")]))
        self.assertEqual("c1c-test-001", planned["luau_plan"]["run_id"])
        self.assertEqual(planned["rig"]["folder"], planned["luau_plan"]["rig"]["folder"])
        self.assertFalse(planned["uploads_assets"])
        self.assertFalse(planned["saves_or_publishes"])
        self.assertFalse(planned["writes_b1_events"])
        self.assertEqual([], list((self.root / "registry/evidence/c1c").glob("*")))
        self.assertFalse((self.root / "registry/events.jsonl").exists())


class HardeningOwnershipTests(HarnessFixture):
    RUN_ID = "c1c-test-001"
    FOLDER = f"Workspace.C1C_TextureTest_{RUN_ID}"

    def _run_with_last_capture_hook(self, hook, run_id="c1c-test-001"):
        class HookAdapter(InMemoryStudioAdapter):
            def screenshot(self, capture_id, camera):
                result = super().screenshot(capture_id, camera)
                if capture_id == "C1C_seam_1":
                    hook(self)
                return result

        raw = self.spec_dict(run_id=run_id)
        spec = self.write_spec(raw, f"hook-{run_id}.json")
        adapter = HookAdapter(scratch_dir=self.root / "scratch")
        return spec, adapter, Harness(self.root, spec, adapter).run()

    def test_run_root_must_be_a_folder(self):
        def corrupt(adapter):
            adapter.nodes[f"Workspace.C1C_TextureTest_{self.RUN_ID}"]["class_name"] = "Model"

        spec, adapter, report = self._run_with_last_capture_hook(corrupt)
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        self.assertTrue(any(item["code"] == "cleanup_run_root_not_folder"
                            for item in report["failures"]))

    def test_incomplete_snapshot_marker_blocks_cleanup(self):
        class TruncatedAdapter(InMemoryStudioAdapter):
            truncate = False

            def screenshot(self, capture_id, camera):
                result = super().screenshot(capture_id, camera)
                if capture_id == "C1C_seam_1":
                    self.truncate = True
                return result

            def snapshot(self):
                document = super().snapshot()
                if self.truncate:
                    document["complete"] = False
                return document

        spec = self.write_spec()
        adapter = TruncatedAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        self.assertTrue(any(item["code"] == "cleanup_snapshot_incomplete"
                            for item in report["failures"]))
        self.assertTrue(report["evidence"]["failure_evidence"])

    def test_structurally_incomplete_snapshot_blocks_cleanup(self):
        target = f"{self.FOLDER}.C1C_Panel_4spt.C1C_Texture"

        class MissingChildAdapter(InMemoryStudioAdapter):
            truncate = False

            def screenshot(self, capture_id, camera):
                result = super().screenshot(capture_id, camera)
                if capture_id == "C1C_seam_1":
                    self.truncate = True
                return result

            def snapshot(self):
                document = super().snapshot()
                if self.truncate:
                    document["objects"].pop(target, None)
                return document

        spec = self.write_spec()
        adapter = MissingChildAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertTrue(any(item["code"] == "cleanup_snapshot_incomplete"
                            for item in report["failures"]))
        issues = report["cleanup"]["verification"]["snapshot"]["issues"]
        self.assertTrue(any(item["code"] == "child_missing" for item in issues))

    def test_unexpected_owned_object_inside_folder_refuses_deletion(self):
        def inject(adapter):
            adapter.inject_object(
                f"Workspace.C1C_TextureTest_{self.RUN_ID}", "C1C_Stray", "Part",
                attributes={RUN_ATTR: self.RUN_ID, TESTONLY_ATTR: True}, tags=[TAG])

        spec, adapter, report = self._run_with_last_capture_hook(inject)
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertTrue(any(item["code"] == "unexpected_object"
                            for item in report["cleanup"]["verification"]["violations"]))

    def test_unexpected_tracked_object_outside_folder_refuses_deletion(self):
        def inject(adapter):
            adapter.inject_object(
                "Workspace", "Stray", "Part",
                attributes={RUN_ATTR: self.RUN_ID, TESTONLY_ATTR: True}, tags=[TAG])

        spec, adapter, report = self._run_with_last_capture_hook(inject)
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["cleanup"]["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        verification = report["cleanup"]["verification"]
        self.assertTrue(verification["outside_tagged"])
        self.assertTrue(verification["outside_run_attribute"])
        self.assertIn("Workspace.Stray", adapter.snapshot()["objects"])

    def test_fresh_ownership_recheck_runs_immediately_before_destroy(self):
        class TwoFaceAdapter(InMemoryStudioAdapter):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self.snapshot_calls = 0
                self.flip_at = None
                self.flip_path = None

            def snapshot(self):
                self.snapshot_calls += 1
                document = super().snapshot()
                if (self.flip_at == self.snapshot_calls
                        and self.flip_path in document["objects"]):
                    document["objects"][self.flip_path]["tags"] = []
                return document

        spec = self.write_spec()
        adapter = TwoFaceAdapter(scratch_dir=self.root / "scratch")
        baseline = capture_baseline(adapter.snapshot())
        build = build_rig(adapter, spec, build_rig_plan(spec))
        self.assertTrue(build["build_ok"])
        store = EvidenceStore(self.root, spec.evidence.out_dir, spec.run_id).open_run()
        harness = Harness(self.root, spec, adapter)
        harness.store = store
        harness.baseline = baseline
        harness.phase = "cleanup"
        adapter.snapshot_calls = 0
        adapter.flip_at = 2
        adapter.flip_path = f"Workspace.C1C_TextureTest_{spec.run_id}.C1C_Panel_4spt"
        harness._cleanup()
        self.assertEqual("FAIL", harness.cleanup_report["result"])
        self.assertFalse(harness.cleanup_report["destroyed"])
        self.assertEqual([], adapter.destroy_calls)
        self.assertTrue(any(item["code"] == "cleanup_recheck_failed"
                            for item in harness.failures))
        self.assertTrue(harness.cleanup_report["fresh_verification"])


class PartialBuildTests(HarnessFixture):
    def test_partial_object_creation_failure_is_safely_cleaned_up(self):
        class FailingCreateAdapter(InMemoryStudioAdapter):
            def create_part(self, folder_path, name, attributes, tags, properties):
                if name.endswith("16spt"):
                    raise RuntimeError("simulated object creation failure")
                return super().create_part(folder_path, name, attributes, tags, properties)

        spec = self.write_spec()
        adapter = FailingCreateAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertFalse(report["rig"]["build_success"])
        self.assertEqual("build_failed", report["rig"]["build_phase"])
        self.assertTrue(report["rig"]["partial_objects"])
        self.assertTrue(any(item["code"] == "build_failed" for item in report["failures"]))
        self.assertEqual("PASS", report["cleanup"]["result"])
        self.assertTrue(report["cleanup"]["destroyed"])
        self.assertNotIn(spec.folder_path, adapter.snapshot()["objects"])
        state_path = self.root / f"registry/evidence/c1c/{spec.run_id}/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        self.assertEqual("build_failed", state["last_confirmed_build_phase"])
        self.assertTrue(state["partial_objects"])
        self.assertFalse(state["build"]["success"])

    def test_preload_failure_is_distinct_from_build_success(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline", known_assets=set())
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(report["rig"]["build_success"])
        self.assertFalse(report["rig"]["preload_success"])
        self.assertEqual("preload_failed", report["rig"]["build_phase"])
        self.assertTrue(any(item["code"] == "preload_failed"
                            for item in report["failures"]))
        self.assertEqual("PASS", report["cleanup"]["result"])
        self.assertTrue(report["cleanup"]["destroyed"])
        self.assertNotIn(spec.folder_path, adapter.snapshot()["objects"])

    def test_incomplete_rig_refuses_rig_captures(self):
        panel = "Workspace.C1C_TextureTest_c1c-test-001.C1C_Panel_4spt"

        class PruningAdapter(InMemoryStudioAdapter):
            def preload(self, asset_id, paths):
                self.destroy(panel)
                return super().preload(asset_id, paths)

        spec = self.write_spec()
        adapter = PruningAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(any(item["code"] == "rig_incomplete"
                            for item in report["failures"]))
        self.assertEqual(["C1C_baseline_1"], adapter.screenshot_calls)
        self.assertEqual("PASS", report["cleanup"]["result"])
        self.assertNotIn(spec.folder_path, adapter.snapshot()["objects"])

    def test_cleanup_failure_preserves_actionable_recovery_information(self):
        spec = self.write_spec()
        adapter = self.adapter(screenshot_mode="inline", fail_destroy=True)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        failure_path = self.root / report["evidence"]["failure_evidence"]
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        self.assertIn("next_action", failure)
        self.assertIn("recover", failure["next_action"].lower())
        self.assertEqual("cleanup", failure["last_confirmed_phase"])
        self.assertIsNotNone(failure["recovery_info"])


class OriginalRunIntegrityTests(HarnessFixture):
    def _interrupted(self, run_id):
        raw = self.spec_dict(run_id=run_id)
        spec = self.write_spec(raw, f"interrupt-{run_id}.json")
        adapter = self.adapter(screenshot_mode="inline", interrupt_after_objects=7)
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("INCOMPLETE", report["result"])
        return spec, adapter

    def test_recovery_rejects_changed_spec_with_same_run_id(self):
        run_id = "c1c-provenance-spec"
        spec, adapter = self._interrupted(run_id)
        changed = self.spec_dict(run_id=run_id)
        changed["geometry"]["panel_size_studs"] = 40
        changed_spec = self.write_spec(changed, "changed-spec.json")
        with self.assertRaises(ProvenanceError):
            recover(self.root, changed_spec, adapter)
        self.assertIn(spec.folder_path, adapter.snapshot()["objects"])

    def test_recovery_rejects_b1_change_between_crash_and_recovery(self):
        run_id = "c1c-provenance-b1"
        spec, adapter = self._interrupted(run_id)
        (self.root / "registry/events.jsonl").write_text('{"fake":"event"}\n',
                                                         encoding="utf-8")
        with self.assertRaises(ProvenanceError):
            recover(self.root, spec, adapter)
        self.assertIn(spec.folder_path, adapter.snapshot()["objects"])

    def test_recovery_rejects_changed_asset_manifest(self):
        run_id = "c1c-provenance-manifest"
        spec, adapter = self._interrupted(run_id)
        changed = copy.deepcopy(self.manifest)
        changed["assets"].append({
            **copy.deepcopy(changed["assets"][0]),
            "roblox_asset_id": "999999999999",
            "source_path": "outputs/other.png",
        })
        (self.root / "outputs/other.png").write_bytes(_png_bytes((1, 2, 3)))
        self.write_manifest(changed)
        with self.assertRaises(ProvenanceError):
            recover(self.root, spec, adapter)

    def test_recovery_rejects_missing_provenance_fields(self):
        fields = ("spec_sha256", "baseline_sha256", "b1_before", "asset_manifest",
                  "plan", "expected_object_inventory")
        for index, field in enumerate(fields):
            with self.subTest(field=field):
                run_id = f"c1c-provenance-missing-{index}"
                spec, adapter = self._interrupted(run_id)
                state_path = (self.root / f"registry/evidence/c1c/{run_id}/state.json")
                state = json.loads(state_path.read_text(encoding="utf-8"))
                state.pop(field)
                state_path.write_text(json.dumps(state), encoding="utf-8")
                with self.assertRaises(ProvenanceError):
                    recover(self.root, spec, adapter)
                self.assertIn(spec.folder_path, adapter.snapshot()["objects"])

    def test_recovery_is_bound_to_original_baseline_and_b1_window(self):
        run_id = "c1c-provenance-ok"
        spec, adapter = self._interrupted(run_id)
        state_path = self.root / f"registry/evidence/c1c/{run_id}/state.json"
        original = json.loads(state_path.read_text(encoding="utf-8"))
        recovered = recover(self.root, spec, adapter)
        self.assertEqual("RECOVERED", recovered["result"], recovered["failures"])
        self.assertTrue(recovered["recovery"]["provenance_verified"])
        self.assertTrue(recovered["provenance"]["recovery"]["verified"])
        self.assertEqual(original["baseline_sha256"],
                         recovered["provenance"]["recovery"]["baseline_sha256"])
        self.assertEqual(original["b1_before"],
                         recovered["provenance"]["recovery"]["b1_before"])
        self.assertEqual(original["spec_sha256"],
                         recovered["provenance"]["recovery"]["spec_sha256"])


class EvidenceBindingTests(HarnessFixture):
    def test_malformed_b2_claim_rows_are_rejected(self):
        spec = self.write_spec()
        cases = [
            ("claims_not_object", []),
            ("claim_not_object", {"technical": "pending"}),
            ("missing_result", {"technical": {"evidence": []}}),
            ("non_string_result", {"technical": {"result": 1, "evidence": []}}),
            ("evidence_not_list", {"technical": {"result": "pending", "evidence": "x"}}),
        ]
        for name, claims in cases:
            with self.subTest(case=name):
                document = copy.deepcopy(self.b2)
                document["registry_gate_claims"] = claims
                (self.root / "registry/evidence/b2.json").write_text(
                    json.dumps(document), encoding="utf-8")
                with self.assertRaises(HarnessError):
                    verify_b2_evidence(self.root, spec, self.digest)

    def test_capture_id_mismatch_is_rejected(self):
        class WrongIdAdapter(InMemoryStudioAdapter):
            def screenshot(self, capture_id, camera):
                return CaptureResult(capture_id + "_wrong", inline_only=True)

        spec = self.write_spec()
        adapter = WrongIdAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertEqual(8, report["evidence"]["invalid_captures"])
        self.assertTrue(all("different capture ID" in (item["invalid_reason"] or "")
                            for item in report["captures"]))
        self.assertTrue(report["cleanup"]["destroyed"])

    def test_ambiguous_capture_payload_is_rejected(self):
        class AmbiguousAdapter(InMemoryStudioAdapter):
            def screenshot(self, capture_id, camera):
                target = self.scratch_dir / f"{capture_id}-ambiguous.png"
                target.write_bytes(self._png(pattern=True))
                return CaptureResult(capture_id, image_bytes=self._png(pattern=True),
                                     image_path=str(target))

        spec = self.write_spec()
        adapter = AmbiguousAdapter(scratch_dir=self.root / "scratch")
        report = Harness(self.root, spec, adapter).run()
        self.assertEqual("FAIL", report["result"])
        self.assertTrue(all("ambiguous" in (item["invalid_reason"] or "")
                            for item in report["captures"]))

    def test_evidence_acceptance_requires_required_durable_files(self):
        durable = self.spec_dict(run_id="c1c-accept-durable")
        durable["evidence"]["require_durable_files"] = True
        spec = self.write_spec(durable, "accept-durable.json")
        report = Harness(self.root, spec,
                         self.adapter(screenshot_mode="saved_file")).run()
        self.assertTrue(report["evidence"]["accepted"])
        self.assertTrue(report["evidence"]["durable_required_satisfied"])

        inline = self.spec_dict(run_id="c1c-accept-inline")
        inline["evidence"]["require_durable_files"] = False
        spec = self.write_spec(inline, "accept-inline.json")
        report = Harness(self.root, spec, self.adapter(screenshot_mode="inline")).run()
        self.assertFalse(report["evidence"]["accepted"])
        self.assertFalse(report["evidence"]["durable_required_satisfied"])
        self.assertEqual("PASS_WITH_RESIDUALS", report["result"])

        strict = self.spec_dict(run_id="c1c-accept-strict")
        strict["evidence"]["require_durable_files"] = True
        spec = self.write_spec(strict, "accept-strict.json")
        report = Harness(self.root, spec, self.adapter(screenshot_mode="inline")).run()
        self.assertFalse(report["evidence"]["complete"])
        self.assertFalse(report["evidence"]["accepted"])
        self.assertEqual("FAIL", report["result"])


class CorrectnessTests(HarnessFixture):
    def test_planned_object_count_is_25_not_26(self):
        spec = self.write_spec()
        plan = build_rig_plan(spec)
        self.assertEqual(25, len(plan.objects))
        self.assertEqual(25, plan.as_dict()["object_count"])
        report = Harness(self.root, spec, self.adapter(screenshot_mode="inline")).run()
        self.assertEqual(25, report["rig"]["planned_object_count"])
        self.assertEqual(25, len(report["rig"]["expected_object_inventory"]))
        self.assertIsNotNone(report["provenance"]["plan_sha256"])
        self.assertEqual(25, len(report["provenance"]["expected_object_inventory"]))

    def test_pinned_test_asset_cannot_change_status(self):
        document = copy.deepcopy(self.manifest)
        document["assets"][0]["status"] = "approved"
        self.write_manifest(document)
        spec = self.write_spec()
        manifest = AssetManifest(self.root).load()
        with self.assertRaises(ManifestError):
            manifest.resolve(spec.asset)

    def test_schema_version_is_checked(self):
        raw = self.spec_dict()
        raw["schema_version"] = "2.0"
        with self.assertRaises(Exception):
            self.write_spec(raw, "future-schema.json")

    def test_luau_helper_retains_plan_validation_and_fresh_recheck(self):
        source = (ROOT / "tool/c1c/studio_rig.luau").read_text(encoding="utf-8")
        self.assertIn("validatePlan(plan)", source)
        self.assertIn("unexpected_object", source)
        self.assertIn("fresh pre-destruction ownership check failed", source)
        self.assertIn("pre-existing C1C_-prefixed objects exist", source)
        self.assertIn("preload_failed", source)


if __name__ == "__main__":
    unittest.main()
