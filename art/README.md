# Art direction foundation — Milestone A

This folder defines *starting points*, not a universal game style. Select a baseline from `presets/`, write a game-specific `ART_BIBLE_TEMPLATE.md` copy, and approve that direction before requesting assets. The five presets differ in silhouette, palette, surface, light, UI, sound and performance intent. Derive a new profile for a game where a preset is unsuitable; retain the `schema_version` contract and record changes in the Bible.

## File index and contracts

| File | Purpose |
| --- | --- |
| `ART_BIBLE_TEMPLATE.md` | Per-game design and decision record; replace placeholders, sign off before generation. |
| `schemas/style-profile.schema.json` | Draft 2020-12 JSON Schema v1.0 for genre-specific profile data. |
| `schemas/asset-request.schema.json` | Draft 2020-12 JSON Schema v1.0 for requests, provenance, gates and final approval. |
| `schemas/generation-request.schema.json` | Draft 2020-12 JSON Schema v1.0 for B3 local generation requests. |
| `presets/{playful-cartoon,adventure-fantasy,atmospheric-survival,competitive-clean,cozy-social}.json` | Original baseline profiles validated against the style schema. |
| `requests/` | B3 generation requests; experimental requests are staging-only, not approvals. |
| `imports/roblox-assets.json` | Project-local Roblox asset ID provenance; `test_only_unapproved` entries are not B1 events or approvals. |
| `../tool/validate_art.py` | Read-only schema/preset and approval-invariant checks. |
| `REGISTRY_B1.md` | Milestone B1 local registry event/CLI contract and trust boundary. |
| `TEXTURE_QA_B2.md` | Milestone B2 offline texture QA contract and evidence rules. |
| `GENERATION_B3.md` | Milestone B3 local FLUX 3 pipeline, staging and B2 integration contract. |

`style_profile_id` in a request must resolve to the selected profile `id` in the game registry; JSON Schema cannot check cross-file existence. Request `id` must be unique in that registry (also a cross-record check). Reserve unique IDs before submitting; never reuse an ID for a derivative. `schema_version` is `1.0` in both contracts. For non-image assets, resolution is `null`; mesh/audio formats and image format/dimensions are constrained by type. `generation.model` and `generation.workflow` identify the actual generator and workflow, or `none` with a documented manual/procedural method. Paths in evidence should be project-relative when possible. `date` uses ISO 8601 calendar date and validators must enable JSON Schema format checking.

## Production path and responsibilities

1. **Concept** — producer records genre, mechanics, audience, target camera/devices and original identity.
2. **Art Director** — chooses/derives a profile; fills the Art Bible, checks semantic cues against gameplay and budgets.
3. **Approval** — game owner approves the concept/Bible version and profile before requests; record name and date.
4. **Asset Request** — allocate ID, usage, dimensions/format/tiling, method, provenance and seven gate records, initially pending. Link game ID and profile ID.
5. **Local Generation** — operator uses the recorded local workflow and seed; saves new outputs and hashes without overwriting sources. A manual/procedural asset records its own method instead.
6. **Quality Control** — check originality/rights/style/technical/performance and tiling where relevant; attach evidence and named reviewer for every pass. Fail or rework an asset with unresolved findings.
7. **Approval** — art owner signs off the QC candidate for *import*, recorded as `qc_passed`; this is not final `approved` status.
8. **Roblox Import** — separately authorized import, record Roblox asset ID and check platform processing. `imported` remains provisional.
9. **In-engine Verification** — inspect at intended scale, camera, light, filtering and lowest target device; attach screenshots/measurements and reviewer to `in_engine` gate.
10. **Asset Registry** — record immutable request ID, version, SHA-256 of deliverable, provenance, profile/Bible version, evidence, Roblox ID and registry path; set `approval.status` to `approved` only after validation of *all* final gates and named sign-off.

The final schema requires passes with evidence/reviewer for originality, rights, style, technical, performance and in-engine; also tiling when required. Non-tiling assets may mark the tiling gate `not_applicable` or pass with evidence. It also requires final reviewer/date, imported asset ID, registry path and deliverable hash. Schema validity is a structural gate, not proof that a review actually happened. No asset is approved in this milestone.

## Mandatory gates and proposed acceptance thresholds

These are **proposals**, not measured universal standards. The game's Art Bible sets final numbers before generation. Reject if a mandatory check has no evidence; human review remains decisive.

| Gate | Minimum evidence / proposed threshold |
| --- | --- |
| Originality | Review silhouette, motif, icon/text and composition against references; zero recognizable third-party identities/logos/watermarks. |
| Rights | Source, license and derivative chain recorded; zero unlicensed or unknown-rights inputs. |
| Style | Side-by-side profile/Bible comparison at intended camera; semantic interactable/hazard/reward cues readable by shape/label as well as color. |
| Technical | Correct format, dimensions and alpha/channel behavior; no corrupt file or unintended text/border; texture edge and byte size at or under profile budget unless a named exception is approved. |
| Performance | Representative worst-case target-device scene meets the Bible FPS goal (presets propose 30 FPS phone, 60 for competitive); log device, scene and capture. Asset-level estimate is provisional until engine test. |
| Tiling (required only for repeating textures) | Exact 3×3 preview at native resolution and visual join/motif inspection. Proposed raw opposite-edge/ordinary-neighbor mean RGB ratios ≤ 1.25 on both axes; compare broad tone and inspect distinctive repeated motifs. A numerical pass alone never clears this gate. |
| In-engine | Roblox import, intended UV scale, filtering/compression, lighting, camera and target-device review; no visible join, lost legibility or unacceptable frame-time impact. Record screenshot/measurement and Roblox ID. |

Existing stone v4 has measured ratios 0.941 / 1.146 and flat-image visual review, **not** the other gate passes and **not** in-engine approval. These proposed limits may be tightened or adjusted in a game Bible after target-device trials; keep exceptions explicit with evidence and reviewer.

## Integration design (future authorized implementation)

Use `../flux3-stone-workflow.json` as a **read-only reference graph**. Copy it to a new, per-request API-format workflow; set node `4` (`CLIPTextEncode.inputs.text`) from the approved style/asset brief, node `6` width/height from the request when the installed model supports them, and node `7` seed/sampling from the request. Record graph path/hash, installed model filenames, seed, prompt, output hash and job ID as provenance. Validate the copy locally before any run; the reference graph has only been proven for one 1024×1024 stone run, so do not assume it supports all styles or asset types. No runtime, checkpoint or model change is part of this milestone.

For repeating stone-like 1024×1024 PNGs, route a **separate derivative** through `../workflows/textures/seamless_stone.py` with a unique stem and pre-created project-local output directory. Its v1/v2 method can be reused on other project-local 1024×1024 textures; v3/v4 vein mask is **source-specific** and must not be blindly reused. It refuses overwrites and emits a 3×3 preview, join crop and metrics; record those files and original/derivative hashes. `../tool/texture_seam_check.py` is the existing baseline comparison for the original stone and writes its fixed evidence locations, so do not run it as a generic request handler. Human review of repeats precedes any Roblox import. Neither existing script, workflow nor corrected PNGs are edited by this design.

## Validation

With the already-available Python `jsonschema` package: `python tool/validate_art.py`. It checks the schema metaschemas, every preset, a synthetic draft request, a synthetic complete approval and negative cases (missing gate, missing evidence/reviewer, unpassed required tiling/in-engine, missing import/registry/hash, incompatible format). Synthetic approval data are test fixtures only, not proof of a real asset. Structural validation cannot enforce cross-file IDs, factual licenses or perceptual quality; production registry tooling should enforce uniqueness and profile resolution before Stage B. No Stage B review is claimed here.

Milestone B3 adds `GENERATION_B3.md` and `schemas/generation-request.schema.json`. A B3 experimental request must use a baseline preset, writes no B1 event and remains unapproved. A production request requires an existing B1 record at `art_approved` with matching Bible/profile/delivery/generation fields; B3 then generates and stages a prospective `generated` payload for a separately authorized B1 CLI call. The pinned reference workflow is read-only.
