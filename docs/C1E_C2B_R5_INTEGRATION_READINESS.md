# C1E-C2B-R5 — Offline integration readiness review

## 1. Decision, scope and evidence boundary

**Gate A remains NOT TECHNICALLY READY. STOP after this offline review.** R4 is a
useful synthetic recorder, not an activatable Roblox MCP registration. R5 fixes
one reproduced cleanup defect. It supplies no real launcher, proxy, approval,
configuration activation or compatibility evidence. No Gate A execution approval
is requested; a later separate review must establish every prerequisite first.

- Baseline verified: `4661903d4f97cdb8d62adea89544741d3a00871c`.
- Review label: 2026-10-18, from the harness date, **not verified UTC**. Runtime:
  `python --version` reported **Python 3.12.7** on Windows.
- Single agent; no Swarm/delegation. All children launched by this work were the
  controlled Python fixtures/local test helpers. Evidence tests used synthetic
  temporary directories; no existing evidence ACL was changed.
- No Studio MCP call (including discovery/state), real `StudioMCP.exe` launch,
  `mcp.bat` execution, Luau, capture, Studio change, ComfyUI, external time/network
  request, clock/service change, live authorization operation, dependency install,
  MCP registration change, Git staging/commit/push or external-file access occurred.
- Read the requested preflight/R1/R2/R4 documents, `status.md` §2.27, project
  `opencode.json`, supervisor, evidence helper, complete supervisor tests and fake
  fixture; additionally inspected helper tests and verification entry points.
  Project `**/AGENTS.md` found none. This is not a claim about inaccessible parents.
  Existing modified/untracked milestone files and unrelated work were preserved.

R4 §1 supplies **operator-reported**, not independently acquired, metadata:
`mcp.bat`, 341 bytes, SHA-256
`705CF29E8CA920AFC38E5E1508C797856AAFCCB913049D88FBF9D1A448D17E33`;
`Versions\version-4f087c32742644ab\StudioMCP.exe`, 8,208,336 bytes, SHA-256
`3D5CF029E535251D530BBE1E4765D4183BD1396F52D51E85C97CD98D9E285092`,
reported valid Roblox Corporation Authenticode signature. Installed contents,
arguments, dependency/child chain and source-to-build correspondence remain unknown.
R3's access denial remains in force; no alternate access path was attempted.

## 2. Findings from the actual source

Locations below refer to the post-R5 source; the two-line fix shifts later R4
locations by two. Severity **High/blocker** means the guarantee is required before
a real observation, not that a live exploit was observed. **Medium** identifies
a concrete local correctness issue; **Low** identifies a reporting qualification.

| ID / severity | Source location | Finding and disposition |
| --- | --- | --- |
| R5-01 — Medium, **fixed** | `tool/c2b_recording_supervisor.py:159–195`, especially `process.wait()` at 175 | R4 caught `TimeoutExpired` but not `OSError` from root wait. An injected wait-handle error escaped `_stop`, interrupting subsequent active-job verification and the caller's remaining `finally` cleanup, including Job Object closure. No success receipt was produced, but cleanup guarantees were incomplete. R5 records the error, continues verification/closure and retains `uncertain=true`, even when later polls confirm exit. No error is converted to success. |
| R5-02 — High/blocker, open | supervisor `:79–156`, `:525–532`; fixture `:29–39`, `:63–66` | `Popen` executes before `AssignProcessToJobObject`. The trusted fake waits for stdin before spawning its descendant; an eager real root/shell can execute/spawn before assignment. “Assigned before stdin” is not “contained before execution.” No real launch is permitted through this seam. See §4. |
| R5-03 — High/blocker, open | supervisor `:496–563`; `opencode.json:35–39` | The runner constructs its own requests; it neither consumes OpenCode stdin nor exposes a filtered MCP catalog/CLI. Registration still names an enabled unrestricted batch launch. Merely pointing it at this module would not create a functioning proxy; adding another registration would leave a bypass. Effective settings and sole-path integration are unverified (§5). |
| R5-04 — High/blocker, open | supervisor `:510–516`, `:637–660`; `tool/c2b_evidence.py:33–58` | Exclusive creates, hashes and pathname reparse checks do not establish NTFS confidentiality, effective ACLs, race-resistant opens or power-loss durability. No protected live directory was provisioned or verified (§6). |
| R5-05 — High/blocker, open | supervisor `:553–563`, `:612–629` | `synthetic_state_review` is a test boolean; no independently authenticated pause, withdrawal check or UTC validity/expiry verifier exists. Receipts correctly say `authorization=null`, `utc_verified=false`. A caller-set flag cannot become operator consent (§7). |
| R5-06 — High/blocker, open | supervisor `:437–493`, `:615–627`; R4 report §1 | Protocol version/capabilities and result schemas are synthetic expectations. Installed short-wire/tool-alias mapping, upstream transformations/completeness and independent real identity fields are unverified. Plausible silent shortening cannot be detected; the code correctly withholds full-upstream/compatibility claims. Unknown real wrappers must stop for offline review, without retries or a weakened decoder. |
| R5-07 — High/policy blocker, open | preflight §§5/7; R1 §4; R2 §3; R4 §5 | Complete-raw-retention wording has not been amended to permit incomplete oversized-failure prefixes. R5 proposes exact text in §8 but does not adopt it. Passing prefix tests or a later tool-call approval cannot settle this policy. |
| R5-08 — Low, reporting qualification | supervisor `:437–444`; R4 report `:103–105` | Initialization does **not** pin the fixture's exact server name/version; it accepts any nonempty strings under exact `serverInfo` keys. R4's “name/version result ... checked” must be read as shape/type checking, not identity attestation. No version/build or real server identity is proved by that check. Historical R4 text is preserved. |
| R5-09 — Medium, verified limitation | supervisor `:344–409`, `:569–606` | Per-call watchdogs do not bound process creation, all disk calls, final evidence commit or total runner lifetime. Post-response nonzero root exit is detected when observed before stop (`root_before_stop`), not an atomic proof of no crash racing teardown. A per-frame `accepted=true` can coexist with later session refusal. Overall status, cleanup certainty and verified files must govern; neither a frame flag nor marker existence establishes successful/complete observation. No live success claim is justified. |

### Policy, lifecycle, capture and fail-closed audit

| Check | Verified source behavior / limit |
| --- | --- |
| Fake-child-only boundary | `run_synthetic` validates a fixed `SCENARIOS` set, actual bool review flag, safe name and finite `0 < window <= 30`. It constructs `[sys.executable, '-I', '-u', bundled_fixture, scenario]`, with binary pipes, `shell=False`, `close_fds=True`, and refuses non-Windows launch. No user argv, real executable, live option, network or authorization API exists. Fixture/source/runtime integrity is a local trust assumption: the digest read before `Popen` does not prevent file replacement. This is not a sandbox against rewriting Python/repository files. |
| Exact tools/arguments/order | `GateAPolicy` (`:51–76`) allows `tools/call` only: once `list_roblox_studios` with `{}`, then review, once `get_studio_state` with exactly the fixed `studio_id`. Extra keys/metadata/task arguments, aliases, other IDs, repeats and other methods are refused. `check()` is a policy check, not an authorization/consumption API; actual runner dispatch is sequential and hardcoded. |
| JSON-RPC IDs/envelopes | `request` (`:344–409`) keeps one pending client request, uses fresh session string IDs and requires exact ID type/value and exact result envelope. RPC errors refuse. `_strict_json` rejects duplicate keys, nonfinite numbers, malformed UTF-8/JSON, overflow and excessive decoder recursion. Batches and result/error ambiguity refuse. Predictable IDs correlate messages, not authenticate a server. |
| Lifecycle/unsolicited messages | Fixed initialize/version/empty client capabilities, then exactly initialized notification with bounded writer join. Only typed, unreused server ping IDs and exact bounded logging shapes are handled during a pending request (`control`, `:411–434`). All other notifications/requests, including unrequested progress, sampling, roots, elicitation and list changes, refuse. No shutdown RPC is invented. Pending idle output refuses before the next request; trailing bytes invalidate final success. Allowed logging arriving between requests can therefore conservatively refuse too. No grace-period quiet check can prove absence of later output. |
| Raw bytes before parsing | Binary `os.read(..., 4096)` feeds bounded memory (`_Capture`, `:198–255`). `next_frame` (`:318–342`) exclusively writes, fsyncs and compares frame readback **before** `_strict_json`. Original LF/CRLF, UTF-8 and whitespace survive. Incomplete/overlimit data is retained only as bounded raw prefixes, not parsed as successful responses. This boundary is the fake stdout pipe, not Studio's internal transport or OpenCode's model display. |
| Size/frame bounds | 65,536 bytes **including delimiter** per frame; 262,144-byte session stdout prefix; 65,536-byte stderr prefix; failure after the 33rd frame is seen. At most 32 frames can be processed successfully, but the refused 33rd delimiter can be retained. No unbounded event queue; JSON object overhead and child memory are not certified limits. A consumed OS read may contain up to 4,096 bytes, including unretained tail beyond the crossing; received counts are lower bounds, not upstream lengths. |
| Watchdog | Independent thread, absolute `monotonic_ns` deadline set before request persistence/write, never reset by control traffic. Storage/validation time is included; at/after-deadline validation refuses. Watchdog lateness is recorded. `notifications/initialized` has a separate bounded join, not the per-request guard. An arbitrarily stuck filesystem call or suspended controller is not physically interrupted by this design. |
| Tree termination | Kill-on-close Job Object, job termination plus owned-root kill fallback, bounded root wait and active-job polling. Root/tree/reader/writer/watchdog uncertainty withholds success. A synthetic descendant is actually tested. R5-01 improves wait-error handling without waiving uncertainty. Job membership is not authority to stop an existing external Studio operation. |
| Storage errors/commit | Request bytes are saved before attempted transmission; completed pipe-write counts are recorded separately. `StorageFailure` aborts dispatch, runs cleanup and propagates without creating a final marker. Final-prefix/receipt/marker write errors likewise return no trusted success. Exclusive-create errors never reuse the destination. `verify_recording` checks regular/reparse status, safe manifest names and file/receipt digests. A marker can exist before a later verification fails; require successful verification and status review, never file existence alone. |
| Semantics/success | Discovery requires 1–16 unique synthetic ID/name entries and exactly the expected target/name. State canonical comparison preserves bool/int distinctions and requires all fixture fields; it never backfills identity. Substring truncation suspicion may conservatively reject legitimate text; silent semantic shortening may evade it. All receipts still set `compatibility_pass=false`, `upstream_completeness='unverified'`, `full_upstream_response_claim=false`, upstream total null. A synthetic `status` is not a compatibility PASS. |

No exposed arbitrary-command or extra-tool bypass was found in this runner under
its stated trusted-source/fake-child assumptions. This conclusion neither removes
the identified gaps nor extends the checks to an unimplemented proxy or live server.

## 3. Minimal R5 correctness change and reproduction

Only production change: catch `OSError` around `_stop`'s bounded root wait and
append its message to `errors`. No limits, allowlist, process-launch mechanism,
protocol policy, identity comparison, evidence contract or configuration changed.

New regressions in `tests/test_c2b_recording_supervisor.py`:

- `StopTests.test_wait_oserror_preserves_uncertainty_and_tree_verification`: first
  run against R4 **ERROR**, 1 test, 0.001s, uncaught `OSError` at supervisor line
  175. Confirms the original defect with pure local doubles.
- `SupervisorTests.test_wait_oserror_still_closes_job_and_withholds_success`:
  launches only the real fake child, injects a wait error, verifies Job Object
  closure, confirmed empty owned tree, committed **uncertain failure** receipt
  and incomplete-failure evidence classification. Both regressions pass after fix.

## 4. Real-process containment design — feasible, not implemented

**Pre-resume containment is feasible on Windows in principle. The intended
installed launch mechanism is not yet verified, so feasibility is not readiness.**

1. Obtain exact permitted launcher bytes/child arguments first. Current project
   configuration explicitly launches `cmd.exe /d /c %LOCALAPPDATA%\Roblox\mcp.bat`.
   `shell=False` around that command would still execute a shell. The batch may
   select a version or start/delegate processes; hashes/signature alone reveal no
   such behavior. Do not silently substitute a direct executable or invent args.
2. A narrowly scoped future launcher can use `CreateProcessW` with an explicit
   absolute application path, a reviewed quoted command line/environment/cwd and
   **CREATE_SUSPENDED**, retaining both process and primary-thread handles.
   Create/configure the Job Object first (kill-on-last-handle-close, no breakaway
   permissions); assign the suspended root and verify success **before** any resume.
   An incompatible enclosing job, assignment failure or failed verification must
   terminate the still-suspended root, confirm exit/empty job, close handles and
   dispatch zero bytes. `ResumeThread` and its expected suspend count must be checked.
3. `subprocess.Popen(creationflags=CREATE_SUSPENDED)` is not a sufficient public-API
   solution: CPython's Windows `Popen` does not retain a usable public primary-thread
   handle for checked resumption. Do not resume by PID lookup/thread enumeration or
   launch normally and hope the root waits. A reviewed small Win32 creation seam
   must own those handles explicitly; no such seam is added in R5.
4. Address supervisor death **between creation and assignment**: a suspended orphan
   cannot run but can remain stranded. On a verified supporting Windows version,
   `STARTUPINFOEX`/`PROC_THREAD_ATTRIBUTE_JOB_LIST` offers creation-time job membership,
   combined with suspension and later checked resume. Validate support/nested-job
   behavior in fake-only tests; fail closed without a normal-spawn fallback. Otherwise
   a separately verified owning broker/recovery design is needed. A kill-on-close job
   cannot clean up a process never assigned to it.
5. Use an explicit inherited-handle list containing only the child's stdin-read,
   stdout-write and stderr-write ends. Parent ends and the job handle must be
   noninheritable. Close parent copies of child ends immediately after creation;
   close all partial handles on every failure. `close_fds=True` in R4 narrows
   inheritance but is not proof that a future batch/child chain closes pipe copies.
   A descendant holding a pipe open must remain in the owned job and must be tested.
6. No shell search or uncontrolled `%...%` expansion is acceptable as a pin. If the
   batch is truly necessary, contain the **shell root** before its first instruction,
   review quoting/version selection and every spawned/delegated path. If direct
   executable launch is equivalent, establish that from permitted source evidence
   before choosing it. Disable breakaway; job assignment is still not a general
   security sandbox against same-user code delegating work to external services.
7. Keep request deadlines, startup/handshake and shutdown budgets distinct. Define
   bounded pipe-write cancellation/join behavior (checked Windows I/O cancellation
   or a tested teardown that unblocks every owned pipe), EOF/trailing-output handling,
   and externally recorded timeout/cleanup uncertainty. A blocked disk call or OS
   suspension still precludes a universal physical hard-stop claim. Terminating the
   local job does not cancel already-delivered work in an existing Studio process;
   refuse, retain evidence, stop without retry/diagnostics.

Required evidence: fake root that signals at its first instruction and eagerly
spawns, blocked stdin and inherited-pipe descendant cases, assignment/resume failure,
nested-job incompatibility, supervisor death in the creation window, and checked
root/tree/handle/thread cleanup. The failure cases must show **no first-instruction
signal before containment**. No real executable needs to run for these tests.

## 5. OpenCode integration and missing configuration evidence

Project `opencode.json:35–39` has one enabled Roblox registration using the batch
command and `timeout: 30000`; `:48–61` denies external-directory access and Git
mutation commands. The config was read only. Neither its presence nor this
session's already-exposed tool definitions establishes the effective registration.
R1/R3's denied external directories/files were not accessed again.

**The existing supervisor cannot be integrated as-is.** A future narrow stdio
front end would replace the **same effective Roblox registration**, never add a
second Roblox route. It must expose only the approved discovery/state surface,
record upstream stdout before SDK parsing and mediate every upstream dispatch.
Automatic OpenCode startup must start only that front end; the real child must
remain unlaunched until the separately verified launch/protocol approval, storage
and time prerequisites pass. A narrowed catalog alone does not gate connection.
The current tool catalog/session aliases must not remain as another selectable
server. Old loaded bindings need retirement and separately authorized new-session
activation; a disk edit does not prove that has happened.

Before a design can be pinned, supply a credential-free, provenance-bound packet:

- Exact installed OpenCode executable/package/build identity and matching SDK
  versions/source excerpts for local spawning, config precedence/merge,
  initialization, tools enumeration, aliasing, timeout origin, cancellation,
  parallel calls, default retry/reconnect and result transformation/limits.
- Explicit list of **all loaded config paths and override sources**, effective
  resolved Roblox command/enabled/timeout/permissions, relevant environment
  overrides and plugin/hook identities with digests. Include global/project/
  command-line/managed settings as actually applicable; do not assume a generic
  OpenCode precedence description establishes this installation.
- Operator-supplied copies, or separate exact-file read permission, for the launcher
  and each identified child/config/source file. Original absolute paths, byte
  counts, digests and acquisition/source-to-build provenance must accompany copies.
  This review does not grant access to `.config\opencode`, credentials or other
  denied directories. Unknown installed source paths cannot yet be enumerated.
- A resolved effective binding/catalog/loaded-session inventory proving no alias,
  plugin, duplicate registration or stale session routes directly to the batch/
  executable; a reviewed config diff limited to the Roblox entry for later approval.

OpenCode may require `tools/list`/other lifecycle exchanges. R4 denies `tools/list`
and has no client-facing catalog. A future front end may answer a fixed reviewed
catalog locally, with state dispatch disabled until genuine review, but even that
control contract must be explicitly reviewed. It must not forward the unrestricted
upstream catalog, treat automatic requests as approval, add retries or relax the
raw collection limits. Required real protocol/name/result evidence remains absent;
it may require supplied vendor/build evidence or a separately bounded observation
that stops on unknown results. No automatic wrapper adaptation is allowed.

## 6. Windows evidence storage: distinct guarantees

| Property | Current guarantee | Missing proof/control before live use |
| --- | --- | --- |
| Exclusive creation | `mkdir` reserves a new run name; `xb` refuses existing leaf files. Short/zero-write handling and readback are tested, including concurrent collectors. | Does not prevent later replacement/deletion, prove owner rights, or protect a replaced parent. Never reuse a partial name. |
| SHA-256 integrity | Hashes actual readback bytes; marker hashes receipt; manifest verification detects changed retained files. | Local consistency only. A same-user writer can recompute all hashes. It neither authenticates the server/operator nor proves original upstream length. |
| Actual NTFS ACL protection | **Not verified.** Numeric `0700` in this Python 3.12.7 run is not evidence of a Windows DACL. | Prove NTFS volume, owner, inherited/explicit DACL and effective access including group membership at the exact approved parent/new leaves. Operator-reviewed trusted principals only; broad unapproved readers/writers must be absent. ACLs cannot promise secrecy from every privileged administrator. |
| Path-race protection | `lstat` rejects symlink/reparse ancestors and nonregular evidence leaves at check time. | Check/use and close/reopen races remain in `mkdir`, `open`, readback and verification. Use reviewed handle-based no-follow/relative opens, or substantiate exclusively controlled ancestors and permitted-writer threat model. A point-in-time ACL listing alone does not stop an authorized writer racing paths. |
| Flush/fsync | Each successful helper write calls Python flush and `os.fsync`, then compares reopened bytes. Failure aborts. | No directory-entry flush or volume/device cache/power-failure validation. Readback may come from cache. Filesystem calls have no certified hard deadline. |
| Power-loss durability | **Not proved.** A completed marker/readback is not a power-cut experiment. | Agree the required crash/power-loss fault model, retention/backup guarantees and recovery validation; provide supporting filesystem/device/flush or other reviewed durable-storage evidence for any guarantee claimed. Do not relabel `fsync` as universal durability. |
| Confidentiality/retention | Raw evidence remains potentially private/adversarial; no encryption or ACL provisioning by the recorder. | Verify private nonshared/nonsynced parent, approved backups and recipients, available quota/headroom and agreed aggregate budget; protected originals for at least 30 days **and** until review completion. Identity validation uses originals; separate redacted copy and manifest for sharing; operator-decided disposal. |

Only temporary synthetic storage was used for tests. R5 changed no ACL, storage
location or existing evidence. New-only files, hash/readback and failure behavior
are verified; private/protected live storage remains an independent blocker.

## 7. Smallest verifiable UTC/monotonic procedure — design only

R2's correction stands: `2026-10-17T17:34:19.979028+00:00` equals
`2026-10-18T01:34:19.979028+08:00`. This is timezone conversion, not measured clock
error. A local UTC-formatted timestamp, harness date, stopped Windows Time service
or monotonic timer establishes neither UTC accuracy nor approval validity. No
clock query, time-source request, service start or clock change was made in R5.

Retain the existing two-independent-source requirement; the smallest useful
implementation is a **pure interval/expiry check over independently acquired
evidence**, not a time synchronization client:

1. The operator first approves exact source identities, authenticated acquisition
   methods and numeric freshness/uncertainty/query/drift limits. Two independent
   authenticated sources must provide auditable UTC estimates, synchronization
   state, precision/error bounds and provenance, tied to the local capture interval.
   Two URLs backed by one clock, ordinary unauthenticated NTP, a bare HTTPS `Date`,
   an unsigned copied timestamp or an operator's “clock looks right” do not suffice.
   A signed time response or authenticated service evidence still needs an accuracy
   bound; authentication alone proves who spoke, not that the clock was correct.
2. Bracket each bounded read with local wall UTC and `monotonic_ns` samples and keep
   its complete protected source evidence. At a common monotonic anchor `M`, derive
   each source interval `[Li, Ui]`, including source error, request/capture delay,
   timer precision and elapsed drift. For a timestamp generated somewhere inside
   bracket `[a,b]`, a conservative starting form is
   `[t-u+(M-b)-D, t+u+(M-a)+D]`, with units aligned and a justified drift/precision
   bound `D`. Missing generation/capture semantics or unknown `u` is refusal, not
   permission to invent a narrow interval.
3. Require fresh synchronized evidence and overlapping intervals. Use their
   conservative **covering** interval `[min(Li), max(Ui)]`, not an averaged clock.
   Nonoverlap, overlong query, stale source or excessive uncertainty stops the
   procedure. Preserve disagreement; never widen tolerances to obtain acceptance.
4. Advance that interval using elapsed monotonic time and documented worst-case
   drift. Before real launch/connection and each actual dispatch, check verified
   operator channel/reference,
   scope, withdrawal and that the **entire** interval lies within approval validity.
   Require `latest_possible_UTC + 30 seconds + drift/timer margin < expiry`.
   Set the absolute monotonic per-call deadline before persistence/write; no
   notification resets it. Launch/handshake need their own reviewed expiry budget.
   Discovery evidence finalization and human review may
   age the mapping: reverify before state rather than reuse stale calibration.
5. Check bracketing wall-versus-monotonic deltas for steps/excess drift, and require
   no suspend/resume, reboot, missing monitoring samples or clock anomaly. Obtain
   independent post-observation comparisons before certifying authorization-time
   validity. A changed mapping retains evidence but invalidates that claim and
   prevents the next call; no retry, clock repair or extra Studio diagnostic follows.

A concrete **proposal for separate review**, not adopted limits: each source read
at most 5 seconds; common-anchor covering width at most 2 seconds; calibration age
at most 60 seconds at dispatch; post-check within 60 seconds. Require a measured/
documented platform drift bound for that interval, not an assumed oscillator rate.
If the selected sources cannot substantiate these ceilings, stop and revise the
proposal offline. Record all numeric bounds with the evidence so another reviewer
can recompute the intervals and expiry inequality without trusting a boolean flag.

Permission would be needed separately for authenticated external source queries,
corporate time-service access or operator acquisition/submission of source evidence
under an approved method. Any synchronization/service/clock change is a distinct
operation; this procedure can operate read-only and does not authorize it. UTC
verification, monitoring and independently authenticated pause/withdrawal remain
unimplemented; current receipts must continue to say `utc_verified=false`.

## 8. Oversized-response policy: proposed amendment, NOT adopted

The user's proposed distinction matches R1's synthetic collector and R2 §3's four
outcomes. It is **conditionally consistent** with the preflight only if its complete
retention requirement is explicitly scoped to accepted responses and bounded partial
failure evidence is permitted. Arbitrarily large full failures and a fixed retained
response cap cannot both be guaranteed. Operator decision is still required.

Exact proposed amendment to preflight §§3/5/7 and the R1/R2/R4 live contract:

> At the explicitly reviewed capture boundary, an accepted response must retain
> and verify the complete original response bytes, including JSON-RPC envelope
> and framing, within 65,536 bytes and all other approved limits. This is necessary
> but does not alone prove upstream semantic completeness, identity or compatibility.
> If a response exceeds that limit, stop acceptance/dispatch and initiate reviewed
> teardown. Retain at most the first 65,536 response bytes as explicitly incomplete
> oversized-failure evidence; do not drain the tail for collection. Never classify
> this outcome as compatible, complete or successful, and never claim that its
> prefix is the full upstream response. Hash/count only retained bytes. Record
> any actually consumed OS-read count separately as a lower bound; full upstream
> length remains unknown unless independently established. No retry or next call
> follows. Preserve the refusal reason, correlation/timing and cleanup uncertainty
> under the same approved confidentiality, retention and redaction requirements.
> This exception changes failed-response retention only; it adds no envelope,
> tool, target or authorization. Control frames, combined stream copies, stderr,
> metadata and aggregate storage/read-ahead budgets require separate explicit
> limits; they cannot be used to retain an additional oversized-response tail.

Clarify at decision time whether the 65,536-byte cap is on **distinct retained
response content** (R4 duplicates some bounded frame/stream bytes) or **total physical
storage per response**. R4 is not the latter: stdout copies can total 524,288 bytes
per session, plus stderr/outbound/metadata. A strict total-storage interpretation
would require a separately reviewed deduplicated layout. R5 does not alter either
contract or implementation to choose an interpretation. No prefix is a full-response
receipt and no synthetic test grants policy authority.

## 9. Focused readiness matrix and smallest next milestone

| Class | Requirement / current decision | Exact evidence needed to close or retain qualification |
| --- | --- | --- |
| Resolved (offline) | Fixed fake-child-only launch and exact tool/argument/order denial | Inspected source and passing policy/Windows tests; continue to keep real argv absent. |
| Resolved (offline) | R5-01 wait-error cleanup defect | Reproduced original uncaught error; both new regressions pass, job closes, uncertainty retained. |
| Resolved (offline) | Raw-byte-before-parse, local hashing/new-only writes, byte/frame bounds | Passing exact-cap, original-byte, overflow/flood, write/readback/storage-failure and tamper tests. Not proof of private/live storage. |
| Verified but qualified | Watchdog, Job Object owned-tree exit and refusal lifecycle | Current tests cover controlled Windows children only. Scheduler/disk stalls, crash races and external Studio cancellation remain outside a universal stop guarantee. |
| Verified but qualified | IDs, controls, fixture discovery/state validation | Strict synthetic schemas/IDs and negative tests. Supply provenance-bound real wire/tool-name/lifecycle/result contract; stop any unknown live result for offline review. No invented identity/defaults. |
| Verified but qualified | Commit marker / `accepted` flags | Verified file set plus final status/cleanup review required. Marker means local consistency, not PASS; upstream completeness remains unverified. |
| Unresolved technical blocker | Installed launcher/runtime/child provenance | Permitted exact copies or scoped reads, original paths/args/bytes/digests, signature/build/source correspondence, dependency and delegation topology. Supplied hashes alone are insufficient. |
| Unresolved technical blocker | Containment before execution | Reviewed suspended/creation-time-job seam, first-instruction/eager-child failure evidence, handle inheritance, nested-job and death-window tests from §4; no real executable required. |
| Unresolved technical blocker | Sole-path OpenCode front end | Effective installed config/build/plugin/SDK packet from §5, narrow protocol/catalog design and exact replacement plan with no duplicate/stale unrestricted route; later separately approved activation only. |
| Unresolved technical blocker | Genuine review/approval/withdrawal boundary | Authenticated operator-channel design with unique scope/expiry binding, replay/withdrawal behavior and tested stop-before-state on refusal/storage failure/expiry. Not `synthetic_state_review=True`, and no mutation authorization-store use. |
| Unresolved technical blocker | Private race-resistant Windows evidence | Exact NTFS path/owner/effective ACL and permitted-writer evidence, no-follow or exclusive-parent proof, headroom/aggregate budget and supported flush/recovery/retention/confidentiality plan (§6). |
| Unresolved technical blocker | Independently verified UTC mapping/expiry | Approved sources/numeric bounds, original authenticated comparison evidence, recomputable intervals, drift/anomaly/suspend checks and dispatch/post-check records (§7). No OS clock adjustment is implied. |
| Operator decision required | Oversized-failure retention and duplicate-storage interpretation | Explicit approval/rejection of §8 amendment and per-response/control/session/storage budgets; rejection needs a different reviewed design. Do not adopt by implication. |
| Operator decision required | Storage fault model/principals and UTC acquisition | Approved confidentiality/retention/durability criteria, trusted writers/readers, exact permitted external time sources/acquisition and numerical bounds. Decisions need technical evidence; approval cannot substitute for it. |
| Later separate readiness gate | Gate A launch/protocol observation | A new offline review finding all prerequisites satisfied; only afterward a fresh independently verified launch/protocol/discovery/conditional-state authorization could be considered. None requested here. |

**Smallest next milestone:** first obtain the permitted, credential-free installed
launcher/OpenCode evidence packet and settle the §8 retention interpretation. The
smallest useful next **implementation** is a Windows **fake-child-only** suspended/
creation-time Job Object containment seam with explicit inherited handles and the
focused failure tests in §4. Keep arbitrary executable paths, live approval and
MCP configuration activation absent. Do not build a general MCP platform or add
a parallel recorder route. The genuine pause/time/storage/sole-path front end
must then be implemented and reviewed against established contracts; they are
not delivered by the two-line R5 fix.

Gate B's bounded query, serialization/path/stability and same-read session identity
blockers remain unchanged. Gate A observation cannot be used to waive them.

## 10. Executed verification

All final commands below exited 0. The earlier intentional R5-01 reproduction
failed as recorded in §3; it is not a final-suite failure.

| Command | Exact result |
| --- | --- |
| `python -m unittest tests.test_c2b_recording_supervisor -v` | **PASS: 37 run, 37 passed, 0 skips, 9.998s**. Includes 35 existing R4 tests plus two R5 regressions; all Windows cases ran. |
| `python -m unittest discover -s tests -p "test_*.py"` | **PASS: 267 run, 266 passed, 1 skipped, 31.602s**. Existing skip: `test_asset_registry.RegistryTests.test_symlink_escape`, `symlinks unavailable`. No new skips. |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events**. |
| `python tool/validate_art.py` | **PASS: 2 metaschemas, 5 presets, 3 positive request fixtures, 36 negative request fixtures; no files written**. |
| `python -m compileall -q tool/c2b_recording_supervisor.py tests/test_c2b_recording_supervisor.py` | **PASS**, no compiler output; both parent directories verified first. |
| `git diff --check` | **PASS**, exit 0; existing LF→CRLF warnings for `docs/IMPLEMENTATION_STATUS.md` and `status.md` only. |
| `git diff --no-index --check -- /dev/null <path>` for `tool/c2b_recording_supervisor.py`, `tests/test_c2b_recording_supervisor.py`, `docs/C1E_C2B_R5_INTEGRATION_READINESS.md` | **PASS**, each exit 0; LF→CRLF warnings only. These files were already untracked, so ordinary `git diff --check` does not cover them. |

The helper, fake fixture, project/global registration and prior milestone history
were not changed. Only supervisor wait-error handling, two regression tests, this
report and R5 status entries changed. **STOP: offline review complete; Gate A not
ready, no execution approval request.**
