"""B1 fixtures are synthetic local files, never real approvals or imports."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
from asset_registry import Registry, RegistryError  # noqa: E402
from validate_art import draft_request  # noqa: E402


def sha(data):
    return hashlib.sha256(data).hexdigest()


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for folder in ("art/schemas", "art/presets", "art/games", "registry/evidence",
                       "outputs", "workflows"):
            (self.root / folder).mkdir(parents=True)
        for name in ("asset-request", "style-profile"):
            shutil.copy2(ROOT / f"art/schemas/{name}.schema.json", self.root / "art/schemas")
        shutil.copy2(ROOT / "art/presets/adventure-fantasy.json", self.root / "art/presets")
        bible = "# Synthetic Art Bible\n**Game ID:** example-game\n**Style profile:** adventure-fantasy\n**Version:** 1.0\n"
        bible_hash = self.write("art/games/example-bible.md", bible)
        approval = {"game_id": "example-game", "version": "1.0", "bible_sha256": bible_hash,
                    "profile_id": "adventure-fantasy", "approved_by": "fixture-art-owner",
                    "approved_on": "2026-10-17"}
        approval_hash = self.write("registry/evidence/bible-approval.json", json.dumps(approval))
        self.manifest = {"game_id": "example-game", "actors": {
            "creators": ["fixture-maker"], "art_owners": ["fixture-art-owner"],
            "qc_reviewers": ["fixture-qc"], "importers": ["fixture-importer"],
            "final_reviewers": ["fixture-final"]}, "art_bibles": [{
                "version": "1.0", "path": "art/games/example-bible.md", "sha256": bible_hash,
                "profile_id": "adventure-fantasy", "approval_evidence": "registry/evidence/bible-approval.json",
                "approval_evidence_sha256": approval_hash, "approved_by": "fixture-art-owner",
                "approved_on": "2026-10-17"}]}
        self.write("art/games/example-game.json", json.dumps(self.manifest))
        self.output = "outputs/fixture-image.png"
        self.output_hash = self.write(self.output, "synthetic file bytes")
        self.workflow = "workflows/fixture.json"
        self.workflow_hash = self.write(self.workflow, "{}")
        self.evidence_path = "registry/evidence/fixture-note.txt"
        self.write(self.evidence_path, "Synthetic review evidence only")
        self.registry = Registry(self.root)
        self.asset = "fixture-image-0001"

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content.encode() if isinstance(content, str) else content
        path.write_bytes(data)
        return sha(data)

    def request(self, asset=None):
        request = draft_request()
        request.update(id=asset or self.asset, asset_type="image")
        request["delivery"].update(tiling_required=False)
        request["generation"].update(workflow=self.workflow)
        return request

    def data(self, action):
        if action == "create":
            return {"request": self.request()}
        if action == "art_approved":
            return {"bible_version": "1.0", "bible_sha256": self.manifest["art_bibles"][0]["sha256"],
                    "approval_evidence_sha256": self.manifest["art_bibles"][0]["approval_evidence_sha256"]}
        if action == "generated":
            return {"path": self.output, "sha256": self.output_hash, "size_bytes":
                    (self.root / self.output).stat().st_size, "workflow_path": self.workflow,
                    "workflow_sha256": self.workflow_hash}
        if action == "qc_pending":
            return {}
        if action == "qc_passed":
            gates = {name: {"result": "pass", "evidence": [self.evidence_path],
                            "reviewer": "fixture-qc"} for name in
                     ("originality", "rights", "style", "technical", "performance")}
            gates["tiling"] = {"result": "not_applicable", "evidence": []}
            return {"gates": gates, "preimport_performance": {"kind": "estimate",
                    "notes": "Fixture-only estimate, not device measurement", "evidence": [self.evidence_path]}}
        if action == "imported":
            import_record = {"game_id": "example-game", "asset_id": self.asset, "revision": 1,
                             "output_sha256": self.output_hash, "roblox_asset_id": "12345",
                             "imported_by": "fixture-importer", "imported_on": "2026-10-17"}
            digest = self.write("registry/evidence/import.json", json.dumps(import_record))
            return {"roblox_asset_id": "12345", "record_path": "registry/evidence/import.json",
                    "record_sha256": digest}
        if action == "approved":
            return {"in_engine": {"result": "pass", "reviewer": "fixture-final",
                                  "evidence": [self.evidence_path]},
                    "measured_performance": {"kind": "in_engine_measurement", "device": "fixture device",
                                             "scene": "fixture scene", "fps": 30,
                                             "evidence": [self.evidence_path]},
                    "final_evidence": [self.evidence_path]}
        if action == "rejected":
            return {"reason": "Synthetic defect", "evidence": [self.evidence_path]}
        if action == "rework":
            return {"request": self.request()}
        raise AssertionError(action)

    def actor(self, action):
        return {"create": "fixture-maker", "art_approved": "fixture-art-owner",
                "generated": "fixture-maker", "qc_pending": "fixture-maker",
                "qc_passed": "fixture-qc", "imported": "fixture-importer",
                "approved": "fixture-final", "rejected": "fixture-qc",
                "rework": "fixture-maker"}[action]

    def step(self, action, data=None, dry_run=False, actor=None):
        return self.registry.apply(action, self.asset, actor or self.actor(action),
                                   self.data(action) if data is None else data, dry_run)

    def drive(self, through):
        for action in ("create", "art_approved", "generated", "qc_pending", "qc_passed",
                       "imported", "approved"):
            self.step(action)
            if action == through:
                break

    def test_all_legal_transitions_and_replay(self):
        self.drive("approved")
        record = self.registry.validate()[self.asset]
        self.assertEqual("approved", record["request"]["approval"]["status"])
        self.assertEqual(7, len(record["history"]))
        self.assertEqual("in_engine_measurement", record["performance"]["kind"])
        self.assertEqual("12345", record["request"]["approval"]["roblox_asset_id"])

    def test_forbidden_transition_matrix(self):
        stages = ("create", "art_approved", "generated", "qc_pending", "qc_passed", "imported", "approved")
        self.step("create")
        for current_index in range(len(stages)):
            with self.subTest(current=stages[current_index]):
                if current_index:
                    self.step(stages[current_index])
                for action in stages[1:]:
                    if current_index + 1 < len(stages) and action == stages[current_index + 1]:
                        continue
                    with self.subTest(current=stages[current_index], attempted=action):
                        with self.assertRaises(RegistryError):
                            self.step(action, dry_run=True)
                with self.assertRaises(RegistryError):
                    self.step("rework", dry_run=True)
        with self.assertRaises(RegistryError):
            self.step("rejected")
        with self.assertRaises(RegistryError):
            self.step("unsupported", {}, dry_run=True, actor="fixture-maker")

    def test_reject_and_rework_preserve_candidate(self):
        self.drive("generated")
        self.step("rejected")
        with self.assertRaises(RegistryError):
            self.step("rejected", dry_run=True)
        result = self.step("rework")
        self.assertEqual(2, result["revision"])
        self.assertEqual("draft", result["request"]["approval"]["status"])
        self.assertEqual("rejected", result["candidates"][0]["approval"]["status"])
        self.assertEqual(self.output_hash, result["candidates"][0]["delivery"]["artifact_sha256"])
        self.assertEqual(5, len(self.registry.validate()[self.asset]["history"]))

    def test_dry_run_no_mutation_and_lock(self):
        self.step("create", dry_run=True)
        self.assertFalse(self.registry.journal.exists())
        self.registry.lock.write_text("other writer", encoding="utf-8")
        with self.assertRaises(RegistryError):
            self.step("create")
        with self.assertRaises(RegistryError):
            self.registry.validate()
        self.registry.lock.unlink()
        self.step("create")

    def test_duplicate_ids_and_forged_draft(self):
        self.step("create")
        with self.assertRaisesRegex(RegistryError, "duplicate"):
            self.step("create", dry_run=True)
        forged = self.request("another-image-0002")
        forged["approval"]["status"] = "qc_passed"
        with self.assertRaises(RegistryError):
            self.registry.apply("create", forged["id"], "fixture-maker", {"request": forged}, True)

    def test_missing_profile_and_unknown_or_modified_bible(self):
        request = self.request()
        request["style_profile_id"] = "missing-profile"
        with self.assertRaises(RegistryError):
            self.step("create", {"request": request}, True)
        self.step("create")
        with self.assertRaises(RegistryError):
            self.step("art_approved", {**self.data("art_approved"), "bible_version": "missing"}, True)
        self.write("art/games/example-bible.md", "changed")
        with self.assertRaises(RegistryError):
            self.step("art_approved", dry_run=True)

    def test_output_hash_size_and_path_traversal(self):
        self.drive("art_approved")
        for key, wrong in (("sha256", "0" * 64), ("size_bytes", 1),
                           ("path", "../outside.png"), ("path", "art/games/example-bible.md"),
                           ("workflow_path", "../outside.json")):
            with self.subTest(key=key, wrong=wrong):
                data = self.data("generated")
                data[key] = wrong
                with self.assertRaises(RegistryError):
                    self.step("generated", data, True)
        self.step("generated")
        self.write(self.output, "tampered")
        with self.assertRaisesRegex(RegistryError, "SHA-256"):
            self.registry.validate()

    def test_qc_evidence_and_estimate_and_reviewer(self):
        self.drive("qc_pending")
        for variant in ("missing_file", "bad_gate", "missing_reviewer", "measured_instead",
                        "creator_review", "missing_estimate"):
            with self.subTest(variant=variant):
                data = self.data("qc_passed")
                if variant == "missing_file":
                    data["gates"]["rights"]["evidence"] = ["registry/evidence/missing.txt"]
                elif variant == "bad_gate":
                    data["gates"]["technical"]["result"] = "pending"
                elif variant == "missing_reviewer":
                    del data["gates"]["rights"]["reviewer"]
                elif variant == "measured_instead":
                    data["preimport_performance"]["kind"] = "in_engine_measurement"
                elif variant == "creator_review":
                    data["gates"]["style"]["reviewer"] = "fixture-maker"
                else:
                    data["preimport_performance"]["evidence"] = []
                with self.assertRaises((RegistryError, KeyError)):
                    self.step("qc_passed", data, True)
        self.step("qc_passed")
        self.write(self.evidence_path, "tampered evidence")
        with self.assertRaisesRegex(RegistryError, "SHA-256"):
            self.registry.validate()

    def test_fake_imports(self):
        self.drive("qc_passed")
        for variant in ("zero_id", "missing_record", "wrong_record", "wrong_hash", "unlisted_actor"):
            with self.subTest(variant=variant):
                data = self.data("imported")
                actor = "fixture-importer"
                if variant == "zero_id":
                    data["roblox_asset_id"] = "0"
                elif variant == "missing_record":
                    data["record_path"] = "registry/evidence/missing.json"
                elif variant == "wrong_record":
                    record = json.loads((self.root / data["record_path"]).read_text())
                    record["roblox_asset_id"] = "67890"
                    data["record_sha256"] = self.write(data["record_path"], json.dumps(record))
                elif variant == "wrong_hash":
                    data["record_sha256"] = "f" * 64
                else:
                    actor = "fixture-maker"
                with self.assertRaises(RegistryError):
                    self.step("imported", data, True, actor)

    def test_final_gate_and_rejection_requirements(self):
        self.drive("imported")
        for variant in ("missing_engine", "no_evidence", "wrong_signer", "no_measurement",
                        "fake_kind", "creator_signoff"):
            with self.subTest(variant=variant):
                data = self.data("approved")
                actor = "fixture-final"
                if variant == "missing_engine":
                    data["in_engine"]["result"] = "pending"
                elif variant == "no_evidence":
                    data["final_evidence"] = []
                elif variant == "wrong_signer":
                    data["in_engine"]["reviewer"] = "fixture-maker"
                elif variant == "no_measurement":
                    data["measured_performance"]["evidence"] = []
                elif variant == "fake_kind":
                    data["measured_performance"]["kind"] = "estimate"
                else:
                    actor = "fixture-maker"
                with self.assertRaises(RegistryError):
                    self.step("approved", data, True, actor)
        with self.assertRaises(RegistryError):
            self.step("rejected", {"reason": "", "evidence": [self.evidence_path]}, True,
                      "fixture-final")
        self.step("rejected", actor="fixture-final")

    def test_reject_missing_evidence_and_chain_tamper(self):
        self.step("create")
        with self.assertRaises(RegistryError):
            self.step("rejected", {"reason": "fixture issue", "evidence": ["registry/evidence/missing"]}, True)
        self.step("rejected")
        events = self.registry.read_events()
        events[0]["data"]["request"]["approval"]["status"] = "approved"
        self.write("registry/events.jsonl", "".join(json.dumps(e) + "\n" for e in events))
        with self.assertRaisesRegex(RegistryError, "hash chain"):
            self.registry.validate()

    def test_symlink_escape(self):
        self.drive("art_approved")
        outside = self.root.parent / (self.root.name + "-outside.png")
        outside.write_bytes(b"external fixture")
        self.addCleanup(outside.unlink)
        link = self.root / "outputs/link.png"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlinks unavailable")
        data = self.data("generated")
        data.update(path="outputs/link.png", sha256=sha(outside.read_bytes()), size_bytes=outside.stat().st_size)
        with self.assertRaises(RegistryError):
            self.step("generated", data, True)

    def test_import_id_unique_across_records(self):
        self.drive("imported")
        self.asset = "fixture-image-0002"
        self.drive("qc_passed")
        record_path = "registry/evidence/import-second.json"
        import_record = {"game_id": "example-game", "asset_id": self.asset, "revision": 1,
                         "output_sha256": self.output_hash, "roblox_asset_id": "12345",
                         "imported_by": "fixture-importer", "imported_on": "2026-10-17"}
        data = {"roblox_asset_id": "12345", "record_path": record_path,
                "record_sha256": self.write(record_path, json.dumps(import_record))}
        with self.assertRaisesRegex(RegistryError, "duplicate Roblox"):
            self.step("imported", data, True)

    def test_pinned_bible_and_profile_after_transition(self):
        self.drive("art_approved")
        self.manifest["art_bibles"][0]["sha256"] = "f" * 64
        self.write("art/games/example-game.json", json.dumps(self.manifest))
        with self.assertRaises(RegistryError):
            self.registry.validate()
        self.write("art/games/example-game.json", json.dumps({**self.manifest, "art_bibles": []}))
        with self.assertRaises(RegistryError):
            self.registry.validate()

    def test_cli_validate_and_dry_run_report(self):
        cli = ROOT / "tool/registry.py"
        cmd = [sys.executable, str(cli), "--root", str(self.root)]
        check = subprocess.run(cmd + ["validate"], capture_output=True, text=True)
        self.assertEqual(0, check.returncode, check.stderr)
        self.assertIn("PASS: 0 unique assets", check.stdout)
        payload = self.root / "create-payload.json"
        payload.write_text(json.dumps(self.data("create")), encoding="utf-8")
        result = subprocess.run(cmd + ["record", "create", "--id", self.asset, "--actor", "fixture-maker",
                                       "--data", str(payload), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("dry-run", result.stdout)
        self.assertFalse(self.registry.journal.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
