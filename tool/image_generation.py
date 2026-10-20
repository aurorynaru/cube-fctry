"""Milestone B3 local image generation through ComfyUI.

This module validates a B3 generation request, builds a style-aware prompt,
writes a parameterized copy of the pinned reference workflow, submits it to a
local ComfyUI instance, verifies the returned PNG, runs B2 texture QA, and
writes candidate provenance under registry/staging/b3/.

It never appends a B1 registry event, never claims human approval, and never
calls a paid/partner API node.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
import colorsys
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from PIL import Image, UnidentifiedImageError
from jsonschema import Draft202012Validator, FormatChecker

import b3_postprocess
import texture_qa
from asset_registry import Registry, RegistryError


ROOT = Path(__file__).resolve().parents[1]
REQUEST_SCHEMA = "art/schemas/generation-request.schema.json"
CATALOG_PATH = "workflows/flux3/workflow-catalog.json"
STAGING_ROOT = "registry/staging/b3"
EVIDENCE_ROOT = "registry/evidence/texture-qa-b3"
DEFAULT_BASE_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class GenerationError(ValueError):
    code = "generation_error"

    def __init__(self, message, detail=None):
        super().__init__(message)
        self.detail = detail

    def as_dict(self):
        return {"code": self.code, "message": str(self), "detail": self.detail}


class RequestValidationError(GenerationError):
    code = "invalid_request"


class ComfyUnavailable(GenerationError):
    code = "comfy_unavailable"


class ComfyProtocolError(GenerationError):
    code = "comfy_protocol_error"


class WorkflowValidationError(GenerationError):
    code = "workflow_invalid"


class GenerationJobError(GenerationError):
    code = "generation_failed"


class GenerationTimeout(GenerationError):
    code = "generation_timeout"


class OutputVerificationError(GenerationError):
    code = "output_invalid"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        raise RequestValidationError(f"refusing to overwrite existing path: {path}")
    with path.open("xb") as stream:
        stream.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def _json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _project_relative(root, name, *, must_exist=False):
    """Resolve a project-relative POSIX path without allowing escapes."""
    if not isinstance(name, str) or not name or "\\" in name or ":" in name:
        raise RequestValidationError(f"unsafe project path: {name!r}")
    pure = PurePosixPath(name)
    if pure.is_absolute() or any(part in ("", ".", "..") for part in pure.parts):
        raise RequestValidationError(f"unsafe project path: {name!r}")
    if pure.as_posix() != name:
        raise RequestValidationError(f"path must use project-relative POSIX form: {name!r}")
    root = Path(root).resolve()
    path = root / pure
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise RequestValidationError(f"escaping project path: {name!r}")
    if path.is_symlink():
        raise RequestValidationError(f"symlink path refused: {name!r}")
    if must_exist and not resolved.is_file():
        raise RequestValidationError(f"missing file: {name}")
    return path


def _path_from_argument(root, value):
    root = Path(root).resolve()
    path = Path(value)
    if not path.is_absolute():
        path = root / path
    path = path.resolve()
    if not path.is_relative_to(root):
        raise RequestValidationError("request file must be inside the project")
    if not path.is_file():
        raise RequestValidationError(f"request file not found: {value}")
    return path, path.relative_to(root).as_posix()


def _json_load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise RequestValidationError(f"invalid JSON: {path}: {exc}") from exc


def _combo(spec):
    if not isinstance(spec, list) or not spec:
        return None
    return spec[0] if isinstance(spec[0], list) else None


def _field_spec(object_info, node_class, field_name):
    node = object_info.get(node_class) if isinstance(object_info, dict) else None
    if not isinstance(node, dict):
        return None
    return node.get("input", {}).get("required", {}).get(field_name)


def _int_options(spec):
    if not isinstance(spec, list) or len(spec) < 2 or not isinstance(spec[1], dict):
        return {}
    return spec[1]


def color_name(value):
    """Human-readable deterministic color label for profile palette values."""
    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return "unspecified color"
    red, green, blue = (int(value[index:index + 2], 16) / 255 for index in (0, 2, 4))
    hue, saturation, brightness = colorsys.rgb_to_hsv(red, green, blue)
    hue *= 360
    if saturation < 0.12:
        return ("near-black" if brightness < 0.2 else "charcoal" if brightness < 0.35
                else "stone grey" if brightness < 0.65 else "pale grey" if brightness < 0.9
                else "off-white")
    if 20 <= hue <= 50 and saturation < 0.42:
        return ("warm brown-grey" if brightness < 0.45 else
                "warm stone grey" if brightness < 0.65 else "pale sand")
    base = ("red" if hue < 15 or hue >= 345 else "orange" if hue < 40 else
            "amber" if hue < 60 else "yellow-green" if hue < 85 else "green" if hue < 150 else
            "teal" if hue < 190 else "blue" if hue < 220 else "indigo" if hue < 250 else
            "violet" if hue < 290 else "magenta" if hue < 330 else "rose")
    if brightness < 0.25:
        return f"dark {base}"
    if brightness < 0.4:
        return f"deep {base}"
    if saturation < 0.3:
        return f"muted {base}"
    if brightness > 0.82 and saturation < 0.55:
        return f"pale {base}"
    return base


def _palette_phrase(profile):
    palette = profile["palette"]
    base = [f"{color_name(color)} ({color})" for color in palette["base"][:3]]
    accent = [f"{color_name(color)} ({color})" for color in palette["accent"][:2]]
    phrase = "Palette anchored in " + ", ".join(base)
    if accent:
        phrase += ", with " + " and ".join(accent) + " accents"
    return phrase + "."


def build_prompt(request, profile, workflow_spec):
    """Build an original, style-aware positive prompt from the selected profile."""
    details = [item.strip() for item in request["prompt"].get("details", []) if item.strip()]
    pieces = [request["prompt"]["subject"].strip().rstrip(".") + "."]
    if details:
        pieces.append(" ".join(item.rstrip(".") + "." for item in details))
    pieces.append(f"Intended Roblox use: {request['roblox_usage'].strip().rstrip('.')}.")
    pieces.append(
        f"Style direction: {profile['name']}. {profile['materials']['surfaces'].strip()} "
        f"Surface detail rule: {profile['materials']['texture_rule'].strip()}"
    )
    pieces.append(_palette_phrase(profile))
    pieces.append(f"Lighting and material response: {profile['lighting'].strip()}")
    if request["delivery"]["tiling_required"]:
        pieces.append(
            "Tiling requirement: an edge-to-edge repeating texture with no visible border, "
            "frame or vignette. " + profile["materials"]["tiling_rule"].strip()
        )
    if request["asset_type"] == "tileable_texture":
        pieces.append("This is a flat albedo material texture, not a scene mockup or a perspective render.")
    else:
        pieces.append(f"This is a Roblox {request['asset_type']} image, not a scene mockup.")
    pieces.append(f"Originality: {profile['originality'].strip()}")
    pieces.append(
        "Avoid recognizable existing games, brands, characters, logos, watermarks, readable text "
        "and copied compositions."
    )
    positive = " ".join(" ".join(pieces).split())
    negative = request["prompt"].get("negative", "").strip()
    if len(positive) > 6000:
        raise RequestValidationError("generated positive prompt exceeds 6000 characters")
    if len(negative) > 3000:
        raise RequestValidationError("negative prompt exceeds 3000 characters")
    return positive, negative


def load_catalog(root):
    root = Path(root).resolve()
    path = _project_relative(root, CATALOG_PATH, must_exist=True)
    catalog = _json_load(path)
    if catalog.get("schema_version") != "1.0" or not isinstance(catalog.get("workflows"), dict):
        raise RequestValidationError("workflow catalog has an unsupported shape")
    return catalog, path, sha256_file(path)


def _workflow_spec(catalog, version):
    workflows = catalog.get("workflows", {})
    if version not in workflows:
        raise RequestValidationError(f"unknown workflow version: {version}")
    spec = workflows[version]
    required = ("reference_path", "reference_sha256", "nodes", "allowed_classes", "models",
                "sampling", "resolution")
    if not isinstance(spec, dict) or any(key not in spec for key in required):
        raise RequestValidationError(f"workflow catalog entry incomplete: {version}")
    return spec


def verify_reference_workflow(root, spec):
    root = Path(root).resolve()
    reference = _project_relative(root, spec["reference_path"], must_exist=True)
    reference_sha = sha256_file(reference)
    if reference_sha != spec["reference_sha256"]:
        raise WorkflowValidationError(
            "reference workflow hash changed; refusing to parameterize a modified graph",
            {"expected": spec["reference_sha256"], "actual": reference_sha},
        )
    graph = _json_load(reference)
    if not isinstance(graph, dict) or not graph:
        raise WorkflowValidationError("reference workflow is not an API-format object")
    verify_workflow_structure(graph, spec)
    return graph, reference, reference_sha


def verify_workflow_structure(graph, spec):
    if not isinstance(graph, dict):
        raise WorkflowValidationError("workflow must be a JSON object")
    nodes = spec["nodes"]
    for label, node_id in nodes.items():
        node = graph.get(node_id)
        if not isinstance(node, dict) or "class_type" not in node:
            raise WorkflowValidationError(f"workflow node {node_id} ({label}) is missing")
    expected = {
        nodes["positive"]: "CLIPTextEncode",
        nodes["negative"]: "CLIPTextEncode",
        nodes["latent"]: "EmptyFlux2LatentImage",
        nodes["sampler"]: "KSampler",
        nodes["save"]: "SaveImage",
    }
    for node_id, class_type in expected.items():
        if graph[node_id].get("class_type") != class_type:
            raise WorkflowValidationError(f"node {node_id} is not {class_type}")
    allowed = set(spec["allowed_classes"])
    unexpected = sorted({node.get("class_type") for node in graph.values()
                         if isinstance(node, dict) and node.get("class_type") not in allowed})
    if unexpected:
        raise WorkflowValidationError("workflow contains unapproved node classes", unexpected)
    for node_id, node in graph.items():
        inputs = node.get("inputs", {})
        if not isinstance(inputs, dict):
            raise WorkflowValidationError(f"node {node_id} inputs are malformed")
        for value in inputs.values():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                if value[0] not in graph:
                    raise WorkflowValidationError(f"node {node_id} links to missing node {value[0]}")


def parameterize_graph(reference, spec, *, positive, negative, width, height, seed, request_id):
    graph = deepcopy(reference)
    nodes = spec["nodes"]
    graph[nodes["positive"]]["inputs"]["text"] = positive
    graph[nodes["negative"]]["inputs"]["text"] = negative
    graph[nodes["latent"]]["inputs"].update(width=width, height=height,
                                            batch_size=spec["sampling"]["batch_size"])
    graph[nodes["sampler"]]["inputs"].update(
        seed=seed,
        steps=spec["sampling"]["steps"],
        cfg=spec["sampling"]["cfg"],
        sampler_name=spec["sampling"]["sampler_name"],
        scheduler=spec["sampling"]["scheduler"],
        denoise=spec["sampling"]["denoise"],
    )
    graph[nodes["save"]]["inputs"]["filename_prefix"] = f"b3-{request_id}"
    verify_workflow_structure(graph, spec)
    return graph


def verify_workflow_against_installation(graph, spec, object_info):
    """Reject missing nodes, paid/partner API nodes, and unavailable models."""
    if not isinstance(object_info, dict) or not object_info:
        raise ComfyProtocolError("object_info is empty or malformed")
    allowed = set(spec["allowed_classes"])
    checks = []
    for node_id, node in graph.items():
        class_type = node.get("class_type")
        if class_type not in allowed:
            raise WorkflowValidationError(f"node {node_id} class is not allowed: {class_type}")
        installed = object_info.get(class_type)
        if not isinstance(installed, dict):
            raise WorkflowValidationError(f"node class is not installed: {class_type}")
        if installed.get("api_node") is True:
            raise WorkflowValidationError(
                f"paid/partner API node is forbidden: {class_type}", {"node_id": node_id}
            )
        checks.append({"node_id": node_id, "class_type": class_type, "api_node": False})
    models = spec["models"]
    model_fields = (
        ("UNETLoader", "unet_name", models["unet"]),
        ("CLIPLoader", "clip_name", models["clip"]),
        ("VAELoader", "vae_name", models["vae"]),
    )
    for class_type, field_name, expected in model_fields:
        spec_field = _field_spec(object_info, class_type, field_name)
        options = _combo(spec_field)
        if options is None or expected not in options:
            raise WorkflowValidationError(f"installed {class_type}.{field_name} does not offer {expected}")
    clip_type = _combo(_field_spec(object_info, "CLIPLoader", "type"))
    if clip_type is None or models["clip_type"] not in clip_type:
        raise WorkflowValidationError(f"CLIPLoader does not offer type {models['clip_type']}")
    sampler_enum = _combo(_field_spec(object_info, "KSampler", "sampler_name"))
    scheduler_enum = _combo(_field_spec(object_info, "KSampler", "scheduler"))
    if sampler_enum is None or spec["sampling"]["sampler_name"] not in sampler_enum:
        raise WorkflowValidationError("configured sampler is unavailable")
    if scheduler_enum is None or spec["sampling"]["scheduler"] not in scheduler_enum:
        raise WorkflowValidationError("configured scheduler is unavailable")
    latent_width = _int_options(_field_spec(object_info, "EmptyFlux2LatentImage", "width"))
    latent_height = _int_options(_field_spec(object_info, "EmptyFlux2LatentImage", "height"))
    for axis, options in (("width", latent_width), ("height", latent_height)):
        value = graph[spec["nodes"]["latent"]]["inputs"][axis]
        if "min" in options and value < options["min"]:
            raise WorkflowValidationError(f"requested {axis} is below the latent node minimum")
        if "max" in options and value > options["max"]:
            raise WorkflowValidationError(f"requested {axis} is above the latent node maximum")
        if "step" in options and value % options["step"]:
            raise WorkflowValidationError(f"requested {axis} is not a multiple of {options['step']}")
    sampler_seed = _int_options(_field_spec(object_info, "KSampler", "seed"))
    seed = graph[spec["nodes"]["sampler"]]["inputs"]["seed"]
    if seed > sampler_seed.get("max", seed):
        raise WorkflowValidationError("seed exceeds the KSampler maximum")
    return {
        "checked_nodes": len(graph),
        "allowed_classes": sorted(allowed),
        "models": models,
        "api_nodes_rejected": 0,
        "node_checks": checks,
    }


class ComfyUIClient:
    """Minimal local ComfyUI HTTP client. No cloud/partner endpoints are used."""

    def __init__(self, base_url=DEFAULT_BASE_URL, timeout=15.0, poll_interval=1.0):
        self.base_url = str(base_url).rstrip("/")
        self.timeout = float(timeout)
        self.poll_interval = float(poll_interval)
        if not re.fullmatch(r"https?://[^\s/]+", self.base_url):
            raise RequestValidationError(f"invalid ComfyUI URL: {base_url}")

    def _request(self, method, path, payload=None, timeout=None):
        url = self.base_url + path
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
                body = response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read()[:2000].decode("utf-8", "replace")
            raise ComfyProtocolError(f"ComfyUI HTTP {exc.code} for {path}", detail) from exc
        except (urllib.error.URLError, socket.timeout, TimeoutError, ConnectionError, OSError) as exc:
            raise ComfyUnavailable(f"ComfyUI unavailable at {self.base_url}: {exc}") from exc
        return body

    def _json(self, method, path, payload=None, timeout=None):
        body = self._request(method, path, payload=payload, timeout=timeout)
        try:
            value = json.loads(body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ComfyProtocolError(f"malformed JSON from {path}") from exc
        if not isinstance(value, (dict, list)):
            raise ComfyProtocolError(f"unexpected JSON shape from {path}")
        return value

    def system_stats(self):
        value = self._json("GET", "/system_stats")
        if not isinstance(value, dict):
            raise ComfyProtocolError("system_stats is not an object")
        return value

    def object_info(self):
        value = self._json("GET", "/object_info", timeout=max(self.timeout, 60.0))
        if not isinstance(value, dict) or not value:
            raise ComfyProtocolError("object_info is empty or not an object")
        return value

    def submit(self, graph, client_id):
        value = self._json("POST", "/prompt", {"prompt": graph, "client_id": client_id})
        if not isinstance(value, dict):
            raise ComfyProtocolError("prompt submission response is not an object")
        if value.get("node_errors"):
            raise GenerationJobError("ComfyUI rejected the workflow", value["node_errors"])
        prompt_id = value.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyProtocolError("prompt submission response has no prompt_id", value)
        return value

    def history(self, prompt_id):
        value = self._json("GET", "/history/" + urllib.parse.quote(prompt_id, safe=""))
        if not isinstance(value, dict):
            raise ComfyProtocolError("history response is not an object")
        entry = value.get(prompt_id)
        if entry is None:
            return None
        if not isinstance(entry, dict):
            raise ComfyProtocolError("history entry is not an object")
        return entry

    def view(self, filename, subfolder="", image_type="output"):
        query = urllib.parse.urlencode({"filename": filename, "subfolder": subfolder,
                                        "type": image_type})
        return self._request("GET", "/view?" + query, timeout=max(self.timeout, 60.0))

    def queue(self):
        value = self._json("GET", "/queue")
        if not isinstance(value, dict):
            raise ComfyProtocolError("queue response is not an object")
        return value

    def cancel(self, prompt_id):
        """Best-effort cancel without interrupting an unrelated job."""
        result = {"prompt_id": prompt_id, "queued_delete": False, "interrupt_sent": False}
        try:
            queue = self.queue()
            running = [item[1] for item in queue.get("queue_running", [])
                       if isinstance(item, list) and len(item) > 1]
            pending = [item[1] for item in queue.get("queue_pending", [])
                       if isinstance(item, list) and len(item) > 1]
            if prompt_id in pending:
                self._request("POST", "/queue", {"delete": [prompt_id]})
                result["queued_delete"] = True
            if prompt_id in running:
                self._request("POST", "/interrupt", {})
                result["interrupt_sent"] = True
        except GenerationError as exc:
            result["error"] = str(exc)
        return result


@dataclass
class PreparedRequest:
    root: Path
    request_path: str
    request: dict
    request_bytes: bytes
    request_sha256: str
    profile: dict
    profile_path: str
    profile_sha256: str
    catalog: dict
    catalog_path: str
    catalog_sha256: str
    workflow_version: str
    workflow_spec: dict
    reference_path: str
    reference_sha256: str
    graph: dict
    positive_prompt: str
    negative_prompt: str
    prompt_sha256: str
    image_path: str
    workflow_path: str
    staging_dir: str
    qa_dir: str
    b1_request: dict
    b1_request_origin: str
    b1_record: dict | None
    approval_basis: dict
    warnings: list = field(default_factory=list)
    registry_event_count: int = 0
    registry_journal_sha256: str | None = None

    @property
    def request_id(self):
        return self.request["id"]

    @property
    def tiling(self):
        return self.request["delivery"]["tiling_required"]

    def summary(self):
        return {
            "schema_version": "1.0",
            "valid": True,
            "request_id": self.request_id,
            "mode": self.request["mode"],
            "asset_type": self.request["asset_type"],
            "approval_basis": self.approval_basis,
            "profile": {
                "id": self.profile["id"],
                "path": self.profile_path,
                "sha256": self.profile_sha256,
                "schema_version": self.profile["schema_version"],
                "budgets": self.profile["budgets"],
            },
            "workflow": {
                "version": self.workflow_version,
                "catalog_path": self.catalog_path,
                "catalog_sha256": self.catalog_sha256,
                "reference_path": self.reference_path,
                "reference_sha256": self.reference_sha256,
                "run_path": self.workflow_path,
                "prompt_sha256": self.prompt_sha256,
            },
            "prompt": {
                "positive": self.positive_prompt,
                "negative": self.negative_prompt,
                "negative_effective": self.workflow_spec.get("negative_prompt_effective", False),
            },
            "generation": {
                "workflow_version": self.workflow_version,
                "seed": self.request["generation"]["seed"],
                "steps": self.workflow_spec["sampling"]["steps"],
                "cfg": self.workflow_spec["sampling"]["cfg"],
                "sampler": self.workflow_spec["sampling"]["sampler_name"],
                "scheduler": self.workflow_spec["sampling"]["scheduler"],
                "width_px": self.request["delivery"]["width_px"],
                "height_px": self.request["delivery"]["height_px"],
            },
            "planned": {
                "image": self.image_path,
                "workflow": self.workflow_path,
                "staging": self.staging_dir,
                "qa_evidence": self.qa_dir,
            },
            "b1": {
                "request_origin": self.b1_request_origin,
                "staged_or_referenced": ("registry/events.jsonl" if self.b1_record
                                         else f"{self.staging_dir}/b1-draft-request.json"),
                "record_status": (self.b1_record["request"]["approval"]["status"]
                                  if self.b1_record else "not registered"),
                "registry_events_written": False,
            },
            "warnings": self.warnings,
        }


def _validate_no_collisions(root, prepared):
    root = Path(root).resolve()
    planned = (
        (prepared.request["output"]["directory"], "output directory"),
        (prepared.image_path, "image output"),
        (prepared.workflow_path, "workflow copy"),
        (PurePosixPath(prepared.workflow_path).parent.as_posix(), "workflow directory"),
        (prepared.staging_dir, "staging directory"),
        (prepared.qa_dir, "QA evidence directory"),
    )
    for name, label in planned:
        path = _project_relative(root, name)
        if path.exists():
            raise RequestValidationError(f"duplicate {label} path already exists: {name}")
    output_dir = Path(prepared.request["output"]["directory"])
    workflow_dir = PurePosixPath(prepared.workflow_path).parent
    if output_dir.name != workflow_dir.name:
        raise RequestValidationError(
            "output directory and workflow directory must use the same run folder name"
        )


def _b1_request(request, profile, workflow_spec, workflow_path):
    gates = {name: {"result": "pending", "evidence": []} for name in
             ("originality", "rights", "style", "technical", "performance", "tiling", "in_engine")}
    return {
        "schema_version": "1.0",
        "id": request["id"],
        "asset_type": request["asset_type"],
        "game_id": "b3-experimental",
        "style_profile_id": profile["id"],
        "description": request["description"],
        "roblox_usage": request["roblox_usage"],
        "delivery": {
            "width_px": request["delivery"]["width_px"],
            "height_px": request["delivery"]["height_px"],
            "format": request["delivery"]["format"],
            "tiling_required": request["delivery"]["tiling_required"],
        },
        "generation": {
            "model": workflow_spec["models"]["unet"],
            "workflow": workflow_path,
            "method": "local_ai",
            "seed": request["generation"]["seed"],
        },
        "provenance": {
            "source": "EXPERIMENTAL: local FLUX 3 generation from a baseline preset; "
                      "not a game-approved Art Bible and not a registered B1 candidate.",
            "license": "Rights and license review pending; generated locally with no third-party "
                       "source asset input.",
            "derivations": [f"style profile: {profile['id']}",
                            f"workflow version: {request['generation']['workflow_version']}",
                            f"workflow path: {workflow_path}"],
        },
        "quality_gates": gates,
        "approval": {"status": "draft"},
    }


def prepare_request(root, request_path, *, check_collisions=True):
    root = Path(root).resolve()
    path, relative = _path_from_argument(root, request_path)
    request_bytes = path.read_bytes()
    request = _json_load(path)
    schema_path = _project_relative(root, REQUEST_SCHEMA, must_exist=True)
    schema = _json_load(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(request), key=lambda error: str(error.path))
    if errors:
        raise RequestValidationError(f"schema: {errors[0].message}",
                                     [{"path": list(error.path), "message": error.message}
                                      for error in errors[:10]])
    request_id = request["id"]

    registry = Registry(root)
    try:
        records = registry.validate()
        registry.profile(request["style"]["profile_id"])
    except RegistryError as exc:
        raise RequestValidationError(str(exc)) from exc
    journal = root / "registry/events.jsonl"
    journal_sha = sha256_file(journal) if journal.is_file() else None

    profile_id = request["style"]["profile_id"]
    candidates = [name for name in (f"art/profiles/{profile_id}.json",
                                    f"art/presets/{profile_id}.json")
                  if (root / name).is_file()]
    if len(candidates) != 1:
        raise RequestValidationError(f"missing or ambiguous style profile: {profile_id}")
    profile_path = candidates[0]
    profile = _json_load(root / profile_path)
    profile_sha = sha256_file(root / profile_path)
    budget = profile["budgets"]
    width = request["delivery"]["width_px"]
    height = request["delivery"]["height_px"]
    if max(width, height) > budget["max_texture_edge_px"]:
        raise RequestValidationError(
            f"requested edge {max(width, height)} exceeds profile maximum "
            f"{budget['max_texture_edge_px']}"
        )

    warnings = []
    if request["mode"] == "experimental":
        if not profile_path.startswith("art/presets/"):
            raise RequestValidationError(
                "experimental requests must use an art/presets/ baseline, not a game profile"
            )
        if request_id in records:
            raise RequestValidationError(
                f"experimental request ID is already present in the B1 registry: {request_id}"
            )
        b1_record = None
        b1_origin = "staged synthetic draft (not registered)"
        approval_basis = {
            "kind": "baseline_preset",
            "production_request": False,
            "profile_path": profile_path,
            "profile_sha256": profile_sha,
            "note": "Experimental technical integration test only; no game Art Bible approval.",
        }
        warnings.append("Experimental baseline preset; the candidate is not a game-approved asset.")
    else:
        if profile_path.startswith("art/presets/"):
            warnings.append("Production request uses a game-approved baseline preset profile.")
        b1_record = records.get(request_id)
        if b1_record is None:
            raise RequestValidationError(
                f"production request has no B1 registry record: {request_id}"
            )
        status = b1_record["request"]["approval"]["status"]
        if status != "art_approved":
            raise RequestValidationError(
                f"production generation requires B1 status art_approved, found {status}"
            )
        b1 = b1_record["request"]
        style = request["style"]
        if b1["game_id"] != style["game_id"]:
            raise RequestValidationError("B1 game_id does not match the generation request")
        if b1["style_profile_id"] != style["profile_id"]:
            raise RequestValidationError("B1 style profile does not match the generation request")
        if b1["asset_type"] != request["asset_type"]:
            raise RequestValidationError("B1 asset type does not match the generation request")
        for field in ("width_px", "height_px", "format", "tiling_required"):
            if b1["delivery"][field] != request["delivery"][field]:
                raise RequestValidationError(f"B1 delivery.{field} does not match the request")
        generation = b1["generation"]
        if generation.get("method") != "local_ai":
            raise RequestValidationError("B1 generation method must be local_ai")
        if generation.get("seed") != request["generation"]["seed"]:
            raise RequestValidationError("B1 seed does not match the generation request")
        if generation.get("workflow") != request["output"]["workflow_path"]:
            raise RequestValidationError("B1 workflow path does not match output.workflow_path")
        bible = b1_record.get("bible")
        if not bible or bible.get("version") != style["bible_version"]:
            raise RequestValidationError("B1 art approval does not match the requested Bible version")
        if bible.get("profile_id") != profile_id:
            raise RequestValidationError("B1 Art Bible profile does not match the request")
        b1_origin = "existing B1 registry record"
        approval_basis = {
            "kind": "b1_art_bible_approval",
            "production_request": True,
            "game_id": b1["game_id"],
            "bible": {"version": bible["version"], "path": bible["path"],
                      "sha256": bible["sha256"], "approved_by": bible["approved_by"],
                      "approved_on": bible["approved_on"]},
            "b1_asset_status": status,
            "note": "B3 consumes an existing B1 art approval and does not create or upgrade it.",
        }
        warnings.append("Production generation consumes an existing B1 art approval; "
                        "B3 does not write registry events.")

    catalog, catalog_path, catalog_sha = load_catalog(root)
    workflow_version = request["generation"]["workflow_version"]
    workflow_spec = _workflow_spec(catalog, workflow_version)
    if b1_record is not None:
        b1_model = b1_record["request"]["generation"].get("model")
        if b1_model != workflow_spec["models"]["unet"]:
            raise RequestValidationError(
                f"B1 generation model does not match the pinned workflow model: {b1_model!r}"
            )
    if request["asset_type"] not in workflow_spec.get("supported_asset_types", []):
        raise RequestValidationError(
            f"workflow {workflow_version} does not support asset type {request['asset_type']}"
        )
    reference, reference_path, reference_sha = verify_reference_workflow(root, workflow_spec)
    positive, negative = build_prompt(request, profile, workflow_spec)
    graph = parameterize_graph(
        reference, workflow_spec,
        positive=positive, negative=negative,
        width=width, height=height, seed=request["generation"]["seed"],
        request_id=request_id,
    )
    prompt_sha = sha256_bytes((positive + "\0" + negative).encode("utf-8"))
    if negative and not workflow_spec.get("negative_prompt_effective", False):
        warnings.append("Negative prompt is recorded but CFG 1.0 provides no classifier-free "
                        "negative guidance; do not rely on it.")
    if request["asset_type"] in ("decal", "ui"):
        warnings.append("The pinned graph produces an opaque image; alpha transparency is not "
                        "generated and requires separate review.")
    if request["delivery"]["tiling_required"]:
        warnings.append("Tiling is requested; B2 seam screens and human visual review are required.")
    postprocess = request["quality"]["postprocess"]
    if postprocess["seamless"] == "generic_wrap_blend" and not request["delivery"]["tiling_required"]:
        raise RequestValidationError("generic seamless post-processing requires tiling")

    output_dir = request["output"]["directory"]
    image_path = f"{output_dir}/{request_id}.png"
    workflow_path = request["output"]["workflow_path"]
    staging_dir = f"{STAGING_ROOT}/{request_id}"
    qa_dir = f"{EVIDENCE_ROOT}/{request_id}"
    prepared = PreparedRequest(
        root=root,
        request_path=relative,
        request=request,
        request_bytes=request_bytes,
        request_sha256=sha256_bytes(request_bytes),
        profile=profile,
        profile_path=profile_path,
        profile_sha256=profile_sha,
        catalog=catalog,
        catalog_path=catalog_path.relative_to(root).as_posix(),
        catalog_sha256=catalog_sha,
        workflow_version=workflow_version,
        workflow_spec=workflow_spec,
        reference_path=reference_path.relative_to(root).as_posix(),
        reference_sha256=reference_sha,
        graph=graph,
        positive_prompt=positive,
        negative_prompt=negative,
        prompt_sha256=prompt_sha,
        image_path=image_path,
        workflow_path=workflow_path,
        staging_dir=staging_dir,
        qa_dir=qa_dir,
        b1_request=(deepcopy(b1_record["request"]) if b1_record else
                    _b1_request(request, profile, workflow_spec, workflow_path)),
        b1_request_origin=b1_origin,
        b1_record=b1_record,
        approval_basis=approval_basis,
        warnings=warnings,
        registry_event_count=sum(len(record["history"]) for record in records.values()),
        registry_journal_sha256=journal_sha,
    )
    try:
        registry.schema(registry.request_validator, prepared.b1_request)
    except RegistryError as exc:
        raise RequestValidationError(f"derived B1 request is invalid: {exc}") from exc
    if check_collisions:
        _validate_no_collisions(root, prepared)
    return prepared


def preflight_comfy(client, prepared):
    stats = client.system_stats()
    object_info = client.object_info()
    checks = verify_workflow_against_installation(prepared.graph, prepared.workflow_spec, object_info)
    system = stats.get("system", {}) if isinstance(stats, dict) else {}
    return {
        "available": True,
        "server_url": client.base_url,
        "comfyui_version": system.get("comfyui_version") or system.get("version"),
        "system": system,
        "devices": stats.get("devices", []),
        "object_info_nodes": len(object_info),
        "workflow_checks": checks,
    }


def _extract_outputs(entry):
    outputs = entry.get("outputs")
    if not isinstance(outputs, dict):
        raise ComfyProtocolError("history entry has no outputs object")
    images = []
    for node_id, node_output in outputs.items():
        if not isinstance(node_output, dict):
            continue
        for image in node_output.get("images", []):
            if isinstance(image, dict):
                images.append((node_id, image))
    if not images:
        raise OutputVerificationError("ComfyUI reported no image outputs")
    if len(images) != 1:
        raise OutputVerificationError(f"expected exactly one image output, got {len(images)}")
    return images[0]


def _execution_events(entry):
    events = {}
    status = entry.get("status", {})
    for message in status.get("messages", []):
        if isinstance(message, list) and len(message) == 2 and isinstance(message[1], dict):
            events[message[0]] = message[1].get("timestamp")
    return events


def _verify_png(data, expected_width, expected_height):
    if len(data) < 64:
        raise OutputVerificationError("downloaded image is too small")
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise OutputVerificationError("downloaded image exceeds the safety cap")
    if not data.startswith(PNG_SIGNATURE):
        raise OutputVerificationError("downloaded file is not a PNG")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "PNG":
                raise OutputVerificationError(f"unexpected image format: {image.format}")
            if image.size != (expected_width, expected_height):
                raise OutputVerificationError(
                    f"image dimensions {image.size} do not match request "
                    f"{(expected_width, expected_height)}"
                )
            mode = image.mode
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise OutputVerificationError(f"downloaded PNG failed verification: {exc}") from exc
    return {"format": "PNG", "width": expected_width, "height": expected_height, "mode": mode}


def _qa_summary(role, path, report, evidence):
    return {
        "role": role,
        "path": path,
        "sha256": report["source_sha256"],
        "automated_result": report["automated_result"],
        "overall_result": report["overall_result"],
        "checks": report["checks"],
        "assessments": report["assessments"],
        "evidence": evidence,
        "registry_gate_claims": report["registry_gate_claims"],
    }


def _evaluate_and_write(root, qa_dir, path, profile_id, tiling, b1_request, expected_sha):
    report, images = texture_qa.evaluate(
        root, path, profile_id, seamless=tiling, request=b1_request,
        expected_sha256=expected_sha,
    )
    evidence = texture_qa.write_evidence(root, qa_dir, report, images)
    return report, evidence


def _write_failure(prepared, exc, context=None):
    staging = prepared.root / prepared.staging_dir
    if not staging.is_dir() or (staging / "result.json").exists():
        return
    result = {
        "schema_version": "1.0",
        "status": "failed",
        "request_id": prepared.request_id,
        "mode": prepared.request["mode"],
        "request_path": prepared.request_path,
        "request_sha256": prepared.request_sha256,
        "approval_basis": prepared.approval_basis,
        "profile": {"id": prepared.profile["id"], "path": prepared.profile_path,
                    "sha256": prepared.profile_sha256},
        "workflow": {"version": prepared.workflow_version,
                     "reference_path": prepared.reference_path,
                     "reference_sha256": prepared.reference_sha256,
                     "run_path": prepared.workflow_path,
                     "run_sha256": (sha256_file(prepared.root / prepared.workflow_path)
                                    if (prepared.root / prepared.workflow_path).is_file() else None),
                     "prompt_sha256": prepared.prompt_sha256},
        "error": exc.as_dict() if isinstance(exc, GenerationError) else {
            "code": "unexpected_error", "message": str(exc), "detail": None},
        "partial": context or {},
        "registry_events_written": False,
        "approval_status": "not_approved",
        "finished_at": now_iso(),
    }
    try:
        _write_new(staging / "result.json", _json_bytes(result))
    except OSError:
        pass


def execute_generation(prepared, client, *, timeout_seconds=600, poll_interval=1.0):
    root = prepared.root
    _validate_no_collisions(root, prepared)
    preflight = preflight_comfy(client, prepared)
    request = prepared.request

    staging = root / prepared.staging_dir
    try:
        staging.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RequestValidationError(f"duplicate staging path: {prepared.staging_dir}") from exc
    _write_new(staging / "request.json", prepared.request_bytes)
    if prepared.b1_record is None:
        _write_new(staging / "b1-draft-request.json", _json_bytes(prepared.b1_request))
    else:
        reference = {
            "asset_id": prepared.request_id,
            "journal": "registry/events.jsonl",
            "status": prepared.b1_record["request"]["approval"]["status"],
            "request_sha256": prepared.b1_record["history"][0]["hash"],
            "note": "Existing B1 record referenced; B3 writes no registry event.",
        }
        _write_new(staging / "b1-record-reference.json", _json_bytes(reference))
    _write_new(root / prepared.workflow_path, _json_bytes(prepared.graph))
    run_workflow_sha = sha256_file(root / prepared.workflow_path)
    _write_new(staging / "preflight.json", _json_bytes(preflight))

    client_id = str(uuid.uuid4())
    started_at = now_iso()
    started = time.monotonic()
    context = {"client_id": client_id, "preflight": preflight}
    prompt_id = None
    try:
        submission = client.submit(prepared.graph, client_id)
        prompt_id = submission.get("prompt_id")
        if not isinstance(prompt_id, str) or not prompt_id:
            raise ComfyProtocolError("prompt submission returned no prompt_id", submission)
        context.update(prompt_id=prompt_id, comfy_number=submission.get("number"))
        deadline = time.monotonic() + float(timeout_seconds)
        entry = None
        polls = 0
        last_status = None
        while time.monotonic() <= deadline:
            polls += 1
            entry = client.history(prompt_id)
            if entry is not None:
                status = entry.get("status", {})
                last_status = status.get("status_str") if isinstance(status, dict) else None
                if isinstance(status, dict) and (status.get("completed") is True or
                                                 status.get("status_str") in ("success", "error")):
                    break
            time.sleep(max(0.01, float(poll_interval)))
        if entry is None or not isinstance(entry.get("status"), dict) or not (
                entry["status"].get("completed") is True or entry["status"].get("status_str") in
                ("success", "error")):
            cancel = client.cancel(prompt_id)
            raise GenerationTimeout(
                f"generation did not complete within {timeout_seconds} seconds",
                {"prompt_id": prompt_id, "polls": polls, "last_status": last_status,
                 "cancel": cancel},
            )
        status = entry["status"]
        if status.get("status_str") != "success" or status.get("completed") is not True:
            raise GenerationJobError(
                "ComfyUI job did not succeed",
                {"prompt_id": prompt_id, "status": status},
            )
        node_id, image_ref = _extract_outputs(entry)
        filename = image_ref.get("filename")
        subfolder = image_ref.get("subfolder", "")
        image_type = image_ref.get("type", "output")
        if not isinstance(filename, str) or not filename:
            raise OutputVerificationError("ComfyUI output image has no filename")
        if image_type != "output":
            raise OutputVerificationError(f"unexpected ComfyUI output type: {image_type}")
        data = client.view(filename, subfolder, image_type)
        verified = _verify_png(data, request["delivery"]["width_px"],
                               request["delivery"]["height_px"])
        image_path = root / prepared.image_path
        _write_new(image_path, data)
        image_sha = sha256_bytes(data)
        image_size = len(data)
    except GenerationError as exc:
        context.update(finished_at=now_iso(), elapsed_seconds=round(time.monotonic() - started, 3))
        _write_failure(prepared, exc, context)
        raise
    except OSError as exc:
        wrapped = OutputVerificationError(f"failed to persist generated output: {exc}")
        context.update(finished_at=now_iso(), elapsed_seconds=round(time.monotonic() - started, 3))
        _write_failure(prepared, wrapped, context)
        raise wrapped from exc

    elapsed = round(time.monotonic() - started, 3)
    finished_at = now_iso()
    events = _execution_events(entry)
    outcome = {
        "status": "completed",
        "schema_version": "1.0",
        "request_id": prepared.request_id,
        "mode": request["mode"],
        "asset_type": request["asset_type"],
        "request": {"path": prepared.request_path, "sha256": prepared.request_sha256},
        "approval_basis": prepared.approval_basis,
        "approval_status": "not_approved",
        "profile": {
            "id": prepared.profile["id"],
            "path": prepared.profile_path,
            "sha256": prepared.profile_sha256,
            "schema_version": prepared.profile["schema_version"],
            "budgets": prepared.profile["budgets"],
        },
        "prompt": {
            "positive": prepared.positive_prompt,
            "negative": prepared.negative_prompt,
            "sha256": prepared.prompt_sha256,
            "negative_effective": prepared.workflow_spec.get("negative_prompt_effective", False),
        },
        "workflow": {
            "version": prepared.workflow_version,
            "catalog_path": prepared.catalog_path,
            "catalog_sha256": prepared.catalog_sha256,
            "reference_path": prepared.reference_path,
            "reference_sha256": prepared.reference_sha256,
            "run_path": prepared.workflow_path,
            "run_sha256": run_workflow_sha,
        },
        "generation": {
            "server_url": preflight["server_url"],
            "comfyui_version": preflight.get("comfyui_version"),
            "client_id": client_id,
            "prompt_id": prompt_id,
            "comfy_number": context.get("comfy_number"),
            "node_id": node_id,
            "comfy_filename": filename,
            "comfy_subfolder": subfolder,
            "comfy_output_type": image_type,
            "polls": polls,
            "started_at": started_at,
            "finished_at": finished_at,
            "elapsed_seconds": elapsed,
            "execution_start_timestamp_ms": events.get("execution_start"),
            "execution_success_timestamp_ms": events.get("execution_success"),
            "seed": request["generation"]["seed"],
            "steps": prepared.workflow_spec["sampling"]["steps"],
            "cfg": prepared.workflow_spec["sampling"]["cfg"],
            "sampler_name": prepared.workflow_spec["sampling"]["sampler_name"],
            "scheduler": prepared.workflow_spec["sampling"]["scheduler"],
            "width_px": request["delivery"]["width_px"],
            "height_px": request["delivery"]["height_px"],
            "models": prepared.workflow_spec["models"],
        },
        "output": {
            "path": prepared.image_path,
            "sha256": image_sha,
            "size_bytes": image_size,
            **verified,
            "comfy_filename": filename,
            "comfy_subfolder": subfolder,
        },
        "postprocess": [],
        "qa": [],
        "qa_errors": [],
        "candidate_recommendation": None,
        "b1": {
            "request_origin": prepared.b1_request_origin,
            "record_status": (prepared.b1_record["request"]["approval"]["status"]
                              if prepared.b1_record else "not registered"),
            "staged_draft": (None if prepared.b1_record
                             else f"{prepared.staging_dir}/b1-draft-request.json"),
            "registry_events_written": False,
            "note": "A human/authorized operator must use the B1 CLI; B3 does not transition status.",
        },
        "preflight": {
            "object_info_nodes": preflight["object_info_nodes"],
            "comfyui_version": preflight.get("comfyui_version"),
            "workflow_checks": preflight["workflow_checks"],
        },
        "warnings": list(prepared.warnings),
        "registry": {
            "events_file": "registry/events.jsonl",
            "event_count_before": prepared.registry_event_count,
            "journal_sha256_before": prepared.registry_journal_sha256,
        },
        "finished_at": finished_at,
    }

    candidates = []
    evidence_parent = root / EVIDENCE_ROOT
    if evidence_parent.exists() and not evidence_parent.is_dir():
        evidence_parent = None
    elif not evidence_parent.exists():
        evidence_parent.mkdir(parents=True, exist_ok=True)
    try:
        if evidence_parent is None:
            raise texture_qa.QAError(f"{EVIDENCE_ROOT} is not a directory")
        raw_report, raw_evidence = _evaluate_and_write(
            root, prepared.qa_dir, prepared.image_path, prepared.profile["id"],
            request["delivery"]["tiling_required"], prepared.b1_request, image_sha,
        )
        candidates.append(("raw", prepared.image_path, raw_report, raw_evidence,
                           image_sha, image_size))
        outcome["qa"].append(_qa_summary("raw", prepared.image_path, raw_report, raw_evidence))

        postprocess = request["quality"]["postprocess"]
        current = candidates[-1]
        seam_checks = (raw_report["checks"].get("edge_screen", {}).get("result"),
                       raw_report["checks"].get("tone_screen", {}).get("result"))
        apply_seam = request["delivery"]["tiling_required"] and (
            postprocess["seamless"] == "generic_wrap_blend" or
            (postprocess["seamless"] == "auto" and "FAIL" in seam_checks)
        )
        if apply_seam:
            destination = f"{request['output']['directory']}/{prepared.request_id}-seamless.png"
            try:
                detail = b3_postprocess.generic_wrap_blend(root / prepared.image_path,
                                                           root / destination)
                derived_sha = detail["output_sha256"]
                report, evidence = _evaluate_and_write(
                    root, prepared.qa_dir, destination, prepared.profile["id"], True,
                    prepared.b1_request, derived_sha,
                )
                outcome["postprocess"].append(detail)
                outcome["qa"].append(_qa_summary("seamless", destination, report, evidence))
                current = ("seamless", destination, report, evidence, derived_sha,
                           detail["size_bytes"])
                candidates.append(current)
            except (b3_postprocess.PostprocessError, texture_qa.QAError, OSError) as exc:
                outcome["warnings"].append(f"generic seamless post-processing skipped: {exc}")
                outcome["qa_errors"].append({"stage": "postprocess_seamless",
                                             "message": str(exc)})

        if postprocess["optimize_png"] == "lossless" or (
                postprocess["optimize_png"] == "auto" and
                current[2]["checks"].get("texture_budget", {}).get("result") == "FAIL"):
            destination = f"{request['output']['directory']}/{prepared.request_id}-optimized.png"
            try:
                detail = b3_postprocess.lossless_optimize(root / current[1], root / destination)
                report, evidence = _evaluate_and_write(
                    root, prepared.qa_dir, destination, prepared.profile["id"],
                    request["delivery"]["tiling_required"], prepared.b1_request,
                    detail["output_sha256"],
                )
                outcome["postprocess"].append(detail)
                outcome["qa"].append(_qa_summary("optimized", destination, report, evidence))
                current = ("optimized", destination, report, evidence,
                           detail["output_sha256"], detail["size_bytes"])
                candidates.append(current)
            except (b3_postprocess.PostprocessError, texture_qa.QAError, OSError) as exc:
                outcome["warnings"].append(f"lossless PNG optimization skipped: {exc}")
                outcome["qa_errors"].append({"stage": "postprocess_optimize",
                                             "message": str(exc)})
    except (texture_qa.QAError, OSError, KeyError, TypeError, ValueError) as exc:
        outcome["warnings"].append(f"B2 QA could not complete: {exc}")
        outcome["qa_errors"].append({"stage": "b2_qa", "message": str(exc)})

    passing = [candidate for candidate in candidates if candidate[2]["overall_result"] != "FAIL"]
    recommended = passing[-1] if passing else (candidates[0] if candidates else None)
    if recommended is None:
        outcome["status"] = "completed_with_errors"
        outcome["candidate_recommendation"] = {
            "role": None,
            "path": prepared.image_path,
            "sha256": image_sha,
            "size_bytes": image_size,
            "overall_result": "NOT_EVALUATED",
            "note": "QA failed to run; the generated candidate is preserved for inspection.",
        }
        outcome["qa_outcome"] = "ERROR"
    else:
        outcome["candidate_recommendation"] = {
            "role": recommended[0],
            "path": recommended[1],
            "sha256": recommended[4],
            "size_bytes": recommended[5],
            "overall_result": recommended[2]["overall_result"],
            "note": "Recommendation is for human review only; it is not an approval or registry event.",
        }
        outcome["qa_outcome"] = ("FAIL" if not passing else
                                 ("REVIEW_REQUIRED" if any(c[2]["overall_result"] == "REVIEW_REQUIRED"
                                                           for c in candidates) else "PASS"))
    if outcome["qa_errors"] and outcome["status"] == "completed":
        outcome["status"] = "completed_with_warnings"
    outcome["notes"] = ("Automated generation and QA only. All human gates remain pending. "
                        "No B1 registry event was written.")

    payload_candidate = recommended or ("raw", prepared.image_path, None, None,
                                        image_sha, image_size)
    generated_payload = {
        "path": payload_candidate[1],
        "sha256": payload_candidate[4],
        "size_bytes": payload_candidate[5],
        "workflow_path": prepared.workflow_path,
        "workflow_sha256": run_workflow_sha,
        "note": "Prospective B1 generated payload only; not recorded. Requires separate authorization.",
    }
    _write_new(staging / "b1-generated-payload.json", _json_bytes(generated_payload))

    after_registry = Registry(root)
    try:
        records_after = after_registry.validate()
        journal_after = root / "registry/events.jsonl"
        outcome["registry"].update(
            event_count_after=sum(len(record["history"]) for record in records_after.values()),
            journal_sha256_after=sha256_file(journal_after) if journal_after.is_file() else None,
        )
        outcome["registry"]["unchanged"] = (
            outcome["registry"]["event_count_after"] == prepared.registry_event_count
            and outcome["registry"]["journal_sha256_after"] == prepared.registry_journal_sha256
        )
        if not outcome["registry"]["unchanged"]:
            outcome["warnings"].append("B1 registry state changed during this run; inspect immediately.")
    except RegistryError as exc:
        outcome["registry"]["error"] = str(exc)

    outcome["candidate"] = {
        "path": prepared.image_path,
        "sha256": image_sha,
        "size_bytes": image_size,
        "preserved": True,
    }
    _write_new(staging / "result.json", _json_bytes(outcome))
    return outcome


def dry_run_report(prepared, client=None, *, check_comfy=True):
    report = prepared.summary()
    report["status"] = "dry_run"
    report["dry_run"] = True
    report["comfy"] = None
    if check_comfy:
        if client is None:
            client = ComfyUIClient()
        report["comfy"] = preflight_comfy(client, prepared)
    return report
