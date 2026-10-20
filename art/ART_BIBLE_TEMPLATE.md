# Art Bible — [game title]

**Game ID:** [slug]
**Version / owner / date:** [version, art director, YYYY-MM-DD]
**Style profile:** [preset ID or derived profile path; record changes from baseline]
**Decision status:** [draft / approved by named owner + date]

## 1. Context

- **Genre / core loop:** [what players do minute to minute; mood shifts by mode]
- **Audience / accessibility:** [age/readability assumptions; text size, non-color cues]
- **Camera / distances:** [view type, min/typical/max gameplay distance, obstruction risks]
- **Devices / input:** [phone, tablet, desktop, console; touch/controller constraints]
- **Identity in one sentence:** [what makes this game identifiable without borrowed IP]

## 2. Visual direction

| Pillar     | Observable rule      | Counterexample   |
| ---------- | -------------------- | ---------------- |
| [pillar 1] | [what to draw/model] | [what to reject] |
| [pillar 2] | [what to draw/model] | [what to reject] |
| [pillar 3] | [what to draw/model] | [what to reject] |

**Signature shapes / landmarks / recurring motifs:** [original forms, hierarchy, silhouette tests]
**Broad references:** [mood or material principles only; source and why; no copied compositions or identities]

## 3. Color and gameplay semantics

| Role               | Hex / range | Shape, label or motion redundancy | Use / exclusions |
| ------------------ | ----------- | --------------------------------- | ---------------- |
| Base / background  | [#RRGGBB]   | [n/a]                             | [where]          |
| Accent             | [#RRGGBB]   | [n/a]                             | [where]          |
| Interactable       | [#RRGGBB]   | [cue]                             | [where]          |
| Hazard             | [#RRGGBB]   | [cue]                             | [where]          |
| Reward             | [#RRGGBB]   | [cue]                             | [where]          |
| Neutral / disabled | [#RRGGBB]   | [cue]                             | [where]          |

**Contrast tests:** [minimum text/icon readability at actual camera and target device; state overlays]

## 4. World and asset rules

- **Geometry:** [proportions, bevels, silhouette hierarchy, collision clarity, modular grid]
- **Materials:** [approved Roblox material families, roughness/glare guidance, surface scale]
- **Textures:** [intended resolution by use, file format, color/detail frequency, UV density, compression review]
- **Tiling:** [which surfaces repeat; 3×3 join/motif check, UV scale and variation strategy]
- **Reuse:** [shared meshes, atlases, trims, palette variants; naming and ownership]

## 5. Presentation and feedback

- **Lighting:** [time of day, practical lights, shadow range, readability in darkest scene]
- **Effects:** [particle density/lifetime, fog, bloom, hazard and reward visibility]
- **UI:** [typography, hierarchy, touch targets, states, color-independent affordances]
- **Audio:** [ambient palette, SFX categories, warning/reward priority, volume and licensing]

## 6. Budgets and verification

| Metric                                | Target                                    | Target device / scene | Measurement and reviewer     |
| ------------------------------------- | ----------------------------------------- | --------------------- | ---------------------------- |
| FPS                                   | [profile target; override with rationale] | [device/scene]        | [capture method]             |
| Texture edge / decoded or upload size | [px / bytes]                              | [asset class]         | [file and Studio check]      |
| Draw / instance / particle load       | [per scene limit]                         | [worst case]          | [profiler and reviewer]      |
| Readability                           | [distance / UI size]                      | [smallest screen]     | [screenshots / human review] |

**Reuse plan / exceptions:** [which asset families share a source; approved exceptions and rationale]

## 7. Rights and exclusions

- **Originality:** [how shapes, characters, icons and layouts differ from known works]
- **Provenance / license:** [source, author, use rights, model/workflow and derivative history per asset]
- **Prohibited:** [logos, recognizable game identities, watermarks, unlicensed sources, generated text used as UI, unsafe or unsuitable content for audience; game-specific exclusions]
- **Approval owner:** [who signs off concept, each asset and final in-engine result]

## 8. Decisions and open questions

| Date         | Decision / evidence | Owner  | Impact on profile / requests |
| ------------ | ------------------- | ------ | ---------------------------- |
| [YYYY-MM-DD] | [decision]          | [name] | [references]                 |

Start from one preset, then tailor this document to the game's genre and mechanics. A preset is a baseline, not a mandate; changed semantic mappings must be propagated to every asset request and verified in-engine.
