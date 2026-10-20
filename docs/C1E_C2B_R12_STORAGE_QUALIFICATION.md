# C1E-C2B-R12 — Offline durable replay and evidence storage qualification

## T0 — Pre-implementation policy/design preflight

Review label: 2026-10-18 (harness date, not authenticated UTC). Single agent;
no delegation/Swarm. Explicit R12 authorization supersedes the historical R11
STOP only for disposable offline engineering. Gate A BLOCKED / NOT TECHNICALLY
READY; D1–D6 PENDING; Gate B separately BLOCKED. R10 remains QUALIFIED fake-only;
R11 remains the completed fake-only slice. Phase 1 Task 1.1 is not complete.

Read status §§2.31–2.34/blockers, R11 exact contracts/code/fakes/tests, R8 D2/D5,
relevant R7/R9/R10 reports, evidence/review code, README, implementation handoff
and `.swarm/plan.md`. Workspace `**/AGENTS.md` search found none. No installed
MCP/source acquisition research repeated. HEAD `4661903d4f97cdb8d62adea89544741d3a00871c`.
Entry Git inventory: modified `docs/IMPLEMENTATION_STATUS.md`, `opencode.json`,
`status.md`, plus existing untracked reports/modules/tests/source evidence and
unrelated artifacts. These are existing work, not disposable cleanup targets.

| Topic | Adopted requirement / existing boundary | Pending candidate policy / operator decision | Safe disposable mechanism; independently provisioned prerequisite |
| --- | --- | --- | --- |
| Originals / prefixes | Exact intended bytes and verified checkpoint originals; incomplete evidence never success | D2 accepted-full versus bounded incomplete oversized-prefix amendment; R8 numbers all fixture candidates | New-only binary records; explicitly labeled partial category; no live collector/prefix-policy change |
| Content / copies / categories | Account every retained copy and partial; bounded writes | Distinct-content versus total-copy interpretation, per-frame/category values | Injected per-record/category limits; duplicates charged again; no implicit deduplication |
| Session / campaign | Fail closed when accounting/capacity uncertain | Aggregate bytes, session count, concurrency and backup budgets | Serialized logical reservation ledger; per-session finalization headroom; backups/NTFS allocation outside ledger remain unimplemented |
| Physical / metadata | Logical bytes are not allocated bytes, filesystem quotas or reservations | NTFS volume/quota, clusters, directory/backup overhead and numeric headroom | Charge ledger metadata and conservative seal allowance; physical reservation NOT implemented; no disk-free sampling proof |
| Full budget | Refuse; never delete/rotate to regain authority | Exact approved budgets | Pre-write refusal, retained interrupted records, no automatic cleanup/retry |
| Namespace / ACL | Trusted parent/ancestors; effective inherited/explicit ACLs; controlled writers/readers | D5 exact NTFS parent, writer/reader/operator/recovery principals and exclusive-writer versus handle-relative model | Read-only local NTFS/reparse/regular-file checks in disposable namespace only; ACL effectiveness, principal separation and namespace-race protection require independent provisioning/verification |
| One-use | Atomic one-winner `(issuer, approval_id)` across bindings/sessions/processes; permanently spent before bytes | Supported fault/durability model, recovery ownership | Exclusive directory guard + new-only append ledger, fsync/readback; crash/uncertainty retains guard and blocks whole campaign; no leases/reset |
| Durability / tamper | Re-read/digest-check; preserve incomplete attempts; no reconstructed success | Device/power-loss/backup/restore guarantees and recovery owner | Actual process-exit tests; no universal power-loss, hostile writer, complete-ledger deletion or rollback resistance |
| Confidentiality / sharing | Private originals; separately redacted approved sharing | Readers, recipients, redaction/backup location/access | No sharing/export facility; disposable synthetic bytes only; hashes/path labels are not privacy proof |
| Retention | At least 30 days AND until review completion, whichever later; explicit disposal | Review-completion authority, recovery/retention owner and backup policy | Pure eligibility arithmetic and no deletion API; no trusted-time acquisition or actual 30-day enforcement claim |

### Chosen bounded design (recorded before implementation)

Standard library only. Standalone candidate, no live dispatch/transport integration.
Explicit fixture policy and disposable namespace required, no production mode.
One campaign guard is acquired by atomic mkdir; contenders refuse rather than
queue. Successful checked transactions remove only their own empty guard; any
uncertain mutated transaction or dead process leaves it indefinitely quarantined.
Each record has new-only reservation, exact binary original and readback seal,
chained to the previous seal. Missing/incomplete/corrupt records refuse. Recovery
is inspection only, never completion, reset, restore-to-unspent or dispatch.
Filesystem object identity checks detect ordinary replacement, not malicious
same-user rewriting. Trusted namespace, ACLs, anti-rollback and physical reservation
are essential production blockers, not assumed guarantees.

## Entry preservation inventory

`git hash-object -- <ordered paths>` executed before the first repository edit.
These are Git object IDs (local consistency, not signatures/security attestations).
The R11 preservation set extends R11's own 18-file baseline with all four R11 files.

| Protected path | Entry Git object ID |
| --- | --- |
| `opencode.json` | `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd` |
| `.swarm/plan.md` | `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2` |
| `tool/c2b_evidence.py` | `cac86a3ca6875a1ec5f1afebb5d4f8f2ed125adc` |
| `tool/c2b_windows_containment.py` | `9e25319b10d2605dbb86412014a3ac0d12c7bfd7` |
| `tool/c2b_native_recorder.py` | `8edf90a11785ca998d9eea3b9ae8aea07c327291` |
| `tool/c2b_recording_supervisor.py` | `7dcfdc0c2b587bd945610df0c4b5371e10cdd649` |
| `tool/c2b_restricted_frontend.py` | `f43380ca63c90837245991930819cb1f8cb708bc` |
| `tool/c2b_synthetic_review.py` | `de64f25655122d64ab374efdc0a8364da04319e4` |
| `tests/test_c2b_evidence.py` | `4c3100ea879046e6582fb32ffeab31c925e31a96` |
| `tests/test_c2b_windows_containment.py` | `9ac9687319ab8034d76f47c76dfba90323355e49` |
| `tests/test_c2b_native_recorder.py` | `34247d343a83f7a318ed027f4c77ac2ddfaf9669` |
| `tests/test_c2b_recording_supervisor.py` | `ec1a47ec3490101e93a4c7ca7bc586b76a6260af` |
| `tests/test_c2b_restricted_frontend.py` | `b9f154fd344a678152ea4135257a4b888e2eafa3` |
| `tests/test_c2b_r10_compatibility.py` | `bb89dcb4e60fab954bd0d55f1c90b8321a976bbf` |
| `docs/C1E_C2B_R7_RECORDER_INTEGRATION.md` | `3425b1be3b1d2f2fb6aa07eb548017b5d7c97fdf` |
| `docs/C1E_C2B_R8_GATE_A_DECISIONS.md` | `93b9ab2ba8365f604ca32d86f2f633f999ffd738` |
| `docs/C1E_C2B_R9_FRONTEND_CONFORMANCE.md` | `811617789911b21b01f5c49a6051ecfde951719c` |
| `docs/C1E_C2B_R10_OPENCODE_COMPATIBILITY.md` | `a0797bb5a34151601e86bf7cb668d58afc821ac2` |
| `tool/c2b_authorization_gate.py` | `e2497307c3d52d91d385dc5a21e7afaff9ea1dcb` |
| `tests/fixtures/c2b_r11_fakes.py` | `b1f395445373224ee3f38da2f2579ff32a115436` |
| `tests/test_c2b_authorization_gate.py` | `21d0dbb4b01f21d79fd8579480d1bfebd4d2b1af` |
| `docs/C1E_C2B_R11_AUTHORIZATION_GATE.md` | `16184b194c87e34ebe5fa4cb5407b33c6988c789` |

## 1. Result, exact files and trust boundary

**QUALIFIED disposable offline candidate delivered; protected production storage
qualification is BLOCKED.** R12 demonstrates replay persistence through real
process exit/restart and cross-process exclusivity on this host. It does not close
D2/D5 or authorize a real protected namespace. No production authority exists here.

| Added file | Responsibility |
| --- | --- |
| `tool/c2b_durable_storage.py` | Small new-only ledger, one-use consumption, R11 evidence adapter, logical reservation checks and inspection-only recovery/retention predicate |
| `tests/fixtures/c2b_r12_worker.py` | Fixed bounded `-I -S -u` synthetic workers and abrupt self-exit/held-writer seams |
| `tests/test_c2b_durable_storage.py` | 42 focused cases, process restart/contention/crash, fault injection and accounting/security-limit assertions |
| This report | Preflight, entry hashes, exact qualification evidence and STOP |

Modified only `status.md` (current summary, additive §2.35, blockers/evidence/next
handoff) and `docs/IMPLEMENTATION_STATUS.md` (addendum). No dependency added or
installed. R7–R11 source/tests/reports, original evidence, plan and `opencode.json`
are preserved. Historical completed entries remain historical, not new permission.

The ledger is **not** wired to R9's frontend, R7's writer or any live route. Tests
inject it into R11's unchanged **inert memory sink** only. Approval and time remain
the explicit unauthenticated R11 fakes. No actual approval service, trusted-time
service, Roblox, ComfyUI, vendor binary or installed MCP client is invoked.

### Implemented mechanisms versus conditional requirements

- Implemented: exclusive campaign guard; append-only reserve/data/seal files;
  exact issuer/ID/binding/attempt consumption; readback/digest checks; original-byte
  preservation; bounded parser/writes; cross-process refusal; logical accounting;
  conservative no-repair recovery and advisory retention arithmetic.
- Validations only: local fixed NTFS volume, point-in-time non-reparse ancestors,
  regular single-link files, file identity/readback consistency, exact injected
  namespace token/policy and prerequisite digests. A token or digest is **not**
  trusted ownership, approval, namespace security or authenticated UTC.
- Required independent infrastructure: protected code/runtime/ancestors, actual
  principals/effective ACLs and negative access tests, no hostile namespace writer
  (or safe handle-relative access), physical quotas/reservations, confidential
  retention/backups, recovery ownership, fault/durability acceptance and anti-rollback
  support if required. None is supplied or certified by these tests.

## 2. Storage/transaction state machine

`NEW EMPTY DISPOSABLE ROOT → FORMAT.json → IDLE → WRITER guard acquired → audited
ledger → reservation → exact binary data → seal → full audit/readback → acknowledgment
→ owned empty guard removed → IDLE`.

`WRITER` is an exclusive mkdir, not a lease or PID lock. Contenders refuse immediately
with `busy_or_quarantined_campaign`; no queue, retry or stale-owner removal. A clean
pre-write capacity/duplicate validation refusal can remove its own guard. Any
uncertain mutation, corrupt audit or dead writer preserves the guard and blocks
**the entire campaign indefinitely**, sacrificing availability. There is no reset,
release-spent, resume, recovery-complete or restore-to-unspent API. Removing the
guard manually is outside this qualification and is not a recommended recovery.

Record names are monotonic `00000000.reserve`, `.bin`, `.seal`, etc. Reservation
records bind category/identity/session, intended size/digest, previous seal digest
and logical charge. Writes exclusively create, loop over positive checked short
writes, flush/fsync, close and reread exact bytes. Seal binds the descriptor/data
digests and payload's NTFS-exposed device/file identity. Full audit checks bounded
canonical JSON (including duplicate-key refusal), sequence, new-only identities,
file inventory, all bytes/digests/seals, replacement identities and capacity.
Unknown extra files and incomplete transactions refuse rather than being ignored.

Consumption identity is SHA-256 of canonical `(issuer, approval_id)`, independent
of action/session/target. Stored bytes include complete immutable binding, binding
digest and attempt. Under the guard an existing key cannot append another spent
record, even if binding/session changes. The exact `Consumption(key, binding_digest,
attempt)` acknowledgment follows full reread. Crash/uncertain acknowledgment never
makes the key unspent. No outcome is necessary to preserve one-use state.

Evidence `prepare` verifies admitted same-session checkpoint/policy/prerequisite
originals, then writes a distinct exact action original and candidate intent.
`verify` reaudits all records and rechecks exact binding/action/checkpoint/policy/
prerequisites and intent digest. `record` admits only R11's explicit fake-only
decision shapes; candidate requires the exact spent intent, outcome requires its
distinct candidate digest. Denial is terminal for later candidate/outcome. A denial
may follow a persisted outcome when its acknowledgment was lost, preserving that
uncertainty. New-only decision identities refuse duplicates. Public generic append
admits only synthetic checkpoint/prerequisite/explicit incomplete-partial categories;
transaction categories require the typed adapter (private Python methods are not
a same-user security boundary).

**Candidate never means dispatch permission or final success.** An outcome records
the inert test transition only. Recovery never reconstructs success from either.
R11 still requires final authorization/withdrawal/time/evidence revalidation and
returns `completed=false` on uncertain outcome acknowledgment, even when factual
simulated bytes were already appended. Storage failure can prevent a denial receipt;
no finalization reservation promises writing through a broken/quarantined store.

`inspect_recovery` is read-only and always returns `trusted_success=false` and
`reusable_authority=false`. It can report verified records and logical reservation
charges, or `accounting=unknown_preserve_all_files`. With an active writer its
inventory is only a point-in-time sample, never trusted completion. An incomplete
original or reservation remains present; no fabricated seal, outcome or receipt.

## 3. Accounting, retention and Windows guarantees/limitations

All policy numbers are required injected `Limits`, persisted in `FORMAT.json` and
matched on open. There are no production defaults. The main fixture uses:
16,384 data bytes/record; 300,000 charged bytes per category; 500,000/session;
1,500,000/campaign; 3 sessions; 200 records; 12,000/session finalization headroom.
Smaller boundary fixtures intentionally use other values. These are invented
test values, **not** approval of R8's proposed limits or oversized-prefix amendment.

For each record, charge = exact intended payload length + exact reservation-file
length + 1,024-byte maximum seal allowance. Header length is also charged to the
campaign. The 4,096-byte descriptor and 1,024-byte seal maxima are format bounds,
not selected production budgets. Charge is a **conservative logical reservation**,
not a claim that every seal uses 1,024 bytes. Duplicate content under new identities
charges again; new-only duplicate identity refuses. Final categories are denial,
outcome and explicit incomplete partial. For each admitted session, retain
`max(0, finalization_allowance - final_category_charges)` in both its session limit
and campaign total, so one session cannot consume another's reserve. Capacity is
checked inside the guard before each new reservation. A prepare interrupted between
original and intent remains quarantined, not retroactively rolled back.

Complete stores are audited from disk, not in-memory counters. Interrupted stores
retain partial files/reservations and block all new writes; unknown accounting is
not counted as zero/free capacity. This candidate does not create backups, arbitrary
temporary staging copies or exports outside its ledger. Future backups, redacted
copies and extra metadata need separately approved budgets/retention and adapters.
Generic per-record/category limits are implemented; actual live frame/prefix/category
mapping is **not integrated** and existing R7 caps/semantics remain unchanged.

**Physical reservation/allocation/quotas are UNIMPLEMENTED.** Directory entries,
NTFS metadata, cluster allocation, compression/sparse behavior, filesystem overhead,
backup allocation and reserved device/quota capacity are not measured or enforced.
No disk-free sample is treated as reservation. Simulated ENOSPC/EDQUOT proves refusal
paths only, not native NTFS quota or real device-full behavior.

Retention advisory predicate requires explicit minimum >=30 days AND explicit
review completion, refusing invalid/backward inputs. No deletion API, trusted clock,
authenticated review-completion source, actual 30-day retention enforcement, legal
hold service or approved backup/disposal/recovery owner exists. Test fixtures are
synthetic and disposable under R12 authorization; their cleanup is not disposal of
real protected originals. Confidential sharing/redaction is not implemented.

### Supported host/fault model

Executed on Python **3.12.7 AMD64 (Anaconda packaged)**, Windows version tuple
**10.0.26200**, `Windows-11-10.0.26200-SP0`. Read-only `GetDriveTypeW` must report
fixed local drive, `GetVolumeInformationW` must report NTFS. UNC/extended-device,
relative, alternate-stream, dot-dot and trailing-dot/space paths, unsupported object
types, reparse ancestors and hard-linked payload leaves refuse. Root must have an
explicit disposable `c2b-r12-*` name and matching namespace token/policy; neither
condition authenticates an owner. Missing stores are never automatically initialized.

Atomic mkdir/exclusive file creation, file fsync/readback and stable ordinary
payload file identity are relied upon under the local Windows/NTFS API contract.
Actual process restart/exclusion, abrupt exit and actual hard-link/replacement
experiments executed successfully on this host. No universal host/version/driver,
device-cache or scheduling certification follows.

### Explicitly unsupported / independently NOT VERIFIED

- ACL effectiveness/inheritance/group access; writer/reader/operator/recovery identity
  separation; confidentiality against another principal or hostile same-user code.
- Exclusively controlled trusted ancestors; safe handle-relative no-follow opens;
  resistance to racing junction/symlink/namespace replacement. Point-in-time lstat
  and read/fstat comparisons are **not** a solution to these races. Native adversarial
  junction tests and negative access from another principal were **NOT VERIFIED**;
  reparse refusal was simulated, not falsely reported as a native junction attack.
- Authenticated integrity, protected append-only authority, external freshness/tail
  anchoring, rollback/restore resistance. A writer able to replace/rehash the entire
  ledger, delete a complete tail, restore old files or delete/reinitialize the entire
  namespace can defeat these local consistency checks. Production is **BLOCKED**
  until the required threat model and protections are independently established.
- Directory metadata durability through power loss; device/volume failure, reboot,
  filesystem rollback, crash exactly inside kernel operations or universal power-cut
  persistence. No power cut/reboot was induced. File fsync/readback is not proof that
  directory creates/guard/spent files survive those faults. Such a loss could reopen
  authority unless independently prevented; **AC-1 is process-restart only**.
- Approved backups/restore: copied files may have different identities and refuse.
  No recovery owner, restore procedure or permission to restore unspent state exists.
- Hard disk/OS deadlines or a guarantee of successful finalization after failure.
  Storage APIs are synchronous; all detected uncertainty still refuses.

## 4. Process ownership and failure-injection evidence

Before tests, `Test-Path` verified the explicitly authorized existing parent
`C:\Users\juara\AppData\Local\Temp\opencode` and workspace `tool`/`tests` parents.
Compilation's `docs/evidence/r10-source` parent was also verified. Every fixture is
a unique `TemporaryDirectory(prefix='c2b-r12-', dir=parent)`; workers independently
require it to be a direct child of that parent and validate header/policy/namespace.
Cleanup verifies parent/name/plain namespace/token before removing only its exact
synthetic directory. Existing repository/unrelated temporary files are not cleaned.

Workers execute only current Python with `-I -S -u` and the exact bundled fixture.
Allowed operations are enumerated; no executable/command/environment/service input.
Parents retain exact Popen ownership, use bounded pipe readiness/communicate and
terminate only a still-running owned worker on cleanup/error. Crashes use worker
`os._exit(73/74)`, no unrelated PID search/termination. READY/GO and HELD/CONTINUE
pipe barriers coordinate contention deterministically; no broad sleeps or guessed
race timing. Process-restart tests use distinct new Popen instances after exit.

| Required case | Evidence executed / fault classification |
| --- | --- |
| Persistent consumption/restart | First independent process OK; exits; new process DENIED; one intact spent record. Actual OS processes, not surviving memory fake |
| Two-process race | Both READY before GO; outputs exactly one OK and one DENIED; one spent record, both exit 0. Actual independent processes |
| Cross-action/session/target reuse | After consumption, new workers with same issuer/ID but changed action, session or target all DENIED; issuer dimension separately tested |
| Spent before outcome/ack crash | Abrupt self-exit 73 after verified spent seal but before acknowledgment; no outcome; guard retained; new worker DENIED. Actual process exit |
| Incomplete reservation crash | Exit 73 after reservation fsync/readback, no data/seal; guard retained; recovery accounting unknown. Actual process exit |
| Incomplete data crash | Worker writes/fsyncs seven payload bytes then exits 74; seven-byte file/no seal preserved; new process DENIED. Actual partial file + process exit, not a power cut |
| Missing/wrong acknowledgments | Actual spent record followed by injected missing/wrong exact attempt acknowledgment; unchanged R11 returns zero bytes and no completion; replay refused. Simulated lost/invalid response |
| Corrupt/missing/truncated/malformed/extra | Actual synthetic file changes/unlink, truncated bytes, malformed seal, duplicate JSON keys and extra file; audit refuses and preserves ambiguity. Controlled filesystem tampering |
| Checkpoint/intent/replacement | Changed checkpoint; missing intent; changed action; byte-identical payload replaced with new file identity; all refuse. Actual disposable file operations |
| Storage failure before/after candidate | Injected ENOSPC before candidate or lost acknowledgment after real persisted candidate; zero simulated dispatch bytes; spent retained. Simulated faults |
| Outcome uncertainty | Actual inert bytes and persisted outcome followed by missing digest ack; completed=false, factual bytes retained, recovery never success. Simulated acknowledgment loss |
| Quota/partial/headroom | Explicit limits, record +1, exact category equality, duplicates, session/campaign/session-count/record-count refusal; finalization cannot steal other session reserve; simulated EDQUOT after original leaves original/quarantine |
| Checked write/flush/readback | Real short writes complete exact CRLF/space bytes; injected zero write, ENOSPC partial file, fsync error/readback mismatch all refuse. Native real disk-full/quota NOT VERIFIED |
| Concurrent evidence | Independent writer/reader race; deterministic held writer excludes both another writer and reader; release yields one valid partial record; fresh process verifies. Actual processes/pipes |
| Unsupported namespaces | Relative/UNC/ADS/root/policy/token refusal; simulated reparse/non-NTFS failure; actual NTFS hard link refused. Native hostile junction/ACL tests NOT VERIFIED |
| Conservative recovery/retention | Candidate has no outcome; inspection always false success/reusable authority; 30-day exact boundary, earlier/late review hold and invalid minimum tested. Arithmetic only, no trusted retention enforcement |

## 5. Exact verification commands and results

All results are **agent-run engineering verification**, not independent third-party
or operator/security acceptance. Final commands used the unchanged R7–R11 tests.

| Command/check | Actual result |
| --- | --- |
| `python -m unittest tests.test_c2b_durable_storage -v` (final) | **42 passed, 0 skips, 4.998s** |
| `python -m unittest tests.test_c2b_durable_storage tests.test_c2b_authorization_gate tests.test_c2b_r10_compatibility tests.test_c2b_restricted_frontend tests.test_c2b_native_recorder tests.test_c2b_windows_containment tests.test_c2b_recording_supervisor tests.test_c2b_evidence` | **298 passed, 0 skips, 30.692s** = 42 R12 + unchanged 256 R11/boundary/profile tests |
| `python -m unittest discover -s tests -p "test_*.py"` | **503 run, 502 passed, 1 existing skip, 45.464s** = R11 baseline 461 + 42 R12; all R12/native Windows cases ran |
| `python tool/validate_art.py` | **PASS**, 2 metaschemas, 5 presets, 3 positive / 36 negative fixtures; no files written |
| `python tool/registry.py validate` | **PASS**, 0 unique assets, 0 events |
| `python -m compileall -q tool tests docs/evidence/r10-source/acquire.py` | **PASS**, no diagnostics; no vendor code executed |
| `git diff --check` | Initial post-code and final documentation **PASS**, no whitespace errors; LF→CRLF advisories only |
| Individual `git diff --no-index --check -- /dev/null <path>` for the three new Python files | **PASS**, no whitespace errors; LF→CRLF advisories only; wrapper rejects native status >1 and maps difference-from-empty status 1 to 0 |
| Post-test ordered `git hash-object -- <22 protected paths>` | **22/22 identical** to entry inventory above |

The sole full-suite skip remains `test_asset_registry.RegistryTests.test_symlink_escape`
(`symlinks unavailable`), as reported by the R11 baseline. R12 adds no skip or relaxed
assertion. No Luau/Rojo file changed; relevant existing R11 Python compilation/art/
registry validation commands ran. No build/serve/publish/Studio command was needed.

Development history: initial 32-case run in 3.756s had 31 pass/one fixture-helper
failure: `test_fsync_and_readback_failures_are_uncertain` called a helper that wrongly
asserted the primary fixture was empty after intentionally retaining a failed write.
Helper corrected to create/verify a distinct owned disposable fixture, preserving
the failed original. Expanded 38-case run passed in 4.590s. Four final cases added
record-count/exact-category, terminal denial, missing-intent/changed-action and
no-production-mode checks; final 42/298/503 runs above all passed. The initial
missing/wrong-ack loop was split to exercise each acknowledgment after a real spend;
no legacy security assertion changed or failure hidden.

## 6. Preservation and final review

Protected 22-file post-test object IDs match the entry table **exactly, 22/22**.
This includes all four R11 files and the original 18 R7–R10/config/plan files.
R10's saved-source hash/provenance assertions also ran in the unchanged focused/full
suites; source acquisition was not repeated and those original bytes were not edited.
Current project config was read as data: `roblox_studio.enabled=false` and
`comfyui.enabled=false`. Effective loaded config/hooks/sessions remain unknown.
No configuration/ACL/permission edit, Git staging/commit/push or destructive cleanup.

Final tracked `git diff --check` and new-report
`git diff --no-index --check -- /dev/null docs/C1E_C2B_R12_STORAGE_QUALIFICATION.md`
both **PASS** (no whitespace diagnostics; LF→CRLF advisories only). Together with
the three new Python checks, all four R12 untracked authored files were checked;
existing untracked/vendor evidence was preserved rather than normalized. No-index
wrapper maps difference status 1 to 0 and rejects >1. Final
`git status --short --untracked-files=all` compared with entry shows only the four
new R12 paths; existing modified path set remains the same three files. Agent edits
only the two status documents; the pre-existing `opencode.json` diff is unchanged.
Tracked diff/stat reviewed with those pre-existing changes distinguished from R12.
No staging, deletion or unrelated new runtime artifact. Final dedicated Read of
`opencode.json:34–47` reconfirmed both MCP entries disabled on disk. The exact R12
file scope is the six paths in §1.

## 7. Acceptance verdicts (bounded criteria evaluated separately)

| Criterion | Verdict | Exact scope/reason |
| --- | --- | --- |
| AC-1 durable one-use across actual restart | **PASS** | Demonstrated new OS process after successful exit and abrupt spent-intent exit; cooperative unchanged local NTFS namespace, process-death model only. Power-loss/rollback NOT VERIFIED |
| AC-2 exactly one independent-process winner | **PASS** | READY/GO independent workers, exclusive mkdir and new-only key, one winner/record; held writer also excludes contenders. Protected-host deployment remains prerequisite |
| AC-3 effective checkpoint/evidence protection | **BLOCKED** | Local integrity/replacement detection implemented/tested, but trusted ancestors, independent principals/effective ACLs, race resistance and protected anti-rollback not established. No production-secure claim |
| AC-4 fail closed on corruption/interruption/exhaustion/ack uncertainty | **QUALIFIED** | Actual corrupt/partial files and process exits plus injected ENOSPC/EDQUOT/fsync/readback/ack faults refuse. Native full/quota/device/power faults NOT VERIFIED |
| AC-5 distinct originals/candidates/partials/denials/outcomes and recovery | **PASS** | Separate categories/files/identities; exact original bytes; no candidate permission; terminal denial; inspection never reconstructs success; interrupted campaigns blocked |
| AC-6 accounting/retention and physical limitations | **QUALIFIED** | Configured conservative logical accounting/headroom and retention predicate tested/documented. Physical reservation, confidential retention/backup enforcement and trusted review/time unimplemented |
| AC-7 R7–R11 preservation/regressions | **PASS** | Unchanged 256 regressions + full 503 suite, 22/22 preservation hashes; no frontend/dispatch/config integration |
| AC-8 evidence/limitations/status handoff | **PASS** | Preflight, reproducible commands/results, fault classification, preservation inventory and explicit blockers/STOP in report and both status handoffs |

## 8. Remaining decisions, independent verification and exact STOP

**D2 PENDING:** choose/reject accepted-full versus bounded incomplete prefix policy;
distinct-content versus physical-copy interpretation; approved category/frame/session/
campaign/session-count budgets and duplicate/partial/metadata/backup accounting;
finalization allowance; actual physical quota/allocation/headroom and refusal model.
No proposed R8 numeric value or amendment was adopted here.

**D5 PENDING:** exact independently controlled NTFS parent/volume/ancestors; writer,
reader, operator and recovery principals; effective inherited/explicit DACL and
negative access proof; exclusive trusted writer/ancestor model or qualified safe
handle-relative access; threat/fault/durability/power-loss/rollback model; physical
capacity provisioning; confidential originals/redacted sharing/approved backups;
>=30-day-and-review retention enforcement and recovery/disposal ownership. Independent
operator/security verification must demonstrate these properties in a separately
authorized provisioned test environment; agent-run fixture tests cannot substitute.

D1/D3/D4/D6 also remain PENDING. Genuine approval/withdrawal/root and authenticated
time/continuity infrastructure remain interfaces/fakes, as do real installed topology,
build/effective-state/sole-route qualification. R10 QUALIFIED fake-only and R11 completed
fake-only classification are unchanged. Gate B remains separately BLOCKED.

**Smallest recommended follow-up (not begun):** an operator-owned D2/D5 disposition
and narrow security qualification specification naming the intended threat/fault
model, principals, namespace/capacity/recovery owner and evidence required for negative
access/path-race/retention/durability tests. Only after separate authorization should
any independently provisioned non-production NTFS/principal test environment or
adapter qualification be attempted. Do not promote this candidate into production.

**STOP after this R12 offline handoff.** No R13, live frontend integration, protected
production provisioning, ACL/routing/config change, real approval/time operation,
Roblox/MCP/Studio/ComfyUI execution, install, broad escalation or Git mutation follows.
Both project MCP entries remain disabled on disk. **Gate A = BLOCKED / NOT
TECHNICALLY READY; D1–D6 = PENDING.**
