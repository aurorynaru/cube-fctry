# B2 texture QA — workflows/textures/stone-seamless-v4.png

**Overall: FAIL** (automated: FAIL). No human gate pass or registry transition is claimed.

Validator: `B2-1.2` · Source SHA-256: `ab79d9c624862469d7a969020110eb5dbbed2e91d85a9c7ace68d376b3422849`
Profile: `art/presets/adventure-fantasy.json` version `1.0` SHA-256 `8b5389b494d503aada07cd982d9189c5caf33a247da3317ec7f2080daa9910cd`

## Automated checks

| Check | Result | Evidence / reason |
| --- | --- | --- |
| style_profile | PASS | Unique v1.0 profile resolves and validates via B1 |
| asset_metadata | REVIEW_REQUIRED | No B1 request supplied; provenance, usage and delivery intent unverified |
| file | PASS | Existing file: 2098500 bytes |
| sha256 | REVIEW_REQUIRED | actual=ab79d9c624862469d7a969020110eb5dbbed2e91d85a9c7ace68d376b3422849; expected=not supplied |
| readability | PASS | Full image decoded successfully |
| pixel_mode | PASS | RGB opaque |
| transparency | PASS | Opaque |
| delivery | REVIEW_REQUIRED | No validated request dimensions/format |
| texture_budget | FAIL | edge=1024/1024 px; file=2098500/2097152 bytes |
| style_proxy | REVIEW_REQUIRED | stylized detail and legible material features; screening limits residual_std=24.0, broad_std=12.0; no proxy alert |
| edge_screen | PASS | right-left/neighbor=0.941, bottom-top/neighbor=1.146; proposed max=1.25 |
| tone_screen | PASS | 8px-blurred edge means=2.882, 4.918; screening max=8 |
| repeated_motif_screen | PASS | broad_std=2.983, p99_deviation=7.326; no large-scale motif proxy alert; inspect 5x5 |

## Visual and in-engine assessments

| Assessment | Result | Required review |
| --- | --- | --- |
| style_compliance | REVIEW_REQUIRED | Material, silhouette, palette and genre judgment require a human at intended scale |
| in_engine_suitability | REVIEW_REQUIRED | UV, filtering, compression, lighting and target device untested |
| mathematical_continuity | FAIL | Exact equality of opposing RGB edge pixels on both axes |
| visual_seamlessness | REVIEW_REQUIRED | Inspect both grids and center joins; numerical screens do not establish visual acceptability |
| repetition_quality | REVIEW_REQUIRED | Inspect distinctive repeated motifs in 5x5 at use scale |

## Evidence

- json: `registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486.json`
- markdown: `registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486.md`
- 3x3: `registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486-3x3.png`
- 5x5: `registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486-5x5.png`
- seam_detail: `registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486-seam_detail.png`

B1 gate entries remain pending. A named, independent QC reviewer must verify rights, originality, style, flat-image tiling, and technical/performance evidence before any separate B1 `qc_passed` event. In-engine suitability needs a later target-device check.
