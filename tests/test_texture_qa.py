"""B2 fixture evaluation never writes the production registry or approves assets."""

import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
from texture_qa import QAError, evaluate, write_evidence  # noqa: E402
from validate_art import draft_request  # noqa: E402


class TextureQATests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ("art/schemas", "art/presets", "registry/evidence", "outputs"):
            (self.root / folder).mkdir(parents=True)
        for name in ("asset-request", "style-profile"):
            shutil.copy2(ROOT / f"art/schemas/{name}.schema.json", self.root / "art/schemas")
        for name in ("adventure-fantasy", "competitive-clean", "playful-cartoon"):
            shutil.copy2(ROOT / f"art/presets/{name}.json", self.root / "art/presets")
        self.name = "outputs/tile.png"
        Image.new("RGB", (128, 128), "#888888").save(self.root / self.name)

    def request(self, tiling=True):
        req = draft_request()
        req["delivery"].update(width_px=128, height_px=128, tiling_required=tiling)
        req["asset_type"] = "tileable_texture" if tiling else "image"
        return req

    def run_qa(self, name=None, **kwargs):
        return evaluate(self.root, name or self.name, kwargs.pop("profile_id", "adventure-fantasy"), **kwargs)

    def test_valid_png_request_and_new_only_evidence(self):
        report, images = self.run_qa(request=self.request(), seamless=True)
        self.assertEqual("PASS", report["checks"]["delivery"]["result"])
        self.assertEqual("REVIEW_REQUIRED", report["automated_result"])
        self.assertEqual("REVIEW_REQUIRED", report["overall_result"])
        self.assertEqual("PASS", report["assessments"]["mathematical_continuity"]["result"])
        self.assertEqual((384, 384), images["3x3"].size)
        self.assertEqual((640, 640), images["5x5"].size)
        refs = write_evidence(self.root, "registry/evidence/texture-qa", report, images)
        self.assertTrue(all((self.root / ref).is_file() for ref in refs.values()))
        saved = json.loads((self.root / refs["json"]).read_text())
        self.assertEqual("pending", saved["registry_gate_claims"]["tiling"]["result"])
        self.assertFalse((self.root / "registry/events.jsonl").exists())
        with self.assertRaisesRegex(QAError, "overwrite"):
            write_evidence(self.root, "registry/evidence/texture-qa", report, images)

    def test_corrupt_png_and_missing_file(self):
        (self.root / self.name).write_bytes(b"not a PNG")
        report, images = self.run_qa()
        self.assertEqual("FAIL", report["checks"]["readability"]["result"])
        self.assertFalse(images)
        report, _ = self.run_qa("outputs/missing.png")
        self.assertEqual("FAIL", report["checks"]["file"]["result"])

    def test_dimension_hash_and_profile_failures(self):
        req = self.request()
        req["delivery"]["width_px"] = 256
        report, _ = self.run_qa(request=req, seamless=True, expected_sha256="0" * 64)
        self.assertEqual("FAIL", report["checks"]["delivery"]["result"])
        self.assertEqual("FAIL", report["checks"]["sha256"]["result"])
        report, _ = self.run_qa(profile_id="nonexistent-style")
        self.assertEqual("FAIL", report["checks"]["style_profile"]["result"])
        req = self.request()
        req["style_profile_id"] = "competitive-clean"
        report, _ = self.run_qa(request=req, seamless=True)
        self.assertEqual("FAIL", report["checks"]["asset_metadata"]["result"])
        actual = hashlib.sha256((self.root / self.name).read_bytes()).hexdigest()
        report, _ = self.run_qa(expected_sha256=actual)
        self.assertEqual("PASS", report["checks"]["sha256"]["result"])
        report, _ = self.run_qa()
        self.assertEqual("REVIEW_REQUIRED", report["checks"]["sha256"]["result"])

    def test_supported_jpeg_and_webp_and_unsupported_gif(self):
        for extension in ("jpg", "webp", "gif"):
            name = f"outputs/format.{extension}"
            Image.new("RGB", (64, 64), "red").save(self.root / name)
            report, _ = self.run_qa(name)
            self.assertEqual("FAIL" if extension == "gif" else "PASS",
                             report["checks"]["readability"]["result"])

    def test_opposite_edge_failures_on_both_axes(self):
        for axis in (0, 1):
            pixels = np.zeros((128, 128, 3), dtype=np.uint8)
            pixels[:] = 80
            if axis == 0:
                pixels[-1, :, :] = 230
            else:
                pixels[:, -1, :] = 230
            Image.fromarray(pixels).save(self.root / self.name)
            report, _ = self.run_qa(seamless=True)
            self.assertEqual("FAIL", report["checks"]["edge_screen"]["result"])
            self.assertEqual("FAIL", report["overall_result"])
            metric = "horizontal_ratio" if axis == 0 else "vertical_ratio"
            self.assertGreater(report["metrics"]["raw_edges"][metric], 1.25)

    def test_exact_edges_do_not_prove_repetition_quality(self):
        tile = Image.new("RGB", (128, 128), (60, 60, 60))
        draw = ImageDraw.Draw(tile)
        draw.ellipse((40, 40, 88, 88), fill=(250, 250, 250))
        tile.save(self.root / self.name)
        report, _ = self.run_qa(seamless=True)
        self.assertEqual("PASS", report["assessments"]["mathematical_continuity"]["result"])
        self.assertEqual("REVIEW_REQUIRED", report["checks"]["repeated_motif_screen"]["result"])
        self.assertEqual("REVIEW_REQUIRED", report["assessments"]["repetition_quality"]["result"])

    def test_broad_tone_screen_and_quiet_texture_false_positive_guard(self):
        pixels = np.full((128, 128, 3), 80, dtype=np.uint8)
        pixels[-24:, :, :] = 200
        Image.fromarray(pixels).save(self.root / self.name)
        report, _ = self.run_qa(seamless=True)
        self.assertEqual("FAIL", report["checks"]["tone_screen"]["result"])
        Image.new("RGB", (128, 128), (80, 80, 80)).save(self.root / self.name)
        report, _ = self.run_qa(seamless=True)
        self.assertEqual("PASS", report["checks"]["repeated_motif_screen"]["result"])
        self.assertEqual("REVIEW_REQUIRED", report["assessments"]["repetition_quality"]["result"])

    def test_budget_and_transparency_and_nonseamless(self):
        Image.new("RGBA", (768, 768), (55, 80, 90, 100)).save(self.root / self.name)
        report, _ = self.run_qa(profile_id="competitive-clean")
        self.assertEqual("FAIL", report["checks"]["texture_budget"]["result"])
        self.assertEqual("REVIEW_REQUIRED", report["checks"]["transparency"]["result"])
        self.assertEqual("NOT_APPLICABLE", report["checks"]["edge_screen"]["result"])

    def test_traversal_and_human_approval_claim_rejected(self):
        for name in ("../outside.png", "outputs/../tile.png", "C:/outside.png"):
            with self.assertRaises(QAError):
                self.run_qa(name)
        req = self.request()
        req["approval"]["status"] = "qc_passed"
        report, _ = self.run_qa(request=req, seamless=True)
        self.assertEqual("FAIL", report["checks"]["asset_metadata"]["result"])
        req = self.request()
        req["quality_gates"]["tiling"] = {"result": "pass", "evidence": ["claimed"], "reviewer": "made-up"}
        report, _ = self.run_qa(request=req, seamless=True)
        self.assertEqual("FAIL", report["checks"]["asset_metadata"]["result"])
        self.assertEqual("pending", report["registry_gate_claims"]["tiling"]["result"])

    def test_cli_dry_run_batch_is_reproducible_and_read_only(self):
        (self.root / "batch.json").write_text(json.dumps([self.name, "outputs/missing.png"]))
        args = [sys.executable, str(ROOT / "tool/validate_texture.py"), "--root", str(self.root),
                "--profile", "adventure-fantasy", "--batch", "batch.json", "--dry-run"]
        first = subprocess.run(args, text=True, capture_output=True)
        second = subprocess.run(args, text=True, capture_output=True)
        self.assertEqual(1, first.returncode, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(2, len(first.stdout.splitlines()))
        self.assertFalse((self.root / "registry/events.jsonl").exists())
        self.assertFalse((self.root / "registry/evidence/texture-qa").exists())

    def test_historical_stone_regressions_are_not_auto_approved(self):
        original, _ = evaluate(ROOT, "7c1a96f1_000.png", "adventure-fantasy", seamless=True)
        corrected, _ = evaluate(ROOT, "workflows/textures/stone-seamless-v4.png", "adventure-fantasy", seamless=True)
        baseline = json.loads((ROOT / "stone-texture-seam-evidence.json").read_text())
        v4 = json.loads((ROOT / "workflows/textures/stone-seamless-v4-metrics.json").read_text())
        self.assertEqual(baseline["source_sha256"], original["source_sha256"])
        for report, prior in ((original, baseline["raw"]), (corrected, v4["candidate_raw"])):
            vertical = prior.get("vertical_seam_to_neighbor_mean_ratio", prior.get("vertical_join_ratio"))
            horizontal = prior.get("horizontal_seam_to_neighbor_mean_ratio", prior.get("horizontal_join_ratio"))
            self.assertEqual(vertical, report["metrics"]["raw_edges"]["vertical_ratio"])
            self.assertEqual(horizontal, report["metrics"]["raw_edges"]["horizontal_ratio"])
            self.assertEqual("REVIEW_REQUIRED", report["assessments"]["visual_seamlessness"]["result"])
        self.assertEqual("FAIL", original["checks"]["edge_screen"]["result"])
        self.assertEqual("PASS", corrected["checks"]["edge_screen"]["result"])
        self.assertEqual("FAIL", corrected["checks"]["texture_budget"]["result"])
        self.assertEqual([3072, 3072], corrected["metrics"]["preview_dimensions"]["3x3"])


if __name__ == "__main__":
    unittest.main()
