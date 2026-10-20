# Milestone C1B — Authorized Execution Log

**Execution date:** 2026-10-17
**Status:** COMPLETE (test-only import/render check). No save, publish, B1 registry event, plan change, C1C, or additional uploads.
**Authorized test asset:** `workflows/textures/b21/stone-seamless-v4-lossless-opt.png` (SHA-256 `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a`).
**Roblox upload result:** `rbxassetid://112705883084796` (`112705883084796`), created once under signed-in user `aurory_naru` (user ID 11822718311).

## 1. Recovery checkpoint verification

- Resumed from the verified recovery checkpoint; the previous diagnostic confirmed `roblox_studio_upload_image` had never been invoked.
- Existing loopback HTTP server: `127.0.0.1:61139`, PID **76360** (`python -m http.server 0 --bind 127.0.0.1 --directory C:\Users\juara\AppData\Local\Temp\opencode\c1b-c1b-20261017-01`). Process and listening socket both verified before the request.

## 2. Single read-only HTTP GET + independent SHA-256

- Request (exactly one): `GET http://127.0.0.1:61139/C1B_TEST_ONLY_stone-seamless-v4-lossless-opt.png`
- Returned bytes: **2,038,645**
- Independently computed SHA-256: `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a`
- Expected: `782b2c956c404622ea3e992edf9f906ddcb22422596a4f9ad9c501de14a1d33a`
- **Result: MATCH**

## 3. Studio instance and creator confirmation (read-only)

- `roblox_studio_list_roblox_studios` returned exactly one instance: **`Roblox_Template`**, `studio_id` `577768ad-49d8-42f5-ac96-8c66cd12a144` — unchanged.
- Edit mode; Workspace children **4** (`Camera, Baseplate, Terrain, SpawnLocation`); `PlaceId=0`, `GameId=0`, `CreatorId=0`, `CreatorType=User` — unchanged.
- `StudioService:GetUserId()` returned **11822718311**, matching the preflight principal `aurory_naru`.
- Pre-test camera CFrame (recorded for exact restoration): `-25.2102032, 33.4859009, -41.3457031, -0.864860833, 0.240521491, -0.44064191, -0, 0.877752125, 0.479115129, 0.502011895, 0.414367914, -0.759133279`; position `-25.210203170776367, 33.48590087890625, -41.345703125`; CameraType `Fixed`; viewport `1219x793`.
  - Observation: this differs from the camera recorded in the earlier preflight (`-23.400, 34.181, -41.904`). The current value was recorded as the execution baseline; no camera mutation was performed to reconcile it.
- Workspace baseline: 0 attributes, 0 tags, empty Selection, 0 `C1B_TextureTest` tags, 0 `C1B_` descendants. Baseplate `2048x16x2048` at `(0,-8,0)`, top `y=0`, `Texture` `rbxassetid://6372755229` 8/8 studs; SpawnLocation `12x1x12` at `(0,0.5,0)` with `rbxasset://textures/SpawnLocation.png`.
- Studio was brought to the foreground with the user32 foreground-window API; verified foreground PID **96800**, title `Place1 - Roblox Studio`.
- Baseline capture **`C1B_exec_baseline_1`** (no camera arguments) returned a valid viewport showing sky, checkered Baseplate and the centered SpawnLocation. **PASS — foreground baseline.**

## 4. Authorized upload (exactly one invocation)

- `roblox_studio_upload_image` called **once** with:
  - `studio_id`: `577768ad-49d8-42f5-ac96-8c66cd12a144`
  - `imagePaths`: `["http://127.0.0.1:61139/C1B_TEST_ONLY_stone-seamless-v4-lossless-opt.png"]`
- Actual response (verbatim): `{"http://127.0.0.1:61139/C1B_TEST_ONLY_stone-seamless-v4-lossless-opt.png":"rbxassetid://112705883084796"}`
- **Confirmed asset ID: `rbxassetid://112705883084796`** (numeric `112705883084796`).
- No retry, no second upload. The asset is a persistent cloud image under the signed-in user; it is **test-only and unapproved**, not a B1 import or production asset.

## 5. Studio test rig

- Temporary folder: `Workspace.C1B_TextureTest_20261017-01`.
- Six anchored, non-colliding 32x32 panels with `Texture` on the **Top** face, all bound to `rbxassetid://112705883084796`:
  - `C1B_Panel_4spt` at `(-18, 0.5, 47)`, 4 studs/tile
  - `C1B_Panel_8spt` at `(18, 0.5, 47)`, 8 studs/tile
  - `C1B_Panel_16spt` at `(-18, 0.5, 83)`, 16 studs/tile
  - `C1B_Panel_32spt` at `(18, 0.5, 83)`, 32 studs/tile
  - `C1B_SeamLeft` at `(-8, 0.5, 125)`, `16x1x16`, 6 studs/tile, offset 0
  - `C1B_SeamRight` at `(8, 0.5, 125)`, `16x1x16`, 6 studs/tile, `OffsetStudsU=16` (exactly one panel width, so the UVs are continuous across the shared edge)
- Initially four scale labels plus a seam-pair label were created as small `BillboardGui`/`TextLabel` objects (AlwaysOnTop). After the wide capture all six `BillboardGui` objects were set `Enabled=false` so they could not obscure close-ups. The labels did **not** appear in the 3D viewport captures; scale identification therefore relies on the documented panel positions.
- Every rig object (folder, parts, textures, GUIs, labels) carried name prefix `C1B_`, attribute `C1B_RunId="20261017-01"`, attribute `C1B_TestOnly=true`, and the `C1B_TextureTest` tag.
- Preload of the six `Texture` objects returned OK; all six read back `rbxassetid://112705883084796` before cleanup.
- No save, publish or playtest. Edit-mode rendering only.

## 6. Screenshot evidence

Captures were taken with Studio visible and foregrounded (foreground PID 96800 re-established before each capture). All are inline MCP captures; no capture file was written.

| Capture | Camera | Observed result |
| --- | --- | --- |
| `C1B_exec_baseline_1` | default, no arguments | Valid baseline: sky, checkered Baseplate, centered SpawnLocation; no rig. |
| `C1B_rig_wide_1` | `(0,45,20)` → `(0,0,65)` | All four scale panels and the far seam pair visible; every panel rendered the uploaded stone texture, no black/missing texture. 4/8 studs-per-tile panels show fine grain; 16/32 show softer, larger-scale stone. Labels not rendered by the viewport-capture path. |
| `C1B_scale_4_1` | `(-18,28,42)` → `(-18,0.5,47)` | 4 studs/tile: eight repeats across the 32-stud panel; fine repeat, no obvious hard join at capture resolution. |
| `C1B_scale_8_1` | `(18,28,42)` → `(18,0.5,47)` | 8 studs/tile: four repeats; grain retained; no obvious hard join. |
| `C1B_scale_16_1` | `(-18,28,78)` → `(-18,0.5,83)` | 16 studs/tile: two repeats; visibly softer/upscaled; no hard line. |
| `C1B_scale_32_1` | `(18,28,78)` → `(18,0.5,83)` | 32 studs/tile: one tile across the panel; full v4 stone image visible; no hard line. |
| `C1B_seam_1` | `(0,30,105)` → `(0,0.5,125)` | Two 16x16 panels joined with continuous UV offset; stone tone and fine grain appear continuous across the part boundary. Only a faint part-edge/lighting line is visible; no obvious bright/dark texture discontinuity. |
| `C1B_cleanup_1` | default, no arguments | Clean scene with no rig; camera view differed slightly from baseline because of the capture tool's rotation side effect (see section 7). |
| `C1B_cleanup_2` | recorded baseline position → recorded baseline look point | Matches `C1B_exec_baseline_1`: sky, checkered Baseplate and centered SpawnLocation, no rig, no `C1B_` objects. |

**Interpretation limits:** these are edit-mode viewport renders. They do not establish Roblox UV behavior under player movement, mipmapping/compression, target-device filtering, lighting fidelity, memory or FPS. No in-engine target-device or playtest verification was performed.

## 7. Cleanup and baseline restoration

- The first cleanup pass **aborted before deletion** because the six `Texture` children were named `Texture` rather than `C1B_`-prefixed. This is the safety check working as intended; nothing was deleted on that attempt.
- The texture children were renamed to `C1B_Texture`; one duplicate seam-pair label was removed so the rig matched the planned one-label-per-panel plus seam-pair layout. The full verification then passed for the folder and all **22 descendants** (name prefix, `C1B_RunId`, `C1B_TestOnly`, tag).
- `Workspace.C1B_TextureTest_20261017-01` was destroyed. Post-cleanup read-only checks:
  - `CollectionService:GetTagged("C1B_TextureTest")` → **0**
  - `C1B_`-named descendants → **0**
  - descendants with `C1B_RunId` → **0**
  - Workspace children → **4** (`Camera, Baseplate, Terrain, SpawnLocation`)
  - Selection → **0**
  - Baseplate/Texture and SpawnLocation/Decal properties, Workspace attributes and tags → match baseline
  - camera CFrame restored to the exact recorded baseline; component max delta **0.0**; `CameraType=Fixed`
  - cleanup capture `C1B_cleanup_2` visually matches the baseline scene
- **Capture-tool side effects (disclosed):** each `screen_capture` altered the camera rotation and restored only its position, and the 3D viewport changed from `1219x793` to `690x675`. The camera CFrame was explicitly restored after the final capture and verified at delta 0; the viewport size is a Studio session/capture-tool state and was not restored. No DataModel scene content depends on it.
- No new `.rbxl`/`.rbxlx` file exists in the project. The place remains unsaved/local (`PlaceId=0`); no save or publish occurred.

## 8. Final constraint checks

- `python tool/registry.py validate` → **PASS: 0 unique assets, 0 events** (no B1 production event).
- `.swarm/plan.md` and `.swarm/plan.json` were not modified; the approved plan hash remains `2lnzncyys8pi5` as recorded.
- Loopback HTTP server stopped: PID **76360** terminated, port **61139** no longer listening.
- No C1C work was started and no additional upload was performed.
- The uploaded cloud image (`rbxassetid://112705883084796`) is the one persistent effect; it was not deleted or registered. It must remain labeled `test_only_unapproved` and must not be used in production.
