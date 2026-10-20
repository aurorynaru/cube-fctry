"""Make a lossless 3x3 tile preview and measure opposite-edge discontinuity.

Run from any directory: python tool/texture_seam_check.py
Requires Pillow and NumPy. Does not modify the source image or workflow.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "7c1a96f1_000.png"
PREVIEW = ROOT / "stone-texture-3x3-preview.png"
DETAIL = ROOT / "stone-texture-seam-detail.png"
EVIDENCE = ROOT / "stone-texture-seam-evidence.json"


def summary(pixel_differences):
    """Absolute RGB difference averaged over channels, on an 8-bit scale."""
    per_pixel = np.mean(np.abs(pixel_differences), axis=-1)
    return {
        "mean_abs_rgb": round(float(per_pixel.mean()), 3),
        "median_abs_rgb": round(float(np.median(per_pixel)), 3),
        "p95_abs_rgb": round(float(np.percentile(per_pixel, 95)), 3),
        "max_abs_rgb": round(float(per_pixel.max()), 3),
    }


def compare_edges(rgb):
    pixels = np.asarray(rgb, dtype=np.float32)
    vertical = summary(pixels[:, -1, :] - pixels[:, 0, :])
    horizontal = summary(pixels[-1, :, :] - pixels[0, :, :])
    interior_vertical = summary(pixels[:, 1:, :] - pixels[:, :-1, :])
    interior_horizontal = summary(pixels[1:, :, :] - pixels[:-1, :, :])
    return {
        "left_to_right_vertical_seam": vertical,
        "top_to_bottom_horizontal_seam": horizontal,
        "ordinary_vertical_neighbors": interior_vertical,
        "ordinary_horizontal_neighbors": interior_horizontal,
        "vertical_seam_to_neighbor_mean_ratio": round(
            vertical["mean_abs_rgb"] / interior_vertical["mean_abs_rgb"], 3
        ),
        "horizontal_seam_to_neighbor_mean_ratio": round(
            horizontal["mean_abs_rgb"] / interior_horizontal["mean_abs_rgb"], 3
        ),
    }


def main():
    source_bytes = SOURCE.read_bytes()
    with Image.open(SOURCE) as image:
        if image.format != "PNG" or image.size != (1024, 1024):
            raise ValueError(f"Expected a 1024x1024 PNG, got {image.format} {image.size}")
        rgb = image.convert("RGB")
        mode = image.mode

    width, height = rgb.size
    preview = Image.new("RGB", (width * 3, height * 3))
    for row in range(3):
        for column in range(3):
            preview.paste(rgb, (column * width, row * height))
    preview.save(PREVIEW, format="PNG")

    # Both join directions intersect at (1024, 1024); no guides obscure pixels.
    preview.crop((width - 384, height - 384, width + 384, height + 384)).save(
        DETAIL, format="PNG"
    )

    blurred = rgb.filter(ImageFilter.GaussianBlur(radius=8))
    report = {
        "source": SOURCE.name,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_bytes": len(source_bytes),
        "source_format": "PNG",
        "source_mode": mode,
        "source_dimensions": [width, height],
        "preview": PREVIEW.name,
        "preview_dimensions": list(preview.size),
        "seam_detail": DETAIL.name,
        "comparison": "Absolute RGB differences (0-255) across opposite edges versus adjacent pixels inside the original image. A vertical join uses its right and left columns; a horizontal join uses its bottom and top rows. Gaussian blur radius 8 px compares broad color/tone changes.",
        "raw": compare_edges(rgb),
        "blurred_radius_8_px": compare_edges(blurred),
        "limitation": "Metrics and planar image preview do not measure 3D appearance, lighting, UV mapping, compression, or Roblox rendering. No threshold alone determines visual acceptability.",
    }
    EVIDENCE.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
