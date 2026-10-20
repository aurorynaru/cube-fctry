# Milestone C1D — Repository Checkpoint and Live Adapter Preflight

- **Date:** 2026-10-17
- **Status:** **PREFLIGHT COMPLETE — NO LIVE STUDIO EXECUTION, NO GIT MUTATION.**
- **Scope:** Git preservation audit, C1C harness and Luau helper safety review, live Roblox Studio MCP adapter design, and offline regression verification.
- **Constraints observed:** no Roblox Studio MCP call or mutation, no asset upload, no save/publish, no ComfyUI generation, no B1 registry event, no Swarm plan/task change, no Git staging/commit/push/deletion, and no dependency installation.
- **Existing test asset:** `rbxassetid://112705883084796` (`test_only_unapproved`). It is reused as-is; no new upload is designed into this milestone.

## 1. Executive result

C1C is a sound offline harness with a strong default posture: schema-validated runs, run-scoped ownership metadata, fail-closed cleanup, honest inline-only evidence, and a non-approval B1/B2 boundary. It is **not yet safe to run live without an adapter wrapper and a small number of hardening fixes**, because the current orchestration does not automatically clean up after some partial-creation failures, and deletion correctness depends on the adapter returning a complete snapshot. The Luau helper itself only destroys a fully ownership-verified run folder and contains no save, publish or upload path; it was not executed.

The repository is **ready for an operator-authorized checkpoint** of 110 paths (about 35 MB) and excludes 140 generated/debug files (about 222 MB). Nothing was staged, committed, pushed, deleted or rewritten. The approved `.swarm/plan.md`/`plan.json` are intentionally outside Git via `.git/info/exclude`, so the checkpoint does not preserve them; that is a separate operator decision.

## 2. Git preservation audit

### 2.1 Repository state (read-only)

| Item | Finding |
| --- | --- |
| Branch | `main` |
| HEAD | `e7f5c27` (`Merge pull request #3 …`) |
| Tracked files | 54 |
| Untracked paths | 248 before this document; **249 including `docs/C1D_INTEGRATION_PREFLIGHT.md`** |
| Modified tracked files | 1: `.gitignore` |
| Total untracked bytes | **~257.15 MB** (257.11 MB before this document) |
| Staged paths | 0 |
| Unmerged/conflicted paths | 0 |
| `git diff --check` | PASS (no output) |
| `registry/events.jsonl` | Absent; B1 replay remains 0 assets / 0 events |
| `.swarm/plan.md`, `.swarm/plan.json` | Present locally; **excluded by `.git/info/exclude`**, not part of a Git checkpoint |

The `.gitignore` modification is a deliberate hardening change: it adds `*.part`, tool `__pycache__`, `registry/events.lock`, `outputs/tmp`, pytest/ruff caches, `.env`/`.env.*` (with `.env.example` re-allowed), and comments that `outputs/generated/`, `workflows/generated/`, `registry/staging/` and `registry/evidence/` are intentionally preserved. A `git check-ignore` pass over every proposed staged path returned no hits, so the change does not accidentally exclude the candidate checkpoint content.

### 2.2 Secrets and machine-specific data

No API key, token, password or private key was found in the untracked text files that are proposed for staging.

- `opencode.json` contains only local MCP launcher configuration (`%LOCALAPPDATA%\Roblox\mcp.bat`, `comfy-mcp`); it contains no secret.
- `tool/publish.env` is already tracked and contains `UNIVERSE_ID=0`, `PLACE_ID=0`, no key; it remains unchanged.
- `.env`/`.env.*` are ignored; no `.env` or `.env.publish` file is present in the proposed set.
- `docs/C1B_EXECUTION.md:11` records an operator-local temporary path (`C:\Users\juara\AppData\Local\Temp\opencode\c1b-c1b-20261017-01`) and a loopback port. This is historical evidence, not a credential; it is machine-specific and should be understood as such if the repository is shared.
- `docs/C1B_EXECUTION.md` and `status.md` also record the signed-in Roblox user id/name. They are already part of the documented evidence chain and contain no credential.

### 2.3 Large/generated and excluded inventory

These paths are deliberately **not** in the proposed checkpoint. They are not deleted or modified.

| Category | Paths | Files | Size | Reason |
| --- | --- | ---: | ---: | --- |
| B4 debug scratch | `outputs/b4-stone-correction/_scratch/**` | 118 | 140.54 MB | Exploratory/prototype scripts and images; finalists and metrics remain. |
| Regenerable tiled evidence | `registry/evidence/**/*-3x3.png`, `**/*-5x5.png` | 16 | 48.80 MB | Large 3×3/5×5 previews; JSON/Markdown and seam-detail crops remain. |
| Workflow tiled previews | `workflows/textures/*-3x3.png` | 4 | 23.45 MB | Regenerable from the source PNGs and scripts. |
| Root 3×3 preview | `stone-texture-3x3-preview.png` | 1 | 7.03 MB | Regenerable; the source PNG and seam evidence remain. |
| Working intermediate | `workflows/textures/stone-offset-512-working.png` | 1 | 2.28 MB | Intermediate produced by `seamless_stone.py`; not a final candidate. |
| **Total excluded** | | **140** | **222.10 MB** | No deletions performed. |

No other untracked path is excluded by this proposal. The excluded set contains no source code, schema, manifest, test, small JSON/Markdown report, or final C1B asset source.

### 2.4 Exact proposed staging manifest

**110 paths** (1 modified tracked file, 109 untracked including the new C1D document). Approximate aggregate size: **35.01 MB**. This is a proposal only; nothing below is staged. The 108 untracked paths that existed before C1D account for 35.01 MB; this document adds about 39 KB.

```text
.gitignore
7c1a96f1_000.png
art/ART_BIBLE_TEMPLATE.md
art/games/.gitkeep
art/GENERATION_B3.md
art/imports/roblox-assets.json
art/presets/adventure-fantasy.json
art/presets/atmospheric-survival.json
art/presets/competitive-clean.json
art/presets/cozy-social.json
art/presets/playful-cartoon.json
art/profiles/.gitkeep
art/README.md
art/REGISTRY_B1.md
art/requests/b3-stone-paving-0001.json
art/schemas/asset-request.schema.json
art/schemas/generation-request.schema.json
art/schemas/style-profile.schema.json
art/TEXTURE_QA_B2.md
docs/C1A_PREFLIGHT.md
docs/C1B_EXECUTION.md
docs/C1B_IMPORT_PLAN.md
docs/C1C_HARNESS.md
docs/C1D_INTEGRATION_PREFLIGHT.md
docs/IMPLEMENTATION_STATUS.md
flux3-stone-workflow.json
opencode.json
outputs/b4-stone-correction/stone-paving-b4-comparison.png
outputs/b4-stone-correction/stone-paving-b4-edge-taper.png
outputs/b4-stone-correction/stone-paving-b4-finalists-5x5.png
outputs/b4-stone-correction/stone-paving-b4-grout-graft.png
outputs/b4-stone-correction/stone-paving-b4-metrics.json
outputs/generated/b3-stone-paving-0001/b3-stone-paving-0001.png
outputs/generated/b3-stone-paving-0001/b3-stone-paving-0001-seamless.png
registry/.gitkeep
registry/evidence/.gitkeep
registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364.json
registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364.md
registry/evidence/texture-qa-b21/stone-seamless-v4-512-lanczos-382b3607d3f5-c92dcbf5e364-seam_detail.png
registry/evidence/texture-qa-b21/stone-seamless-v4-lossless-opt-f18d45a9bf68-782b2c956c40.json
registry/evidence/texture-qa-b21/stone-seamless-v4-lossless-opt-f18d45a9bf68-782b2c956c40.md
registry/evidence/texture-qa-b21/stone-seamless-v4-lossless-opt-f18d45a9bf68-782b2c956c40-seam_detail.png
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-d4a8cecc54c7-85dfb0578bc0.json
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-d4a8cecc54c7-85dfb0578bc0.md
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-d4a8cecc54c7-85dfb0578bc0-seam_detail.png
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b.json
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b.md
registry/evidence/texture-qa-b3/b3-stone-paving-0001/b3-stone-paving-0001-seamless-fe19d612c022-4c58c683605b-seam_detail.png
registry/evidence/texture-qa-b4/stone-paving-b4-edge-taper-3db0e4578e44-a10451079097.json
registry/evidence/texture-qa-b4/stone-paving-b4-edge-taper-3db0e4578e44-a10451079097.md
registry/evidence/texture-qa-b4/stone-paving-b4-edge-taper-3db0e4578e44-a10451079097-seam_detail.png
registry/evidence/texture-qa-b4/stone-paving-b4-grout-graft-9a781bd41330-5d40dcc272d9.json
registry/evidence/texture-qa-b4/stone-paving-b4-grout-graft-9a781bd41330-5d40dcc272d9.md
registry/evidence/texture-qa-b4/stone-paving-b4-grout-graft-9a781bd41330-5d40dcc272d9-seam_detail.png
registry/evidence/texture-qa-native/7c1a96f1_000-6845bfeb2c9c-71891bc7e2c5.json
registry/evidence/texture-qa-native/7c1a96f1_000-6845bfeb2c9c-71891bc7e2c5.md
registry/evidence/texture-qa-native/7c1a96f1_000-6845bfeb2c9c-71891bc7e2c5-seam_detail.png
registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486.json
registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486.md
registry/evidence/texture-qa-native/stone-seamless-v4-4f883c59ee85-ab79d9c62486-seam_detail.png
registry/staging/b3/b3-stone-paving-0001/b1-draft-request.json
registry/staging/b3/b3-stone-paving-0001/b1-generated-payload.json
registry/staging/b3/b3-stone-paving-0001/preflight.json
registry/staging/b3/b3-stone-paving-0001/request.json
registry/staging/b3/b3-stone-paving-0001/result.json
status.md
stone-texture-seam-detail.png
stone-texture-seam-evidence.json
stone-texture-seam-review.md
tests/test_asset_registry.py
tests/test_c1c_harness.py
tests/test_image_generation.py
tests/test_texture_qa.py
tool/asset_registry.py
tool/b3_postprocess.py
tool/c1c/example-spec.json
tool/c1c/harness-spec.schema.json
tool/c1c/studio_rig.luau
tool/c1c_harness.py
tool/c1c_verify.py
tool/generate_asset.py
tool/image_generation.py
tool/registry.py
tool/texture_qa.py
tool/texture_seam_check.py
tool/validate_art.py
tool/validate_texture.py
workflows/flux3/README.md
workflows/flux3/workflow-catalog.json
workflows/generated/b3-stone-paving-0001/workflow.json
workflows/textures/b21/REVIEW.md
workflows/textures/b21/stone-seamless-v4-512-lanczos.png
workflows/textures/b21/stone-seamless-v4-comparison.png
workflows/textures/b21/stone-seamless-v4-lossless-opt.png
workflows/textures/b21_derivatives.py
workflows/textures/b4_material_aware.py
workflows/textures/README.md
workflows/textures/seamless_stone.py
workflows/textures/stone-seamless-v1.png
workflows/textures/stone-seamless-v1-join.png
workflows/textures/stone-seamless-v1-metrics.json
workflows/textures/stone-seamless-v2.png
workflows/textures/stone-seamless-v2-join.png
workflows/textures/stone-seamless-v2-metrics.json
workflows/textures/stone-seamless-v3.png
workflows/textures/stone-seamless-v3-join.png
workflows/textures/stone-seamless-v3-metrics.json
workflows/textures/stone-seamless-v4.png
workflows/textures/stone-seamless-v4-join.png
workflows/textures/stone-seamless-v4-metrics.json
```

Why these are included:

- **Reproduction-critical:** `tool/`, `tests/`, `tool/c1c/`, `art/schemas/`, `art/presets/`, `art/requests/`, `workflows/*.py`, `workflows/flux3/`, `workflows/generated/.../workflow.json`, `art/imports/roblox-assets.json`.
- **Asset provenance:** `workflows/textures/b21/stone-seamless-v4-lossless-opt.png` is hash-pinned by the manifest and the C1C example spec; `workflows/textures/stone-seamless-v4.png` is the parent candidate. `registry/evidence/texture-qa-b21/*` and `b3`/`b4` JSON/Markdown are the QA records.
- **Decision history:** `docs/C1A`–`C1D`, `status.md`, B1/B2/B3/B4 contracts.
- **Selected evidence:** B3 raw/seamless candidates, B4 A/B candidates plus comparison/finalist/metrics, small seam-detail crops, and the original FLUX PNG. Multi-MB tiled previews are excluded as regenerable.
- **Local configuration:** `opencode.json`, `flux3-stone-workflow.json`; no secret is present.

If repository size is a concern, the optional evidence PNGs can be deferred in a second commit: the B3/B4 candidate PNGs and comparison/finalist images, the historical v1–v3 PNGs/joins, and the root seam-detail PNG. The authoritative code/schema/test/doc checkpoint does not depend on them; the C1C example spec does depend on the b21 lossless-opt PNG.

### 2.5 Recommended commit message (not executed)

```text
checkpoint: preserve art pipeline and C1C QA harness

- Add B1/B2/B3/B4 tooling, schemas, tests and evidence
- Add the offline C1C harness, Luau helper and 22 mocked tests
- Record C1A-C1D decision history and the live-adapter preflight
- Keep large tiled previews and B4 scratch output untracked

Verified: 63 tests (1 skipped), registry 0/0, art validation,
compileall, C1C validate/plan, stylua/selene, git diff --check
```

### 2.6 Checkpoint readiness

**Ready for operator review, not executed.** Recommended sequence after explicit authorization:

1. Re-run `git status --porcelain=v1 -uall`, `git diff --check`, and the offline suite.
2. Stage exactly the 110 paths above.
3. Confirm `git diff --cached --stat` shows no `_scratch`, no `-3x3`/`-5x5` preview, no `.env`, and no `registry/events.jsonl`.
4. Commit with the message above (or a project-approved equivalent).
5. Do not push until separately authorized.

## 3. C1C harness safety review

Reviewed `tool/c1c_harness.py`, `tool/c1c_verify.py`, `tool/c1c/harness-spec.schema.json`, `tool/c1c/example-spec.json`, and `tests/test_c1c_harness.py`.

### 3.1 Schema and ownership boundaries

- **PASS.** `load_spec` validates against Draft 2020-12 with `additionalProperties: false`, rejects traversal/backslash/drive-letter/absolute spec paths via `safe_path`, and normalizes only known fields. `run_id`, capture IDs, scale names and evidence directory are constrained. `_spec_from_raw` independently requires `asset.upload == false`, `asset.status == "test_only_unapproved"`, and `evidence.out_dir == "registry/evidence/c1c"`.
- **PASS.** The asset must already exist in `art/imports/roblox-assets.json`; duplicate manifest IDs are rejected; the source file is re-hashed and must match both the spec and manifest. There is no upload method in the adapter protocol, and the test double exposes a spy `upload_asset` that must never be called.
- **PASS.** Every planned rig object carries `C1C_` naming, `C1C_RunId`, `C1C_TestOnly=true` and the `C1C_TextureTest` tag. `verify_ownership` also scans for tagged or prefixed objects outside the run folder.
- **Note (low):** `asset.status` must be exactly `test_only_unapproved`, so a later approved asset cannot be re-verified with this harness without a deliberate status/manifest change. This is a conservative test-only boundary, not a production approval path.
- **Note (low):** `b1` and `b2` are optional in the schema and receive safe defaults; `verify_b2_evidence` ignores non-dict claim rows instead of rejecting them. A malformed B2 report could therefore appear “pending” by omission. It still cannot create an approval.

### 3.2 Safe deletion and naming

- **PASS.** Deletion is performed only through `adapter.destroy(folder)` after `verify_ownership` returns no violations. There is no `ClearAllChildren()`, no name-only deletion, and no template “repair” to force a baseline match. The run folder and every descendant must carry the run tag/attribute and prefix.
- **PASS.** `C1B`-style raw `Texture`/`Decal` children are a repairable naming issue only when `cleanup.allow_safe_rename` is true; the rename target must be free and ownership is re-verified afterward. Otherwise cleanup refuses and preserves `cleanup-failure-N.json`.
- **PASS.** The Python side scans all snapshot nodes for `C1C_` names outside the folder and all tags for `C1C_TextureTest` outside the folder; either blocks deletion.
- **Finding (medium, live-relevant):** Python `verify_ownership` does not explicitly require the run path to be a `Folder`; it checks only presence and ownership (`tool/c1c_harness.py:1286-1300`). The Luau helper does check `folder:IsA("Folder")` (`tool/c1c/studio_rig.luau:330-332`). In the normal create path the folder is created by the adapter and preflight rejects pre-existing `C1C_` paths, but recovery/defense-in-depth should add the class check.
- **Finding (high for a live adapter):** deletion correctness depends on the adapter's snapshot containing the complete descendant tree. `adapter.destroy(folder)` may delete children that were not present in the snapshot. A real adapter must enumerate every descendant and fail closed if the tree is incomplete; otherwise an unowned child could be destroyed without appearing in `verify_ownership`. This is an adapter-contract requirement, not a proven offline defect.
- **Finding (medium):** if `build_rig` raises after creating some objects (for example a part-creation exception, or `preload` failure at `tool/c1c_harness.py:643-646`), `run()` catches the `HarnessError` but does not call `_cleanup`; only the explicit post-build ownership-failure path and normal/`recover()` paths clean up. A live wrapper must catch this and invoke recovery/cleanup, or the harness should be hardened before live use.

### 3.3 Test-only assets cannot silently become production-approved

- **PASS with trust caveats.** The harness has no approval path: it never writes `registry/events.jsonl`, fingerprints the journal before/after and fails if it changes, and accepts a B2 report only while all claims are `pending`. The report contains no gate passes, no `approved` status, and no B1 transition.
- The manifest/evidence are local, operator-trusted records; the report is not platform-attested. `simulates_studio` is a self-declared adapter field, so a live report is only as truthful as the adapter implementation.
- `import-capture` writes a separate `manual-capture-<id>.json` and never changes the original report's inline-only record; however, it is not bound to a capture ID present in the spec/report. An operator could import an unrelated PNG under a chosen capture ID. It still does not create an approval, but integrity review should check the binding.
- **Finding (low):** the report's `rig.planned_object_count` and `RigPlan.as_dict()["object_count"]` are off by one. `build_rig_plan` already includes the folder in `plan.objects` (25 objects for the example), but the report adds 1 again (`tool/c1c_harness.py:487`, `tool/c1c_harness.py:2063`). Ownership verification correctly uses `len(plan.objects)`. This is a reporting inconsistency, not a deletion error.

### 3.4 Interrupted-run recovery and error handling

- **PASS.** `recover()` requires an existing state with a baseline, re-reads Studio rather than trusting the journal, restores and verifies the camera, runs the same ownership-verified cleanup on a partial but fully owned rig, does not repeat captures, and writes a new `recovery-N.json` with honest `RECOVERED` / `RECOVERED_WITH_RESIDUALS` / failure.
- **PASS.** Camera restoration is attempted before cleanup; if restoration fails, cleanup is not performed and the rig is left for the operator.
- **Finding (medium):** recovery's B1 fingerprint starts at recovery time (`tool/c1c_harness.py:2166`), so a B1 journal change that occurs between the crash and recovery is not detected by that recovery report.
- **Finding (low):** recovery does not bind the stored state to the current spec content (only `run_id`), so a changed spec with the same run ID could be used; ownership verification still constrains deletion, but the expected plan/captures may differ.
- **Finding (low):** `EvidenceStore.open_run` rejects an existing `report.json` but accepts a leftover `state.json` without a report. A deliberate restart with the same run ID can overwrite state and collide with existing capture files; the normal preflight/leftover-rig checks usually stop it, but the journal should be treated as “use recovery, not restart.”

### 3.5 Camera, viewport and evidence

- **PASS.** Baseline records 12-component CFrame, `CameraType`, viewport, selection and a curated snapshot. Every capture is wrapped by before/after camera comparison; the harness restores the exact baseline and requires a `1e-6` match. If it cannot restore, it stops before cleanup.
- **PASS.** Viewport changes are detected and restored only when the adapter explicitly declares `supports_viewport_restore` and implements it; otherwise `viewport.restored` and `restoration.complete` stay false and the result is at most `PASS_WITH_RESIDUALS`.
- **PASS.** Durable captures are decoded/validated, written new-only, and hashed from the actual file; inline-only captures keep `evidence_path`/`sha256` null. Empty, corrupt, non-PNG, all-black and all-transparent captures are invalid. The harness cannot prove scene content or visual quality, which is documented.
- **Note (low):** a non-numeric camera CFTime/value can raise outside the capture `try` block and be caught only as `unexpected_exception`, with no automatic cleanup. The live adapter must validate and normalize all snapshot values.
- **Note (low):** preflight treats a missing `studio_id`/`place` as acceptable (`tool/c1c_harness.py:1438-1443`). The live adapter must require the exact Studio ID, place identity, Edit mode and non-Team-Create before any mutation.

### 3.6 Untested edge cases identified

1. Partial creation with all valid ownership (fewer objects than planned) proceeds to rig captures; `rig_incomplete` is raised only at cleanup. It is safe but late.
2. Creation/preload failure leaves the rig in place because there is no automatic cleanup on that exception path.
3. Adapter snapshot missing descendants (the deletion-safety dependency).
4. Run folder path that is not a `Folder` (Python side).
5. Recovery after a B1 change between crash and recovery.
6. Recovery with a different spec under the same `run_id`.
7. Malformed/non-dict B2 claim entries.
8. `import-capture` not bound to a spec/report capture ID.
9. All screenshots marked `required: false`, or a spec with no pre/post phase (schema permits both).
10. `inline_bytes` mode (bytes plus `inline_only=True`) is not directly covered; the harness does save those bytes as durable evidence when present.
11. Off-by-one planned object count in reports.
12. Missing `supports_viewport_restore` attribute or non-numeric camera data from a real adapter.

## 4. Luau helper safety review

Reviewed `tool/c1c/studio_rig.luau`; it was linted/formatted only and **not executed**.

### 4.1 Creation

- `buildFromPlan` requires a non-empty `plan.run_id`, verifies `plan.rig.folder == "C1C_TextureTest_" .. runId`, refuses an existing folder and pre-existing `C1C_TextureTest` tags, creates the folder, then creates only `Part`, `Texture` and `BillboardGui` classes from the plan plus a fixed `C1C_Text` `TextLabel`.
- Every created object gets `C1C_RunId`, `C1C_TestOnly=true`, the `C1C_TextureTest` tag, and must pass the `C1C_` name assertion. Plan parents must be the run folder or a descendant.
- The helper does not create anything outside `Workspace.C1C_TextureTest_<runId>`.
- **Finding (medium):** it checks pre-existing tags but not pre-existing `C1C_`-named objects before building. It detects them in the post-build ownership verification and returns `built=false`, but the new rig remains; the caller must clean up. It also trusts `plan.run_id` without a regex; the Python schema is the authority.
- **Finding (medium):** `ContentProvider:PreloadAsync` is wrapped in `pcall`, but `built=true` is returned even when `preload_ok=false` (`tool/c1c/studio_rig.luau:304-312`). A live adapter must treat preload failure as fatal.

### 4.2 Deletion

- `cleanup(runId, allowSafeRename)` resolves only `Workspace:FindFirstChild("C1C_TextureTest_" .. runId)`, requires `folder:IsA("Folder")`, and runs `verifyOwnership` over every descendant. It refuses when there are any violations, outside tagged objects, or outside prefixed objects (the latter are added as violations by `verifyOwnership`).
- A raw `Texture`/`Decal` name is only renamed with `allowSafeRename`; the target must be free, and ownership is re-verified before `folder:Destroy()`.
- It never uses `ClearAllChildren()`, never deletes by name alone, and never deletes outside the exact run folder. `Destroy()` is applied only to the fully verified folder.
- **Residual risk:** `Destroy()` deletes all descendants of the verified folder. `verifyOwnership` enumerates the live tree with `GetChildren`, so the set is complete at verification time; there is no yield between verification and destroy. A concurrent plugin mutation in that same frame is a theoretical TOCTOU, not a demonstrated issue.
- **Finding (low):** if the folder is missing but untagged `C1C_` objects remain, `cleanup` returns `cleaned=false` with no `outside_prefixed` list. It is safe (nothing deleted) but recovery logic should use the Python `recover()` semantics or re-read the tree.
- The helper does not restore the camera and does not compare the Workspace baseline; the caller must call `restoreCamera` and/or use the Python harness.

### 4.3 Run ID/tag validation and forbidden actions

- **PASS for the intended harness flow.** The run ID reaches only the folder name and attributes; the Python schema constrains it to `[A-Za-z0-9][A-Za-z0-9_-]{0,63}` before a plan is produced.
- **Finding (medium for standalone use):** the helper itself does not enforce that regex, does not reject dots/spaces/slashes, and does not validate duplicate object names in a hand-supplied plan. The live adapter must validate the plan before injection.
- **PASS.** The helper calls no save, publish, upload, HTTP, DataStore or asset-insertion API. Services used are `CollectionService`, `ContentProvider` (read/preload) and `Selection` (read-only baseline). `ContentProvider:PreloadAsync` can fetch an existing asset, but cannot upload one.
- **Finding (medium):** `captureBaseline` returns an empty Workspace-attributes map and no per-object properties; it is not a full baseline and cannot detect unrelated property drift. It is not a substitute for the Python `capture_baseline`/`compare_baseline` contract.

## 5. Live MCP adapter design (not implemented)

### 5.1 Design goals and hard boundaries

The adapter is a future, separately authorized `McpStudioAdapter` implementing the existing `StudioAdapter` protocol. It must:

- Reuse `load_spec`, `AssetManifest`, `build_rig_plan`, `verify_ownership`, `capture_baseline`, `compare_baseline`, `EvidenceStore`, `Harness` and `recover`. No second planning or verification contract.
- Use only the existing `rbxassetid://112705883084796`; never call an upload/insert-asset tool. No additional asset uploads.
- Never call save, publish, play/stop, or any tool that writes place files. Edit-mode DataModel mutation only.
- Use only a curated property set for snapshots and fail closed on an incomplete tree.
- Require an explicit, single-use operator authorization before the first mutation.

### 5.2 Proposed module and tool allow-list

Future file: `tool/c1c_mcp_adapter.py` (not created in C1D).

Allowed MCP operations:

| C1C operation | MCP binding |
| --- | --- |
| Discover/verify target | `list_roblox_studios`, `get_studio_state`, read-only `execute_luau` |
| Baseline/snapshot | read-only `execute_luau` returning Workspace children/descendants, curated properties, attributes, tags, Selection, camera CFrame/type/viewport, place/creator/mode |
| Create rig | `execute_luau` with the validated plan (prefer the existing `C1C.buildFromPlan`, or strict per-object snippets with the same ownership assertions) |
| Preload | `execute_luau` `ContentProvider:PreloadAsync` plus read-back of asset IDs |
| Camera set/restore | `execute_luau` writing `workspace.CurrentCamera.CFrame`/`CameraType`, then read-back |
| Rename | `execute_luau` after re-checking tag/run ID/prefix |
| Cleanup | `execute_luau` calling the existing `C1C.cleanup` (or equivalent) after Python `verify_ownership`; assert `cleaned=true` and zero residual |
| Screenshot | `roblox_studio_screen_capture` with the planned camera args, after foreground precondition |

Forbidden/unused: `roblox_studio_upload_image`, any asset insertion for this test, save/publish tools, `start_stop_play`, `generate_*`, ComfyUI tools, and any tool that writes outside the run folder.

The adapter should expose `simulates_studio = False`, `supports_viewport_restore = False` unless a separately verified viewport API exists, and a static `assert_tool_policy()` that fails if a forbidden tool is enabled.

### 5.3 Live run sequence

1. **Read-only preflight.** Confirm exactly one Studio instance with the spec `studio_id`; Edit mode; not Team Create; place/creator/user identity expected; no C1C tags/prefixes; no leftover state for the run ID; asset manifest entry/hash; B2 claims pending; B1 fingerprint; evidence dir empty for the run.
2. **Operator authorization check.** Validate a one-use `LiveRunAuthorization` object (see 5.7) against the spec. No mutation before this passes.
3. **Baseline.** Full snapshot + baseline capture. Confirm Studio is visible/foregrounded; treat a black/empty capture as invalid.
4. **Rig creation.** Create only the run folder and planned descendants. Re-read and run `verify_ownership` immediately; fail before any rig capture if tags/run ID/prefix are wrong.
5. **Captures.** For each phase, set the requested camera, capture, read camera/viewport after, restore baseline camera, verify within `1e-6`; restore viewport only if supported, otherwise record a residual.
6. **Cleanup.** Re-read the tree, run `verify_ownership`, optionally safe-rename, destroy only the verified folder, verify no tagged/prefixed/run-attribute objects remain and Workspace matches the baseline.
7. **Post-cleanup capture and final report.** Record camera/viewport/selection/Workspace/B1 checks. Write the report new-only.
8. **Partial-failure wrapper.** If any step raises or the report is `INCOMPLETE`/`FAIL`, restore the camera first, then call `recover(root, spec, adapter)`; if recovery also fails, leave the rig, preserve failure evidence, and stop for manual operator action. Never broad-delete and never repeat captures during recovery.

### 5.4 Camera and viewport side effects

- Snapshot the 12-component CFrame, `CameraType`, viewport size, Selection and the full curated Workspace tree before any capture.
- Treat the capture tool as untrusted: it is known from C1B to rotate the camera and change the viewport even when camera arguments are supplied. Read before/after every capture, restore the baseline explicitly via Luau, and verify the component delta.
- If the camera cannot be restored, stop before cleanup and leave the rig; report `camera_restore_failed`.
- There is no verified MCP viewport-restore method in the current tool surface. Declare `supports_viewport_restore = False`; record `viewport.restored=false` and a residual. Do not fabricate a restore.
- Require Studio foreground/visible before capture; a dark/empty image is invalid and should be retried within the spec limit, then fail honestly.
- Use `screen_capture` with the planned camera only; the Python harness already sets the camera, so the adapter should avoid a second, conflicting camera write where possible.

### 5.5 Durable versus inline-only evidence

- If the MCP response exposes the actual image bytes to the adapter, decode them and return `CaptureResult(image_bytes=...)`. The existing `EvidenceStore` validates, saves new-only under `registry/evidence/c1c/<run>/captures/`, and records the real SHA-256, size and dimensions.
- If the client only displays the image and no bytes/path reach the adapter, return `CaptureResult(inline_only=True, note=...)`. The report must say `storage: inline_only`, with null path/hash and a limitation. It must never invent a file.
- For a formal evidence run, set `require_durable_files: true`; inline-only required captures then make `evidence.complete=false` and the result `FAIL`, which is the honest outcome. For a diagnostic run, `false` may yield `PASS_WITH_RESIDUALS`; that is not durable evidence.
- The operator can use `python tool/c1c_verify.py import-capture ...` for a real local PNG; it writes a separate manual-import record and leaves the original inline-only report truthful.
- The report must set `adapter.simulates_studio=false`, `studio_touched=true`, and `evidence_kind=studio_capture` only when a real MCP adapter performed the operations.

### 5.6 Reusing the asset and the no-upload boundary

- The adapter must reject any spec whose asset ID is not `rbxassetid://112705883084796`, whose status is not `test_only_unapproved`, or whose `upload` is true.
- It must never call `roblox_studio_upload_image` or `insert_asset`; the existing ID is assigned to temporary `Texture` objects via properties/plan.
- The asset remains a persistent cloud object; C1D does not delete, re-upload, register or approve it.

### 5.7 Operator authorization gate

A separate local, non-B1 authorization record should be required before any live mutation, for example:

```json
{
  "authorization_id": "c1d-live-20261017-01",
  "actor": "...",
  "approved_at": "2026-10-17T...",
  "expires_at": "2026-10-17T...",
  "studio_id": "577768ad-49d8-42f5-ac96-8c66cd12a144",
  "place": "local-unsaved",
  "run_id": "c1c-live-20261017-01",
  "asset_id": "rbxassetid://112705883084796",
  "allowed_actions": ["create", "rename", "destroy", "camera", "screenshot"],
  "max_objects": 32,
  "evidence_require_durable": true,
  "acknowledge_no_save_publish_upload": true,
  "one_use_nonce": "..."
}
```

The adapter must verify the authorization matches the spec exactly, is unexpired and unused, and covers every mutation. The operator must explicitly confirm the Studio instance, run ID, target asset, temporary scope, capture plan, cleanup policy, and that no save/publish/upload occurs. A read-only `--preflight` mode is recommended before any `--execute` mode.

## 6. Offline validation results

All commands were run from the repository root on 2026-10-17. No Studio, ComfyUI, upload, save, publish or B1 write occurred.

| Check | Result |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | **PASS: 63 tests, 1 skipped** (Windows symlink skip) |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events** |
| `python tool/validate_art.py` | **PASS: 2 metaschemas, 5 presets, 3 positive, 36 negative fixtures; no files written** |
| `python -m compileall -q tool/c1c_harness.py tool/c1c_verify.py tests/test_c1c_harness.py` | **PASS** |
| `python tool/c1c_verify.py validate --spec tool/c1c/example-spec.json` | **PASS**; asset/hash/B2 pending checks pass; no writes |
| `python tool/c1c_verify.py plan --spec tool/c1c/example-spec.json` | **PASS**; deterministic 25-entry rig plan including the folder; the report’s planned count currently shows 26 (known off-by-one); no Studio call |
| `stylua --check tool/c1c/studio_rig.luau` | **PASS** (0 exit) |
| `selene tool/c1c/studio_rig.luau` | **PASS: 0 errors, 0 warnings, 0 parse errors** |
| `git diff --check` | **PASS** (no output) |

`stylua`/`selene` were invoked from `$env:USERPROFILE\.aftman\bin` because they are not on the default `PATH`; no installation was performed. `registry/evidence/c1c/` was not created by the CLI checks.

## 7. Outstanding risks

1. **No live adapter exists and no Studio execution has occurred.** The Luau helper is linted/formatted only. The first live run needs a separate authorization and its own evidence.
2. **Snapshot completeness is a deletion-safety precondition.** A real adapter that omits descendants could cause the folder destroy to remove unverified objects. The adapter must enumerate the full tree and fail closed.
3. **No automatic cleanup on some partial-creation/preload failures.** A live runner must wrap `Harness.run()` and invoke `recover()`; the harness itself should be hardened before relying on it unattended.
4. **Python cleanup does not assert the run path is a `Folder`.** Add the check (the Lua helper already has it).
5. **Partial-but-owned rigs proceed to captures** and are only flagged at cleanup; this should fail earlier for a live run.
6. **Recovery’s B1 guard starts at recovery time,** so a journal change between crash and recovery is not detected; recovery also does not bind the stored state to the current spec.
7. **Malformed B2 claim rows can be ignored**; validate the B2 document shape before trusting a “pending” result.
8. **Screenshot evidence may be inline-only.** Unless the adapter can decode and save the actual MCP image bytes, a formal durable-evidence run should fail rather than claim a hash.
9. **Viewport restoration is unsupported** in the current MCP surface; a live run will likely leave a viewport residual and must report it.
10. **The capture tool can change the camera** and requires Studio to be visible/foregrounded; the adapter must restore and verify after every capture and treat dark/empty captures as invalid.
11. **Reporting is off by one** for `planned_object_count`/`RigPlan.object_count`; this does not affect ownership, but should be corrected before relying on the number.
12. **The C1B asset remains test-only/unapproved** and persistent in the cloud. No production approval, B1 import or registry event exists.
13. **The approved `.swarm` plan is not in Git** (local exclude). The checkpoint does not preserve it; the operator should archive or track it separately if that is intended.
14. **The 35 MB checkpoint includes selected image evidence.** Multi-MB 3×3/5×5 previews and 140 MB of B4 scratch are excluded; a future evidence-retention or Git LFS decision may change that.

## 8. Authorization requirements for the next phase

Before any live C1C execution, the operator must explicitly authorize, in writing:

1. The exact Studio instance (`studio_id`), place, Edit mode and non-Team-Create state.
2. The new run ID and the existing asset ID `rbxassetid://112705883084796`; no uploads.
3. The allowed mutation set: create the tagged temporary rig, temporary camera changes, safe rename, and destroy of the run folder only.
4. The capture plan, foreground/visibility precondition, evidence retention path, and whether durable files are required.
5. Acceptance that viewport size may remain changed (no verified restore method) and that camera restoration must be verified.
6. The cleanup/recovery policy after partial failure, including who resolves a failed cleanup and how failure evidence is preserved.
7. That no save, publish, playtest, asset insertion/upload, ComfyUI generation or B1 registry event is permitted.
8. A one-use authorization record and a read-only preflight result, before the first mutation.

Until those are supplied, C1D remains an offline preflight only.

## 9. References

- `docs/C1C_HARNESS.md` — C1C contract, evidence semantics, limitations and future outline.
- `docs/C1B_EXECUTION.md` — the observed camera/viewport side effects and the test-only asset.
- `tool/c1c_harness.py`, `tool/c1c_verify.py`, `tool/c1c/harness-spec.schema.json`, `tool/c1c/example-spec.json`.
- `tool/c1c/studio_rig.luau`.
- `tests/test_c1c_harness.py`.
- `art/imports/roblox-assets.json` — `112705883084796` as `test_only_unapproved`.
- `status.md` section 2.17 — factual C1D summary.

## 10. Hardening addendum (C1D-R1) — offline safety implementation

- **Date:** 2026-10-17
- **Status:** **OFFLINE HARDENING COMPLETE — NO STUDIO EXECUTION.**
- **Scope:** resolve the C1D findings in sections 3–4 and 7 without a live adapter, Studio access, screenshot, upload, save/publish, B1 event, plan/task change or Git mutation.
- **Evidence preservation:** all prior C1B/C1C/C1D artifacts and test outputs are unchanged; only source, tests and documentation were added/edited.

### 10.1 Original gap → resolution

| C1D finding | C1D-R1 resolution |
| --- | --- |
| Python cleanup did not assert the run root was a `Folder`. | `verify_ownership()` now requires the exact run path to resolve to class `Folder`; cleanup returns `cleanup_run_root_not_folder` and deletes nothing otherwise. |
| Deletion correctness depended on an unverified adapter snapshot. | Every snapshot must declare `complete: true` and pass `validate_snapshot()`: path/parent/name consistency, parent and child existence, no duplicate/cyclic/unreachable nodes, tag-index agreement, and camera/selection shape. Any gap becomes a cleanup violation. |
| A build/preload exception left the rig in place. | `build_rig()` reports structured `build_ok`/`preload_ok`/phase/error/partial objects. `run()` performs camera restoration and ownership-verified cleanup after creation, configuration or preload failures. Simulated interruptions remain recoverable and are not auto-deleted. |
| A valid-but-partial rig proceeded to captures. | Ownership is verified immediately after build. A partial or unexpected inventory fails with `rig_incomplete` **before** any rig capture; the last confirmed phase and partial objects are recorded in `state.json` and the report. |
| A repairable raw `Texture`/`Decal` name blocked all captures. | It remains a repairable naming issue when the object is present, owned and count-complete; captures may proceed, but cleanup must still rename/re-verify before deletion. |
| Cleanup used a possibly stale verification result. | Cleanup now takes a fresh, complete snapshot and repeats the full ownership/inventory check immediately before `destroy()`; a stale passing read cannot authorize deletion (`cleanup_recheck_failed`). |
| Unexpected objects inside the run folder were not rejected. | Every visible descendant must be in the deterministic plan, except a repairable raw `Texture`/`Decal`; otherwise `unexpected_object` blocks deletion. |
| Objects with the run attribute outside the run folder were not scanned. | `outside_run_attribute` is a first-class violation, alongside tagged and `C1C_`-prefixed objects outside the folder. |
| Recovery's B1 window started at recovery time and was not bound to the spec. | `verify_recovery_provenance()` requires the original schema version, run ID, spec SHA-256, baseline identity, B1 fingerprint, asset manifest identity and expected object inventory. Recovery never captures a replacement baseline; a changed spec/B1/manifest or any missing field is rejected before any mutation. |
| Malformed B2 claim rows were ignored. | `verify_b2_evidence()` validates the claims map and every row (object, non-empty string result, list evidence) and rejects malformed data. |
| `import-capture` was not bound to a spec/report capture. | The CLI now requires `--spec`; import verifies run ID, spec hash, capture ID/phase, original `inline_only` storage, no existing durable file, and no duplicate manual record. |
| Non-numeric camera data could escape the capture `try` block. | Capture/snapshot values are validated by the adapter contract and the structural checks; malformed camera structures are rejected as invalid evidence or a preflight failure rather than trusted. |
| Planned count was off by one (25 objects shown as 26). | `RigPlan.as_dict()["object_count"]` and `report.rig.planned_object_count` now use `len(plan.objects)` (25). |
| Luau helper trusted hand-supplied plans and run IDs. | `validatePlan()` now enforces run-ID/name patterns, exact folder match, object count, class allow-list, prefix, parent containment, path/parent/name consistency, duplicate-path rejection, and per-object run-ID/test-only/tag metadata. `buildFromPlan()` also refuses pre-existing `C1C_`-prefixed objects and cleans up a fully owned partial rig on failure. |
| Luau preload failure returned `built=true` with no distinction. | `buildFromPlan()` returns separate `build_ok`/`preload_ok` and `status` (`complete`/`preload_failed`); a preload failure is not reported as a complete build. |
| Luau cleanup did not re-check immediately before `Destroy()`. | Cleanup accepts an optional validated plan, rejects unexpected/missing expected objects, and performs a fresh ownership verification immediately before destruction. |
| Pinned test-asset status could be weakened. | `PINNED_TEST_ASSETS` enforces `112705883084796 == test_only_unapproved` in addition to the spec/manifest checks. |

### 10.2 New regression coverage

`tests/test_c1c_harness.py` now has **45 C1C tests** (22 original + 23 hardening). New tests cover every rejection path above: non-Folder root, incomplete marker, structural child gap, unexpected object inside, tracked object outside, stale pre-destruction read, creation exception cleanup, preload failure distinction, early partial-rig refusal, actionable failure evidence, changed spec/B1/manifest, each missing provenance field, successful original-run binding, malformed B2 rows, capture-ID mismatch, ambiguous payloads, durable-evidence acceptance, the 25-object count, pinned asset status, schema-version compatibility, and the Luau source contract.

### 10.3 Verification

See `status.md` section 2.18 and `docs/C1C_HARNESS.md` section 12 for the executed commands and results. No Roblox Studio, ComfyUI, asset upload, save/publish, B1 transition, dependency installation or Git mutation occurred.

### 10.4 Residual risks

- **No live adapter or Studio execution.** Snapshot completeness is an adapter contract; a malicious or buggy adapter can still lie about `complete: true`. The Python side now fails closed on inconsistency, but cannot prove a real hierarchy was fully enumerated.
- **TOCTOU remains theoretical.** A concurrent Studio mutation between the fresh ownership read and `Destroy()` is not prevented by either helper; there is no yield in the Luau path, but a plugin/operator could still race it.
- **Inline-only images remain unhashable.** The harness records them honestly and withholds `evidence.accepted`; only operator-supplied durable files or adapter bytes can be hashed.
- **Luau is still linted/formatted, not executed.** The plan validation and failure cleanup are offline-reviewed only until a separately authorized live run.
- **The C1B asset remains persistent, test-only and unapproved.** Nothing in C1D-R1 changes its status or creates production evidence.

### 10.5 Readiness

The code is **ready for live-adapter implementation**, not for live execution. The adapter must implement the documented snapshot contract, call `Harness.run()`/`recover()` unchanged, and add the one-use operator authorization gate. A live run still requires separate written authorization.
