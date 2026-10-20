# Milestone C1B — Import Authorization Preflight and Reversible Studio Test Plan

- **Date:** 2026-10-17
- **Scope:** C1B preparation only. This document does not upload an asset, create or modify Studio objects, save/publish a place, or change B1 registry state.
- **Status:** **PREFLIGHT COMPLETE — EXECUTION NOT AUTHORIZED.**
- **Blocking decision:** the only verified upload principal is the signed-in Studio user. No group, universe, place ID, or published experience is bound to the open place. The target creator/group and intended test experience must be confirmed by the operator before any upload or Studio test object is created.
- **Asset:** `workflows/textures/b21/stone-seamless-v4-lossless-opt.png`
- **SHA-256:** `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a`
- **Proposed Studio instance:** `Roblox_Template`, `studio_id` `577768ad-49d8-42f5-ac96-8c66cd12a144`
- **Proposed local test place:** unsaved `Place1` in that Studio instance (not a published experience)
- **B1 registry:** unchanged at 0 unique assets, 0 events. C1B is not a B1 import and must not create a B1 `imported` or approval event.

## 1. Decision summary

C1B can be executed as a **single, isolated, reversible Studio test** once the operator confirms the creator principal, the intended place, and authorization to create one persistent cloud image asset. The test is deliberately out of band: it is a technical import/render check, not a production approval, not a B1 registry transition, and not a game publication.

The proposed path is:

1. Upload the byte-verified PNG once through Roblox Studio's asset-upload capability, using a temporary localhost HTTP server and a test-only staged filename.
2. Apply the returned asset ID to temporary `Texture` instances on temporary parts at four tiling scales, plus one cross-part seam pair.
3. Capture MCP screenshots with Studio visible and foregrounded, validating each image before treating it as evidence.
4. Destroy only the tagged temporary rig, restore the camera, and verify the Workspace and camera against a recorded baseline.
5. Leave the cloud asset in place and record its ID as **test-only, unapproved**; never save/publish the place and never write a B1 event.

**The only irreversible effect is the cloud image upload.** Everything Studio-side in this design is designed to be removable before the place is saved. The upload itself cannot be automatically removed by this project.

## 2. Inputs reviewed

- `status.md` (through section 2.13)
- `docs/C1A_PREFLIGHT.md` (including the resumed capture that resolved the empty-viewport blocker)
- `art/README.md`, `art/REGISTRY_B1.md`, `art/TEXTURE_QA_B2.md`
- `workflows/textures/README.md`, `workflows/textures/b21/REVIEW.md`
- `art/presets/adventure-fantasy.json` result through the B2 CLI
- `registry/evidence/texture-qa-b21/stone-seamless-v4-lossless-opt-f18d45a9bf68-782b2c956c40.json`
- `default.project.json`, `.gitignore`, `tool/publish.env`, `Documentation/GitHub_Roblox_Publish.md`
- Live Roblox Studio MCP read-only inspection (instance, state, hierarchy, properties, console, one capture)
- Live B1 registry validation and B2 dry-run

## 3. Asset verification

### 3.1 File facts

| Property | Verified value | Method |
| --- | --- | --- |
| Path | `workflows/textures/b21/stone-seamless-v4-lossless-opt.png` | filesystem |
| SHA-256 | `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a` | `Get-FileHash -Algorithm SHA256` |
| Size | **2,038,645 bytes** | filesystem |
| Format | PNG, 8-bit RGB, opaque, no alpha channel | Pillow decode |
| Dimensions | **1024 x 1024** | Pillow |
| Decoded RGB estimate | 3,145,728 bytes | 1024 x 1024 x 3 |
| Preset byte cap | 2,097,152 bytes; **58,507 bytes under** | B2 / Adventure Fantasy preset |
| Pixel equality | **Identical to `workflows/textures/stone-seamless-v4.png`** after RGB decode | Pillow `ImageChops.difference` |
| Historical QA evidence | `registry/evidence/texture-qa-b21/` | 3x3 (3072x3072), 5x5 (1280x1280), seam crop (512x512) |

The hash matches the expected value supplied for C1B. The file is the losslessly optimized derivative of the corrected v4 texture; it has the same decoded pixels as v4 and is smaller only because of PNG re-encoding. The original FLUX output and corrected v4 remain unchanged.

### 3.2 QA evidence

The unchanged B2-1.2 validator was re-run in **dry-run** mode (no evidence written) against the Adventure Fantasy baseline preset:

| Check | Result | Detail |
| --- | --- | --- |
| Style profile resolution | PASS | `adventure-fantasy` v1.0, SHA-256 `8b5389...10cd` |
| File exists / readability / RGB / opaque | PASS | 2,038,645 bytes; full decode |
| `texture_budget` | PASS | 1024/1024 px; 2,038,645 / 2,097,152 bytes |
| `edge_screen` | PASS | right-left/neighbor 0.941, bottom-top/neighbor 1.146; max 1.25 |
| `tone_screen` | PASS | 8 px blurred means 2.882, 4.918; max 8 |
| `repeated_motif_screen` | PASS | broad std 2.983, p99 deviation 7.326; no large-motif alert |
| SHA-256 integrity | REVIEW_REQUIRED | B2 had no expected hash argument; C1B independently verifies the operator-supplied hash |
| Metadata / delivery intent | REVIEW_REQUIRED | No B1 request supplied |
| Style compliance | REVIEW_REQUIRED | Human judgment at intended scale |
| Visual seamlessness / repetition | REVIEW_REQUIRED | Numerical screens do not establish perceptual acceptance |
| In-engine suitability | REVIEW_REQUIRED | UV, filtering, compression, lighting, device untested |
| Exact opposing-edge equality | FAIL (informational) | Not a hard B2 gate; not required for perceived tiling |
| Overall automated result | **REVIEW_REQUIRED** | No hard automated failure; no approval |

**Interpretation:** the image clears the automated budget and seam-screening heuristics and is suitable as the first import-test candidate. It is **not** B1-approved, not a human QC pass, and not an in-engine verification. All B1 gates remain pending.

## 4. Live Studio and account inspection (read-only)

### 4.1 Instance and mode

| Property | Value |
| --- | --- |
| Connected Studio instances | exactly 1 |
| Instance name | `Roblox_Template` |
| `studio_id` | `577768ad-49d8-42f5-ac96-8c66cd12a144` |
| Studio mode | Edit; only Edit DataModel available |
| Studio process | `RobloxStudioBeta`, PID 96800, title `Place1 - Roblox Studio`, responding |
| Place name | `Place1` |
| Place ID | **0** (unpublished/local) |
| Game/universe ID | **0** (no published experience) |
| Creator ID | **0** |
| Creator type | `Enum.CreatorType.User` |
| Signed-in Studio user | **`aurory_naru`**, user ID **11822718311** |
| Open Cloud key present | No (`ROBLOX_API_KEY` absent; no `.env.publish`) |
| `tool/publish.env` | `UNIVERSE_ID=0`, `PLACE_ID=0` |

The place is an unsaved local place; the Studio title confirms `Place1`, and the DataModel has no published identity. No group ownership is evidenced. The GarfGames organization is documented as the CI/repository organization, but **that is not evidence that this place or upload target belongs to GarfGames**. Do not infer or guess the target group from the repository.

### 4.2 Workspace baseline

The baseline was recorded read-only and is the reference for cleanup verification.

| Object | Baseline properties |
| --- | --- |
| `Workspace` | 4 direct children: `Camera`, `Baseplate`, `Terrain`, `SpawnLocation`; no attributes; no CollectionService tags |
| `Workspace.Camera` | `CameraType.Fixed`; position `(-23.400354, 34.181324, -41.904236)`; focus `(-2.886278, 9.212833, -2.886278)`; viewport `1219 x 793` |
| `Workspace.Baseplate` | `Part`; position `(0, -8, 0)`; size `(2048, 16, 2048)`; `Transparency=0`; `Anchored=true`; `Material=Plastic`; top surface at `y=0` |
| `Baseplate.Texture` | `Texture` on `Top`; `rbxassetid://6372755229`; `StudsPerTileU=8`, `StudsPerTileV=8`; offsets `0,0`; `Transparency=0.8` |
| `Workspace.SpawnLocation` | position `(0, 0.5, 0)`; size `(12, 1, 12)` |
| `SpawnLocation.Decal` | `Decal` on `Top`; `rbxasset://textures/SpawnLocation.png`; `Transparency=0` |
| `Workspace.Terrain` | no children |
| `Selection` | 0 selected |
| `Workspace.StreamingEnabled` | `true` |
| Lighting | `ClockTime=14.5`, `Brightness=3`, `Ambient=OutdoorAmbient=0.27451,0.27451,0.27451`, `GlobalShadows=true`, `EnvironmentDiffuseScale=1`, `EnvironmentSpecularScale=1` |

Exact camera CFrame components were recorded for restoration: position `(-23.400354385375978, 34.18132400512695, -41.90423583984375)`, right vector `(-0.8851209878921509, 0, 0.465361088514328)`, up vector `(0.22934997081756593, 0.870118260383606, 0.4362257122993469)`, look vector `(0.4049191474914551, -0.49284303188323977, 0.770159900188446)`.

### 4.3 Screenshot path

- One read-only capture (`C1B_preflight_1`) was taken against this instance with no camera arguments.
- The returned viewport image (~1223 x 753) is **valid**: blue sky, the checker-grid Baseplate extending to the horizon, and the centered white SpawnLocation with its decal are visible.
- At capture time the Studio window was visible and responding but **not the foreground window** (foreground PID 24696; Studio PID 96800). The image is a valid content sanity check but does **not** satisfy the C1B foreground precondition.
- Execution captures must be taken with Studio verified as the foreground window; black or empty captures are invalid evidence.

### 4.4 Console state

Pre-existing console output includes loader bootstrap success messages, repeated `UIBlox` `FoundationProvider` warnings, and `rbxassetid://203785492` "Asset type does not match requested type" errors. These are recorded as pre-existing output and are not asserted as an import-test defect. Any new asset-loading error during C1B is a stop condition.

## 5. Target creator account/group and test experience

### 5.1 What is verified

- The Studio session is authenticated as **`aurory_naru` (user ID 11822718311)**.
- That account is the only verified principal that could own an upload initiated from this Studio session.
- The open place is an **unsaved local `Place1`** in `Roblox_Template`; `PlaceId=0`, `GameId=0`, `CreatorId=0`, `CreatorType.User`.
- No group is bound to the place by the DataModel.
- No Open Cloud credentials or nonzero universe/place IDs are available.

### 5.2 What is not verified

- Whether `aurory_naru` is the **intended** creator/upload owner.
- Whether the intended target is a **group** and, if so, which group, its ID, and whether the session account has group asset-upload permission.
- Whether the intended test place is the current unsaved `Place1` or a specific published test experience (universe/place ID).
- Whether the account is permitted to upload images at all (account restrictions, moderation, rate limits).
- Whether the MCP upload capability uploads under the user, the place owner, or a group when the place is unpublished.

### 5.3 Stop condition

Per the milestone restriction "Stop if required permissions or account details cannot be verified," **no upload or Studio mutation may occur until the operator confirms all three target facts**:

1. Creator principal (user `aurory_naru` / user ID 11822718311, **or** a named group with ID and verified upload role).
2. Test experience (the current unsaved local `Place1`, **or** a named universe/place ID opened in Studio).
3. Authorization to create one persistent cloud asset under that principal (section 13).

This is a confirmation gap, not a failure of the Studio connection or the asset. The plan below is ready to execute once the gap is closed.

## 6. Asset-import capabilities and permissions

### 6.1 Available capabilities (tool surface inspected, not executed)

| Capability | Status | Notes |
| --- | --- | --- |
| Studio MCP read/inspect | **Verified** | Instance, state, hierarchy, properties, console, capture |
| Studio MCP screenshot | **Verified** | One valid capture; foreground gate still required at execution |
| Studio MCP `upload_image` | **Available, not executed** | Accepts HTTP(S) image URLs; returns `{url: "rbxassetid://..."}` |
| Studio MCP `insert_asset` | **Available, not needed** | Could insert an asset object; C1B instead assigns the ID to a temporary `Texture` |
| Studio MCP Luau write | **Available, not executed** | Will be limited to the tagged test rig and camera restoration |
| Open Cloud asset/place upload | **Not available** | No API key; universe/place IDs are 0 |
| Manual Studio Asset Manager upload | **Fallback, operator-only** | Creates the same persistent cloud asset; requires operator UI action and ID handoff |
| Group-owned upload | **Unverified** | No group-bound place or group permission evidence |

Studio services `AssetImportService`, `BulkImportService`, `AssetManagerService`, `PublishService`, and `StudioPublishService` are present in the DataModel, but service presence does not prove an upload permission or a supported programmatic import path. The MCP `upload_image` tool is the only automated image-upload path identified.

### 6.2 Supported procedure

**Primary (MCP):** serve the staged PNG from a temporary loopback HTTP server, call `roblox_studio_upload_image` with the exact URL, capture the returned asset ID, then stop the server. This is the only automated path exposed by the current MCP server.

**Fallback (manual):** the operator uploads the same file through Studio's Asset Manager, records the resulting asset ID, and supplies it. The asset is still persistent; the same authorization and recording rules apply. No Open Cloud path is proposed because the required key and IDs are absent.

### 6.3 Permission and persistent-change matrix

| Action | Permission evidence | Persistent effect |
| --- | --- | --- |
| Read Studio state/properties | Verified | None |
| Capture screenshot | Verified | None (inline image only) |
| Create temporary parts/Texture objects | Tool available; requires authorization | In-memory/local place only until save; removable |
| Temporary camera override for framing | Tool available; requires authorization | Camera restored and verified; no lasting effect |
| Upload image to Roblox | Tool available; Roblox permission **unverified** | **Persistent cloud asset**; cannot be automatically removed |
| Save place | Forbidden in C1B | Would persist test objects locally/cloud |
| Publish place | Forbidden in C1B | Would publish to players |
| B1 registry transition | Forbidden in C1B | Would create a false approval/import record |

## 7. Proposed import procedure (not executed)

### 7.1 Preconditions

- Operator confirms section 5.3 and authorizes section 13.
- Studio is open on the confirmed place, in **Edit** mode, with no playtest running.
- Studio is visible and foregrounded for every capture.
- No Team Create/collaboration session is active. If collaboration is detected, stop; another user could receive the temporary objects.
- The source PNG hash is re-verified immediately before staging.
- A run ID is assigned, e.g. `c1b-20261017-01`; all temporary objects and evidence use it.

### 7.2 Upload steps

1. **Re-verify the source.**
   `Get-FileHash -Algorithm SHA256 workflows/textures/b21/stone-seamless-v4-lossless-opt.png`
   Must equal `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a`.
2. **Stage a byte-identical test copy** in a temporary directory outside the project, named `C1B_TEST_ONLY_stone-seamless-v4-lossless-opt.png`. This makes the intended test-only status visible in the asset name where the upload path derives a name from the file. Verify the copy's hash is identical.
3. **Start a loopback-only HTTP server** from the temporary directory:
   `python -m http.server 8765 --bind 127.0.0.1 --directory <temp-dir>`
   No dependency is installed; this uses the Python standard library.
4. **Verify the served bytes** by downloading the URL locally and comparing its SHA-256 to the source. Do not upload until this matches.
5. **Upload once** with:
   `roblox_studio_upload_image(studio_id="577768ad-49d8-42f5-ac96-8c66cd12a144", imagePaths=["http://127.0.0.1:8765/C1B_TEST_ONLY_stone-seamless-v4-lossless-opt.png"])`
   Record the complete raw response, including the URL-to-asset-ID map and any asset type metadata.
6. **Stop the HTTP server immediately** and delete the temporary directory after recording its path and the copy hash.
7. **Check for ambiguity before continuing.** If the response is missing, contains more than one asset ID, or reports an error, stop. Do not retry blindly: a retry can create a duplicate persistent asset. Check the Creator Dashboard/inventory for the actual result and record it.
8. **Load-check the asset** by creating one temporary `Texture` on a temporary part and calling `ContentProvider:PreloadAsync` with a timeout. A moderation or type failure is a stop condition; do not treat a placeholder as visual evidence.
9. **Record the asset metadata** (asset ID, type if reported, uploader/session account, timestamp, source hash, staged filename, HTTP server port, and the fact that this is test-only/unapproved). The asset type must be recorded from the response or Creator Dashboard, not assumed.

### 7.3 Failure handling

- **401/403/permission denied:** stop; report the exact response; do not retry or switch accounts without operator authorization.
- **Moderation/pending:** stop the visual test; record the asset ID as pending; do not present a placeholder as evidence.
- **Wrong asset type / not usable as a Texture:** stop; report the actual type; do not substitute a different asset or upload a different file without authorization.
- **Duplicate asset created:** stop; record both IDs; do not continue until the operator decides which one, if any, is the test asset.
- **Staging/hash mismatch:** stop before upload.

## 8. Reversible isolated Studio test design

### 8.1 Isolation rules

- Create exactly one folder: `Workspace.C1B_TextureTest_<runid>`.
- Create only the objects listed in section 8.2 under that folder. Do not reparent, rename, or edit `Baseplate`, `Baseplate.Texture`, `SpawnLocation`, `SpawnLocation.Decal`, `Terrain`, or `Camera`.
- Every created instance receives:
  - name prefix `C1B_`
  - attribute `C1B_RunId = "<runid>"`
  - attribute `C1B_TestOnly = true`
  - CollectionService tag `C1B_TextureTest`
- No scripts, no gameplay logic, no server/client code, no UI beyond temporary BillboardGui labels.
- No save, no publish, no playtest in C1B. Edit-mode rendering is the scope; runtime/device behavior remains untested.

### 8.2 Test rig

A 2x2 grid of 32 x 32 stud flat panels is placed on the Baseplate in a clear area away from the spawn, centered near `(0, 0.5, 65)`:

| Object | Center | Size | Tiling |
| --- | --- | --- | --- |
| `C1B_Panel_4spt` | `(-18, 0.5, 47)` | `(32, 1, 32)` | `StudsPerTileU/V = 4` |
| `C1B_Panel_8spt` | `(18, 0.5, 47)` | `(32, 1, 32)` | `StudsPerTileU/V = 8` |
| `C1B_Panel_16spt` | `(-18, 0.5, 83)` | `(32, 1, 32)` | `StudsPerTileU/V = 16` |
| `C1B_Panel_32spt` | `(18, 0.5, 83)` | `(32, 1, 32)` | `StudsPerTileU/V = 32` |

Each panel:

- `Anchored=true`, `CanCollide=false`, `CanTouch=false`, `CanQuery=false`, `CastShadow=false`
- `Material=Enum.Material.SmoothPlastic`, `Color=Color3.new(1, 1, 1)`
- `TopSurface=Enum.SurfaceType.Smooth`, `BottomSurface=Enum.SurfaceType.Smooth`
- child `Texture`:
  - `Face=Enum.NormalId.Top`
  - `Texture="rbxassetid://<uploaded-id>"`
  - `StudsPerTileU/V` as in the table
  - `OffsetStudsU=0`, `OffsetStudsV=0`
  - `Transparency=0`

A separate **cross-part seam pair** tests continuity across a part boundary, not just within one tile:

| Object | Center | Size | Tiling |
| --- | --- | --- | --- |
| `C1B_SeamLeft` | `(-8, 0.5, 125)` | `(16, 1, 16)` | `StudsPerTileU/V = 6`; offset `0,0` |
| `C1B_SeamRight` | `(8, 0.5, 125)` | `(16, 1, 16)` | `StudsPerTileU/V = 6`; `OffsetStudsU=16` |

The shared edge is at `x=0`. The right panel's 16-stud U offset continues the 6-stud pattern across the join. This is a test of Texture offset behavior, not a claim that the source has exact mathematical edge equality.

Temporary labels (one `BillboardGui` per panel plus the seam pair) use a `TextLabel` with text such as `4 studs/tile`, `8 studs/tile`, `16 studs/tile`, `32 studs/tile`, and `seam 6 studs/tile`. Labels are `AlwaysOnTop=true`, small, and removed with the rig. They exist only to identify panels in screenshots. After `C1B_rig_wide_1`, set all label `BillboardGui.Enabled=false` so they do not obscure the close-up captures; this is a reversible property change on tagged rig objects only.

### 8.3 Camera and screenshot plan

Studio must be **visible and foregrounded** for every capture. The pre-capture gate is:

1. `RobloxStudioBeta` is running, responding, and its `MainWindowTitle` matches the confirmed place.
2. `GetForegroundWindow()` belongs to the Studio PID. If not, stop and ask the operator to bring Studio to the foreground; do not capture.
3. Capture; inspect the returned image for the expected scene. A black, empty, clipped, or error-overlay image is invalid and must not be used as evidence. Fix the condition and retry; invalid captures are not counted.

**Persisting captures:** the MCP capture returns inline image data. For each valid capture, write it to `docs/c1b-evidence/<capture-id>.png` (new-only) and record its SHA-256, or, if the client cannot persist the inline image, record the capture ID, timestamp, viewport size, camera arguments and observation in the execution log and explicitly state that only the inline image exists. Do not claim a durable image file that was not written. Evidence from an invalid/black capture must not be saved as a test result.

Capture sequence:

| Capture ID | Camera | Purpose |
| --- | --- | --- |
| `C1B_baseline_1` | default, no arguments | Confirm original Baseplate/Spawn scene before any test object |
| `C1B_rig_wide_1` | explicit, e.g. `(0, 45, 20)` look at `(0, 0, 65)` | Show all four scale panels and labels together |
| `C1B_scale_4_1` | near-top-down over panel A, e.g. `(-18, 28, 42)` look at `(-18, 0.5, 47)` | Close inspection at 4 studs/tile |
| `C1B_scale_8_1` | near-top-down over panel B, e.g. `(18, 28, 42)` look at `(18, 0.5, 47)` | Close inspection at 8 studs/tile |
| `C1B_scale_16_1` | near-top-down over panel C, e.g. `(-18, 28, 78)` look at `(-18, 0.5, 83)` | Close inspection at 16 studs/tile |
| `C1B_scale_32_1` | near-top-down over panel D, e.g. `(18, 28, 78)` look at `(18, 0.5, 83)` | Close inspection at 32 studs/tile |
| `C1B_seam_1` | explicit above the seam pair, e.g. `(0, 30, 105)` look at `(0, 0.5, 125)` | Inspect cross-part continuity |
| `C1B_cleanup_1` | default, no arguments | Confirm the scene is back to baseline after cleanup |

For each explicit-camera capture, record the exact camera position/look-at arguments. The MCP capture is expected to restore the camera, but this is verified, not assumed:

- Record the baseline camera CFrame before the first override.
- After every capture, read `workspace.CurrentCamera.CFrame` and compare it with the baseline.
- If it differs, restore the exact baseline CFrame with a targeted write and verify equality. Do not leave the camera moved.
- If the camera cannot be restored, stop; do not proceed to cleanup while the camera state is unknown.

### 8.4 Visual observations to record

For each valid capture, record observations rather than a binary "pass":

- Are the panels and labels visible? Is the texture actually rendered (not solid white/gray/placeholder)?
- Is there an obvious straight seam within a panel at 4/8/16/32 studs per tile?
- Does the cross-part seam pair show a visible discontinuity?
- At which scale does repetition become objectionable? Does the pale marking recur?
- Are there filtering/aliasing artifacts, shimmering, or mipmap transitions at grazing angles?
- Does the imported asset differ visibly from the flat PNG (compression, color shift, blur)?
- Any console errors, asset-type errors, or moderation placeholders?

These are **observations for the operator**, not B1 gate passes. The test does not establish production style acceptance, device FPS, or performance.

## 9. Cleanup and original-state verification

### 9.1 Cleanup algorithm

1. Stop any HTTP server (normally already stopped) and delete the temporary upload directory. Keep the source PNG and the recorded cloud asset ID.
2. Confirm Edit mode, no playtest running, no pending save dialog.
3. Locate `Workspace.C1B_TextureTest_<runid>`. If it is missing, stop and inspect; do not perform a broad cleanup.
4. Verify every descendant has `C1B_RunId == "<runid>"`. If any unknown or mismatched object is present, stop and report; do not delete it.
5. Destroy the folder with a single `Destroy()` call. Destroying the folder removes its descendants and their tags.
6. Query `CollectionService:GetTagged("C1B_TextureTest")`; it must be empty.
7. Search `workspace:GetDescendants()` for names beginning `C1B_` or attributes named `C1B_RunId`; expect none.
8. Restore the camera to the recorded baseline CFrame if it is not already there; verify the exact position/focus/CFrame.
9. Verify the Workspace baseline:
   - direct children are exactly `Camera`, `Baseplate`, `Terrain`, `SpawnLocation` (4)
   - `Workspace` attributes and tags are empty
   - `Baseplate` position/size/transparency/anchored/material match section 4.2
   - `Baseplate.Texture` asset ID, face, tiling, offsets, and transparency match section 4.2
   - `SpawnLocation` position/size and its `Decal` texture/face/transparency match section 4.2
   - `Terrain` has no children
   - `Selection` is empty
10. Capture `C1B_cleanup_1` with Studio visible and foregrounded. Visually compare it with `C1B_baseline_1`; the scene must match. An empty/black capture is invalid, not evidence of cleanup.
11. Do **not** save the place. Do not press Ctrl+S or use Publish. If Studio prompts to save on close, choose not to save. Verify no new `.rbxl`/`.rbxlx` file appeared in the project.
12. Record the cleanup result, any deviations, and the remaining persistent effect (the cloud asset).

### 9.2 Failure handling

- If the rig contains an unexpected object or the run ID is missing, stop and inspect manually; never use a broad `ClearAllChildren()` or delete by name alone.
- If the baseline mismatch is structural, stop and report. Do not "fix" template objects to make the comparison pass.
- If the camera cannot be restored, stop and report the last known CFrame.
- If cleanup leaves any `C1B_` object, do not save the place; close without saving and report the residual state.

## 10. Persistent effects and irreversibility

### 10.1 Cannot be undone automatically

1. **Cloud image asset.** The upload creates a persistent Roblox asset under the confirmed principal. It has an asset ID, upload/moderation history, and potentially CDN copies and platform-side records. The MCP has no delete-asset capability, and this project has no authenticated deletion path. Deleting or archiving it later in the Creator Dashboard, if permitted, is a manual operator action and may not remove all copies or platform records. This is the main irreversible effect.
2. **Roblox account/audit history.** The upload is associated with the account/group and its audit/creation history. That association is not removable by this project.
3. **Moderation/scanning outcome.** The platform may review, re-encode, reject, or retain the asset. A rejection does not necessarily erase the upload record.
4. **Asset naming/metadata.** The uploaded asset may inherit the staged filename or an automatically generated name. Renaming later is a manual Creator Dashboard action and does not change the asset ID or history.
5. **Screenshots and evidence.** Captures may contain the asset and scene. They are retained as project evidence; they are not a cloud effect but are not automatically deleted.

### 10.2 Reversible or avoidable

- **Temporary Studio parts, Texture objects, labels, tags, and attributes:** removed by destroying the tagged folder; verified against baseline.
- **Camera override:** restored to the recorded CFrame; verified.
- **Local HTTP server and staged copy:** stopped and deleted; the source PNG is untouched.
- **Local place changes:** not saved; closing without saving discards them. Studio recovery/autosave may create a local recovery file, which is not a published change but should be noted and removed if it appears.
- **B1 registry:** no event is written; state remains 0 assets, 0 events.
- **Git:** no production file is changed by the test; only the planned documentation/evidence is added.

### 10.3 Explicit non-actions

C1B will not:

- save the place;
- publish or update a universe/place;
- create a B1 `imported`/`approved` event or claim;
- insert the asset as a permanent object in `Workspace`;
- modify the source PNG, the corrected v4 PNG, the FLUX workflow, the B3/B4 candidates, or the Swarm plan;
- install dependencies, generate new images, or call ComfyUI/partner APIs.

## 11. Future permanent Workspace content in Git/Rojo

### 11.1 Current representation gap

`default.project.json` maps `ReplicatedFirst`, `ReplicatedStorage`, `ServerScriptService`, `ServerStorage`, `StarterPlayer`, and `StarterGui`, but **not `Workspace`**. The current `Baseplate`, `Terrain`, and `SpawnLocation` are template/Studio content, not Git source. `*.rbxl`/`*.rbxlx` place files are gitignored. Therefore any object created directly in `Workspace` is not represented in Git and would be lost or become unmanaged on the next Rojo sync.

### 11.2 Recommended representation

1. **Map a dedicated Workspace folder, not the whole Workspace.** Add a `Workspace` entry to `default.project.json` that maps a named folder (for example `C1B_Permanent` or the eventual game content folder) to `src/Workspace/<folder>`, with `$ignoreUnknownInstances: true`. This preserves `Baseplate`, `Terrain`, `SpawnLocation`, and any template objects while making the mapped folder source-controlled.
2. **Use text Rojo formats for static content.** Prefer `.model.json` for parts, models, and props; use `.rbxmx` (XML) only for imported meshes/complex models that cannot be expressed cleanly as JSON. Do not commit binary `.rbxm`/`.rbxl`.
3. **Keep reusable content out of Workspace.** Put reusable models in `ReplicatedStorage` or `ServerStorage` and clone them at runtime from Luau modules. Workspace should contain placed instances, not duplicate source models.
4. **Keep asset IDs in a config module or manifest.** Add `src/ReplicatedStorage/Config/AssetIds.luau` (or a JSON module) with named constants and comments linking the source path and SHA-256. Runtime code assigns `Texture.Texture` from those constants. This avoids scattering environment-specific IDs through geometry.
5. **Add an asset manifest.** A project-relative file such as `art/imports/roblox-assets.json` should record the cloud asset linkage:
   - `source_path`
   - `sha256`
   - `roblox_asset_id`
   - `asset_type`
   - `uploaded_by`
   - `uploaded_on`
   - `creator` (user/group and ID)
   - `experience` (universe/place or `local-unsaved`)
   - `status` (`test_only_unapproved`, later `b1_imported` / `approved`)
   - `notes` / evidence pointers

   A C1B test entry must be `test_only_unapproved`. It must never be referenced by production code or presented as a B1 import.
6. **Keep the PNG as the source of truth.** The uploaded asset is a platform artifact; the Git-tracked PNG plus its hash is the reproducible source. If the asset is re-uploaded, record a new ID and keep the old entry/history rather than overwriting it.
7. **Preserve the B1 boundary.** A later production import must be a separately authorized B1 transition. The B1 `imported` event pins a `registry/evidence/<...>.json` record with `game_id`, `asset_id`, `revision`, `output_sha256`, `roblox_asset_id`, `imported_by`, and `imported_on`. The C1B test must not create that record. B2/B1 QC gates, a real game-specific Art Bible, and an authorized reviewer remain prerequisites for production import.
8. **Do not commit the place.** Keep `.rbxl`/`.rbxlx` ignored. The edit-time scene should be reproducible by Rojo from `src/` plus the documented asset manifest. If a local place is needed for a test, treat it as a disposable artifact and do not commit it.

### 11.3 Planned manifest shape (illustrative; no asset ID yet)

```json
{
  "assets": [
    {
      "source_path": "workflows/textures/b21/stone-seamless-v4-lossless-opt.png",
      "sha256": "782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a",
      "roblox_asset_id": null,
      "asset_type": null,
      "uploaded_by": null,
      "uploaded_on": null,
      "creator": null,
      "experience": "local-unsaved",
      "status": "test_only_unapproved",
      "notes": "C1B import test only; not B1-approved; do not use in production."
    }
  ]
}
```

The file is shown for design only; it is not created by this preflight.

## 12. Risks and stop conditions

**Stop immediately and report if any of the following occurs:**

- The operator has not confirmed the creator principal, group role, or test experience.
- Studio is not the confirmed place, is not in Edit mode, is in Team Create, or another user could receive the temporary objects.
- Studio cannot be made visible/foregrounded; a capture is black, empty, clipped, or unreadable.
- The source hash differs from `782b2c...d33a`, or the served HTTP bytes differ.
- Upload returns 401/403, a moderation/pending state, an unknown asset type, or an ambiguous/duplicate ID.
- The asset does not load as a Texture, or the console shows new asset-type/content errors.
- Any object outside the tagged rig is created, modified, or deleted.
- Baseline before/after comparison fails, or cleanup leaves any `C1B_` object.
- The camera cannot be restored exactly.
- A save/publish prompt appears, or any workflow attempts to save/publish.
- Any B1 registry transition or production asset claim is requested.

**Residual risk after a successful test:** the cloud asset remains. The test does not prove production visual acceptance, target-device FPS, ownership/rights, or B1 QC. The operator must treat the asset as test-only evidence.

## 13. Authorization request (required before execution)

To proceed, the operator must explicitly confirm all of the following in one authorization:

1. **Creator principal:** `aurory_naru` (user ID 11822718311) is the intended upload owner, **or** a named group and ID is the target and the session account has verified group asset-upload permission.
2. **Test experience:** the current unsaved local `Place1` in `Roblox_Template` is the intended test place, **or** a named universe/place ID is the target and that place is opened in Studio before execution.
3. **Upload method:** authorize `roblox_studio_upload_image` through a temporary loopback HTTP server serving a test-only copy of the PNG, **or** choose the manual Studio Asset Manager upload and agree to supply the resulting asset ID.
4. **Test scope:** authorize creation of only the tagged temporary rig in section 8, temporary camera overrides for the listed captures, and deletion of the rig after the test. No save, publish, or B1 registry transition.
5. **Persistent effect:** acknowledge that the uploaded image becomes a persistent cloud asset that cannot be automatically deleted by this project and will be recorded as `test_only_unapproved`.

Until all five confirmations are supplied, **no upload and no Studio object creation will occur**. C1B execution is intentionally stopped here.

## 14. Constraints observed during this preflight

- No image upload or asset creation.
- No Studio object mutation, property write, camera override, play/stop, save, or publish.
- One read-only MCP screenshot was taken (`C1B_preflight_1`); it was valid but not foreground-qualified, so it is a method sanity check, not the formal baseline.
- Read-only Luau queries were used to inspect identity, place state, Workspace/camera properties, and console output.
- `python tool/validate_texture.py ... --dry-run` wrote no evidence and changed no file.
- `python tool/registry.py validate` reported `PASS: 0 unique assets, 0 events`.
- `git diff --check` reported no tracked-file whitespace errors.
- The Swarm plan (`.swarm/plan.md`, `.swarm/plan.json`), task statuses, B1 registry, source PNG, corrected v4, FLUX workflow, B3/B4 candidates, and ComfyUI state were not changed.

## 15. Evidence index

| Artifact | Location / reference |
| --- | --- |
| This plan | `docs/C1B_IMPORT_PLAN.md` |
| Asset | `workflows/textures/b21/stone-seamless-v4-lossless-opt.png` |
| Asset hash | `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a` |
| B2 JSON evidence | `registry/evidence/texture-qa-b21/stone-seamless-v4-lossless-opt-f18d45a9bf68-782b2c956c40.json` |
| B2 3x3 / 5x5 / seam | same directory, matching `-3x3.png`, `-5x5.png`, `-seam_detail.png` |
| B2 interpretation | `workflows/textures/b21/REVIEW.md` |
| Studio baseline citation | `docs/C1B_IMPORT_PLAN.md` section 4.2 and the live read-only inspection recorded in `status.md` section 2.14 |
| C1A capture history | `docs/C1A_PREFLIGHT.md` |
| C1B baseline capture | `C1B_preflight_1` (inline; valid content, foreground precondition not met) |

**Next action:** operator confirms section 13. No execution until then.
