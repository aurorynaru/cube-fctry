# C1E-C2B-R9 — Fake-only restricted MCP frontend

## 1. Result and scope

**Synthetic frontend usability: verified on this Windows host. Candidate MCP
protocol conformance only; installed OpenCode conformance is NOT established.
Gate A remains BLOCKED / NOT TECHNICALLY READY. D1–D6 remain PENDING.**

Baseline: `4661903d4f97cdb8d62adea89544741d3a00871c`. Review label: 2026-10-18
(harness date, not authenticated UTC). Single agent; no delegation or Swarm.
Option B's reusable independently enforced dispatch/evidence/containment approach
is preserved. No real frontend registration or configuration activation occurred.

Read status §2.31, R8/R7 reports, relevant R4–R7 source/tests/fixtures and project
`opencode.json`; no project `AGENTS.md` was found. An implementation-skill file
read was denied by tool policy; no retry, permission change or alternate access
followed. Existing dirty/untracked work was inventoried and preserved. In
particular, the pre-existing `opencode.json` edit was not made by R9.

## 2. Provenance reconciliation

### 2.1 Operator-supplied launcher text, not independently acquired bytes

The supplied text is now recorded here as operator evidence:

```bat
@echo off
if exist "C:\Users\juara\AppData\Local\Roblox\Versions\version-4f087c32742644ab\StudioMCP.exe" ( "C:\Users\juara\AppData\Local\Roblox\Versions\version-4f087c32742644ab\StudioMCP.exe" %* ) else (for /f "tokens=2*" %%A in ('reg query HKEY_CURRENT_USER\Software\Roblox\RobloxStudio /v ContentFolder') do (
"%%B/..\StudioMCP.exe" %*
))
```

| Operator report | Identity and qualification |
| --- | --- |
| Launcher | `C:\Users\juara\AppData\Local\Roblox\mcp.bat`, **341 bytes**, SHA-256 `705CF29E8CA920AFC38E5E1508C797856AAFCCB913049D88FBF9D1A448D17E33` |
| Primary executable | `StudioMCP.exe` at the version-specific path in the text, **8,208,336 bytes**, SHA-256 `3D5CF029E535251D530BBE1E4765D4183BD1396F52D51E85C97CD98D9E285092`; operator reports a **valid Roblox Corporation Authenticode signature** |

These are operator-reported facts, not fresh file/hash/signature verification.
The Markdown code block may normalize encoding/line endings. **No assertion is
made that its bytes reproduce the reported 341-byte file or digest.** R8's missing
text gap is narrowed by this submission; original-byte provenance remains distinct.

Static branch interpretation, with neither branch executed:

1. `if exist` selects the quoted version-specific executable when that path exists;
   it supplies `%*` at that invocation. The condition tests existence, not the
   reported digest/signature or successful startup. There is no explicit fallback
   on primary execution failure in this text.
2. Otherwise `for /f "tokens=2*" %%A` executes the quoted `reg query` command against
   HKCU `Software\Roblox\RobloxStudio`, value `ContentFolder`. `%%A` receives token 2;
   `%%B` receives the remaining tokens. The body invokes `"%%B/..\StudioMCP.exe"`
   with `%*`. The actual registry value, selected executable and its identity are
   unknown. This is an additional registry-dependent launch branch, not a pinned
   equivalent of the primary path.
3. No `cd`, explicit environment setup or `start` appears in the pasted text.
   Actual cmd expansion/argument/cwd/environment and executable delegation/stdio
   ownership still need build-bound evidence. `%*` is shell text; it does not prove
   a safe arbitrary-argv API or equivalence to direct native launching.

### 2.2 Why `deny` is visible despite the earlier operator `ask`

Project `opencode.json` has `permission.external_directory: "deny"` at line 49.
`git diff -- opencode.json` shows that value unchanged from baseline; its sole
visible pre-existing diff is `edit: "deny"` to `edit: "allow"`. R8 did not introduce
an `ask`→`deny` project-file change and R9 made no configuration edit.

This session's denied external skill read returned a rule list containing an early
`external_directory: ask`, specific allows, and a later wildcard `deny`. That is
consistent with conflicting permission scopes and with the observed refusal.
It does **not** identify the acquisition/source of every rule or establish the
installed client's merge/precedence/session-snapshot behavior. The operator's prior
`ask` could refer to another loaded scope or time; that remains unresolved. Visible
scope is the project file and the refusal's rule output, not a verified global,
managed, CLI/environment/plugin or effective merged configuration inventory.
The historical R1/R3 denials are policy refusals, not proof of a Windows ACL denial
or nonexistent file. No denied path was bypassed and no permission was changed.

The project still shows one direct enabled Roblox batch entry, `timeout: 30000`,
and one enabled ComfyUI entry. These are existing disk configuration facts, not
evidence that the new frontend is loaded or that alternate/stale routes are retired.

### 2.3 Smallest missing installed OpenCode contract evidence

No accessible build-bound OpenCode/SDK implementation packet was found in the
reviewed repository. The historical session label for an agent/plugin version is
not an executable identity or an MCP SDK contract. The smallest next packet is:

- Exact installed OpenCode package/executable path, version/build, digest and
  relevant MCP SDK/plugin identities, with acquisition provenance.
- Matching narrow excerpts or build-bound documentation for actual stdio spawn,
  initialize protocol versions/capabilities/clientInfo, initialized notification,
  catalog/schema and alias handling, result/error parsing, concurrency,
  timeout/cancellation and automatic retry/reconnect behavior.
- Credential-free loaded configuration paths/override sources and resolved
  permission/Roblox binding inventory, sufficient to explain the `ask`/`deny`
  discrepancy and eventual retirement of direct/stale aliases and sessions.

An operator-supplied packet inside an accessible project location can resolve
these facts offline. Unavailable installed source is not permission to guess its
behavior; a substitute for build-matched source must be explicitly identified and
reviewed. R9's fixture is **not** called source-derived OpenCode or evidence of
installed-build equivalence. Exact Roblox startup/delegation/wire-envelope
provenance also remains a separate live-binding prerequisite.

## 3. Implementation and reviewed candidate client contract

| File | Responsibility |
| --- | --- |
| `tool/c2b_restricted_frontend.py` | Disposable stdio loop; inert local lifecycle/catalog; strict runtime method/tool validation; single outstanding request; terminal refusal; Python-only synthetic injection surface |
| `tool/c2b_synthetic_review.py` | Test-only session/launch token, new-only session intent, verified discovery checkpoint, real bounded wait and explicit continuation/state rendezvous |
| `tool/c2b_recording_supervisor.py` | Minimal `run_paused_contained_synthetic` seam around R7; register-before-start readers; per-write synthetic checks; due-watchdog race correction; additive synthetic receipt fields |
| `tool/c2b_native_recorder.py` | Existing R7 bridge retained; internal check before create/resume; skip conclusively unstarted reader joins and quarantine unknown starts |
| `tests/fixtures/c2b_synthetic_client.py` | Independently specified candidate client messages and bounded synthetic byte streams |
| `tests/fixtures/c2b_frontend_controller.py` | Fixed disposable before/after-checkpoint controller-death fixture |
| `tests/test_c2b_restricted_frontend.py` | 39 new candidate conformance, boundary, failure and regression tests |

The inert module entrypoint is `python -m tool.c2b_restricted_frontend`; it accepts
**no CLI options**. It has no evidence destination or launch authorization by
default, so client tool calls refuse. Synthetic tests create `Frontend` with a
temporary store and inject Python test-only prerequisites separately from MCP.
This is useful for fake clients today; it is not an activated OpenCode integration.

Candidate protocol assumptions, intentionally strict:

- UTF-8 NDJSON JSON-RPC 2.0; LF and CRLF accepted and bounded including delimiter.
  No BOM, invalid UTF-8, duplicate keys, nonfinite numbers, batches, partial lines,
  concatenated envelopes, result/error-as-request or extra envelope keys.
- Client frame ≤4,096 bytes; ≤64 handled frames; combined handled input/serialized
  success output ≤262,144 bytes; emitted response ≤65,536 bytes. The input queue
  holds at most two additional bounded frames; flooding or overflow refuses.
  These are test-frontend traffic limits, not approved production storage quotas.
- IDs are exact strings of 1–128 characters or integers strictly between
  `-2**53` and `2**53`, excluding booleans. Typed IDs are distinct, never reused
  within the connection. No JSON-RPC batch or pipelined tool execution.
- `initialize` once, with exactly `protocolVersion: "2025-11-25"`,
  `capabilities: {}`, and `clientInfo: {name, version}` with bounded nonempty
  strings. This version is inherited from the reviewed R7 synthetic contract,
  not observed from installed OpenCode. Reply advertises only `tools: {}` and
  fixed test-only server name/version. Other versions/capabilities refuse without
  negotiation/retry.
- `notifications/initialized` once after initialize, absent or empty params;
  no response. Requests before READY refuse. `ping` and `tools/list` accept absent
  or empty params only. No cursor, `_meta`, task or dynamic catalog support.
- Bounded `notifications/cancelled` with typed `requestId` and optional string
  `reason` terminates the connection. During an active request, any second frame,
  including cancellation, aborts rather than queueing a dispatch. Unknown
  notifications/methods/envelopes terminate. Refusal errors use code `-32000` and
  a bounded local diagnostic; malformed/uncorrelatable IDs use `null`.
- Stdout contains protocol responses only; diagnostics go to stderr. EOF, input
  reader failure, output-write failure and timeouts refuse. The process exits
  after terminal success/refusal. Callable Python test objects stay terminal and
  may only return further errors, never reopen their observation.

The fixed catalog has exactly:

| Tool | Authoritative runtime parameters |
| --- | --- |
| `list_roblox_studios` | Exactly `{"name":"list_roblox_studios","arguments":{}}`; at most once after injected synthetic launch |
| `get_studio_state` | Exactly `{"name":"get_studio_state","arguments":{"studio_id":"577768ad-49d8-42f5-ac96-8c66cd12a144"}}`; at most once after checkpoint-bound injected synthetic continuation |

Both schemas disallow extra arguments; state additionally pins a `const` target.
All aliases, other tools and methods refuse at runtime regardless of advertised
schemas. There is no generic forwarding, real launcher option, executable/argv/
environment/shell input, Studio parameters, resources/prompts/tasks, authorization
method or continuation tool. No OpenCode configuration change is delivered.

## 4. True synthetic pause and contained recording

**Before integration:** R7 `run_contained_synthetic(...,
synthetic_state_review=False/True)` was synchronous and finalizing. False recorded
discovery then tore down; True immediately dispatched state. It did not support
an externally controlled pause. R9 does not reinterpret that boolean as a pause.

The new seam reuses `_Session`, `_Capture`, `GateAPolicy`, finalization and the
same `SyntheticRecorderProcess` / R6 creation-time job-list+suspension+explicit
handle-list boundary. `c2b_windows_containment.py` and the fake MCP child were not
changed. Executable selection remains internal: current fixed Python runtime,
bundled fake MCP file, enumerated scenarios; no ordinary-Popen/late-assignment
fallback. Test-only checks run before creation and again before checked resume.

Executed sequence:

`INERT → injected TEST-ONLY launch → new observation directory/session intent →
contained initialize/initialized → one discovery attempt → durable verified
discovery checkpoint → WAIT_REVIEW → separately injected TEST-ONLY continuation
and exact client state request → spent state intent → one conditional state
attempt → teardown/readback/final receipt → TERMINAL`.

- Launch token binds test-only action, observation, random session ID and target.
  The new-only observation directory burns this synthetic attempt before launch;
  existing/partial/committed directories are never resumed or overwritten.
- The checkpoint binds observation and exact session, actual discovery result,
  explicit target/identity expectations, accepted request timing, launch-intent
  digest and SHA-256/length of all recorded initialize/initialized/discovery
  request/response/control files. `_write_new` provides exclusive create, full
  write, flush/fsync and SHA-256 readback. Checkpoint and originals are reread.
- Only then is discovery returned to the client. The runner and contained child
  remain alive in **WAIT_REVIEW**; no final commit and no state bytes exist yet.
  A continuation alone does not dispatch state; neither does a state request
  without continuation. Continuation binds the checkpoint digest, same session,
  observation and exact target arguments and is explicitly **TEST ONLY**.
- The real wait has a fixed monotonic bound (default 5 seconds, test-injectable
  0–30 exclusive/inclusive); no traffic resets it. Idle unsolicited stdout,
  EOF/failure, cancellation, disconnect, decline, missing/invalid/replayed
  continuation or expiry ends the session without state.
- Before state, originals/checkpoint/session binding are verified again and a
  new-only state-attempt record is persisted. After potentially slow storage,
  checkpoint/session/deadline/cancellation checks run again at **each actual
  pipe-write attempt**, including partial writes. A regression corrupts the
  checkpoint during state-intent storage: intended state is recorded, **zero
  state bytes are written**, and no state result is accepted.
- State is returned only after confirmed teardown, final receipt/marker readback
  and `verify_recording`. A completed recording whose client stdout subsequently
  fails is not a successful frontend delivery. Error or uncertainty never becomes
  success merely because a client reconnects.

Raw child stdout remains retained/readback-verified **before JSON decoding**;
original frame bytes, Unicode, whitespace and delimiters are not reconstructed
from client output. R7's inclusive 65,536-byte frame, 262,144-byte stdout session,
65,536-byte stderr, 32-frame acceptance limit and ≤4,096-byte OS reads remain.
The frontend stores no client transcript. Checkpoint reads are bounded and refuse
nonregular/reparse/oversized evidence files. Final R7 receipt schema remains
`c2b-offline-supervisor/1`, with additive session/checkpoint/review-mode fields.
It still reports `studio_touched=false`, `authorization=null`,
`utc_verified=false`, `compatibility_pass=false`, upstream completeness unverified
and no full-response claim.

## 5. Refusal, replay and interruption findings

| Tested category | Observed enforcement |
| --- | --- |
| Startup / initialize / catalog / ping | Zero child launches; exact two-tool catalog. Real inert subprocess stdout parses as protocol only; stderr carries terminal diagnostic. |
| Unauthorized tools, wrong args/target, aliases, methods, versions/envelopes | Terminal refusal; no tool forwarding or unauthorized launch. Invalid/nonserializable launch inputs also refuse. |
| Duplicate IDs / discovery with a fresh ID / continuation replay / terminal redispatch | No second discovery/state attempt; terminal objects cannot reopen. Typed numeric/string IDs remain distinct. |
| Concurrent Python callers and pipelined stdio tools | No dispatch queue; connection aborts, ≤one discovery attempt and no conditional state. Cancellation during setup prevents resume; in-flight cancellation ends local tree and prevents a next tool. |
| Reconnect while paused | Old session closes/refuses; new frontend starts inert. New launch injection cannot reopen the same observation directory or accept an old continuation. |
| Controller crash before/after checkpoint | Actual disposable processes killed; observer duplicates only the exact root wait handle, never a job handle. Owned root exits; no state or final commit is fabricated. Existing incomplete directory blocks restart before new child creation. |
| Missing/declined/invalid continuation, wait timeout, unknown/disconnected client | Zero state dispatch; no automatic retry. Explicit test-only injection is not human approval. |
| Checkpoint/original/launch corruption and checkpoint disk failure | No state accepted; verified-final-recording checks also reject altered originals. No ready checkpoint is advertised after its storage failure. |
| Unknown server controls, wrong IDs, malformed/oversized output, active timeout | Existing raw collector/refusal paths reused; no checkpoint or state follows invalid discovery. Paused unsolicited tail ends the session. |
| Client output failure / final commit failure / injected cleanup uncertainty | No successful frontend state result or reusable session. Actual cleanup still runs; original uncertainty/ownership assertions remain mandatory. |
| Reader registration/start interruption | Reader enters registry **before** `start`. Documented unstarted failure is not joined as a running thread; hidden successful start remains registered and is joined. Unobserved interrupted start remains quarantined/uncertain, never guessed safe. |

The reader fix applies to both existing supervisor entrypoints and the new seam.
Native finalization skips only conclusively unstarted threads; unknown starts
quarantine leases and withhold handle/success certainty. No original ownership,
tree-exit, handle-close or cleanup test assertion was removed or weakened.

A separate existing race was reproduced: `next_frame` could detect timeout just
before its independent watchdog ran, then `finally` could disarm that already-due
guard, leaving `watchdog_fired_ns=null`. After immediate refusal/tree stop, the
supervisor now gives the due guard a bounded join before disarming; unconfirmed
delivery records worker uncertainty. A deliberately delayed guard regression
verifies an actual firing, not a fabricated timestamp or relaxed assertion.

## 6. Executed verification

Final code verification (before documentation-only updates):

| Command | Result |
| --- | --- |
| `python -m unittest tests.test_c2b_restricted_frontend tests.test_c2b_native_recorder tests.test_c2b_windows_containment tests.test_c2b_recording_supervisor tests.test_c2b_evidence` | **194 passed, 0 skipped, 23.804s** = 39 R9 + existing 60 R7 / 33 R6 / 37 supervisor / 25 evidence |
| `python -m unittest discover -s tests -p "test_*.py"` | **399 run, 398 passed, 1 existing skip, 36.272s**. Only `test_asset_registry.RegistryTests.test_symlink_escape` (`symlinks unavailable`); all native Windows tests ran. |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events** |
| `python tool/validate_art.py` | **PASS: 2 metaschemas, 5 presets, 3 positive request fixtures, 36 negative request fixtures; no files written** |
| `python -m compileall -q tool tests` | **PASS**, no output; `tool`, `tests`, `tests/fixtures` parent locations verified first |
| Tracked `git diff --check`; per-file untracked `git diff --no-index --check -- /dev/null <path>` | **PASS: no whitespace errors**. Untracked checks cover this milestone's two updated Python modules, five new Python files and this report (8 paths). LF→CRLF advisory warnings only. No-index returns **1 for differences from empty** here; whitespace/error statuses above 1 are rejected. |

Development failures were resolved, not hidden: first 29-test R9 run had one
duplicate-ID test error; 184-test and later 192-test focused runs each exposed
the existing due-watchdog race; intervening 190-test run passed. A tentative
pre-write-check scoping correction did not eliminate that race; the explicit
due-guard fix and delayed-guard regression did. The 193-test focused run passed
before the final client-output test was added. First full 399-test run had one
failure in that new fault fixture: substring matching against `memoryview` never
triggered the intended broken output; converting to bytes fixed the injector.
The final 194/399 results above include that regression and all final code edits.
The first whitespace wrapper incorrectly treated no-index's expected difference
exit 1 as a whitespace failure; the corrected 8-path check returned zero
whitespace diagnostics. No source change was needed for that wrapper correction.

## 7. Remaining boundaries, decisions and next milestone

**Synthetic injected launch/continuation/session/storage objects are not production
approval, trusted time, protected replay storage or ACL verification.** Hashes prove
local consistency, not authenticity against another writer. New-only temporary
directories demonstrate conservative crash/reconnect refusal, not a protected
cross-principal authorization service. No production evidence or ACL was changed.

R8's per-category/session/campaign/physical-storage budget proposals are not fully
implemented or adopted by these test-only traffic/checkpoint bounds. The
oversized-response retention amendment and distinct-content versus physical-copy
interpretation remain **PENDING**. No universal power-loss, same-user adversary,
path-replacement, OS/kernel scheduling/disk deadline or in-kernel interruption
guarantee is claimed. Existing hidden native/CRT-return uncertainty stays blocked.

The disposable stdio loop owns registered request workers. Its input reader
borrows stdin; if a client holds the pipe open at terminal exit, that daemon may
remain blocked until **process exit**, without an unsafe close of its borrow.
The callable fixture loop is not a long-lived plugin guarantee. Blocking client
stdout and arbitrary filesystem/kernel stalls have no certified hard deadline.
Production supervision/deployment and independent channel protections still need
their own decision/qualification. Containment says nothing about real Studio
delegation or cancellation; this milestone never contacted Studio.

| Decision | Status after R9 |
| --- | --- |
| D1 — supported fault/ownership model | **PENDING**; reader/death/due-watchdog evidence added, not operator acceptance or universal leak-free recovery |
| D2 — oversized retention/accounting | **PENDING**; existing synthetic limits preserved, no amendment adoption/physical-quota proof |
| D3 — independent human approval/withdrawal | **PENDING**; only separately injected TEST-ONLY tokens/rendezvous exist |
| D4 — independent authenticated UTC | **PENDING**; only monotonic synthetic deadlines, no time-service operation or UTC attestation |
| D5 — protected private storage/fault model | **PENDING**; temporary stores/readback only, no production ACL/path/quota/retention qualification |
| D6 — installed client/launcher/sole route | **PENDING**; pasted launcher branch evidence reconciled, installed-build/effective-binding/retirement evidence missing |

**Gate A readiness verdict: BLOCKED.** Frontend fake-only usability has advanced;
installed OpenCode compatibility, actual independent authority/time verification,
protected replay/evidence budgets/deployment, exact real launch topology and sole
route/stale-session retirement remain essential live prerequisites. Gate B remains
separately blocked.

**Smallest next milestone:** obtain/reconcile the narrow build-bound client and
effective-setting packet in §2.3, then qualify this candidate against those exact
messages with fixed synthetic children only. In parallel policy planning, obtain
explicit D1–D6 dispositions; follow with a narrow offline independent approval/
withdrawal/time verifier and protected-storage/replay contract, rather than
promoting these test tokens into production authority. No live binding, permission
change or execution authorization is requested.

STOP after synthetic verification. No `StudioMCP.exe`/`mcp.bat` execution, Roblox
MCP call, Luau, screenshot, Studio mutation/upload/save/publish, ComfyUI, real
approval/time-service operation, dependency install, OpenCode edit/activation,
production evidence/ACL change, Git staging/commit/push or Swarm occurred.
