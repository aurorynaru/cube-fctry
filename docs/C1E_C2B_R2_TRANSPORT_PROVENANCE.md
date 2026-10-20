# C1E-C2B-R2 — Transport provenance and readiness (offline)

## Decision and scope

**STOP: provenance is insufficient to begin an actual-transport recording
supervisor implementation. Gate A remains NOT TECHNICALLY READY.** Essential
installed launcher/implementation and effective-client configuration access is
not established. No protocol was inferred from the synthetic NDJSON experiment.
This is a blocked investigation report, not a completed transport audit.

Baseline verified: `4661903d4f97cdb8d62adea89544741d3a00871c`.
Existing working-tree work was preserved. Only this report and `status.md` were
edited. No Studio/ComfyUI tool, server launch, Luau, screenshot, network request,
dependency installation, real authorization lifecycle, global configuration
change, staging, commit, push or subagent was used. Tests used local doubles and
temporary synthetic stores. No real transport child was started or inspected.

## 1. Verified facts versus unavailable provenance

Reviewed the required project documents, collector/tests, adapter transport and
decoder seams, and project configuration. No project `AGENTS.md` was found by
`**/AGENTS.md`; this does not establish absence in inaccessible parent directories.

| Item | Verified finding / explicit limit |
| --- | --- |
| Configured launch | `opencode.json:35–40`: `cmd.exe /d /c %LOCALAPPDATA%\Roblox\mcp.bat`, enabled, `timeout: 30000`. |
| Expanded launcher candidate | Current process `LOCALAPPDATA` is `C:\Users\juara\AppData\Local`; therefore the configured candidate is `C:\Users\juara\AppData\Local\Roblox\mcp.bat`. Existence, contents, resolved target and actual session launch are **not verified**. |
| Access boundary | Project `permission.external_directory` is `deny`. R1 records denial of `C:\Users\juara\.config\opencode`. No new external read or alternate access route was attempted. Knowing a pathname does not grant read permission. |
| Installed provenance/version | Launcher bytes, executable/source origin, hashes, signature/build/package versions and source-to-installed-build correspondence: **unavailable**. No version is inferred from tool definitions. |
| Process topology | Only the configured command-shell entry is known. All batch child processes, runtime, proxy, Studio bridge and transport links are **unverified**; even whether a simple stdio tee is the correct insertion point is unresolved. |
| Framing | Actual stdin/stdout delimiters, encoding, initialization, notifications, ID correlation, stderr behavior and server-initiated requests: **unverified**. Synthetic newline framing is not evidence about Roblox. |
| Timeout | 30,000 ms is a config value only. Enforcement, timing origin, progress reset, cancellation, process-tree exit and upstream execution termination are **unverified**. |
| Pre-display bytes | Current mapping adapter exposes no original-wire byte interface. Availability of complete bytes at an installed boundary is **unverified**, not proved impossible. |
| Transformation/truncation | Candidate sites requiring inspection: Studio result construction/serialization, bridge/proxy buffering, stdout framing, SDK parsing, client/plugin formatting or limits, provider/model display. These are investigation targets, not observed truncation locations. File-reader capping is not an MCP limit measurement. |

`McpTransport.call()` accepts/returns Python objects; `read_studio_state()` copies
a mapping; `decode_mcp_payload()` accepts the documented synthetic mapping/text
contracts. They cannot recover original whitespace, duplicate keys already
collapsed upstream, JSON-RPC envelope or framing bytes. The collector explicitly
labels all inputs synthetic and always withholds compatibility PASS. Its broader
adapter allow-list also includes Luau/screenshots and is unsuitable as Gate A's
discovery/state-only policy.

### SHA-256 of inspected repository artifacts (actual on-disk bytes)

These hashes pin reviewed local artifacts, **not installed transport provenance**.
No installed launcher/source/executable hash is available.

| Artifact | Bytes | SHA-256 |
| --- | ---: | --- |
| `opencode.json` | 1531 | `20508710e7b9a5b9b39bb125c1bb9aef88247950204ff2cf9c94d84a4dfcc604` |
| `docs/C1E_C2_MCP_PREFLIGHT.md` | 28686 | `76cf923ef247bceb74445b9d35805b441e6e6fc85d0911805a11e284e9cecd50` |
| `docs/C1E_C2B_R1_EVIDENCE_TRANSPORT.md` | 19271 | `cdaf6c87b103595b0a54f6c21aad98cdba0b0d51d09378d1b7cc76d2897d555d` |
| `tool/c2b_evidence.py` | 8372 | `61720f6f3e31299e976d0c32404128ca7769521f919cfe9461365a8bfcc69d98` |
| `tests/test_c2b_evidence.py` | 10996 | `2a3be7e3a891b0f96e839ebe2c3c20689ca4c9cf462c3033a5aeff660894810e` |
| `tool/c1c_mcp_adapter.py` | 128123 | `2233810136eebcf1a87dd12e21548cf23db9b38c00d30afefacfa3035f7f5db4` |

## 2. Effective OpenCode configuration and insertion decision

The project defines separate `roblox_studio` and `comfyui` registrations. It also
has a pre-existing `edit: deny` → `allow` diff; this was preserved. Neither the
project file nor the session's injected tool definitions establish the complete
effective configuration, running client version, environment overrides, plugin
hooks, config precedence or correspondence with this disk registration.

A future change could be scoped to **only** the effective Roblox command entry,
leaving unrelated integrations untouched, **if** the installed transport and
merge/override behavior support it. This cannot yet be certified. Required future
change: after source review, substitute a pinned reviewed recorder invocation at
the verified boundary, review effective settings, and activate only in a separately
approved session. No command, config patch or activation is supplied now; no
global config modification is needed or authorized by this milestone.

## 3. Evidence contract: four distinct outcomes

| Class | Retention and verdict |
| --- | --- |
| Complete within cap | Preserve exact response bytes including verified envelope/framing, at most 65,536 bytes. Accept only at the verified capture boundary after framing/ID/error/deadline checks. Semantic completeness and target identity require separate checks; transport acceptance alone is not compatibility PASS. |
| Oversized | Refuse; retained data is a clearly labeled **incomplete prefix**, at most 65,536 bytes under the R1 experiment. Hash only that prefix; total upstream size remains unknown unless independently established. Never call it the full raw response. |
| Truncated or malformed | Refuse even below cap. Preserve actual bytes with explicit failure/completeness fields. A newline or valid JSON alone does not establish upstream completeness. |
| Completeness unknown | Refuse compatibility when framing/end provenance, upstream completeness, original bytes or transformation behavior cannot be established. Do not repair, concatenate guessed blocks or reconstruct evidence from a display. |

**Unresolved policy conflict:** C2A §§5/7 require complete raw response retention;
R1's bounded oversize refusal retains only a prefix. They are compatible only if
complete retention applies to accepted responses and explicitly permits partial
failure evidence. If complete retention includes oversized failures, arbitrary
full retention and a strict 64 KiB storage cap cannot both hold. Before any live
observation, the operator must separately decide whether bounded incomplete
failure-prefix retention is permitted or commission a revised bounded full-retention
policy. No choice or waiver is made here; Gate A approval is not requested.

## 4. Clock interpretation and future bounded verification

Offline Python timezone conversion independently reproduced:

```text
2026-10-17T17:34:19.979028+00:00
= 2026-10-18T01:34:19.979028+08:00
```

The reported calendar-date difference is fully explained by UTC versus Philippine
local date. It is **not evidence of a real clock disagreement**. The harness gave
only a date with no exact instant/source, so relative clock offset cannot be
measured. This corrects R1's date-disagreement interpretation, while preserving
its historical record. Actual synchronization/UTC accuracy remain unverified.
Windows Time being stopped proves neither that the wall clock is wrong nor that
it is correct. No new clock query, service start, settings change or synchronization
was performed.

For future expiry verification, retain R1 §5's conservative interval method:

1. Separately approve two independent trusted UTC comparisons with authenticated
   source provenance and explicit precision, freshness, synchronization and drift
   bounds. Agree numeric freshness, query-duration and uncertainty ceilings before
   use; no justified numeric bounds are available in this offline milestone.
2. Bound each query by that duration; bracket it with local UTC and monotonic
   samples. Record source evidence and intervals, including transit/capture delay.
   Timeout, missing uncertainty, stale/unsynchronized evidence or nonoverlap stops
   verification; do not average conflicting clocks or silently widen bounds.
3. Advance the conservative covering UTC interval using monotonic elapsed plus
   bounded drift. Require its entirety inside approval validity and its latest
   instant plus the entire 30-second call window and drift margin strictly before
   expiry. Recheck withdrawal independently before each permitted dispatch.
4. Reject clock steps, suspend/reboot, lost samples or excessive drift; repeat a
   bounded comparison afterward. Keep evidence but withhold validity if the
   mapping fails. Read-only comparisons do not require changing the OS clock.

This is an independently auditable procedure specification, not a certified clock
or implemented verifier. Missing source/bound decisions remain a live prerequisite.

## 5. Minimum next task and exact access request — STOP boundary

**No supervisor architecture is selected and no code change is justified yet.**
First obtain either operator-provided local copies with original absolute paths,
byte counts/SHA-256, acquisition provenance and supported version/build information,
or path-scoped read-only permission for:

1. **`C:\Users\juara\AppData\Local\Roblox\mcp.bat` only**: read/hash as data;
   no execution. Its contents must identify the next exact script/executable paths.
   Request a second scoped grant for those concrete files, source/package metadata
   and framing/bridge implementation after they are identified. Unknown child
   paths cannot honestly be enumerated before reading the launcher.
2. **`C:\Users\juara\.config\opencode\opencode.json` and
   `C:\Users\juara\.config\opencode\opencode.jsonc`**, if present, or a
   credential-free operator-supplied effective MCP/permission/plugin configuration
   and explicit list of all loaded config paths/override sources. No recursive
   directory or credential-store access is requested.
3. Operator-supplied **exact installed OpenCode executable/package/source paths
   and version/build identity**, followed by specific read/hash permission for
   its config-merging, local MCP spawning, SDK framing/parsing, timeout/cancellation
   and response-formatting code/dependency metadata, plus any configured plugin
   implementing those hooks. A generic upstream version is insufficient without
   correspondence to the installed build. These absolute paths are currently unknown.

No permission above authorizes launching any MCP server, contacting Studio or
changing configuration. Do not bypass denial with shell reads, alternate aliases,
copies, network retrieval or execution. Next smallest task is **read/hash the
launcher under a scoped grant, then identify concrete child artifacts**.

After provenance is established, review whether a small dedicated discovery/state
supervisor suffices. It must deny all other operations; validate exact target,
arguments and order; explicitly review initialization/control messages; capture
pre-display bytes with bounded reads/storage; track absolute monotonic deadlines;
record timeout/cancellation uncertainty; fail closed on partial/malformed frames;
use protected new-only local evidence with hashes of retained bytes; never retry
or PASS incomplete data. These are retained requirements, not proof of a viable
insertion topology. Windows synthetic-child pipe/watchdog tests come only after
that design is justified; the real server must never be their test child.

## 6. Actual offline checks

No collector/adapter/test code changed; the original 25 collector tests remain.
All commands below exited 0:

| Command | R2 outcome |
| --- | --- |
| `python -m unittest tests.test_c2b_evidence -v` | 25 passed, 0.696s. |
| `python -m unittest discover -s tests -p "test_*.py"` | 230 run, 1 skipped, 21.715s; 229 passed. Existing Windows symlink skip. |
| `python tool/registry.py validate` | PASS: 0 unique assets, 0 events. |
| `python tool/validate_art.py` | PASS: 2 metaschemas, 5 presets, 3 positive and 36 negative request fixtures; no files written. |
| `python -m compileall -q tool tests` | PASS, no compiler output; parent directories verified first. |

Final documentation whitespace checks are recorded in `status.md` §2.25.
Synthetic success is not installed transport evidence. **STOP after R2; no Gate A
execution approval is requested.**
