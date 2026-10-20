"""Milestone B2 offline texture evidence. No registry mutations or approvals."""

import hashlib
import json
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageFilter, UnidentifiedImageError

from asset_registry import Registry, RegistryError


VERSION = "B2-1.2"
FORMATS = {"PNG": "png", "JPEG": "jpg", "WEBP": "webp"}
# Screening heuristics, not per-game Art Bible acceptance criteria.
RULES = {
    "playful-cartoon": (12.0, 6.0, "broad fields and sparse marks; inspect photo-like grain"),
    "adventure-fantasy": (24.0, 12.0, "stylized detail and legible material features"),
    "atmospheric-survival": (20.0, 10.0, "controlled noise and navigable dark values"),
    "competitive-clean": (9.0, 5.0, "restrained surface detail and clear geometry"),
    "cozy-social": (11.0, 5.0, "soft, clean and consistent material fields"),
}
MAX_PIXELS = 4096 * 4096  # Bound decoded arrays and maliciously large headers.


class QAError(ValueError):
    pass


def safe_path(root, name, must_exist=True):
    """Project-relative POSIX reference; reject escapes, including symlinks."""
    if (not isinstance(name, str) or not name or "\\" in name or name.startswith("/")
            or ":" in name or any(p in ("", ".", "..") for p in name.split("/"))):
        raise QAError(f"unsafe project path: {name!r}")
    base = Path(root).resolve()
    path = base / name
    # A missing target is allowed, but no existing parent may escape the root.
    if not path.resolve().is_relative_to(base):
        raise QAError(f"escaping project path: {name!r}")
    if must_exist and not path.is_file():
        return path
    if path.is_symlink():
        raise QAError(f"symlink source refused: {name!r}")
    return path


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check(result, name, status, detail):
    result["checks"][name] = {"result": status, "detail": detail}


def edge_stats(rgb):
    p = np.asarray(rgb, dtype=np.float32)
    def mean(delta):
        return round(float(np.abs(delta).mean()), 3)
    vx, hx = mean(p[:, -1] - p[:, 0]), mean(p[-1] - p[0])
    nx, ny = mean(p[:, 1:] - p[:, :-1]), mean(p[1:] - p[:-1])
    def ratio(a, b):
        return round(a / b, 3) if b else (0.0 if a == 0 else None)
    return {"vertical_edge_mean": vx, "horizontal_edge_mean": hx,
            "ordinary_x_mean": nx, "ordinary_y_mean": ny,
            "vertical_ratio": ratio(vx, nx), "horizontal_ratio": ratio(hx, ny)}


def proxies(rgb):
    gray = np.asarray(rgb.convert("L"), dtype=np.float32)
    fine = np.asarray(rgb.convert("L").filter(ImageFilter.GaussianBlur(2)), dtype=np.float32)
    broad = np.asarray(rgb.convert("L").filter(ImageFilter.GaussianBlur(32)), dtype=np.float32)
    return {"high_frequency_residual_std": round(float((gray - fine).std()), 3),
            "broad_tone_std": round(float(broad.std()), 3),
            "broad_tone_p99_deviation": round(float(np.percentile(np.abs(broad - broad.mean()), 99)), 3)}


def previews(rgb):
    """Native 3x3 up to 1024px; bounded 5x5 and native-pixel central crop."""
    w, h = rgb.size
    grids = {}
    for count in (3, 5):
        sample = rgb.copy()
        if count == 5 or w * h > 1024 * 1024:
            sample.thumbnail((256, 256), Image.Resampling.LANCZOS)
        grid = Image.new("RGB", (sample.width * count, sample.height * count))
        for y in range(count):
            for x in range(count):
                grid.paste(sample, (x * sample.width, y * sample.height))
        grids[f"{count}x{count}"] = grid
    cross = Image.new("RGB", (w * 2, h * 2))
    for y in range(2):
        for x in range(2):
            cross.paste(rgb, (x * w, y * h))
    half_x, half_y = min(w // 2, 256), min(h // 2, 256)
    grids["seam_detail"] = cross.crop((w - half_x, h - half_y, w + half_x, h + half_y))
    return grids


def evaluate(root, name, profile_id, *, seamless=False, request=None, expected_sha256=None):
    """Return (serializable report, preview images). Does not write anything."""
    root = Path(root).resolve()
    source = safe_path(root, name)
    registry = Registry(root)
    report = {"validator_version": VERSION, "source": name, "source_sha256": None,
              "profile": {"id": profile_id, "path": None, "schema_version": None, "sha256": None},
              "checks": {}, "metrics": {}, "assessments": {}, "evidence": {},
              "registry_gate_claims": None}
    images = {}
    try:
        registry.profile(profile_id)  # B1's exact-one-profile and v1.0 schema checks.
        profile_path = next(path for path in (f"art/profiles/{profile_id}.json",
                                            f"art/presets/{profile_id}.json")
                            if (root / path).is_file())
        profile = json.loads((root / profile_path).read_text(encoding="utf-8"))
        report["profile"].update(path=profile_path, schema_version=profile["schema_version"],
                                 sha256=sha256(root / profile_path))
        check(report, "style_profile", "PASS", "Unique v1.0 profile resolves and validates via B1")
    except (RegistryError, OSError, ValueError, TypeError) as exc:
        profile = None
        check(report, "style_profile", "FAIL", str(exc))

    if request is None:
        check(report, "asset_metadata", "REVIEW_REQUIRED", "No B1 request supplied; provenance, usage and delivery intent unverified")
    else:
        try:
            registry.schema(registry.request_validator, request)
            if request["approval"]["status"] not in ("draft", "art_approved", "generated", "qc_pending"):
                raise QAError("B2 cannot accept a claimed QC/import/final approval")
            if any(gate["result"] != "pending" or gate["evidence"] or "reviewer" in gate
                   for gate in request["quality_gates"].values()):
                raise QAError("B2 cannot accept human gate claims in request metadata")
            if request["style_profile_id"] != profile_id or request["asset_type"] not in ("image", "tileable_texture"):
                raise QAError("request profile or asset type does not match texture QA")
            if request["delivery"]["tiling_required"] and not seamless:
                raise QAError("request requires tiling: use --seamless")
            check(report, "asset_metadata", "PASS", "B1 v1.0 request structure and pending-gate intent validated; content still needs human verification")
        except (RegistryError, QAError, KeyError, TypeError) as exc:
            check(report, "asset_metadata", "FAIL", str(exc))

    if not source.is_file():
        check(report, "file", "FAIL", "Source file missing")
        return finish(report), images
    size = source.stat().st_size
    report["metrics"]["file_bytes"] = size
    report["source_sha256"] = sha256(source)
    check(report, "file", "PASS" if size else "FAIL", f"Existing file: {size} bytes")
    pinned = (request or {}).get("delivery", {}).get("artifact_sha256")
    expected = expected_sha256 or pinned
    check(report, "sha256", "REVIEW_REQUIRED" if not expected else ("PASS" if expected == report["source_sha256"] else "FAIL"),
          f"actual={report['source_sha256']}; expected={expected or 'not supplied'}")
    if not re.fullmatch(r"[0-9a-f]{64}", expected or "" ) and expected is not None:
        check(report, "sha256", "FAIL", "Expected SHA-256 must be 64 lowercase hex characters")
    if pinned and pinned != report["source_sha256"]:
        check(report, "sha256", "FAIL", f"B1 request deliverable hash mismatch: {pinned}")
    try:
        with Image.open(source) as image:
            fmt, mode, (w, h) = image.format, image.mode, image.size
            if w * h > MAX_PIXELS:
                raise QAError(f"decoded pixel count exceeds safety cap {MAX_PIXELS}")
            image.load()  # Detect truncation/corrupt pixels, not only headers.
            if fmt not in FORMATS or source.suffix.lower() not in ({".jpg", ".jpeg"} if fmt == "JPEG" else {"." + FORMATS[fmt]}):
                raise QAError(f"unsupported format/extension: {fmt}, {source.suffix}")
            rgb = image.convert("RGB")
            alpha = image.convert("RGBA").getchannel("A").getextrema() if "A" in image.getbands() or "transparency" in image.info else (255, 255)
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        check(report, "readability", "FAIL", str(exc))
        return finish(report), images
    report["metrics"].update(format=fmt, mode=mode, dimensions=[w, h],
                             alpha_range=list(alpha), decoded_bytes_estimate=w * h * len(image.getbands()),
                             rgba_runtime_bytes_estimate=w * h * 4)
    check(report, "readability", "PASS", "Full image decoded successfully")
    check(report, "pixel_mode", "PASS" if mode in ("RGB", "RGBA", "L") else "REVIEW_REQUIRED",
          f"mode={mode}; alpha range={alpha}; alpha/greyscale intent needs visual review" if mode != "RGB" or alpha != (255, 255) else "RGB opaque")
    if alpha != (255, 255):
        check(report, "transparency", "REVIEW_REQUIRED", f"Nonopaque alpha range {alpha}; inspect use and edge halos")
    else:
        check(report, "transparency", "PASS", "Opaque")
    if request is not None and report["checks"]["asset_metadata"]["result"] == "PASS":
        delivery = request["delivery"]
        check(report, "delivery", "PASS" if (w, h, FORMATS[fmt]) == (delivery["width_px"], delivery["height_px"], delivery["format"]) else "FAIL",
              f"actual={w}x{h} {FORMATS[fmt]}; requested={delivery['width_px']}x{delivery['height_px']} {delivery['format']}")
    else:
        check(report, "delivery", "REVIEW_REQUIRED", "No validated request dimensions/format")
    if profile:
        budget = profile["budgets"]
        check(report, "texture_budget", "PASS" if max(w, h) <= budget["max_texture_edge_px"] and size <= budget["max_texture_bytes"] else "FAIL",
              f"edge={max(w,h)}/{budget['max_texture_edge_px']} px; file={size}/{budget['max_texture_bytes']} bytes")
        report["metrics"]["budget"] = budget
    else:
        check(report, "texture_budget", "REVIEW_REQUIRED", "Profile budget unavailable")

    stats = proxies(rgb)
    report["metrics"]["style_proxies"] = stats
    max_noise, max_tone, guidance = RULES.get(profile_id, (None, None, "Compare against the game Art Bible"))
    if max_noise is not None:
        flagged = stats["high_frequency_residual_std"] > max_noise or stats["broad_tone_std"] > max_tone
        check(report, "style_proxy", "REVIEW_REQUIRED", f"{guidance}; screening limits residual_std={max_noise}, broad_std={max_tone}; {'flagged for closer inspection' if flagged else 'no proxy alert'}")
    else:
        check(report, "style_proxy", "REVIEW_REQUIRED", guidance)
    report["assessments"]["style_compliance"] = {"result": "REVIEW_REQUIRED", "detail": "Material, silhouette, palette and genre judgment require a human at intended scale"}
    report["assessments"]["in_engine_suitability"] = {"result": "REVIEW_REQUIRED", "detail": "UV, filtering, compression, lighting and target device untested"}
    if seamless:
        raw = edge_stats(rgb)
        broad = edge_stats(rgb.filter(ImageFilter.GaussianBlur(8)))
        report["metrics"].update(raw_edges=raw, blurred_radius_8_edges=broad)
        pixels = np.asarray(rgb)
        exact = bool(np.array_equal(pixels[:, 0], pixels[:, -1])
                     and np.array_equal(pixels[0], pixels[-1]))
        report["assessments"]["mathematical_continuity"] = {"result": "PASS" if exact else "FAIL", "detail": "Exact equality of opposing RGB edge pixels on both axes"}
        ratios = (raw["vertical_ratio"], raw["horizontal_ratio"])
        seam_ok = all(r is not None and r <= 1.25 for r in ratios)
        tone_ok = broad["vertical_edge_mean"] <= 8 and broad["horizontal_edge_mean"] <= 8
        check(report, "edge_screen", "PASS" if seam_ok else "FAIL", f"right-left/neighbor={ratios[0]}, bottom-top/neighbor={ratios[1]}; proposed max=1.25")
        check(report, "tone_screen", "PASS" if tone_ok else "FAIL", f"8px-blurred edge means={broad['vertical_edge_mean']}, {broad['horizontal_edge_mean']}; screening max=8")
        motif = stats["broad_tone_std"] > 6 and stats["broad_tone_p99_deviation"] > 15
        check(report, "repeated_motif_screen", "REVIEW_REQUIRED" if motif else "PASS",
              f"broad_std={stats['broad_tone_std']}, p99_deviation={stats['broad_tone_p99_deviation']}; {'potential repeated landmark' if motif else 'no large-scale motif proxy alert'}; inspect 5x5")
        report["assessments"]["visual_seamlessness"] = {"result": "REVIEW_REQUIRED", "detail": "Inspect both grids and center joins; numerical screens do not establish visual acceptability"}
        report["assessments"]["repetition_quality"] = {"result": "REVIEW_REQUIRED", "detail": "Inspect distinctive repeated motifs in 5x5 at use scale"}
        images = previews(rgb)
        report["metrics"]["preview_dimensions"] = {key: list(image.size) for key, image in images.items()}
        report["metrics"]["preview_policy"] = "3x3 native up to 1024x1024 source; otherwise each tile downscaled to <=256x256. 5x5 downscaled to <=256x256 per tile; seam detail native-pixel crop."
    else:
        for key in ("edge_screen", "tone_screen", "repeated_motif_screen"):
            check(report, key, "NOT_APPLICABLE", "Seamless testing not requested")
        for key in ("mathematical_continuity", "visual_seamlessness", "repetition_quality"):
            report["assessments"][key] = {"result": "NOT_APPLICABLE", "detail": "Seamless testing not requested"}
    return finish(report), images


def finish(report):
    for name in ("mathematical_continuity", "visual_seamlessness", "repetition_quality",
                 "style_compliance", "in_engine_suitability"):
        report["assessments"].setdefault(name, {"result": "NOT_APPLICABLE" if name == "mathematical_continuity" else "REVIEW_REQUIRED",
                                                "detail": "Cannot evaluate without a readable image or complete metadata"})
    results = [value["result"] for value in report["checks"].values()]
    report["automated_result"] = "FAIL" if "FAIL" in results else ("REVIEW_REQUIRED" if "REVIEW_REQUIRED" in results else "PASS")
    report["overall_result"] = "FAIL" if "FAIL" in results else "REVIEW_REQUIRED"
    report["registry_gate_claims"] = {name: {"result": "pending", "evidence": []} for name in
                                      ("originality", "rights", "style", "technical", "performance", "tiling", "in_engine")}
    return report


def assessment(report):
    lines = [f"# B2 texture QA — {report['source']}", "", f"**Overall: {report['overall_result']}** (automated: {report['automated_result']}). No human gate pass or registry transition is claimed.", "",
             f"Validator: `{VERSION}` · Source SHA-256: `{report['source_sha256']}`", f"Profile: `{report['profile']['path']}` version `{report['profile']['schema_version']}` SHA-256 `{report['profile']['sha256']}`", "", "## Automated checks", "",
             "| Check | Result | Evidence / reason |", "| --- | --- | --- |"]
    for name, item in report["checks"].items():
        lines.append(f"| {name} | {item['result']} | {item['detail'].replace('|', '/')} |")
    lines += ["", "## Visual and in-engine assessments", "", "| Assessment | Result | Required review |", "| --- | --- | --- |"]
    for name, item in report["assessments"].items():
        lines.append(f"| {name} | {item['result']} | {item['detail'].replace('|', '/')} |")
    lines += ["", "## Evidence", ""]
    lines += [f"- {key}: `{path}`" for key, path in report["evidence"].items()]
    lines += ["", "B1 gate entries remain pending. A named, independent QC reviewer must verify rights, originality, style, flat-image tiling, and technical/performance evidence before any separate B1 `qc_passed` event. In-engine suitability needs a later target-device check.", ""]
    return "\n".join(lines)


def write_evidence(root, out_dir, report, images):
    """Write new-only project-local B1 evidence references; never touch registry journal."""
    root = Path(root).resolve()
    folder = safe_path(root, out_dir, must_exist=False)
    if not out_dir.startswith("registry/evidence/"):
        raise QAError("evidence must be under registry/evidence/")
    if folder.exists() and not folder.is_dir():
        raise QAError("evidence output is not a directory")
    if not folder.parent.is_dir():
        raise QAError("evidence parent directory must already exist")
    token = hashlib.sha256(report["source"].encode()).hexdigest()[:12]
    stem = f"{Path(report['source']).stem}-{token}-{(report['source_sha256'] or 'missing')[:12]}"
    files = {"json": f"{stem}.json", "markdown": f"{stem}.md"}
    files.update({key: f"{stem}-{key}.png" for key in images})
    if any((folder / filename).exists() for filename in files.values()):
        raise QAError("evidence already exists; refusing overwrite")
    report["evidence"] = {key: f"{out_dir}/{filename}" for key, filename in files.items()}
    folder.mkdir(exist_ok=True)
    for key, image in images.items():
        with (folder / files[key]).open("xb") as stream:
            image.save(stream, format="PNG")
    with (folder / files["json"]).open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    with (folder / files["markdown"]).open("x", encoding="utf-8") as stream:
        stream.write(assessment(report))
    return report["evidence"]
