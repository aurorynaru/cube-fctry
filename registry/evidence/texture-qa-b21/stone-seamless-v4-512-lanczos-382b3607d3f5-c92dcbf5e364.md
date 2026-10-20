# B2 texture QA — workflows/textures/b21/stone-seamless-v4-512-lanczos.png

**Overall: REVIEW_REQUIRED** (automated: REVIEW_REQUIRED). No human gate pass or registry transition is claimed.

Validator: `B2-1.2` · Source SHA-256: `c92dcbf5e364ac681261f01b81d0c91ed249cee20bafe96394daedd9a437b0e1`
Profile: `art/presets/adventure-fantasy.json` version `1.0` SHA-256 `8b5389b494d503aada07cd982d9189c5caf33a247da3317ec7f2080daa9910cd`

## Automated checks

| Check | Result | Evidence / reason |
| --- | --- | --- |
| style_profile | PASS | Unique v1.0 profile resolves and validates via B1 |
| asset_metadata | REVIEW_REQUIRED | No B1 request supplied; provenance, usage and delivery intent unverified |
| file | PASS | Existing file: 482394 bytes |
| sha256 | REVIEW_REQUIRED | actual=c92dcbf5e364ac681261f01b81d0c91ed249cee20bafe96394daedd9a437b0e1; expected=not supplied |
| readability | PASS | Full image decoded successfully |
| pixel_mode | PASS | RGB opaque |
| transparency | PASS | Opaque |
| delivery | REVIEW_REQUIRED | No validated request dimensions/format |
| texture_budget | PASS | edge=512/1024 px; file=482394/2097152 bytes |
| style_proxy | REVIEW_REQUIRED | stylized detail and legible material features; screening limits residual_std=24.0, broad_std=12.0; no proxy alert |
| edge_screen | PASS | right-left/neighbor=0.936, bottom-top/neighbor=1.15; proposed max=1.25 |
| tone_screen | PASS | 8px-blurred edge means=2.164, 4.02; screening max=8 |
| repeated_motif_screen | PASS | broad_std=1.609, p99_deviation=4.314; no large-scale motif proxy alert; inspect 5x5 |

## Visual and in-engine assessments

| Assessment | Result | Required review |
| --- | --- | --- |
| style_compliance | REVIEW_REQUIRED | Material, silhouette, palette and genre judgment require a human at intended scale |
| in_engine_suitability | REVIEW_REQUIRED | UV, filtering, compression, lighting and target device untested |
| mathematical_continuity | FAIL | Exact equality of opposing RGB edge pixels on both axes |
| visual_seamlessness | REVIEW_REQUIRED | Inspect both grids and center joins; numerical screens do not establish visual acceptability |
| repetition_quality | REVIEW_REQUIRED | Inspect distinctive repeated motifs in 5x5 at use scale |

## Evidence

- json: `registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364.json`
- markdown: `registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364.md`
- 3x3: `registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364-3x3.png`
- 5x5: `registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364-5x5.png`
- seam_detail: `registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364-seam_detail.png`

B1 gate entries remain pending. A named, independent QC reviewer must verify rights, originality, style, flat-image tiling, and technical/performance evidence before any separate B1 `qc_passed` event. In-engine suitability needs a later target-device check.
