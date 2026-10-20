# GF-001-Q4-OFFLINE — Server-owned binding implementation

**Verdict: QUALIFIED offline implementation.** The implemented composition root
passes **37/37 standalone Luau integration cases** within the declared mock
contract. Actual Roblox Instance, Humanoid, connection, signal scheduling and
destruction behavior are **NOT VERIFIED**. No Studio integration was performed.

Review date: 2026-10-20 (harness date). One agent, no delegation or Swarm.
The selected model identity supplied by this session is
**`openai/gpt-6.1-sol`**, not GLM-5.3 High; no model/account/configuration switch
was performed. This separately authorized offline milestone supersedes the
historical Q3 STOP only for this implementation. It does not execute Q3's
previously proposed live Q4 test.

**R13 remains the latest completed security milestone. Gate A and Gate B remain
BLOCKED; D1–D6 remain PENDING. Both project MCP entries remain disabled on disk;
effective loaded MCP state is unknown. STOP after GF-001-Q4-OFFLINE.**

## 1. Actual files and core reuse

New implementation, all under `experiments/gf001_npc_waves/luau/`:

| File | Responsibility |
| --- | --- |
| `ServerOwnedBinding.luau` | Reusable server-owned composition root, internal WaveRuntime adapter, issuance/binding ledger, serialized controls, bounded death queue, conservative teardown and restart control |
| `MockEngineOperations.luau` | Standalone Luau mock of the injected engine-operations interface; receiver-required and void-returning methods, private issuance/destruction observations, scheduling and failure controls |
| `run_binding_tests.luau` | Executable integration suite requiring the actual new binding, mock, and existing GF-001 core |

New `experiments/gf001_npc_waves/q4_evidence/` contains an evidence README and
fresh `vectors.json`, `luau_results.jsonl`, `python_results.jsonl`. Historical
Q1 parity files and Q2/Q3 evidence/source are preserved. Other Q4 changes are
this report and additive handoffs in `status.md` §2.41 and
`docs/IMPLEMENTATION_STATUS.md`. The experiment's historical README is preserved.

The existing `Config`, `Clock`, `Rng`, `Mobs`, `SpawnPoints`, `Rewards`,
`WaveRuntime`, example, Python reference, and parity algorithms were **not
changed**. The new root validates a detached configuration copy using the
existing `Config.validate`, recursively freezes it, constructs private
`Rewards` and `WaveRuntime` instances, and injects its internal
`spawn(record, point)` / `despawn(record)` adapter. Only the original
`WaveRuntime.killMob` → `Mobs.kill` → `Rewards.recordDeath` path emits a death
and synthetic reward intent. There is no payout consumer, currency, player
beneficiary, damage-credit attribution, DataStore, purchasing or networking.

## 2. Module interfaces and trust boundary

### Composition root

```text
ServerOwnedBinding.new(rawPlainConfig, {
    clock, rng, waveRuntime, mobs, selectSpawn, engineOps
}) -> frozen session API

session.start()             -> boolean, reason?
session.tick()              -> boolean, reason?  (core tick, then serial drain)
session.drain()             -> boolean, reason?  (explicit serial drain)
session.stop(reason?)       -> boolean, reason?  (also the explicit cleanup retry)
session.status()            -> detached core status + bindingState/queue/fault fields
session.report()            -> detached obligation/diagnostic summary
session.recordsSnapshot()  -> detached plain-data record copies
session.eventLog()          -> detached plain-data event copies
session.clientRewardClaim(player, payload) -> nil; original unconditional rejection
```

There is no public runtime, `killMob`, `damageMob`, reward mutation, writable
core record, Model, Humanoid, connection or token accessor. The diagnostic run
serial is not the ownership token. Client identifiers are not ownership proof;
non-scalar claim-player inputs are reduced to a diagnostic placeholder. All
returned diagnostic tables are detached from private state. Trusted server code
holds the lifecycle API; it is not wired to a client RemoteEvent.

Engine operations, module dependencies, RNG and clock are trusted server-side
dependencies. The mock's separate test-inspection API intentionally exposes
mock objects/receipts to the test driver; that API is not returned by the
composition root and is not a client interface. This is an in-process ownership
policy, not protection against malicious server code, a compromised dependency
or a hostile process with equivalent memory access.

### Narrow injected operations

All functions below are ordinary injected function calls. The mock implements
the receiver-dependent method calls **inside** the operations (for example,
`humanoid.Died:Connect(fn)`, `handle:Disconnect()`, `model:Destroy()`). The binding
never indexes an engine object's fields or assumes an Instance is a Lua table.

| Operation | Contract |
| --- | --- |
| `createRunContainer(token)` | Returns an issued run container; nil is allocation-free only under the declared allocation-free contract. A throw/yield is unknown allocation. |
| `ownsContainer(container, token)` | Exact private container issuance check |
| `createMob(allocation, point, container, token)` | Returns `(created, model, humanoid)`, including known partial `(false, model, humanoid)`; `(false, nil, nil)` is allocation-free only with the explicit contract flag |
| `describeIssue(model)` | Private exact-reference issuance receipt: token, record ID, mob ID, point ID, exact Humanoid |
| `isModel(value)`, `isHumanoid(value)`, `humanoidOf(model)` | Expected type and exact intended Humanoid association checks; future implementation must enforce one intended Humanoid |
| `humanoidDead(humanoid)` | Trusted server-side death-eligibility/death-state observation; not player-damage attribution |
| `connectDeath(humanoid, fn)` | Returns the actual issued connection handle; throw/yield/missing handle without a no-listener guarantee is unknown listener state |
| `connectionIssued(handle, humanoid)` | Exact handle association with this Humanoid's death subscription |
| `disconnect(handle)` | **Void**; calls with the appropriate receiver |
| `isConnected(handle)` | Connection-specific observation; acknowledgment requires **exactly false**, not nil/unreadable/unknown |
| `destroy(object)` | **Void**; calls on the exact issued resource with its receiver |
| `parentOf(object)`, `isDescendantOf(object, ancestor)` | Scoped observations, never universal destruction proof |
| `teardownObserved(model, humanoid, container)` | Agreed scoped teardown evidence, stronger than unparenting: in the mock, private destruction ledger, removal from container census, nil parent, and no live Humanoid signal listeners |
| `containerEmpty(container)` | Complete scoped emptiness observation before container destruction; never delete a container containing foreign/unverified children |
| `containerTeardownObserved(container, token)` | Exact issuance, private mock destruction observation, nil parent and empty owned container |

The two explicit declarations in `engineOps.contract` are
`failedCreateGuaranteesNoAllocation` and `connectNilGuaranteesNoListener`.
The root snapshots them per run. A thrown operation is never converted into
the allocation-free case. The mock's guaranteed nil-listener path genuinely
installs no listener; its throwing Connect path installs a listener **before**
throwing. The binding treats non-guaranteed nil results as unknown even when a
particular mock execution happened to allocate nothing.

`allocation` is a frozen plain descriptor (`id`, `mobId`, `maxHealth`), not the
mutable core record. `point` is the exact private frozen configured point,
including position. The allocation contract permits one issued root and its
intended Humanoid, no additional independently allocated hidden resources.
Every independently allocated returned reference must be represented in that
pair; a future richer factory needs an expanded reviewed resource contract.
The current factory contract is a trusted seam, not a discovery mechanism for
arbitrary hidden allocations.

## 3. Spawn acknowledgment and private ownership

1. Validate running state, token, record state/mob definition, exact configured
   point reference, record→point association, and absence of a prior binding.
2. Allocate through injected operations. Immediately register returned Model
   and Humanoid references, exact core record reference, immutable ID/type/point
   association and run token before further fallible preparation. Maintain the
   reverse map keyed by exact Model reference. A returned child without a root
   is retained as an unknown allocation obligation, not treated as empty.
3. Check private issuance, run/record/type/point match, expected types, exact
   Humanoid association, correct run ancestry and initial death eligibility.
4. Subscribe; immediately store the **actual returned** connection handle, then
   check issuance/association and `Connected == true`.
5. Reconcile any callback/death observation during setup by **conservative
   refusal**. Tear down known resources, do not activate, and return false.
   No setup callback is silently upgraded into an authorized death.
6. Activate and return **exactly true** only after preparation succeeds.

An allocation-free failure or known partial returns false and the unchanged
core withholds `mob_spawned`. A thrown allocation records an unresolved
record-scoped obligation; neither cleanup nor restart is acknowledged. Foreign
or replaced resources are quarantined. Names, attributes, forgeable fields,
client IDs and mock `Destroyed` fields are ignored as ownership evidence.

## 4. Queue, callbacks and serialized controls

The death queue is bounded at **8 candidates**. Callback work is enqueue-only
for active bindings, with conservative guards/refusal markers for stale,
setup, disarmed, stopping or reentrant delivery. A callback never calls core
death, cleanup, stop or restart. During registration it records an early-event
marker for refusal before activation. During stop it records a teardown
refusal. During a drain it records a reentrancy fault instead of replaying
unresolved ordering.

`tick()` calls the core tick first, lets its spawn/cleanup loops return, then
drains serially. `drain()` is also an explicit server control. Candidates are
revalidated by exact token, binding, Model, Humanoid, reverse issuance, current
record state, run state, ownership/ancestry, server-held death eligibility and
once-only death acceptance before entering `WaveRuntime.killMob`. The core's
one-way record/reward guards are an additional duplicate barrier. No client
claim, raw signal without corroborated death eligibility or new-run ID can
authorize an old candidate.

Every lifecycle control has a shared busy guard, including reentry during
allocation and cleanup. Nested controls return a refusal; they do not stop or
restart the runtime inside an outer drain. A run that observes reentry/overflow
does not return a successful control outcome. Clean teardown after a known
ordering fault may allow an **explicit fresh start**; no restart is automatic.
Unaccepted events are discarded, so conservative refusal may lose a synthetic
intent rather than fabricate one.

Each operation and outer lifecycle control is run once on a private coroutine.
A suspension is detected by non-dead status, faults/quarantines the run, and is
never resumed or returned by this module. Tests actually inject allocation and
teardown yields. This establishes fail-closed behavior in standalone Luau; it
does **not** qualify real Roblox task scheduling or engine-owned resumptions of
a yielded task. Such behavior is a future engine integration blocker.

The mock simulates immediate delivery and explicit deferred delivery. An
adversarial resumption-point mode dispatches pending mock signals during other
operations; it is a chosen fault schedule, **not** a claim that a real Roblox
property lookup is a documented yield/resumption point. Saved callbacks are
also invoked directly to test guards independently of cancellation behavior.

## 5. Teardown, uncertainty and restart

- Disarm all forwarding before stop. Each record teardown also disarms itself
  before connection work. Verify the exact record, binding, Model/Humanoid,
  container and private issuance before destructive operations.
- Disconnect the exact issued handle, ignore its void return, and require a
  nonthrowing call plus `isConnected(handle) == false`. Retain failed handles;
  do not destroy that model after a failed/unverified disconnect.
- Destroy only the exact positively identified issued root. Require a
  nonthrowing call, removal from owned ancestry **and** the agreed scoped
  teardown observation. The mock's private destruction ledger is used behind
  the ops contract together with census/listener checks, never a public
  `Destroyed` field. A void return, `pcall` success or `Parent == nil` alone
  cannot acknowledge cleanup.
- Retain known intact failures for explicit serialized `stop("retry")`.
  A failed teardown encountered during `tick()` is **not automatically retried**
  by an additional stop inside that tick; the test checks the exact call count.
  Observation errors/yields and ambiguous side effects leave persistent
  uncertainty even if later identifiable resources can be torn down.
- Unknown allocation/listener obligations withhold the actual core
  `record.cleaned` acknowledgment. Destroying a known model cannot account for
  an unreturned listener. The binding/obligation stays retained; removing a
  model or container does not make an unknown resource safe.
- Container destruction requires its exact issuance and an empty scoped census.
  A foreign descendant prevents container deletion and is never destroyed.
- Direct WaveRuntime restart is unavailable: the private runtime can only be
  restarted through `session.start`, which refuses retained bindings,
  unresolved/uncertain obligations and a retained container. A permitted new
  run gets a fresh unexposed table token; core IDs stay monotonic as before.

`status().state` is the **raw core state**; `bindingState`, returned control
success, `report().uncertain`, `containerOutstanding`, retained obligations and
`restartAllowed` describe the binding outcome. If the core emitted
`all_waves_completed` before later container teardown failed, its historical
event remains in the diagnostic log; the wrapper returns
`false, "cleanup_unverified"`, reports faulted/uncertain binding state, and
refuses restart. That core event alone is not a binding-completion receipt.
This case is executed explicitly. Repeat stop on an already stopped core can
return `false, nil` while `report().restartAllowed` confirms accounted resources;
this retains the existing core's stop semantics.

## 6. Executed integration coverage

`run_binding_tests.luau`: **37 passed, 0 failed, exit 0**. These are executed
integration cases of the new module with the actual core, not Q3's local probe.

| Cases (in suite order) | Meaningful assertions |
| --- | --- |
| 1–4 | Three simultaneous exact bindings; independent deaths; full example 8 mobs / 3 waves / 96 points; exact receipts and point association; ownership survives forged names/attributes/fields |
| 5–7 | Preexisting versus actual returned handle, only own handle disconnected before a failed Destroy; receiver-required void methods; immediate registration death refuses spawn and rewards with known cleanup |
| 8–10 | Deferred post-stop delivery, callback during cleanup, duplicate death, disconnected saved callback, forged signal refused, one intent per accepted death |
| 11–14 | Foreign model, replaced Humanoid and duplicate Model-reference quarantine; missing-Humanoid and guaranteed no-listener partial cleanup; installed-but-unreturned listener uncertainty; failed Disconnect retains model and exact handle for explicit retry |
| 15–17 | Thrown/no-op/ambiguous Destroy, actual withheld completion and restart; allocation-free versus non-guaranteed nil failure; thrown container allocation leaves an orphan and refuses start |
| 18–20 | Queued death discarded on interruption, nil-handle permanent obligation, clean restart with **unequal exact tokens**, monotonic mob IDs and inert old callback |
| 21–23 | Overflow (9 deaths / queue bound 8) refuses success; reentrant callback and nested drain refusal; forged client claim yields no intent, real accepted death uses configured points |
| 24–27 | Detached configuration/record/event snapshots; immutable allocation and point descriptors; thrown allocation retains actual unknown orphan and uncleaned core record; returned false+resources is cleaned but never spawned; callback during another allocation cannot enter core death mid-spawn |
| 28–31 | Nested start/tick/stop/drain refusal during allocation; teardown observation failure retains actual uncleaned record; allocation and teardown yields are never resumed/acknowledged |
| 32–35 | Nonthrowing unparent-only Destroy rejected; foreign descendant blocks container teardown; raw core completion cannot bypass retained container; server-held eligibility rechecked when draining |
| 36–37 | Deferred/captured callbacks stay inert after interrupted failed stop and fresh restart; nested cleanup controls refused, exact resources accounted without reporting reentrant control success |

Expected failure scenarios pass by asserting refusal, retained obligations,
untouched foreign resources, absent spawn/completion/reward events and/or actual
uncleaned core records. They are not classified as successful engine operations.

## 7. Toolchain, regressions and exact commands

Existing pinned Luau **0.743** was reused without download/replacement/install.
SHA-256 rechecks match Q1/Q3:

- `luau.exe`: `5246429297673bc845b947b135226d2f9e8cac77518c04269652486cf9a2383d`
- `luau-analyze.exe`: `e8c8d1149b9ff97d154022be33829df62ac583a15683f3da33f8c15d5443b74f`

| Evidence class / executed check | Result |
| --- | --- |
| Actual Luau CLI: new binding integration | **37/37**, exit 0 |
| Actual Luau CLI: unchanged Q3 mock contract suite | **11/11**, exit 0 (design probe, separately counted) |
| Actual Luau CLI: unchanged Q2 adapter suite | **16/16**, exit 0 |
| Actual Luau CLI: original core suite | **20/20**, exit 0 |
| Fresh Luau dump/runner and Python reference comparator | **12/12**, exit 0; new Q4 evidence files only |
| Python reference suite | **20 passed**, zero skips, 0.011s |
| Full existing offline Python discovery | **523 run, 522 passed, one existing Windows symlink skip, 75.051s** |
| Static: strict and default luau-analyze across all GF-001 Luau/parity | Exit 0, no diagnostics |
| Static: StyLua check and Selene across all GF-001 Luau/parity | Exit 0; Selene **0 errors / 0 warnings / 0 parse errors** |
| Registry / art validators | **0 unique assets / 0 events**; **2 metaschemas / 5 presets / 3 positive / 36 negative fixtures**, PASS |

Commands run from the project root (tools invoked at existing absolute paths):

```powershell
$luau = "$env:TEMP\opencode\luau-0.743\extracted\luau.exe"
$analyze = "$env:TEMP\opencode\luau-0.743\extracted\luau-analyze.exe"
& $luau experiments\gf001_npc_waves\luau\run_binding_tests.luau
& $luau experiments\gf001_npc_waves\luau\run_engine_contract_tests.luau
& $luau experiments\gf001_npc_waves\luau\run_adapter_tests.luau
& $luau experiments\gf001_npc_waves\luau\run_tests.luau

# New Q4 output directory verified first; old evidence never overwritten.
cmd /c "`"$luau`" experiments\gf001_npc_waves\parity\dump_vectors.luau > experiments\gf001_npc_waves\q4_evidence\vectors.json"
cmd /c "`"$luau`" experiments\gf001_npc_waves\parity\parity_run.luau > experiments\gf001_npc_waves\q4_evidence\luau_results.jsonl"
python experiments\gf001_npc_waves\parity\gf001_parity.py --vectors ..\q4_evidence\vectors.json --luau-results ..\q4_evidence\luau_results.jsonl --out ..\q4_evidence\python_results.jsonl
python -m unittest tests.test_gf001_npc_waves -v
python -m unittest discover -s tests -p "test_*.py"
$files = @(rg --files experiments/gf001_npc_waves/luau experiments/gf001_npc_waves/parity -g '*.luau')
& $analyze --mode=strict $files
& $analyze $files
& "$env:USERPROFILE\.aftman\bin\stylua.exe" --check experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity
& "$env:USERPROFILE\.aftman\bin\selene.exe" experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity
python tool/registry.py validate
python tool/validate_art.py
git diff --check
```

Fresh evidence SHA-256:

| File in `q4_evidence/` | SHA-256 |
| --- | --- |
| `vectors.json` | `465c11b29b7073ec4aa02b30814a896bf85f923aec5179e5424277fc6460629f` |
| `luau_results.jsonl` | `f2b688256105e283c480a438227fd87df52d6a19432bc89bad819f3e63fd5d8c` |
| `python_results.jsonl` | `b20017033683cd3dd2ccbf08d240f7dbf0431aa50bef6a5a969e9fd9c46fb727` |

The first two hashes equal Q1's canonical artifacts; comparison retains Q1's
documented payload-type/null/numeric/error normalization. Parity does not test
the new binding; the direct integration suite does.

### Corrections and deviations recorded

Initial draft execution was **1 passed / 22 failed**, then 15/8 and 21/2 during
development, not qualification results. The missing mock-container child list
caused allocation throws; it was fixed. Test corrections removed a placeholder
and a tautology, corrected premature restart and listener-snapshot assumptions,
cleared intentional failure controls before healthy restarts, and fixed numeric
queue-count assertions and teardown-attempt counts. An important implementation
defect was corrected: a nested drain refusal must not itself stop the runtime
inside the outer drain.

Further review added deep/frozen config isolation, exact returned resource and
handle registration, stronger scoped teardown observations, control/yield
guards, actual core-record assertions, persistent unknown allocation/listener
obligations, and explicit-only retry after failed tick teardown. Final expanded
37-case execution and affected static checks pass. Initial analyzer inference
diagnostics and Selene shadowing/empty-branch/duplicate-branch findings were
corrected without editing the proven core or suppressing checks. A StyLua
format-only second-pass difference was applied and rechecked.

Two attempts to write an external temporary debug file were policy-denied in
the earlier part of the session. No permission/account/configuration was
changed. A workspace-local temporary debug file was used and deleted; fresh
parity outputs are now new-only in the experiment's Q4 evidence directory.
No unresolved executed test failure is reported as PASS.

## 8. Preservation evidence

Entry state: `main`, one commit ahead of origin, HEAD
`4661903d4f97cdb8d62adea89544741d3a00871c`. `opencode.json`, `status.md` and
`docs/IMPLEMENTATION_STATUS.md` already had modifications, with extensive
untracked work. No reset, clean, staging, commit or push occurred. Only the
agent-created debug helper was deleted. Existing historical sections and
handoffs are retained; current gameplay overview and §2.41 identify Q4.

Explicit working-file Git object identities match the historical Q3 values:

| Protected file | Working-file Git object ID |
| --- | --- |
| `.swarm/plan.md` | `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2` |
| `.swarm/plan.json` | `ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899` |
| `opencode.json` | `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd` |
| R13 decision report | `a739d0e0e6d011e9726e78a96165d890cdf4a1f7` |

A Q4 focused preservation manifest covers **149 existing paths** selected by
`git ls-files --cached --others --exclude-standard -- src tool tests
docs/evidence docs/C1E_C2B* experiments/gf001_npc_waves .swarm/plan.md
.swarm/plan.json opencode.json default.project.json`, sorted unique, excluding
the three new Q4 Luau files and `/q4_evidence/`. Hash each with read-only
`git hash-object`, join `path=objectID` rows with LF and no final LF, UTF-8
SHA-256. Before/after match:
`079f3a93537f5553335526357f8fcb130f3fb9016f87770f4facf1f3a35a00f1`.
The four explicit artifacts above are separately checked, including ignored
plan files. This is a focused Q4 consistency check; the historical R13
392/107-path manifests were not recomputed and are not claimed as new evidence.

Production `src/`, Loader, Rojo mapping, C1E-C2B R7–R13 code/tests/decisions,
approved plan and Task 1.1 are preserved. `PLAN_HASH: 2lnzncyys8pi5`; Task 1.1
remains unchecked/in progress. Both disabled MCP entries were read from disk.
Windows identity remains `desktop-hojha7u\juara`. No account, ACL, permission,
service, trusted writer, provisioning, dependency or toolchain change occurred.
No Studio/MCP/Open Cloud, Rojo-to-Studio, upload, asset generation, ComfyUI or
production integration was invoked. Whitespace checks pass; pre-existing
LF/CRLF Git advisories are not whitespace errors. HEAD and index remain unchanged.

## 9. Acceptance and remaining engine qualification

| Criterion | Verdict |
| --- | --- |
| AC-1 actual reusable binding; AC-2 unchanged core reuse | **PASS** — implemented module, real core composition, preserved source identities |
| AC-3 multiple mobs/listeners/run identities; AC-4 direct Luau integration | **PASS** — 37 executed cases, exact token/handle/record assertions |
| AC-5 scheduling/ownership/uncertainty safe failure; AC-6 no void-return false success | **PASS within the declared offline mock model** — explicit failure outcomes and scoped observations; real engine **NOT VERIFIED** |
| AC-7 existing GF-001 regressions/parity | **PASS** — §7 executed matrix |
| AC-8 offline isolation; AC-9 preservation | **PASS** — scoped additions, preserved dirty work and protected identities |
| AC-10 evidence distinction | **PASS** — interpreter/mock/static evidence separated from unverified Studio behavior |

Compared with Q3's test-local single-binding `probe()`, Q4 is a reusable
multi-binding composition root with private actual core state, injected ops,
multiple run identities, real wave/reward event flow, bounded queue, lifecycle
API, and retained obligations. Q3 remains historical design/probe evidence and
is counted separately.

**Still engine-dependent / NOT VERIFIED:** actual Instance/Humanoid type and
rig structure, exactly-one-Humanoid association, templates/placement/health,
Immediate/Deferred `Died` ordering and cancellation, receiver/API behavior on
engine values, real post-Destroy census and connection observations, engine
task resumption/cancellation, replication/network ownership, collision,
physics/navigation, memory/performance and damage/beneficiary provenance. The
private mock destruction ledger is not an available real Instance property;
a real ops implementation must establish a separately qualified scoped
observation policy and cannot translate `Parent == nil` into destruction proof.
Core record/event history is finite-campaign data, not an unbounded durable
service or process-crash recovery system.

### Minimum prerequisites for any future Studio integration

1. Separate written authorization for a named disposable place, exact temporary
   server-only scope, fixtures and restoration/census evidence. Q4-OFFLINE does
   not authorize this. Applicable live gates must be resolved; neither MCP entry
   may be enabled by inference from gameplay progress.
2. Review server ModuleScript packaging/bootstrap and a dedicated temporary
   test mapping. Current relative CLI `require` paths are not a qualified
   Studio packaging solution; keep production Loader/mapping isolated.
3. Implement and review a Roblox-specific ops boundary, permitted templates
   and trusted point map. Establish actual issuance, callback serialization,
   non-yield/cancellation behavior, allocation guarantees, connection
   observations, exact scoped teardown and unknown-resource recovery policy.
4. Review death eligibility/damage provenance before attributing any player
   benefit. Retain synthetic intents only; no payout or persistent state.
5. Execute a separately authorized matrix under Immediate and Deferred signals,
   including early/stale/duplicate callbacks, partial/throwing allocations,
   uncertain listeners, failed disconnect/destruction, overflow/reentry,
   interrupted retry/restart and baseline/post-cleanup census. Capture factual
   engine evidence and restore the exact temporary scope.

**Smallest useful next gameplay milestone (proposal only):** an independent
offline Q4 binding/API review and conformance check of the proposed real-ops
observation/cancellation policy. It can refine the narrow engine boundary before
any separately authorized disposable Studio qualification; it does not require
GF-002, a new NPC framework or production activation.

**STOP after GF-001-Q4-OFFLINE.** No GF-002, live Q4 Studio qualification, R14,
security provisioning, publication or production integration has begun. R13
remains latest completed security milestone; Gate A/B **BLOCKED**, D1–D6
**PENDING**. Current Windows account unchanged.
