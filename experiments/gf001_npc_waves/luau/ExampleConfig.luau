--!strict
-- GF-001 offline NPC wave prototype: example configuration.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Synthetic
-- game-mode-independent example: three mob types, four spawn points and three
-- waves. Any game mode replaces this data with its own mob/spawn/wave table.

return {
	maxActiveMobs = 6,
	interWaveDelay = 1.5,
	mobs = {
		dummy = {
			displayName = "Training Dummy",
			maxHealth = 30,
			reward = { points = 5 },
		},
		crawler = {
			displayName = "Stone Crawler",
			maxHealth = 60,
			reward = { points = 12 },
		},
		golem = {
			displayName = "Vein Golem",
			maxHealth = 150,
			reward = { points = 40 },
		},
	},
	spawnPoints = {
		{ id = "north-gate", capacity = 2, position = { x = 0, y = 1, z = -40 } },
		{ id = "east-gate", capacity = 2, position = { x = 40, y = 1, z = 0 } },
		{ id = "south-gate", capacity = 2, position = { x = 0, y = 1, z = 40 } },
		{ id = "west-gate", capacity = 2, position = { x = -40, y = 1, z = 0 } },
	},
	waves = {
		{ mobId = "dummy", count = 4, spawnInterval = 0.5, startDelay = 0 },
		{ mobId = "crawler", count = 3, spawnInterval = 1, startDelay = 1 },
		{ mobId = "golem", count = 1, spawnInterval = 1, startDelay = 2 },
	},
}
