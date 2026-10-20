# Seamless stone correction — local deterministic pipeline

## Result

**PASS for the flat-image 3×3 repeat check:** `stone-seamless-v4.png` (1024×1024 RGB PNG). No obvious straight horizontal or vertical join was seen in `stone-seamless-v4-3x3.png` and `stone-seamless-v4-join.png`. The large pale diagonal vein that dominated the original repeat is substantially reduced; fine grain remains crisp. Some smaller pale markings still repeat, so very large unbroken surfaces may benefit from material variation. Roblox UV mapping, compression and lighting were not tested; the result is not an in-engine approval.

## Method and reproduction

`seamless_stone.py` is a local, deterministic Pillow/NumPy/OpenCV script. It verifies the source against the prior seam-evidence SHA-256, saves an exact 512×512 circular-offset working copy, then uses a four-way blend of source and axis-shifted copies to repair the central vertical/horizontal cross without reintroducing the source discontinuity at the outer edges. LAB luminance flattening reduces broad light motifs. v3/v4 also blend a less conspicuous in-image stone patch over the source-specific pale vein; v4 restores fine grain with a wrap-aware sharpening kernel.

The script writes new-only PNGs, 3×3 previews, center-join crops and JSON metrics. It refuses to overwrite existing outputs and never edits the input or FLUX 3 workflow. To reproduce in a fresh output folder **inside this project**, run:

```powershell
python workflows/textures/seamless_stone.py --versions v1 v2 v3 v4 --out-dir workflows/textures/new-run
```

Create that project-local output folder first; no dependencies are installed by the script. For another project-local 1024×1024 texture, pass `--source`, `--out-dir`, `--stem` and use v1/v2. The v3/v4 vein-replacement coordinates and donor patch are tailored to `7c1a96f1_000.png`; adapting that mask is necessary for a different image. Existing candidate outputs in this folder demonstrate all four variants.

## Evidence and comparison

Original: `../../7c1a96f1_000.png`, SHA-256 `71891bc7e2c5c2868ff82d88eedfd30341d1b4c86c4a4b52037d27c8b79535a3`; baseline preview/metrics: `../../stone-texture-3x3-preview.png` and `../../stone-texture-seam-evidence.json`. Working copy: `stone-offset-512-working.png`.

| Image | Vertical join / ordinary-neighbor ratio | Horizontal join / ordinary-neighbor ratio | Visual result |
| --- | ---: | ---: | --- |
| Original | 1.902× | 2.395× | FAIL: obvious joins and repeated vein |
| `stone-seamless-v1.png` | 1.029× | 1.107× | Joins improved; original vein still obvious |
| `stone-seamless-v2.png` | 1.038× | 1.116× | Same repeated vein; broader tones flatter |
| `stone-seamless-v3.png` | 0.932× | 1.150× | Vein reduced and joins unobtrusive, but grain softer |
| **`stone-seamless-v4.png`** | **0.941×** | **1.146×** | **PASS for flat tiling: no obvious join, vein reduced, grain restored** |

Values are mean absolute RGB differences over 8-bit channels for opposite-edge neighbors divided by ordinary adjacent-pixel differences in the same image. For v4, right→left is 13.902 vs 14.766; bottom→top is 17.533 vs 15.302. On the original those values were 25.535 vs 13.422 and 33.244 vs 13.878. Sharpening raises both texture and boundary differences; ratios are context, not pass/fail thresholds. The v4 broad-tone standard deviation at 32-pixel blur is 3.036 vs 7.44 original; Laplacian variance is 2752.958 vs 2082.193 original. These proxy metrics do not prove perceptual quality.

Each `stone-seamless-vN-metrics.json` records raw and 8-pixel-blurred edge comparisons plus texture statistics. Each `stone-seamless-vN-3x3.png` is an exact 3072×3072 repeat, and each `stone-seamless-vN-join.png` shows the center join at native resolution. The original and reusable ComfyUI workflow remain untouched. No AI image editing, model download, dependency installation, Studio edit or asset upload occurred.

**Next step:** If the texture is to be deployed, separately inspect it with the intended Roblox UV scale, filtering, compression and lighting. For unusually large expanses, consider a secondary detail/variation layer to hide remaining small repeated markings. No further correction iteration is required for the present flat-image acceptance check.
