# GF-001 — Offline NPC/Mob Wave Prototype (isolated, non-production)

Reusable, game-mode-independent NPC/mob wave spawning prototype implemented for
milestone GF-001. **Isolated and non-production:** nothing here is mapped by
`default.project.json`, loaded by the main game, or executed in Roblox Studio.

- `luau/` — the reusable Luau modules (pure Luau, no Roblox engine APIs) plus
  `run_tests.luau`, a deterministic test suite. GF-001 could only lint/parse it
  (no local Luau runtime); GF-001-Q1 later executed it under a pinned portable
  official Luau CLI (see `docs/GF_001_Q1_LUAU_PARITY_QUALIFICATION.md`).
- `python/gf001_core.py` — the Python reference twin used for the executed
  offline verification (`tests/test_gf001_npc_waves.py`) and for the
  GF-001-Q1 cross-language parity comparison.
- `parity/` — GF-001-Q1 cross-language parity harness: shared deterministic
  vectors (`vectors.luau`, canonical dump `vectors.json`), a Luau runner
  (`parity_run.luau`) that executes the real `../luau/` modules, and the Python
  driver/comparator (`gf001_parity.py`) that runs the identical vectors against
  `python/gf001_core.py` and compares both outputs. Evidence and exact commands:
  `docs/GF_001_Q1_LUAU_PARITY_QUALIFICATION.md`.
- `luau/SyntheticMobAdapter.luau`, `luau/SyntheticMobFactory.luau` and
  `luau/run_adapter_tests.luau` — GF-001-Q2 server-owned offline adapter,
  minimal synthetic Instance/Humanoid/Signal seam and directly executed Luau
  scenarios. This is not a Roblox engine adapter or Studio evidence; see
  `docs/GF_001_Q2_ADAPTER_SIMULATION.md`.

Full contract, architecture, verification evidence and Studio integration plan:
`docs/GF_001_OFFLINE_NPC_WAVES.md`.
