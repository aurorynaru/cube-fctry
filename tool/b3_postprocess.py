"""Optional, non-destructive B3 post-processing adapters.

Only two generic operations are offered:

- ``generic_wrap_blend`` reuses the geometric four-way wrap blend from the
  existing seamless-stone experiment. It does not use the stone-specific vein
  mask, LAB flattening, or sharpening settings.
- ``lossless_optimize`` re-encodes a PNG without changing decoded pixels.

Both write new files exclusively and never overwrite a source or candidate.
"""

import hashlib
import importlib.util
from pathlib import Path

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SEAMLESS_SCRIPT = ROOT / "workflows/textures/seamless_stone.py"


class PostprocessError(ValueError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_seamless_module():
    if not SEAMLESS_SCRIPT.is_file():
        raise PostprocessError("existing seamless correction script is missing")
    spec = importlib.util.spec_from_file_location("b3_seamless_source", SEAMLESS_SCRIPT)
    if spec is None or spec.loader is None:
        raise PostprocessError("cannot load existing seamless correction script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _read_rgb(path):
    with Image.open(path) as image:
        image.load()
        if image.format != "PNG" or image.mode not in ("RGB", "RGBA", "L"):
            raise PostprocessError("post-processing requires an existing PNG")
        return image.convert("RGB").copy(), image.mode


def generic_wrap_blend(source, destination, *, flat=None, support=None):
    """Apply only the generic geometric wrap blend from seamless_stone.py.

    Defaults scale with the source (1/16 flat and 1/4 support), which matches
    the existing 1024px stone settings without hard-coding stone dimensions.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise PostprocessError(f"source missing: {source}")
    if destination.exists():
        raise PostprocessError(f"refusing to overwrite: {destination}")
    rgb, original_mode = _read_rgb(source)
    edge = min(rgb.size)
    flat = max(4, edge // 16) if flat is None else int(flat)
    support = max(flat * 2 + 2, edge // 4) if support is None else int(support)
    if flat < 1 or support <= flat:
        raise PostprocessError("invalid wrap blend parameters")
    module = _load_seamless_module()
    corrected = module.correct(np.asarray(rgb), flat, support)
    result = Image.fromarray(corrected, mode="RGB")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        result.save(stream, format="PNG")
    return {
        "method": "generic_wrap_blend",
        "source": source.name,
        "output": destination.name,
        "source_sha256": sha256(source),
        "output_sha256": sha256(destination),
        "size_bytes": destination.stat().st_size,
        "dimensions": list(result.size),
        "original_mode": original_mode,
        "parameters": {"flat": flat, "support": support},
        "note": "Uses only the geometric wrap blend; no stone-specific vein replacement or LAB homogenization.",
    }


def lossless_optimize(source, destination, *, compress_level=9):
    """Re-encode a PNG losslessly and verify decoded RGB/RGBA pixel identity."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if not source.is_file():
        raise PostprocessError(f"source missing: {source}")
    if destination.exists():
        raise PostprocessError(f"refusing to overwrite: {destination}")
    with Image.open(source) as image:
        image.load()
        if image.format != "PNG":
            raise PostprocessError("lossless optimization requires a PNG source")
        original = image.copy()
        original_bytes = original.tobytes()
        mode = original.mode
        dimensions = list(original.size)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as stream:
        original.save(stream, format="PNG", optimize=True, compress_level=compress_level)
    with Image.open(destination) as check:
        check.load()
        if check.mode != mode or check.size != original.size or check.tobytes() != original_bytes:
            destination.unlink(missing_ok=True)
            raise PostprocessError("optimized PNG is not pixel-identical; derivative removed")
    return {
        "method": "lossless_png_optimize",
        "source": source.name,
        "output": destination.name,
        "source_sha256": sha256(source),
        "output_sha256": sha256(destination),
        "size_bytes": destination.stat().st_size,
        "source_bytes": source.stat().st_size,
        "dimensions": dimensions,
        "mode": mode,
        "parameters": {"compress_level": compress_level, "optimize": True},
        "pixel_identical": True,
    }
