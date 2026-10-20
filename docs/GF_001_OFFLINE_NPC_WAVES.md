# GF-001 — Offline reusable NPC/mob waves

## 1. Result and scope

**Result: QUALIFIED offline prototype. Luau behavioral execution and Studio
integration: NOT VERIFIED.** Review label: 2026-10-19 (harness date).

GF-001 supplies reusable Luau components under
`experiments/gf001_npc_waves/luau/`. They operate on plain tables and injected
dependencies, independently of a game mode or Roblox services. The example has
three synthetic mob types, four spawn points and three finite waves.

The available environment provided StyLua/Selene but no callable `luau` or `lune`
runtime. No tool or dependency was installed. Consequently:

- **PASS:** Luau formatting and lint/parser checks on all ten Luau files.
- **PASS:** 20 executed deterministic tests of the **separate Python reference
  twin**, using stepping time, seeded/injected randomness and in-memory adapters.
- **NOT VERIFIED:** execution of the reusable Luau implementation, its authored
  20-case Luau suite, cross-language behavioral parity, and Luau type analysis.
- **NOT VERIFIED:** Roblox Studio playtesting, real NPC spawning or cleanup,
  Humanoid events, movement, networking, engine performance and player combat.

The Python tests are useful specification/reference evidence; they are **not
tests executing the Luau source**. This qualification is the main remaining
gameplay verification gap.

Single agent; no Swarm/delegation. The experiment is outside every mapping in
`default.project.json`; production `src/`, Rojo mapping and tool configuration
were preserved. No Studio/MCP access, experience save/upload/publish, assets,
ComfyUI, player data, persistent currency, Windows identity/ACL/service change or
security provisioning occurred. R13 remains the latest completed security
milestone. **Gate A and Gate B remain BLOCKED; D1–D6 remain PENDING.**

## 2. Files and architecture

| File under `experiments/gf001_npc_waves/luau/` | Interface / responsibility |
| --- | --- |
| `Config.luau` | `validate(raw) -> (ok, normalizedOrErrors)`. Validates finite numeric fields, positive counts/capacities/health, nonnegative integer points, unique spawn IDs, mob references and dense wave/spawn arrays. Defaults `startDelay` to zero. |
| `Clock.luau` | `new(nowFunction)`, `stepping(startAt?)` with `now()` / `advance(delta)`. Inject time; no ambient timers or Roblox heartbeat. |
| `Rng.luau` | `new(seedOrFunction)` with `nextFloat()` / `pick(array)`. Lehmer generator, multiplier 48271/modulus 2147483647, or injected values in `[0,1)`. Invalid source values and nonfinite seeds refuse. |
| `Mobs.luau` | `new(nextId?)`, `spawn(registry, definition, mobId, spawnPointId, now)`, `damage(record, amount, now)`, `kill(record, now)`, `despawn(record, now)`, `aliveCount(registry)`, `all(registry)`. Plain records and one-way health/death transitions. |
| `SpawnPoints.luau` | `select(points, occupancy, rng) -> pointOrNil`. Excludes full points; chooses among least-occupied eligible points using injected RNG. |
| `Rewards.luau` | `new({events})` with `recordDeath(record, definition, now)` and `handleClientRequest(playerId, payload, now)`. Validated synthetic point intents once per dead record; client claims always reject. |
| `MemoryAdapter.luau` | `new()` with synchronous `spawn(record, point)` / `despawn(record)` returning `true`, and call-history arrays. Pure synthetic runtime adapter; no instances created. |
| `WaveRuntime.luau` | `new(normalizedConfig, deps)` with `start()`, `tick()`, `damageMob(id, amount)`, `killMob(id)`, `stop(reason?)`, `records()`, `status()`. Scheduling, maximum active count, progression and cleanup. |
| `ExampleConfig.luau` | Three synthetic mob definitions and the sample spawn/wave data. |
| `run_tests.luau` | Authored deterministic suite, composed through relative CLI requires. Parsed/linted, **not executed** here. |

Other new files:

- `experiments/gf001_npc_waves/README.md`: experiment entry point.
- `experiments/gf001_npc_waves/python/gf001_core.py`: explicitly non-production
  Python reference transcription, standard library only.
- `tests/test_gf001_npc_waves.py`: executed reference tests, following the
  repository's existing unittest discovery convention.
- This report. Only `status.md` and `docs/IMPLEMENTATION_STATUS.md` were additionally
  edited for the GF-001 handoff; both already had unrelated modifications.

The existing production tree contains a generic shared Loader, server/client
loader entry points and placeholder Services/Controllers folders. The Loader's
`Init()`/`Start()` discovery convention is not used to auto-load this experiment.
Existing configuration was inspected: Rojo 7.7.0, StyLua 2.5.2, Selene 0.31.0
pins; `stylua.toml` Luau syntax/sorted requires; `selene.toml` Roblox standard;
`.luaurc` existing aliases. No `AGENTS.md` was found in the workspace.

## 3. Configuration and composition

The complete example is `luau/ExampleConfig.luau`:

| Mob ID | Display name | Health | Synthetic points |
| --- | --- | ---: | ---: |
| `dummy` | Training Dummy | 30 | 5 |
| `crawler` | Stone Crawler | 60 | 12 |
| `golem` | Vein Golem | 150 | 40 |

Four spawn points (`north/east/south/west-gate`) each have capacity 2 and numeric
`{x,y,z}` positions at cardinal offsets of 40. These are data, not existing world
objects. Global `maxActiveMobs = 6`; `interWaveDelay = 1.5` seconds.

```lua
waves = {
    { mobId = "dummy", count = 4, spawnInterval = 0.5, startDelay = 0 },
    { mobId = "crawler", count = 3, spawnInterval = 1, startDelay = 1 },
    { mobId = "golem", count = 1, spawnInterval = 1, startDelay = 2 },
}
```

Composition after loading the module tables (the Luau suite shows CLI loading):

```lua
local ok, config = Config.validate(ExampleConfig)
assert(ok, "invalid NPC wave configuration")
local events = {}
local clock = Clock.stepping(0)
local adapter = MemoryAdapter.new()
local rewards = Rewards.new({ events = events })
local waves = WaveRuntime.new(config, {
    clock = clock,
    rng = Rng.new(20261018),
    adapter = adapter,
    events = events,
    mobs = Mobs,
    selectSpawn = SpawnPoints.select,
    rewards = rewards,
})
waves.start()
waves.tick()
clock.advance(0.5)
waves.tick()
```

This is an interface example, **not an executed Studio script**. Core modules
have no sibling `require` dependency: the composition root injects module tables.
The CLI suite uses `require("./Module")`; a future Studio bootstrap would require
server-owned ModuleScripts and supply the same dependencies.

## 4. State transitions and contracts

### Wave scheduling

`idle -> running -> completed` or `running -> stopped`. A wave runs
`delay -> spawning -> clearing`; subsequent waves pass through
`intermission -> delay`. The wave index advances to the upcoming wave during
intermission; `wave_started` is the indicator that it has actually begun.

- Call `Config.validate` first. The runtime constructor checks basic shape and
  required dependencies; it is **not a substitute for full validation**.
- The host calls `tick()` serially. Clock values must be finite, monotonic
  seconds. No real sleeping, task scheduling or background loop is started.
- Spawn eligibility requires running/spawning state, pending mobs, an elapsed
  interval, global active count below the cap, and a spawn point below capacity.
- A positive interval permits at most one spawn per tick. Its next deadline is
  `actualSpawnTime + spawnInterval`; missed intervals do not cause catch-up
  bursts. A zero interval fills only available global/point capacity.
- Logical occupancy counts living mobs assigned to a point for their lifetime;
  it is not a distance, navigation, collision or physical-safety test.
- Intermission expiry changes to delay; a subsequent tick starts that wave.
  Completion requires no pending/living mobs and successful cleanup of dead
  records. The last wave emits `all_waves_completed` exactly once.

### Mob lifecycle, death and cleanup

Records start `alive`; positive finite damage reduces health, lethal damage or a
server `killMob` changes to `dead`. Further damage/kill calls are ignored. Zero,
negative, nonfinite and nonnumeric damage refuse without changing health.
Death releases logical occupancy, emits `mob_died`, and asks the reward recorder
for an intent. The next tick releases the dead instance through the adapter.

`cleaned` is a separate successful adapter-cleanup acknowledgment. Dead records
can remain `dead` for inspection after cleanup. `stop(reason)` cleans every
outstanding record, including a dead record or a failed-spawn partial allocation;
living records become `despawned`. It clears pending spawns and emits
`mob_despawned` for living records plus `wave_stopped`. Repeat stop after a
successful stop/completion returns false.

Restart resets per-run stats/records but retains increasing mob IDs within that
runtime, so old callbacks cannot target replacement mobs. It does not clear the
event sink or reseed RNG. IDs are **not globally unique across different runtime
objects**; future engine callbacks must also be bound to their runtime/run.

### Adapter and data ownership

`spawn(record, point)` and `despawn(record)` must synchronously return exactly
`true` on success. `despawn` must be idempotent and tolerate partial creation.
False results or thrown errors raise; no successful spawn/completion is reported
for that failure. The record remains available for cleanup. On an adapter
exception, the host must catch it, stop spawning and call `stop("adapter_failure")`;
failed cleanup must retain the record and be resolved before restarting. Only
the memory adapter has been tested; real resource cleanup is not established.

Dependencies are trusted, non-yielding and non-reentrant. Do not call back into
the runtime while an adapter call is in progress. `records()` returns a copied
list of **shared mutable records**; validated config also shares mob/spawn
tables. Treat these as server-owned read-only views while running. Mutable
server data and ordinary function calls do not constitute an authentication or
network boundary. Historical records/events are not memory-bounded for an
unlimited campaign; this prototype uses small finite wave lists.

### Reward authority

The only intended producer of `reward_intent` is the server death transition.
The recorder requires a dead/unrewarded record and finite nonnegative integer
points from the server-held definition. It marks that record rewarded once.
The event contains `type`, `mob`, `mobId`, `points`, `at`; it is a **synthetic
intent**, not a balance update or grant. `handleClientRequest` always emits
`client_reward_rejected` and returns nil, regardless of claimed kills or amounts.

There is no RemoteEvent wiring, persistent balance, DataStore, purchase, player
beneficiary/kill-credit calculation, or payout consumer. The host must keep
runtime/config/records/recorder server-only and must never directly expose
`damageMob`, `killMob` or `recordDeath` as client-authoritative endpoints.

## 5. Executed verification and evidence boundaries

Commands were run from the repository root with existing tools. The Aftman bin
directory was not on this shell's PATH, so tools were invoked by their existing
absolute location. No installation or configuration change was needed.

### Luau formatting/lint — PASS

```powershell
& "$env:USERPROFILE\.aftman\bin\stylua.exe" --check experiments/gf001_npc_waves/luau
& "$env:USERPROFILE\.aftman\bin\selene.exe" experiments/gf001_npc_waves/luau
```

Final StyLua exit 0; Selene exit 0, **0 errors, 0 warnings, 0 parse errors**.
StyLua formatting was applied only to the new experiment. These are parser,
format and lint results, not Luau behavior or `--!strict` typecheck results.

### Executed logic tests / synthetic adapters — PASS for Python reference only

`python -m unittest tests.test_gf001_npc_waves -v`: **20 passed, zero skips,
0.011s**. Every new test uses synthetic mob records and memory adapters; no
Roblox instances or live clients are involved.

| Test method suffix in `Gf001NpcWaveTests` | Verified reference behavior |
| --- | --- |
| `example_config_validates_and_fills_start_delay_defaults` | Valid example and omitted-delay default |
| `invalid_configurations_are_rejected` | 15 mutated invalid configurations plus nil/non-table input |
| `wave_start_and_stop_transitions` | Idle/start/double-start/stop/restart and non-running tick |
| `maximum_active_mob_enforcement` | Cap of 3 while 10 scheduled mobs spawn and clear |
| `spawn_eligibility_requires_running_state_delay_and_capacity` | Delay, capacity blocking and reuse after death |
| `duplicate_death_and_duplicate_rewards_are_prevented` | Repeated damage/kill yields one death and one reward |
| `wave_completion_progresses_through_all_waves` | Clear-gated progression, intermission and final completion |
| `cleanup_after_interruption_and_clean_restart` | Active cleanup, queue cancellation and reset |
| `untrusted_client_reward_requests_are_always_rejected` | Forged amount/kill/text claims reject; shared sink records rejection; only server death emits points |
| `deterministic_replay_with_the_same_seed` | Equal seed/clock/action schedule yields equal full event logs; alternate seed differs |
| `full_example_scenario_completes_with_validated_rewards` | 8 spawned/killed, 3 completed waves, 8 intents totaling 96 synthetic points |
| `wave_runtime_rejects_invalid_config_and_deps` | Basic constructor guard and missing dependency refusal |
| `nonfinite_configuration_values_are_rejected` | NaN/+Infinity/-Infinity at 11 numeric field paths |
| `invalid_damage_cannot_heal_or_poison_health` | Bad damage inputs leave state/health/rewards unchanged |
| `dead_instances_are_cleaned_once_before_wave_completion` | 8 mock instance cleanups, no duplicates or repeat completion |
| `restart_does_not_reuse_ids_for_stale_death_callbacks` | Old record ID cannot kill new-run mob |
| `adapter_spawn_failure_is_not_a_successful_spawn` | Injected false spawn reports no success; partial record remains cleanable |
| `cleanup_failure_prevents_completion_and_can_be_retried` | Injected false despawn withholds completion/ack; stop cleans later without repeat reward |
| `reward_recorder_rejects_living_invalid_and_duplicate_deaths` | Living/invalid-point calls refuse, one valid dead-record intent |
| `injected_randomness_and_invalid_rng_inputs` | Injected selection endpoints, invalid source/seed and empty-list refusals |

`luau/run_tests.luau` authors corresponding scenarios (including a Luau-specific
sparse-array rejection). **None of those Luau tests were executed.** The Python
and Luau versions share intended algorithms, not a tested cross-language binding.
For example, rejection diagnostics use Python `dict`/`str` payload type names
versus Luau `table`/`string`, and validation indexes differ by language. Do not
infer byte-identical cross-language logs or exhaustive equivalence.

### Existing offline regressions / auxiliary checks — PASS

| Exact command | Final result |
| --- | --- |
| `python -m unittest discover -s tests -p "test_*.py"` | **523 run, 522 passed, 1 skipped, 68.678s**. Existing `test_asset_registry.RegistryTests.test_symlink_escape` skip; no new skips. R12's historical 503 + GF-001's 20 = 523. |
| `python -m compileall -q experiments/gf001_npc_waves/python/gf001_core.py tests/test_gf001_npc_waves.py` | Exit 0 |
| `python tool/registry.py validate` | PASS: 0 unique assets, 0 events |
| `python tool/validate_art.py` | PASS: 2 metaschemas, 5 presets, 3 positive/36 negative fixtures; no files written |
| `git diff --check` and new-file `git diff --no-index --check -- NUL <path>` | PASS: tracked check exit 0; all 14 new files have zero whitespace failures. LF-to-CRLF advisories only. No-index status 1 means differences from empty; whitespace diagnostics are checked separately. |

The existing regression suite uses its existing synthetic Windows children and
disposable stores, not a real Studio connection. Rojo build/serve/sourcemap was
not needed for this unmapped experiment and was not run. Studio-dependent checks
remain **NOT VERIFIED**.

### Development findings

Early Python runs exposed 1-based-to-0-based RNG indexing and module-method
binding mistakes. Subsequent failures exposed a max-active test driver that did
not drain its final mobs, an incorrect instant-spawn phase expectation, and a
test diagnostic format error. These were corrected without weakening existing
repository assertions. Early format/lint issues (line endings, unused test
variables) were corrected locally. Final review added finite-value guards, dead
record cleanup, adapter-failure assertions and non-reused restart IDs, followed
by the final 20-test/523-test runs above. No remaining executed test failure is
reported as a pass.

## 6. Git and preservation evidence

Entry Git status: `main`, HEAD
`4661903d4f97cdb8d62adea89544741d3a00871c`, one commit ahead of `origin/main`.
`status.md`, `docs/IMPLEMENTATION_STATUS.md` and `opencode.json` were already
modified; substantial source/evidence/generated/untracked work was present.
Nothing was staged, committed, pushed or cleaned.

The R13 §1.2 preservation method was reproduced with read-only `git ls-files`,
`git hash-object` (no `-w`), PowerShell `Sort-Object -Unique`, and SHA-256 over
UTF-8 LF-joined `path=Git-object-ID` rows without a trailing LF. New GF-001 paths
were excluded. Results match the historical R13 manifests:

| Preserved set / explicit artifact | Result |
| --- | --- |
| All 392 original tracked/untracked paths plus explicit approved plans, excluding R13's three deliverables as specified by R13 | **PASS**, manifest `f884d1290a685feffd592b3a47b3f3fbee508a93bfa9781149914f5bafa26ba0` |
| R13's 107 security/source/test/evidence/config paths | **PASS**, manifest `56dca6a22ef5686a14fe97c13e215b35e18f1748b4204148d6eb8c01b53cf3fe` |
| `.swarm/plan.md` | Git object `5b06f8973d9871296ef0e17c44fdd8d7a0992ed2`; original-file SHA-256 `DBF77AD2F79F32DCC3CB8AF8E8E6CB25D2FDB8052B213D3198C138D83000ED46` unchanged |
| `.swarm/plan.json` | Git object `ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899` unchanged |
| `opencode.json` | Git object `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd`; SHA-256 `6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32` unchanged; both project MCP entries disabled on disk |
| R13 report | Git object `a739d0e0e6d011e9726e78a96165d890cdf4a1f7` captured during final review for recheck |

The broader set covers main source/mapping, original art/assets/reports and
unrelated files without researching their contents. The R13 report is checked
separately because R13's own manifest excluded it. Git object checks normalize
according to Git's existing filters; they are local consistency evidence, not
signatures or authenticated storage. Ignored caches/harness telemetry and
external files are outside these sets. Only agent-created temporary debug/check
scripts were removed; no unrelated file was deleted. One external temporary
helper-file write was policy-denied; that path was not retried.

Plan marker remains `PLAN_HASH: 2lnzncyys8pi5`; Task 1.1 stays unchecked/in
progress. No Swarm plan/task edit occurred. Actual loaded MCP state remains
unknown; the on-disk disabled entries were never activated.

Final recheck after documentation edits again matches the 392-path manifest and
the explicit R13 report/plan/config object IDs above. The final inventory has
**247 paths = R13's 232 entry paths + its report + 14 new GF-001 files**. Filtering
out those additions reproduces R13's original path/status digest
`bb6627dc0c05fff261ed11ceb2a21a61c81073c09088844c801d2c5d2bc6bc0c`.
The staged diff is empty and HEAD is unchanged. Tracked whitespace check exit 0;
all 14 new-file whitespace checks PASS, LF-to-CRLF advisories only. Existing
tracked diff statistics include pre-existing work and are not GF-001 edit counts.

## 7. Acceptance criteria

| Criterion | Verdict | Evidence / qualification |
| --- | --- | --- |
| AC-1: Reusable game-mode-independent NPC wave logic | **QUALIFIED** | Config-driven pure Luau components and documented seams; only reference behavior executed |
| AC-2: Deterministic offline core verification | **QUALIFIED** | 20 Python reference cases PASS; actual Luau execution and cross-language parity NOT VERIFIED |
| AC-3: Server authority; no client reward claims | **QUALIFIED** | No remote/grant/balance path; rejection and server-config-only intent cases PASS in reference; future server-only binding/engine integration NOT VERIFIED |
| AC-4: No live Studio/upload/persistent game mutation | **PASS** | Offline tools/mocks only, no live integration/asset/persistent data calls |
| AC-5: C1E-C2B security code/decisions preserved | **PASS** | Matching 107/392-path R13 manifests and separate R13-report check; pending decisions unchanged |
| AC-6: Approved plan/task unchanged | **PASS** | Both plan IDs unchanged; Task 1.1 unchecked |
| AC-7: Accurate status and documentation | **PASS** | Additive status/handoff; executed reference, static Luau and unverified engine results distinguished |
| AC-8: Future Studio requirements without live readiness claim | **PASS** | Explicit sequence below; no integration authorization inferred |

## 8. Reuse and smallest future milestone

An arena, defense, dungeon room or survival mode can supply its own mob IDs,
health/points, spawn-point data, cap and finite waves. It can consume
`wave_started`, `wave_completed`, `all_waves_completed` and `reward_intent`
events for its own objectives/presentation. Reuse the core unchanged; inject
mode-specific selection/adapters rather than importing mode rules into it.
No behavior-tree, pathfinding, targeting or large NPC framework is included.

**Smallest recommended next gameplay milestone (proposal only): standalone
Luau execution/parity qualification.** Under separate authorization for any
required tool acquisition, provide a pinned standalone Luau runtime, execute the
authored suite on the actual modules, run Luau type analysis, and compare a
defined canonical state/event projection against the reference. Replace or
retire the duplicate Python twin after obtaining direct Luau evidence. No
Studio access is needed for this step. No GF-002 work has begun.

### Future authorized Studio integration plan (not executed)

1. Finish direct Luau testing first. Resolve any divergence and specify callback
   run binding, adapter exception behavior and config/view immutability.
2. Obtain separate authorization naming a disposable non-production place and
   precise temporary scope. Any MCP route remains subject to the existing Gate
   A/Gate B blockers; GF-001 grants no exception or permission to enable it.
3. Keep production mapping intact; prepare a separately reviewed test mapping
   with server-only modules/bootstrap. Do not let the generic production Loader
   discover or auto-start the prototype.
4. Implement a minimal server-owned adapter using temporary synthetic instances:
   exact owned folder/run identity; template-to-record association; monotonic
   server clock; serialized heartbeat ticks; server-validated damage and
   Humanoid/death mapping; disconnect every callback and destroy only owned
   instances on cleanup. No asset uploads, persistent currency or purchases.
5. In the separately authorized run, verify real maximum counts, eligible
   positions/collision, death/reward duplicate handling, cleanup on interruption
   and partial failure, stale callbacks, and all wave completion events. Check
   instance/connection counts before and after, and device/server performance.
   Review attribution and exploit resistance before ever adding a reward consumer.
6. Retain factual engine evidence and limitations; restore the temporary scope
   and stop. Any production integration, persistence or publishing would need
   its own authorization and design review.

**STOP after GF-001. R14, GF-002, provisioning and live integration are not
started. Gate A/B remain BLOCKED; D1–D6 remain PENDING.**
