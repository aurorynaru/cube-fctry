# C1E-C2B-R1 — Offline evidence transport readiness

## Decision

**Gate A evidence collection is NOT TECHNICALLY READY. Do not retry discovery or
request approval yet.** An offline synthetic collector is implemented and tested;
there is no verified recording transport for the configured live integration.
No Roblox MCP tool, Luau, screenshot, ComfyUI, authorization lifecycle, Swarm,
staging, commit or push was used. No network request or dependency install was
made. Existing config/adapter/authorization code and historical evidence remain
unchanged. This report does not relax `C1E_C2_MCP_PREFLIGHT.md` §§3, 5–7 or 9.

The previous zero-call stop is operator-reported context, not newly recovered raw
transport evidence. No raw bytes were reconstructed from tool displays.

## 1. Investigation and provenance

Accessible sources: project `opencode.json`, `status.md`,
`docs/C1E_C2_MCP_PREFLIGHT.md`, and `tool/c1c_mcp_adapter.py`. No project
`AGENTS.md`, MCP implementation source or dependency lockfile was found by the
performed searches. The injected OpenCode customization guidance was read as
documentation; its generic examples are not proof of this installation's code.

| Layer | Verified locally | Not established |
| --- | --- | --- |
| Project registration | `opencode.json:34–46`: local Roblox command is `cmd.exe /d /c %LOCALAPPDATA%\Roblox\mcp.bat`; enabled; `timeout: 30000` | Batch contents, actual executable/version/digest, downstream proxy implementation, stdio framing and cancellation |
| Effective OpenCode | Session exposes tool definitions; project config exists | Installed OpenCode version/source, merged config, plugin overrides, precise timeout start/reset behavior, SDK parsing/cancellation, raw stdout retention |
| Display | This session's file reader explicitly capped the first `status.md` read at 50 KB; later sections were read separately | MCP tool display limit, provider/model truncation, whether all MCP content/metadata survives presentation |
| Existing adapter | Dependency-injected mapping transport; strict selected JSON-content parsing; no concrete live recorder | Original JSON-RPC envelope/whitespace/duplicate keys already lost before mapping; exact raw-byte access is not exposed by the adapter |
| Tool declarations | Discovery/state tools and argument shapes are exposed without invocation | Their return-envelope schema, independently observed identity fields, complete response bounds or abort guarantees |

Reading `C:\Users\juara\.config\opencode` was denied by the external-directory
boundary. No alternate route was used to inspect that directory or installed
code/batch files. No web schema fetch was attempted because this task is offline;
no config fields were changed. Project `opencode.json` already had an unrelated
`edit: deny` → `allow` working-tree change, confirmed by read-only diff and preserved.

**Consequence:** 30,000 ms is a configured value, not a tested hard 30-second
observation guarantee. Provider token budgets, tool display limits and MCP wire
limits are distinct. A complete displayed JSON object may have been reserialized
or shortened upstream; saving it cannot recover the original wire bytes.

## 2. Recording transport feasibility and safer alternative

A recorder at a verified stdio boundary can in principle capture exact server
stdout message bytes **before** OpenCode parses/formats/displays them. It must
record exact client request bytes separately; keep stderr separate; correlate
JSON-RPC ID/type as well as the named operation; preserve framing; handle
notifications, initialization and server-initiated messages without mistaking
them for the approved tool response. A plugin receiving an already parsed result
or `tool.execute.after` text is too late to assert original-wire preservation.
Those hooks' behavior in this installation has not been inspected.

**No tee/proxy was installed or launched.** Starting `mcp.bat` merely to inspect
its behavior could connect to Studio and is excluded. A generic unrestricted tee
would also leave unbounded buffering, ambiguous cutoff and unrelated-call risks.
Raw stdio is not necessarily raw bytes on the internal proxy→Studio connection;
the capture boundary must be named honestly, and upstream truncation cannot be
disproved from downstream bytes alone.

Safer next offline engineering path:

1. Obtain separately permitted read-only access to the installed OpenCode/MCP
   source/config/batch artifacts, or have the operator provide exact local copies
   with provenance/version/digests. Review merged config and any plugin path.
2. Implement a dedicated, deny-by-default recording supervisor **outside the
   model tool display path**, against a synthetic child process first. Pin its
   source and runtime. Allow only exact discovery/state requests in order and
   require a human pause after discovery. Protocol initialization must be fully
   enumerated/reviewed; do not silently add capability/discovery requests to the
   approved call list. No auto-reconnect/retry or alternate server routing.
3. Use bounded OS-pipe reads and an independently scheduled monotonic watchdog,
   an absolute deadline from immediately before dispatch, and a bounded worker
   process. On refusal, stop forwarding/acceptance and quarantine late bytes;
   record whether deadline handling was delayed. Verify this on Windows with a
   synthetic child that stalls, ignores cancellation, floods stdout/stderr,
   sends multiple frames/IDs and dies mid-frame. Test process-tree ownership and
   shutdown without touching Roblox. Killing the client does not prove Studio
   execution stopped; never follow timeout with a retry or extra diagnostic call.
4. Review/pin the replacement binding and storage/clock controls before a fresh
   authorization. Any config activation requires a new OpenCode session; this
   session's already-loaded bindings cannot be assumed to switch in place.

This is a proposed alternative, not a deployed live runner. Changing collection,
protocol-message scope, evidence budgets or identity requirements requires a
**separately reviewed policy change**, not an implementation convenience.

## 3. Implemented offline collector

`tool/c2b_evidence.py` accepts **synthetic byte events only**; it has no socket,
subprocess launch, MCP dispatch, live CLI or authorization-store dependency.
`tests/test_c2b_evidence.py` is its executable specification. Its timeline uses
explicit virtual monotonic offsets. It does not sleep for 30 seconds or claim a
real-time watchdog. Synthetic subprocesses in the concurrency test only compete
for a local evidence directory; they do not load the Roblox integration.

For the experiment, one frame is newline-delimited UTF-8 JSON-RPC 2.0, including
the newline in the 65,536-byte budget. This is **a test framing contract**, not an
observation of Roblox framing or an accepted new adapter envelope. The collector
retains bytes before JSON interpretation, rejects duplicate keys/nonfinite
numbers/malformed frames/wrong typed IDs, and distinguishes RPC/tool errors,
missing termination, declared/suspected truncation, oversize, timeout and failure.
Passing transport framing never passes discovery semantics or state identity.
`compatibility_pass` is always false; UTC is always unverified.

### New-only storage and verification

- Existing operator-selected parent required. Reject symlink/reparse ancestors
  seen at check time and unsafe observation names. Atomically create a new run
  directory; a losing concurrent writer cannot reuse/overwrite it.
- Exclusive `xb` files: `request.bin`, `response-prefix.bin`, `receipt.json`,
  `COMMITTED.json`. No append/resume/reset/overwrite/recovery function.
- Handle short writes; fail on zero writes; flush, `fsync`, read back exact bytes,
  then calculate actual retained-byte counts and SHA-256. Receipt records counts,
  refusal, virtual elapsed time, budget and synthetic provenance. Final marker
  hashes the actual receipt. `verify_synthetic()` rereads and verifies the files.
- Storage failure leaves a partial directory without a trusted commit marker.
  Keep it for inspection, stop, and never reuse the name. Do not infer success
  from file existence. A partial response hash covers only retained bytes.
- Each accepted in-budget frame is preserved completely at the synthetic capture
  boundary. For oversize, only up to 65,536 bytes are saved; total upstream length
  stays null. This is refusal evidence, **not a complete response**. The count of
  bytes delivered in consumed synthetic events is separately labeled.

The marker is a local consistency check, not an authenticated/tamper-proof seal.
A same-user writer can replace evidence and recompute every hash. Mode `0700`
does not establish private Windows ACLs. Ancestor checks have a filesystem race
against an adversarial writer; Windows directory-entry/power-loss durability is
not proved by file `fsync`. These limitations explicitly prevent protected-live-
storage readiness from being claimed.

### Required live storage controls (not yet verified)

Use a new operator-owned private NTFS directory outside automatic sync/sharing;
verify owner and effective ACLs before dispatch, remove inherited broad write/read
access through an operator-reviewed setup, restrict writers, and verify that raw
evidence is not automatically staged/backed up/shared beyond the approved policy.
Use handle-based/no-follow protections or a verified exclusively owned parent to
address path races. Require disk/quota headroom and validate marker + hashes on
readback after each call. A storage failure prevents the next call.

Preserve exact requests/responses, actual supplied tool/server versions and call
IDs, approval reference and UTC/monotonic timestamps. Never fill absent metadata
from expectations. Retain protected originals at least 30 days **and** until
compatibility review completes, whichever is later; disposal is operator-decided.
Make a separate redacted sharing copy/manifest; identity validation uses originals.
No live evidence directory or redacted copy was created by this work.

## 4. Limits and what can be guaranteed

| Requirement | Verified result / remaining limit |
| --- | --- |
| Actual retained bytes/hashes | Tested on actual synthetic files and readback; failed writes/changed files reject |
| New-only concurrent ownership | Tested with 16 threads and four independent Python processes; exactly one winner for each shared name |
| 64 KiB acceptance/storage bound | Tested at exactly 65,536 bytes and above. No in-budget acceptance of an oversized synthetic frame; saved prefix bounded |
| Entire oversized response plus strict storage cap | Cannot both be guaranteed for arbitrary responses. Stop/refuse, report partial only. If the original contract requires entire oversized raw responses, remain blocked pending separately reviewed policy; do not expand or waive the cap |
| No unbounded upstream allocation | Not established. Future live reader must bound read buffers before JSON parsing; recorder cannot control server allocations |
| 30-second observation | Virtual boundary tested before/exactly at/after 30s, with exact boundary refused. No live watchdog/dispatch timing verified. Scheduler stalls prevent a universal physical hard-stop guarantee; reliably record late handling and reject all late results |
| Timeout cancellation | Never proof the remote operation stopped; configured OpenCode behavior unknown |
| Truncation detection | Malformed/partial JSON, missing frame end, explicit flags and common display markers rejected. Syntactically valid silent upstream shortening is inherently undetectable without a verified upstream completeness contract |
| Full original MCP wire bytes | Not available from current displayed tools; not reconstructed. Synthetic capture only |
| Discovery ≤16 entries / exact target | Still require a reviewed real-envelope decoder and post-capture check before state dispatch; no synthetic transport success implies these checks |
| Identity and continuity | No defaults or echoed request identity allowed; C2A missing-identity stop and snapshot continuity blockers remain unchanged |
| Private durable evidence / trusted UTC | Not established on this machine; ACL/durability/clock prerequisites remain |

For live bounds, count raw complete response bytes including envelope/framing,
not characters, parsed payload bytes or token estimates. Any stricter downstream
bound must also be satisfied; if the full in-budget frame is saved but display
truncates, stop for offline file review rather than scraping its display. A future
worker should stop at the first over-budget byte without draining the tail.
Record receive/dispatch/deadline times with a monotonic clock. Deadline must not
reset for progress notifications. Disk finalization is separately timed and
must finish before any subsequent dispatch; it is not evidence that a late
response was received in time.

## 5. UTC verification and disagreement procedure

Offline read-only checks actually executed:

- `w32tm /query /status /verbose` failed: **service has not been started**,
  code `0x80070426`. No service or clock settings were changed.
- A Python `datetime.now(timezone.utc)` sample returned
  **`2026-10-17T17:34:19.979028+00:00`**; nearby `perf_counter_ns` was
  `901796759763000`, reported resolution `1e-07` seconds. This is an OS clock
  reading, **not verified UTC**.
- The harness supplies date **2026-10-18**, disagreeing in calendar date.
  Its exact instant/source/uncertainty is unavailable. No trusted external clock
  was contacted. Do not pick the convenient/later timestamp, backdate the run,
  or use either value to establish an approval's validity.

Reliable procedure before future authorization/dispatch:

1. Operator establishes a trusted UTC source and its authenticated provenance,
   recent synchronization status, offset and conservative uncertainty. Obtain a
   second independent trusted comparison with capture-time uncertainty. A bare
   HTTP Date, chat date, screenshot or local timestamp is not a trusted source.
   This offline task cannot perform that external verification.
2. Record each source's interval `[earliest UTC, latest UTC]`, source ID, freshness,
   provenance, local UTC and bracketing monotonic samples. Account for query delay,
   precision and drift. Require overlapping intervals; missing uncertainty,
   unsynchronized/stale sources or nonoverlap stops collection. Do not average
   disagreement or silently enlarge uncertainty to make it pass. Resolve source
   disagreement out of band and repeat clock checks before seeking authorization.
3. Use the conservative interval covering the trusted estimates, advanced by
   monotonic elapsed time and drift uncertainty. Require the **entire** interval
   to be after approval time and before expiry. Before dispatch require latest
   possible time plus the full 30-second window and drift margin strictly before
   expiry. Recheck withdrawal through the verified approval channel.
4. Detect wall-clock steps by comparing wall elapsed with monotonic elapsed and
   established uncertainty; missing samples, reboot/suspend/clock anomaly or
   unexpected drift invalidates the mapping and stops dispatch/acceptance.
   Perform a post-observation check too. If disagreement is discovered later,
   retain evidence but mark authorization-time validity unverified; no next call.
5. All numerical uncertainty/freshness/drift criteria and source provenance must
   be reviewed with the future runner. If a reliable bound cannot be established,
   remain blocked; human confirmation alone cannot turn an unknown clock into a
   verified expiry check. No numeric tolerance has been silently added to policy.

## 6. Offline verification

`python -m unittest tests.test_c2b_evidence -v`: **25 passed**, 1.423s.
Coverage: original UTF-8 preservation/hashes; bytewise multibyte split; exact cap;
oversize; explicit/display/syntactic truncation; silent-semantic-truncation limit;
before/exact/late virtual deadline; missing end; transport failure with prefix;
wrong/duplicate IDs, nonfinite/malformed/multiple frames; RPC/tool errors;
short/zero/incomplete writes; fsync/readback/receipt failure; receipt/raw tamper;
unsafe names/timeline; immutable existing destinations; thread/process contention.

An initial full-suite run after the first 20 new tests passed **225 tests run,
1 existing Windows symlink skip**, 22.258s. Final full-suite and whitespace checks
are recorded in `status.md` §2.24 after the additional five failure/concurrency tests.
All collector artifacts were synthetic temporary files, removed by test cleanup;
there is no production evidence receipt. These tests prove local behavior only.

## 7. Fresh operator authorization requirements — future checklist, not a request

**First resolve the technical blockers above. No authorization is requested or
issued here.** Retire the prior attempt; do not reuse a prior approval. Before
seeking a fresh §9A authorization, present the reviewed transport/recorder source
and digest, pinned executable/config provenance, verified raw-capture boundary,
synthetic watchdog/pipe tests, effective limits, private storage proof and trusted
clock intervals. Any change to scope/identity/collection policy requires separate
review first. No technical blocker is waived by approval.

The fresh written declaration must include every original §9A requirement:

- Named operator and independently verified channel/reference; unique observation
  and approval reference, explicit UTC approval/expiry checked by the procedure;
  never create a mutation authorization/store record to enable these reads.
- Intended historical Studio ID `577768ad-49d8-42f5-ac96-8c66cd12a144`, current
  operator-confirmed unsaved local `Place1`, Edit, non-Team-Create, PlaceId=0,
  GameId=0, CreatorId=0, CreatorType=User, signed-in user ID=11822718311. These
  are expectations only. A different intended target requires offline plan
  revision and new review before discovery.
- Exactly one `roblox_studio_list_roblox_studios({})`; at most 16 entries; exactly
  one expected ID and consistent name. Only after raw capture, hash/storage and
  discovery checks pass, exactly one
  `roblox_studio_get_studio_state({"studio_id":"577768ad-49d8-42f5-ac96-8c66cd12a144"})`.
  Require independently reported identity for all original fields; missing
  identity or unknown envelope stops and returns to offline review.
- 65,536 bytes per complete response, 30 seconds per call, no retry, polling,
  fallback, extra tool or target substitution. Bind to the reviewed recorder and
  exact protected new-only directory, collection fields, retention/redaction
  rules, and verified approval reference without inventing raw metadata.
- Explicit exclusions: Luau/Gate B, screenshots, mutations, camera/viewport,
  upload/insert, playtest, save/publish, ComfyUI, authorization-store operations,
  B1 events and production approval. Stop after discovery/state and report offline.

Gate B remains separately blocked by the C2A source/serialization/path/stability/
same-read identity requirements; this evidence experiment does not make it
requestable. **Stop after this offline investigation and tests.**
