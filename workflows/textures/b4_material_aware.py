"""B4 non-destructive, material-aware stone-paving seam correction.

Run from the project root:
    python workflows/textures/b4_material_aware.py

Strategy A: grout-routed border graft. Min-cut routes a border band along the
dark grout network, then fills that band with 512-offset copies of the same
texture so opposite edges meet along grout instead of through stone faces.

Strategy B: directional 24 px edge taper. The border band is blended toward a
circularly rolled copy over a narrow cosine ramp; the interior is untouched.
The roll offset is tuned to the source so the two bands straddling the wrap
have closely matching local tone (B2 blurred-edge tone 3.93/5.00).

Both candidates are new files. The B3 raw source and its generic derivative are
read-only. Outputs are refused if any planned path already exists. The script
uses only the existing Pillow, NumPy and SciPy installations. Run the unchanged
B2 validator afterward for authoritative seam evidence.
"""

import argparse
import hashlib
import json
from collections import deque
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import sparse
from scipy.sparse.csgraph import maximum_flow


ROOT = Path(__file__).resolve().parents[2]
B3_DIR = ROOT / "outputs/generated/b3-stone-paving-0001"
SOURCE = B3_DIR / "b3-stone-paving-0001.png"
GENERIC = B3_DIR / "b3-stone-paving-0001-seamless.png"
SOURCE_SHA256 = "85DFB0578BC0159B450E0F994A9A6BB15976C69CBB5B9C1D5EA0DCB73B12E6C3"
GENERIC_SHA256 = "4C58C683605B321266FABC0C5DEE927CCBE7BC36BFA0C37FE645A870477EDCC5"
OUT_DIR = ROOT / "outputs/b4-stone-correction"


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def save_new(image, path):
    with path.open("xb") as stream:
        image.save(stream, format="PNG")


def checked_input(path, expected, label):
    path = path.resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise ValueError(f"{label} must be a project-local file")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{label} hash changed: {actual}")
    with Image.open(path) as file:
        if file.format != "PNG" or file.size != (1024, 1024) or file.mode != "RGB":
            raise ValueError(f"{label} must be a 1024x1024 RGB PNG")
        return np.asarray(file.convert("RGB"))


def max_flow_side(pair, source_cost, sink_cost):
    """Return the source-side mask of a two-terminal grid cut.

    pair is the undirected edge cost between 4-neighbours. source_cost and
    sink_cost are unary costs. Nodes on the source side are kept.
    """
    height, width = pair.shape
    count = height * width
    index = np.arange(count, dtype=np.int32).reshape(height, width)
    rows, cols, caps = [], [], []

    def add(a, b, capacity):
        rows.append(np.asarray(a, dtype=np.int64).ravel())
        cols.append(np.asarray(b, dtype=np.int64).ravel())
        caps.append(np.broadcast_to(np.asarray(capacity, dtype=np.int32), np.shape(a)).ravel())

    add(np.full((height, width), count), index, source_cost)
    add(index, np.full((height, width), count + 1), sink_cost)
    left, right = index[:, :-1], index[:, 1:]
    weight = np.minimum(pair[:, :-1], pair[:, 1:])
    add(left, right, weight)
    add(right, left, weight)
    top, bottom = index[:-1, :], index[1:, :]
    weight = np.minimum(pair[:-1, :], pair[1:, :])
    add(top, bottom, weight)
    add(bottom, top, weight)
    graph = sparse.coo_matrix(
        (np.concatenate(caps), (np.concatenate(rows), np.concatenate(cols))),
        shape=(count + 2, count + 2),
    ).tocsr()
    flow = maximum_flow(graph, count, count + 1)
    residual = (graph - flow.flow).tocsr()
    seen = np.zeros(count + 2, dtype=bool)
    seen[count] = True
    queue = deque([count])
    indptr, indices, values = residual.indptr, residual.indices, residual.data
    while queue:
        node = queue.popleft()
        for position in range(indptr[node], indptr[node + 1]):
            other = indices[position]
            if values[position] > 0 and not seen[other]:
                seen[other] = True
                queue.append(other)
    return seen[:count].reshape(height, width)


def grout_graft(image):
    """Strategy A: hard border graft routed through the grout network."""
    height, width = image.shape[:2]
    gray = np.asarray(Image.fromarray(image).convert("L"), dtype=np.float32)
    stone = np.clip((gray - 45.0) / 50.0, 0.0, 1.0)
    pair = (1.0 + 20000.0 * stone * stone).astype(np.int32)
    infinity = 20_000_000
    yy, xx = np.mgrid[0:height, 0:width]
    dx = np.minimum(xx, width - 1 - xx)
    dy = np.minimum(yy, height - 1 - yy)
    distance = np.minimum(dx, dy).astype(np.float64)
    corner_distance = np.sqrt(dx.astype(np.float64) ** 2 + dy.astype(np.float64) ** 2)

    ramp = np.clip((distance - 16.0) / (88.0 - 16.0), 0.0, 1.0)
    ring_band = np.rint(8.0 * (1.0 - ramp)).astype(np.int32)
    ring_interior = np.rint(8.0 * ramp).astype(np.int32)
    ring_band[distance <= 12] = 0
    ring_interior[distance <= 12] = infinity
    ring_band[distance >= 120] = infinity
    ring_interior[distance >= 120] = 0
    interior = max_flow_side(pair, ring_band, ring_interior)

    unary = 8.0
    a_cost = np.rint(np.clip((corner_distance - 64.0) / 128.0, 0.0, 1.0) * unary).astype(np.int32)
    edge_cost = np.rint(np.clip((192.0 - corner_distance) / 128.0, 0.0, 1.0) * unary).astype(np.int32)
    edge_cost[corner_distance <= 12.0] = infinity
    a_cost[distance >= 120] = infinity
    a_cost[(distance <= 3) & (corner_distance > 128.0)] = infinity
    a_cost[(distance <= 3) & (((xx > 320) & (xx < 704)) | ((yy > 320) & (yy < 704)))] = infinity
    corner_a = max_flow_side(pair, edge_cost, a_cost)

    band = ~interior
    a_region = band & corner_a
    top_bottom = band & ~corner_a & (dy <= dx)
    left_right = band & ~corner_a & (dy > dx)

    shifted = {
        "a": np.roll(image, (height // 2, width // 2), axis=(0, 1)),
        "b": np.roll(image, height // 2, axis=0),
        "c": np.roll(image, width // 2, axis=1),
    }
    output = image.copy()
    output[top_bottom] = shifted["b"][top_bottom]
    output[left_right] = shifted["c"][left_right]
    output[a_region] = shifted["a"][a_region]
    share = float(band.mean())
    return output, {"border_band_share": round(share, 4),
                    "top_bottom_pixels": int(top_bottom.sum()),
                    "left_right_pixels": int(left_right.sum()),
                    "corner_pixels": int(a_region.sum())}


def edge_taper(image, width=24.0, offset_y=229, offset_x=93):
    """Strategy B: narrow directional taper toward a tuned circular roll."""
    height, width_px = image.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width_px]
    dx = np.minimum(xx, width_px - 1 - xx).astype(np.float32)
    dy = np.minimum(yy, height - 1 - yy).astype(np.float32)
    distance = np.minimum(dx, dy)
    alpha = np.clip(1.0 - distance / float(width), 0.0, 1.0)
    alpha = (0.5 - 0.5 * np.cos(np.pi * alpha))[..., None].astype(np.float32)
    a = np.roll(image, (offset_y, offset_x), axis=(0, 1)).astype(np.float32)
    b = np.roll(image, offset_y, axis=0).astype(np.float32)
    c = np.roll(image, offset_x, axis=1).astype(np.float32)
    corner = (dx < width) & (dy < width)
    target = np.where((dy <= dx)[..., None], b, c)
    target = np.where(corner[..., None], a, target)
    output = image.astype(np.float32) * (1.0 - alpha) + target * alpha
    return np.clip(np.rint(output), 0, 255).astype(np.uint8), {
        "taper_px": width, "offset_y": offset_y, "offset_x": offset_x}


def tiled(image, count, tile):
    result = Image.new("RGB", (count * tile, count * tile))
    source = Image.fromarray(image)
    if tile != source.width:
        source = source.resize((tile, tile), Image.Resampling.LANCZOS)
    for row in range(count):
        for column in range(count):
            result.paste(source, (tile * column, tile * row))
    return result


def comparison_sheet(raw, generic, graft, taper):
    font = ImageFont.load_default(size=20)
    canvas = Image.new("RGB", (1024, 1040), "#202020")
    draw = ImageDraw.Draw(canvas)
    panels = [("RAW B3", raw), ("GENERIC 512 blend", generic),
              ("A: grout-routed graft", graft), ("B: 24 px edge taper", taper)]
    for position, (label, image) in enumerate(panels):
        x = 512 * (position % 2)
        y = 28 + 512 * (position // 2)
        tile = Image.fromarray(image).resize((512, 512), Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, y))
        draw.rectangle([x, y - 26, x + 230, y], fill="#000000")
        draw.text((x + 6, y - 23), label, fill="white", font=font)
    draw.text((8, 1020), "One-tile view; seams and repetition are assessed on the B2 3x3/5x5 evidence.",
              fill="#d0d0d0", font=font)
    return canvas


def finalists_sheet(raw, graft, taper):
    font = ImageFont.load_default(size=20)
    panel = 512
    canvas = Image.new("RGB", (panel * 3, panel + 30), "#202020")
    draw = ImageDraw.Draw(canvas)
    panels = [("RAW 5x5", raw), ("A 5x5", graft), ("B 5x5", taper)]
    for position, (label, image) in enumerate(panels):
        x = panel * position
        tile = tiled(image, 5, 256)
        tile = tile.resize((panel, panel), Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, 30))
        draw.rectangle([x, 0, x + 150, 30], fill="#000000")
        draw.text((x + 6, 5), label, fill="white", font=font)
    return canvas


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--generic", type=Path, default=GENERIC)
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    parser.add_argument("--stem", default="stone-paving-b4")
    parser.add_argument("--taper-px", type=float, default=24.0)
    parser.add_argument("--offset-y", type=int, default=229)
    parser.add_argument("--offset-x", type=int, default=93)
    args = parser.parse_args()

    source_path = args.source.resolve()
    out_dir = args.out_dir.resolve()
    if not out_dir.is_relative_to(ROOT) or not out_dir.is_dir():
        raise ValueError("Output directory must exist inside the project")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.stem):
        raise ValueError("Stem must be a simple filename")
    image = checked_input(source_path, SOURCE_SHA256, "B3 raw source")
    generic = checked_input(args.generic.resolve(), GENERIC_SHA256, "B3 generic derivative")
    if generic.shape != image.shape:
        raise ValueError("Generic derivative dimensions changed")

    graft, graft_stats = grout_graft(image)
    taper, taper_stats = edge_taper(image, args.taper_px, args.offset_y, args.offset_x)
    if graft.shape != image.shape or taper.shape != image.shape:
        raise ValueError("Candidate dimensions changed")

    paths = {
        "graft": out_dir / f"{args.stem}-grout-graft.png",
        "taper": out_dir / f"{args.stem}-edge-taper.png",
        "comparison": out_dir / f"{args.stem}-comparison.png",
        "finalists": out_dir / f"{args.stem}-finalists-5x5.png",
        "metrics": out_dir / f"{args.stem}-metrics.json",
    }
    if any(path.exists() for path in paths.values()):
        raise FileExistsError("A planned B4 output already exists; refusing overwrite")

    save_new(Image.fromarray(graft), paths["graft"])
    save_new(Image.fromarray(taper), paths["taper"])
    save_new(comparison_sheet(image, generic, graft, taper), paths["comparison"])
    save_new(finalists_sheet(image, graft, taper), paths["finalists"])

    result = {
        "source": source_path.relative_to(ROOT).as_posix(),
        "source_sha256": SOURCE_SHA256,
        "generic_derivative": args.generic.resolve().relative_to(ROOT).as_posix(),
        "generic_sha256": GENERIC_SHA256,
        "dimensions": [1024, 1024],
        "strategy_a": {
            "name": "grout-routed border graft",
            "candidate": paths["graft"].name,
            "sha256": sha256(paths["graft"]),
            "settings": {"stone_pair_cost": "1 + 20000*stone^2",
                         "ring_band_ramp": [16, 88], "ring_band_floor": 12,
                         "ring_band_ceiling": 120, "corner_unary": 8.0},
            **graft_stats,
            "note": "Source-specific corner guards; min-cut may cross narrow grout or stone at depth.",
        },
        "strategy_b": {
            "name": "directional edge taper",
            "candidate": paths["taper"].name,
            "sha256": sha256(paths["taper"]),
            "settings": {"taper_px": args.taper_px, "profile": "cosine",
                         "interior": "unchanged outside the border band",
                         "target": "rolled copy at offset_y/offset_x for top/bottom or "
                                   "left/right, combined offset at corners"},
            **taper_stats,
        },
        "comparison": paths["comparison"].name,
        "finalists_5x5": paths["finalists"].name,
        "b2_evidence_command": (
            "python tool/validate_texture.py "
            f"{paths['graft'].relative_to(ROOT).as_posix()} "
            f"{paths['taper'].relative_to(ROOT).as_posix()} "
            "--profile adventure-fantasy --seamless --out-dir registry/evidence/texture-qa-b4"
        ),
        "note": "B2 reports are authoritative; this JSON records construction only.",
    }
    with paths["metrics"].open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")

    for key in ("graft", "taper", "comparison", "finalists", "metrics"):
        print(f"{paths[key].relative_to(ROOT).as_posix()}: {paths[key].stat().st_size} bytes")
    print("A sha256:", result["strategy_a"]["sha256"])
    print("B sha256:", result["strategy_b"]["sha256"])


if __name__ == "__main__":
    main()
