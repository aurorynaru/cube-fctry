"""Deterministic, non-destructive seamless-stone experiment.

Run from any directory: python workflows/textures/seamless_stone.py --versions v1 v2
For this source's localized-vein iterations: ... --versions v3 v4
For another project-local 1024px texture, use --source, --out-dir, --stem
and v1/v2. v3/v4 use a mask tailored to the original stone image.
Requires pre-existing NumPy, OpenCV and Pillow. Outputs are placed alongside
this script and are never overwritten; source PNG and ComfyUI graph are read-only.
"""

import argparse
import hashlib
import json
from pathlib import Path
import re

import cv2
import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / "7c1a96f1_000.png"
BASELINE = ROOT / "stone-texture-seam-evidence.json"


def save_new(image, path):
    with path.open("xb") as output:
        image.save(output, format="PNG")


def homogenize(rgb, low_strength, highlight_strength):
    """Suppress broad pale motifs while retaining mineral-grain frequencies."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    light = lab[:, :, 0].astype(np.float32)
    low = cv2.GaussianBlur(light, (0, 0), 48)
    light -= low_strength * (low - low.mean())
    neighborhood = cv2.GaussianBlur(light, (0, 0), 12)
    light -= highlight_strength * np.maximum(light - neighborhood - 12, 0)
    lab[:, :, 0] = np.clip(np.rint(light), 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def replace_distinctive_vein(rgb):
    """Blend a mundane exemplar onto the unique pale diagonal in this source.

    This is source-specific: change the polygon/patch for other material images.
    The donor is another in-image stone region, not synthesized or downloaded.
    """
    donor = np.roll(rgb, (-490, 290), axis=(0, 1)).astype(np.float32)
    mask = np.zeros(rgb.shape[:2], dtype=np.uint8)
    cv2.polylines(mask, [np.array([[640, 55], [602, 143], [548, 255], [486, 375]],
                                    dtype=np.int32)], False, 255, thickness=115)
    mask = cv2.GaussianBlur(mask, (0, 0), 30).astype(np.float32) / 255.0
    alpha = mask[:, :, None]
    output = rgb.astype(np.float32) * (1 - alpha) + donor * alpha
    return np.clip(np.rint(output), 0, 255).astype(np.uint8)


def center_weight(length, half_flat, half_support):
    """Zero at both outer edges, one across the central seam, smooth in between."""
    distance = np.abs(np.arange(length, dtype=np.float32) - length / 2 + 0.5)
    ramp = np.clip((half_support - distance) / (half_support - half_flat), 0, 1)
    return 0.5 - 0.5 * np.cos(np.pi * ramp)


def correct(rgb, flat, support):
    """Four-way wrap blend: A outer, B fixes x, C fixes y, D fixes cross.

    At outer x only A/C contribute (each continuous there); at outer y only
    A/B contribute. At central x only B/D contribute; at central y only C/D.
    Thus blends never reintroduce the source's discontinuity on a join.
    """
    h, w = rgb.shape[:2]
    ax = center_weight(w, flat, support)[None, :, None]
    ay = center_weight(h, flat, support)[:, None, None]
    pixels = rgb.astype(np.float32)
    a = np.roll(pixels, (h // 2, w // 2), axis=(0, 1))
    b = np.roll(pixels, h // 2, axis=0)
    c = np.roll(pixels, w // 2, axis=1)
    result = ((1 - ax) * (1 - ay) * a + ax * (1 - ay) * b
              + (1 - ax) * ay * c + ax * ay * pixels)
    return np.clip(np.rint(result), 0, 255).astype(np.uint8)


def sharpen_periodic(rgb, amount):
    """Restore fine grain using a wrapped kernel, including across tile edges."""
    pixels = np.pad(rgb.astype(np.float32), ((4, 4), (4, 4), (0, 0)), mode="wrap")
    blurred = cv2.GaussianBlur(pixels, (0, 0), 1.0)[4:-4, 4:-4]
    return np.clip(np.rint(rgb + amount * (rgb - blurred)), 0, 255).astype(np.uint8)


def diff_summary(delta):
    values = np.abs(delta).mean(axis=2)
    return {
        "mean_abs_rgb": round(float(values.mean()), 3),
        "p95_abs_rgb": round(float(np.percentile(values, 95)), 3),
    }


def edge_metrics(image):
    p = np.asarray(image, dtype=np.float32)
    vertical = diff_summary(p[:, -1:, :] - p[:, :1, :])
    horizontal = diff_summary(p[-1:, :, :] - p[:1, :, :])
    inside_x = diff_summary(p[:, 1:, :] - p[:, :-1, :])
    inside_y = diff_summary(p[1:, :, :] - p[:-1, :, :])
    return {
        "right_to_left_vertical_join": vertical,
        "bottom_to_top_horizontal_join": horizontal,
        "ordinary_neighbors_x": inside_x,
        "ordinary_neighbors_y": inside_y,
        "vertical_join_ratio": round(vertical["mean_abs_rgb"] / inside_x["mean_abs_rgb"], 3),
        "horizontal_join_ratio": round(horizontal["mean_abs_rgb"] / inside_y["mean_abs_rgb"], 3),
    }


def texture_stats(rgb):
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    low = cv2.GaussianBlur(gray, (0, 0), 32)
    return {
        "mean_luminance": round(float(gray.mean()), 3),
        "broad_tone_std_radius_32": round(float(low.std()), 3),
        "laplacian_variance": round(float(cv2.Laplacian(gray, cv2.CV_32F).var()), 3),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--versions", nargs="+", choices=("v1", "v2", "v3", "v4"),
                        default=("v1", "v2"))
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--out-dir", type=Path, default=HERE)
    parser.add_argument("--stem", default="stone")
    args = parser.parse_args()
    requested = args.versions
    source = args.source.resolve()
    out_dir = args.out_dir.resolve()
    if not source.is_relative_to(ROOT) or not out_dir.is_relative_to(ROOT):
        raise ValueError("Source and output directory must be inside the project")
    if not out_dir.is_dir() or not re.fullmatch(r"[A-Za-z0-9_-]+", args.stem):
        raise ValueError("Output directory must exist and stem must be a simple filename")
    if source != SOURCE and any(name in ("v3", "v4") for name in requested):
        raise ValueError("v3/v4 vein mask is specific to the original stone image")

    original_bytes = source.read_bytes()
    with Image.open(source) as file:
        if file.format != "PNG" or file.size != (1024, 1024):
            raise ValueError("Expected the original 1024x1024 PNG")
        original = np.asarray(file.convert("RGB"))
    digest = hashlib.sha256(original_bytes).hexdigest()
    if source == SOURCE:
        baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        if digest != baseline["source_sha256"]:
            raise ValueError("Original image hash differs from existing seam evidence")

    variants = {
        "v1": {"low_strength": 0.55, "highlight_strength": 0.35, "flat": 48, "support": 220},
        "v2": {"low_strength": 0.78, "highlight_strength": 0.55, "flat": 64, "support": 256},
        "v3": {"low_strength": 0.72, "highlight_strength": 0.45, "flat": 64, "support": 256,
               "replace_vein": True},
        "v4": {"low_strength": 0.72, "highlight_strength": 0.45, "flat": 64, "support": 256,
               "replace_vein": True, "periodic_sharpen": 0.5},
    }
    working = out_dir / f"{args.stem}-offset-512-working.png"
    paths = []
    for name in requested:
        paths.extend(out_dir / f"{args.stem}-seamless-{name}{suffix}" for suffix in
                     (".png", "-3x3.png", "-join.png", "-metrics.json"))
    if any(path.exists() for path in paths):
        raise FileExistsError("A planned output already exists; choose a new version, do not overwrite")

    offset = np.roll(original, (512, 512), axis=(0, 1))
    if working.exists():
        with Image.open(working) as file:
            if not np.array_equal(np.asarray(file.convert("RGB")), offset):
                raise ValueError("Existing working copy does not match the source's 512x512 offset")
    else:
        save_new(Image.fromarray(offset), working)
    for name in requested:
        settings = variants[name]
        prepared = replace_distinctive_vein(original) if settings.get("replace_vein") else original
        processed = homogenize(prepared, settings["low_strength"], settings["highlight_strength"])
        corrected = correct(processed, settings["flat"], settings["support"])
        if settings.get("periodic_sharpen"):
            corrected = sharpen_periodic(corrected, settings["periodic_sharpen"])
        candidate = Image.fromarray(corrected)
        image_path = out_dir / f"{args.stem}-seamless-{name}.png"
        preview_path = out_dir / f"{args.stem}-seamless-{name}-3x3.png"
        detail_path = out_dir / f"{args.stem}-seamless-{name}-join.png"
        metrics_path = out_dir / f"{args.stem}-seamless-{name}-metrics.json"
        save_new(candidate, image_path)
        preview = Image.new("RGB", (3072, 3072))
        for row in range(3):
            for column in range(3):
                preview.paste(candidate, (1024 * column, 1024 * row))
        save_new(preview, preview_path)
        save_new(preview.crop((640, 640, 1408, 1408)), detail_path)
        result = {
            "source": str(source.relative_to(ROOT)),
            "source_sha256": digest,
            "working_copy": working.name,
            "candidate": image_path.name,
            "preview": preview_path.name,
            "join_detail": detail_path.name,
            "dimensions": [1024, 1024],
            "method": "512x512 circular offset; four-way center-cross wrap blend; LAB luminance low-frequency flattening and highlight attenuation; optional feathered in-image exemplar replacement of pale vein and wrapped-kernel fine-grain sharpening",
            "settings": settings,
            "original_raw": edge_metrics(Image.fromarray(original)),
            "candidate_raw": edge_metrics(candidate),
            "original_blurred_radius_8": edge_metrics(Image.fromarray(original).filter(ImageFilter.GaussianBlur(8))),
            "candidate_blurred_radius_8": edge_metrics(candidate.filter(ImageFilter.GaussianBlur(8))),
            "original_texture_stats": texture_stats(original),
            "candidate_texture_stats": texture_stats(np.asarray(candidate)),
            "note": "Metrics do not replace visual evaluation; no Roblox rendering tested.",
        }
        with metrics_path.open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
        print(f"{name}: {image_path.name}; joins {result['candidate_raw']['vertical_join_ratio']}x / {result['candidate_raw']['horizontal_join_ratio']}x")


if __name__ == "__main__":
    main()
