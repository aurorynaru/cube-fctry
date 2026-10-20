"""Non-destructive B2.1 stone derivatives and matched-scale visual comparison.

Run from the project root: python workflows/textures/b21_derivatives.py
Requires the existing Pillow installation. Refuses to replace any output.
"""

from pathlib import Path
import hashlib

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "workflows/textures/stone-seamless-v4.png"
OUT = ROOT / "workflows/textures/b21"
EXPECTED = "ab79d9c624862469d7a969020110eb5dbbed2e91d85a9c7ace68d376b3422849"


def save_new(image, path, **kwargs):
    with path.open("xb") as stream:
        image.save(stream, format="PNG", **kwargs)


def main():
    if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != EXPECTED:
        raise ValueError("Corrected v4 input hash changed; refusing derivatives")
    with Image.open(SOURCE) as source:
        source.load()
        if source.size != (1024, 1024) or source.mode != "RGB":
            raise ValueError("Expected 1024x1024 RGB corrected texture")
        original = source.copy()
    resized = original.resize((512, 512), Image.Resampling.LANCZOS)
    outputs = [OUT / "stone-seamless-v4-512-lanczos.png",
               OUT / "stone-seamless-v4-lossless-opt.png",
               OUT / "stone-seamless-v4-comparison.png"]
    if any(path.exists() for path in outputs):
        raise FileExistsError("B2.1 output already exists; refusing overwrite")
    OUT.mkdir(exist_ok=True)
    save_new(resized, outputs[0], optimize=True, compress_level=9)
    # PNG re-encoding preserves every RGB pixel; only the on-disk representation changes.
    save_new(original, outputs[1], optimize=True, compress_level=9)

    # Equal display footprints: top row full tile, bottom row the same central
    # 512px source area (the 512 derivative is scaled 2x to match 1024 scale).
    canvas = Image.new("RGB", (1536, 1060), "#202020")
    draw = ImageDraw.Draw(canvas)
    variants = [
        ("v4 1024 source", original),
        ("v4 lossless 1024", original),
        ("v4 Lanczos 512", resized.resize((1024, 1024), Image.Resampling.NEAREST)),
    ]
    for column, (label, tile) in enumerate(variants):
        x = 512 * column
        draw.text((x + 8, 6), label, fill="white")
        canvas.paste(tile.resize((512, 512), Image.Resampling.LANCZOS), (x, 20))
        draw.text((x + 8, 532), "center at 1024-pixel source scale", fill="white")
        canvas.paste(tile.crop((256, 256, 768, 768)), (x, 548))
    save_new(canvas, outputs[2], optimize=True)
    for path in outputs:
        print(f"{path.relative_to(ROOT).as_posix()}: {path.stat().st_size} bytes")
    print("Lossless RGB pixel identity:", original.tobytes() == Image.open(outputs[1]).tobytes())


if __name__ == "__main__":
    main()
