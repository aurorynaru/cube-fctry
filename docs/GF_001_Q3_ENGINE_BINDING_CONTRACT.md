# GF-001-Q3 — Engine-binding contract qualification

**Verdict: QUALIFIED as an offline design and mock-contract review; real Roblox
engine binding NOT VERIFIED.** Review label: 2026-10-20 (harness date). One
agent, selected OpenCode model `openai/gpt-6-sol` (session-provided identity);
no Swarm. This report does not implement an engine adapter or authorize Studio.
R13 remains the latest completed security milestone. Gate A and Gate B remain
**BLOCKED**; D1–D6 remain **PENDING**.

## 1. Baseline and exact gap

The Q1 direct Luau suite (20 cases) and Python–Luau parity (12 vectors) test the
pure wave core. Q2 (16 direct Luau cases) composes that core with a synthetic
factory. `WaveRuntime` expects synchronous `adapter.spawn(record, point)` and
`adapter.despawn(record)` returning **exactly `true`** before spawn or cleanup is
acknowledged. On failure it retains the record; the host catches the error and
stops/cleans before restart. `Mobs` makes death one-way; `Rewards` emits a
once-only server-config **intent**, never a grant, and rejects client claims.
`Config.validate` supplies plain-data definitions and spawn-point IDs. Records
and normalized mob/point tables share mutable references, so the host must keep
them server-owned and not expose them as writable views.

Q2's `SyntheticMobFactory` issues tables in a private map; table fields
`OwnerToken`, `MobRecordId`, `MobId`, `SpawnPointId`, `Humanoid`, `Destroyed` and
boolean-returning dot-style `Disconnect`/`Destroy` help its own test model.
`SyntheticMobAdapter` ties a new token to each run, checks issuance plus those
fields, forwards active synthetic `Died` to `runtime.killMob(record.id)`,
disarms then disconnects/destroys, and permanently refuses restart for
uncertain creation/connection. Q2 explicitly assumes synchronous, non-yielding,
non-reentrant calls and callback dispatch. Its PASS remains valid **only for
that synthetic contract**; it cannot be reused directly with engine values.

### Official API facts versus implementation assumptions

| Difference / source | Documented fact | Consequence and proposed boundary |
| --- | --- | --- |
| Connection [API][connection], signal [API][signal] | `RBXScriptSignal:Connect(fn)` returns an `RBXScriptConnection`; `RBXScriptConnection:Disconnect(): ()` returns **nothing**; `Connected` is a boolean property. | Q2 lines 72 and 108 call unbound functions via dot and demand `disconnected == true`. Use `signal:Connect(fn)` and `connection:Disconnect()` with the receiver. Inspect `Connected == false` as a *connection-specific observation* and track each issued handle; neither a void return nor `pcall` proves all resources cleaned. A failed/read-uncertain disconnect retains an obligation. |
| Instance [API][instance] | `Instance:Destroy(): ()` returns **nothing**; documented effects include `Parent = nil`, locked parent, connection disconnection and descendant destruction. `Parent = nil` can also mean a still-live unparented object. | Q2 lines 114–116 require `destroyed == true` and a synthetic `Destroyed` field. Neither exists as that engine verification contract. Call on the exact owned instance, check expected ancestry/removal and tracked connections after the call, and distinguish *observed scoped teardown* from proof of global memory release. Void or `pcall` success alone cannot acknowledge cleanup. |
| Instance/Humanoid [APIs][instance][humanoid] | Instances are engine objects; `Humanoid` is an Instance in a Model; `Health`/`MaxHealth` and `Died` are engine members. `Instance.Name` is mutable and non-unique; `UniqueId` is not script-readable. | `type(...) == "table"`, synthetic fields and a string name cannot authenticate or type real values. Use `typeof(value) == "Instance"`, `:IsA("Model")`/`:IsA("Humanoid")`, exact captured references and server-private issuance; verify one intended Humanoid in the owned model, correct parent/root and server-held definition. Type and ancestry checks are proposed runtime checks, not observed Studio results. |
| Receiver syntax [APIs][signal][instance] | Official examples use `signal:Connect(fn)` and `instance:Destroy()`. | Dot invocation without explicitly passing the receiver is wrong for these methods. Keep engine calls behind a narrow boundary; the existing synthetic factory's dot functions remain synthetic-only. |
| Signal scheduling [guide][deferred] | `Workspace.SignalBehavior` controls immediate/deferred handlers; `Default` currently equals Immediate but is documented to change. Deferred handlers resume at resumption points; the guide warns that destruction may leave pending handlers to run, whereas explicit `Disconnect()` drops pending invocations under the documented deferred pattern. Immediate handlers can run nested/reentrantly. | Q2's synchronous `Die()/Fire()` is not a scheduling oracle. Disarm **before** disconnect/destroy, capture run/binding identity and recheck at dispatch. Queue/refuse callbacks during creation, tick, cleanup or stop. Never assume a callback cannot arrive after a destroy attempt; test both signal modes in Studio later. |
| Humanoid death [API][humanoid] | The Humanoid docs describe health reaching zero and `Died`; rig structure and state affect behavior. | The mock's `Die()` setting zero then firing synchronously does not establish real event timing, rig validity, death attribution or client trust. A server callback must validate the still-issued model/Humanoid and an authorized server-side cause; a client-reported kill or displayed health/name alone cannot mint a reward. |

[connection]: https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptConnection
[signal]: https://create.roblox.com/docs/reference/engine/datatypes/RBXScriptSignal
[instance]: https://create.roblox.com/docs/reference/engine/classes/Instance
[humanoid]: https://create.roblox.com/docs/reference/engine/classes/Humanoid
[deferred]: https://create.roblox.com/docs/scripting/events/deferred

The signatures, `Connected`, documented `Destroy` effects, non-unique names,
unavailable script `UniqueId`, Humanoid properties/events and immediate/deferred
behavior above are **official documentation**, fetched read-only. Whether a
specific NPC rig, `Died` ordering, callback cancellation, a failed method's
partial side effects or post-destroy resource census behave as expected in a
particular place is **NOT VERIFIED**. `pcall` reports only whether the protected
Lua call threw; it is not a teardown receipt.

## 2. Smallest future server-only wrapper

One server Script/composition root, one run-scoped binding table and a narrow
engine factory are sufficient; do not introduce a general object manager. The
wrapper owns `Config.validate`'s input snapshot, clock, `WaveRuntime`, rewards,
spawn definitions and the engine-created run container. The existing core sees
only plain records, `{id, capacity, position}` point data and its existing
boolean adapter acknowledgments. A separately reviewed server-only template
selection maps each configured mob ID to a permitted NPC model; a separately
reviewed point map binds each configured ID to one trusted server-selected
transform. Both maps are immutable for the run. Set up a cloned/new Model and
its Humanoid off-world where feasible, then parent only the prepared owned model
into the exact run container. Validate rig, position, ancestry and server-owned
health before enabling death forwarding; physical clearance/navigation and
actual replication remain later engine checks.

**Minimum interface between core and engine boundary (design, not implemented):**

```text
beginRun() -> runToken, ownedContainer | failure/uncertain
create(record, point) -> exactly true | false/error
  internally: allocate -> immediately ledger-register every exact Instance
  -> validate Model/Humanoid/point -> connect and ledger-register handle
  -> publish/activate; failed partial allocations remain ledger obligations
despawn(record) -> exactly true ONLY for observed, complete owned teardown
  otherwise false/error plus diagnostic {run, record, resource, phase, observation}
drainDeathEvents() -> serialized, validated runtime.killMob(record.id) calls
stopAndReport() -> {known obligations, failed/unknown resources, restartAllowed}
```

The GF-001 adapter signatures remain `spawn(record, point)` and
`despawn(record)`; the extra lifecycle/report operations belong to the
server-owned composition root, not `WaveRuntime`. No boolean returned by an
engine method is used as their success value. The wrapper produces `true` only
after its own narrowly defined checks have succeeded and all **known** resource
obligations for that record are accounted for. An unknown allocation/listener
cannot be converted to success by observing a different object disappear.

For each run, mint an unexposed identity token; for each `record.id`, retain a
private issuance entry `{runToken, exact record reference, record.id, mobId,
spawnPointId, exact Model reference, exact Humanoid reference, owned container,
connections, phase}`. Maintain a reverse map by exact Instance reference.
Register an allocated reference immediately, **before** another fallible step.
Display names, attributes/tags, `GetFullName`, client-supplied IDs, model
children found by name and an unreadable `UniqueId` do not establish issuance.
Check exact record/run/type/point and model/Humanoid relationship on every
death and teardown; if an object was moved/replaced or identity is ambiguous,
disarm and quarantine rather than deleting a foreign object. Only delete
objects created/issued in the private ledger. An owned run container may aid a
scoped census, but never `ClearAllChildren()` or destroy a folder containing
unverified descendants.

The signal callback closes over the binding and enqueues only a candidate
`{runToken, exact binding, exact Humanoid}`. At a serial dispatch boundary,
verify the binding is active and still issued, the same run/record is running
and alive, the model/Humanoid identities and allowed server death condition
hold, and no earlier death has been accepted; then invoke the existing
`killMob(record.id)` once. `Mobs`/`Rewards` supply a second duplicate guard.
Never invoke `killMob` inline from `Connect`, during `WaveRuntime.tick()`'s
spawn loop, or during teardown. Immediate callbacks while constructing are
held/inert, followed by server-side state reconciliation **before activation**;
if the death state/cause cannot be safely resolved, refuse that spawn/run. A
bounded queue drained without yielding on the same server execution lane is a
proposed serialization policy; overflow, concurrent entry or any yield during
a critical transition faults/stops the run rather than replaying events.
Deferred candidates are revalidated when drained; disconnect/disarm is still
required even if callbacks are thought to have been cancelled.

Never expose `runtime.killMob`, `damageMob`, `recordDeath`, mutable records,
config or issued references to clients. A client RemoteEvent, if added in a
different milestone, can submit only a damage *request* subject to separate
server verification/rate limits/attribution; it cannot report an authoritative
death or amount. There is no payout consumer, balance or DataStore here.
`reward_intent` is not a grant or player-credit determination. A live reward
system needs independent beneficiary/damage-provenance design.

## 3. Allocation, cleanup and uncertainty rule

1. Allocate only under the owned run. Ledger-register each returned root and
   any independently allocated child/connection before proceeding. If a call
   throws after allocation but before the caller can capture/register a
   reference, record **unknown allocation**, disarm/stop and prohibit restart;
   `false, nil` is accepted as no-allocation only from a factory that can
   actually establish that invariant. A returned known partial object stays
   eligible for exact-owned cleanup. A `Connect` that throws or fails to return
   a handle may already have installed a listener: mark unknown listener even
   if the known model is later removed.
2. Disarm the binding before teardown. Disconnect each recorded connection
   with the proper receiver; read `Connected == false` for each handle after a
   nonthrowing call. On throw, unreadable state or still-connected handle,
   retain the obligation and withhold `despawn == true`. Do not rely on
   `Destroy` to discard queued callbacks; do not drop a handle before checking
   it. A later retry is only for an exact-known owned resource and must be
   serialized. Unexpected listener side effects make the run uncertain.
3. With handles accounted for, call `model:Destroy()` on the exact issued root
   only. Check its expected removal from the owned hierarchy and census of all
   independently owned roots/connections; `Parent == nil` alone cannot
   distinguish destruction from unparenting, and `Destroyed` is not an Instance
   property. On throw, unexpected descendants, mismatch, missing reference,
   unaccounted event handle or contradictory observations, report uncertainty,
   retain the ledger/recovery evidence and withhold acknowledgment/restart.
   A nonthrowing `Destroy()` plus expected observations can satisfy a *scoped
   application cleanup policy* after engine qualification, not prove memory
   reclamation or absence of hidden engine work.
4. A failed `spawn` must not emit `mob_spawned`; `WaveRuntime` retains the
   record and the host calls stop/cleanup. A failed `despawn` must not set
   `record.cleaned`, complete a wave or permit restart. After a partial stop,
   explicitly retry only known owned resources; never reset an unknown state
   to success because `runtime.stop()` is false or the model is no longer in
   Workspace. If runtime has already marked completed but a wrapper-level
   obligation remains, report `cleanup_unverified` and refuse another run.

This is an **in-process server ownership policy**, not authentication against
compromised server code or an engine-level proof that every reference was
released. The scoped census, known allocations and connected-handle observations
must be tested with real objects before choosing an acknowledgment criterion.

## 4. Evidence and targeted findings

| Class | Actual Q3 evidence / limit |
| --- | --- |
| Direct interpreter | Existing pinned Luau 0.743 `luau.exe` SHA-256 `5246429297673bc845b947b135226d2f9e8cac77518c04269652486cf9a2383d` matched Q1/Q2; `run_tests.luau`: **20 passed**; `run_adapter_tests.luau`: **16 passed**. Fresh parity runner and Python comparator: **12/12 passed**; Python reference unittest: **20 passed**. These exercise core/Q2, not real engine objects. |
| New synthetic mock | `run_engine_contract_tests.luau`: **11 passed, 0 failed** under the same actual standalone CLI. Receiver-required `Connect` and void teardown calls; `Connected`/parent observations; private issuance despite display-name mutation; foreign-object refusal; known allocation before listener registration; inline/cleanup/stale callback suppression; ambiguous Connect, failed Disconnect/retry, thrown/silent Destroy and restart refusal. The probe is deliberately a small test-local decision model, not an engine adapter or proof of Roblox scheduling/destruction. |
| Static/type analysis | Pinned `luau-analyze.exe` SHA-256 `e8c8d1149b9ff97d154022be33829df62ac583a15683f3da33f8c15d5443b74f` matched; strict and default analysis of all GF-001 `luau/*.luau` and `parity/*.luau`: **exit 0**, no diagnostics. StyLua `--check` PASS; Selene **0 errors, 0 warnings, 0 parse errors**. Static tools cannot verify engine APIs at runtime. |
| Official engine API facts | Read-only Roblox Creator Hub references and deferred-events guide linked in §1. No Studio call. |
| Engine behavior not verified | Actual Instance creation/Destroy side effects, `Connected` observation timing, Humanoid rig/`Died`/health ordering, immediate/deferred dispatch in a place, server/client damage provenance, physics/spawn clearance, replication, interruption recovery, instance/connection census and memory/performance. |

Commands actually used from the repository root (the parity output files were
written under the pre-existing `%TEMP%\opencode` directory, not over Q1's
historical artifacts):

```powershell
& "$env:TEMP\opencode\luau-0.743\extracted\luau.exe" experiments\gf001_npc_waves\luau\run_engine_contract_tests.luau
& "$env:TEMP\opencode\luau-0.743\extracted\luau.exe" experiments\gf001_npc_waves\luau\run_adapter_tests.luau
& "$env:TEMP\opencode\luau-0.743\extracted\luau.exe" experiments\gf001_npc_waves\luau\run_tests.luau
$exe = "$env:TEMP\opencode\luau-0.743\extracted\luau.exe"
$runner = "experiments\gf001_npc_waves\parity\parity_run.luau"
$out = "$env:TEMP\opencode\gf001-q3-luau-results.jsonl"
cmd /c "`"$exe`" `"$runner`" > `"$out`""
python experiments\gf001_npc_waves\parity\gf001_parity.py --luau-results "$env:TEMP\opencode\gf001-q3-luau-results.jsonl" --out "$env:TEMP\opencode\gf001-q3-python-results.jsonl"
python -m unittest tests.test_gf001_npc_waves -v
$files = @(rg --files experiments/gf001_npc_waves/luau experiments/gf001_npc_waves/parity -g '*.luau')
& "$env:TEMP\opencode\luau-0.743\extracted\luau-analyze.exe" --mode=strict $files
& "$env:TEMP\opencode\luau-0.743\extracted\luau-analyze.exe" $files
& "$env:USERPROFILE\.aftman\bin\stylua.exe" --check experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity
& "$env:USERPROFILE\.aftman\bin\selene.exe" experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity
```

No unrelated full Python repository suite was rerun in Q3. After the final
additional Connect-receiver probe, the targeted 11-case CLI and affected-file
strict/default analyzer, StyLua and Selene checks were rerun and passed.

**Exact defects/corrections qualified:** Q2's boolean-success tests on
`Disconnect`/`Destroy` and its synthetic `Destroyed` field are incompatible
with engine API signatures; dot-style unbound calls omit the required receiver.
Q2's table type checks/field identity are synthetic-only. Q2's inline death
forwarding is unsafe as an engine scheduling assumption because it can enter
the core mid-spawn, and its callback registration can miss a death before
activation. Q2's assumed no-allocation or known partial result is a factory
contract to enforce, not a property of arbitrary throwing engine construction.
No defect in the proven wave algorithms was demonstrated; **no core or Q2
source changed**. The correction is a proposed separate engine boundary,
explicit refusal policy and isolated tests, not a claim of integration.

## 5. Preservation, acceptance and next scope

Entry `git status --short --branch`: `main...origin/main [ahead 1]` with
pre-existing modifications to `status.md`, `docs/IMPLEMENTATION_STATUS.md`,
`opencode.json`, extensive untracked work and an empty staging area. HEAD
`4661903d4f97cdb8d62adea89544741d3a00871c`. No workspace `AGENTS.md`;
approved `.swarm/plan.md` marker `PLAN_HASH: 2lnzncyys8pi5`, Task 1.1
unchecked/in progress. Q3 changes only this new report, one new isolated
Luau mock suite and additive status/handoff entries. Protected object IDs at
entry: plan.md `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2`, plan.json
`ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899`, `opencode.json`
`50f1db7d3ff2332baf8e15f428b1e11bb0d37edd`, R13 report
`a739d0e0e6d011e9726e78a96165d890cdf4a1f7`.

Exit: HEAD and staging area unchanged; all four protected Git object IDs
match entry. Plan.md original-file SHA-256 still
`DBF77AD2F79F32DCC3CB8AF8E8E6CB25D2FDB8052B213D3198C138D83000ED46`;
`opencode.json` original-file SHA-256 still
`6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32`.
Both project MCP entries still have `enabled: false` on disk; loaded state is
unknown. `git status --short --branch` retains the entry modified/untracked
inventory plus only the new Q3 report (the experiment directory was already
untracked and now contains one additional Q3 test). `git diff --check` reports
no whitespace errors; new-file no-index checks have no whitespace diagnostics
(native exit 1 means difference from empty, not test failure). Git's LF/CRLF
advisories are not whitespace errors. The historical R13 392/107-path
manifests were **not** recomputed in Q3; protected explicit artifacts and
the unchanged scope were checked directly. No stage, commit, push or cleanup.

| Acceptance | Verdict |
| --- | --- |
| AC-1 API mismatches; AC-2 ownership/cleanup contract; AC-3 no void-return false success | **QUALIFIED** — documented API facts, source anchors and proposed check/uncertainty rules; actual engine acknowledgment criterion NOT VERIFIED |
| AC-4 new tests execute in standalone Luau | **PASS** — 11/11 synthetic probes on pinned CLI |
| AC-5 GF-001 regressions | **PASS** — 20 core, 16 Q2 adapter, 12 parity, 20 Python reference; strict/default/static checks pass |
| AC-6 isolation/offline; AC-7 security/config/plan preservation | **PASS** — scoped Q3 edits, unchanged protected IDs/hashes and disabled on-disk entries; no Studio/MCP/production mapping or security change |
| AC-8 design distinct from engine verification | **PASS** — engine behavior explicitly NOT VERIFIED |

**Smallest proposed next gameplay milestone, not authorized here:** a separately
authorized, disposable non-production **GF-001-Q4 Studio binding qualification**,
after applicable live-gate resolution and an exact temporary place/server-only
test mapping are approved. Implement only this narrow wrapper and a minimal
known-owned rig. Record baseline and post-run scoped Instance/connection census;
exercise both immediate/deferred signal settings, valid/duplicate/early/stale
death, client-origin claim refusal, partial allocation/Connect failure,
Disconnect/Destroy ambiguity, restart refusal and cleanup/recovery without
currency grant. Review server damage provenance and callback ordering. Restore
the exact temporary scope and retain factual before/after evidence. Production
integration, GF-002 and reward payout remain separate decisions.

**STOP after GF-001-Q3.** No Roblox Studio/Studio MCP, MCP activation,
production Loader, `src/`, `default.project.json`, Rojo-to-Studio, save,
upload, publish, ComfyUI, dependency installation, Windows account/ACL/service
provisioning, security R7–R13 or approved-plan/task edit, Git staging/commit/
push, GF-002, R14 or live integration is authorized or undertaken. R13 is the
latest completed security milestone; Gate A/B **BLOCKED**, D1–D6 **PENDING**.
