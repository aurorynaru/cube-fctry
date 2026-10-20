# C1E-C2B-R13 — D2/D5 deployment decisions and security qualification plan

## 1. Executive finding and source baseline

**R13: QUALIFIED offline decision/review package. Protected production storage:
BLOCKED. Gate A: BLOCKED / NOT TECHNICALLY READY. D1–D6: PENDING.** Gate B is
separately BLOCKED. This is an agent recommendation, not operator disposition or
independent Windows security acceptance. Review label: 2026-10-18, harness date,
not authenticated UTC. Single agent, no delegation or Swarm.

The explicit C1E-C2B-R13 authorization supersedes R12's historical STOP **only for
offline reconciliation, targeted static review, documentation and operator-decision
preparation**. It grants no D2/D5 approval or provisioning authority.

### 1.1 Recovered sources and evidence classification

| Source | Use / status in this review |
| --- | --- |
| `status.md` §2.35, blockers and next milestones; `docs/IMPLEMENTATION_STATUS.md` | Current handoff and historical results; no historical task completion inferred |
| `docs/C1E_C2B_R12_STORAGE_QUALIFICATION.md` T0 preflight and §§1–8 | Candidate mechanisms, limitations and reported test evidence |
| `tool/c2b_durable_storage.py`, `tests/test_c2b_durable_storage.py`, `tests/fixtures/c2b_r12_worker.py` | Actual source and assertions statically inspected, **not executed** |
| `docs/C1E_C2B_R8_GATE_A_DECISIONS.md` §§6–8, also §§2/4/5 | Pending D2/D5 text, original Option B architecture, broker distinction and dependencies |
| `docs/C1E_C2B_R11_AUTHORIZATION_GATE.md` §§3–4; `tool/c2b_authorization_gate.py:232–262,331–400` | Consumption/evidence obligations and exact inert-sink acknowledgment/final-check order |
| `docs/C1E_C2B_R7_RECORDER_INTEGRATION.md` §§1–3; `tool/c2b_evidence.py:17,33–58,115–185`; `tool/c2b_recording_supervisor.py:19–24,220–312` | Unchanged pre-parse originals, stream/frame bounds, duplicate evidence and synthetic-only contract |
| `tool/c2b_restricted_frontend.py:19–21`; R9/R10 historical handoffs | Existing client serialization limits, not persisted-storage guarantees |
| `README.md`, `.swarm/plan.md`, `.swarm/plan.json`, project `opencode.json` | Applicable repository guidance, unchanged plan/status and disabled on-disk entries |

Workspace `**/AGENTS.md` search returned none; no external parent instruction search
or unrelated user-file access was attempted. No historical source acquisition,
vendor inspection or MCP protocol research was repeated.

**Reported baseline, not independently rerun:** R12 QUALIFIED disposable offline
Windows/NTFS candidate; 42 new tests; 298 focused passed; full 503 run / 502 passed /
one existing skip. R11 completed fake-only; R10 QUALIFIED fake-only. Phase 1 Task
1.1 remains incomplete (`plan.json` status `in_progress`, unchecked in `plan.md`).
No runtime tests, validators, compilation, synthetic workers, native attacks or
external services were executed in R13. All source findings below are static.

### 1.2 Entry inventory and preservation method

Before documentation edits, `git status --short --untracked-files=all` recorded
three already modified paths: `docs/IMPLEMENTATION_STATUS.md`, `opencode.json`,
`status.md`, plus existing untracked work. Porcelain inventory: **232 lines**,
SHA-256 of UTF-8 lines joined by LF without trailing LF:
`bb6627dc0c05fff261ed11ceb2a21a61c81073c09088844c801d2c5d2bc6bc0c`.
HEAD: `4661903d4f97cdb8d62adea89544741d3a00871c`.

Read-only `git hash-object` recorded 107 unique paths selected by `git ls-files
--cached --others --exclude-standard -- tool tests docs/evidence opencode.json
'docs/C1E_C2B_R[7-9]*' 'docs/C1E_C2B_R1[0-2]*'
docs/R10_OPERATOR_EVIDENCE.txt` (the attempted plan pathspecs are ignored by Git;
the two approved plan files were therefore explicitly hashed separately).
Sorted `path=Git-object-ID` lines, LF joined, UTF-8 SHA-256:
`56dca6a22ef5686a14fe97c13e215b35e18f1748b4204148d6eb8c01b53cf3fe`.

An additional **392-path preservation set** includes **all** paths returned by
`git ls-files --cached --others --exclude-standard`, plus explicit `.swarm/plan.md`
and `.swarm/plan.json`, excluding only the three R13 deliverable paths. This covers
existing code/tests, R7–R12 reports, original repository evidence and unrelated
tracked/untracked work, without opening it for research. Its manifest is built by
`Sort-Object -Unique`, hashing each path with `git hash-object -- <path>`, forming
`path=ID` lines, then SHA-256 over UTF-8 LF-joined lines without a trailing LF.
Entry manifest: `f884d1290a685feffd592b3a47b3f3fbee508a93bfa9781149914f5bafa26ba0`.
Ignored harness telemetry/database files are not represented; the approved plan
and authoritative task statuses are represented explicitly. No claim is made about
unrelated external or ignored files. Object IDs are consistency evidence, not signatures.

| Key protected path | Entry Git object ID |
| --- | --- |
| `opencode.json` | `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd` |
| `.swarm/plan.md` | `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2` |
| `.swarm/plan.json` | `ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899` |
| `tool/c2b_durable_storage.py` | `16797fef1b2207437883de0260d926c51931e5d5` |
| `tests/test_c2b_durable_storage.py` | `68ac61f19f930c5a162a3be3c43d0b1e4aaa884b` |
| `tests/fixtures/c2b_r12_worker.py` | `a6d4cb55227aacd5830b810036f5a5fd9e28861b` |
| `docs/C1E_C2B_R12_STORAGE_QUALIFICATION.md` | `f36037e3c61f0ad508785cf11c71afd88c41e642` |
| `docs/C1E_C2B_R8_GATE_A_DECISIONS.md` | `93b9ab2ba8365f604ca32d86f2f633f999ffd738` |
| `tool/c2b_authorization_gate.py` | `e2497307c3d52d91d385dc5a21e7afaff9ea1dcb` |

Exit results are recorded in §10. Existing dirty/untracked artifacts are preserved;
the pre-existing `opencode.json` diff is not an R13 configuration edit.

## 2. Focused R12 static review

Severity is the consequence **if promoted to protected production authority**:
Critical = possible replay/forged authority; High = evidence disclosure, invalid
evidence or unsafe namespace/capacity admission; Medium = availability/accounting
or bounded-contract gap. These are deployment blockers/assumptions, not claims that
R12 promised hostile-writer protection. R12 explicitly discloses the main limits.
`S` below means `tool/c2b_durable_storage.py`; `T` means
`tests/test_c2b_durable_storage.py`; `G` means `tool/c2b_authorization_gate.py`.

### 2.1 One-use and integrity findings

| ID / exact source | Supported claim and evidence boundary | Uncovered assumption / consequence | Severity; decision or independent test |
| --- | --- | --- | --- |
| F01 — `S:177–203,268–301,331–346`; `T:122–192`; worker `:31–47,63–87` | Atomic campaign `mkdir` excludes cooperating processes; exclusive files and audit precede exact key/binding/attempt acknowledgment. Key hashes issuer + approval ID, independent of binding/session. Reported new-process/race/crash assertions match source. | Every consumer must use this unchanged writer and namespace. Direct writes/private methods, guard removal or a second ledger bypass the rule. `consume` delegates scope authentication to R11; wrong binding is not independently authenticated by storage. An already spent key refuses changed bindings; a never-spent invalid approval needs the verifier to refuse it. | Critical outside cooperative boundary; D3/D5 trusted writer and replay domain; Q01–Q04/Q10–Q12 |
| F02 — `S:190–203,288–300,314–329`; `G:357–368,389–400`; `T:276–355,408–436` | Dirty failures retain the guard; clean validation refusals may release only their own guard. Missing/wrong spend ack yields no inert bytes; lost outcome ack may follow factual inert bytes but never completion. Recovery is never success/reusable authority. | Availability is deliberately lost campaign-wide. The guard has no timeout or lease; operator deletion is not recovery authorization. Storage failure may also prevent a denial receipt. | Medium availability / Critical if reset into reuse; D5 recovery owner must preserve spent/unknown history; Q10/Q12/Q15 |
| F03 — `S:205–245` (chain starts at zero), `:331–341`; R12 report `:239–250` | Gaps, partial triplets and unknown entries are detected. No independently protected expected tail, sequence high-water mark or epoch exists. | Removing the final complete reserve/bin/seal triplet leaves a valid shorter ledger; removing the only spent triplet can leave a valid empty ledger. An older consistent ledger restored in place can pass. Loss of an entire committed directory entry/triplet need not be detectable. File-ID checks may reject copied files but do not establish freshness. Same issuer/ID can also be consumed in a different fresh campaign ledger. | **Critical replay blocker**; D5 must select rollback/missing-history barrier and D3 global replay/epoch scope. Protected cross-campaign replay authority or independent permanent invalidation is required; Q11/Q12. No attack executed |
| F04 — `S:28–47,146–172,205–245,275–301`; `T:240–274,489–515` | New-only reservation → exact data → seal; checked short writes, fsync/readback, canonical metadata/duplicate-key rejection, exact descriptor keys/charge/sequence/length/digests and payload device/inode check. Raw evidence is not canonicalized; original whitespace/CRLF is retained. | Canonicalization applies to ledger metadata, not authenticated truth. Seal binds payload identity, not persistent identity of every descriptor/seal; a privileged writer can recompute the chain and file IDs, rewrite all history, or replace code. Hash chaining alone never prevents a privileged complete rewrite. Audit validates storage structure, not approval authenticity or every business decision's semantics. | High integrity / Critical authority if treated as authentication; D5 code/namespace isolation, D3 independent verifier; Q03–Q08/Q11 |
| F05 — `S:349–419`; `G:357–388`; `T:194–238,517–565` | Same-session checkpoint/policy/prerequisite originals are required; action/original/intent binding is reverified. Candidate requires exact spent intent; outcome links a distinct candidate; denial blocks later candidate/outcome. An uncertainty denial may follow an already persisted outcome. | All records remain fake-only. `prepare` is two ledger appends in one guard, not an all-or-nothing transaction: an original may survive without intent and quarantine. Candidate/outcome presence cannot reconstruct authorization or real Studio success. | High if promoted; keep typed semantics and final guarded revalidation; Q09/Q10/Q15 |

### 2.2 Namespace, accounting and recovery findings

| ID / exact source | Supported claim and evidence boundary | Uncovered assumption / consequence | Severity; decision or independent test |
| --- | --- | --- | --- |
| F06 — `S:79–113,123–144,177–185`; `T:574–603` | Local absolute disposable-root validation, fixed NTFS check; UNC/device-style paths, ADS, dot-dot, trailing dot/space and nonplain ancestors refuse. Point-in-time leaf checks reject reparse/symlink/nonregular/multiple-link objects. Actual hard-link assertion exists; reparse test is mocked. | No handle-relative opens, ancestor handles retained through use, effective DACL checks or ownership authentication. `lstat → open → lstat/fstat` does not exclude a racing junction/rename or in-place concurrent writer. A matching token/root prefix is not a protected principal. | High namespace blocker; D5 exclusive ancestors/single trusted writer or Option C; Q02/Q05–Q08 |
| F07 — `S:1–5,89–92,303–308,349–354`; `opencode.json:48–68`; R11 report §3.4 | Module explicitly assumes a cooperative namespace/process-death environment. Public category restrictions are API hygiene. Project policy permits repository editing; shell prompts and Python private methods are not Windows security boundaries. | No evidence that agent cannot modify storage, verifier, imports/runtime, config, policy, replay or originals. Same-user equivalent-token processes ordinarily have the same access; a DACL naming that user does not distinguish the trusted writer from the agent. Confidentiality is not supplied. | **Critical independent-trust blocker**, High confidentiality; choose Option B for the recommended threat model; Q01–Q04/Q16/Q17 |
| F08 — `S:56–76,247–286`; worker `:17–20`; `T:357–406,532–543` | Exact payload + exact descriptor + 1,024 seal allowance is conservatively reserved; header charged campaign-wide. Every distinct retained copy charges again; duplicate category/identity refuses. Session/campaign/max-record/max-session checks occur under guard. | `category_bytes` sums **across the campaign**, not separately per session; categories are semantic ledger kinds, not R8 stdout/stderr/client/outbound groups. Fixture record cap 16,384 cannot hold a 65,536-byte response in one record. No R8 mapping/enforcement follows from passing fixtures. | High policy mismatch if promoted; D2 explicit mapping and per-session category enforcement, Q09 |
| F09 — `S:177–203,248–266,303–329`; `T:173–192,388–406,438–487` | Every session represented by rows retains its remaining finalization allowance in both session and campaign totals. Complete duplicates/partials charge; interrupted/unknown inventory is preserved and blocks writes. | Empty abandoned directories/sessions with no row are not counted; no external session admission inventory. The guard serializes transactions, not entire observation lifetimes: it does not independently enforce one active session. `inspect_recovery.logical_reserved_bytes` omits outstanding finalization allowances and is not free-capacity certification. Incomplete writes have unknown physical usage. `snapshot()` acquires a writing mkdir guard: the fixture reader is not proof of an independently read-only reviewer role. | Medium accounting / High if used for admission; D2 count empty/abandoned attempts, enforce one active observation, no unknown-as-zero; D5 read-only verification path; Q03/Q09/Q10 |
| F10 — `S:23,247–266,268–299`; `T:374–406,408–436` | Byte headroom prevents nonfinal categories from spending a session's unspent allowance; denial/outcome/partial use it. Other sessions' allowances remain reserved. | No reserved record slots or final-category capacity; many partials, category caps, record-count exhaustion, guard quarantine or ENOSPC can prevent finalization. Headroom is logical, not a promise to persist a receipt through broken storage. | Medium / High false-receipt risk; D2 size/layout proof plus category/record-slot reservations, Q09/Q13/Q15 |
| F11 — `S:161–172,247–266`; `T:408–436,567–572`; R12 report `:201–205` | fsync/readback and logical refusal paths are implemented; injected ENOSPC/EDQUOT assertions match report. | No physical allocation/quota/reservation, cluster/MFT/directory/backup accounting or finalization guarantee. External writers/device failure can exhaust capacity despite logical headroom. No real quota/full condition was independently verified. | High capacity blocker; D2/D5 actual volume/quota/headroom and Q13–Q15 |
| F12 — `S:161–172,182,203,288–300`; worker `:39–47`; R12 report `:244–250` | File flush/readback and worker exits support process-death evidence. No directory durability barrier or external commit witness is implemented. | Reboot/power loss can lose guard or spent record/directory entries after readback; a consistent older prefix may appear healthy. File fsync is not proof of directory/device-cache durability. Device failure may destroy evidence entirely. | **Critical replay fault boundary**, High retention; D5 §5 model and independent continuity barrier; Q10–Q15, conditional Q19 |
| F13 — `S:314–329,422–427`; `T:605–613`; R12 report `:207–212` | Inspection is read-only, no repair/delete API; advisory >=30-day-and-review predicate checks basic inputs. | No trusted age/review authority, actual retention hold, confidential backup, approved sharing, disposal or recovery owner. Thirty-day evidence expiry alone must never authorize deleting still-relevant spent history. | High confidentiality/replay retention; D5 retention/recovery decisions, Q16–Q18 |

**Conclusion:** source supports the report's qualified cooperative candidate claim.
It supplies neither independently protected production authority nor a general
hostile same-user sandbox. F03/F08–F10 sharpen deployment implications, without
changing R12 code, tests or historical evidence. No fix is implemented in R13.

## 3. D2 policy recommendation

### 3.1 Decision-ready reconciliation

All recommended values remain **proposed operator policy, PENDING**. R8 references
below are its actual §6.1 table/text at lines 369–413; no oversized-failure amendment
is adopted. “Existing” means statically observed synthetic behavior; R13 has not
independently executed it. **Independently verified physical guarantees: none.**

| D2 item | Exact R8 proposal / recommended disposition | Existing enforced synthetic behavior | New enforcement / unknowns |
| --- | --- | --- | --- |
| D2.1 Accepted versus oversized | Full original accepted response/envelope and LF/CRLF delimiter **<=65,536 bytes**, readback before acceptance. Oversize: retain **at most first 65,536 bytes**, labeled incomplete failure, terminal, no tail elsewhere/no retry/conditional state. Recommend this narrow amendment for consideration (`R8:371–384,398`). | R7 frame/stream prefix bounds, pre-parse persistence; `supervisor:241–272`, R7 §2. R12 generic `partial` is not an integrated response collector. | Explicit operator adoption needed; future integrated boundary test 65,536 / 65,537 and no hidden tails. Retained-byte hash/count only; OS reads are lower bounds, not full upstream size. Semantic upstream completeness remains unknown. |
| D2.2 Interpretation | **Distinct response-content** cap, not total-copy or physical limit (`R8:386–391`). Recommend distinct-content with separate copy budget. | R7 keeps frame and stream copies; R12 charges each copy under a new identity. | Total-copy alternative requires reviewed layout and remains blocked; no silent deduplication or R7 change. |
| D2.3 Duplicates | stdout frame+stream copies **<=524,288**; stderr **<=65,536**; combined raw copies **<=589,824 bytes/session** (`R8:400`). | Each retained R12 payload separately charged (`S:268–286`); no dedup. | Map all copies including checkpoint/original/transcript copies. Charge each in one appropriate group and aggregate; no copy exempt because content repeats. Layout may refuse earlier. |
| D2.4 stdout/stderr/frames | **262,144 / 65,536 distinct bytes/session**, **32 upstream frames maximum for acceptance**, each including initialize/control <=65,536; reads <=4,096. A refused 33rd delimiter may be retained within stream cap (`R8:398–399`). Recommend retain these bounds. | `LIMIT=64*1024`, `SESSION_LIMIT=4*LIMIT`, `MAX_FRAMES=32`, `supervisor:241–272`. | Preserve exact inclusive delimiter handling, flood/partial classification; map categories to logical storage. No storage or semantic success from frame count alone. |
| D2.5 Upstream outbound | **4,096 bytes/frame; 65,536 bytes/session including request/control copies** (`R8:401`). Recommend these limits. | R7 saves intended bytes before write (`supervisor:308–312`); R11 synthetic action bounded 4,096. R7 has no comprehensive outbound session/copy quota. | New reviewed writer-side aggregate and every-control-frame admission. Client-input bound is a separate dimension. |
| D2.6 Client transcripts | If persisted, **262,144 combined input/output bytes/session**, input frame **4,096** (`R8:402`). Recommend no optional extra transcript copy by default; if retained, same cap. | R9/R10 `CLIENT_FRAME=4096`, `CLIENT_TRAFFIC=262144`, `CLIENT_FRAMES=64` bound serialization, **not disk**. | Persisted copies need admission/accounting; do not confuse 64 client frames with 32 upstream frames. Existing 64 client-frame cap is not a new R8 value. |
| D2.7 Other records | **262,144 bytes/session combined** approval/time/checkpoint/receipt/manifest/diagnostics/marker (`R8:403`). Recommend same payload grouping; storage descriptors/seals/header additionally charged under aggregate. | R12 semantic categories and format bounds; prerequisite originals required, but no matching combined per-session metadata group. | Include original/intent/consumption/candidate payloads and all nonraw duplicates; no uncharged “security metadata.” Oversized prerequisite refuses prelaunch; no truncated success receipt. |
| D2.8 Session aggregate | **2,097,152 bytes (2 MiB)** all retained logical file lengths incl duplicate/temp/partial/metadata (`R8:404`). Recommend additionally use R12's conservative reservation charge for admission, which can refuse earlier than actual lengths. | R12 configurable session ceiling on charges + remaining finalization allowance, not selected R8 values. | Integrated per-session categories and full inventory; account staging before creation. Preserve the distinction between actual lengths and conservative charges; no claim that slack may exceed category limits. |
| D2.9 Campaign | **16 observation directories; 33,554,432 logical bytes (32 MiB); one active run** including failed/abandoned (`R8:405`). Recommend same; quota never grants attempts. | R12 guard serializes individual transactions, not complete sessions; charged-byte/session-count/max-record checks, session count inferred from rows. | Explicit campaign/session admission before first file and one-active-run enforcement for the entire observation lifetime; include empty/abandoned attempts, header/shared metadata; no rotation or reset. Cross-campaign replay protection is separate (F03). |
| D2.10 Finalization | R8 requires reserve **inside** aggregate but selects **no numeric finalization allowance** (`R8:403–404`). New R13 candidate: **131,072 charged bytes (128 KiB)/admitted session**, not added to the 2 MiB limit. | R12 per-session remaining byte reserve; fixture uses **12,000**, not 128 KiB (`worker:17–20`). | Validate maximum final/refusal/partial layout, reserve category slack and record slots as well as bytes. Partials consume headroom. Exact slot/category partition remains unresolved until layout proof; unavailable storage still permits no receipt guarantee. |
| D2.11 Physical capacity | R8 **16 MiB = 16,777,216 bytes** free/quota headroom candidate for next <=2 MiB session, conditioned on actual cluster/layout/file counts (`R8:406`). Recommend retain only as a qualification candidate/minimum, never certify it sufficient. | No physical reservation; real allocation/quota/full behavior NOT VERIFIED. | Operator must select actual volume, allocation/quota ceiling, numeric capacity guarantee, competing-consumer controls and supported layout. All unresolved. A free-space sample is not a reservation. |
| D2.12 Backup/metadata allocation | R8 counts physical clusters/directories/overhead/approved backups separately (`R8:406–413`). Recommend all ledger metadata charged logically, all backups/export copies separately inventoried, quota-reserved and access-controlled. | Descriptor <=4,096 and seal <=1,024 are parser bounds; R12 charges header + intended payload + exact descriptor +1,024 seal allowance. No backup/export API. | Backup logical/physical ceilings, version count, location, schedule, overlap during restore and disposal remain unresolved. No unspecified backup may consume reserved collection space or hold unapproved originals. |

Verified R8 arithmetic: `524,288 + 65,536 = 589,824` raw-copy bytes;
`589,824 + 65,536 + 262,144 + 262,144 = 1,179,648` category bytes.
The difference from 2 MiB is **917,504 bytes**, not an allocation guarantee.
`16 * 2,097,152 = 33,554,432`; shared campaign header/metadata also count, so
16 simultaneous maximum-charged sessions are not promised.

### 3.2 Minimal internally consistent enforcement proposal

Recommend two nested meters: (1) the per-session content/copy groups above;
(2) conservative ledger admission plus every other retained file, staging copy and
outstanding final reserve. Persist both actual lengths and reservation charges
without double-counting a file in two content groups. Descriptor/seal overhead is
charged even when not response content. Map checkpoint duplicates explicitly: raw
copies to raw group, additional checkpoint/decision payloads to other-record group;
all are aggregate charges. The group mapping must be reviewed, not guessed from
R12's `CATEGORIES`. Campaign category caps alone do not enforce session caps.

For a finite candidate layout, **new R13 proposals, not R8 values**: at most **128
ledger records/session, 2,048/campaign** (16 sessions), plus the fixed header and
guard; no unmetered staging/exports. Each record creates three files. With maximum
descriptor/seal overhead, `128 * (4,096 + 1,024) = 655,360` bytes. A deliberately
conservative simultaneous envelope is:

`1,179,648 payload + 655,360 record overhead + 131,072 outstanding final reserve
+ 4,096 header allowance = 1,970,176 < 2,097,152`.

This reserves slack **126,976 bytes**, does not prove the profile needs <=128
records, and does not allow every category to reach its maximum irrespective of
record/finalization limits. Header is actually campaign-charged; including its full
bound here is conservative. The outstanding reserve and payload sum may overlap
future final payloads; overreservation is intentional. Extra files invalidate this
envelope unless separately budgeted. Record-slot/final-category reservation,
maximum receipt shape and actual layout remain prerequisites. If they do not fit,
refuse or return for operator revision rather than increasing limits implicitly.

Tradeoff: distinct-content plus bounded copies preserves the existing recorder
shape with less redesign, at the cost of more storage than a total-copy cap.
Conservative charges and one active run simplify audit but sacrifice utilization
and availability. Physical headroom and backup budgets cannot be finalized offline
without the actual volume/layout/quota and independently controlled provisioning.
No R7 collector, policy or R12 limit is modified by this recommendation.

## 4. D5 deployment alternatives

“Option B” in this section is the **storage deployment alternative**; it complements
the project's existing **Option B high-assurance authorization / contained recorder
architecture** (R8 §§4–5). R8 §2.3's deferred subprocess-ownership broker addresses
native handle/lifetime ambiguity. Protected storage ownership is a different
requirement; its necessity does not automatically revive that deferred broker.

| Alternative | Operator effort / permissions | Isolation / maintainability | Failure handling / complexity | Compatibility and disposition |
| --- | --- | --- | --- | --- |
| **A — same-user cooperative filesystem** | Lowest effort; ordinary user writable files, no principal separation | Easy to maintain; detects accidental changes under unchanged code. Equivalent-token agent/process can change code, config, originals, seals, guard or ledger. Same-user DACL grants do not distinguish processes. | R12-style quarantine is simple; no hostile-writer freshness or confidentiality guarantee. | Suitable for disposable offline engineering only. Cannot be a protected production authority when agent can modify trusted files; insufficient for §5 recommended model. |
| **B — independently controlled storage principal, controlled ancestors** | Moderate operator work; independently managed non-agent writer identity and reader/recovery roles, later verified DACLs. Writer should need no administrator privilege during ordinary operation. Exact identities/rights/path remain unresolved. | Protect code/runtime/imports/policy/config, replay authority and originals from agent/child; approved reviewer read-only, unapproved users denied. Small reviewed interface and pinned deployment are maintainable. Token/process/credential isolation must be real, not merely a second process under same user. | Small short-lived operator-started writer/gate can suffice; exclusive campaign writer, bounded transactions and persistent quarantine. Independently reviewed local IPC/control contract only if required by future workflow; not a general privileged file service. Moderate implementation/qualification work. | **Recommended smallest protected architecture**, conditional on actual identity/ancestor/process isolation and independent replay-continuity barrier. Compatible with existing Option B; no always-on service, scheduled task or large broker is presumed. |
| **C — handle-relative hardened namespace** | Higher effort; native Windows expertise and qualification. Requires rights to open/hold approved directory/file handles; no blanket elevation justified. | Anchor operations to verified directory/volume handles; protect against ancestor/leaf substitution where exclusive control cannot be established. Native code and platform contracts add maintenance cost. | No-follow/reparse-aware opens, explicit sharing modes preventing relevant delete/rename while held, relative object opens through reviewed native facilities, handle-based identity/volume checks and create/readback on the same object. Reject traversal/mount/cross-volume/link surprises; test each supported Windows/NTFS profile. High complexity. | Conditional addition to B if namespace control cannot be proved. Not a replacement for principal/code/authority isolation, confidentiality or anti-rollback; handles alone do not stop authorized in-place rewrites. |

### 4.1 Smallest recommended protected deployment

Choose B with one trusted writer and exclusively controlled ancestors, after
operator review. A separately managed, explicitly launched short-lived process
under the protected principal is a candidate, **not an implemented deployment**.
Do not select any existing username, path or ACL by implication. OpenCode and its
children must not obtain that token, modify its executable/config/import paths,
inject into the process, duplicate authority-bearing handles or invoke an arbitrary
write/initialize/delete/restore command. A second identity alone is insufficient
if the agent can control that identity's session, credentials or trusted launch.

If a narrow interface is necessary, its future independently reviewed contract must:

- Accept only bounded typed evidence/attempt operations, fixed destination references
  and independently verified scope; resolve paths internally. No caller paths,
  arbitrary code/argv, generic file writes, ACL changes, guard clearing or replay reset.
- Authenticate the actual caller and enforce operation rights server-side; treat
  submitted hashes/labels/bytes as untrusted, not human approval or UTC. Keep D3/D4
  verification independent and bind the exact checkpoint/action/policy/destination.
- Atomically spend in a protected replay domain before any first byte; return exact
  acknowledgments, never dispatch permission from a candidate. Connect storage to
  the independently enforced gate, not to an agent-controlled “approved” flag.
- Serialize/reject concurrent calls, validate lengths/category/aggregate/reserve,
  preserve originals and partials, fail closed on disconnect/lost ack, and expose
  read-only verification to approved reviewers. No retry implied by a lost response.
- Bind namespace/policy/epoch and detect missing/older authority state using a
  separately protected continuity source or permanently invalidate all affected
  old authority before admitting new work. Actual mechanism remains a decision.

R12 `snapshot()` creates/removes a writer guard (`S:310–312`); its reader fixture
does not demonstrate a read-only security principal. Future reviewer verification
must use a reviewed read-only path over quiescent preserved records or a bound
verified snapshot. Do not grant R write access merely to call the current API;
an actively changing inventory is not a trusted completed snapshot.

If this small deployment cannot demonstrate control of ancestors and processes,
stop and review C or stronger isolation. Do not present path normalization, Python
`0700`, application permissions or a hash token as equivalent protections.

## 5. Recommended threat/fault model

Classifications are **proposed**, all D5 decisions remain PENDING. Trust the approved
Windows/kernel/NTFS/runtime contracts, independently administered writer/reviewer
and their pinned protected deployment. Treat agent/model inputs, child output and
all restored state as untrusted until verified. An administrator or trusted writer
deliberately subverting these roots is outside the recommended attacker model.

| Threat/fault | Proposed classification | Required authorization/replay behavior | Evidence availability / present qualification |
| --- | --- | --- | --- |
| Accidental agent modifications | **Required to defend** | Deny changes to trusted files/parents/code and detect corruption before next call | Preserve originals; current effective denial NOT VERIFIED |
| Malicious/compromised agent within assigned token | **Required to defend** | No forge/bypass, injection, writer-token use, namespace change, replay reset or permissive interface | Confidential originals protected; Option A insufficient, Option B tests required |
| Another ordinary Windows user | **Required to defend** | Negative access to authority, code, evidence and writable parents | Deny unauthorized reading/copying/modification; NOT VERIFIED |
| Same-user equivalent-privilege process in the **agent** context | **Required to defend through separation** | Must still lack protected writer/replay/code access; process name is irrelevant | If writer shares this token, protection is not established and B's premise fails |
| Same-user equivalent-privilege process in the **trusted writer** context | **Explicitly excluded from recommended scope** | Treat as trusted-root compromise, not something user-based DACLs defeat | If operator includes this attacker, B alone fails; stronger process/security isolation required |
| Privileged administrator/kernel modification | **Explicitly excluded from recommended scope** | No universal tamper/rollback claim against trusted OS/admin; detect what can be detected | Conditional stronger requirement needs separately justified roots outside admin control |
| Filesystem corruption | **Required to defend for detected uncertainty**; complete consistent loss **not established by evidence** | Corrupt/missing/unknown state refuses; undetectable valid-prefix loss needs independent continuity barrier | Exact evidence survival not universally guaranteed; current hashes only local consistency |
| Process crashes | **Required to defend** | Spent stays spent, no uncertain retry, campaign quarantine and zero next call | Reported R12 process-death evidence only; independent deployment test required |
| OS restarts | **Required to defend replay; availability not guaranteed** | Fresh process audits + independent continuity check, new time epoch; no old monotonic or approval reuse when history uncertain | R12 reboot durability NOT VERIFIED; safe halt acceptable |
| Sudden power loss | **Required to defend replay after uncertainty**; guaranteed byte survival **conditional on operator decision** | Missing-history barrier or independent invalidation of all affected old authority; no assumption local guard survived | No universal persistence promise; current directory/device durability NOT VERIFIED |
| Storage-device failure | **Required to fail closed**; recovery-time/data-survival SLA **conditional on operator decision** | No fresh empty store accepting old approvals; stop and escalate | Backup redundancy/restore RPO/RTO unknown, no availability promise |
| Backup rollback / directory restoration | **Required to defend replay** | Reject stale/incomplete state even if self-consistent, or independently invalidate its entire authority epoch before any new attempt | Restored file IDs may refuse; not sufficient freshness proof. Q11/Q12 required; mechanism unresolved |

The essential safety invariant is **no replay from lost history**, not “every disk
write survives every fault.” For the selected nonadministrator fault model, a
continuity anchor must be protected from the same restore/loss domain it detects;
another file inside the restored ledger is insufficient. Alternatively require an
independent authority to permanently retire all affected approval identities/epochs
and prohibit old submissions before replacement storage is used. A new approval
string or newly initialized campaign alone is not such a barrier. No source/root,
boot service, epoch issuer or implementation is selected or created here.

Availability is separate: a stale guard can block forever; no bounded recovery time,
always-writable receipt or automatic restart is promised. Recovery ownership may
authorize inspection/preservation, **never clearing spent history to retry an
operation**. Thirty-day evidence retention is a minimum, not an expiry date for
replay protection: retain replay history or independently retire its authority for
as long as reuse could otherwise occur.

Independently qualifiable: effective access on named tokens/objects, supported
namespace race cases, byte/accounting behavior, finite crash/restart/restore and
capacity scenarios, retention controls. Not universally provable from finite tests:
every scheduling/power-cut/device/driver outcome, administrator-proof integrity,
instantaneous revocation, indefinite availability or zero device loss. Conditional
claims must name host/build/storage/firmware/cache/backup configuration and faults;
no software test total establishes authenticated UTC or operator authority.

## 6. Independent security qualification matrix

**Specification only: every Q test is NOT VERIFIED in R13; none is executed.**
Require separately authorized, **independently provisioned non-production Windows
test infrastructure** with synthetic confidential canaries only, approved disposable
NTFS namespace/volume, independently selected identities and rollback-safe test
snapshots. No production namespace, identity, credential or ACL may be inferred from
this document. A future runner must refuse unresolved principal/path/policy fields.

### 6.1 Common execution and evidence contract

Roles are abstract: **P** independent provisioner; **W** approved trusted writer;
**R** approved read-only reviewer; **A** agent token and its actual child token;
**U** unauthorized ordinary user; **O** recovery/disposal owner; **I** independent
security reviewer. These are role labels, not usernames or created identities.
P/I must not rely on agent-supplied token labels or agent-editable logs as proof.

For every row, the future harness records: case/subcase ID, resolved environment
manifest, host/OS/NTFS/runtime/storage layout and code/policy digests, actual process
token user/group/restricted/elevation/integrity/privilege state, attempted native
operation and exact target object/parent identity, native result/error, before/after
inventory/digests/allocation, synchronization/crash point, expected/actual verdict,
and independent reviewer identity/assessment. Preserve private originals of results
and canaries under the test evidence policy. No credentials or full environment dump.

Execute each negative operation in a fresh owned fixture to avoid laundering a
previous corrupt state; positive controls establish the test can actually access
the intended objects. Deterministic barriers coordinate races, not guessed sleeps.
Use an inert sink to measure factual byte counts; no Roblox or live MCP. A test
failure means BLOCKED, retain artifacts and stop the affected campaign. Missing
evidence, unavailable rights/fault injection or skipped subcases mean NOT VERIFIED,
not PASS. Post-byte faults may have nonzero factual inert bytes but **no trusted
completion and no next attempt**. No result authorizes automatic retry or cleanup.

The matrix is executable as a future case specification: resolve prerequisites,
perform the enumerated operation under the listed actual token, assert each PASS
and fail-closed condition, capture the stated evidence, then obtain I's review.
Commands/runners and provisioning are intentionally not executed or installed here.

### 6.2 Identity, ACL and namespace tests

| Test / preconditions / principal | Exact property and operation | Expected PASS / expected fail-closed | Evidence; why independent; remaining risk after PASS |
| --- | --- | --- | --- |
| **Q01 Token/launch isolation** — P has selected W/R/A/U roles and pinned trusted deployment; P/I observe actual W, A and A-child processes | Compare effective token identities/groups/privileges and process access. Under A/child/U attempt writer-token impersonation, authority-handle duplication, process modification/injection and unapproved start-as-W via available interfaces. | Only independently launched W holds authority; negative operations denied. Ambiguous token/process ownership or successful escalation blocks qualification and all inert dispatch. | Token/access results, trusted executable/import/launch provenance and native errors, positive W control. I must establish real identities rather than strings. Residual OS vulnerabilities/admin or W-context compromise excluded. |
| **Q02 Ancestors/inheritance** — P provisions chosen test hierarchy and leaves; W creates all supported object types; I/R inspect | Record owner, explicit/inherited DACLs, group grants and effective access at every ancestor/root/child/leaf; verify new leaves inherit intended protection. Exercise supported inheritance changes in separate fixtures. | No broad unauthorized read/write/delete/WRITE_DAC/WRITE_OWNER grants; W required rights and R read/verify rights work. Unknown/broader inheritance refuses before admission. | Native security descriptors + actual access probes + parent/child identities. Independent P/I needed for group/inheritance truth. Residual later policy drift requires revalidation; ACL text alone is insufficient. |
| **Q03 Positive/negative object access** — Q01/Q02 pass; private canaries and valid ledger; W/R/A/child/U | W create/read/append via typed interface; R read/verify but no writes. A/child/U attempt read/copy/write/truncate/delete/rename/replace originals, spent records, descriptors/seals/header/guard, config/verifier/runtime/imports and policy. | Required W/R access succeeds; every unauthorized operation denied and canaries unchanged. Any forbidden access blocks qualification; uncertain store refuses next inert byte. | Per-operation token/target/native result and before/after hashes. I witnesses non-agent assertions; residual authorized insider/admin compromise and exfiltration via permitted outputs require scope control. |
| **Q04 Writable-parent bypass** — separate fixtures for every ancestor/child and an unauthorized replacement file; A/child/U | Attempt parent rename/delete-child, sibling swap, root replacement, change DACL/owner and replacement through writable install/config/import parent. | All authority-changing parent operations denied; trusted object identity unchanged. Any writable bypass blocks use even if leaf ACL looks restrictive. | Parent access masks/results, object identities and full chain inventory; independent test under actual unauthorized tokens. Residual future deployment/parent changes invalidate result. |
| **Q05 Reparse/junction** — P-only disposable link targets and barriers approved separately; P/A/U attempt, W audits | Attempt insertion/replacement of root/ancestor/leaf with junction/symlink/reparse/mount redirection before admission and at open/readback seams. Never target unrelated files. | Under B unauthorized replacement denied; any existing reparse object refuses. If C selected, operations remain anchored to authorized handles or refuse, with no outside writes/reads. Unexpected resolution is terminal. | Reparse tags/targets, operation errors, held handle identities and outside-canary unchanged proof; I controls link setup. Residual untested tags/drivers/interleavings not universally covered. |
| **Q06 Hard links** — P-approved same-volume canary and separate leaf fixtures; P/A/U/W | Try linking payload/descriptor/seal to alternate names and admission of multiple-link objects; verify unauthorized link creation access and typed writer refusal. | Unauthorized link denied; preexisting multiple-link leaf rejected; no external canary altered. Unknown link/identity state refuses. | Native link counts/IDs, results, snapshots/digests; independent setup ensures actual NTFS link, not mock. Residual link-count race needs Q07/exclusive writer protection. |
| **Q07 Namespace TOCTOU** — deterministic barriers around check/open/write/readback; B or reviewed C deployment, P test attacker and W | Race ancestor/leaf rename, junction swap, hard-link substitution, identity-preserving in-place mutation and sharing/delete access while W holds/uses objects. | B access/sharing prevents hostile changes; C stays on verified volume/object with approved no-follow semantics or refuses. No outside access, false verified checkpoint or inert next byte on uncertainty. | Event/handle/native trace and before/after identities/canaries, forced seam coverage; I independently orchestrates attacker. Residual finite race coverage/native-contract dependence. |
| **Q08 Interface confinement** — reviewed bounded interface, if any, Q01–Q04 pass; A/child/U clients and W | Submit malformed/oversized/duplicate/wrong-binding/path/command inputs, stale epoch, unauthorized caller and forged approval/time labels; request generic append/initialize/delete/guard reset/restore. | Only reviewed typed operations accepted within scope; forbidden inputs produce zero additional inert bytes and no unapproved mutation. Lost/ambiguous acknowledgment terminal, no client retry right. | Exact bounded requests/results, caller authentication evidence, state snapshots and inert-byte counts; I evaluates actual endpoint, not API declarations. Residual parser/authentication dependencies; D3/D4 real authority still separately required. |

### 6.3 Accounting, crash, attack and fault tests

| Test / preconditions / principal | Exact property and operation | Expected PASS / expected fail-closed | Evidence; why independent; remaining risk after PASS |
| --- | --- | --- | --- |
| **Q09 D2 limits/reservations** — operator-disposed D2 and reviewed group/layout mapping; W; I supplies cases | Exercise equality and +1 for 65,536 inclusive frame, incomplete prefix/no hidden tail, stdout/stderr/32 vs 33 frames, outbound/control, client copies, metadata, all duplicates/partial/temp files, record count, final byte/category/slot reserves, 2 MiB session, 16 sessions/32 MiB campaign. Admit empty/failed/abandoned sessions and a second active run. | Exact-bound acceptance only if all other checks pass; +1 and unknown inventory refuse without extra inert bytes. Failed/empty runs count; duplicates charge again; final reserve cannot be stolen. No truncate/delete-to-fit. | Original byte files, group and physical inventories, charge arithmetic, stream read lower bounds, admission and dispatch logs. I verifies layout/math independently. Residual physical/device faults separate; a cap test never approves policy. |
| **Q10 Concurrent writers/readers** — Q01–Q09 setup; independent W instances and R, deterministic READY/GO/HELD barriers | Race same issuer/ID across bindings/sessions/controllers and independent reader; hold writer during partial append; force lost/wrong consumption/candidate/outcome acks. | Exactly one possible spend/dispatch winner, contenders refuse without queue; R refuses active inconsistent snapshot. After lost spend/candidate ack zero inert bytes; outcome ack loss may follow bytes but completion false and no replay. | Actual process IDs/tokens, barrier trace, single spent record, exact acks/inert counts and fresh-process audit. I launches witnesses; residual finite schedules, power-loss separate. |
| **Q11 Tail deletion / missing spent history / new campaign** — valid spent ledger plus independent replay-continuity mechanism and protected session registry; P/O inject faults in **separate** copies; W verifies | Remove one file, middle triplet, **last complete triplet**, only triplet, entire campaign directory; remove guard; present valid older prefix; attempt same issuer/ID in a different campaign. | Detect mismatch against independent state and refuse, or demonstrate preexisting permanent invalidation of all affected old authority. Internally valid empty/shorter ledger never re-enables old approval. No automatic initialize/reset. | Pre/post ledger + independent high-water/epoch state, exact attempts and zero replay bytes. I/P must control loss and independent witness. **Current R12 alone cannot meet this test.** Residual common-failure-domain loss invalidates anchor; whole-root admin compromise excluded. |
| **Q12 Restart and backup rollback** — disposable supported host/volume; separately approved restart/snapshot procedure, protected continuity witness outside restored domain; P/O/W/I | Interrupt before/after reservation/data/seal/spent/candidate/outcome ack/guard release; start fresh process; separately restart OS. Restore older entire directory/volume snapshot with and without preserved file IDs; restore partial/corrupt backup. | All uncertain sessions remain nonreusable; stale self-consistent history rejected or its old authority independently retired. New boot invalidates old time mapping; no resumed observation, regenerated seal/outcome or stale-lock clearance. | Exit/boot boundaries, original and restored inventories/IDs, independent witness, backup version/access, inert replay counts. I controls restore/restart so copy-ID rejection is not misreported as anti-rollback. Residual finite interruption points; no universal power-cut guarantee. |
| **Q13 Native quota/full/allocation** — separately provisioned bounded nonproduction volume/quota and competing-consumer fixture; P/O adjust only that test resource; W writes | Measure allocated clusters/file counts/directory/metadata effects, actual quota ceiling and candidate >=16 MiB headroom, final reserve and backup overlap. Fill test quota/volume before/during each write phase; attempt concurrent capacity consumption. | Admission backed by chosen capacity mechanism or refuses; real full/quota errors terminal, originals/partials preserved, no false completion/next byte. Free-space sample alone cannot PASS reservation. | Native capacity/quota/allocated-length readings, exact error codes/phase, independent logical/physical inventories and retained partials. I verifies actual allocation, not injected errno. Residual device/media loss, metadata variability and excluded external consumers require explicit support limits. |
| **Q14 Failed write/flush/readback** — reviewed fault seam plus actual disposable I/O path; W, P/I fault controller | Exercise positive short writes, zero/partial writes, failed flush/close/readback, changed bytes and identity; include controlled native error path if supported. Label injection separately from native faults. | Only checked exact completed/readback bytes accepted; any uncertainty quarantines, no next call or invented receipt. Existing partial files remain unchanged for review. | Raw files/reservations/seals, native/injected classification, exceptions, readback and inert counts. I controls fault seam and validates actual object. Residual device lying about flush cannot be ruled out by readback. |
| **Q15 Incomplete retention/finalization** — each phase has separate fixture and approved maximum final layout; W/O/I | Interrupt prepare between original/intent and each transaction phase; exhaust record/category reserve or storage; kill owned worker before final receipt. Inspect twice from fresh process/reviewer. | Preserve originals/partials, no synthetic success, no next call, unknown accounting never zero. Recovery always inspection-only; unavailable receipt explicit. Byte headroom never claimed to override broken storage. | Before/after inventories, exact phase/error, reserved slots/bytes, recovery report and missing-receipt classification. I owns interruption and reviews preserved originals. Residual total device loss may prevent retention; availability deliberately sacrificed. |

### 6.4 Retention, confidentiality and optional durability tests

| Test / preconditions / principal | Exact property and operation | Expected PASS / expected fail-closed | Evidence; why independent; remaining risk after PASS |
| --- | --- | --- | --- |
| **Q16 Confidential originals/sharing** — approved W/R recipients and redaction policy, synthetic sensitive canaries; W/R/A/child/U/I | Attempt unauthorized reads/copies through storage, logs, diagnostics, IPC, temporary/redacted paths and backup access. Separately produce approved redacted derivative with original/derivative provenance manifest. | Originals private; unauthorized reads denied; only approved recipients receive reviewed derivative, no original canary leaks. Unapproved/missing redaction disposition blocks sharing, not an invitation to export originals. | Access/native results, approved recipient record, private originals and redaction manifest/reviewer diff. I tests from unauthorized roles and inspects actual output. Residual inference through permitted data, screenshots/pagefile/dumps or platform tooling needs operator confidentiality scope; not blanket prevention of all OS leakage. |
| **Q17 Backups/access/recovery** — operator specifies backup location/access/version/capacity/retention and O escalation; P/O/R/A/U/I | Verify backup readers/writers, inheritance, no automatic sync/upload, restore into isolated new review namespace; test corrupted/partial backup and missing recovery owner/continuity witness. | Only approved backup visibility; capacity charged separately. Restore verifies bytes/access but never authorizes dispatch; uncertainty escalates to O, no replay or permissive fallback. | Backup inventory/version/access/allocation, restore digests/IDs, recovery incident/escalation record. I inspects backup system and both domains. Residual untested backup/device failures and RPO/RTO unresolved until approved. |
| **Q18 Retention/disposal/replay hold** — approved age/review-completion evidence and O disposal authority, synthetic chronology fixtures, no production deletion; O/R/W/I | Test <30 days, exactly 30 days, >=30 with review incomplete, review complete later, invalid/backward age, unknown review and separately approved holds. Attempt unauthorized disposal and spent-history purge while old authority could be replayed. | Keep originals >=30 days **and** until review completion, whichever later; no automatic disposal at eligibility. Only separately authorized synthetic disposal may proceed after all holds, and replay history retained or independently invalidated. Unknown inputs/owner/approval refuse disposal. | Hold/age/review/disposal records, token/access results, before/after synthetic inventory and retained/invalidation proof. I validates controls/authorities; accelerated arithmetic is not observed 30-day enforcement. Residual real elapsed-time operation requires longitudinal review; authenticated UTC not supplied by this test plan. |
| **Q19 Conditional power/device durability** — only if operator requires data-survival claim; dedicated sacrificial infrastructure, approved supported device/cache/firmware fault envelope and owner; P/O/I | Future approved device/power-fault procedure at named commit/ack phases; verify restart/evidence and independent continuity under that exact profile. No universal power-cut or production destructive test. | Meets explicitly selected byte-survival requirement for tested faults **and** no replay after loss; otherwise data-survival qualification BLOCKED, fail closed and preserve what remains. | Device/config/fault traces, pre/post ack/evidence inventories and independent continuity results. Independent lab/operator owns destructive capability. Residual untested power timing/device/driver faults; PASS never promises universal durability. |

## 7. Operator decision sheet

**All rows PENDING.** A recommendation or approval of R13's documentation scope
does not approve any row. Record approve/reject/revise with exact scope in a later
operator-owned disposition. Do not request credentials or sensitive account data;
actual roles can be identified through credential-free references in that later
packet. No real identity/location/quota/backup choice is invented here.

| ID / exact approval question | Recommended default; alternatives / tradeoff | Available evidence / evidence still required | Sufficient by itself? / status |
| --- | --- | --- | --- |
| **D2-P1** — Adopt bounded oversized-failure amendment and distinct-content interpretation? | Full <=65,536 including delimiter; failure prefix <=65,536, no hidden tail; budget duplicates separately. Alternative total-copy cap needs new layout; rejecting amendment keeps live use blocked. | R8 §6.1 + unchanged R7 synthetic behavior; integrated exact/+1/no-tail proof Q09 still required. | No; numeric/storage/authority gates remain. **PENDING** |
| **D2-P2** — Approve §3 content/copy/category/session/campaign bounds and explicit failed/empty/abandoned session counting? | R8 262,144 stdout / 65,536 stderr / 32 accepted frames; 589,824 raw copies; outbound 4,096/frame and 65,536/session; optional client 262,144; other 262,144; 2 MiB/session; 16 sessions/32 MiB/one active. Alternative smaller budgets refuse sooner; higher values require review. | R8 exact values, R12 accounting primitives; per-session mapping/integrated enforcement and Q09/Q10 absent. | No; categories are not currently mapped. **PENDING** |
| **D2-P3** — Approve conservative charge overlay and new R13 candidate 128 KiB final reserve, 128 records/session and 2,048/campaign? | Count descriptors/seals/header and all retained files; reserve final category/record slots. Alternative layout-derived lower/higher bounds needs arithmetic and review; no automatic cap increase. | §3.2 envelope, R12 charge/reserve source; maximum final layout, exact slot/category partition and implementation/tests still required. | No; slot/category proof unresolved. **PENDING** |
| **D2-P4 / D5-P4** — Which actual volume/quota/capacity/backup allocation and numeric headroom guarantee are approved? | Evaluate >=16 MiB candidate with real allocation/file counts; protected capacity guarantee, not free-space sample. Backup ceiling/versioning/restore-overlap separately budgeted. Alternative operator-managed equivalent requires evidence. | R8 proposal, R12 explicit absence; actual volume/capacity/quota/backup policy **UNRESOLVED**, Q13/Q17 required. | No. **PENDING** |
| **D5-P1** — Choose cooperative A, protected-principal B, or B+C hardened namespace; which exact threat classes are required/excluded? | B with exclusively controlled ancestors for §5 threat model. A only disposable cooperative use; C if exclusive control cannot be proved, higher complexity. W-context equivalent-token/admin compromise excluded by proposed model. | Static F01–F13 and R8/R11 requirements; real principal/process/effective access and interface evidence Q01–Q08 absent. | No. **PENDING** |
| **D5-P2** — Identify approved writer/reviewer/operator/recovery roles and protected namespace/ancestor/code/runtime/config boundaries? | Independent W, approved read-only R, O recovery; no agent/child direct authority writes or unauthorized reads. Actual identities, NTFS parent/volume, access masks and inheritance **UNRESOLVED**. | R11 interface/R12 limitation; independently provisioned role/token/DACL/parent proof Q01–Q08 required. | No; naming roles does not establish isolation. **PENDING** |
| **D5-P3** — Approve fault/replay model and choose independent missing-history/rollback/epoch barrier including cross-campaign scope? | Preserve safety across process/boot/restore uncertainty; halt allowed; no automatic reuse. Complete-byte power/device survival conditional. Select independent protected continuity or permanent affected-authority invalidation. | F03/F12, R11 consumption contract; actual barrier, boot/restore/fault procedure and Q10–Q15 (Q19 if selected) absent. | No; R12 alone cannot meet Q11. **PENDING** |
| **D5-P5** — Approve confidential originals, redacted recipients, >=30-day-and-review retention, backup visibility and disposal/escalation ownership? | Private originals, separate reviewed sharing; explicit O disposal authorization and replay hold. Actual backup policy/recipients/owner **UNRESOLVED**; no automatic deletion. | R8 §6.2/R11 requirements, R12 advisory predicate; Q16–Q18 independent and longitudinal evidence required. | No; policy plus enforcement and verification needed. **PENDING** |

D1/D3/D4/D6 remain PENDING independently; D2/D5 disposition cannot approve human
identities/signatures, real UTC acquisition, installed routes or live observation.

## 8. Unresolved blockers

1. **D2/D5 operator disposition absent.** No approved amendment, numeric production
   limits, record layout/reserved slots, physical quota/headroom or backup allocation.
2. **Protected deployment absent.** Actual principal/token/process isolation,
   ancestor/code/config/import/runtime protections, effective DACL inheritance,
   confidentiality and negative access/race evidence are NOT VERIFIED.
3. **Replay continuity absent.** Complete tail/ledger loss, rollback and fresh campaign
   reuse are not prevented by local chaining/file IDs. No independent barrier or
   permanent authority-invalidation procedure is selected/implemented/qualified.
4. **Fault/recovery/retention acceptance absent.** Recovery owner, backup/restore
   permissions/visibility, trusted hold/review/disposal controls, actual NTFS capacity
   and supported reboot/power/device guarantees remain unresolved.
5. **Implementation/integration absent.** R12 remains disposable-only with fixture
   policy and fake-only R11 adapter, not a production writer or integrated R7/R9 gate.
6. **Other Gate A prerequisites remain:** D1 supported ownership model; D3 authentic
   out-of-model approval/review/withdrawal and protected verification roots; D4 two
   independent authenticated UTC sources, justified bounds/continuity/final/post checks;
   D6 installed build/effective settings/hooks/contained topology/sole-route retirement
   and separate readiness/activation authority. Gate B fixed-query/same-read identity
   blockers remain separate. Task 1.1 remains incomplete.

## 9. Proposed smallest future executable milestone

**Not begun; no R14 authorization implied.** First obtain a credential-free,
operator-owned approve/reject/revise disposition for §7, including the unresolved
roles/namespace/capacity/fault/backup fields. Then separately authorize **only a
non-production identity/namespace isolation qualification slice Q01–Q04**, after an
independent provisioner supplies the test environment. Scope: pinned trusted
code/runtime/config ownership, actual tokens, ancestor/leaf inheritance, required
positive and denied negative access, and independent evidence review. No real
approval/time/MCP/Roblox interface is needed for that slice.

Entry: resolved roles/paths, test-only ownership/provisioning authority, reviewed
access-probe specification, synthetic canaries and preservation/retention owner.
Exit: independent Q01–Q04 evidence or explicit BLOCKED/NOT VERIFIED result, preserve
all failures, STOP. If isolation fails, return to deployment design before IPC or
namespace hardening. This milestone alone is **not production qualification**;
Q05–Q18, approved D2 enforcement and selected continuity/fault implementation remain
prerequisites; Q19 only under an explicit additional durability requirement.

## 10. Exact STOP and nonauthorization statement

### R13 verification record

All checks below were actually performed in R13; they are **static/preservation
checks only**, not independent Windows runtime/security verification. No reported
R12 runtime result is reclassified as R13 independent evidence.

| Check / method | Result and scope |
| --- | --- |
| Recompute §1.2's sorted 392-path manifest using `git ls-files`, explicit plan paths and `git hash-object`, compare count + SHA-256 | **PASS 392/392 unchanged**, same `f884d129…a26ba0`; includes source/tests/original evidence/R7–R12 reports/config/both plans and unrelated inventoried work. No source or test modified |
| Recompute 107-path focused manifest; explicit `git hash-object -- .swarm/plan.md .swarm/plan.json opencode.json` | **PASS 107/107 unchanged**, same `56dca6a2…cf3fe`; all three explicit IDs exactly match §1.2 |
| `git status --porcelain=v1 --untracked-files=all`, omit only new R13 report, compare original count + SHA-256 | **PASS**, 232 original lines and original `bb6627dc…6bc0c` preserved; 233 total lines after adding exactly one report. Existing modified path set unchanged; R13 additionally edits only the two already-dirty status documents |
| `git diff --check`; `git diff --no-index --check -- /dev/null docs/C1E_C2B_R13_D2_D5_DEPLOYMENT_DECISIONS.md` | **PASS**, no whitespace diagnostics; Git LF-to-CRLF advisories only. No-index wrapper accepts native 0/1 for comparison-to-empty and rejects >1; no whitespace error output observed. Final document edits rechecked |
| Dedicated Read of `opencode.json:34–47` | **PASS** on-disk `roblox_studio.enabled=false`, `comfyui.enabled=false`; unchanged config hash. Effective loaded settings/sessions **NOT VERIFIED** |
| Dedicated Read of `.swarm/plan.md`; initial Read of `.swarm/plan.json` plus unchanged hashes at exit | **PASS**, PLAN_HASH `2lnzncyys8pi5`, Phase 1 in progress, Task 1.1 unchecked / `in_progress`, not complete; approved plan/task statuses unchanged |
| Targeted document readback/source comparison and R8 arithmetic | **PASS** static reconciliation of all 12 D2 dimensions, thirteen findings, three deployment alternatives, threat/fault model, Q01–Q19 and PENDING sheet. No dependency/install/config/runtime action |
| Windows security/runtime/provisioning tests, authenticated UTC or genuine approval verification | **NOT VERIFIED / not performed** in R13; future Q tests remain NOT VERIFIED, protected production qualification BLOCKED |

`git diff --stat` includes pre-existing historical documentation additions and the
pre-existing `opencode.json` diff; it is not an R13-only edit list. R13's exact file
scope is the new decision report plus `status.md` and `docs/IMPLEMENTATION_STATUS.md`.
The all-work manifest comparison establishes preservation of the other inventoried
files; nothing was staged, committed, pushed or cleaned.

### Acceptance verdicts (R13 documentation scope)

| Criterion | Verdict | Supporting evidence |
| --- | --- | --- |
| AC-1 precise D2 decisions tied to R8/R12 | **PASS** | §3.1's 12 dimensions cite exact R8 lines and current mechanisms; §3.2 checks arithmetic and labels new proposals/unknown enforcement |
| AC-2 explicit D5 principal/namespace/confidentiality/fault models | **PASS** | §§4–6; actual identities/namespace/capacity/backup choices unresolved, no invented approval |
| AC-3 no same-user independent-trust assumption | **PASS** | F07/F09, Options A/B/C and separate agent-token versus writer-token threat classes; read-only reviewer API gap explicit |
| AC-4 independent tests with PASS/FAIL evidence requirements | **PASS** | Q01–Q19 specify preconditions, principals, operations, positive/fail-closed behavior, evidence, independent reviewer rationale and residual risk; execution remains NOT VERIFIED |
| AC-5 no production ACL/identity/namespace/approval modification | **PASS** | Documentation-only file scope and recorded tool activity; no provisioning/native test/real authority/time/config action |
| AC-6 R7–R12 code/tests/evidence/plan preserved | **PASS** | 392-path and 107-path before/after manifests, explicit config/plan IDs and unchanged original status inventory |
| AC-7 accurate status/handoff | **PASS** | `status.md` latest/§2.36/blockers/evidence/next milestone and implementation addendum reflect R13; historical sections retained |
| AC-8 Gate A blocked, D1–D6 pending | **PASS** | Current status, §7 decision sheet, §8 blockers and exact STOP below; no policy approval inferred |

These PASS verdicts qualify the requested documentation milestone, **not production
storage**. Overall R13 **QUALIFIED**; production and Gate A **BLOCKED**.

**STOP after this R13 documentation/static-review handoff. No R14 or live execution
is authorized or started. Gate A stays BLOCKED / NOT TECHNICALLY READY. Gate B stays
separately BLOCKED. D1–D6 stay PENDING. Both project MCP entries remain disabled on
disk; effective loaded configuration remains unknown.**

This milestone approves no D2/D5 policy, Windows identity, storage location, ACL,
quota, credential, verification root, signature, token or protected production
evidence infrastructure. No storage/source/test fix, production/test ACL change,
provisioning, user/service/scheduled task/privileged process, native adversarial test,
time-service query, dependency install or system/configuration change is authorized.
No Studio, StudioMCP.exe, mcp.bat, Roblox tool, ComfyUI, MCP activation/live integration,
asset upload/publication/mutation, Git stage/commit/push or unrelated cleanup follows.
Software tests and static review cannot substitute for operator authority,
independent OS security evidence, authenticated UTC or production readiness.
