# GF-001-Q2 — Offline synthetic mob adapter simulation

## Result and boundary

**PASS for the scoped standalone Luau/mock model; Roblox engine integration NOT VERIFIED.**
Review label: 2026-10-20 (harness date). This is an isolated, server-owned
simulation, not a Studio playtest or a production adapter. GF-001's existing
`WaveRuntime`, `Mobs`, `Rewards`, validated configuration, clock, RNG and spawn
selection are reused without algorithm changes. Nothing is mapped into Rojo or
loaded by `src/`.

R13 is still the latest completed security milestone. Gate A and Gate B remain
**BLOCKED** and D1–D6 **PENDING**. Q2 does not alter their approval or scope.

## Architecture and contracts

New files under `experiments/gf001_npc_waves/luau/`:

- `SyntheticMobAdapter.luau` composes the existing `WaveRuntime.new(config,
  deps)` and implements its exact synchronous `adapter.spawn(record, point)` /
  `adapter.despawn(record)` interface. The caller first uses `Config.validate`.
  The session exposes `start()`, `tick()`, `stop(reason?)`, `status()` and
  `clientRewardClaim(player, payload)`; it deliberately does not expose
  `killMob`, `damageMob`, mutable records or a reward-grant endpoint.
- `SyntheticMobFactory.luau` is the minimal **synthetic** Instance/Humanoid/
  Signal/connection stand-in. Its injected `create(record, point, token)` returns
  `(true, object)`, `(false, nil)` for a known no-allocation failure, or
  `(false, object)` for a known partial allocation. Its private issuance table
  backs `owns(object, token)`. Objects carry `synthetic`, `OwnerToken`,
  `MobRecordId`, `MobId`, `SpawnPointId`, `Humanoid`, `Destroyed`; the synthetic
  Humanoid has `Health`, `Died.Connect(callback)` and `Die()`. Connections have
  `Disconnect()`. The mock has explicit failure switches and a callback snapshot
  only to exercise stale-listener behavior. No actual Roblox globals are read.
- `run_adapter_tests.luau` executes the real GF-001 Luau modules together with
  these two new files under the pinned standalone Luau CLI.

The caller supplies the validated config plus server-held `factory`, `clock`,
`rng`, `events`, `mobs`, `selectSpawn`, `rewards`, and `waveRuntime` module. A
fresh table token is allocated for every run, including restart. The adapter
associates each returned object with its exact GF-001 record and attaches its
synthetic `Humanoid.Died` callback. A callback only forwards to the existing
`runtime.killMob(record.id)` when its binding is active, the run token matches,
the binding is still registered, factory issuance and identity fields match,
the runtime is running, and the record is alive. The core then performs the
once-only `Mobs.kill` transition and `Rewards.recordDeath` intent. The adapter
does not compute points or pay currency. `clientRewardClaim` delegates solely
to the existing unconditional `Rewards.handleClientRequest` rejection.

Cleanup first disarms callbacks. `despawn` requires private factory issuance
**and** matching token, record, mob type and Humanoid identity. It disconnects
the owned connection, then destroys the owned synthetic object, and only then
acknowledges the core's `cleaned` record. A failed disconnect or destroy retains
the binding for retry on `stop`; it does not acknowledge cleanup or completion.
Missing bindings represent known zero-allocation failures. A foreign object,
unknown ownership or altered identity is never destroyed. Successful cleanup
removes the binding, so repeated stop/cleanup cannot destroy twice. A failed
tick stops the core, clears pending work and disarms listeners; a failed stop
must be retried explicitly, and ticks cannot resume that faulted run.

Creation exceptions, a claimed successful creation without an object, failed
or ambiguous listener registration, and unknown ownership permanently mark
that session uncertain. Even if a known object is subsequently cleaned, no
success/restart is reported for the uncertain run: out-of-band resources cannot
be proven absent. A false creation result with nil is trusted as a strict
no-allocation contract; a false result with a verified-owned object is cleaned
on stop. Restart is permitted only after known-complete cleanup, with no
bindings and no uncertainty. Runtime IDs also remain monotonic within a
runtime, but the fresh token guards even against cross-runtime ID reuse.

## Executed tests and corrections

Existing portable release `luau-lang/luau` 0.743 was already available at
`%TEMP%\opencode\luau-0.743\extracted\`. Recomputed SHA-256 matched Q1's pins:
`luau.exe` `5246429297673bc845b947b135226d2f9e8cac77518c04269652486cf9a2383d`,
`luau-analyze.exe` `e8c8d1149b9ff97d154022be33829df62ac583a15683f3da33f8c15d5443b74f`.
No replacement was installed or downloaded. Commands below ran from the repo
root; executable variables expand to these existing paths.

| Executed command | Result |
| --- | --- |
| `& "$env:TEMP\opencode\luau-0.743\extracted\luau.exe" experiments\gf001_npc_waves\luau\run_adapter_tests.luau` | **16 passed, 0 failed, exit 0**, direct Luau execution of adapter, mock and core |
| Same CLI with `experiments\gf001_npc_waves\luau\run_tests.luau` | **20 passed, 0 failed, exit 0**, original direct Luau suite |
| Same CLI with `experiments\gf001_npc_waves\parity\parity_run.luau` redirected to `%TEMP%\opencode\gf001-q2-luau-results.jsonl`; `python experiments\gf001_npc_waves\parity\gf001_parity.py --luau-results <that path> --out %TEMP%\opencode\gf001-q2-python-results.jsonl` | **12/12 PASS, exit 0**, fresh Luau and Python reference execution; historical parity artifacts untouched |
| `python -m unittest tests.test_gf001_npc_waves -v` | **20 passed, zero skips** against the separate Python reference |
| `luau-analyze.exe --mode=strict <all luau/*.luau and parity/*.luau>` and default invocation on same files | **0 diagnostics** in both modes |
| `stylua.exe --check experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity` | **PASS**, exit 0 |
| `selene.exe experiments\gf001_npc_waves\luau experiments\gf001_npc_waves\parity` | **PASS**, 0 errors, 0 warnings, 0 parse errors |

The 16 adapter cases cover: successful creation and exact identity; three
simultaneous mobs; all three existing waves and 8 objects/96 synthetic points;
death callback forwarding; duplicate events and disconnection; unknown/altered
identity and foreign-factory object refusal; no-allocation spawn failure;
verified-owned partial allocation cleanup; throwing creation; claimed success
without object; ambiguous connect; failed destroy with withheld completion and
retry; failed disconnect with disarmed event and retry; interrupted cleanup and
repeat cleanup; stale callback after restart; and forged client claim rejection.
The synthetic signal's saved callback is invoked directly after disconnection
to test the guard, not to claim Roblox delivers disconnected callbacks.

Initial adapter suite: **12 passed, 1 failed** because the test incorrectly
expected a session already marked uncertain by an ownership mismatch to become
successful after metadata restoration. The assertion was corrected to require
conservative `cleanup_unverified` even though the reverified object is removed.
Initial strict analysis found five inference errors (`any`/unknown binding
elements and refined read-only properties), corrected by explicit binding/
listener annotations and a narrowed factory-function alias; StyLua layout was
also corrected. Subsequent cases added foreign-object, nil-success and full
three-wave coverage. Final tests and static checks above all pass.

These are **actual Luau interpreter executions of simulated Roblox-like
behavior**, not Studio or real Humanoid/Instance evidence. No Python test is
substituted for the Luau adapter suite.

## Assumptions and unverified engine behavior

- Factory, signal dispatch, connection/disconnection, destroy, clock and
  WaveRuntime calls are synchronous, non-yielding, serial and non-reentrant.
  `Connect` does not fire inline before the binding is active; `Destroy` does
  not emit `Died`; callbacks do not interleave with `spawn`, `tick` or `stop`.
- `(false, nil)` means no allocation or listener exists. A throwing factory
  violates the returned-object contract and remains uncertain. The factory's
  private issuance table and dependencies are trusted server-side; mutable
  synthetic fields alone are never proof of ownership. This is not a security
  boundary against a compromised server process or hostile injected factory.
- Synthetic `Die()` sets `Health` to zero and synchronously fires `Died`; repeat
  `Fire()` may occur. The core uses `killMob`, rather than treating a client
  event or arbitrary Humanoid health value as authority. The mock does not
  simulate real Humanoid lifetime, damage attribution, physics, `Died` ordering,
  ancestry, replication, destruction races, deferred signals or task scheduling.
- Object and callback history in the test factory is only for observation;
  released objects remain reachable there. No persistent currency, DataStore,
  player credit, purchases, RemoteEvent or payout consumer exists.

Before any separately authorized Studio test: resolve the applicable live
gates, name a disposable non-production place and temporary scope, review a
server-only test mapping/bootstrap isolated from the production Loader, define
real Instance/Humanoid/connection ownership and death-damage provenance,
serialize real engine callbacks and heartbeat ticks, specify what happens on
yield/reentrancy/destruction ambiguity, and capture baseline/post-cleanup
instance/connection counts. Test real spawn positions, health/death timing,
duplicate/stale callbacks, partial creation and failed cleanup without a
client-authoritative reward path. No such engine test has been executed here.

## Preservation and acceptance

Only the three new Luau files, this report, the experiment README, project
`status.md` and appended `docs/IMPLEMENTATION_STATUS.md` handoff are Q2 edits.
The pre-existing dirty/untracked work remains. Git HEAD is still one commit
ahead of origin; no staging, commit or push. Production `src/`, Rojo mapping,
Loader, Q1 core/parity files, Python reference, R7–R13 security modules, plan
and config were not changed by Q2. Read-only Git object checks match Q1/R13:
`.swarm/plan.md` `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2`,
`.swarm/plan.json` `ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899`,
`opencode.json` `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd`,
R13 report `a739d0e0e6d011e9726e78a96165d890cdf4a1f7`.
`git diff --check` passed (existing LF/CRLF advisories only); staged diff is
empty. The `opencode.json` modification was present at entry, and its original
file SHA-256 remains `6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32`;
both project MCP entries remain disabled on disk; loaded state is unknown.
No Studio/MCP, ComfyUI, upload/save/publish, dependency install, Windows
account/ACL/service/credential change or Swarm plan/task change occurred.

| Acceptance | Verdict |
| --- | --- |
| AC-1 core reuse; AC-2 simulated object/event adapter; AC-3 direct Luau execution | **PASS** — real core injection, 16 direct Q2 cases |
| AC-4 ownership, duplicate/stale callback, cleanup | **PASS within mock model** — explicit fault and restart cases; engine **NOT VERIFIED** |
| AC-5 client claims/currency | **PASS within mock model** — client rejection, server-config-only synthetic intents; no balance path |
| AC-6 offline/production isolation; AC-7 security/plan preservation | **PASS** — scoped additions and checked protected artifacts |
| AC-8 evidence distinction | **PASS** — mock assumptions and real-engine gaps stated above |

**Smallest recommended next gameplay milestone (proposal only):** GF-001-Q3
offline real-engine binding contract/readiness review, specifying the server
bootstrap, exact ownership/teardown semantics and a disposable Studio test
matrix. Any actual Studio execution needs separate authorization and the
applicable Gate A/B resolution. **STOP after GF-001-Q2.** No GF-002, R14,
provisioning or live integration begins.
