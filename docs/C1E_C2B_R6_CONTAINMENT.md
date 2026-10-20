# C1E-C2B-R6 — Windows pre-execution containment (offline synthetic only)

## 1. Decision and exact scope

**BLOCKED for supervisor adoption and Gate A. The isolated synthetic boundary is
implemented and its supported-host pre-resume contract is verified.** This is not
an unconditional controller-death certification or a live launcher. R4/R5 still
use their original fake-child-only entry point and post-Popen assignment; R6 does
not silently upgrade those historical guarantees.

- Baseline: `4661903d4f97cdb8d62adea89544741d3a00871c` (unchanged).
- Runtime: Python **3.12.7**, native Windows version tuple **10.0.26200**, platform
  2, empty service pack. Date label **2026-10-18** is the harness date, not verified
  UTC. No external time-source request or clock/service operation occurred.
- Single agent, no delegation/Swarm. Required R4/R5 reports, status §2.28,
  supervisor, evidence helper, complete supervisor tests and original fixture
  were read. Project `**/AGENTS.md` found none. An optional external skill-file
  read was refused by the harness; it was not retried or bypassed.
- Only fixed local Python test children/controllers ran. Temporary synthetic
  directories were removed by tests. No existing production evidence or ACL was
  modified. Pre-existing dirty/untracked work and milestone records were retained.
- No Roblox MCP call (including discovery/state), real `StudioMCP.exe`/`mcp.bat`
  execution, Luau, screenshot, Studio change, upload/save/publish, ComfyUI,
  authorization creation/consumption, dependency installation, MCP configuration
  change, Git staging/commit/push or live approval request occurred.

### R6 files

| File | Responsibility |
| --- | --- |
| `tool/c2b_windows_containment.py` | Isolated `SyntheticBoundary`, Win32 structures/signatures, creation-time job/handle lists, suspended root, checked resumption, explicit ownership/cleanup report |
| `tests/fixtures/c2b_containment_child.py` | Fixed marker, eager-descendant, inherited-pipe and natural-exit scenarios; one fixed internal descendant role |
| `tests/fixtures/c2b_containment_controller.py` | Disposable fixed-scenario controller for deterministic abrupt-death checkpoints and enclosing-job test |
| `tests/test_c2b_windows_containment.py` | 33 native Windows/fault-injection tests |
| This report; `status.md` | Contract, executed evidence, qualifications, blockers and handoff |

The existing supervisor, helper, original fake MCP fixture/tests, R4/R5 reports,
`opencode.json` and other existing implementation/status files were not edited.

## 2. Containment contract and API choice

R5 §4 is implemented as the **creation-time** branch only. The launch target is
the current trusted Python runtime's absolute `sys.executable`, with an internally
constructed quoted command line containing only `-I -S -u`, the absolute bundled
`tests/fixtures/c2b_containment_child.py`, and one of four fixed scenario words.
There is no executable/argv/environment/command-line parameter, shell, executable
search, batch launch, live flag, CLI or configuration entry. Python, repository
contents, OS and local fixture-directory integrity remain trust assumptions;
this is not a sandbox against rewriting them or modifying Python module state.

| Required contract | Mechanism and refusal rule |
| --- | --- |
| Suspended or atomic containment | Configure an unnamed `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` job first. `CreateProcessW` receives `STARTUPINFOEX`, `EXTENDED_STARTUPINFO_PRESENT` (`0x80000`), `CREATE_SUSPENDED` (`0x4`) and `PROC_THREAD_ATTRIBUTE_JOB_LIST` (`0x2000D`) containing that exact job. No breakaway flags/limits are enabled. |
| Membership before first application instruction | The OS applies job association during creation; the primary thread stays suspended. `IsProcessInJob` must return success **and true** for the owned process/job; owned process and thread must still be nonsignaled. Membership is checked again immediately before resumption. |
| No normal-launch fallback | Attribute sizing/initialization/update, creation, membership or nested-job incompatibility failure refuses. There is no production `AssignProcessToJobObject` call in the R6 creation path and no alternate spawn. |
| Failure before containment executes zero child instructions | Pre-resume failures never invoke `ResumeThread`; cleanup terminates the job/owned suspended root. Tests assert absent fixture markers. Unsupported capability is refusal, not a skipped capability labeled PASS. |
| Explicit root/thread ownership | Retain both `PROCESS_INFORMATION` handles immediately after successful native creation. Failure with nonzero output values cannot establish handle ownership and is explicitly uncertain; those values are never used to close/terminate an unrelated object. Check `ResumeThread` returns exactly **1**, then close the primary-thread handle. Any exception, `0`, `2`, or `0xFFFFFFFF` refuses and initiates cleanup. |
| Explicit pipe ownership | Exactly three child ends in `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` (`0x20002`), with `STARTF_USESTDHANDLES` and `bInheritHandles=TRUE`. Verify child inherit flags and clear/verify parent-end inherit flags; job/process/thread handles are noninheritable. Close controller copies of child ends after creation and before membership verification/resume. |
| Verify tree termination | Request `TerminateJobObject`, bounded-wait owned root, use exact-handle root termination only if needed, poll job active-process accounting to zero **before closing the job**, then check closes. A terminate request or a closed handle alone is not tree-exit evidence. |
| Uncertainty refuses success | `report.errors`, `phase='refused'`, `execution_may_have_started`, `uncertain`, and separate cleanup root/tree/handle/error fields retain the outcome. Never promote dispatch or a later empty job over a prior error. |

`InitializeProcThreadAttributeList`'s sizing failure must specifically be
`ERROR_INSUFFICIENT_BUFFER` (122) with a nonzero size. Attribute buffers **and the
arrays referenced by their values** remain alive through creation. The list is
deleted on success and failure. Job ownership is registered in a two-phase
`_CreationJob` wrapper before the reused R4 initializer can allocate; even an
initializer/configuration/close exception cannot hide the retained job handle.

`Popen(CREATE_SUSPENDED)` was rejected because its public interface does not retain
the required primary-thread handle. PID-based thread enumeration/resumption was
not implemented. Suspended-then-assigned creation was also rejected: it prevents
execution but does not close the unassigned-orphan controller-death window.
`STARTUPINFOEX` alone does not confer containment; the checked job-list creation
attribute is essential. Job-list support is documented for Windows 10/Server
2016 and newer; this run proves the actual combination on the host above, not a
compatibility result for every release, architecture or enclosing-job policy.

### Meaning of “before first instruction”

**Verified within the trusted Windows API contract on this host:** native creation
accepts both attributes and suspension; membership is observed while suspended;
the real `ResumeThread` previous count is 1; a 100 ms suspended interval produces
no marker, and checked resumption produces it. Eager creation then produces two
job members. Every tested failure before resumption leaves no marker.

The file named `first-instruction.marker` is explicitly an **earliest observable
Python fixture action after interpreter/bootstrap imports**, not instrumentation
of the native PE entry point. Absence of that file alone cannot prove no native
instruction ran. The pre-instruction ordering guarantee derives from suspended
creation plus creation-time membership, not from marker timing, stdin cooperation
or an assumed fast assignment. No uninstrumented native-entry probe is called a
PASS. Resume anomalies retain `execution_may_have_started=true` and uncertainty;
the artificial failures' absent markers do not certify arbitrary real anomalies.

## 3. Controller-death evidence and remaining qualification

The disposable controller is abruptly terminated using its exact Popen-owned
handle at these five deterministic checkpoints:

| Checkpoint | Actual observation |
| --- | --- |
| Immediately before `CreateProcessW` | No creation call occurs, no marker. |
| Native call returned, before the seam registers either returned handle | Observer duplicates the exact returned root handle from the still-live controller, then kills that controller; root becomes signaled, no marker. This is the important creation/ownership-return gap. |
| Handles registered, before child-end closure/membership query | Root exit confirmed through the duplicated handle after controller death, no marker. |
| Membership verified, still suspended | Same root-exit confirmation, no marker. |
| Resumed, eager descendant has actually executed | Root and descendant exit independently confirmed through duplicated **owned handles**, not PID lookup. The descendant handle is duplicated from the exact root-owned Popen handle. |

The observer never duplicates/retains the Job Object handle: doing so would keep
the job alive and invalidate a last-handle-close death experiment. Observer root
rights are only `SYNCHRONIZE | PROCESS_DUP_HANDLE`; descendant observer rights are
only `SYNCHRONIZE`. All observer handles are explicitly closed. No PID-reuse-based
lookup, wait, cleanup or unrelated process termination exists.

**The post-creation/pre-assignment window is absent in this seam:** assignment is
part of creation, and both the ownership-return gap and later checkpoints actually
kill the suspended/eager tree on controller death. This is stronger than R5's
suspended-then-assigned prototype design.

**Still unverified:** deterministic abrupt controller death while execution is
inside the kernel implementation of `CreateProcessW`, OS/kernel failure, arbitrary
scheduler suspension and cross-version failure atomicity. The return-gap test is
not relabeled an in-kernel interruption test. That behavior relies on the supported
API contract; no empirical unconditional death-window certification is issued.
The existing R4/R5 runner has not adopted this seam, so its original Popen/assignment
window and real-launch blocker remain. There is no claim that a controller-death
window is solved for the current recorder or any installed Roblox launcher.

## 4. Handles, cleanup, inheritance and nested jobs

- Root and thread handles are returned by `CreateProcessW`; the seam never opens
  arbitrary processes, requests debug privileges, changes a DACL or expands rights
  on an existing process. Native default creation handles are retained, not claimed
  to be separately least-privilege duplicates. Test observer duplication requests
  only the specific rights described above.
- Parent stdin-write/stdout-read/stderr-read ends and the job are noninheritable.
  Child stdin-read/stdout-write/stderr-write are the complete inherited list. Tests
  verify all three child standard handles are pipes, actual stdin delivery, separate
  stdout/stderr data, and exclusion of an otherwise-inheritable unrelated event.
  That event remains valid in its parent after boundary cleanup.
- Partial setup paths retain all documented owned handles. Cleanup tries every
  remaining close even after an earlier failure. Native handle invalidity after
  ordinary close is independently checked with `GetHandleInformation` error 6.
  A failed close retains failure bookkeeping; it is not retried using a guessed
  or recycled handle. Tests that inject failure *after actually closing* discard
  only their synthetic stale bookkeeping, never close those values again.
- Failed `CreateProcessW` output fields have no documented valid-handle ownership
  contract. Nonzero failure outputs therefore set
  `failed_creation_handles_unverified=true`, leave root/handle certainty false,
  stop/verify the known job, and refuse. A regression fills those fields with an
  unrelated live event and verifies it remains valid. Another injector actually
  creates a suspended child before reporting failure: job termination empties the
  tree, the injector's independently owned root handle confirms exit, and the
  injector closes its own known handles. The boundary never assumes ownership
  from that failed result or promotes it to clean partial-creation success.
- Cleanup waits up to 1 second for root job termination, then up to another second
  after exact-root fallback if necessary; job accounting has a separate 1 second
  polling budget. No universal physical deadline for OS calls is claimed.
- An eager child is verified at two active job processes. In the inherited-pipe
  case the root exits first, the descendant holds stdout open, the job still has
  one member, then termination produces zero members and actual pipe EOF. Root
  exit alone is not mistaken for complete teardown.
- A disposable controller inside a UI-restricted outer job **supports** the normal
  R6 creation list on this host. An early assumption that UI restrictions alone
  would force refusal was disproved. No blanket incompatible-job rule is inferred.
- A separate test establishes an actual two-job hierarchy using a suspended seed,
  sets the enclosing active-process limit to 1, then attempts another creation
  into that enclosing job plus the candidate's own job. The actual native
  `CreateProcessW` result is checked to be failure, with nonzero last error; the
  original seed remains the sole member, no marker exists, candidate cleanup is
  confirmed and seed cleanup empties the outer job. This is actual nested-limit
  incompatibility evidence, not just a mocked membership check.
- Shutdown is serialized with creation/resumption by an `RLock`. A real Timer
  watchdog shutdown and ordinary shutdown return the same verified result; close
  before create or before resume prevents dispatch. This does **not** bound an
  already-stuck creation call or prove the recorder's blocked-writer integration.

Job Objects here are owned-tree lifecycle controls, not a security sandbox against
trusted same-user code delegating work to existing external services. The brief
inheritable child-pipe interval also does not certify arbitrary noncooperating
concurrent launchers elsewhere in a host process; sole-path integration remains
unverified.

## 5. Failure evidence matrix

All named tests are in `tests/test_c2b_windows_containment.py`; groupings below
describe executed assertions, not additional test counts.

| Failure / interaction | Execution and cleanup evidence |
| --- | --- |
| Job setup before allocation; injected failure after actual job allocation | No creation/marker; registered job ownership survives exception, job/handles close. |
| Second pipe fails; attribute sizing fails; job-list update fails | No creation/marker, all earlier owned ends/list/job cleaned; no alternate spawn. |
| Creation/assignment result fails | One creation attempt only, no marker, known job/pipes close. Nonzero failure outputs are unverified, not assumed owned. |
| Injected native success followed by partial-return failure; unrelated values in failed outputs | Known job empties without marker, but boundary root/handle certainty stays false. Injector independently verifies/closes its actual native-success handles. Unrelated live event is never closed/terminated. |
| Membership query fails during setup or immediately before resume | No resume/marker, owned root/job empty and handles closed. |
| Actual nested active-limit refusal | Native creation fails, no marker; pre-existing **owned seed** remains unaffected until its separate cleanup. |
| `ResumeThread` returns `0xFFFFFFFF`, 0 or 2, or raises (injected without calling native resume) | No marker in injected cases, actual suspended root killed and handles closed. Report refuses/retains uncertainty; zero-instruction behavior for an arbitrary unexpected real resume result remains unverified. |
| Native resume succeeds but primary-thread close fails | Membership already true, resume count 1, execution may have started **contained**. No zero-execution claim. Refusal/uncertainty and failed handle-close receipt retained; test restores API and closes the exact retained handle. |
| Child is terminated during setup or after create/before resume | Actual suspended root exits, setup/resume refuses, no marker. Natural exit after authorized resume is separately verified. |
| Job termination error | Actual exact-root fallback stops the suspended root; empty tree confirmed but error/uncertainty retained. No marker. |
| Job accounting unavailable | Root exit/handle closure confirmed; tree verification remains false/uncertain even though kill-on-close is requested. No marker. |
| Handle close reports failure | Tree empty, failure/handle uncertainty retained; no marker. Test's real handle closes prevent an artificial resource leak. |
| Eager/inherited-pipe descendants, controller death, watchdog/close races | Native tree accounting, actual EOF or exact owned root/descendant wait handles as described in §§3–4. Any child instructions in resumed cases are after verified containment. |

Creation and cleanup reports are in-memory synthetic diagnostics. These helpers
do not create a production evidence receipt, grant authorization or assert MCP
compatibility. A true `create()` means contained/suspended creation, and a true
`resume()` means checked dispatch, **not final session success**. Review errors,
uncertainty and all cleanup fields together. On abrupt controller death, the
independent test observer supplies the evidence because the dead controller cannot
write a final report.

## 6. Integration boundary and remaining Gate A prerequisites

**Keep isolated.** The R6 fixed fixture is a containment diagnostic, not an MCP
server. There is no verified adapter from these explicitly owned native handles
to R4's Popen/file-descriptor reader/writer/wait interface, nor end-to-end R6
evidence-receipt propagation, blocked-write cancellation/join and watchdog teardown
coverage. In particular, the Timer test does not certify a watchdog waiting behind
the creation lock. Converting native handles to CRT descriptors transfers ownership
and needs a separately tested exact-once closure contract; it is not an innocuous
drop-in substitution. No untested integration is enabled just because isolated
creation tests pass.

R4/R5 behavior is preserved, including exact discovery → recorded review pause →
conditional state, typed JSON-RPC correlation, raw bytes before parsing, output
bounds, independent per-request watchdog and cleanup uncertainty. Its existing
37 tests pass, but its pre-execution limitation remains explicit. No real launch
argument, automatic startup, replacement/duplicate registration or OpenCode edit
has been introduced.

Gate A still needs R5 §§4–9's permitted installed launcher/child/runtime and
OpenCode/SDK/plugin/effective-configuration provenance, real topology containment,
sole-path front end with retired bypass/stale routes, genuine authenticated human
pause/withdrawal checks, trusted two-source UTC intervals/expiry mapping, and
private race-resistant NTFS storage/access/durability/headroom/retention evidence.
The **oversized-failure-prefix policy and distinct-content versus physical-copy
budget remain explicitly PENDING**, unless the operator separately approves them.
Synthetic tests do not adopt the R5 §8 proposal. Gate B blockers are unchanged.

**Next smallest offline milestone:** test a fixed-fixture-only native-handle/CRT
ownership adapter and evidence propagation against the existing synthetic MCP
runner, including blocked stdin, inherited-pipe EOF, watchdog/close races and
creation/death qualification. Resolve the in-kernel/cross-version evidence limit
before claiming unconditional death recovery. Keep arbitrary/live argv absent;
obtain the provenance packet and policy decisions independently. A later offline
readiness review must establish all prerequisites before any Gate A approval
could be considered. **No live approval is requested. STOP after R6.**

## 7. Exact executed verification

Authoritative final code verification, all exit 0:

| Command | Result |
| --- | --- |
| `python -m unittest tests.test_c2b_windows_containment -v` | **33 run, 33 passed, 0 skips, 3.154s**. Native Windows capability tests actually ran. |
| `python -m unittest tests.test_c2b_recording_supervisor -v` | **37 run, 37 passed, 0 skips, 9.877s**. |
| `python -m unittest discover -s tests -p "test_*.py"` | **300 run, 299 passed, 1 skipped, 34.726s**. Existing `test_asset_registry.RegistryTests.test_symlink_escape`, `symlinks unavailable`. No new skips. |
| `python tool/registry.py validate` | **PASS: 0 unique assets, 0 events**. |
| `python tool/validate_art.py` | **PASS: 2 metaschemas, 5 presets, 3 positive request fixtures, 36 negative request fixtures; no files written**. |
| `python -m compileall -q tool/c2b_windows_containment.py tests/test_c2b_windows_containment.py tests/fixtures/c2b_containment_child.py tests/fixtures/c2b_containment_controller.py` | **PASS**, no compiler output. `Test-Path` for all three parent directories returned True first. |
| `git diff --check` | **PASS**, exit 0; existing LF→CRLF warnings only. Rechecked after final documentation updates. |
| `git diff --no-index --check -- /dev/null <path>` individually for the four new Python files and this report | **PASS**, each exit 0; LF→CRLF warnings only. Ordinary tracked diff does not cover these new files. |

Intermediate development runs (superseded, not hidden): 25 tests initially had
13 failures in 2.053s; the root-kill race and premature EOF assertion were corrected.
An intermediate 25-test run passed in 2.978s, but its incompatible-job injection
had not retained the attribute array through creation, so that apparent refusal
was **not valid native incompatibility evidence**. After fixing value lifetime,
27 tests had 1 failure in 3.138s, correctly disproving the UI-restriction assumption.
The replacement nested-limit test first failed in 0.016s because kill-on-close
extended limits cannot be round-tripped through basic-limit setting; using the
extended structure corrected it (1 test passed in 0.019s). A subsequent 31-test
run passed in 3.282s; a 298-test suite passed in 36.632s with the same one existing
skip. Inspection added the close-before-create guard/regression and native
creation-result assertion: 32 tests passed in 3.211s, and 299 suite tests ran in
34.549s with that same skip. Final ownership review rejected treating failed
creation's nonzero output fields as documented owned handles; the added unrelated
handle regression and revised uncertainty test produce the authoritative 33/300
counts above. Nonzero failed-output ownership remains explicitly unverified.

No unresolved final test failure exists. In-kernel death interruption, universal
cross-version behavior, recorder integration and live prerequisites are **unverified
or BLOCKED**, not skipped Windows tests counted as PASS.
