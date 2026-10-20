"""C1C reusable in-engine QA harness — offline orchestration and safety checks.

The harness verifies an *existing* Roblox image asset through a temporary,
run-specific Studio rig. It never uploads assets, saves or publishes a place,
writes a B1 registry event, or treats a test render as an approval.

The Studio connection is abstracted by :class:`StudioAdapter`. A real run must
supply an MCP-backed adapter in a separately authorized milestone; the included
:class:`InMemoryStudioAdapter` is test-only and its reports explicitly say that
Studio was not touched.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from jsonschema import Draft202012Validator, SchemaError
from PIL import Image, UnidentifiedImageError

TOOL_DIR = Path(__file__).resolve().parent
C1C_DIR = TOOL_DIR / "c1c"
SCHEMA_PATH = C1C_DIR / "harness-spec.schema.json"
DEFAULT_MANIFEST = "art/imports/roblox-assets.json"
DEFAULT_EVIDENCE_DIR = "registry/evidence/c1c"

C1C_PREFIX = "C1C_"
FOLDER_PREFIX = "C1C_TextureTest_"
TAG = "C1C_TextureTest"
RUN_ATTR = "C1C_RunId"
TESTONLY_ATTR = "C1C_TestOnly"
CAMERA_TOLERANCE = 1e-6
TEST_ASSET_STATUS = "test_only_unapproved"
SPEC_SCHEMA_VERSION = "1.0"
PINNED_TEST_ASSETS = {"112705883084796": TEST_ASSET_STATUS}

# Build phases recorded in the mutable run-state journal. Recovery uses the
# last confirmed phase to decide whether a rig may exist.
RIG_PHASES = {
    "rig_creating",
    "rig_created",
    "preload_started",
    "preload_complete",
    "preload_failed",
    "capturing",
}


class HarnessError(ValueError):
    """Base error for harness validation and lifecycle failures."""


class SpecError(HarnessError):
    pass


class ManifestError(HarnessError):
    pass


class EvidenceError(HarnessError):
    pass


class SafetyError(HarnessError):
    pass


class CameraRestoreError(HarnessError):
    pass


class AdapterInterruption(HarnessError):
    """A simulated crash / interrupted Studio operation; recoverable."""


class SnapshotError(SafetyError):
    """The adapter returned an incomplete or internally inconsistent hierarchy."""


class ProvenanceError(SafetyError):
    """Recovery is not bound to the original run's recorded provenance."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def canonical_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def require(condition: bool, error: type[HarnessError], message: str) -> None:
    if not condition:
        raise error(message)


def safe_path(root: Path, name: str, must_exist: bool = True) -> Path:
    """Project-relative POSIX path; reject traversal, drive letters and symlinks."""
    root = Path(root).resolve()
    if (not isinstance(name, str) or not name or "\\" in name or name.startswith("/")
            or ":" in name or any(part in ("", ".", "..") for part in name.split("/"))):
        raise HarnessError(f"unsafe project path: {name!r}")
    path = root / name
    if not path.resolve().is_relative_to(root) or path.is_symlink():
        raise HarnessError(f"escaping project path: {name!r}")
    if must_exist and not path.is_file():
        raise HarnessError(f"missing project file: {name!r}")
    return path


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: Any, name: str) -> float:
    require(isinstance(value, (int, float)) and not isinstance(value, bool), SpecError,
            f"{name} must be a number")
    return float(value)


def _position(value: Any, name: str) -> tuple[float, float, float]:
    require(isinstance(value, list) and len(value) == 3, SpecError,
            f"{name} must be an array of three numbers")
    return tuple(_number(item, name) for item in value)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Specification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AssetSpec:
    asset_id: str
    asset_type: str
    status: str
    upload: bool
    source_path: str | None = None
    source_sha256: str | None = None
    manifest_path: str = DEFAULT_MANIFEST

    @property
    def numeric_id(self) -> str:
        return self.asset_id.split("://", 1)[1]


@dataclass(frozen=True)
class StudioTarget:
    studio_id: str
    place: str
    mode: str
    team_create: bool


@dataclass(frozen=True)
class TextureScale:
    name: str
    studs_per_tile: float


@dataclass(frozen=True)
class SeamSpec:
    enabled: bool
    center: tuple[float, float, float]
    size_studs: float
    studs_per_tile: float
    right_offset_u: float


@dataclass(frozen=True)
class GeometrySpec:
    grid_origin: tuple[float, float, float]
    panel_size_studs: float
    columns: int
    gap_studs: float
    labels_enabled: bool
    seam: SeamSpec


@dataclass(frozen=True)
class CameraPose:
    position: tuple[float, float, float]
    look_at: tuple[float, float, float]

    def as_dict(self) -> dict[str, list[float]]:
        return {"position": list(self.position), "look_at": list(self.look_at)}


@dataclass(frozen=True)
class CaptureSpec:
    capture_id: str
    phase: str
    purpose: str
    required: bool
    camera: CameraPose | None = None


@dataclass(frozen=True)
class CleanupSpec:
    verify_baseline: bool
    allow_safe_rename: bool
    preserve_failure_evidence: bool


@dataclass(frozen=True)
class EvidenceSpec:
    out_dir: str
    require_durable_files: bool
    capture_retries: int


@dataclass(frozen=True)
class B1Spec:
    registry_unchanged: bool


@dataclass(frozen=True)
class B2Spec:
    evidence_path: str | None
    require_pending_gates: bool


@dataclass(frozen=True)
class HarnessSpec:
    schema_version: str
    run_id: str
    asset: AssetSpec
    studio: StudioTarget
    texture_scales: tuple[TextureScale, ...]
    geometry: GeometrySpec
    screenshots: tuple[CaptureSpec, ...]
    cleanup: CleanupSpec
    evidence: EvidenceSpec
    b1: B1Spec
    b2: B2Spec
    raw: dict[str, Any] = field(default_factory=dict, compare=False)

    @property
    def folder_name(self) -> str:
        return FOLDER_PREFIX + self.run_id

    @property
    def folder_path(self) -> str:
        return "Workspace." + self.folder_name


def load_spec(root: Path, spec_path: str) -> HarnessSpec:
    """Load, schema-validate and normalize a project-relative harness spec."""
    root = Path(root).resolve()
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
    except (OSError, SchemaError, json.JSONDecodeError) as exc:
        raise SpecError(f"harness schema unavailable: {exc}") from exc
    path = safe_path(root, spec_path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SpecError(f"invalid spec JSON: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(raw), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(part) for part in err.path) or '<root>'}: {err.message}"
            for err in errors[:8]
        )
        raise SpecError("spec schema validation failed: " + detail)
    return _spec_from_raw(raw)


def _spec_from_raw(raw: dict[str, Any]) -> HarnessSpec:
    require(isinstance(raw, dict), SpecError, "spec must be a JSON object")
    require(raw.get("schema_version") == SPEC_SCHEMA_VERSION, SpecError,
            f"unsupported spec schema_version: {raw.get('schema_version')!r}")
    asset_raw = raw["asset"]
    asset = AssetSpec(
        asset_id=asset_raw["asset_id"],
        asset_type=asset_raw["asset_type"],
        status=asset_raw["status"],
        upload=asset_raw["upload"],
        source_path=asset_raw.get("source_path"),
        source_sha256=asset_raw.get("source_sha256"),
        manifest_path=asset_raw.get("manifest_path", DEFAULT_MANIFEST),
    )
    studio_raw = raw["studio"]
    studio = StudioTarget(
        studio_id=studio_raw["studio_id"],
        place=studio_raw["place"],
        mode=studio_raw["mode"],
        team_create=studio_raw["team_create"],
    )
    scales = tuple(
        TextureScale(item["name"], _number(item["studs_per_tile"], "studs_per_tile"))
        for item in raw["texture_scales"]
    )
    require(len({scale.name for scale in scales}) == len(scales), SpecError,
            "texture scale names must be unique")
    geo_raw = raw["geometry"]
    seam_raw = geo_raw["seam"]
    geometry = GeometrySpec(
        grid_origin=_position(geo_raw["grid_origin"], "geometry.grid_origin"),
        panel_size_studs=_number(geo_raw["panel_size_studs"], "panel_size_studs"),
        columns=int(geo_raw["columns"]),
        gap_studs=_number(geo_raw["gap_studs"], "gap_studs"),
        labels_enabled=bool(geo_raw["labels_enabled"]),
        seam=SeamSpec(
            enabled=bool(seam_raw["enabled"]),
            center=_position(seam_raw["center"], "seam.center"),
            size_studs=_number(seam_raw["size_studs"], "seam.size_studs"),
            studs_per_tile=_number(seam_raw["studs_per_tile"], "seam.studs_per_tile"),
            right_offset_u=_number(seam_raw["right_offset_u"], "seam.right_offset_u"),
        ),
    )
    captures = []
    for item in raw["screenshots"]:
        camera = item.get("camera")
        captures.append(CaptureSpec(
            capture_id=item["capture_id"],
            phase=item["phase"],
            purpose=item["purpose"],
            required=bool(item["required"]),
            camera=None if camera is None else CameraPose(
                _position(camera["position"], "camera.position"),
                _position(camera["look_at"], "camera.look_at"),
            ),
        ))
    require(len({capture.capture_id for capture in captures}) == len(captures), SpecError,
            "capture IDs must be unique")
    cleanup_raw = raw["cleanup"]
    evidence_raw = raw["evidence"]
    b1_raw = raw.get("b1", {"registry_unchanged": True})
    b2_raw = raw.get("b2", {"require_pending_gates": True, "evidence_path": None})
    spec = HarnessSpec(
        schema_version=raw["schema_version"],
        run_id=raw["run_id"],
        asset=asset,
        studio=studio,
        texture_scales=scales,
        geometry=geometry,
        screenshots=tuple(captures),
        cleanup=CleanupSpec(
            verify_baseline=bool(cleanup_raw["verify_baseline"]),
            allow_safe_rename=bool(cleanup_raw["allow_safe_rename"]),
            preserve_failure_evidence=bool(cleanup_raw["preserve_failure_evidence"]),
        ),
        evidence=EvidenceSpec(
            out_dir=evidence_raw["out_dir"],
            require_durable_files=bool(evidence_raw["require_durable_files"]),
            capture_retries=int(evidence_raw["capture_retries"]),
        ),
        b1=B1Spec(registry_unchanged=bool(b1_raw["registry_unchanged"])),
        b2=B2Spec(evidence_path=b2_raw.get("evidence_path"),
                  require_pending_gates=bool(b2_raw["require_pending_gates"])),
        raw=raw,
    )
    require(spec.asset.upload is False, SpecError,
            "asset.upload must be false: the harness never uploads assets")
    require(spec.asset.status == TEST_ASSET_STATUS, SpecError,
            "only test_only_unapproved assets are eligible for the C1C harness")
    if spec.evidence.out_dir != DEFAULT_EVIDENCE_DIR:
        raise SpecError(f"evidence.out_dir must be {DEFAULT_EVIDENCE_DIR}")
    return spec


# ---------------------------------------------------------------------------
# Asset manifest and B1/B2 guards
# ---------------------------------------------------------------------------


@dataclass
class AssetManifest:
    root: Path
    path: str = DEFAULT_MANIFEST
    assets: dict[str, dict[str, Any]] = field(default_factory=dict)

    def load(self) -> "AssetManifest":
        document = json.loads(safe_path(self.root, self.path).read_text(encoding="utf-8"))
        require(document.get("schema_version") == "1.0", ManifestError,
                "asset manifest schema_version must be 1.0")
        entries = document.get("assets")
        require(isinstance(entries, list), ManifestError, "asset manifest assets must be a list")
        for entry in entries:
            require(isinstance(entry, dict), ManifestError, "asset manifest entries must be objects")
            asset_id = entry.get("roblox_asset_id")
            require(isinstance(asset_id, str) and asset_id.isdigit() and int(asset_id) > 0,
                    ManifestError, "asset manifest has an invalid Roblox asset ID")
            require(asset_id not in self.assets, ManifestError,
                    f"duplicate Roblox asset ID in manifest: {asset_id}")
            self.assets[asset_id] = entry
        return self

    def resolve(self, asset: AssetSpec) -> dict[str, Any]:
        entry = self.assets.get(asset.numeric_id)
        require(entry is not None, ManifestError,
                "asset ID is not recorded in the project manifest; no upload is permitted")
        require(entry.get("status") == TEST_ASSET_STATUS, ManifestError,
                "asset manifest entry is not test_only_unapproved")
        pinned = PINNED_TEST_ASSETS.get(asset.numeric_id)
        if pinned is not None:
            require(entry.get("status") == pinned, ManifestError,
                    f"asset {asset.numeric_id} must remain {pinned}")
        require(entry.get("asset_type", asset.asset_type) == asset.asset_type, ManifestError,
                "asset manifest type does not match the spec")
        source_path = asset.source_path or entry.get("source_path")
        require(isinstance(source_path, str) and source_path, ManifestError,
                "asset source path is required")
        source = safe_path(self.root, source_path)
        digest = sha256_file(source)
        expected = asset.source_sha256 or entry.get("sha256")
        require(isinstance(expected, str) and re.fullmatch(r"[0-9a-f]{64}", expected) is not None,
                ManifestError, "asset source SHA-256 is required")
        require(digest == expected, ManifestError,
                "asset source SHA-256 does not match the spec/manifest")
        if entry.get("sha256"):
            require(entry["sha256"] == digest, ManifestError,
                    "asset source SHA-256 does not match the manifest")
        return {
            "manifest_path": self.path,
            "entry": entry,
            "source_path": source_path,
            "source_sha256": digest,
        }


def registry_fingerprint(root: Path) -> dict[str, Any]:
    path = Path(root).resolve() / "registry/events.jsonl"
    if not path.exists():
        return {"exists": False, "sha256": None, "size_bytes": 0}
    data = path.read_bytes()
    return {"exists": True, "sha256": sha256_bytes(data), "size_bytes": len(data)}


def asset_manifest_identity(root: Path, spec: HarnessSpec,
                            asset_info: dict[str, Any] | None = None) -> dict[str, Any]:
    """Stable identity of the manifest file and the resolved asset entry."""
    path = safe_path(Path(root).resolve(), spec.asset.manifest_path)
    info = asset_info or {}
    return {
        "path": spec.asset.manifest_path,
        "sha256": sha256_file(path),
        "asset_id": spec.asset.asset_id,
        "numeric_id": spec.asset.numeric_id,
        "status": spec.asset.status,
        "source_path": info.get("source_path") or spec.asset.source_path,
        "source_sha256": info.get("source_sha256") or spec.asset.source_sha256,
    }


def spec_identity(spec: HarnessSpec) -> dict[str, Any]:
    return {
        "schema_version": spec.schema_version,
        "run_id": spec.run_id,
        "spec_sha256": canonical_sha256(spec.raw),
    }


def plan_identity(plan: "RigPlan") -> dict[str, Any]:
    payload = plan.as_dict()
    return {
        "plan_sha256": canonical_sha256(payload),
        "object_count": len(plan.objects),
        "objects": sorted(item.path for item in plan.objects),
    }


def verify_b2_evidence(root: Path, spec: HarnessSpec, actual_sha256: str) -> dict[str, Any]:
    """Check an optional B2 report without treating it as an approval.

    Malformed claim rows are rejected rather than silently skipped: an absent or
    non-object row must never look like a pending gate.
    """
    if not spec.b2.evidence_path:
        return {"checked": False, "result": "NOT_PROVIDED"}
    path = safe_path(Path(root).resolve(), spec.b2.evidence_path)
    document = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(document, dict), HarnessError, "B2 evidence must be a JSON object")
    recorded = document.get("source_sha256")
    require(recorded == actual_sha256, HarnessError,
            "B2 evidence source SHA-256 does not match the harness asset")
    claims = document.get("registry_gate_claims")
    require(isinstance(claims, dict), HarnessError, "B2 registry_gate_claims must be an object")
    for name, claim in claims.items():
        require(isinstance(name, str) and name.strip(), HarnessError,
                "B2 registry_gate_claims has an empty or non-string gate name")
        require(isinstance(claim, dict), HarnessError,
                f"B2 registry_gate_claims[{name!r}] must be an object")
        result = claim.get("result")
        require(isinstance(result, str) and result.strip(), HarnessError,
                f"B2 registry_gate_claims[{name!r}] has no string result")
        if "evidence" in claim:
            require(isinstance(claim["evidence"], list), HarnessError,
                    f"B2 registry_gate_claims[{name!r}].evidence must be a list")
    non_pending = {
        name: claim.get("result")
        for name, claim in claims.items()
        if claim.get("result") != "pending"
    }
    if spec.b2.require_pending_gates and non_pending:
        raise HarnessError(
            "B2 evidence claims non-pending B1 gates; the harness cannot consume it as test-only: "
            + json.dumps(non_pending, sort_keys=True)
        )
    return {
        "checked": True,
        "path": spec.b2.evidence_path,
        "source_sha256": recorded,
        "overall_result": document.get("overall_result"),
        "registry_gate_claims_pending": not non_pending,
        "result": "PASS",
    }


# ---------------------------------------------------------------------------
# Deterministic test-rig plan
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RigObject:
    path: str
    name: str
    class_name: str
    parent: str
    properties: dict[str, Any]
    attributes: dict[str, Any]
    tags: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "class_name": self.class_name,
            "parent": self.parent,
            "properties": self.properties,
            "attributes": self.attributes,
            "tags": list(self.tags),
        }


@dataclass(frozen=True)
class RigPlan:
    folder: str
    objects: tuple[RigObject, ...]

    @property
    def texture_paths(self) -> list[str]:
        return [item.path for item in self.objects if item.class_name == "Texture"]

    def as_dict(self) -> dict[str, Any]:
        return {
            "folder": self.folder,
            "object_count": len(self.objects),
            "objects": [item.as_dict() for item in self.objects],
            "texture_paths": self.texture_paths,
        }


def _rig_attributes(run_id: str) -> dict[str, Any]:
    return {RUN_ATTR: run_id, TESTONLY_ATTR: True}


def build_rig_plan(spec: HarnessSpec) -> RigPlan:
    """Compute the exact temporary geometry and ownership metadata.

    The default example spec reproduces C1B's 2x2 32-stud panel grid at
    (0, 0.5, 65) and a 16-stud cross-part seam pair at z=125.
    """
    attributes = _rig_attributes(spec.run_id)
    tags = (TAG,)
    folder = spec.folder_path
    objects: list[RigObject] = []

    def add(path: str, name: str, class_name: str, parent: str,
            properties: dict[str, Any] | None = None) -> None:
        objects.append(RigObject(path, name, class_name, parent,
                                 properties or {}, dict(attributes), tags))

    add(folder, spec.folder_name, "Folder", "Workspace", {})

    size = spec.geometry.panel_size_studs
    pitch = size + spec.geometry.gap_studs
    origin_x, origin_y, origin_z = spec.geometry.grid_origin
    columns = spec.geometry.columns
    rows = (len(spec.texture_scales) + columns - 1) // columns

    def panel(scale_name: str, studs: float, center: tuple[float, float, float],
              name: str) -> None:
        path = f"{folder}.{name}"
        add(path, name, "Part", folder, {
            "Anchored": True,
            "CanCollide": False,
            "CanTouch": False,
            "CanQuery": False,
            "CastShadow": False,
            "Material": "SmoothPlastic",
            "Color": [1, 1, 1],
            "Position": list(center),
            "Size": [size, 1, size],
        })
        texture_path = f"{path}.C1C_Texture"
        add(texture_path, "C1C_Texture", "Texture", path, {
            "Texture": spec.asset.asset_id,
            "Face": "Top",
            "StudsPerTileU": studs,
            "StudsPerTileV": studs,
            "OffsetStudsU": 0,
            "OffsetStudsV": 0,
            "Transparency": 0,
        })
        if spec.geometry.labels_enabled:
            label_path = f"{path}.C1C_Label_{scale_name}"
            add(label_path, f"C1C_Label_{scale_name}", "BillboardGui", path, {
                "AlwaysOnTop": True,
                "Enabled": True,
                "Text": f"{studs:g} studs/tile",
            })
            add(f"{label_path}.C1C_Text", "C1C_Text", "TextLabel", label_path, {
                "Text": f"{studs:g} studs/tile",
            })

    for index, scale in enumerate(spec.texture_scales):
        row, column = divmod(index, columns)
        x = origin_x + (column - (columns - 1) / 2) * pitch
        z = origin_z + (row - (rows - 1) / 2) * pitch
        panel(scale.name, scale.studs_per_tile, (x, origin_y, z),
              f"C1C_Panel_{scale.name}")

    if spec.geometry.seam.enabled:
        seam = spec.geometry.seam
        half = seam.size_studs / 2
        for side, x, offset in (
            ("Left", seam.center[0] - half, 0),
            ("Right", seam.center[0] + half, seam.right_offset_u),
        ):
            name = f"C1C_Seam{side}"
            path = f"{folder}.{name}"
            add(path, name, "Part", folder, {
                "Anchored": True,
                "CanCollide": False,
                "CanTouch": False,
                "CanQuery": False,
                "CastShadow": False,
                "Material": "SmoothPlastic",
                "Color": [1, 1, 1],
                "Position": [x, seam.center[1], seam.center[2]],
                "Size": [seam.size_studs, 1, seam.size_studs],
            })
            texture_path = f"{path}.C1C_Texture"
            add(texture_path, "C1C_Texture", "Texture", path, {
                "Texture": spec.asset.asset_id,
                "Face": "Top",
                "StudsPerTileU": seam.studs_per_tile,
                "StudsPerTileV": seam.studs_per_tile,
                "OffsetStudsU": offset,
                "OffsetStudsV": 0,
                "Transparency": 0,
            })
            if spec.geometry.labels_enabled:
                label_name = f"C1C_Label_Seam{side}"
                label_path = f"{path}.{label_name}"
                add(label_path, label_name, "BillboardGui", path, {
                    "AlwaysOnTop": True,
                    "Enabled": True,
                    "Text": f"seam {seam.studs_per_tile:g} studs/tile",
                })
                add(f"{label_path}.C1C_Text", "C1C_Text", "TextLabel", label_path, {
                    "Text": f"seam {seam.studs_per_tile:g} studs/tile",
                })

    return RigPlan(folder=folder, objects=tuple(objects))


def rig_paths_in_snapshot(snapshot: dict[str, Any], spec: HarnessSpec) -> list[str]:
    """Best-effort list of run-owned objects currently visible in a snapshot."""
    folder = spec.folder_path
    nodes = snapshot.get("objects", {}) if isinstance(snapshot, dict) else {}
    paths = {
        path for path, node in nodes.items()
        if path == folder
        or _basename(path).startswith(C1C_PREFIX)
        or node.get("attributes", {}).get(RUN_ATTR) == spec.run_id
        or TAG in node.get("tags", [])
    }
    return sorted(paths)


def build_rig(adapter: "StudioAdapter", spec: HarnessSpec,
              plan: RigPlan) -> dict[str, Any]:
    """Create only the tagged temporary rig. Never touches pre-existing objects.

    Creation and preload are reported separately. Any non-interruption exception
    returns a structured partial-build record so the caller can attempt an
    ownership-verified cleanup; a simulated interruption is left recoverable.
    """
    result: dict[str, Any] = {
        "folder": None,
        "created": [],
        "preload": None,
        "build_ok": False,
        "preload_ok": False,
        "phase": "rig_creating",
        "error": None,
        "partial_objects": [],
    }
    try:
        folder = adapter.create_folder(spec.folder_name, _rig_attributes(spec.run_id), [TAG])
        require(folder == plan.folder, HarnessError,
                f"adapter created unexpected folder: {folder!r}")
        result["folder"] = folder
        result["created"].append(folder)
        result["phase"] = "rig_created"
        for item in plan.objects:
            if item.class_name in ("Folder", "TextLabel"):
                continue
            if item.class_name == "Part":
                path = adapter.create_part(folder, item.name, item.attributes, list(item.tags),
                                           item.properties)
                require(path == item.path, HarnessError,
                        f"adapter created unexpected part path {path!r}, expected {item.path!r}")
            elif item.class_name == "Texture":
                parent = item.parent
                path = adapter.create_texture(parent, item.name, item.attributes,
                                              list(item.tags), item.properties)
                # A real adapter may return the C1B-style raw name "Texture". Do not
                # hide it: record it and let cleanup's ownership/naming checks decide.
                require(path.startswith(parent + "."), HarnessError,
                        f"adapter created texture outside its planned part: {path!r}")
            elif item.class_name == "BillboardGui":
                paths = adapter.create_label(item.parent, item.name,
                                             item.properties.get("Text", ""),
                                             item.attributes, list(item.tags),
                                             item.properties)
                require(paths and paths[0] == item.path, HarnessError,
                        f"adapter created unexpected label path: {paths!r}")
                result["created"].extend(paths)
                continue
            else:  # pragma: no cover - plan builder only emits known classes
                raise HarnessError(f"unsupported rig class: {item.class_name}")
            result["created"].append(path)
        result["build_ok"] = True
        result["phase"] = "preload_started"
        preload = adapter.preload(spec.asset.asset_id, plan.texture_paths)
        result["preload"] = preload
        result["preload_ok"] = preload.get("ok") is True
        result["phase"] = "preload_complete" if result["preload_ok"] else "preload_failed"
    except AdapterInterruption:
        raise
    except Exception as exc:  # noqa: BLE001 - record the partial build, do not hide it
        result["error"] = f"{type(exc).__name__}: {exc}"
        if result["build_ok"]:
            result["phase"] = "preload_failed"
        else:
            result["phase"] = "build_failed"
        try:
            result["partial_objects"] = rig_paths_in_snapshot(adapter.snapshot(), spec)
        except Exception:  # noqa: BLE001 - the failure record still matters
            result["partial_objects"] = list(result["created"])
    return result


# ---------------------------------------------------------------------------
# Baseline capture and comparison
# ---------------------------------------------------------------------------


def capture_baseline(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Record the Workspace, camera, selection, tags and relevant properties."""
    return {
        "studio": copy.deepcopy(snapshot.get("studio", {})),
        "workspace": {
            "attributes": copy.deepcopy(snapshot["workspace"].get("attributes", {})),
            "tags": sorted(snapshot["workspace"].get("tags", [])),
            "children": sorted(snapshot["workspace"].get("children", [])),
        },
        "objects": copy.deepcopy(snapshot.get("objects", {})),
        "selection": sorted(snapshot.get("selection", [])),
        "camera": copy.deepcopy(snapshot.get("camera", {})),
        "tagged": {tag: sorted(paths) for tag, paths in snapshot.get("tagged", {}).items()},
    }


def _object_view(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "class_name": node.get("class_name"),
        "attributes": copy.deepcopy(node.get("attributes", {})),
        "tags": sorted(node.get("tags", [])),
        "properties": copy.deepcopy(node.get("properties", {})),
    }


def compare_baseline(baseline: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
    """Compare everything except camera cframe/camera type, which is reported separately."""
    differences: list[dict[str, Any]] = []
    workspace = snapshot["workspace"]
    for key in ("attributes", "tags"):
        expected = baseline["workspace"].get(key)
        actual = sorted(workspace.get(key, [])) if key == "tags" else workspace.get(key, {})
        if actual != expected:
            differences.append({"scope": "Workspace", "field": key,
                                "expected": expected, "actual": actual})
    expected_children = baseline["workspace"].get("children", [])
    actual_children = sorted(workspace.get("children", []))
    if actual_children != expected_children:
        differences.append({"scope": "Workspace", "field": "children",
                            "expected": expected_children, "actual": actual_children})
    expected_selection = baseline.get("selection", [])
    actual_selection = sorted(snapshot.get("selection", []))
    if actual_selection != expected_selection:
        differences.append({"scope": "Selection", "field": "selection",
                            "expected": expected_selection, "actual": actual_selection})
    expected_objects = {
        path: _object_view(node)
        for path, node in baseline.get("objects", {}).items()
        if path != "Workspace.Camera"
    }
    actual_objects = {
        path: _object_view(node)
        for path, node in snapshot.get("objects", {}).items()
        if path != "Workspace.Camera"
    }
    for path in sorted(set(expected_objects) | set(actual_objects)):
        if path not in actual_objects:
            differences.append({"scope": path, "field": "missing", "expected": True})
        elif path not in expected_objects:
            differences.append({"scope": path, "field": "unexpected", "actual": _object_view(
                snapshot["objects"][path])})
        elif expected_objects[path] != actual_objects[path]:
            differences.append({"scope": path, "field": "object",
                                "expected": expected_objects[path],
                                "actual": actual_objects[path]})
    expected_tagged = {tag: list(paths) for tag, paths in baseline.get("tagged", {}).items()}
    actual_tagged = {tag: sorted(paths) for tag, paths in snapshot.get("tagged", {}).items()}
    if actual_tagged != expected_tagged:
        differences.append({"scope": "Tags", "field": "tagged",
                            "expected": expected_tagged, "actual": actual_tagged})
    return {
        "result": "PASS" if not differences else "FAIL",
        "differences": differences[:100],
        "truncated": len(differences) > 100,
    }


def camera_delta(expected: dict[str, Any], actual: dict[str, Any]) -> dict[str, Any]:
    expected_cframe = expected.get("cframe")
    actual_cframe = actual.get("cframe")
    if (not isinstance(expected_cframe, list) or not isinstance(actual_cframe, list)
            or len(expected_cframe) != 12 or len(actual_cframe) != 12):
        return {"cframe_max_delta": None, "camera_type_match": False,
                "comparable": False}
    delta = max(abs(float(a) - float(b)) for a, b in zip(expected_cframe, actual_cframe))
    return {
        "cframe_max_delta": delta,
        "camera_type_match": expected.get("camera_type") == actual.get("camera_type"),
        "comparable": True,
    }


def camera_matches(expected: dict[str, Any], actual: dict[str, Any]) -> bool:
    delta = camera_delta(expected, actual)
    return bool(delta["comparable"] and delta["camera_type_match"]
                and delta["cframe_max_delta"] <= CAMERA_TOLERANCE)


# ---------------------------------------------------------------------------
# Evidence store
# ---------------------------------------------------------------------------


def validate_image_bytes(data: bytes) -> dict[str, Any]:
    """Reject empty, non-PNG, corrupt, fully black or fully transparent evidence."""
    require(isinstance(data, bytes) and len(data) > 0, EvidenceError,
            "capture returned no image bytes")
    require(data.startswith(b"\x89PNG\r\n\x1a\n"), EvidenceError,
            "capture is not a PNG file")
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            rgba = image.convert("RGBA")
            extrema = rgba.getextrema()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise EvidenceError(f"capture is not a decodable image: {exc}") from exc
    require(width > 0 and height > 0, EvidenceError, "capture image is empty")
    visible = max(channel[1] for channel in extrema[:3])
    alpha = extrema[3][1]
    require(visible > 0 and alpha > 0, EvidenceError,
            "capture is entirely black or transparent")
    return {"width": width, "height": height, "bytes": len(data)}


class EvidenceStore:
    """New-only durable evidence plus a mutable run-state journal."""

    def __init__(self, root: Path, out_dir: str, run_id: str):
        self.root = Path(root).resolve()
        self.out_dir = out_dir
        self.run_id = run_id
        self.rel_dir = f"{out_dir}/{run_id}"
        self.run_dir = safe_path(self.root, self.rel_dir, must_exist=False)

    def open_run(self) -> "EvidenceStore":
        require(self.out_dir == DEFAULT_EVIDENCE_DIR, EvidenceError,
                f"evidence must be under {DEFAULT_EVIDENCE_DIR}")
        parent = (self.root / "registry/evidence")
        require(parent.is_dir(), EvidenceError, "registry/evidence must already exist")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        require(not (self.run_dir / "report.json").exists(), EvidenceError,
                "run evidence already exists; choose a new run ID or use recovery")
        require(not (self.run_dir / "state.json").exists(), EvidenceError,
                "leftover run state exists; use recovery instead of restarting the run")
        return self

    def open_existing_run(self) -> "EvidenceStore":
        require(self.run_dir.is_dir(), EvidenceError, "run evidence directory does not exist")
        return self

    def rel(self, name: str) -> str:
        return f"{self.rel_dir}/{name}"

    def write_state(self, state: dict[str, Any]) -> None:
        target = self.run_dir / "state.json"
        temporary = self.run_dir / "state.json.tmp"
        temporary.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
        os.replace(temporary, target)

    def read_state(self) -> dict[str, Any] | None:
        path = self.run_dir / "state.json"
        if not path.is_file():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def save_capture(self, capture_id: str, data: bytes,
                     source: str) -> dict[str, Any]:
        meta = validate_image_bytes(data)
        captures = self.run_dir / "captures"
        captures.mkdir(exist_ok=True)
        name = f"captures/{capture_id}.png"
        target = self.run_dir / name
        require(not target.exists(), EvidenceError,
                f"capture evidence already exists: {name}")
        with target.open("xb") as stream:
            stream.write(data)
        # Hash the bytes that actually reached the durable file, not an
        # intermediate buffer.
        written = target.read_bytes()
        require(written == data, EvidenceError,
                "durable capture bytes differ from the supplied capture bytes")
        return {
            "storage": "saved_file",
            "source": source,
            "evidence_path": self.rel(name),
            "sha256": sha256_file(target),
            "size_bytes": target.stat().st_size,
            "width": meta["width"],
            "height": meta["height"],
        }

    def write_json_new_only(self, name: str, payload: dict[str, Any]) -> str:
        target = self.run_dir / name
        require(not target.exists(), EvidenceError, f"evidence already exists: {name}")
        with target.open("x", encoding="utf-8") as stream:
            json.dump(payload, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
        return self.rel(name)

    def unique_name(self, stem: str) -> str:
        base = stem[:-5] if stem.endswith(".json") else stem
        index = 1
        while (self.run_dir / f"{base}-{index}.json").exists():
            index += 1
        return f"{base}-{index}.json"

    def write_json_unique(self, stem: str, payload: dict[str, Any]) -> str:
        return self.write_json_new_only(self.unique_name(stem), payload)


def import_capture_file(root: Path, spec_path: str, run_id: str, capture_id: str,
                        source_file: str,
                        camera: dict[str, Any] | None = None,
                        out_dir: str = DEFAULT_EVIDENCE_DIR) -> dict[str, Any]:
    """Manual evidence fallback: copy and hash a real operator-supplied PNG.

    The import is bound to the existing spec, run report and capture ID. It never
    invents an image or a path and refuses a capture that already has durable
    evidence. A separate manual-import record keeps the original (inline-only)
    lifecycle report truthful.
    """
    root = Path(root).resolve()
    spec = load_spec(root, spec_path)
    require(spec.run_id == run_id, EvidenceError,
            "import run ID does not match the spec")
    require(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", capture_id) is not None,
            EvidenceError, "invalid capture ID")
    expected = {capture.capture_id: capture for capture in spec.screenshots}
    require(capture_id in expected, EvidenceError,
            "capture ID is not defined by the spec")
    store = EvidenceStore(root, out_dir, run_id).open_existing_run()
    report_path = store.run_dir / "report.json"
    require(report_path.is_file(), EvidenceError,
            "run report is missing; import must bind to a completed run")
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvidenceError(f"run report is not valid JSON: {exc}") from exc
    require(isinstance(report, dict) and report.get("run_id") == run_id, EvidenceError,
            "run report does not match the requested run ID")
    require(canonical_sha256(report.get("spec")) == canonical_sha256(spec.raw),
            EvidenceError, "run report was produced from a different spec")
    report_captures = [
        item for item in report.get("captures", [])
        if isinstance(item, dict) and item.get("capture_id") == capture_id
    ]
    require(len(report_captures) == 1, EvidenceError,
            "capture ID is not uniquely recorded in the run report")
    reported = report_captures[0]
    require(reported.get("evidence", {}).get("storage") == "inline_only", EvidenceError,
            "capture already has durable evidence or was not an inline-only capture")
    require(reported.get("phase") == expected[capture_id].phase, EvidenceError,
            "capture phase does not match the spec")
    record_path = store.run_dir / f"manual-capture-{capture_id}.json"
    require(not record_path.exists(), EvidenceError,
            "a manual import already exists for this capture")
    require(not (store.run_dir / f"captures/{capture_id}.png").exists(), EvidenceError,
            "durable capture evidence already exists for this capture")
    source = Path(source_file)
    require(source.is_absolute() and source.is_file(), EvidenceError,
            "manual capture file must be an existing absolute path")
    data = source.read_bytes()
    saved = store.save_capture(capture_id, data, source="manual_import")
    record = {
        "schema_version": "1.0",
        "run_id": run_id,
        "capture_id": capture_id,
        "capture_phase": expected[capture_id].phase,
        "capture_purpose": expected[capture_id].purpose,
        "spec_path": spec_path,
        "spec_sha256": canonical_sha256(spec.raw),
        "storage": "manual_import",
        "source_file": str(source),
        "imported_at": utc_now(),
        "camera": camera,
        "evidence_path": saved["evidence_path"],
        "sha256": saved["sha256"],
        "size_bytes": saved["size_bytes"],
        "width": saved["width"],
        "height": saved["height"],
        "limitations": [
            "Imported by an operator from a local file; the harness did not take this capture.",
            "The image's provenance and camera state are operator-supplied.",
            "The import is bound to the original spec, run ID and capture ID.",
        ],
    }
    store.write_json_new_only(f"manual-capture-{capture_id}.json", record)
    return record


# ---------------------------------------------------------------------------
# Studio adapter contract and test-only in-memory implementation
# ---------------------------------------------------------------------------


@dataclass
class CaptureResult:
    capture_id: str
    inline_only: bool = False
    image_bytes: bytes | None = None
    image_path: str | None = None
    note: str | None = None


class StudioAdapter(Protocol):
    name: str
    simulates_studio: bool
    supports_viewport_restore: bool

    def snapshot(self) -> dict[str, Any]: ...
    def create_folder(self, name: str, attributes: dict[str, Any],
                      tags: list[str]) -> str: ...
    def create_part(self, folder_path: str, name: str, attributes: dict[str, Any],
                    tags: list[str], properties: dict[str, Any]) -> str: ...
    def create_texture(self, parent_path: str, name: str, attributes: dict[str, Any],
                       tags: list[str], properties: dict[str, Any]) -> str: ...
    def create_label(self, parent_path: str, name: str, text: str,
                     attributes: dict[str, Any], tags: list[str],
                     properties: dict[str, Any]) -> list[str]: ...
    def preload(self, asset_id: str, paths: list[str]) -> dict[str, Any]: ...
    def set_camera(self, camera: dict[str, Any] | None) -> None: ...
    def set_viewport_size(self, width: int, height: int) -> bool: ...
    def rename(self, path: str, new_name: str) -> str: ...
    def destroy(self, path: str) -> None: ...
    def screenshot(self, capture_id: str,
                   camera: dict[str, Any] | None) -> CaptureResult: ...


def _normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = sum(component * component for component in vector) ** 0.5
    require(length > 0, HarnessError, "camera look-at produced a zero-length vector")
    return tuple(component / length for component in vector)  # type: ignore[return-value]


def _cross(a: tuple[float, float, float],
           b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def look_at_cframe(position: tuple[float, float, float],
                   look_at: tuple[float, float, float]) -> list[float]:
    forward = _normalize(tuple(look_at[i] - position[i] for i in range(3)))
    right = _normalize(_cross(forward, (0.0, 1.0, 0.0)))
    up = _cross(right, forward)
    return [*position, *right, *up, *forward]


class InMemoryStudioAdapter:
    """Test-only Studio double. Reports say ``simulates_studio: true``.

    It reproduces the C1B baseline scene and the safe rig semantics, including
    the observed capture-tool camera drift and viewport-size side effect.
    """

    name = "in-memory-c1c"
    simulates_studio = True

    def __init__(self, *, known_assets: set[str] | None = None,
                 screenshot_mode: str = "inline",
                 capture_mutates_camera: bool = False,
                 capture_changes_viewport: bool = False,
                 supports_viewport_restore: bool = True,
                 naming_mode: str = "prefixed",
                 fail_destroy: bool = False,
                 interrupt_after_objects: int | None = None,
                 scratch_dir: Path | None = None):
        self.supports_viewport_restore = supports_viewport_restore
        self.known_assets = ({"112705883084796"} if known_assets is None
                             else set(known_assets))
        self.screenshot_mode = screenshot_mode
        self.capture_mutates_camera = capture_mutates_camera
        self.capture_changes_viewport = capture_changes_viewport
        self.naming_mode = naming_mode
        self.fail_destroy = fail_destroy
        self._interrupt_after_objects = interrupt_after_objects
        self.interrupt_after_objects = None
        self.scratch_dir = Path(scratch_dir) if scratch_dir else None
        self.nodes: dict[str, dict[str, Any]] = {}
        self.selection: list[str] = []
        self.camera = {
            "cframe": [
                -25.210203170776367, 33.48590087890625, -41.345703125,
                -0.8648608326911926, 0.24052149057388306, -0.4406419098377228,
                -0.0, 0.8777521252632141, 0.4791151285171509,
                0.5020118951797485, 0.4143679141998291, -0.7591332793235779,
            ],
            "camera_type": "Fixed",
            "viewport": [1219, 793],
        }
        self.screenshot_calls: list[str] = []
        self.destroy_calls: list[str] = []
        self.rename_calls: list[tuple[str, str]] = []
        self.upload_calls = 0
        self.preload_calls: list[list[str]] = []
        self._mutations = 0
        self._build_baseline()
        self._mutations = 0
        self.interrupt_after_objects = self._interrupt_after_objects

    # -- tree helpers -----------------------------------------------------
    def _add(self, parent: str, name: str, class_name: str,
             attributes: dict[str, Any] | None = None,
             tags: list[str] | None = None,
             properties: dict[str, Any] | None = None) -> str:
        require(parent == "" or parent in self.nodes, HarnessError,
                f"missing parent: {parent}")
        path = f"{parent}.{name}" if parent else name
        require(path not in self.nodes, HarnessError, f"duplicate object path: {path}")
        self.nodes[path] = {
            "path": path,
            "name": name,
            "class_name": class_name,
            "parent": parent,
            "attributes": dict(attributes or {}),
            "tags": list(tags or []),
            "properties": dict(properties or {}),
            "children": [],
        }
        if parent:
            self.nodes[parent]["children"].append(path)
        self._mutations += 1
        if (self.interrupt_after_objects is not None
                and self._mutations >= self.interrupt_after_objects):
            raise AdapterInterruption(
                f"simulated interruption after {self._mutations} object mutations")
        return path

    def _build_baseline(self) -> None:
        self._add("", "Workspace", "Workspace", properties={"StreamingEnabled": True})
        self._add("Workspace", "Camera", "Camera", properties={
            "CameraType": "Fixed", "CFrame": list(self.camera["cframe"]),
            "ViewportSize": list(self.camera["viewport"]),
        })
        self._add("Workspace", "Baseplate", "Part", properties={
            "Position": [0, -8, 0], "Size": [2048, 16, 2048], "Anchored": True,
            "CanCollide": True, "Transparency": 0, "Material": "Plastic",
        })
        self._add("Workspace.Baseplate", "Texture", "Texture", properties={
            "Texture": "rbxassetid://6372755229", "Face": "Top",
            "StudsPerTileU": 8, "StudsPerTileV": 8,
            "OffsetStudsU": 0, "OffsetStudsV": 0, "Transparency": 0.8,
        })
        self._add("Workspace", "Terrain", "Terrain")
        self._add("Workspace", "SpawnLocation", "SpawnLocation", properties={
            "Position": [0, 0.5, 0], "Size": [12, 1, 12], "Anchored": True,
            "CanCollide": True, "Transparency": 0,
        })
        self._add("Workspace.SpawnLocation", "Decal", "Decal", properties={
            "Texture": "rbxasset://textures/SpawnLocation.png", "Face": "Top",
            "Transparency": 0,
        })
        self._mutations = 0

    def _sync_camera_object(self) -> None:
        node = self.nodes.get("Workspace.Camera")
        if node is not None:
            node["properties"]["CFrame"] = list(self.camera["cframe"])
            node["properties"]["CameraType"] = self.camera["camera_type"]
            node["properties"]["ViewportSize"] = list(self.camera["viewport"])

    def _descendants(self, path: str) -> list[str]:
        result: list[str] = []
        for child in self.nodes[path]["children"]:
            result.append(child)
            result.extend(self._descendants(child))
        return result

    # -- adapter API ------------------------------------------------------
    def snapshot(self) -> dict[str, Any]:
        self._sync_camera_object()
        objects = copy.deepcopy(self.nodes)
        tagged: dict[str, list[str]] = {}
        for path, node in objects.items():
            for tag in node["tags"]:
                tagged.setdefault(tag, []).append(path)
        workspace = objects["Workspace"]
        return {
            "adapter": self.name,
            "complete": True,
            "studio": {
                "studio_id": "577768ad-49d8-42f5-ac96-8c66cd12a144",
                "place": "local-unsaved",
                "mode": "Edit",
                "team_create": False,
            },
            "workspace": {
                "attributes": copy.deepcopy(workspace["attributes"]),
                "tags": list(workspace["tags"]),
                "children": list(workspace["children"]),
            },
            "objects": objects,
            "selection": list(self.selection),
            "camera": copy.deepcopy(self.camera),
            "tagged": {tag: sorted(paths) for tag, paths in tagged.items()},
        }

    def create_folder(self, name: str, attributes: dict[str, Any],
                      tags: list[str]) -> str:
        return self._add("Workspace", name, "Folder", attributes, tags)

    def create_part(self, folder_path: str, name: str, attributes: dict[str, Any],
                    tags: list[str], properties: dict[str, Any]) -> str:
        return self._add(folder_path, name, "Part", attributes, tags, properties)

    def create_texture(self, parent_path: str, name: str, attributes: dict[str, Any],
                       tags: list[str], properties: dict[str, Any]) -> str:
        actual_name = "Texture" if self.naming_mode == "raw" else name
        return self._add(parent_path, actual_name, "Texture", attributes, tags, properties)

    def create_label(self, parent_path: str, name: str, text: str,
                     attributes: dict[str, Any], tags: list[str],
                     properties: dict[str, Any]) -> list[str]:
        gui = self._add(parent_path, name, "BillboardGui", attributes, tags,
                        {**properties, "Text": text})
        label = self._add(gui, "C1C_Text", "TextLabel", attributes, tags,
                          {"Text": text})
        return [gui, label]

    def preload(self, asset_id: str, paths: list[str]) -> dict[str, Any]:
        self.preload_calls.append(list(paths))
        numeric = asset_id.split("://", 1)[-1]
        return {"ok": numeric in self.known_assets, "asset_id": asset_id,
                "paths": list(paths)}

    def set_camera(self, camera: dict[str, Any] | None) -> None:
        if camera is None:
            return
        if "cframe" in camera:
            cframe = [float(value) for value in camera["cframe"]]
            require(len(cframe) == 12, HarnessError, "camera cframe must have 12 components")
            camera_type = camera.get("camera_type", self.camera["camera_type"])
        else:
            position = _position(camera.get("position"), "camera.position")
            look_at = _position(camera.get("look_at"), "camera.look_at")
            cframe = look_at_cframe(position, look_at)
            camera_type = camera.get("camera_type", "Fixed")
        self.camera = {"cframe": cframe, "camera_type": camera_type,
                       "viewport": list(self.camera["viewport"])}
        self._sync_camera_object()

    def set_viewport_size(self, width: int, height: int) -> bool:
        if not self.supports_viewport_restore:
            return False
        self.camera["viewport"] = [int(width), int(height)]
        self._sync_camera_object()
        return True

    def rename(self, path: str, new_name: str) -> str:
        require(path in self.nodes, HarnessError, f"cannot rename missing object: {path}")
        node = self.nodes[path]
        parent_path = node["parent"]
        new_path = f"{parent_path}.{new_name}"
        require(new_path not in self.nodes, HarnessError,
                f"rename target already exists: {new_path}")
        old_path = path
        self._repath(old_path, new_path, new_name)
        self.rename_calls.append((old_path, new_path))
        return new_path

    def _repath(self, old_path: str, new_path: str, new_name: str | None = None) -> None:
        node = self.nodes.pop(old_path)
        if new_name is not None:
            node["name"] = new_name
        node["path"] = new_path
        self.nodes[new_path] = node
        parent = self.nodes[node["parent"]]
        parent["children"] = [new_path if child == old_path else child
                              for child in parent["children"]]
        for child in list(node["children"]):
            suffix = child[len(old_path):]
            child_node = self.nodes[child]
            child_node["parent"] = new_path
            self._repath(child, new_path + suffix)

    def destroy(self, path: str) -> None:
        if self.fail_destroy:
            raise HarnessError("simulated cleanup failure")
        require(path in self.nodes, HarnessError, f"cannot destroy missing object: {path}")
        self.destroy_calls.append(path)
        parent = self.nodes[path]["parent"]
        for descendant in reversed(self._descendants(path)):
            self.nodes.pop(descendant, None)
        self.nodes.pop(path, None)
        self.nodes[parent]["children"] = [
            child for child in self.nodes[parent]["children"] if child != path
        ]

    def screenshot(self, capture_id: str,
                   camera: dict[str, Any] | None) -> CaptureResult:
        self.screenshot_calls.append(capture_id)
        mode = self.screenshot_mode
        result: CaptureResult
        if mode == "inline":
            result = CaptureResult(capture_id, inline_only=True,
                                   note="simulated inline-only capture")
        elif mode == "invalid_empty":
            result = CaptureResult(capture_id, inline_only=False,
                                   note="simulated empty capture")
        elif mode == "invalid_black":
            result = CaptureResult(capture_id, inline_only=False,
                                   image_bytes=self._png(color=(0, 0, 0)))
        elif mode == "invalid_corrupt":
            result = CaptureResult(capture_id, inline_only=False,
                                   image_bytes=b"not a png")
        elif mode == "saved_file":
            require(self.scratch_dir is not None, EvidenceError,
                    "saved_file screenshot mode needs a scratch directory")
            target = self.scratch_dir / f"{capture_id}.png"
            target.write_bytes(self._png(pattern=True))
            result = CaptureResult(capture_id, inline_only=False,
                                   image_path=str(target))
        elif mode == "inline_bytes":
            result = CaptureResult(capture_id, inline_only=True,
                                   image_bytes=self._png(pattern=True))
        else:
            raise HarnessError(f"unknown screenshot mode: {mode}")
        if self.capture_mutates_camera:
            rotation = self.camera["cframe"][3:]
            rotation[0] = -rotation[0]
            rotation[2] = -rotation[2]
            self.camera["cframe"] = self.camera["cframe"][:3] + rotation
            self._sync_camera_object()
        if self.capture_changes_viewport:
            self.camera["viewport"] = [690, 675]
            self._sync_camera_object()
        return result

    @staticmethod
    def _png(pattern: bool = False, color: tuple[int, int, int] = (0, 0, 0)) -> bytes:
        image = Image.new("RGB", (64, 64), color)
        if pattern:
            for y in range(0, 64, 8):
                for x in range(0, 64, 8):
                    if (x // 8 + y // 8) % 2 == 0:
                        image.paste((96, 112, 128), (x, y, x + 8, y + 8))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    # -- test controls ----------------------------------------------------
    def upload_asset(self, *args: Any, **kwargs: Any) -> None:
        """Deliberately present to prove the harness never calls it."""
        self.upload_calls += 1
        raise AssertionError("the C1C harness must never upload an asset")

    def inject_object(self, parent: str, name: str, class_name: str = "Part",
                      attributes: dict[str, Any] | None = None,
                      tags: list[str] | None = None,
                      properties: dict[str, Any] | None = None) -> str:
        return self._add(parent, name, class_name, attributes, tags, properties)

    def set_attributes(self, path: str, attributes: dict[str, Any]) -> None:
        self.nodes[path]["attributes"] = dict(attributes)

    def set_tags(self, path: str, tags: list[str]) -> None:
        self.nodes[path]["tags"] = list(tags)


# ---------------------------------------------------------------------------
# Ownership verification and cleanup
# ---------------------------------------------------------------------------


def _basename(path: str) -> str:
    return path.rsplit(".", 1)[-1]


def _repairable_name(node: dict[str, Any]) -> bool:
    return (node.get("class_name") in ("Texture", "Decal")
            and node.get("name") in ("Texture", "Decal"))


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Fail-closed structural validation of an adapter hierarchy snapshot.

    A destructive cleanup is allowed only from a snapshot that is both:
    * explicitly declared complete by the adapter (``complete: true``), and
    * internally consistent (parents, children, reachability and tag index).

    Any structural gap means an unverified descendant could be destroyed by a
    folder-level delete, so it is treated as unsafe rather than ignored.
    """
    issues: list[dict[str, Any]] = []

    def issue(code: str, path: str | None = None, detail: str | None = None) -> None:
        item: dict[str, Any] = {"code": code}
        if path is not None:
            item["path"] = path
        if detail is not None:
            item["detail"] = detail
        issues.append(item)

    if not isinstance(snapshot, dict):
        return {"ok": False, "complete": False, "object_count": 0,
                "issues": [{"code": "snapshot_type"}], "truncated": False}
    if snapshot.get("complete") is not True:
        issue("snapshot_not_complete",
              detail="adapter did not assert complete:true for the hierarchy snapshot")
    workspace = snapshot.get("workspace")
    if not isinstance(workspace, dict):
        issue("workspace_missing")
    objects = snapshot.get("objects")
    if not isinstance(objects, dict):
        issue("objects_missing")
        objects = {}
    tagged = snapshot.get("tagged", {})
    if not isinstance(tagged, dict):
        issue("tagged_invalid")
        tagged = {}
    if "Workspace" not in objects:
        issue("workspace_node_missing", "Workspace")
    elif objects["Workspace"].get("class_name") not in ("Workspace", "DataModel"):
        issue("workspace_class_invalid", "Workspace",
              detail=str(objects["Workspace"].get("class_name")))

    for path, node in objects.items():
        if not isinstance(path, str) or not path:
            issue("path_invalid")
            continue
        if not isinstance(node, dict):
            issue("node_invalid", path)
            continue
        name = node.get("name")
        class_name = node.get("class_name")
        parent = node.get("parent")
        children = node.get("children", [])
        if not isinstance(name, str) or not name:
            issue("name_invalid", path)
            continue
        if not isinstance(class_name, str) or not class_name:
            issue("class_invalid", path)
        if not isinstance(parent, str):
            issue("parent_invalid", path)
            continue
        expected_path = name if parent == "" else f"{parent}.{name}"
        if path != expected_path:
            issue("path_parent_mismatch", path, detail=expected_path)
        if parent and parent not in objects:
            issue("parent_missing", path, detail=parent)
        if not isinstance(children, list):
            issue("children_invalid", path)
            children = []
        if len(children) != len(set(children)):
            issue("children_duplicate", path)
        for child in children:
            if not isinstance(child, str) or child not in objects:
                issue("child_missing", path, detail=str(child))
            elif objects[child].get("parent") != path:
                issue("child_parent_mismatch", child, detail=path)

    for path, node in objects.items():
        if not isinstance(node, dict):
            continue
        parent = node.get("parent")
        if isinstance(parent, str) and parent in objects:
            children = objects[parent].get("children", [])
            if isinstance(children, list) and path not in children:
                issue("child_not_listed", path, detail=parent)

    seen: set[str] = set()
    stack = ["Workspace"]
    while stack:
        path = stack.pop()
        if path in seen:
            issue("cycle_or_duplicate_reach", path)
            continue
        seen.add(path)
        node = objects.get(path)
        if not isinstance(node, dict):
            continue
        children = node.get("children", [])
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, str))
    for path in sorted(set(objects) - seen):
        issue("unreachable_node", path)

    for tag, paths in tagged.items():
        if not isinstance(tag, str) or not tag:
            issue("tag_name_invalid")
            continue
        if not isinstance(paths, list):
            issue("tag_index_invalid", detail=tag)
            continue
        for path in paths:
            if not isinstance(path, str) or path not in objects:
                issue("tagged_path_missing", detail=str(path))
            elif tag not in objects[path].get("tags", []):
                issue("tagged_index_mismatch", path, detail=tag)
    for path, node in objects.items():
        if not isinstance(node, dict):
            continue
        for tag in node.get("tags", []) or []:
            indexed = tagged.get(tag, [])
            if not isinstance(indexed, list) or path not in indexed:
                issue("tag_not_indexed", path, detail=str(tag))

    if not isinstance(snapshot.get("camera"), dict):
        issue("camera_missing")
    if not isinstance(snapshot.get("selection", []), list):
        issue("selection_invalid")

    return {
        "ok": not issues,
        "complete": snapshot.get("complete") is True,
        "object_count": len(objects),
        "issues": issues[:100],
        "truncated": len(issues) > 100,
    }


def verify_ownership(snapshot: dict[str, Any], spec: HarnessSpec,
                     plan: RigPlan) -> dict[str, Any]:
    """Verify every visible descendant against plan, name, run ID, tag and attrs.

    The adapter's snapshot must be declared complete and structurally consistent.
    An object inside the run folder that is not in the deterministic plan is a
    violation (except a repairable raw ``Texture``/``Decal`` name).
    """
    folder = spec.folder_path
    integrity = validate_snapshot(snapshot)
    nodes = snapshot.get("objects", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(nodes, dict):
        nodes = {}
    tagged_index = snapshot.get("tagged", {}) if isinstance(snapshot, dict) else {}
    if not isinstance(tagged_index, dict):
        tagged_index = {}
    present = folder in nodes
    owned_paths: list[str] = []
    violations: list[dict[str, Any]] = []
    naming_issues: list[dict[str, Any]] = []
    for item in integrity["issues"]:
        violations.append({
            "path": item.get("path"), "code": "snapshot_" + item["code"],
            "detail": item.get("detail"),
        })
    folder_class_ok = False
    if present and isinstance(nodes.get(folder), dict):
        folder_class_ok = nodes[folder].get("class_name") == "Folder"
        if not folder_class_ok:
            violations.append({
                "path": folder, "code": "run_root_class",
                "expected": "Folder", "actual": nodes[folder].get("class_name"),
            })
        if nodes[folder].get("name") != spec.folder_name:
            violations.append({
                "path": folder, "code": "run_root_name",
                "expected": spec.folder_name, "actual": nodes[folder].get("name"),
            })
        stack = [folder]
        visited: set[str] = set()
        while stack:
            path = stack.pop()
            if path in visited or path not in nodes:
                continue
            visited.add(path)
            owned_paths.append(path)
            children = nodes[path].get("children", [])
            if isinstance(children, list):
                stack.extend(child for child in children if isinstance(child, str))
    expected_paths = {item.path for item in plan.objects}
    unexpected_objects: list[str] = []
    for path in owned_paths:
        node = nodes[path]
        if not isinstance(node, dict):
            violations.append({"path": path, "code": "node_invalid"})
            continue
        name = node.get("name", _basename(path))
        attributes = node.get("attributes", {})
        tags = node.get("tags", [])
        if not name.startswith(C1C_PREFIX):
            if _repairable_name(node):
                proposed = C1C_PREFIX + node["class_name"]
                conflict = f"{node.get('parent')}.{proposed}" in nodes
                naming_issues.append({
                    "path": path,
                    "class_name": node.get("class_name"),
                    "current_name": name,
                    "proposed_name": proposed,
                    "conflict": conflict,
                })
            else:
                violations.append({
                    "path": path, "code": "name_prefix",
                    "expected": C1C_PREFIX, "actual": name,
                })
        if path not in expected_paths and not _repairable_name(node):
            unexpected_objects.append(path)
            violations.append({
                "path": path, "code": "unexpected_object",
                "detail": "object inside the run folder is not in the deterministic plan",
            })
        if attributes.get(RUN_ATTR) != spec.run_id:
            violations.append({
                "path": path, "code": "run_id",
                "expected": spec.run_id, "actual": attributes.get(RUN_ATTR),
            })
        if attributes.get(TESTONLY_ATTR) is not True:
            violations.append({
                "path": path, "code": "test_only",
                "expected": True, "actual": attributes.get(TESTONLY_ATTR),
            })
        if TAG not in tags:
            violations.append({
                "path": path, "code": "tag", "expected": TAG, "actual": tags,
            })
    inside = set(owned_paths)
    outside_tagged = [
        path for path in tagged_index.get(TAG, [])
        if isinstance(path, str) and path not in inside
    ]
    outside_prefixed = [
        path for path in nodes
        if isinstance(path, str) and path != "Workspace"
        and _basename(path).startswith(C1C_PREFIX) and path not in inside
    ]
    outside_run_attribute = [
        path for path, node in nodes.items()
        if isinstance(path, str) and path not in inside and isinstance(node, dict)
        and node.get("attributes", {}).get(RUN_ATTR) == spec.run_id
    ]
    for path in outside_tagged:
        violations.append({"path": path, "code": "tagged_outside_rig"})
    for path in outside_prefixed:
        violations.append({"path": path, "code": "prefixed_outside_rig"})
    for path in outside_run_attribute:
        violations.append({"path": path, "code": "run_attribute_outside_rig"})
    expected = len(plan.objects)
    actual = len(owned_paths)
    owned_set = set(owned_paths)
    missing_objects = sorted(expected_paths - owned_set)
    inventory_complete = bool(
        present and folder_class_ok and not missing_objects
        and not unexpected_objects and not naming_issues
        and actual == expected
    )
    return {
        "folder": folder,
        "present": present,
        "folder_is_folder": folder_class_ok,
        "objects": sorted(owned_paths),
        "object_count": actual,
        "expected_object_count": expected,
        "expected_objects": sorted(expected_paths),
        "missing_objects": missing_objects,
        "unexpected_objects": unexpected_objects,
        "plan_coverage": ("complete" if inventory_complete
                          else "partial" if actual < expected else "unexpected"),
        "inventory_complete": inventory_complete,
        "snapshot": integrity,
        "violations": violations,
        "naming_issues": naming_issues,
        "outside_tagged": outside_tagged,
        "outside_prefixed": outside_prefixed,
        "outside_run_attribute": outside_run_attribute,
        "ok": bool(present and folder_class_ok and integrity["ok"]
                   and not violations and not naming_issues
                   and not outside_tagged and not outside_prefixed
                   and not outside_run_attribute),
    }


def _ownership_payload(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "folder": report["folder"],
        "present": report["present"],
        "folder_is_folder": report["folder_is_folder"],
        "object_count": report["object_count"],
        "expected_object_count": report["expected_object_count"],
        "objects": report["objects"],
        "expected_objects": report["expected_objects"],
        "missing_objects": report["missing_objects"],
        "unexpected_objects": report["unexpected_objects"],
        "inventory_complete": report["inventory_complete"],
        "plan_coverage": report["plan_coverage"],
        "snapshot": report["snapshot"],
        "violations": report["violations"],
        "naming_issues": report["naming_issues"],
        "outside_tagged": report["outside_tagged"],
        "outside_prefixed": report["outside_prefixed"],
        "outside_run_attribute": report["outside_run_attribute"],
    }


class Harness:
    """Offline-testable orchestration of one test-only asset verification run."""

    def __init__(self, root: Path, spec: HarnessSpec, adapter: StudioAdapter):
        self.root = Path(root).resolve()
        self.spec = spec
        self.adapter = adapter
        self.plan = build_rig_plan(spec)
        self.plan_meta = plan_identity(self.plan)
        self.store: EvidenceStore | None = None
        self.baseline: dict[str, Any] | None = None
        self.asset_info: dict[str, Any] | None = None
        self.asset_meta: dict[str, Any] | None = None
        self.b2_info: dict[str, Any] | None = None
        self.b1_before: dict[str, Any] | None = None
        self.b1_after: dict[str, Any] | None = None
        self.failures: list[dict[str, Any]] = []
        self.captures: list[dict[str, Any]] = []
        self.camera_events: list[dict[str, Any]] = []
        self.viewport_events: list[dict[str, Any]] = []
        self.cleanup_report: dict[str, Any] | None = None
        self.workspace_verification: dict[str, Any] | None = None
        self.failure_evidence: str | None = None
        self.final_snapshot: dict[str, Any] | None = None
        self.interrupted = False
        self.camera_restore_failed = False
        self.stop_captures = False
        self.phase = "not_started"
        self.build_phase = "not_started"
        self.rig: dict[str, Any] = {}
        self.rig_verified_complete = False
        self.recovery_info: dict[str, Any] | None = None
        self.started_at = utc_now()
        self.recovery = False

    # -- public -----------------------------------------------------------
    def run(self) -> dict[str, Any]:
        self.store = EvidenceStore(self.root, self.spec.evidence.out_dir,
                                   self.spec.run_id).open_run()
        try:
            self._preflight()
            self._lifecycle()
        except AdapterInterruption as exc:
            self.interrupted = True
            self._fail("interrupted", str(exc), "lifecycle", "fatal")
        except CameraRestoreError as exc:
            self.camera_restore_failed = True
            self._fail("camera_restore_failed", str(exc), "camera", "fatal")
        except HarnessError as exc:
            self._fail("harness_error", str(exc), self.phase, "fatal")
            if self.phase in RIG_PHASES:
                self._attempt_failure_cleanup()
        except Exception as exc:  # noqa: BLE001 - preserve unexpected harness failure
            self.interrupted = True
            self._fail("unexpected_exception", f"{type(exc).__name__}: {exc}",
                       self.phase, "fatal")
        return self._finish()

    # -- preflight --------------------------------------------------------
    def _preflight(self) -> None:
        self.phase = "preflight"
        snapshot = self.adapter.snapshot()
        integrity = validate_snapshot(snapshot)
        require(integrity["ok"], SnapshotError,
                "adapter hierarchy snapshot is incomplete or inconsistent: "
                + json.dumps(integrity["issues"][:5], sort_keys=True))
        studio = snapshot.get("studio", {})
        require(isinstance(studio.get("studio_id"), str) and studio["studio_id"],
                HarnessError, "connected Studio instance identity is unavailable")
        if studio["studio_id"] != self.spec.studio.studio_id:
            raise HarnessError("connected Studio instance does not match the spec")
        if str(studio.get("mode", "")).lower() != self.spec.studio.mode:
            raise HarnessError("Studio is not in the required Edit mode")
        require(isinstance(studio.get("place"), str) and studio["place"],
                HarnessError, "connected place identity is unavailable")
        if studio["place"] != self.spec.studio.place:
            raise HarnessError("connected place does not match the spec")
        if studio.get("team_create"):
            raise HarnessError("Team Create is active; temporary objects could reach another user")
        camera = snapshot.get("camera", {})
        require(isinstance(camera.get("cframe"), list) and len(camera["cframe"]) == 12,
                HarnessError, "baseline camera CFrame is unavailable")
        require(isinstance(camera.get("viewport"), list) and len(camera["viewport"]) == 2,
                HarnessError, "baseline viewport size is unavailable")
        tagged = snapshot.get("tagged", {}).get(TAG, [])
        prefixed = [
            path for path in snapshot.get("objects", {})
            if path != "Workspace" and _basename(path).startswith(C1C_PREFIX)
        ]
        if tagged or prefixed:
            raise SafetyError(
                "pre-existing C1C objects/tags exist; inspect and recover before starting "
                "a new run"
            )
        manifest = AssetManifest(self.root, self.spec.asset.manifest_path).load()
        self.asset_info = manifest.resolve(self.spec.asset)
        self.asset_info["asset_id"] = self.spec.asset.asset_id
        self.asset_info["asset_type"] = self.spec.asset.asset_type
        self.asset_info["status"] = self.spec.asset.status
        self.asset_info["upload"] = False
        self.asset_meta = asset_manifest_identity(self.root, self.spec, self.asset_info)
        self.b2_info = verify_b2_evidence(self.root, self.spec,
                                          self.asset_info["source_sha256"])
        self.b1_before = registry_fingerprint(self.root)

    # -- lifecycle --------------------------------------------------------
    def _lifecycle(self) -> None:
        snapshot = self.adapter.snapshot()
        integrity = validate_snapshot(snapshot)
        require(integrity["ok"], SnapshotError,
                "baseline hierarchy snapshot is incomplete or inconsistent")
        self.baseline = capture_baseline(snapshot)
        self._save_state("baseline_captured")
        self._take_captures("pre_rig")
        if self._must_stop():
            return
        self.phase = "rig_creating"
        self._save_state("rig_creating")
        try:
            build = build_rig(self.adapter, self.spec, self.plan)
        except AdapterInterruption:
            try:
                partial = rig_paths_in_snapshot(self.adapter.snapshot(), self.spec)
            except Exception:  # noqa: BLE001 - keep the interruption recoverable
                partial = []
            self.rig = {
                "build_ok": False, "preload_ok": False,
                "phase": "build_interrupted", "error": "interrupted",
                "partial_objects": partial, "created": [],
            }
            self.build_phase = "build_interrupted"
            self.phase = "build_interrupted"
            self._save_state("build_interrupted")
            raise
        self.rig = build
        self.build_phase = build["phase"]
        self._save_state(build["phase"])
        if not build["build_ok"]:
            self._fail("build_failed", build.get("error") or "rig build failed",
                       "rig_creating", "fatal")
            self._attempt_failure_cleanup(allow_partial=True)
            return
        initial = verify_ownership(self.adapter.snapshot(), self.spec, self.plan)
        self.rig["verification"] = _ownership_payload(initial)
        hard_ownership_failure = bool(
            initial["violations"]
            or initial["outside_tagged"]
            or initial["outside_prefixed"]
            or initial["outside_run_attribute"]
            or not initial["snapshot"]["ok"]
            or not initial["folder_is_folder"]
        )
        # A raw Texture/Decal name is a repairable naming issue: the object is
        # present and owned but not yet C1C_-prefixed. Captures may proceed; the
        # cleanup rename is still required before deletion.
        repairable_gap = bool(
            initial["naming_issues"]
            and not initial["unexpected_objects"]
            and initial["object_count"] == initial["expected_object_count"]
            and len(initial["missing_objects"]) == len(initial["naming_issues"])
        )
        if hard_ownership_failure:
            self._fail(
                "rig_ownership_verification_failed",
                "newly created rig failed ownership/snapshot verification",
                "rig_created", "fatal",
            )
            self._attempt_failure_cleanup(allow_partial=True)
            return
        if not initial["inventory_complete"] and not repairable_gap:
            self._fail(
                "rig_incomplete",
                f"rig contains {initial['object_count']} of "
                f"{initial['expected_object_count']} planned objects; rig captures "
                "are refused",
                "rig_created", "fatal",
            )
            self._attempt_failure_cleanup(allow_partial=True)
            return
        if not build["preload_ok"]:
            self._fail("preload_failed",
                       "rig build succeeded but asset preload failed: "
                       + json.dumps(build.get("preload"), sort_keys=True),
                       "preload_failed", "fatal")
            self._attempt_failure_cleanup(allow_partial=False)
            return
        self.rig_verified_complete = True
        self.phase = "capturing"
        self._save_state("capturing")
        self._take_captures("rig")
        if self._must_stop():
            return
        self._save_state("captures_complete")
        self.phase = "cleanup"
        self._cleanup()
        if self._must_stop():
            return
        if self.cleanup_report is None or self.cleanup_report.get("result") != "PASS":
            return
        self.phase = "post_cleanup"
        self._take_captures("post_cleanup")

    def _must_stop(self) -> bool:
        return self.interrupted or self.camera_restore_failed

    def _attempt_failure_cleanup(self, allow_partial: bool = True) -> None:
        """Restore the camera, then clean only a fully ownership-verified rig.

        If the hierarchy snapshot is incomplete, an object is unowned, the run
        root is not a Folder, or the camera cannot be verified, nothing is
        deleted and actionable recovery information is preserved.
        """
        self.stop_captures = True
        self.phase = "cleanup"
        info: dict[str, Any] = {
            "attempted": True,
            "allow_partial": allow_partial,
            "build_phase": self.build_phase,
            "partial_objects": list(self.rig.get("partial_objects", []))
            if self.rig else [],
            "cleanup_result": None,
            "verified": False,
        }
        if self.baseline is not None and not self.camera_restore_failed:
            try:
                self._restore_camera()
            except CameraRestoreError as exc:
                self.camera_restore_failed = True
                self._fail("camera_restore_failed", str(exc), "failure_cleanup", "fatal")
                info["blocked"] = "camera could not be restored and verified"
                info["next_action"] = (
                    "Leave the rig in place. Restore the camera from the recorded "
                    "baseline, then run recover() and inspect cleanup-failure evidence."
                )
                self.recovery_info = info
                self._save_state("failure_cleanup_blocked")
                return
        try:
            self._cleanup(allow_partial=allow_partial)
        except Exception as exc:  # noqa: BLE001 - never hide a cleanup failure
            self._fail("failure_cleanup_exception",
                       f"{type(exc).__name__}: {exc}", "failure_cleanup", "fatal")
        cleanup_result = (self.cleanup_report or {}).get("result")
        info["cleanup_result"] = cleanup_result
        info["verified"] = cleanup_result == "PASS"
        if not info["verified"]:
            info["next_action"] = (
                "Nothing was deleted. Inspect the preserved ownership/failure "
                "evidence, reconcile the run folder manually, then call recover()."
            )
        self.recovery_info = info
        self._save_state("failure_cleanup_verified" if info["verified"]
                         else "failure_cleanup_unverified")

    def _fail(self, code: str, message: str, phase: str | None = None,
              severity: str = "error") -> None:
        self.failures.append({
            "code": code,
            "message": message,
            "phase": phase or self.phase,
            "severity": severity,
        })

    def _save_state(self, phase: str) -> None:
        if self.store is None:
            return
        baseline_sha = canonical_sha256(self.baseline) if self.baseline is not None else None
        self.store.write_state({
            "schema_version": SPEC_SCHEMA_VERSION,
            "run_id": self.spec.run_id,
            "phase": phase,
            "last_confirmed_phase": phase,
            "started_at": self.started_at,
            "updated_at": utc_now(),
            "adapter": getattr(self.adapter, "name", "unknown"),
            "simulates_studio": bool(getattr(self.adapter, "simulates_studio", True)),
            "spec": spec_identity(self.spec),
            "spec_sha256": canonical_sha256(self.spec.raw),
            "baseline": self.baseline,
            "baseline_sha256": baseline_sha,
            "b1_before": self.b1_before,
            "asset_manifest": self.asset_meta,
            "plan": self.plan_meta,
            "plan_sha256": self.plan_meta["plan_sha256"],
            "expected_object_inventory": list(self.plan_meta["objects"]),
            "capture_count": len(self.captures),
            "last_confirmed_build_phase": self.build_phase,
            "partial_objects": list(self.rig.get("partial_objects", []))
            if self.rig else [],
            "build": {
                "success": bool(self.rig.get("build_ok", False)),
                "preload_success": bool(self.rig.get("preload_ok", False)),
                "phase": self.rig.get("phase", "not_started"),
                "error": self.rig.get("error"),
            } if self.rig else None,
            "recovery": self.recovery_info,
            "capture_ids": [item["capture_id"] for item in self.captures],
        })

    # -- captures ---------------------------------------------------------
    def _take_captures(self, phase: str) -> None:
        if phase == "rig" and not self.rig_verified_complete:
            self._fail("rig_incomplete",
                       "rig captures refused: the rig is not verified as complete",
                       "capture", "fatal")
            self.stop_captures = True
            return
        for capture in self.spec.screenshots:
            if capture.phase != phase:
                continue
            if self._must_stop() or self.stop_captures:
                return
            self._capture_one(capture)

    def _capture_one(self, capture: CaptureSpec) -> None:
        retries = max(1, self.spec.evidence.capture_retries)
        final: dict[str, Any] | None = None
        for attempt in range(1, retries + 1):
            requested = capture.camera.as_dict() if capture.camera else None
            try:
                if requested:
                    self.adapter.set_camera(requested)
                before = self.adapter.snapshot()["camera"]
                result = self.adapter.screenshot(capture.capture_id, requested)
                require(getattr(result, "capture_id", None) == capture.capture_id,
                        EvidenceError,
                        "adapter returned a capture for a different capture ID")
                require(not (result.image_bytes is not None
                             and result.image_path is not None),
                        EvidenceError,
                        "capture returned both bytes and a path; the source is ambiguous")
            except AdapterInterruption:
                raise
            except Exception as exc:  # noqa: BLE001 - a capture failure is reportable
                final = self._capture_record(capture, attempt, requested, None,
                                             None, None,
                                             invalid_reason=f"{type(exc).__name__}: {exc}")
                try:
                    self._restore_camera()
                except CameraRestoreError as restore_exc:
                    self.camera_restore_failed = True
                    self.stop_captures = True
                    self._fail("camera_restore_failed", str(restore_exc),
                               "camera", "fatal")
                if self.camera_restore_failed:
                    break
                continue
            after_snapshot = self.adapter.snapshot()
            after = after_snapshot["camera"]
            drift = not camera_matches(before, after)
            if drift:
                self.camera_events.append({
                    "capture_id": capture.capture_id,
                    "before": copy.deepcopy(before),
                    "after": copy.deepcopy(after),
                    "delta": camera_delta(before, after),
                })
            self._handle_viewport(after_snapshot["camera"].get("viewport", []),
                                  capture.capture_id)
            restored: dict[str, Any] | None = None
            try:
                restored = self._restore_camera()
            except CameraRestoreError as exc:
                self.camera_restore_failed = True
                self.stop_captures = True
                self._fail("camera_restore_failed", str(exc), "camera", "fatal")
                final = self._capture_record(
                    capture, attempt, requested, before, after, None,
                    drift=drift, restored=None,
                    invalid_reason="camera could not be restored",
                )
                self.captures.append(final)
                return
            final = self._capture_record(
                capture, attempt, requested, before, after, result,
                drift=drift, restored=restored,
            )
            if final["valid"]:
                break
            if not capture.required:
                break
        if final is None:
            final = self._capture_record(capture, retries, None, None, None, None,
                                         invalid_reason="no capture attempt completed")
        self.captures.append(final)
        if capture.required and not final["valid"]:
            self._fail("required_capture_invalid",
                       f"{capture.capture_id}: {final.get('invalid_reason')}",
                       "capture")

    def _capture_record(self, capture: CaptureSpec, attempt: int,
                        requested: dict[str, Any] | None,
                        before: dict[str, Any] | None,
                        after: dict[str, Any] | None,
                        result: CaptureResult | None,
                        drift: bool = False,
                        restored: dict[str, Any] | None = None,
                        invalid_reason: str | None = None) -> dict[str, Any]:
        record: dict[str, Any] = {
            "capture_id": capture.capture_id,
            "phase": capture.phase,
            "purpose": capture.purpose,
            "required": capture.required,
            "attempt": attempt,
            "simulated": bool(getattr(self.adapter, "simulates_studio", True)),
            "requested_camera": copy.deepcopy(requested),
            "camera_before": copy.deepcopy(before),
            "camera_after": copy.deepcopy(after),
            "camera_drift_detected": bool(drift),
            "camera_restored_to_baseline": bool(restored and restored["matched"]),
            "evidence": {
                "storage": "missing",
                "evidence_path": None,
                "sha256": None,
                "size_bytes": None,
                "width": None,
                "height": None,
                "durable": False,
            },
            "valid": False,
            "invalid_reason": invalid_reason,
            "note": result.note if result else None,
            "limitations": [],
        }
        if restored:
            record["camera_restore_delta"] = restored
        if result is None:
            return record
        try:
            if result.image_bytes is not None:
                saved = self.store.save_capture(capture.capture_id, result.image_bytes,
                                                source="adapter_inline_bytes")
                record["evidence"] = {**saved, "durable": True}
                record["valid"] = True
            elif result.image_path:
                path = Path(result.image_path)
                require(path.is_absolute() and path.is_file(), EvidenceError,
                        "adapter capture path is not an existing absolute file")
                saved = self.store.save_capture(capture.capture_id, path.read_bytes(),
                                                source="adapter_file")
                record["evidence"] = {**saved, "durable": True}
                record["valid"] = True
            elif result.inline_only:
                record["valid"] = True
                record["evidence"] = {
                    "storage": "inline_only",
                    "evidence_path": None,
                    "sha256": None,
                    "size_bytes": None,
                    "width": None,
                    "height": None,
                    "durable": False,
                }
                record["limitations"].append(
                    "Inline-only capture: no durable image file or content hash was produced."
                )
                record["limitations"].append(
                    "The harness could not independently validate the inline image content."
                )
            else:
                record["invalid_reason"] = invalid_reason or "capture returned no image data"
        except EvidenceError as exc:
            record["valid"] = False
            record["invalid_reason"] = str(exc)
            record["limitations"].append("No evidence file was written for this capture.")
        return record

    def _handle_viewport(self, viewport: list[int], capture_id: str) -> None:
        if not self.baseline:
            return
        expected = self.baseline["camera"].get("viewport")
        if viewport == expected:
            return
        event = {
            "capture_id": capture_id,
            "expected": list(expected) if expected else None,
            "observed": list(viewport),
            "supported_restore": bool(self.adapter.supports_viewport_restore),
            "restored": False,
            "residual": True,
        }
        if self.adapter.supports_viewport_restore and expected:
            try:
                accepted = self.adapter.set_viewport_size(expected[0], expected[1])
                current = self.adapter.snapshot()["camera"].get("viewport")
                event["restored"] = bool(accepted and current == expected)
                event["residual"] = not event["restored"]
                if not event["restored"]:
                    event["note"] = "adapter accepted the request but the viewport did not match"
            except Exception as exc:  # noqa: BLE001 - report, never claim restoration
                event["note"] = f"viewport restore failed: {type(exc).__name__}: {exc}"
        else:
            event["note"] = ("adapter reports no explicitly supported viewport-restore method")
        self.viewport_events.append(event)

    def _restore_camera(self) -> dict[str, Any]:
        assert self.baseline is not None
        expected = self.baseline["camera"]
        try:
            self.adapter.set_camera({
                "cframe": list(expected["cframe"]),
                "camera_type": expected.get("camera_type", "Fixed"),
            })
        except Exception as exc:  # noqa: BLE001
            raise CameraRestoreError(
                f"camera restore write failed: {type(exc).__name__}: {exc}"
            ) from exc
        current = self.adapter.snapshot()["camera"]
        delta = camera_delta(expected, current)
        if not camera_matches(expected, current):
            raise CameraRestoreError(
                "camera did not return to the recorded baseline: "
                + json.dumps(delta, sort_keys=True)
            )
        return {"matched": True, **delta}

    # -- cleanup ----------------------------------------------------------
    def _cleanup(self, recovery: bool = False, allow_partial: bool = False) -> None:
        snapshot = self.adapter.snapshot()
        verification = verify_ownership(snapshot, self.spec, self.plan)
        self.cleanup_report = {
            "result": "PENDING",
            "allow_partial": allow_partial,
            "verification": _ownership_payload(verification),
            "fresh_verification": None,
            "renamed": [],
            "destroyed": False,
            "post_checks": {},
        }
        folder = self.spec.folder_path
        outside_any = (verification["outside_tagged"]
                       or verification["outside_prefixed"]
                       or verification["outside_run_attribute"])
        if not verification["present"]:
            safe = bool(verification["snapshot"]["ok"] and not outside_any)
            if (recovery or allow_partial) and safe:
                self.cleanup_report["result"] = "PASS"
                self.cleanup_report["note"] = "already clean: no run folder or tracked objects"
                return
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = "run folder is missing; no broad cleanup performed"
            self._fail("rig_not_found", "run folder is missing; no broad cleanup performed",
                       "cleanup", "fatal")
            self._preserve_cleanup_failure(snapshot, verification)
            return
        if not verification["snapshot"]["ok"]:
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = (
                "adapter hierarchy snapshot is incomplete or inconsistent; "
                "destructive cleanup refused"
            )
            self._fail("cleanup_snapshot_incomplete",
                       self.cleanup_report["reason"], "cleanup", "fatal")
            self._preserve_cleanup_failure(snapshot, verification)
            return
        if not verification["folder_is_folder"]:
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = "run root is not a Folder; nothing was deleted"
            self._fail("cleanup_run_root_not_folder",
                       self.cleanup_report["reason"], "cleanup", "fatal")
            self._preserve_cleanup_failure(snapshot, verification)
            return
        if verification["violations"] or outside_any:
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = "ownership verification failed"
            self._fail("cleanup_ownership_violation",
                       "unrelated or unverifiable objects present; nothing was deleted",
                       "cleanup", "fatal")
            self._preserve_cleanup_failure(snapshot, verification)
            return
        if verification["naming_issues"]:
            if not self.spec.cleanup.allow_safe_rename:
                self.cleanup_report["result"] = "FAIL"
                self.cleanup_report["reason"] = (
                    "naming inconsistency requires an explicit safe-rename policy"
                )
                self._fail("cleanup_naming_inconsistency",
                           "Texture/Decal child names lack the C1C_ prefix; nothing was deleted",
                           "cleanup", "fatal")
                self._preserve_cleanup_failure(snapshot, verification)
                return
            for issue in verification["naming_issues"]:
                if issue["conflict"]:
                    self.cleanup_report["result"] = "FAIL"
                    self.cleanup_report["reason"] = (
                        f"cannot rename {issue['path']}: {issue['proposed_name']} already exists"
                    )
                    self._fail("cleanup_rename_conflict", self.cleanup_report["reason"],
                               "cleanup", "fatal")
                    self._preserve_cleanup_failure(snapshot, verification)
                    return
                try:
                    new_path = self.adapter.rename(issue["path"], issue["proposed_name"])
                except Exception as exc:  # noqa: BLE001
                    self.cleanup_report["result"] = "FAIL"
                    self.cleanup_report["reason"] = (
                        f"safe rename failed: {type(exc).__name__}: {exc}"
                    )
                    self._fail("cleanup_rename_failed", self.cleanup_report["reason"],
                               "cleanup", "fatal")
                    self._preserve_cleanup_failure(self.adapter.snapshot(), verification)
                    return
                self.cleanup_report["renamed"].append({
                    "from": issue["path"], "to": new_path,
                    "reason": "safe rename after tag/run-ID verification",
                })
            snapshot = self.adapter.snapshot()
            verification = verify_ownership(snapshot, self.spec, self.plan)
            self.cleanup_report["verification"] = _ownership_payload(verification)
            if (verification["violations"] or verification["naming_issues"]
                    or not verification["snapshot"]["ok"]):
                self.cleanup_report["result"] = "FAIL"
                self.cleanup_report["reason"] = "ownership verification still fails after rename"
                self._fail("cleanup_rename_verification_failed",
                           self.cleanup_report["reason"], "cleanup", "fatal")
                self._preserve_cleanup_failure(snapshot, verification)
                return
        if not verification["inventory_complete"] and not allow_partial:
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = (
                f"rig contains {verification['object_count']} of "
                f"{verification['expected_object_count']} planned objects"
            )
            self._fail("rig_incomplete", self.cleanup_report["reason"], "cleanup", "fatal")
            self._preserve_cleanup_failure(snapshot, verification)
            return
        # A fresh, complete ownership read is required immediately before any
        # destructive call. This is the set the folder-level delete will cover.
        fresh_snapshot = self.adapter.snapshot()
        fresh = verify_ownership(fresh_snapshot, self.spec, self.plan)
        self.cleanup_report["fresh_verification"] = _ownership_payload(fresh)
        fresh_outside = (fresh["outside_tagged"] or fresh["outside_prefixed"]
                         or fresh["outside_run_attribute"])
        if (not fresh["snapshot"]["ok"] or not fresh["folder_is_folder"]
                or fresh["violations"] or fresh["naming_issues"] or fresh_outside
                or (not allow_partial and not fresh["inventory_complete"])):
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = (
                "fresh pre-destruction ownership check failed; nothing was deleted"
            )
            self._fail("cleanup_recheck_failed",
                       self.cleanup_report["reason"], "cleanup", "fatal")
            self._preserve_cleanup_failure(fresh_snapshot, fresh)
            return
        verification = fresh
        snapshot = fresh_snapshot
        try:
            self.adapter.destroy(folder)
            self.cleanup_report["destroyed"] = True
        except Exception as exc:  # noqa: BLE001
            self.cleanup_report["result"] = "FAIL"
            self.cleanup_report["reason"] = f"destroy failed: {type(exc).__name__}: {exc}"
            self._fail("cleanup_destroy_failed", self.cleanup_report["reason"],
                       "cleanup", "fatal")
            self._preserve_cleanup_failure(self.adapter.snapshot(), verification)
            return
        post = self.adapter.snapshot()
        post_checks = {
            "tagged_remaining": post.get("tagged", {}).get(TAG, []),
            "prefixed_remaining": [
                path for path in post.get("objects", {})
                if path != "Workspace" and _basename(path).startswith(C1C_PREFIX)
            ],
            "run_attribute_remaining": [
                path for path, node in post.get("objects", {}).items()
                if node.get("attributes", {}).get(RUN_ATTR) == self.spec.run_id
            ],
        }
        workspace_check = (compare_baseline(self.baseline, post)
                           if self.baseline and self.spec.cleanup.verify_baseline
                           else {"result": "NOT_CHECKED", "differences": []})
        post_checks["workspace"] = workspace_check
        self.cleanup_report["post_checks"] = post_checks
        clean = (not post_checks["tagged_remaining"]
                 and not post_checks["prefixed_remaining"]
                 and not post_checks["run_attribute_remaining"]
                 and workspace_check["result"] != "FAIL")
        self.cleanup_report["result"] = "PASS" if clean else "FAIL"
        if not clean:
            self.cleanup_report["reason"] = "post-cleanup verification failed"
            self._fail("cleanup_post_verification_failed",
                       "post-cleanup state does not match the baseline", "cleanup", "fatal")

    def _preserve_cleanup_failure(self, snapshot: dict[str, Any],
                                  verification: dict[str, Any]) -> None:
        if not self.spec.cleanup.preserve_failure_evidence or self.store is None:
            return
        recovery_info = self.recovery_info or {
            "attempted": True,
            "allow_partial": bool((self.cleanup_report or {}).get("allow_partial")),
            "build_phase": self.build_phase,
            "partial_objects": list(self.rig.get("partial_objects", [])) if self.rig else [],
            "cleanup_result": (self.cleanup_report or {}).get("result"),
            "verified": False,
            "next_action": (
                "Nothing was deleted. Inspect the preserved ownership/failure evidence, "
                "reconcile the run objects, then call recover()."
            ),
        }
        payload = {
            "schema_version": "1.0",
            "run_id": self.spec.run_id,
            "recorded_at": utc_now(),
            "phase": self.phase,
            "last_confirmed_phase": self.phase,
            "last_confirmed_build_phase": self.build_phase,
            "partial_objects": list(self.rig.get("partial_objects", [])) if self.rig else [],
            "reason": self.cleanup_report.get("reason") if self.cleanup_report else None,
            "next_action": recovery_info["next_action"],
            "recovery_info": copy.deepcopy(recovery_info),
            "ownership": _ownership_payload(verification),
            "objects": [
                {
                    "path": path,
                    "class_name": node.get("class_name"),
                    "attributes": copy.deepcopy(node.get("attributes", {})),
                    "tags": list(node.get("tags", [])),
                }
                for path, node in snapshot.get("objects", {}).items()
                if path == self.spec.folder_path
                or _basename(path).startswith(C1C_PREFIX)
                or node.get("attributes", {}).get(RUN_ATTR) == self.spec.run_id
                or TAG in node.get("tags", [])
            ],
        }
        self.failure_evidence = self.store.write_json_unique("cleanup-failure", payload)

    # -- reporting --------------------------------------------------------
    def _finish(self) -> dict[str, Any]:
        report = self._build_report()
        if self.store is not None:
            report["evidence"]["report_path"] = self.store.rel("report.json")
            self.store.write_json_new_only("report.json", report)
            self._save_final_state(report)
        return report

    def _save_final_state(self, report: dict[str, Any]) -> None:
        if self.store is None:
            return
        self.store.write_state({
            "schema_version": SPEC_SCHEMA_VERSION,
            "run_id": self.spec.run_id,
            "phase": report["result"],
            "last_confirmed_phase": self.phase,
            "started_at": self.started_at,
            "updated_at": utc_now(),
            "adapter": getattr(self.adapter, "name", "unknown"),
            "simulates_studio": bool(getattr(self.adapter, "simulates_studio", True)),
            "spec": spec_identity(self.spec),
            "spec_sha256": canonical_sha256(self.spec.raw),
            "baseline": self.baseline,
            "baseline_sha256": (canonical_sha256(self.baseline)
                                if self.baseline is not None else None),
            "b1_before": self.b1_before,
            "asset_manifest": self.asset_meta,
            "plan": self.plan_meta,
            "plan_sha256": self.plan_meta["plan_sha256"],
            "expected_object_inventory": list(self.plan_meta["objects"]),
            "capture_count": len(self.captures),
            "last_confirmed_build_phase": self.build_phase,
            "partial_objects": list(self.rig.get("partial_objects", []))
            if self.rig else [],
            "build": {
                "success": bool(self.rig.get("build_ok", False)),
                "preload_success": bool(self.rig.get("preload_ok", False)),
                "phase": self.rig.get("phase", "not_started"),
                "error": self.rig.get("error"),
            } if self.rig else None,
            "recovery": self.recovery_info,
            "captures": [item["capture_id"] for item in self.captures],
            "report_path": report["evidence"].get("report_path"),
        })

    def _finalize_observations(self, recovery: bool = False) -> None:
        if self.baseline is None:
            return
        if self.camera_restore_failed or self.interrupted:
            return
        try:
            self._restore_camera()
        except CameraRestoreError as exc:
            self.camera_restore_failed = True
            self._fail("camera_restore_failed", str(exc), "finalize", "fatal")
        try:
            final = self.adapter.snapshot()
            if self.baseline:
                self._handle_viewport(final["camera"].get("viewport", []), "final")
                final = self.adapter.snapshot()
                self.workspace_verification = compare_baseline(self.baseline, final)
                if (self.workspace_verification["result"] == "FAIL"
                        and not recovery):
                    self._fail("workspace_baseline_mismatch",
                               "post-run Workspace does not match the baseline",
                               "finalize", "fatal")
            self.final_snapshot = final
        except Exception as exc:  # noqa: BLE001
            self._fail("final_snapshot_failed",
                       f"{type(exc).__name__}: {exc}", "finalize", "fatal")
        if self.final_snapshot is None:
            try:
                self.final_snapshot = self.adapter.snapshot()
            except Exception:
                self.final_snapshot = None

    def _build_report(self) -> dict[str, Any]:
        self._finalize_observations(recovery=self.recovery)
        camera = self.final_snapshot.get("camera") if self.final_snapshot else None
        baseline_camera = self.baseline.get("camera") if self.baseline else None
        camera_restored = bool(camera and baseline_camera
                               and camera_matches(baseline_camera, camera)
                               and not self.camera_restore_failed)
        viewport_restored = bool(camera and baseline_camera
                                 and camera.get("viewport") == baseline_camera.get("viewport"))
        residuals: list[str] = []
        if camera and baseline_camera and not viewport_restored:
            residuals.append(
                "viewport size changed: "
                f"{baseline_camera.get('viewport')} -> {camera.get('viewport')} "
                "(not restored through a supported method)"
            )
        if self.failure_evidence:
            residuals.append(f"failure evidence preserved at {self.failure_evidence}")
        if not camera_restored and baseline_camera:
            residuals.append("camera state is not at the recorded baseline")
        workspace_matched = bool(
            self.workspace_verification
            and self.workspace_verification["result"] == "PASS"
        )
        c1c_free = True
        if self.final_snapshot:
            c1c_free = not any(
                _basename(path).startswith(C1C_PREFIX)
                for path in self.final_snapshot.get("objects", {})
                if path != "Workspace"
            )
        restoration_complete = bool(
            self.baseline and camera_restored and viewport_restored
            and workspace_matched and c1c_free and not self.interrupted
            and not self.camera_restore_failed
        )
        durable = sum(1 for capture in self.captures
                      if capture["evidence"]["storage"] == "saved_file")
        inline = sum(1 for capture in self.captures
                     if capture["evidence"]["storage"] == "inline_only")
        invalid = sum(1 for capture in self.captures if not capture["valid"])
        attempted_ids = {capture["capture_id"] for capture in self.captures}
        not_attempted_required = [
            capture.capture_id for capture in self.spec.screenshots
            if capture.required and capture.capture_id not in attempted_ids
        ]
        required_missing = [
            capture["capture_id"] for capture in self.captures
            if capture["required"] and not capture["valid"]
        ] + not_attempted_required
        inline_required = [
            capture["capture_id"] for capture in self.captures
            if capture["required"] and capture["evidence"]["storage"] == "inline_only"
        ]
        durable_ids = {
            capture["capture_id"] for capture in self.captures
            if capture["valid"] and capture["evidence"]["storage"] == "saved_file"
        }
        required_ids = {
            capture.capture_id for capture in self.spec.screenshots if capture.required
        }
        durable_required_satisfied = required_ids <= durable_ids
        evidence_complete = bool(
            self.baseline is not None
            and not self.interrupted
            and not self.camera_restore_failed
            and not required_missing
            and (not self.spec.evidence.require_durable_files or not inline_required)
        )
        # Full acceptance always requires a durable, hashed file for every
        # required capture, even when durable files are optional for a diagnostic run.
        evidence_accepted = bool(
            evidence_complete and durable_required_satisfied and not required_missing
        )
        evidence_limitations = []
        if inline:
            evidence_limitations.append(
                f"{inline} capture(s) are inline-only: capture IDs and camera settings are "
                "recorded, but no image file or content hash exists."
            )
        if self.spec.evidence.require_durable_files and inline_required:
            evidence_limitations.append(
                "Durable evidence was required; inline-only captures leave evidence incomplete."
            )
        if required_ids and not durable_required_satisfied:
            evidence_limitations.append(
                "Full evidence acceptance is withheld because at least one required "
                "capture has no durable, hashed file."
            )
        if invalid:
            evidence_limitations.append(
                f"{invalid} capture(s) were missing or invalid and are not evidence."
            )
        if not_attempted_required:
            evidence_limitations.append(
                "Required captures were not attempted: "
                + ", ".join(not_attempted_required)
            )
        evidence_limitations.append(
            "A capture validates only image bytes when available; the harness cannot prove "
            "the rendered scene or visual acceptance."
        )
        if self.asset_info:
            self.asset_info.pop("entry", None)
        cleanup_result = (self.cleanup_report or {}).get("result", "NOT_RUN")
        hard_failure = bool(self.failures)
        if self.interrupted:
            result = "INCOMPLETE"
        elif hard_failure or (not evidence_complete and not self.recovery) or cleanup_result not in ("PASS", "NOT_RUN"):
            result = "FAIL"
        elif (not restoration_complete or residuals or invalid
              or (not self.spec.evidence.require_durable_files and inline)):
            result = "PASS_WITH_RESIDUALS"
        else:
            result = "PASS"
        if self.recovery:
            if self.interrupted:
                result = "FAIL"
            elif result in ("PASS", "PASS_WITH_RESIDUALS") and cleanup_result == "PASS":
                result = ("RECOVERED_WITH_RESIDUALS" if (residuals
                          or not restoration_complete) else "RECOVERED")
            else:
                result = "FAIL"
        report = {
            "schema_version": "1.0",
            "harness": "c1c",
            "run_id": self.spec.run_id,
            "started_at": self.started_at,
            "finished_at": utc_now(),
            "adapter": {
                "name": getattr(self.adapter, "name", "unknown"),
                "simulates_studio": bool(getattr(self.adapter, "simulates_studio", True)),
                "studio_touched": not bool(getattr(self.adapter, "simulates_studio", True)),
            },
            "spec": copy.deepcopy(self.spec.raw),
            "provenance": {
                "spec_sha256": canonical_sha256(self.spec.raw),
                "run_id": self.spec.run_id,
                "baseline_sha256": (canonical_sha256(self.baseline)
                                    if self.baseline is not None else None),
                "b1_before": copy.deepcopy(self.b1_before),
                "asset_manifest": copy.deepcopy(self.asset_meta),
                "plan_sha256": self.plan_meta["plan_sha256"],
                "expected_object_inventory": list(self.plan_meta["objects"]),
            },
            "asset": copy.deepcopy(self.asset_info),
            "b2": copy.deepcopy(self.b2_info),
            "rig": {
                "folder": self.plan.folder,
                "planned_object_count": len(self.plan.objects),
                "expected_object_inventory": sorted(
                    item.path for item in self.plan.objects),
                "build_success": bool(self.rig.get("build_ok", False)),
                "preload_success": bool(self.rig.get("preload_ok", False)),
                "build_phase": self.build_phase,
                "build_error": self.rig.get("error"),
                "partial_objects": list(self.rig.get("partial_objects", [])),
                "rig_captures_allowed": self.rig_verified_complete,
                **({"created": self.rig.get("created"),
                    "preload": self.rig.get("preload"),
                    "verification": self.rig.get("verification")}
                   if self.rig else {}),
            },
            "captures": copy.deepcopy(self.captures),
            "camera": {
                "baseline": copy.deepcopy(baseline_camera),
                "final": copy.deepcopy(camera),
                "drift_events": copy.deepcopy(self.camera_events),
                "restored": camera_restored,
            },
            "viewport": {
                "baseline": copy.deepcopy((baseline_camera or {}).get("viewport")),
                "final": copy.deepcopy((camera or {}).get("viewport")),
                "events": copy.deepcopy(self.viewport_events),
                "restored": viewport_restored,
            },
            "cleanup": copy.deepcopy(self.cleanup_report),
            "workspace_verification": copy.deepcopy(self.workspace_verification),
            "b1": {
                "before": copy.deepcopy(self.b1_before),
                "after": copy.deepcopy(self.b1_after),
                "unchanged": None,
            },
            "evidence": {
                "out_dir": self.spec.evidence.out_dir,
                "report_path": None,
                "evidence_kind": ("simulated_test_only"
                                  if bool(getattr(self.adapter, "simulates_studio", True))
                                  else "studio_capture"),
                "durable_captures": durable,
                "inline_only_captures": inline,
                "invalid_captures": invalid,
                "not_attempted_required": not_attempted_required,
                "durable_capture_ids": sorted(durable_ids),
                "durable_required_satisfied": durable_required_satisfied,
                "complete": evidence_complete,
                "accepted": evidence_accepted,
                "require_durable_files": self.spec.evidence.require_durable_files,
                "limitations": evidence_limitations,
                "failure_evidence": self.failure_evidence,
                "recovery_info": copy.deepcopy(self.recovery_info),
            },
            "restoration": {
                "complete": restoration_complete,
                "camera_restored": camera_restored,
                "viewport_restored": viewport_restored,
                "workspace_matched": workspace_matched,
                "c1c_objects_remaining": not c1c_free,
                "residual_effects": residuals,
            },
            "failures": copy.deepcopy(self.failures),
            "result": result,
        }
        # B1 must be re-read after the lifecycle, not trusted from the journal.
        self.b1_after = registry_fingerprint(self.root)
        report["b1"]["after"] = copy.deepcopy(self.b1_after)
        if self.b1_before is None:
            report["b1"]["unchanged"] = None
        else:
            report["b1"]["unchanged"] = (self.b1_before == self.b1_after)
        if report["b1"]["unchanged"] is False:
            report["failures"].append({
                "code": "b1_registry_modified",
                "message": "registry/events.jsonl changed during the run",
                "phase": "finalize",
                "severity": "fatal",
            })
            report["result"] = "FAIL"
        report["limitations"] = [
            "This harness verifies an existing asset ID; it cannot upload, save, publish or approve.",
            "Edit-mode capture is not target-device, compression, lighting, memory or FPS verification.",
            "Studio-side availability and real adapter behavior are untested until a separately authorized run.",
            "Local evidence and the asset manifest are operator-trusted, not platform-attested.",
        ]
        return report


# ---------------------------------------------------------------------------
# Interrupted-run recovery
# ---------------------------------------------------------------------------


def verify_recovery_provenance(root: Path, spec: HarnessSpec,
                               state: dict[str, Any]) -> dict[str, Any]:
    """Bind recovery to the original run, never to a fresh baseline or spec."""
    root = Path(root).resolve()
    require(isinstance(state, dict), ProvenanceError, "run state must be an object")
    require(state.get("schema_version") == SPEC_SCHEMA_VERSION, ProvenanceError,
            "run state schema is missing or unsupported")
    require(state.get("run_id") == spec.run_id, ProvenanceError,
            "run state does not match the requested run ID")
    stored_spec = state.get("spec_sha256")
    require(isinstance(stored_spec, str) and stored_spec, ProvenanceError,
            "run state has no spec hash; recovery provenance is incomplete")
    require(stored_spec == canonical_sha256(spec.raw), ProvenanceError,
            "spec content changed since the original run")
    baseline = state.get("baseline")
    require(isinstance(baseline, dict) and baseline, ProvenanceError,
            "run state has no baseline; a safe recovery cannot be verified")
    stored_baseline = state.get("baseline_sha256")
    require(isinstance(stored_baseline, str) and stored_baseline, ProvenanceError,
            "run state has no baseline identity")
    require(stored_baseline == canonical_sha256(baseline), ProvenanceError,
            "stored baseline does not match its recorded identity")
    stored_b1 = state.get("b1_before")
    require(isinstance(stored_b1, dict), ProvenanceError,
            "run state has no original B1 registry fingerprint")
    current_b1 = registry_fingerprint(root)
    require(stored_b1 == current_b1, ProvenanceError,
            "B1 registry changed between the original run and recovery")
    stored_manifest = state.get("asset_manifest")
    require(isinstance(stored_manifest, dict) and stored_manifest, ProvenanceError,
            "run state has no asset manifest identity")
    manifest = AssetManifest(root, spec.asset.manifest_path).load()
    asset_info = manifest.resolve(spec.asset)
    current_manifest = asset_manifest_identity(root, spec, asset_info)
    require(stored_manifest == current_manifest, ProvenanceError,
            "asset manifest identity changed since the original run")
    stored_plan = state.get("plan")
    require(isinstance(stored_plan, dict) and stored_plan, ProvenanceError,
            "run state has no expected test object inventory")
    current_plan = plan_identity(build_rig_plan(spec))
    require(stored_plan == current_plan, ProvenanceError,
            "expected test object inventory changed since the original run")
    stored_inventory = state.get("expected_object_inventory")
    require(isinstance(stored_inventory, list), ProvenanceError,
            "run state has no expected object inventory")
    require(sorted(stored_inventory) == current_plan["objects"], ProvenanceError,
            "recorded object inventory does not match the current plan")
    return {
        "verified": True,
        "spec_sha256": stored_spec,
        "baseline_sha256": stored_baseline,
        "b1_before": copy.deepcopy(stored_b1),
        "asset_manifest": copy.deepcopy(stored_manifest),
        "plan_sha256": stored_plan["plan_sha256"],
        "expected_object_inventory": list(current_plan["objects"]),
        "note": "Recovery is bound to the original spec, baseline, B1, manifest and plan.",
    }


def recover(root: Path, spec: HarnessSpec,
            adapter: StudioAdapter) -> dict[str, Any]:
    """Recover an interrupted run without repeating captures or trusting the journal.

    The journal only says *where* to look. Ownership, tags, run ID and the
    Workspace baseline are re-read from Studio before anything is deleted. The
    stored provenance must match the original run exactly; a newly captured
    baseline or a changed spec is never substituted.
    """
    store = EvidenceStore(root, spec.evidence.out_dir, spec.run_id).open_existing_run()
    state = store.read_state()
    require(state is not None, EvidenceError, "no run state found to recover")
    require(state.get("phase") not in ("PASS", "PASS_WITH_RESIDUALS", "RECOVERED"),
            EvidenceError, "run is already complete; recovery is not required")
    provenance = verify_recovery_provenance(root, spec, state)
    harness = Harness(root, spec, adapter)
    harness.store = store
    harness.recovery = True
    harness.phase = "recovery"
    harness.interrupted = False
    harness.baseline = state.get("baseline")
    harness.b1_before = state.get("b1_before")
    harness.build_phase = state.get("last_confirmed_build_phase", "unknown")
    harness.rig = {
        "build_ok": bool((state.get("build") or {}).get("success")),
        "preload_ok": bool((state.get("build") or {}).get("preload_success")),
        "phase": state.get("last_confirmed_build_phase", "unknown"),
        "partial_objects": list(state.get("partial_objects", [])),
    }
    try:
        if harness.baseline:
            harness._restore_camera()
        harness._cleanup(recovery=True, allow_partial=True)
    except CameraRestoreError as exc:
        harness.camera_restore_failed = True
        harness._fail("camera_restore_failed", str(exc), "recovery", "fatal")
    except AdapterInterruption as exc:
        harness.interrupted = True
        harness._fail("interrupted", str(exc), "recovery", "fatal")
    except HarnessError as exc:
        harness._fail("harness_error", str(exc), "recovery", "fatal")
    except Exception as exc:  # noqa: BLE001
        harness._fail("unexpected_exception", f"{type(exc).__name__}: {exc}",
                      "recovery", "fatal")
    report = harness._build_report()
    report["provenance"]["recovery"] = provenance
    report["recovery"] = {
        "attempted": True,
        "recovered": report["result"] in ("RECOVERED", "RECOVERED_WITH_RESIDUALS"),
        "provenance_verified": provenance["verified"],
        "previous_phase": state.get("phase"),
        "previous_started_at": state.get("started_at"),
        "previous_capture_count": state.get("capture_count"),
        "last_confirmed_build_phase": state.get("last_confirmed_build_phase"),
        "partial_objects": list(state.get("partial_objects", [])),
        "captures_repeated": False,
        "note": "Recovery re-read Studio ownership and baseline state; it took no screenshots.",
    }
    name = store.unique_name("recovery")
    report["evidence"]["report_path"] = store.rel(name)
    path = store.write_json_new_only(name, report)
    report["evidence"]["report_path"] = path
    store.write_state({
        "schema_version": SPEC_SCHEMA_VERSION,
        "run_id": spec.run_id,
        "phase": report["result"],
        "last_confirmed_phase": state.get("last_confirmed_phase"),
        "started_at": state.get("started_at"),
        "updated_at": utc_now(),
        "adapter": getattr(adapter, "name", "unknown"),
        "simulates_studio": bool(getattr(adapter, "simulates_studio", True)),
        "spec": state.get("spec"),
        "spec_sha256": state.get("spec_sha256"),
        "baseline": harness.baseline,
        "baseline_sha256": state.get("baseline_sha256"),
        "b1_before": state.get("b1_before"),
        "asset_manifest": state.get("asset_manifest"),
        "plan": state.get("plan"),
        "plan_sha256": state.get("plan_sha256"),
        "expected_object_inventory": state.get("expected_object_inventory"),
        "capture_count": state.get("capture_count", 0),
        "last_confirmed_build_phase": state.get("last_confirmed_build_phase"),
        "partial_objects": state.get("partial_objects", []),
        "build": state.get("build"),
        "captures_repeated": False,
        "captures": state.get("captures", []),
        "report_path": path,
    })
    return report
