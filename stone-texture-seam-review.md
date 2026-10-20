# FLUX 3 stone texture — independent repeatability check

**Result: FAIL** for seamless repeating Roblox surfaces. This is a planar texture assessment, not a Roblox render or asset-import test.

## Source and preview

- Original: `7c1a96f1_000.png`, PNG RGB, 1024×1024, 2,311,490 bytes, SHA-256 `71891bc7e2c5c2868ff82d88eedfd30341d1b4c86c4a4b52037d27c8b79535a3`.
- 3×3 unaltered tile preview: `stone-texture-3x3-preview.png`, 3072×3072.
- Join close-up: `stone-texture-seam-detail.png`; the central cross is the right-to-left and bottom-to-top joins.
- Machine-readable measurements: `stone-texture-seam-evidence.json`, reproduced by `python tool/texture_seam_check.py` (Pillow and NumPy). The script leaves the original PNG and workflow untouched.

## Findings

| Boundary | Mean absolute RGB difference, 0–255 | Mean for ordinary neighboring pixels | Seam / neighbor |
| --- | ---: | ---: | ---: |
| Right edge → left edge (vertical join) | 25.535 | 13.422 | 1.902× |
| Bottom edge → top edge (horizontal join) | 33.244 | 13.878 | 2.395× |

At an 8-pixel Gaussian blur, the corresponding opposite-edge differences are 15.683 and 21.635, versus 0.433 and 0.343 for ordinary neighboring pixels in the blurred image. This indicates broad tone/feature discontinuity as well as fine-pixel mismatch. The blurred ratios are sensitive to the smoothing radius and are not an acceptance threshold.

Visually, pale mineral features and cracks stop and restart at both joins. The horizontal join is particularly apparent in the 3×3 preview; the vertical join is also visible in the close-up. The same distinctive light vein repeats nine times, adding an obvious grid pattern on a large surface. The image is usable as a single non-repeating stone patch, but does not pass as a seamless tile.

## Suggested correction (not performed)

Create a **separate derivative** from the source using a 512×512 wrap/offset so all four original edges meet in the center. Heal the central cross with clone/content-aware editing while preserving the stone's grain; then blend opposite boundaries and recheck a 3×3 preview and edge statistics. Reduce or vary the distinctive bright vein if the repeated motif remains obvious. Keep the original untouched until a corrected copy is reviewed and approved.

## Limits

The preview and metrics test pixel continuity in a flat 3×3 repeat. They do not test UV scaling, sampling/filtering, compression, lighting, material blending, perspective, or appearance in Roblox Studio. No Studio changes, asset uploads, or new AI generation were made.
