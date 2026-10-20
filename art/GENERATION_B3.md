# Milestone B3 — local FLUX 3 generation and evidence

B3 turns a validated generation request into one local ComfyUI job, verifies the
returned PNG, runs B2 texture QA, and preserves candidate provenance in a staging
record. It does not approve an asset, write a B1 registry event, upload to Roblox,
or call a paid/partner API node.

## Files and contracts

| File | Purpose |
| --- | --- |
| `schemas/generation-request.schema.json` | Draft 2020-12 generation request v1. |
| `requests/b3-stone-paving-0001.json` | Authorized single experimental integration request. |
| `../workflows/flux3/workflow-catalog.json` | Pinned workflow version, reference hash, models, slots and sampling. |
| `../workflows/flux3/README.md` | Read-only reference policy and parameterization slots. |
| `../tool/image_generation.py` | Validation, prompt building, ComfyUI client, output verification, staging. |
| `../tool/generate_asset.py` | CLI for dry-run, request validation and one-request generation. |
| `../tool/b3_postprocess.py` | Optional generic wrap blend and lossless PNG optimization. |
| `../tool/texture_qa.py` | Existing B2 QA engine, called directly by the orchestrator. |
| `../tests/test_image_generation.py` | Mocked ComfyUI unit/integration, failure and production tests. |

The request `id` uses the B1 asset-ID shape. In an experimental request it is
staged only; in a production request it must already exist in the B1 journal at
`art_approved` status.

## Experimental versus production

* **Experimental** (`mode: "experimental"`): `style.kind` must be `preset` and the
  profile must resolve under `art/presets/`. The request ID must not already exist
  in the B1 registry. A B1 v1.0 draft is written to the staging folder with all
  gates pending. It is explicitly labelled as not game-approved.
* **Production** (`mode: "production"`): `style.kind` must be `art_bible` and the
  request ID must resolve to an existing B1 record whose status is exactly
  `art_approved`. The game ID, profile, asset type, dimensions/format/tiling,
  seed, model and workflow path must match the B1 request. The selected Bible
  version must match the Bible recorded by the B1 `art_approved` transition.
  B3 consumes that approval and never creates, upgrades or re-signs it.

Baseline profile limits are enforced before generation: requested edge must not
exceed `budgets.max_texture_edge_px`, and every request uses a 16-pixel-multiple
resolution. PNG is the only supported output format.

## Prompt construction

The positive prompt is deterministic: request subject and details, Roblox usage,
profile material direction and texture rule, profile palette (with a small
deterministic color-name map), profile lighting, tiling rule when required,
asset-type clause and originality rule. Profile identity is not blindly copied
into every material prompt. The request supplies original subject-specific
direction. The negative prompt is recorded and written to the graph's negative
node, but the pinned graph uses CFG 1.0, so it receives no classifier-free
negative guidance; B3 reports this as a warning instead of pretending otherwise.

## Workflow parameterization

The original `flux3-stone-workflow.json` is read-only and hash-pinned. Each run
writes a new parameterized copy under `workflows/generated/<run>/workflow.json`.
The copy sets only the positive/negative text, latent width/height/batch, sampler
seed/steps/cfg/sampler/scheduler/denoise and the save prefix. The reference file
is never modified. A changed reference hash, unexpected node class, missing node,
missing model, unavailable sampler/scheduler, wrong resolution or API node stops
the run before submission.

## Local generation lifecycle

1. Validate the request against the B3 schema and semantic/B1 checks.
2. Replay the B1 journal without appending; resolve the profile and budget.
3. Verify the pinned reference workflow hash and structure.
4. Query local ComfyUI `/system_stats` and `/object_info`.
5. Reject any node class marked `api_node: true`, any class outside the catalog
   allowlist, and any model filename not offered by the local install.
6. Write staging, the parameterized workflow and preflight evidence.
7. `POST /prompt`; poll `/history/<prompt_id>` until success, error or timeout.
8. On timeout, delete a pending queue item or interrupt only the matching running
   prompt, record the attempt and fail safely.
9. Fetch the single output through `/view`; require PNG signature, exact requested
   dimensions, successful decode and the download safety cap. Compute SHA-256 and
   reject multiple or non-output images.
10. Run B2 QA, optional conditional derivatives, and write evidence.
11. Re-replay B1 and verify the event count and journal hash are unchanged.
12. Write `result.json` new-only and a prospective `b1-generated-payload.json`.

Recorded identifiers include the ComfyUI `prompt_id`, client UUID, queue number,
execution timestamps, elapsed seconds, poll count, server URL/version, remote
filename, models, sampler settings and output hash/size.

## Post-processing policy

`quality.postprocess.seamless`:

* `none` — raw candidate only.
* `generic_wrap_blend` — explicitly apply the geometric four-way wrap blend.
* `auto` — apply it only when the raw B2 `edge_screen` or `tone_screen` is `FAIL`.

`quality.postprocess.optimize_png`:

* `none` — no optimization.
* `lossless` — always create a pixel-identical optimized derivative.
* `auto` — optimize only when the current candidate fails the profile byte budget.

The wrap adapter reuses only `correct()` from the existing seamless-stone script,
with parameters scaled to the image (1/16 flat, 1/4 support). It does **not** use
the stone-specific vein mask, LAB homogenization or sharpening presets (v3/v4).
The optimizer verifies decoded pixel identity and refuses to overwrite. Every
derivative is new-only; the raw generated PNG is always preserved.

## B2 evidence and review

B2 is called with the staged B1 draft (experimental) or the existing B1 request
(production). Reports are written under
`registry/evidence/texture-qa-b3/<request-id>/`: JSON, Markdown, 3x3, 5x5 and
seam-detail previews per evaluated candidate. All B1 gate entries remain
`pending`. B2's `overall_result` is always at least `REVIEW_REQUIRED`; B3 never
converts a favourable screen into a human pass. If automated screens fail, the
candidate and evidence are still preserved and the CLI exits non-zero.

## Staging and B1

Candidate provenance is written under `registry/staging/b3/<request-id>/`:

```text
request.json                  exact request bytes
b1-draft-request.json         experimental only; B1 draft, pending gates, not registered
b1-record-reference.json      production only; reference to the existing B1 record
preflight.json                local ComfyUI/model/workflow checks
result.json                   full structured result or failure record
b1-generated-payload.json     prospective payload for a future authorized B1 event
```

`registry/events.jsonl` is replayed but never appended. No reviewer identity,
rights evidence, Art Bible approval, Roblox import or final approval is fabricated.

## CLI

```powershell
python tool/generate_asset.py --request art/requests/b3-stone-paving-0001.json --dry-run
python tool/generate_asset.py --request art/requests/b3-stone-paving-0001.json --dry-run --no-comfy-check
python tool/generate_asset.py --request art/requests/b3-stone-paving-0001.json --json
```

Dry-run validates the request, paths and B1 state and by default also preflights
ComfyUI, but never calls `/prompt` and writes nothing. `--no-comfy-check` makes a
fully offline validation. `--timeout` bounds the generation wait; `--base-url`
defaults to `COMFYUI_URL` or `http://127.0.0.1:8188`.

Exit codes:

* `0` — generation completed and QA produced no hard failure (may still be
  `REVIEW_REQUIRED`).
* `1` — generation completed but a QA hard failure or post-processing/QA error
  exists; candidates and evidence are preserved.
* `2` — validation, preflight, ComfyUI protocol, job failure, timeout or output
  verification error.

## Limits

The pipeline proves local execution and reproducible technical evidence, not art
quality, ownership, rights, human review, Roblox import or target-device
suitability. It does not authenticate the local ComfyUI or model files beyond the
API's own listing. A local operator can modify files or fabricate staging records;
the hash-pinned workflow and B1 replay reduce accidental drift, not a malicious
writer. B2 seam and style screens are heuristics. Output resolution and asset type
are bounded by the pinned FLUX 3 text-to-image graph; alpha, video, mesh and audio
generation are out of scope.

## Verification

```powershell
python -m unittest discover -s tests -p 'test_*.py' -v
python tool/validate_art.py
python tool/registry.py validate
python -m compileall -q tool/image_generation.py tool/generate_asset.py tool/b3_postprocess.py
```

The authorized experimental run and its factual results are recorded in
`status.md`; the request itself is not a production approval.
