"""B3 tests use a fake ComfyUI and temporary projects; no real generation."""

import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
import b3_postprocess  # noqa: E402
import generate_asset  # noqa: E402
import image_generation  # noqa: E402
from asset_registry import Registry  # noqa: E402
from image_generation import (  # noqa: E402
    ComfyProtocolError,
    ComfyUnavailable,
    GenerationJobError,
    GenerationTimeout,
    OutputVerificationError,
    RequestValidationError,
    WorkflowValidationError,
    dry_run_report,
    execute_generation,
    prepare_request,
)


MODELS = {
    "unet": "flux3_image_klein_sd_int8_convrot.safetensors",
    "clip": "qwen3vl_4b_int8_convrot.safetensors",
    "vae": "flux2-vae.safetensors",
}


def object_info(api_node=False, omit=None):
    info = {
        "UNETLoader": {"input": {"required": {"unet_name": [[MODELS["unet"]]]}}},
        "CLIPLoader": {"input": {"required": {
            "clip_name": [[MODELS["clip"]]],
            "type": [["flux3", "flux2"]],
        }}},
        "VAELoader": {"input": {"required": {"vae_name": [[MODELS["vae"]]]}}},
        "CLIPTextEncode": {"input": {"required": {"text": ["STRING"], "clip": ["CLIP"]}}},
        "EmptyFlux2LatentImage": {"input": {"required": {
            "width": ["INT", {"min": 16, "max": 4096, "step": 16}],
            "height": ["INT", {"min": 16, "max": 4096, "step": 16}],
            "batch_size": ["INT", {"min": 1, "max": 16}],
        }}},
        "KSampler": {"input": {"required": {
            "seed": ["INT", {"max": 18446744073709551615}],
            "steps": ["INT", {"min": 1, "max": 10000}],
            "cfg": ["FLOAT", {"min": 0.0, "max": 100.0}],
            "sampler_name": [["euler", "dpmpp_2m"]],
            "scheduler": [["simple", "normal"]],
        }}},
        "VAEDecode": {"input": {"required": {"samples": ["LATENT"], "vae": ["VAE"]}}},
        "SaveImage": {"input": {"required": {
            "images": ["IMAGE"], "filename_prefix": ["STRING"]}}},
    }
    if api_node:
        info["CLIPTextEncode"]["api_node"] = True
    if omit:
        info.pop(omit, None)
    return info


def make_png(size=(128, 128), pattern="noise"):
    if pattern == "gradient":
        column = np.linspace(0, 255, size[0], dtype=np.uint8)[None, :, None]
        pixels = np.repeat(np.repeat(column, size[1], axis=0), 3, axis=2)
    elif pattern == "flat":
        pixels = np.full((size[1], size[0], 3), 128, dtype=np.uint8)
    else:
        rng = np.random.default_rng(20261018)
        pixels = rng.integers(0, 256, (size[1], size[0], 3), dtype=np.uint8)
    image = Image.fromarray(pixels, mode="RGB")
    stream = io.BytesIO()
    image.save(stream, format="PNG", optimize=True)
    return stream.getvalue()


class FakeComfy:
    base_url = "http://fake-comfy:8188"

    def __init__(self, *, image=None, history_mode="success", submit_response=None,
                 info=None, unavailable=False):
        self.image = image if image is not None else make_png()
        self.history_mode = history_mode
        self.submit_response = submit_response
        self.info = info if info is not None else object_info()
        self.unavailable = unavailable
        self.submitted = []
        self.cancelled = []

    def system_stats(self):
        if self.unavailable:
            raise ComfyUnavailable("fake ComfyUI unavailable")
        return {"system": {"comfyui_version": "fake-0.1"}, "devices": []}

    def object_info(self):
        if self.unavailable:
            raise ComfyUnavailable("fake ComfyUI unavailable")
        return self.info

    def submit(self, graph, client_id):
        if self.unavailable:
            raise ComfyUnavailable("fake ComfyUI unavailable")
        self.submitted.append({"graph": deepcopy(graph), "client_id": client_id})
        if self.submit_response is not None:
            return self.submit_response
        return {"prompt_id": "fake-prompt-0001", "number": 7}

    def _entry(self, prompt_id):
        if self.history_mode == "timeout":
            return None
        if self.history_mode == "error":
            return {
                "outputs": {},
                "status": {"status_str": "error", "completed": True,
                           "messages": [["execution_error", {"timestamp": 2}]]},
            }
        return {
            "outputs": {"9": {"images": [{
                "filename": "fake_00001_.png", "subfolder": "", "type": "output",
                "metadata": {"kind": "image", "width": 128, "height": 128},
            }]}},
            "status": {"status_str": "success", "completed": True,
                       "messages": [["execution_start", {"prompt_id": prompt_id,
                                                         "timestamp": 1000}],
                                    ["execution_success", {"prompt_id": prompt_id,
                                                           "timestamp": 2000}]]},
        }

    def history(self, prompt_id):
        return self._entry(prompt_id)

    def view(self, filename, subfolder="", image_type="output"):
        return self.image

    def cancel(self, prompt_id):
        self.cancelled.append(prompt_id)
        return {"prompt_id": prompt_id, "interrupted": True}


class ImageGenerationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        for folder in ("art/schemas", "art/presets", "art/requests", "art/games",
                       "registry/evidence", "registry/staging", "outputs", "workflows/flux3"):
            (self.root / folder).mkdir(parents=True)
        for name in ("asset-request", "style-profile", "generation-request"):
            shutil.copy2(ROOT / f"art/schemas/{name}.schema.json", self.root / "art/schemas")
        shutil.copy2(ROOT / "art/presets/adventure-fantasy.json", self.root / "art/presets")
        shutil.copy2(ROOT / "flux3-stone-workflow.json", self.root / "flux3-stone-workflow.json")
        shutil.copy2(ROOT / "workflows/flux3/workflow-catalog.json",
                     self.root / "workflows/flux3/workflow-catalog.json")
        self.request_path = "art/requests/b3-test-0001.json"
        self.write_request()

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content.encode() if isinstance(content, str) else content)
        return path

    def base_request(self, **updates):
        request = {
            "schema_version": "1.0",
            "id": "b3-test-0001",
            "mode": "experimental",
            "asset_type": "image",
            "description": "Synthetic integration fixture, not a game asset.",
            "roblox_usage": "Synthetic test image, not uploaded.",
            "style": {"kind": "preset", "profile_id": "adventure-fantasy"},
            "prompt": {"subject": "A stylized stone surface.",
                       "details": ["Readable shapes", "Stylized blue-gray palette."],
                       "negative": "text, watermark"},
            "delivery": {"width_px": 128, "height_px": 128, "format": "png",
                         "tiling_required": False},
            "generation": {"workflow_version": "flux3-klein-v1", "seed": 42},
            "output": {"directory": "outputs/generated/b3-test-0001",
                       "workflow_path": "workflows/generated/b3-test-0001/workflow.json"},
            "quality": {"b2_qa": True, "postprocess": {"seamless": "none",
                                                        "optimize_png": "none"}},
        }
        request.update(updates)
        return request

    def write_request(self, request=None):
        self.write(self.request_path, json.dumps(request or self.base_request()))

    def cleanup_failed_run(self, prepared):
        for name in (prepared.staging_dir,
                     PurePosixPath(prepared.workflow_path).parent.as_posix(),
                     prepared.request["output"]["directory"]):
            path = self.root / name
            if path.exists():
                shutil.rmtree(path)

    def test_end_to_end_generation_qa_and_staging(self):
        before_reference = image_generation.sha256_file(self.root / "flux3-stone-workflow.json")
        fake = FakeComfy()
        prepared = prepare_request(self.root, self.request_path)
        result = execute_generation(prepared, fake)
        image = self.root / result["output"]["path"]
        self.assertTrue(image.is_file())
        self.assertEqual(image_generation.sha256_file(image), result["output"]["sha256"])
        self.assertEqual("PNG", result["output"]["format"])
        self.assertEqual((128, 128), (result["output"]["width"], result["output"]["height"]))
        self.assertEqual("fake-prompt-0001", result["generation"]["prompt_id"])
        self.assertEqual(7, result["generation"]["comfy_number"])
        self.assertEqual("REVIEW_REQUIRED", result["qa"][0]["overall_result"])
        self.assertTrue((self.root / result["qa"][0]["evidence"]["json"]).is_file())
        self.assertTrue((self.root / result["qa"][0]["evidence"]["markdown"]).is_file())
        staging = self.root / prepared.staging_dir
        self.assertTrue((staging / "request.json").is_file())
        self.assertTrue((staging / "b1-draft-request.json").is_file())
        self.assertTrue((staging / "result.json").is_file())
        self.assertTrue((staging / "b1-generated-payload.json").is_file())
        draft = json.loads((staging / "b1-draft-request.json").read_text())
        self.assertEqual("draft", draft["approval"]["status"])
        self.assertTrue(all(gate == {"result": "pending", "evidence": []}
                            for gate in draft["quality_gates"].values()))
        self.assertFalse((self.root / "registry/events.jsonl").exists())
        self.assertTrue(result["registry"]["unchanged"])
        self.assertEqual(before_reference,
                         image_generation.sha256_file(self.root / "flux3-stone-workflow.json"))
        self.assertEqual(1, len(fake.submitted))
        run_workflow = self.root / result["workflow"]["run_path"]
        self.assertTrue(run_workflow.is_file())
        graph = json.loads(run_workflow.read_text())
        self.assertEqual("adventure-fantasy", graph["4"]["inputs"]["text"].split("Style direction: ")[1]
                         .split(".")[0].strip().lower().replace(" ", "-"))
        self.assertIn("blue-gray", graph["4"]["inputs"]["text"])

    def test_dry_run_writes_nothing_and_does_not_submit(self):
        fake = FakeComfy()
        prepared = prepare_request(self.root, self.request_path)
        report = dry_run_report(prepared, fake, check_comfy=True)
        self.assertEqual("dry_run", report["status"])
        self.assertEqual([], fake.submitted)
        self.assertFalse((self.root / "outputs/generated/b3-test-0001").exists())
        self.assertFalse((self.root / prepared.staging_dir).exists())
        self.assertEqual("adventure-fantasy", report["profile"]["id"])

    def test_cli_dry_run_and_generation_with_fake_client(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = generate_asset.main([
                "--root", str(self.root), "--request", self.request_path,
                "--dry-run", "--no-comfy-check", "--json",
            ])
        self.assertEqual(0, code)
        self.assertEqual("dry_run", json.loads(output.getvalue())["status"])
        self.assertFalse((self.root / "outputs/generated/b3-test-0001").exists())

        fake = FakeComfy()
        output = io.StringIO()
        with mock.patch("generate_asset.ComfyUIClient", return_value=fake):
            with contextlib.redirect_stdout(output):
                code = generate_asset.main([
                    "--root", str(self.root), "--request", self.request_path, "--json",
                ])
        self.assertEqual(0, code)
        result = json.loads(output.getvalue())
        self.assertEqual("completed", result["status"])
        self.assertTrue((self.root / result["output"]["path"]).is_file())

    def test_invalid_request_schema_and_missing_reference(self):
        request = self.base_request()
        del request["generation"]["seed"]
        self.write_request(request)
        with self.assertRaises(RequestValidationError):
            prepare_request(self.root, self.request_path)
        self.write_request()
        reference = self.root / "flux3-stone-workflow.json"
        reference.write_text(reference.read_text() + "\n", encoding="utf-8")
        with self.assertRaises(WorkflowValidationError):
            prepare_request(self.root, self.request_path)

    def test_duplicate_output_path_is_rejected_before_preflight(self):
        (self.root / "outputs/generated/b3-test-0001").mkdir(parents=True)
        with self.assertRaisesRegex(RequestValidationError, "duplicate"):
            prepare_request(self.root, self.request_path)

    def test_api_node_and_missing_node_are_rejected(self):
        prepared = prepare_request(self.root, self.request_path)
        with self.assertRaisesRegex(WorkflowValidationError, "API node"):
            execute_generation(prepared, FakeComfy(info=object_info(api_node=True)))
        self.assertFalse((self.root / prepared.staging_dir).exists())
        with self.assertRaisesRegex(WorkflowValidationError, "not installed"):
            execute_generation(prepared, FakeComfy(info=object_info(omit="VAEDecode")))
        self.assertFalse((self.root / prepared.staging_dir).exists())

    def test_comfy_unavailable_does_not_write_or_submit(self):
        prepared = prepare_request(self.root, self.request_path)
        fake = FakeComfy(unavailable=True)
        with self.assertRaises(ComfyUnavailable):
            execute_generation(prepared, fake)
        self.assertEqual([], fake.submitted)
        self.assertFalse((self.root / prepared.staging_dir).exists())

    def test_malformed_submit_response_and_failed_job(self):
        prepared = prepare_request(self.root, self.request_path)
        with self.assertRaises(ComfyProtocolError):
            execute_generation(prepared, FakeComfy(submit_response={"number": 1}))
        failure = json.loads((self.root / prepared.staging_dir / "result.json").read_text())
        self.assertEqual("failed", failure["status"])
        self.assertEqual("comfy_protocol_error", failure["error"]["code"])
        self.assertFalse((self.root / prepared.image_path).exists())

        self.cleanup_failed_run(prepared)
        prepared = prepare_request(self.root, self.request_path)
        with self.assertRaises(GenerationJobError):
            execute_generation(prepared, FakeComfy(history_mode="error"))
        failure = json.loads((self.root / prepared.staging_dir / "result.json").read_text())
        self.assertEqual("generation_failed", failure["error"]["code"])
        self.assertFalse((self.root / prepared.image_path).exists())

    def test_timeout_cancels_and_preserves_failure_record(self):
        prepared = prepare_request(self.root, self.request_path)
        fake = FakeComfy(history_mode="timeout")
        with self.assertRaises(GenerationTimeout):
            execute_generation(prepared, fake, timeout_seconds=0.05, poll_interval=0.01)
        self.assertEqual(["fake-prompt-0001"], fake.cancelled)
        failure = json.loads((self.root / prepared.staging_dir / "result.json").read_text())
        self.assertEqual("generation_timeout", failure["error"]["code"])
        self.assertFalse((self.root / prepared.image_path).exists())

    def test_malformed_and_wrong_size_images_are_rejected(self):
        prepared = prepare_request(self.root, self.request_path)
        with self.assertRaises(OutputVerificationError):
            execute_generation(prepared, FakeComfy(image=b"not a png"))
        self.assertFalse((self.root / prepared.image_path).exists())
        self.cleanup_failed_run(prepared)
        prepared = prepare_request(self.root, self.request_path)
        with self.assertRaises(OutputVerificationError):
            execute_generation(prepared, FakeComfy(image=make_png((64, 64))))
        self.assertFalse((self.root / prepared.image_path).exists())

    def test_production_request_requires_an_existing_art_approved_b1_record(self):
        request = self.base_request(
            mode="production",
            style={"kind": "art_bible", "profile_id": "adventure-fantasy",
                   "game_id": "example-game", "bible_version": "1.0"},
        )
        self.write_request(request)
        with self.assertRaisesRegex(RequestValidationError, "no B1 registry record"):
            prepare_request(self.root, self.request_path)

    def create_art_approved_b1_record(self, asset_id):
        bible = self.write(
            "art/games/example-bible.md",
            "# Synthetic Art Bible\n**Game ID:** example-game\n"
            "**Style profile:** adventure-fantasy\n**Version:** 1.0\n",
        )
        bible_sha = image_generation.sha256_file(bible)
        approval = {
            "game_id": "example-game", "version": "1.0", "bible_sha256": bible_sha,
            "profile_id": "adventure-fantasy", "approved_by": "fixture-art-owner",
            "approved_on": "2026-10-17",
        }
        approval_file = self.write("registry/evidence/bible-approval.json",
                                   json.dumps(approval))
        approval_sha = image_generation.sha256_file(approval_file)
        manifest = {
            "game_id": "example-game",
            "actors": {"creators": ["fixture-maker"], "art_owners": ["fixture-art-owner"],
                       "qc_reviewers": ["fixture-qc"], "importers": ["fixture-importer"],
                       "final_reviewers": ["fixture-final"]},
            "art_bibles": [{
                "version": "1.0", "path": "art/games/example-bible.md", "sha256": bible_sha,
                "profile_id": "adventure-fantasy",
                "approval_evidence": "registry/evidence/bible-approval.json",
                "approval_evidence_sha256": approval_sha,
                "approved_by": "fixture-art-owner", "approved_on": "2026-10-17",
            }],
        }
        self.write("art/games/example-game.json", json.dumps(manifest))
        b1_request = {
            "schema_version": "1.0", "id": asset_id, "asset_type": "image",
            "game_id": "example-game", "style_profile_id": "adventure-fantasy",
            "description": "Synthetic production fixture.", "roblox_usage": "Synthetic only.",
            "delivery": {"width_px": 128, "height_px": 128, "format": "png",
                         "tiling_required": False},
            "generation": {"model": MODELS["unet"],
                           "workflow": f"workflows/generated/{asset_id}/workflow.json",
                           "method": "local_ai", "seed": 42},
            "provenance": {"source": "Synthetic fixture", "license": "Synthetic fixture",
                           "derivations": []},
            "quality_gates": {name: {"result": "pending", "evidence": []} for name in
                              ("originality", "rights", "style", "technical", "performance",
                               "tiling", "in_engine")},
            "approval": {"status": "draft"},
        }
        registry = Registry(self.root)
        registry.apply("create", asset_id, "fixture-maker", {"request": b1_request})
        registry.apply("art_approved", asset_id, "fixture-art-owner", {
            "bible_version": "1.0", "bible_sha256": bible_sha,
            "approval_evidence_sha256": approval_sha,
        })
        return b1_request

    def test_production_uses_existing_art_approved_b1_record_without_writing_events(self):
        asset_id = "b3-test-prod-0001"
        self.create_art_approved_b1_record(asset_id)
        request = self.base_request(
            id=asset_id,
            mode="production",
            style={"kind": "art_bible", "profile_id": "adventure-fantasy",
                   "game_id": "example-game", "bible_version": "1.0"},
            output={"directory": f"outputs/generated/{asset_id}",
                    "workflow_path": f"workflows/generated/{asset_id}/workflow.json"},
        )
        self.write("art/requests/b3-test-prod-0001.json", json.dumps(request))
        prepared = prepare_request(self.root, "art/requests/b3-test-prod-0001.json")
        self.assertEqual("existing B1 registry record", prepared.b1_request_origin)
        self.assertEqual(2, prepared.registry_event_count)
        result = execute_generation(prepared, FakeComfy())
        self.assertEqual("art_approved", result["b1"]["record_status"])
        self.assertEqual(2, result["registry"]["event_count_after"])
        self.assertTrue(result["registry"]["unchanged"])
        self.assertTrue(result["approval_basis"]["production_request"])
        self.assertEqual("not_approved", result["approval_status"])
        self.assertFalse(result["b1"]["registry_events_written"])

    def test_auto_seamless_derivative_and_new_only_writes(self):
        request = self.base_request(
            asset_type="tileable_texture",
            delivery={"width_px": 128, "height_px": 128, "format": "png",
                      "tiling_required": True},
            quality={"b2_qa": True,
                     "postprocess": {"seamless": "auto", "optimize_png": "none"}},
        )
        self.write_request(request)
        prepared = prepare_request(self.root, self.request_path)
        result = execute_generation(prepared, FakeComfy(image=make_png(pattern="gradient")))
        self.assertEqual(2, len(result["qa"]))
        self.assertEqual("seamless", result["qa"][1]["role"])
        derived = self.root / result["qa"][1]["path"]
        self.assertTrue(derived.is_file())
        self.assertEqual(1, len(result["postprocess"]))
        self.assertEqual("generic_wrap_blend", result["postprocess"][0]["method"])
        with self.assertRaisesRegex(b3_postprocess.PostprocessError, "overwrite"):
            b3_postprocess.generic_wrap_blend(
                self.root / result["output"]["path"], derived,
            )

    def test_lossless_optimize_is_pixel_identical_and_new_only(self):
        source = self.root / "outputs/source.png"
        source.write_bytes(make_png())
        destination = self.root / "outputs/source-optimized.png"
        detail = b3_postprocess.lossless_optimize(source, destination)
        self.assertTrue(detail["pixel_identical"])
        with Image.open(source) as original, Image.open(destination) as optimized:
            self.assertEqual(original.tobytes(), optimized.tobytes())
        with self.assertRaisesRegex(b3_postprocess.PostprocessError, "overwrite"):
            b3_postprocess.lossless_optimize(source, destination)

    def test_prompt_builder_uses_profile_and_records_negative(self):
        prepared = prepare_request(self.root, self.request_path)
        self.assertIn("Adventure Fantasy", prepared.positive_prompt)
        self.assertIn("Palette anchored", prepared.positive_prompt)
        self.assertEqual("text, watermark", prepared.negative_prompt)
        self.assertTrue(any("CFG 1.0" in warning for warning in prepared.warnings))
        self.assertTrue(any("Experimental baseline" in warning for warning in prepared.warnings))


if __name__ == "__main__":
    unittest.main()
