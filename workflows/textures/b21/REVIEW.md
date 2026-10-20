# B2.1 — stone texture budget investigation (2026-10-17)

## Scope and baseline

The actual B2-1.2 regression reports are in `registry/evidence/texture-qa-native/` for `7c1a96f1_000.png` and `workflows/textures/stone-seamless-v4.png`. Both used `art/presets/adventure-fantasy.json` (schema 1.0, SHA-256 `8b5389b494d503aada07cd982d9189c5caf33a247da3317ec7f2080daa9910cd`) with `--seamless`. This is a valid illustrative fantasy/exploration profile with weathered stone and a 3×3/long-sightline tiling rule. It is a **baseline preset**, not an approved profile for a particular game: `art/games/` and `art/profiles/` have no game-specific Bible/profile, the reports have no B1 request, and no asset is registered. Its phone target of 30 FPS, maximum texture edge of **1024 px**, and maximum PNG file size of **2,097,152 bytes** are proposed values, not device measurements or approved production limits. The reuse rule calls for limited variants of reusable stone trims and landmark pieces. Its material rule asks for mid-frequency edge/contact wear, which a generic stone flat tile alone cannot establish.

| Source / B2 check | Original FLUX 3 | Corrected v4 | Threshold |
| --- | ---: | ---: | ---: |
| PNG compressed file size / `texture_budget` | 2,311,490 B; **FAIL**, 214,338 B over | 2,098,500 B; **FAIL**, 1,348 B over | ≤2,097,152 B |
| Max edge / `texture_budget` | 1024 px; within limit | 1024 px; within limit | ≤1024 px |
| Raw join/neighbor right-left, bottom-top / `edge_screen` | 1.902, 2.395; **FAIL** | 0.941, 1.146; **PASS** | ≤1.25 each |
| Blurred join means vertical, horizontal / `tone_screen` | 15.683, 21.635; **FAIL** | 2.882, 4.918; **PASS** | ≤8 each, 8px blur |
| Repeated-motif proxy / `repeated_motif_screen` | review: broad std 7.422 and p99 21.796 | PASS: 2.983 and 7.326 | flags review only when std >6 **and** p99 >15 |
| Exact opposing edge equality | FAIL | FAIL | informational assessment, not a hard B2 gate |

Both sources are 1024×1024 opaque RGB: estimated decoded RGB bytes **3,145,728**, hypothetical RGBA runtime bytes **4,194,304**. Neither estimate is the compressed PNG size or an actual Roblox GPU allocation. The original's raw edge differences are 25.535/33.244 versus ordinary neighbors 13.422/13.878; v4 is 13.902/17.533 versus 14.766/15.302. The original has both a budget failure and actual seam-screen failures. V4's sole hard automated failure is the **file-byte** subcondition of `texture_budget`, not dimensions, estimated decoded memory, pixel readability, or seam screens. In both reports metadata/delivery, independent expected hash, style, visual judgment, rights and in-engine suitability remain review-required; no B1 gate is passed.

## Derivatives and same-validator results

Reproduce new-only derivatives with `python workflows/textures/b21_derivatives.py` in an empty `workflows/textures/b21/` output location. The script checks v4 SHA-256 `ab79d9c624862469d7a969020110eb5dbbed2e91d85a9c7ace68d376b3422849`, uses the installed Pillow, refuses existing outputs, and creates a 512×512 Lanczos resize and a pixel-identical lossless PNG re-encode (`optimize=True`, `compress_level=9`). The saved derivative files are evidence artifacts; do not re-run the script over them. No new FLUX generation or extra lossy variants were needed.

Both candidates were evaluated by the **unchanged** B2 CLI:

```powershell
python tool/validate_texture.py workflows/textures/b21/stone-seamless-v4-lossless-opt.png workflows/textures/b21/stone-seamless-v4-512-lanczos.png --profile adventure-fantasy --seamless --out-dir registry/evidence/texture-qa-b21
```

Exit code **0** means no hard checks failed, **not** asset approval. Reports and native 3×3, scaled 5×5 and native-pixel seam crop for each candidate are under `registry/evidence/texture-qa-b21/` (output is new-only). The common profile and validator version are unchanged.

| Candidate | SHA-256 | PNG bytes / budget | Pixels; decoded RGB / hypothetical RGBA | Raw ratios V/H | 8px blur V/H | B2 result |
| --- | --- | ---: | --- | --- | --- | --- |
| v4 original | `ab79d9c624862469d7a969020110eb5dbbed2e91d85a9c7ace68d376b3422849` | 2,098,500 / 2,097,152 FAIL | 1024²; 3,145,728 / 4,194,304 B | 0.941 / 1.146 | 2.882 / 4.918 | FAIL |
| [v4 lossless PNG](stone-seamless-v4-lossless-opt.png) | `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a` | **2,038,645 / 2,097,152 PASS** (58,507 B under) | 1024²; 3,145,728 / 4,194,304 B | 0.941 / 1.146 | 2.882 / 4.918 | REVIEW_REQUIRED; no hard failure |
| [v4 512 Lanczos](stone-seamless-v4-512-lanczos.png) | `c92dcbf5e364ac681261f01b81d0c91ed249cee20bafe96394daedd9a437b0e1` | **482,394 / 2,097,152 PASS** | 512²; 786,432 / 1,048,576 B | 0.936 / 1.150 | 2.164 / 4.020 | REVIEW_REQUIRED; no hard failure |

The lossless file is 59,855 B smaller than the corrected source; decoded RGB bytes match exactly (checked by comparing the entire pixel byte stream). This resolves the selected preset's *PNG-byte* failure with no change to appearance, resolution, repetition or decoded-memory estimate. The 512 candidate has one-quarter the decoded pixel count and memory estimate, but changes pixels and detail; its broad repeated motifs are still present. Both pass the raw ≤1.25 and blurred ≤8 screens and the motif proxy has no alert; neither has exact opposing-edge equality (not required for visually acceptable tiling). All B1 gates remain pending.

## Flat-image visual comparison

Opened the [matched-scale comparison](stone-seamless-v4-comparison.png), both candidates' B2 3×3 grids and 5×5 grids, and their center-join crops. The comparison's top row shows the entire tile at equal 512px display footprint; the bottom row shows the same central area at original 1024px source scale, with the 512 version enlarged by nearest neighbor for detail visibility. The lossless variant is pixel-identical to v4: no additional seam or sharpness loss, and the same reduced-but-recurring light patches/fine cracks. Neither candidate grid shows an obvious straight join at the inspected scale. The 512 version retains the broad stone coloring and cracks but visibly loses fine grain and small fissure sharpness when enlarged to the original coverage; at its native resolution the 3×3 is acceptable as a preliminary flat repeat. The 5×5 makes small pale patches recur in both, and the smaller texture repeats at shorter pixel intervals if applied at native texel density. These are subjective offline observations, not a named QC pass or a test at intended Roblox UV scale/camera.

**Recommendation for a future authorized Roblox test:** use the **1024×1024 lossless-optimized v4** as the first candidate. It clears this provisional PNG-byte budget with identical pixels and retains the original corrected texture's detail. Keep 512 as a fallback if an approved game-specific budget or measured target-device performance requires lower resolution; evaluate legibility and repetition at actual UV coverage before choosing it. A smaller on-disk PNG does not imply a corresponding GPU-memory or FPS reduction; Roblox import may re-encode/compress and generate mipmaps. No approved Art Bible, independent expected-hash attestation, rights/reviewer sign-off, Roblox upload, lighting/filtering/compression test, or device FPS measurement exists. The original v4 and FLUX PNG remain unchanged, and no production registry event or approval is claimed. Stop at B2.1.
