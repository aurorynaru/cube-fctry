# Milestone C1C — Reusable In-Engine QA Harness

- **Date:** 2026-10-17
- **Status:** **OFFLINE IMPLEMENTATION COMPLETE — NO STUDIO TEST EXECUTED.**
- **Scope:** Reusable test-rig design, defensive restoration/cleanup, durable-evidence rules, mocked lifecycle/recovery tests, and documentation. No Roblox Studio mutation, no new asset upload, no save/publish, no ComfyUI generation, no B1 production event, and no change to the approved Swarm plan or task statuses.
- **Existing test-only asset:** `rbxassetid://112705883084796` (C1B, `test_only_unapproved`). It was not uploaded again.
- **Default recipe:** `tool/c1c/example-spec.json` reproduces the C1B 4/8/16/32 studs-per-tile rig plus the 6-stud cross-part seam pair at the same positions.

## 1. What C1C adds

C1C turns the one-off C1B experiment into a repeatable, evidence-driven harness:

1. A schema-validated **run specification** that names an existing asset, run ID, Studio target, texture scales, temporary geometry, screenshot phases and cleanup policy.
2. A deterministic **test-rig plan** with run-specific names, tags and attributes.
3. A Python **orchestrator** that captures a baseline, creates only the tagged rig, detects camera drift and viewport side effects, performs ownership-verified cleanup, and refuses unsafe deletion. C1D-R1 hardening adds a mandatory `Folder` class check, complete-snapshot validation, deterministic inventory matching, a fresh ownership read immediately before destruction, and automatic ownership-verified cleanup after build/preload failures.
4. An **adapter contract** for a future MCP-backed Studio connection, plus an in-memory adapter used only by tests.
5. A **Luau Studio helper** (`tool/c1c/studio_rig.luau`) that can execute a generated plan and perform the same ownership-verified cleanup. It was linted and formatted offline but **not executed** in C1C.
6. An **evidence store** with real content hashes for saved files, explicit inline-only records, and a manual capture-import fallback.
7. **B1/B2 guardrails**: the harness never writes `registry/events.jsonl`, only accepts a pending B2 report, and never creates an approval.

## 2. C1B facts encoded in the harness

| C1B fact | Harness handling |
| --- | --- |
| Asset ID `112705883084796`, source SHA-256 `782b2c…d33a` | Must exist in `art/imports/roblox-assets.json` with status `test_only_unapproved`; source bytes are re-hashed before a run. |
| Rig folder `C1B_TextureTest_20261017-01` | C1C uses `Workspace.C1C_TextureTest_<run_id>` and refuses a pre-existing folder. |
| 4/8/16/32 studs-per-tile 32×32 panels | `texture_scales` drives the same 2×2 grid around `(0, 0.5, 65)`. |
| 16×16 seam pair at 6 studs/tile, right `OffsetStudsU=16` | `geometry.seam` drives the same cross-part UV continuity test. |
| Every object `C1B_`-prefixed, `C1B_RunId`, `C1B_TestOnly=true`, tagged `C1B_TextureTest` | C1C uses `C1C_`/`C1C_TextureTest` and verifies all four properties before cleanup. |
| Texture children were initially named `Texture`, causing cleanup to abort | The harness detects the naming inconsistency and can rename **only** after tag/run-ID ownership is verified. |
| Capture tool changed camera rotation and restored only position | Camera CFrame and `CameraType` are recorded; every capture compares before/after and restores/verifies the baseline. |
| Viewport changed `1219×793` → `690×675` and was not restored | Viewport changes are recorded. Restoration is attempted only through an adapter method that explicitly declares support; otherwise `restoration.complete` stays false. |
| All captures were inline-only | Inline-only captures are recorded without a file or hash; C1C never invents a durable path. The manual import fallback can add a real operator-provided file later. |

## 3. Architecture

### 3.1 Files

| File | Purpose |
| --- | --- |
| `tool/c1c_harness.py` | Specification, manifest, rig plan, baseline comparison, adapter protocol, in-memory adapter, lifecycle, cleanup, recovery, evidence store. |
| `tool/c1c_verify.py` | Offline CLI: `validate`, `plan`, `import-capture`. Never connects to Studio. |
| `tool/c1c/harness-spec.schema.json` | Draft 2020-12 contract for a harness spec. |
| `tool/c1c/example-spec.json` | C1B-reproducing example; no run is authorized by its presence. |
| `tool/c1c/studio_rig.luau` | In-Studio rig/cleanup helper for a future authorized MCP run. Not auto-run and not mapped by Rojo. |
| `tests/test_c1c_harness.py` | 45 mocked lifecycle, safety, evidence, provenance and recovery tests (22 C1C + 23 C1D-R1 hardening). |
| `art/imports/roblox-assets.json` | Project-local cloud asset provenance. Not a B1 registry journal or approval. |

### 3.2 Component flow

```text
spec JSON ──schema──> HarnessSpec ──> RigPlan ──> StudioAdapter
                                  │                 │
                                  ├──> Baseline      ├──> in-memory (tests only)
                                  ├──> Capture plan  └──> future MCP adapter
                                  ├──> Cleanup checks
                                  └──> EvidenceStore (report.json, captures/, state.json)
```

The Python harness never calls Roblox directly. A real run needs an adapter that translates its snapshots and mutations into Studio MCP calls. C1C deliberately does not ship such an adapter: it cannot be tested here, and executing it would violate the milestone restriction. `InMemoryStudioAdapter` is marked `simulates_studio: true`; every report records `studio_touched: false`.

A real adapter must return a **stable, curated** set of pre-existing object properties (for example `Anchored`, `Size`, `Position`, `Transparency`, `Material`, `Texture`, `Face`, tiling and offsets). It must not dump volatile engine properties into the baseline, because the comparison is intentionally fail-closed and exact.

The snapshot must also declare `"complete": true` and be internally consistent:

- every `path` must equal `parent.name` (with `Workspace` as the root);
- every `parent` and every listed `children` entry must exist exactly once;
- every object must be reachable from `Workspace` with no cycles or duplicates;
- the `tagged` index must agree with each object's `tags` list;
- `workspace`, `camera` and `selection` must be present with the expected shapes.

A snapshot missing the completeness assertion, or with any structural gap, is treated as **unsafe for deletion**. `validate_snapshot()` reports the issues and `verify_ownership()` turns them into violations; cleanup refuses to call `destroy()`.

## 4. Run specification

The schema is `tool/c1c/harness-spec.schema.json`; `tool/c1c/example-spec.json` is the reference. Required fields:

| Field | Meaning |
| --- | --- |
| `run_id` | Unique, path-safe ID (`[A-Za-z0-9][A-Za-z0-9_-]{0,63}`); becomes `Workspace.C1C_TextureTest_<run_id>`. |
| `asset.asset_id` | Existing `rbxassetid://<positive integer>` only. |
| `asset.asset_type` | `image` (Texture/Decal import verification). |
| `asset.source_path`, `asset.source_sha256` | Source file and expected hash; re-verified against the manifest and disk. |
| `asset.status` | Must be `test_only_unapproved`. |
| `asset.upload` | Must be `false`. The harness has no upload path. |
| `asset.manifest_path` | Defaults to `art/imports/roblox-assets.json`. |
| `studio` | `studio_id`, place label, `mode: edit`, `team_create: false`. |
| `texture_scales` | 2–8 named `studs_per_tile` values; drives the panel grid. |
| `geometry` | Grid origin, panel size, columns, gap, labels, seam pair. |
| `screenshots` | Capture ID, phase (`pre_rig`/`rig`/`post_cleanup`), purpose, required flag, optional camera position/look-at. |
| `cleanup` | Baseline verification, safe-rename policy, failure-evidence preservation. |
| `evidence` | Must be `registry/evidence/c1c`; durable-file requirement; capture retries. |
| `b1` | `registry_unchanged: true`; the harness fingerprints the journal before/after. |
| `b2` | Optional B2 report path and a requirement that all `registry_gate_claims` remain `pending`. |

## 5. Lifecycle

1. **Preflight:** validate the spec, manifest, source hash, B2 report and Studio identity; refuse if Team Create, the wrong Studio ID, any pre-existing `C1C_` tag/object, or an existing run report is found.
2. **Baseline:** record Workspace children, attributes, tags, selection, camera CFrame/type/viewport, and every existing object's class/attributes/tags/properties.
3. **Pre-rig captures:** e.g. the untouched scene.
4. **Rig creation and preload:** create exactly one run folder and its planned descendants. Every object is `C1C_`-prefixed, carries `C1C_RunId` and `C1C_TestOnly=true`, and is tagged `C1C_TextureTest`. Build success and preload success are recorded separately (`rig.build_success`, `rig.preload_success`, `rig.build_phase`, `last_confirmed_build_phase` in `state.json`). A preload failure is fatal even though the build succeeded.
5. **Rig verification:** verify the run root is a `Folder`, the snapshot is complete, every descendant is owned and expected, and the planned inventory is complete. A partial or unexpected rig fails **before** any rig capture; the failure record lists the last confirmed build phase and partial objects.
6. **Rig captures:** for each capture, apply the requested camera if any, take the capture, compare camera before/after, restore the baseline camera, verify it exactly, and restore viewport size only if the adapter declares explicit support. A capture whose ID differs from the request, or that returns both bytes and a path, is rejected as invalid.
7. **Cleanup:** re-read Studio; verify every owned object and the expected inventory; refuse deletion on any mismatch; optionally rename repairable `Texture`/`Decal` children; then perform a **fresh** complete ownership read immediately before destroying only the verified folder; verify the Workspace baseline.
8. **Failure cleanup:** a non-interruption exception during creation/configuration/preload triggers camera restoration and an ownership-verified cleanup. If ownership, snapshot completeness or camera restoration cannot be established, nothing is deleted and `cleanup-failure-N.json` preserves the last phase, partial objects, ownership payload and a `next_action` for recovery. A simulated interruption remains recoverable and is never auto-deleted.
9. **Post-cleanup capture:** confirm the restored scene visually.
10. **Finalize:** re-check camera, viewport, selection, tags, Workspace baseline, provenance and B1 fingerprint; write a new-only report.

The run state journal (`state.json`) is intentionally mutable and is used by recovery. Immutable evidence (`report.json`, capture files, failure records) is new-only.

## 6. Restoration and cleanup rules

### 6.1 Camera

- Baseline CFrame (12 components) and `CameraType` are recorded before the rig exists.
- Before and after every capture, the camera is read. A mismatch is recorded as `camera_drift_detected` with the before/after values and maximum component delta.
- The harness writes the exact baseline CFrame and type back, then re-reads and requires a match within `1e-6`.
- If restoration cannot be verified, the run stops before cleanup and leaves the rig in place. It does not pretend the camera is restored.

### 6.2 Viewport

- The baseline viewport size is recorded.
- A changed viewport is recorded as an event.
- Restoration is attempted only when the adapter exposes `supports_viewport_restore = True` and implements `set_viewport_size`.
- If no supported method exists, the change is a residual effect: `viewport.restored = false`, `restoration.complete = false`, and the final result is at most `PASS_WITH_RESIDUALS`. A UI/session side effect is never reported as a full restoration.

### 6.3 Ownership and deletion

Deletion is allowed only when **all** of the following hold:

- the run root exists and is an actual `Folder` (class check, not just presence);
- the adapter snapshot declares `complete: true` and passes structural validation;
- every descendant is `C1C_`-prefixed (or is a separately verified repairable `Texture`/`Decal` name);
- every descendant has `C1C_RunId == <run_id>`;
- every descendant has `C1C_TestOnly == true`;
- every descendant has the `C1C_TextureTest` tag;
- the visible descendants exactly match the deterministic planned inventory (no missing objects unless explicitly allowed for a partial-build/recovery cleanup, and no unexpected objects);
- no tagged, `C1C_`-prefixed, or run-ID-attributed object exists outside the run folder;
- a **fresh** snapshot, taken immediately before `destroy()`, still satisfies every check above.

A `Texture`/`Decal` child named `Texture`/`Decal` is a **repairable naming inconsistency**, not permission to delete. It is renamed only after its tag/run-ID ownership is verified, only when `allow_safe_rename` is true, and only if the proposed name is free. Otherwise cleanup aborts and preserves evidence. Normal end-of-run cleanup requires a complete planned inventory; partial-build and recovery cleanup may accept a fully owned subset.

Cleanup never calls `ClearAllChildren()`, never deletes by name alone, and never "fixes" a template object to make baseline comparison pass. Failure records (`cleanup-failure-N.json`) list the relevant objects, attributes, tags, ownership payload, last confirmed phase, partial objects and a `next_action`.

## 7. Evidence rules

| Situation | Result |
| --- | --- |
| Adapter returns PNG bytes or a real file path | Validate PNG/decodability/not-all-black-or-transparent, copy new-only into `registry/evidence/c1c/<run>/captures/`, record the **actual** SHA-256, size and dimensions. |
| Adapter returns inline-only image data | Record capture ID, camera, viewport and observation. `storage: inline_only`; `evidence_path` and `sha256` stay `null`. No file is invented. |
| Required capture is missing/empty/corrupt/all-black | Mark invalid, retry up to `capture_retries`, then fail the run. The rig is still cleaned up. |
| Operator has a real screenshot file | `python tool/c1c_verify.py import-capture --spec <spec> --run-id <id> --capture-id <id> --image <absolute path>` copies and hashes the actual file and writes a separate `manual-capture-<id>.json`. The spec, run ID, capture ID, phase and report spec hash must all match; the capture must still be `inline_only` in the original report, and duplicate/unexpected/mismatched imports are rejected. The original report remains truthful about the inline-only capture. |
| Adapter returns a different capture ID or an ambiguous payload | Rejected as invalid evidence; it is not bound to the requested capture. |

Durable files are written new-only; the recorded SHA-256/size are computed from the bytes that actually reached the file. `evidence.complete` means all required captures are accounted for and, when `require_durable_files` is true, all are durable files. `evidence.accepted` is stricter: it is true only when every required capture has a durable, hashed file, even for a diagnostic run where durable files are optional. Neither flag means the image is visually acceptable: the harness can check bytes only, not scene content, lighting, compression or visual quality. Reports from the in-memory adapter are marked `evidence_kind: simulated_test_only`, `simulates_studio: true` and `studio_touched: false`; they must never be presented as Studio captures.

## 8. Recovery

If the process stops after the baseline but before cleanup, `state.json` contains the baseline, phase and run provenance. `recover(root, spec, adapter)`:

1. requires a resumable state and the **original** recorded baseline;
2. verifies provenance: schema version, run ID, spec SHA-256, baseline identity, the original B1 registry fingerprint, the asset manifest identity, and the expected object inventory/list;
3. **never captures or substitutes a new baseline**, and rejects recovery if any required provenance field is absent or inconsistent (including a changed spec with the same run ID, a changed manifest, or a B1 change between crash and recovery);
4. re-reads Studio rather than trusting the journal;
5. restores the recorded baseline camera and verifies it;
6. runs the same ownership-verified cleanup, including the fresh pre-destruction check (a partial rig is acceptable only if every existing object is owned and expected);
7. does **not** repeat any screenshots;
8. writes a new `recovery-N.json`, records the provenance checks, and reports `RECOVERED` / `RECOVERED_WITH_RESIDUALS` honestly.

A recovery report intentionally does not re-evaluate capture completeness: `recovery.captures_repeated` is `false`, and `evidence.complete` may be false because the recovery took no screenshots. The original interrupted report remains the record of any captures that were attempted. Recovery's B1 window starts at the original run, not at recovery time.

If the journal is corrupted, provenance is incomplete, the folder is missing but tracked objects remain, an object is unowned/unexpected, the snapshot is incomplete, or the camera cannot be restored, recovery refuses unsafe actions and reports failure.

## 9. B1/B2 integration and non-approval boundary

- `art/imports/roblox-assets.json` records that `112705883084796` exists, is test-only, and is not an approval. The harness requires that status and never uploads.
- `registry/events.jsonl` is fingerprinted before and after. Any change fails the run. The harness never appends to it.
- A B2 report may be linked only if its source SHA-256 matches and all `registry_gate_claims` remain `pending`. The claims map and every row are validated; a malformed row (non-object, missing/non-string `result`, non-list `evidence`) is rejected instead of being silently ignored. A non-pending claim is rejected rather than treated as an approval.
- The report contains no B1 gate passes and no production status. A C1C run is in-engine **evidence for review**, not a B1 `imported` or `approved` transition.

## 10. Duplicate-upload prevention

1. The spec schema requires `upload: false`.
2. `StudioAdapter` has no upload method; a test adapter deliberately provides a spy `upload_asset` that must never be called.
3. The asset ID must already exist in the manifest as `test_only_unapproved`.
4. Duplicate manifest asset IDs are rejected.
5. Source bytes are re-hashed; a changed source or hash stops the run before any Studio mutation.

## 11. Mocked test coverage

`python -m unittest discover -s tests -p 'test_*.py' -v` covers 45 C1C tests (22 original + 23 C1D-R1 hardening):

| Area | Test |
| --- | --- |
| Successful lifecycle | durable hashed captures, inline-only honesty, B1 unchanged, no upload calls |
| Camera drift | drift detected, baseline restored, exact delta verified |
| Viewport | unsupported restore stays residual and `restoration.complete` false; supported restore verified |
| Missing/invalid screenshots | empty, black and corrupt PNGs are not evidence; rig still cleaned |
| Cleanup failures | destroy failure preserves evidence and does not claim success |
| Unexpected objects | unrelated object inside the rig blocks deletion; unrelated Workspace object fails baseline verification and is left alone; a newly created rig with a missing tag fails before any rig capture |
| Wrong run ID/tag | deletion refused and failure evidence preserved |
| Naming inconsistency | raw `Texture` child blocks by default; safe rename passes only with verified ownership |
| Interrupted recovery | partial rig recovered without repeating captures |
| Duplicate upload | upload request rejected; spy never called; unlisted asset and hash mismatch rejected |
| B2 contract | pending gates accepted; non-pending claim rejected |
| B1 contract | a registry journal created during the run is detected and fails the run |
| Spec safety | traversal/absolute spec paths, unsafe run IDs and wrong evidence directories rejected |
| Rig plan | C1B panel positions, seam offset, tags/attributes; 25-object count (was reported as 26) |
| CLI | `validate`/`plan` produce the expected plan and write nothing |
| Strict ownership (C1D-R1) | run root must be a `Folder`; incomplete marker; structural child gap; unexpected owned object inside; tagged/run-attributed object outside; fresh pre-destruction recheck rejects a stale passing read |
| Partial-build recovery (C1D-R1) | creation exception safely cleans a fully owned partial rig; preload failure is distinct from build success; partial rig refuses rig captures; unverified cleanup preserves `next_action` |
| Original-run integrity (C1D-R1) | recovery rejects changed spec, changed B1, changed manifest and every missing provenance field; successful recovery is bound to the original baseline/spec/B1 |
| Evidence binding (C1D-R1) | malformed B2 rows; capture-ID mismatch; ambiguous bytes+path; durable acceptance withheld without required durable files |
| Correctness (C1D-R1) | pinned `test_only_unapproved` status; schema-version check; Luau plan-validation/fresh-recheck source contract |

## 12. Offline verification (C1C)

| Check | Result (C1D-R1 re-run, 2026-10-17) |
| --- | --- |
| `python -m unittest discover -s tests -p 'test_*.py' -v` | **PASS: 86 tests, 1 Windows symlink skip** (41 prior + 45 C1C) |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events** |
| `python tool/validate_art.py` | **PASS** (2 metaschemas, 5 presets, 3 positive and 36 negative request fixtures; no files written) |
| `python -m compileall -q tool/c1c_harness.py tool/c1c_verify.py tests/test_c1c_harness.py` | **PASS** |
| `stylua --check` / `selene` on `tool/c1c/studio_rig.luau` | **PASS** (0 errors, 0 warnings, 0 parse errors) |
| `python tool/c1c_verify.py validate --spec tool/c1c/example-spec.json` | **PASS**; no evidence or registry write |
| `python tool/c1c_verify.py plan --spec tool/c1c/example-spec.json` | **PASS**; 25-object deterministic plan, no Studio call, no evidence directory created |
| `git diff --check` | **PASS** (no output) |

The Windows symlink test skip is the pre-existing platform limitation in the B1 suite; no new test is skipped.

## 13. Limitations and what remains unverified

- **No live Studio adapter was implemented or executed.** The Python side is fully tested against an in-memory double; the Luau helper is linted/format-checked only. The MCP binding is the remaining integration step and requires a separately authorized execution milestone.
- **Snapshot completeness is an adapter contract.** The harness fails closed on an incomplete or inconsistent snapshot, but it cannot prove a malicious/buggy adapter enumerated the real tree. The live adapter must enumerate every descendant and set `complete: true` only after doing so.
- **A concurrent mutation remains a theoretical TOCTOU.** A plugin/operator change between the fresh ownership read and the folder `Destroy()` is not prevented by either helper.
- **The Luau helper was not run in Studio.** It now validates plans, refuses pre-existing `C1C_` objects, cleans a fully owned partial build, distinguishes preload failure and re-verifies before `Destroy()`, but it must still be loaded through `execute_luau` and validated against a real scene before it is depended on.
- Inline-only images carry no hash and cannot be validated by the harness; only the capture ID, camera settings and operator observations exist.
- An image signature/size/blackness check does not prove the expected scene, absence of a placeholder, UV correctness, filtering, compression, lighting or visual acceptance.
- Edit-mode capture is not target-device FPS, memory, input or gameplay verification.
- The asset manifest, operator-supplied screenshots and B2 reports are local, operator-trusted records, not Roblox attestations.
- No save, publish, asset upload, B1 event, approval, ComfyUI call or Swarm plan/task change occurred in C1C.

## 14. Future authorized execution outline

A future milestone must separately authorize Studio access and the run ID. The intended flow is:

1. `python tool/c1c_verify.py validate --spec <spec>` (read-only preflight).
2. `python tool/c1c_verify.py plan --spec <spec>`; pass `.luau_plan` to `C1C.buildFromPlan` through Studio MCP.
3. Capture the baseline and rig views through MCP; pass the capture IDs/camera settings into the execution log.
4. `C1C.cleanup(runId, allowSafeRename)` and verify the returned ownership/post-cleanup data.
5. Save any real inline images through the client or `import-capture`; never invent a path.
6. Run the Python harness with a real MCP-backed adapter (to be implemented) if automatic orchestration is desired.
7. Record the result as test-only. Do not save/publish and do not write a B1 event.

Until steps 1–7 are authorized, C1C is an offline implementation only.

## 15. Git checkpoint recommendation (no commit made)

`git status` currently shows 248 untracked paths and one modified tracked file (`.gitignore`). Nothing was staged, committed, pushed, deleted or rewritten in C1C.

### 15.1 Important untracked source and documentation (recommended for a checkpoint)

| Path | Reason |
| --- | --- |
| `tool/c1c_harness.py`, `tool/c1c_verify.py`, `tool/c1c/` | C1C implementation, schema, example and Luau helper. |
| `tests/test_c1c_harness.py` | 22 mocked C1C tests. |
| `tool/asset_registry.py`, `tool/registry.py`, `tool/texture_qa.py`, `tool/validate_texture.py`, `tool/image_generation.py`, `tool/generate_asset.py`, `tool/b3_postprocess.py`, `tool/texture_seam_check.py`, `tool/validate_art.py` | B1/B2/B3 source referenced by this status and tests. |
| `tests/test_asset_registry.py`, `tests/test_texture_qa.py`, `tests/test_image_generation.py` | Existing regression suite (63 tests total). |
| `docs/` (C1A, C1B, C1C, implementation status) and `status.md` | Decision/evidence history and handoff. |
| `art/` schemas, presets, contracts, requests, `art/imports/roblox-assets.json` | Art/B1/B3 contracts and test-only asset provenance. |
| `workflows/` scripts, README, reference workflow and final candidate PNGs | Reproducible texture correction/generation sources. |
| `.gitignore` modification | Transient/secret rules; preserve and review before committing. |
| `opencode.json`, `flux3-stone-workflow.json`, root seam evidence/assessment | Local configuration and reference evidence; no secret was found in `opencode.json`. |

### 15.2 Evidence and large artifacts (decide separately)

| Path | Approx. size | Recommendation |
| --- | --- | --- |
| `registry/evidence/texture-qa-*` (41 files) | ~56 MB | Keep the JSON/Markdown reports and small crops. The multi-MB 3×3/5×5 PNGs are reproducible; commit only with Git LFS or an explicit evidence-retention decision. |
| `workflows/textures/*-3x3.png` (28 files) | ~45 MB | Same: source scripts and final PNGs are small; tiled previews dominate size. |
| `registry/staging/b3/...` | ~26 KB | Small provenance; suitable for a checkpoint. |
| `outputs/generated/b3-stone-paving-0001/` | ~3.8 MB | Two candidate PNGs plus evidence; suitable for a checkpoint. |
| `outputs/b4-stone-correction/` | ~154 MB, 123 files | Most are `_scratch/` debug images/scripts. Exclude `_scratch/` from a commit; keep only the finalists, comparison, metrics and B2 evidence. |

### 15.3 Safe checkpoint proposal (requires operator approval)

1. Add `outputs/*/_scratch/` (or the specific B4 scratch path) to `.gitignore` and confirm no tracked file is affected.
2. Stage only source/docs/tests/schemas/manifests/small JSON evidence and the selected final candidate PNGs.
3. Do not stage multi-MB regenerable previews unless Git LFS is approved.
4. Review `git diff --check`, `git status`, and the diff of `.gitignore` before committing.
5. Keep `registry/events.jsonl` absent (currently 0 assets, 0 events). Never commit a live lock or a secret.

C1C itself does not perform any of these Git actions.
