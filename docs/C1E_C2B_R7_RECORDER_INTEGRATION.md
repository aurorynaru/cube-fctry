# C1E-C2B-R7 — Synthetic recorder containment integration

## 1. Scope and pre-implementation ownership decision

OFFLINE ONLY. Fixed bundled Python fixtures, enumerated scenarios, no live launch
or arbitrary executable/argv/environment interface. Baseline is
`4661903d4f97cdb8d62adea89544741d3a00871c`. The following contract was written
**before implementation**. Verification/results are recorded below after execution.
No project `AGENTS.md` was found. An external implementation-skill read was denied;
it was not retried or bypassed. Existing dirty/untracked work is preserved.

### Ownership transitions (normative)

| Resource | Before creation / allocation | After creation, suspended | Transfer / execution | Teardown / failure |
| --- | --- | --- | --- | --- |
| Native process handle | Absent; failed native outputs do not confer ownership | R6 boundary registers documented successful `PROCESS_INFORMATION` output | Boundary retains; adapter only borrows under boundary lock for wait/exit query; never PID lookup | Boundary verifies root exit, queries exit code, closes once; cached result thereafter. No action on failed-creation numeric outputs. |
| Native primary-thread handle | Absent | Boundary owns, root suspended in creation-time job | Membership/liveness rechecked; `ResumeThread == 1`; boundary closes thread | Pre-resume failure kills suspended root/job and closes; anomalous resume remains uncertain. |
| Job Object handle | Boundary's registered two-phase job wrapper owns before configuration | Same owner; noninheritable, kill-on-last-close; creation job-list association | Never transferred to CRT, workers, child, or observer | Terminate, wait owned root, verify active count zero **before** checked job close; failed accounting never means tree success. |
| Child stdin-read/stdout-write/stderr-write | Boundary owns controller copies on each successful pipe allocation | Child inherits exactly these handles; boundary closes controller copies before membership verification | Child/contained descendants own their OS copies | Tree death closes child copies; root exit alone is insufficient for EOF or tree exit. Partial setup closes all registered controller copies. |
| Parent stdin-write/stdout-read/stderr-read | Boundary owns noninheritable native ends | Same until bridge takes each named pipe under boundary lock | Explicit `take_pipe`: register receiver, install native reference, commit `claimed=True`, then remove source entry. Boundary close checks the claim if interrupted before source deletion. Lease native -> CRT only on a documented successful `open_osfhandle` return | Before documented conversion failure lease closes native once. After successful conversion **never CloseHandle** that value. Boundary cannot close transferred ends. |
| CRT descriptor for each parent pipe | Absent | Absent before conversion | Successful `open_osfhandle` transfers handle ownership to descriptor; lease is sole descriptor owner. Failed conversion retains lease's native ownership under API contract | After all borrowers join, retire descriptor ownership **before** one `os.close`; failure is quarantined/uncertain, never retried using a possibly reused value. |
| Python binary stream | Absent | Constructed while root still suspended | Unbuffered `FileIO(fd, mode, closefd=False)` **borrows** descriptor. No fd ownership transfer to Python: failed constructor cannot consume descriptor. Workers borrow stream/fileno only | Retire stream, close once, then close owned fd once. Stream-close failure is retained and does not prevent remaining closes. Never close a pipe while any borrower may still be using it. |
| Reader threads | None | Created only after successful checked resume | Session/controller owns thread references; readers borrow stdout/stderr; capture retains bounded bytes | Kill/verify tree to unblock reads, bounded join; any unjoined borrower quarantines all pipe leases and withholds handle/success certainty. |
| Writer threads | None | None | Session registers every writer before start; serialized writes borrow stdin fd. Intended bytes persisted first; completed counts tracked | Watchdog kills owned tree to unblock synchronous write; bounded joins before stdin/pipe close. Incomplete/error write cannot become success. |
| Watchdog threads | None | None | Session registers each independent absolute-deadline guard before start; only borrows stop interface, no pipe ownership | Signal done, bounded join, retain any uncertainty even if later joined. Native stop/create/resume serialized with R6 lock. |

All pre-resume conversions finish before checked resume. Adapter setup failures
stop/verify the still-suspended job and close every conclusively owned lease. Stops are
idempotent and cached. No ownership is inferred from numeric equality or later
handle validity: successful documented allocation, explicit registry transfer,
and retired state establish ownership. Native R6 close-failure bookkeeping is
cached and never retried by the adapter. CRT close errors retire rather than retry
the value, preventing double-close/reuse hazards; they cannot certify no leak.
If a worker cannot join, descriptors remain quarantined (possible leak explicitly
uncertain), rather than creating use-after-close. No uncertain cleanup is success.
Abrupt controller death relies on OS process-handle closure and the noninherited
job; observer tests must not retain a job handle. In-kernel creation interruption
and universal cross-version behavior retain R6's qualification.

### Final-review refinement: ambiguous native returns are BLOCKED

The initial table assumes documented API returns. Final review added explicit
handling for interruptions that hide an ownership-changing call's return:

- Pipe handoff has an explicit lease claim, so an interruption cannot authorize
  both the source registry and lease to close the same end.
- Before `open_osfhandle`, native-close authority is surrendered into pending
  transfer bookkeeping. A documented `OSError` restores caller ownership. A
  registered successful fd is the only CRT-close authority, even if old native
  bookkeeping remains. `FileIO` never takes descriptor ownership.
- If an interrupt hides that return and no fd was registered, ownership is
  **unverified**. Refuse before resume, terminate/verify the known job, quarantine
  the pending value, set `handles_closed=false`/`uncertain=true`; never close by
  guessing which numeric representation owns it. `KeyboardInterrupt` propagates
  after cleanup, without a successful return or final recording.
- Similarly, interrupted `CreateProcessW` with nonzero output fields but no
  observed success return marks failed-output/root/handle uncertainty. Job
  accounting can still prove the known tree empty. Only a documented successful
  return authorizes registration/closure of those process/thread handles.
- These are **BLOCKED ownership outcomes**, not verified transfers or leak-free
  recovery. Unknown resources may remain until controller exit. Tests' independent
  injectors know the actual successful calls and release their own exact resources;
  the bridge never borrows that knowledge or promotes the uncertain result.

Thus all **documented** native/CRT ownership transitions are verified on this host;
unconditional ownership/no-leak certification across arbitrary hidden-return
interruptions is **not established**. The adapter refuses those cases rather than
implement an unsafe recovery. No claim that every conceivable transfer is known.

## 2. Implementation boundary and preserved contracts

**Synthetic integration succeeded on the supported host. Gate A remains NOT
TECHNICALLY READY.** No live execution approval is requested. Runtime: Python
**3.12.7**, AMD64, Windows version tuple **10.0.26200**, platform 2, empty service
pack. Date label **2026-10-18** is the harness date, not verified UTC.

| File | R7 responsibility |
| --- | --- |
| `tool/c2b_native_recorder.py` | Fixed bundled MCP boundary subclass, explicit pipe leases, native/CRT/borrowing-stream bridge, exact-owned-handle poll/wait, idempotent native stop and worker-safe finalization |
| `tool/c2b_windows_containment.py` | Small reusable fixed-fixture selection seam, explicit pipe handoff, checked exit-code query before native process close, uncertainty for hidden native return; original containment mechanism retained |
| `tool/c2b_recording_supervisor.py` | New `run_contained_synthetic`, shared existing protocol/capture/policy implementation, complete worker registration, contained teardown and additive evidence fields; legacy entrypoint explicitly labeled |
| `tests/fixtures/c2b_fake_mcp.py` | Existing original scenarios plus contained-only `blocked_stdin`, `inherited_stdout`, `eager_stdio`; one fixed internal pipe-holder role |
| `tests/fixtures/c2b_recorder_controller.py` | Fixed disposable controller for death after CRT transfer and after eager descendant execution |
| `tests/test_c2b_native_recorder.py` | 60 Windows tests: 31 bridge/fault/ownership cases and 29 reused original protocol assertions against the new boundary |

`run_contained_synthetic(parent, name, scenario='normal', *,
synthetic_state_review=False, window_seconds=30.0)` accepts only safe evidence
names, finite existing watchdog bounds and enumerated fixture scenarios. The
adapter selects the absolute bundled fixture internally and uses R6's fixed
absolute current Python runtime with `-I -S -u`. No executable/command/argv/env/
shell/live-Studio input, CLI, registration or normal-spawn fallback was added.
The legacy runner refuses the three new diagnostic scenarios; its original
scenarios and tests remain available as regression comparison only.

Creation still configures kill-on-close before `CreateProcessW`, passes job and
explicit child-handle lists with suspension, verifies membership/liveness while
suspended and again before resume, and requires `ResumeThread == 1`. All three
pipe conversions complete before resume. Job/process/thread stay native and
noninherited; CRT pipes are explicitly `O_BINARY | O_NOINHERIT`, with direction
flags. Neither child stdin cooperation nor speed of assignment establishes
containment. The eager descendant runs without receiving stdin, inside the job.

The existing initialize/initialized sequence, exact discovery → recorded review
pause → conditional state policy, strict typed JSON-RPC IDs, allowed ping/logging
controls, raw stdout persistence/readback **before** parsing, bounded stderr,
65,536-byte inclusive frame cap, 262,144-byte stdout session cap, 65,536-byte
stderr cap, 32-frame success limit and absolute independent watchdog are reused.
No tool, alias, identity default, retry or live envelope was added. The original
33 containment tests, 37 supervisor tests and 25 evidence tests were preserved.

Receipt schema remains **`c2b-offline-supervisor/1`**: existing fields and success/
failure meanings are unchanged. Additive `launch_boundary` distinguishes
`creation_time_contained_synthetic` from
`legacy_synthetic_post_popen_assignment`. Contained receipts add `containment`
(R6 report) and `pipe_ownership` (states/events/errors). `shutdown.handles_closed`
in the contained runner covers native **and** CRT/stream closure; R6's nested
`containment.cleanup.handles_closed` covers its native registry only. The change
is additive and requires no schema-version fork. Receipt/manifest and committed
marker SHA-256 verification remain mandatory; marker existence is not success.

Every receipt still states `studio_touched=false`, `authorization=null`,
`utc_verified=false`, `compatibility_pass=false`,
`upstream_completeness='unverified'`, `full_upstream_response_claim=false` and
unknown total upstream bytes. Synthetic review is not operator authorization.

## 3. Actual interruption and teardown evidence

All rows used actual synthetic Windows children where creation is relevant.
Injected failures are distinguished from real blocked I/O and death observations.
Test method names below are in `tests/test_c2b_native_recorder.py` unless noted.

| Required case | Actual assertions / result |
| --- | --- |
| 1. Normal initialize, discovery, conditional state | 29 reused original protocol tests run against contained entrypoint, including discovery-only pause and exact state sequence. Native entrypoint test forbids `Popen` and late assignment in the controller; membership true, resume count 1, complete writes, verified receipt and exact lease-close event sequence. |
| 2. Shutdown before creation | `closed_controller_before_create_never_calls_native`: cached clean stop before `start`; no `CreateProcessW` invocation, no dispatch. |
| 3. Failure after creation/before resume | Actual suspended root; injected verified checkpoint error, native resume never called, blocked-stdin marker absent, known tree/handles closed. Separate resume anomaly receipt remains uncertain despite clean tree/handles. |
| 4. Win32→CRT conversion failure | Documented pre-transfer `OSError` at each of the three pipes; earlier CRT ends close via fd, failing lease closes native, untransferred source ends close in R6; no resume. Post-CRT registered error/interrupt closes fd only. Hidden-return case is explicitly BLOCKED/quarantined (§1), not a PASS for ownership recovery. |
| 5. Failed stream creation | `FileIO` constructor failure at each pipe, asserted `closefd=False`; fd closes once. Post-stream failure closes stream then fd once. A real borrowed-stream close independently leaves fd valid until lease closes it. |
| 6. Reader failure | Injected `os.read` failure on real fixture pipes; no accepted call or write, verified incomplete-failure receipt, confirmed tree stop and closed leases. Failure may occur before first request registration. |
| 7. Partial/blocked stdin | Reused three-byte actual write loop succeeds. Separate **test-only injected 1 MiB initialize frame** fills real anonymous pipe to child that does not read; actual watchdog fires, job stop unblocks synchronous writer, write error/partial completed-call count retained, all workers join and leases close. Normal public requests are unchanged. |
| 8. Child crash | Reused actual mid-frame/crash/trailing/post-response crash scenarios refuse; no incomplete or mismatched result becomes session success. Post-response exit racing teardown remains qualified (§6). |
| 9. Descendant retaining stdout | Actual root returns 0 while job still has one descendant; reader alive and no stdout EOF. Job termination reaches zero, then both EOFs and worker/lease cleanup are verified. Root exit is not treated as tree exit. |
| 10. Watchdog during active request | Real timeout, logging traffic not resetting deadline, and stalled validation: independent guard terminates tree; no accepted late frame. Blocked writer case above is actual pipe backpressure. |
| 11. Shutdown/completion race | Five actual child sessions with barrier-coordinated stop racing writer/read completion, serialized stop, bounded joins and clean tree/lease closure. This is finite interleaving evidence, not exhaustive scheduling proof. |
| 12. Repeated closes/invalidity/reuse | Immediate native handle invalidity error 6 after stop/lease close; repeated `finish`/lease close no extra events. Deliberate reuse of retired CRT fd by an unrelated file survives subsequent closes. Noninheritance and `FileIO.closefd=False` independently checked. |
| 13. Abrupt controller death | Actual disposable controller killed using exact owned Popen handle after first native→CRT transfer while root suspended, and after eager root/descendant execution. Exact duplicated owned root/descendant observer handles become signaled; **no job handle retained by observer**. No commit is fabricated by dead controller. |
| 14. Accounting/cleanup failure | Injected job accounting error retains root confirmation/closed handles but tree false and uncertainty. Native-close, stream-close and CRT-close report failures retain uncertainty and never retry retired values. Graceful wait `OSError` is not erased by later successful native stop. Unjoined borrower quarantines leases and cannot become successful cleanup. |
| 15. Evidence commit failure | Actual protocol exchange, injected `COMMITTED.json` write failure; raises, no marker or successful return; tree and all handles closed. Reused raw-frame storage failure test also stops child and produces no commit. Hash tampering/new-only/readback tests remain passing. |
| 16. Unknown/malformed/oversized frames | Native reuse covers unknown controls, invalid UTF-8, duplicate JSON keys, nonfinite numbers, batches, ambiguous envelopes, wrong typed IDs, duplicate responses, exact cap, oversized prefix, stream/log/stderr/session floods, truncated EOF and declared errors. Failures retain bounded originals and do not claim completeness. |

All known workers are registered before start, including initialized/control
writers and watchdogs. Failed starts remove the unstarted reference. Native
tree stop does not close active CRT I/O. Finalization joins outside the process
lock (avoiding a watchdog waiting on the same lock), then retires/closes streams
and descriptors. Prior watchdog/writer/reader uncertainty is retained even if a
later join finishes. Unjoined-worker and ambiguous-transfer tests deliberately
do **not** certify leak-free teardown; test-owned cleanup releases resources only
after independently establishing ownership/borrower exit, without rewriting the
original uncertain outcome. No guessed PID, thread enumeration or unrelated
process destruction is used.

## 4. Development failures and corrections

1. First focused R7 run: **48 tests, 1 failure, 1 error, 15.877s**. The death
   checkpoint was not reached; reader-failure test assumed a call existed even
   though readers can refuse before first dispatch. Correction asserts **all calls
   unaccepted and no writes**; empty call list is valid refusal, not invented work.
2. Two-case follow-up: **1 failure, 5.273s** (death checkpoint). Three eager-only
   diagnostic runs also failed at the same fixed 5-second checkpoint (5.010s,
   5.020s, 5.018s). Root/descendant were both in the job, but the eager descendant
   did not reach its Python marker while sharing stdin with root blocked reading.
   Using `DEVNULL` for **eager descendant stdin only**, retaining actual inherited
   stdout/stderr, fixed the checkpoint: both eager/death tests passed in **0.621s**.
   No timeout increased. This does not certify the precise internal cause or
   successful concurrent shared-stdin startup; inherited-stdout/root-exit tests
   separately use real shared handles and verify teardown.
3. Review corrections before final checks: join outside process lock; preserve
   graceful wait errors; retire failed closes rather than retry; give registered
   CRT authority priority over stale native bookkeeping; commit explicit source
   handoff claims; mark unobserved CRT/native returns BLOCKED instead of claiming
   handle closure. Added regressions for these paths, borrowed streams,
   noninheritance, reused descriptors, stream/native/CRT close errors and interrupt
   cleanup. These were review discoveries, not hidden passing guarantees.
4. Intermediate successful runs: **152 focused / 25.485s**, **357 full / 46.336s**
   (one existing skip), then **153 focused / 25.569s**. Superseded by the final
   155/360 totals below. No final unresolved test failure exists.

## 5. Final executed verification

| Command | Actual result |
| --- | --- |
| `python -m unittest tests.test_c2b_native_recorder tests.test_c2b_windows_containment tests.test_c2b_recording_supervisor tests.test_c2b_evidence` | **155 passed, 0 skips, 25.133s**: 60 R7 + 33 R6 + 37 R4/R5 + 25 evidence tests. |
| `python -m unittest discover -s tests -p "test_*.py"` | **360 run, 359 passed, 1 skipped, 46.480s**. Only existing `test_asset_registry.RegistryTests.test_symlink_escape` (`symlinks unavailable`); every Windows containment/recorder case ran. |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events**. |
| `python tool/validate_art.py` | **PASS: 2 metaschemas, 5 presets, 3 positive request fixtures, 36 negative request fixtures; no files written**. |
| `python -m compileall -q tool/c2b_native_recorder.py tool/c2b_windows_containment.py tool/c2b_recording_supervisor.py tests/test_c2b_native_recorder.py tests/fixtures/c2b_fake_mcp.py tests/fixtures/c2b_recorder_controller.py` | **PASS**, no compiler output; all three parent directories verified with `Test-Path` first. |
| `git diff --check`; individual `git diff --no-index --check -- /dev/null <path>` for the six changed/new Python files and this report | **PASS**, LF→CRLF warnings only. No-index checks cover untracked milestone files, unlike tracked diff. |

All tests used local temporary synthetic stores/children; no production evidence,
ACL, authorization lifecycle or UTC service was exercised. No StudioMCP.exe,
mcp.bat, Roblox MCP call (including real discovery/state), Luau, screenshot,
Studio mutation/upload/camera/save/publish, ComfyUI, external time request,
OpenCode activation/configuration edit, dependency install, Git staging/commit/
push, Swarm or subagent occurred. Existing `opencode.json` and unrelated changes
were retained. This session used only the requested repository and verification
tools; the refused external skill read was not bypassed.

## 6. Remaining blockers, verdict and smallest next milestone

- **Synthetic recorder integration: succeeded**, with documented ownership paths,
  contained dispatch and receipts verified on this Windows/Python combination.
- **Pre-execution containment: preserved** by R6 creation-time job-list/suspension,
  not inferred from markers, stdin or root exit. Legacy behavior is labeled.
- **Ownership: verified for documented returns and explicit registered transfers**;
  unobservable-return interruption outcomes are **BLOCKED**, possible quarantined
  leaks remain uncertain until process exit. Arbitrary asynchronous Python/OS
  failures between all state/close operations and in-kernel creation death are
  not universally certified. No unrelated value is closed to manufacture proof.
- **Receipts: termination uncertainty propagates**, suppresses synthetic success
  and classifies retained bytes as incomplete failure evidence. Storage/commit
  failure and abrupt death cannot fabricate a verified successful recording.
- No universal hard wall-clock deadline for OS/kernel/disk stalls, final evidence
  persistence or controller scheduling. No exhaustive race coverage, all-Windows/
  nested-policy compatibility, private NTFS ACL/path-race/power-loss guarantee,
  upstream cancellation or real MCP protocol/identity/completeness evidence.
- A post-response root crash racing stop cannot be atomically excluded. Silent
  upstream shortening remains undetectable. The eager shared-stdin startup stall's
  exact cause remains unverified; the bridge relies on tree teardown and bounded
  joins, not successful concurrent stdin consumers.
- Installed launcher/child/runtime and effective OpenCode/SDK/plugin provenance,
  sole-path filtered front end with retired bypass/stale bindings, independently
  authenticated review/withdrawal, trusted two-source UTC/expiry mapping and
  private race-resistant NTFS storage/headroom/durability/retention remain missing.
- **Oversized-response retention amendment and distinct-content versus physical-
  copy budget remain PENDING.** R5 §8 is not adopted. Gate B blockers unchanged.

**Gate A: NOT TECHNICALLY READY / BLOCKED.** Synthetic integration does not grant
live readiness or approval. The next smallest offline milestone is a narrow
ownership-interruption/recovery review: establish the exact supported interruption
model (including hidden native/CRT returns), whether a separately verified owning
broker/native transaction is needed to eliminate uncertain resources, and its
fixed-fixture death/failure evidence. Independently obtain the permitted installed
provenance packet and explicit retention decision. Any front-end/live-binding work
must follow a later readiness review with all other prerequisites established.
**STOP after R7. No Gate A execution approval is requested.**
