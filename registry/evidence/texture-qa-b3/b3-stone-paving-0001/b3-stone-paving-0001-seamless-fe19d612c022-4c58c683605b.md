# B2 texture QA — outputs/generated/b3-stone-paving-0001/b3-stone-paving-0001-seamless.png

**Overall: FAIL** (automated: FAIL). No human gate pass or registry transition is claimed.

Validator: `B2-1.2` · Source SHA-256: `4c58c683605b321266fabc0c5dee927ccbe7bc36bfa0c37fe645a870477edcc5`
Profile: `art/presets/adventure-fantasy.json` version `1.0` SHA-256 `8b5389b494d503aada07cd982d9189c5caf33a247da3317ec7f2080daa9910cd`

## Automated checks

| Check | Result | Evidence / reason |
| --- | --- | --- |
| style_profile | PASS | Unique v1.0 profile resolves and validates via B1 |
| asset_metadata | PASS | B1 v1.0 request structure and pending-gate intent validated; content still needs human verification |
| file | PASS | Existing file: 1703082 bytes |
| sha256 | PASS | actual=4c58c683605b321266fabc0c5dee927ccbe7bc36bfa0c37fe645a870477edcc5; expected=4c58c683605b321266fabc0c5dee927ccbe7bc36bfa0c37fe645a870477edcc5 |
| readability | PASS | Full image decoded successfully |
| pixel_mode | PASS | RGB opaque |
| transparency | PASS | Opaque |
| delivery | PASS | actual=1024x1024 png; requested=1024x1024 png |
| texture_budget | PASS | edge=1024/1024 px; file=1703082/2097152 bytes |
| style_proxy | REVIEW_REQUIRED | stylized detail and legible material features; screening limits residual_std=24.0, broad_std=12.0; no proxy alert |
| edge_screen | PASS | right-left/neighbor=0.935, bottom-top/neighbor=0.934; proposed max=1.25 |
| tone_screen | FAIL | 8px-blurred edge means=8.016, 7.865; screening max=8 |
| repeated_motif_screen | REVIEW_REQUIRED | broad_std=8.951, p99_deviation=28.956; potential repeated landmark; inspect 5x5 |

## Visual and in-engine assessments

| Assessment | Result | Required review |
| --- | --- | --- |
| style_compliance | REVIEW_REQUIRED | Material, silhouette, palette and genre judgment require a human at intended scale |
| in_engine_suitability | REVIEW_REQUIRED | UV, filtering, compression, lighting and target device untested |
| mathematical_continuity | FAIL | Exact equality of opposing RGB edge pixels on both axes |
| visual_seamlessness | REVIEW_REQUIRED | Inspect both grids and center joins; numerical screens do not establish visual acceptability |
| repetition_quality | REVIEW_REQUIRED | Inspect distinctive repeated motifs in 5x5 at use scale |

## Evidence

- json: `registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b.json`
- markdown: `registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b.md`
- 3x3: `registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b-3x3.png`
- 5x5: `registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b-5x5.png`
- seam_detail: `registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b-seam_detail.png`

B1 gate entries remain pending. A named, independent QC reviewer must verify rights, originality, style, flat-image tiling, and technical/performance evidence before any separate B1 `qc_passed` event. In-engine suitability needs a later target-device check.
