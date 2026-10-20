# GF-001-Q1 — Direct Luau execution and Python parity qualification

## 1. Result and scope

**Result: PASS. Direct standalone Luau execution, authored-suite execution,
cross-language parity and strict Luau type analysis are all demonstrated.**
Review label: 2026-10-19 (harness date).

GF-001-Q1 is the separately authorized follow-up to GF-001's smallest proposed
milestone. It closes GF-001's main verification gap: the reusable Luau modules
under `experiments/gf001_npc_waves/luau/` were previously verified only by
StyLua/Selene and by a separate Python reference twin; no Luau runtime existed.

This milestone:

- Acquired and pinned one portable official Windows x64 Luau CLI release
  (bounded, disposable, offline-use; no installer, PATH, package manager or
  system change).
- Executed the authored `run_tests.luau` against the actual GF-001 Luau
  modules: **20 passed, 0 failed, exit 0** (AC-1/AC-2).
- Ran `luau-analyze` in both strict and default modes: initial 22 strict
  errors were fixed with narrow type-level corrections; final result is
  **0 errors in strict and default modes** (AC-4).
- Built a shared deterministic parity harness
  (`experiments/gf001_npc_waves/parity/`) that executes identical scenario
  vectors against both the real Luau modules and the Python reference twin:
  **12/12 vectors PASS, exit 0**, covering all ten required scenarios (AC-3).

Roblox Studio behavior, Humanoid events, networking, physics and performance
remain **NOT VERIFIED** — nothing here claims engine behavior. R13 remains the
latest completed security milestone. **Gate A and Gate B remain BLOCKED;
D1–D6 remain PENDING. STOP after GF-001-Q1; no GF-002, R14 or Studio
integration was started.**

## 2. Toolchain provenance and executable identity

### 2.1 Search before acquisition

`luau`, `luau-analyze` and `lune` were not found on PATH (`where.exe`), in
`%USERPROFILE%\.aftman\bin` (aftman/rojo/selene/stylua only), or in common
install locations (`~\.cargo\bin`, scoop shims, `~\bin`, `~\.local\bin`,
`C:\Program Files`, `C:\tools`, Luarocks). StyLua 2.5.2 and Selene 0.31.0 were
confirmed to be a formatter and a linter — neither executes Luau, and they
were not used as execution evidence.

### 2.2 Pinned official release

| Item | Value |
| --- | --- |
| Release | `luau-lang/luau` tag **0.743**, published 2026-10-16T20:48:51Z |
| Release page | https://github.com/luau-lang/luau/releases/tag/0.743 |
| Asset | `luau-windows.zip` (official Windows x64 portable archive) |
| Asset URL | https://github.com/luau-lang/luau/releases/download/0.743/luau-windows.zip |
| Asset size | 3,205,518 bytes |
| Official SHA-256 (GitHub API asset `digest`) | `9e019b584ea653e53781f1b9f25aa192175f2c057bbf88fc7f72e2720d710b31` |
| Locally computed archive SHA-256 | `9e019b584ea653e53781f1b9f25aa192175f2c057bbf88fc7f72e2720d710b31` — **MATCH** |

Layout check before use: the archive contains exactly four PE executables and
no installer, script or data file — `luau.exe`, `luau-analyze.exe`,
`luau-ast.exe`, `luau-compile.exe`. `luau-ast.exe`/`luau-compile.exe` were not
used.

| Executable | Size (bytes) | SHA-256 (self-computed) |
| --- | ---: | --- |
| `luau.exe` | 1,705,472 | `5246429297673bc845b947b135226d2f9e8cac77518c04269652486cf9a2383d` |
| `luau-analyze.exe` | 3,720,704 | `e8c8d1149b9ff97d154022be33829df62ac583a15683f3da33f8c15d5443b74f` |

Deployment: extracted to the bounded disposable directory
`C:\Users\juara\AppData\Local\Temp\opencode\luau-0.743\extracted\` and invoked
by absolute path only. No installer, package manager, service, driver,
Windows account, global PATH, system configuration, Aftman/toolchain or MCP
configuration change occurred. `luau.exe --version` is unsupported by this CLI
(`Error: Unrecognized option '--version'`); version identity is the pinned
release tag plus the recorded hashes. The archive hash was verified against the
official GitHub API asset digest before extraction.

**Identity limits:** the SHA-256 values above are self-computed local
consistency evidence tied to the pinned official asset URL and its
publisher-listed digest. No Authenticode/signature verification was performed,
and no publisher-authenticated binary identity is claimed from hashes alone.

## 3. Direct Luau execution of the authored suite

Exact command (from any directory; absolute path shown once):

```powershell
& "$env:TEMP\opencode\luau-0.743\extracted\luau.exe" `
  "C:\AI\slop\roblox-factory\experiments\gf001_npc_waves\luau\run_tests.luau"
```

Result: stdout `GF-001: 20 passed, 0 failed`, **exit 0**, empty stderr.

The suite requires `./Clock`, `./Config`, `./ExampleConfig`, `./MemoryAdapter`,
`./Mobs`, `./Rewards`, `./Rng`, `./SpawnPoints`, `./WaveRuntime` — the actual
on-disk reusable GF-001 modules, resolved by the CLI's relative require
semantics from the script's own directory. **No stub, copy, fake or parallel
implementation is involved, and no harness change was needed for module
loading: the suite ran unmodified on first execution.** Failures would have
remained visible: the suite accumulates failures, prints each
`GF-001 FAIL: <name>: <error>` and exits non-zero with
`error("[GF001] Luau test suite failed", 0)` when any case fails.

Per-case coverage is the authored GF-001 suite (all 20 cases listed in
`docs/GF_001_OFFLINE_NPC_WAVES.md` §5), now actually executed: example-config
validation and `startDelay` defaulting; 15 mutated invalid configurations plus
nil input; start/stop/restart transitions; global `maxActiveMobs` enforcement
(10 scheduled mobs under a cap of 3); spawn eligibility (delay, point capacity,
reuse after death); duplicate death and duplicate reward prevention; clear-gated
multi-wave progression and intermission; interrupted cleanup and restart
accounting; client reward rejection (server config as the only point source);
seeded deterministic replay (identical logs, different seed differs); the full
example scenario (8 spawned/killed, 3 waves, 96 points); constructor
config/deps guards; NaN/±Infinity rejection at 11 numeric paths plus the
Luau-specific sparse-array rejection; invalid damage refusal; once-only dead
instance cleanup; restart ID non-reuse and stale-callback refusal; adapter
spawn failure; adapter despawn failure with retained cleanup; reward recorder
guarding; injected RNG endpoint and invalid-source behavior.

## 4. Luau type analysis

Exact commands:

```powershell
& "$env:TEMP\opencode\luau-0.743\extracted\luau-analyze.exe" --mode=strict <all ten luau/*.luau files>
& "$env:TEMP\opencode\luau-0.743\extracted\luau-analyze.exe" <all ten luau/*.luau files>
```

Initial result: **22 strict-mode TypeError diagnostics** (identical set under
the default invocation because every file carries `--!strict`; the repo
`.luaurc` aliases are not needed by this experiment and no `.luaurc` change
was made). All 22 were fixed with narrow, type-level corrections (§5); the
final result is **0 errors and 0 warnings in both `--mode=strict` and the
default mode** for `luau/` and for the new `parity/` Luau files. These results
are `luau-analyze` typecheck evidence, recorded separately from StyLua/Selene
(parser/format/lint) results, which were re-run and also pass.

Strict analysis **is** established for these files (per-file `--!strict` plus
a clean `--mode=strict` run); no claim is made about files outside this
experiment. Note that the modules deliberately use runtime `type(...)` guards
over `any`-shaped data at their public boundaries, so strictness here means
"no analyzer diagnostics", not fully inferred domain types.

### 4.1 Initial diagnostics and root causes

| File (line) | Diagnostic | Root cause | Class |
| --- | --- | --- | --- |
| `Config.luau` 103/107/111 | `Type 'table' does not have key 'displayName'/'maxHealth'/'points'` | new-solver narrows the `mobDef` loop value to a keyless generic `table` after the `type(mobDef) ~= "table"` guard | solver refinement behavior on `any` data |
| `Config.luau` 231–234 | `Type 'unknown' does not have key 'mobId'/'count'/'spawnInterval'/'startDelay'` | `ipairs` over an `any`-typed `config.waves` yields `unknown` elements in the normalization loop | solver inference on `any` |
| `Rng.luau` 35 | `Cannot call a value of type *error-type* in union: *error-type* \| function` | the `type(source) == "function"` refinement is not carried into the captured closure | known new-solver closure-refinement limitation |
| `WaveRuntime.luau` 50-derived (135/147/148/156/169/184) | `Type 'nil' does not have key ...` | `local wave = nil` gave the state variable the inferred type `nil` for its whole scope | **genuine interface defect** (declaration annotation) |
| `WaveRuntime.luau` 81/129/231 | `Type 'unknown' does not have key 'id'/'state'` | same `ipairs(any)` → `unknown` pattern on `deps.mobs.all(registry)` | solver inference on `any` |
| `WaveRuntime.luau` 233/235 | `Key 'spawnPointId'/'id' not found in table '{ read state: "alive" }'` | after `mob.state == "alive"`, the new solver narrows the `any`-typed record to a table carrying only the tested key | solver refinement behavior on `any` |
| `run_tests.luau` 655 | `Type 'unknown' does not have key 'name'/'error'` | `local failures = {}` inferred an empty untyped table whose elements serialize as `unknown` | genuine annotation defect (test-local) |

## 5. Source corrections (all type-level or lint-level; no algorithm change)

All corrections are confined to `experiments/gf001_npc_waves/`. No Python
reference behavior was changed to make outputs match.

1. `luau/WaveRuntime.luau`: `local wave = nil` → `local wave: any = nil`
   (genuine defect: the wave definition variable is reassigned from validated
   config tables and must not be fixed to `nil`).
2. `luau/WaveRuntime.luau`: `findRecord`, `tick` and `stop` now alias
   `deps.mobs.all(registry)` into a `local allRecords: { any }` before
   `ipairs` (solver `unknown`-element workaround); `stop`'s alive branch uses
   `local record = mob :: any` before reading `spawnPointId`/`id` after the
   `mob.state == "alive"` refinement.
3. `luau/Config.luau`: `validateMobs` else-branch reads through
   `local def: any = mobDef`; the normalization loop reads through
   `local waveDef: any = wave` (same two solver patterns as above).
4. `luau/Rng.luau`: the injected-function branch binds
   `local sourceFunction = source :: () -> any` before the closure and calls
   that alias (closure-refinement limitation workaround).
5. `luau/run_tests.luau`: `local failures: { any } = {}` (test-local
   annotation).
6. Lint/format-level only: `parity/parity_run.luau` `projectEvents` uses
   `table.clone`; `parity/vectors.luau` one long line wrapped to StyLua
   formatting; experiment `README.md` pointers updated for the `parity/`
   directory and the now-executed suite.

Rationale: these expose real annotation mistakes where noted; the remainder
are explicit workarounds for the pinned analyzer's inference of `any`-shaped
runtime-validated data, not silencing (`--!strict` is retained everywhere and
strict mode finishes clean). **Behavior is unchanged**: after every correction
the 20-case suite, the parity chain (§6) and StyLua/Selene were re-run and
still pass; the deterministic `vectors.json`/`luau_results.jsonl` hashes were
identical before and after the edits that preceded them.

## 6. Cross-language parity

### 6.1 Harness

New files under `experiments/gf001_npc_waves/parity/`:

| File | Role |
| --- | --- |
| `vectors.luau` | Shared deterministic vectors (single source of truth): 12 scenarios — 2 `validate` vectors (18 + 2 mutations) and 10 `runtime` vectors with explicit ordered step schedules |
| `pjson.luau` | Minimal canonical JSON serializer for harness-owned projections (sorted keys; documented limits) |
| `dump_vectors.luau` | Dumps the vectors to canonical JSON (`vectors.json`) |
| `vectors.json` | Canonical dump consumed by the Python side (SHA-256 `465c11b29b7073ec4aa02b30814a896bf85f923aec5179e5424277fc6460629f`) |
| `parity_run.luau` | Executes every vector against the **real** `../luau/` modules via `require("../luau/...")` and prints one canonical JSON line per vector |
| `luau_results.jsonl` | Luau runner output (SHA-256 `f2b688256105e283c480a438227fd87df52d6a19432bc89bad819f3e63fd5d8c`) |
| `python_results.jsonl` | Python driver output for the identical vectors |
| `gf001_parity.py` | Python driver: runs the identical vectors against `python/gf001_core.py`, writes `python_results.jsonl`, structurally compares both outputs, prints the matrix, exits 0 only on full match |

Exact commands (PowerShell 5.1 `>` redirection writes UTF-16, so byte-exact
redirection uses `cmd /c`):

```powershell
$luau = "$env:TEMP\opencode\luau-0.743\extracted\luau.exe"
$p = "C:\AI\slop\roblox-factory\experiments\gf001_npc_waves\parity"
cmd /c "`"$luau`" `"$p\dump_vectors.luau`" > `"$p\vectors.json`""        # exit 0
cmd /c "`"$luau`" `"$p\parity_run.luau`" > `"$p\luau_results.jsonl`""    # exit 0
python experiments\gf001_npc_waves\parity\gf001_parity.py                # exit 0
```

Final output:

```
PASS 01a-invalid-config-rejections
PASS 01b-valid-config-and-start-delay-default
PASS 02-spawn-eligibility-and-deterministic-selection
PASS 03-global-and-per-point-active-caps
PASS 04-wave-timing-progression-and-completion
PASS 05-health-damage-and-death-transitions
PASS 06-duplicate-death-and-duplicate-reward-refusal
PASS 07-invalid-and-client-origin-reward-rejection
PASS 08-interrupted-cleanup-and-restart-accounting
PASS 09a-adapter-spawn-failure-retains-cleanup
PASS 09b-adapter-despawn-failure-withholds-completion
PASS 10-restart-monotonic-ids-and-stale-callback-refusal
GF-001-Q1 parity: 12 passed, 0 failed
```

Re-running the whole chain reproduces byte-identical `vectors.json` and
`luau_results.jsonl` (same SHA-256 values), demonstrating determinism.

Both sides genuinely exercise their own implementation: the Luau side
requires the on-disk `../luau/` modules (the same files the analyzer and
StyLua/Selene processed); the Python side imports `gf001_core.py` (the twin
executed by `tests/test_gf001_npc_waves.py`). Neither side reads the other's
results before producing its own; comparison happens afterwards in
`gf001_parity.py`.

### 6.2 Comparison semantics

Projections compared: per-step `{op, ok/reason/outcome/skipped/target/amount/raised,
status (10 fields), records (10 fields per record), eventCount}` and the final
full event log. Exact structural equality, with two precisely-scoped
equivalences and one exclusion, all documented in `gf001_parity.py`:

1. `payloadType` in `client_reward_rejected` events: each language reports its
   own type names (Luau `table`/`string`/... vs Python `dict`/`str`/...);
   both are normalized to the Luau names before comparison. This is a
   diagnostic-token difference only — the rejection behavior, event count,
   reason string and absence of any reward intent are compared exactly.
2. JSON `null` ≡ absent key: Lua tables cannot store `nil` (an absent key
   *is* `nil`), so nulls are dropped from both sides before comparison.
3. Numeric representation: Python `int`/`float` compare equal to a Luau
   number of the same value (textual `1` vs `1.0` differences are
   representation, not behavior); booleans never compare equal to numbers.
   Adapter-raised errors are compared via stable markers
   (`adapter_spawn_failed`/`adapter_despawn_failed`) matched by substring on
   each language's own exception text, because Luau runtime errors carry
   `file:line:` prefixes that Python exceptions do not.

### 6.3 Parity matrix (required scenarios)

| Required scenario | Vector(s) | Demonstrated (identical in both languages) |
| --- | --- | --- |
| 1. Invalid configuration | 01a (18 mutations incl. NaN/±Infinity), 01b | Every mutation rejected (`ok:false`); error counts equal (per-mutation, incl. 4 combined errors when `mobs` is emptied while waves still reference it); valid example accepted; removed `startDelay` defaults to 0; explicit delays preserved |
| 2. Spawn eligibility and deterministic selection | 02 | Delay gate (nothing spawns before `startDelay`); per-point capacity blocking; freed capacity reused after death; seeded tie-break chooses `east-gate`/`north-gate`/`south-gate` identically |
| 3. Global/per-point active caps | 03 | `active` never exceeds `maxActiveMobs = 2`; all 10 scheduled mobs spawn over time; point occupancy respected; wave completes |
| 4. Wave timing and progression | 04 | Full example: 3× `wave_started`, 3× `wave_completed`, 1× `all_waves_completed`; 8 mobs; intermission and per-wave `startDelay` phases progress identically per tick/advance schedule |
| 5. Health damage and death transitions | 05 | Partial damage decrements to exact health values; lethal damage → `died` + health 0; post-death damage/kill → `ignored`; zero/negative/NaN/string/boolean damage → `invalid_damage` with state and health unchanged |
| 6. Duplicate death and duplicate reward refusal | 06 | Exactly one `mob_died` and one `reward_intent` per mob; all repeat damage/kill calls ignored; no duplicate events |
| 7. Invalid/client-origin reward rejection | 07 | Both client requests emit `client_reward_rejected` and produce **no** intents; only the server kill produces one `reward_intent` with points 40 from server config |
| 8. Completion and interrupted cleanup | 04, 08 | Completion: all 8 instances cleaned once, `stop` after completion returns false, later ticks `not_running`, 96 total points. Interruption: both `wave_stopped` events report `activeCleaned: 2`; pending queue cleared; restart resets per-run accounting |
| 9. Adapter failure and retained cleanup obligations | 09a, 09b | Spawn failure raises, no `mob_spawned` event, `totalSpawned` stays 0, partial allocation cleaned by `stop`; despawn failure raises, completion withheld (zero `wave_completed`), record retained and cleaned exactly once after restore, reward not repeated |
| 10. Restart semantics and monotonic mob IDs | 08, 10 | IDs continue `mob-0003`/`mob-0004` after restart; stale `mob-0001` kill/damage returns `unknown_mob`; the new-run mob stays alive; no stale-callback reward |

Independent corroboration: vector 04's totals (8 spawned/killed, 3 waves, 96
points) equal the values asserted by the GF-001 Python suite and the Luau
suite, so the parity harness is demonstrably exercising the same behavior
those suites pin down.

## 7. Regression and auxiliary checks

| Exact command | Result |
| --- | --- |
| `luau.exe ... luau/run_tests.luau` | **20 passed, 0 failed, exit 0** (Luau execution — not a Python test) |
| `luau-analyze.exe --mode=strict ...` (all `luau/` + `parity/` `.luau`) | 22 initial errors → fixed → **0 errors** |
| `luau-analyze.exe ...` (default mode) | **0 errors** |
| `stylua --check experiments/gf001_npc_waves/luau` and `.../parity` | exit 0 both |
| `selene experiments/gf001_npc_waves/luau` and `.../parity` | exit 0, 0 errors/0 warnings/0 parse errors both |
| `python experiments/gf001_npc_waves/parity/gf001_parity.py` | **12/12 PASS, exit 0** (executes both implementations) |
| `python -m unittest discover -s tests -p "test_*.py"` | **523 run, 522 passed, 1 existing symlink skip, 56.748s** (includes GF-001's 20 Python reference tests; unchanged by Q1) |
| `python -m compileall -q experiments/gf001_npc_waves/parity/gf001_parity.py experiments/gf001_npc_waves/python/gf001_core.py` | exit 0 |
| `python tool/registry.py validate` | PASS: 0 unique assets, 0 events |
| `python tool/validate_art.py` | PASS (2 metaschemas, 5 presets, 3 positive/36 negative fixtures; no files written) |
| `git diff --check` | exit 0; LF→CRLF advisories only (pre-existing) |
| `git diff --no-index --check -- NUL <each of the 9 new files>` | exit 1 = differences from empty (expected); **0 whitespace findings** per file |

Python tests, Luau executions and static checks are distinguished above; the
Python suite result is historical-reference evidence and does not substitute
for the Luau rows.

## 8. Preservation evidence

- Entry state matched GF-001's exit: `main` at
  `4661903d4f97cdb8d62adea89544741d3a00871c` (unchanged), three already
  modified tracked paths (`docs/IMPLEMENTATION_STATUS.md`, `opencode.json`,
  `status.md`) and the existing untracked work; nothing staged, committed,
  pushed or cleaned. Q1 additionally edits only `status.md`,
  `docs/IMPLEMENTATION_STATUS.md`, this report, the experiment README and the
  GF-001 experiment files listed in §5/§6.
- Read-only manifest reproduction (R13 §1.2 method: `git ls-files`,
  `git hash-object -- <path>` without `-w`, `Sort-Object -Unique`, SHA-256
  over UTF-8 LF-joined `path=object` rows without trailing LF; Q1's new paths
  excluded exactly as GF-001's were):
  - **392/392 paths**, manifest
    `f884d1290a685feffd592b3a47b3f3fbee508a93bfa9781149914f5bafa26ba0` —
    **matches** the historical R13/GF-001 value.
  - **107/107 security/source/test/evidence/config paths**, manifest
    `56dca6a22ef5686a14fe97c13e215b35e18f1748b4204148d6eb8c01b53cf3fe` —
    **matches**.
- Explicit protected artifacts: `.swarm/plan.md` object
  `5b06f8973d9871296ef0e17c44fdd8d7a0962ed2`, file SHA-256
  `DBF77AD2F79F32DCC3CB8AF8E8E6CB25D2FDB8052B213D3198C138D83000ED46`;
  `.swarm/plan.json` object `ff0fa4c6cf67cf2dbfdf09a67b5b5a9651f62899`;
  `opencode.json` object `50f1db7d3ff2332baf8e15f428b1e11bb0d37edd`, SHA-256
  `6C2656F8245444E0B169F1501E7312716615F409D90CC9AB04A76BC9E6E7BB32`
  (both project MCP entries still disabled on disk); R13 report object
  `a739d0e0e6d011e9726e78a96165d890cdf4a1f7`. All **unchanged**.
- No production `src/`, `default.project.json`, Rojo/Aftman tool configuration,
  C1E-C2B security code, assets, registry event, `.swarm/plan.md`/`plan.json`
  or unrelated file was touched. No Studio/MCP access, ComfyUI call, upload,
  Windows account/ACL/service/credential change or dependency install
  occurred. The Python reference twin `gf001_core.py` was **not** modified.

## 9. Remaining differences and limitations

1. **Language-diagnostic differences (documented, normalized):** rejection
   diagnostics use different label indexing (Python 0-based vs Luau 1-based
   `spawnPoints[n]`/`waves[n]` labels) and payload type-token names; parity
   compares outcome and error *counts*, not diagnostic text. Do not infer
   byte-identical cross-language logs.
2. **Luau-only case:** the sparse-array rejection has no Python equivalent
   (Python lists cannot be sparse); it is covered only by the executed Luau
   suite.
3. **Type analysis:** strict mode is clean, but public boundaries are
   intentionally `any`-shaped runtime-validated data; full inferred domain
   types were not attempted. The analyzer itself has no `--version` flag and
   was identified by pinned release + hashes only (no signature check).
4. **Parity harness trust:** the comparator (`gf001_parity.py`) is a new
   component whose correctness is corroborated by the known-value vector 04
   and by 12/12 agreement, but it has no independent unit-test suite of its
   own; a future milestone may add one. `pjson.luau` serializes only
   harness-owned projections (documented in-file).
5. **Not verified here (unchanged from GF-001):** Roblox Studio engine
   behavior, real NPC instances, Humanoid events, movement, networking,
   physics, target-device performance, and any live/persistent integration.
   The portable Luau CLI is a host-language interpreter, not the Roblox
   engine; passing here does not predict engine behavior.
6. **Disposable toolchain:** the pinned CLI lives in a temp directory that may
   be cleaned; re-acquisition is exactly reproducible from the pinned release
   URL + SHA-256 in §2. No repo configuration depends on it.

## 10. Future Studio integration prerequisites

Unchanged from `docs/GF_001_OFFLINE_NPC_WAVES.md` §8 (finish direct Luau
testing — now done; separate authorization naming a disposable non-production
place and precise temporary scope; a separately reviewed test mapping keeping
the production Loader from auto-starting the prototype; a minimal server-owned
synthetic-instance adapter with run-bound callbacks; an authorized in-engine
run verifying real caps/positions/death/cleanup/stale callbacks and counts).
Any MCP route remains subject to the existing Gate A/Gate B blockers; this
milestone grants no exception.

## 11. Acceptance criteria

| Criterion | Verdict | Evidence |
| --- | --- | --- |
| AC-1: Actual standalone Luau execution demonstrated | **PASS** | Pinned official 0.743 CLI; §2–§3 commands, output, exit codes |
| AC-2: Authored Luau tests exercise the real GF-001 modules | **PASS** | Relative requires of the on-disk modules; 20/20 passed unmodified; failures would exit non-zero |
| AC-3: Deterministic Python–Luau parity for the agreed scenarios | **PASS** | 12/12 shared-vector scenarios; all ten required behaviors in §6.3; byte-identical reruns |
| AC-4: Luau type-analysis results recorded accurately | **PASS** | 22 initial strict errors, root causes, fixes, 0 final in both modes; kept separate from StyLua/Selene |
| AC-5: No Studio/MCP/live production activity | **PASS** | Offline only; no Studio, MCP, upload, ComfyUI or persistent game data access |
| AC-6: Security work, approved plan, config and unrelated files preserved | **PASS** | 392/392 and 107/107 manifests + explicit plan/config/report object IDs unchanged (§8) |
| AC-7: Status and report distinguish PASS/QUALIFIED/BLOCKED/NOT VERIFIED | **PASS** | This report and `status.md` §2.38; engine items remain NOT VERIFIED; Gates A/B BLOCKED; D1–D6 PENDING |
| AC-8: No unauthorized dependency/system/account/configuration change | **PASS** | Portable pinned binary in a disposable directory; no installer/PATH/service/account/Aftman/MCP change |

**Verdict: GF-001-Q1 PASS.** GF-001's Luau execution/parity qualification
gap is closed at the prototype level; engine integration remains a separately
authorized future milestone. **STOP after GF-001-Q1. No GF-002, R14, Studio
integration or provisioning is started. Gate A and Gate B remain BLOCKED;
D1–D6 remain PENDING.**
