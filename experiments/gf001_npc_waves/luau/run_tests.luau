--!strict
-- GF-001 offline NPC wave prototype: deterministic Luau test suite.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). This suite
-- runs under a standalone Luau runtime (luau CLI or equivalent) from this
-- directory and uses no Roblox engine APIs. It was NOT executed in milestone
-- GF-001: no Luau runtime is installed in this environment. It is verified
-- by stylua --check and selene only. Corresponding scenarios are executed in
-- Python by tests/test_gf001_npc_waves.py against the separate reference twin
-- experiments/gf001_npc_waves/python/gf001_core.py.

local Clock = require("./Clock")
local Config = require("./Config")
local ExampleConfig = require("./ExampleConfig")
local MemoryAdapter = require("./MemoryAdapter")
local Mobs = require("./Mobs")
local Rewards = require("./Rewards")
local Rng = require("./Rng")
local SpawnPoints = require("./SpawnPoints")
local WaveRuntime = require("./WaveRuntime")

local passed = 0
local failures: { any } = {}

local function test(name: string, fn: () -> ())
	local ok, err = pcall(fn)
	if ok then
		passed += 1
	else
		table.insert(failures, { name = name, error = tostring(err) })
	end
end

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 0)
	end
end

local function countEvents(events: { any }, eventType: string): number
	local count = 0
	for _, event in ipairs(events) do
		if event.type == eventType then
			count += 1
		end
	end
	return count
end

local function findEvent(events: { any }, eventType: string): any
	for _, event in ipairs(events) do
		if event.type == eventType then
			return event
		end
	end
	return nil
end

local function deepCopy(value: any): any
	if type(value) ~= "table" then
		return value
	end
	local result = {}
	for key, item in pairs(value) do
		result[key] = deepCopy(item)
	end
	return result
end

local function deepEqual(left: any, right: any): boolean
	if type(left) ~= type(right) then
		return false
	end
	if type(left) ~= "table" then
		return left == right
	end
	for key, value in pairs(left) do
		if not deepEqual(value, right[key]) then
			return false
		end
	end
	for key in pairs(right) do
		if left[key] == nil then
			return false
		end
	end
	return true
end

local function newRuntime(config: any, seed: number?): (any, any, any, any)
	local events = {}
	local clock = Clock.stepping(0)
	local rng = Rng.new(seed or 20261018)
	local adapter = MemoryAdapter.new()
	local rewards = Rewards.new({ events = events })
	local runtime = WaveRuntime.new(config, {
		clock = clock,
		rng = rng,
		adapter = adapter,
		events = events,
		mobs = Mobs,
		selectSpawn = SpawnPoints.select,
		rewards = rewards,
	})
	return runtime, clock, adapter, events
end

local function driveToCompletion(runtime: any, clock: any)
	local ticks = 0
	while runtime.status().state == "running" and ticks < 1000 do
		runtime.tick()
		for _, mob in ipairs(runtime.records()) do
			if mob.state == "alive" then
				runtime.damageMob(mob.id, 15)
			end
		end
		clock.advance(0.25)
		ticks += 1
	end
	expect(ticks < 1000, "scenario did not complete within the tick budget")
end

test("example config validates and fills startDelay defaults", function()
	local ok, normalized = Config.validate(ExampleConfig)
	expect(ok, "example config must validate")
	expect(#normalized.waves == 3, "example config has three waves")
	expect(normalized.waves[3].startDelay == 2, "explicit startDelay is preserved")
	local withoutDelay, second = Config.validate({
		maxActiveMobs = 2,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = { ExampleConfig.spawnPoints[1] },
		waves = { { mobId = "dummy", count = 1, spawnInterval = 0 } },
	})
	expect(withoutDelay, "config without startDelay must validate")
	expect(type(second) == "table", "valid config returns a normalized table")
	expect(second.waves[1].startDelay == 0, "missing startDelay defaults to 0")
end)

test("invalid configurations are rejected", function()
	local cases = {
		function(config: any)
			config.maxActiveMobs = 0
		end,
		function(config: any)
			config.maxActiveMobs = 1.5
		end,
		function(config: any)
			config.interWaveDelay = -1
		end,
		function(config: any)
			config.mobs = {}
		end,
		function(config: any)
			config.mobs.dummy.maxHealth = 0
		end,
		function(config: any)
			config.mobs.dummy.reward.points = -5
		end,
		function(config: any)
			config.mobs.dummy.reward.points = 1.5
		end,
		function(config: any)
			config.spawnPoints = {}
		end,
		function(config: any)
			config.spawnPoints[1].capacity = 0
		end,
		function(config: any)
			config.spawnPoints[2].id = config.spawnPoints[1].id
		end,
		function(config: any)
			config.waves = {}
		end,
		function(config: any)
			config.waves[1].mobId = "unknown-mob"
		end,
		function(config: any)
			config.waves[1].count = 0
		end,
		function(config: any)
			config.waves[1].spawnInterval = -0.5
		end,
		function(config: any)
			config.waves[1].startDelay = -1
		end,
	}
	for index, mutate in ipairs(cases) do
		local config = deepCopy(ExampleConfig)
		mutate(config)
		local ok, errors = Config.validate(config)
		expect(not ok, "invalid case " .. tostring(index) .. " must be rejected")
		expect(type(errors) == "table" and #errors > 0, "rejection must list errors")
	end
	local ok, errors = Config.validate(nil)
	expect(not ok, "nil config must be rejected")
	expect(type(errors) == "table" and #errors > 0, "nil config rejection must list errors")
end)

test("wave start and stop transitions", function()
	local runtime, clock = newRuntime(ExampleConfig)
	local ok = runtime.tick()
	expect(not ok, "tick before start must fail")
	runtime.start()
	expect(runtime.status().state == "running", "start sets running state")
	expect(runtime.status().wave == 1, "start targets wave 1")
	expect(runtime.status().phase == "delay", "start enters delay phase")
	local again = runtime.start()
	expect(not again, "double start must fail")
	clock.advance(1)
	runtime.tick()
	expect(runtime.status().phase == "spawning", "wave 1 begins spawning after its delay")
	expect(runtime.stop(), "stop must succeed while running")
	expect(runtime.status().state == "stopped", "stop sets stopped state")
	expect(not runtime.stop(), "second stop must fail")
	expect(not runtime.tick(), "tick after stop must fail")
	expect(runtime.start(), "restart after stop must succeed")
end)

test("maximum active mob enforcement", function()
	local ok, normalized = Config.validate({
		maxActiveMobs = 3,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = {
			{ id = "a", capacity = 5, position = { x = 0, y = 0, z = 0 } },
			{ id = "b", capacity = 5, position = { x = 1, y = 0, z = 0 } },
		},
		waves = { { mobId = "dummy", count = 10, spawnInterval = 0.5 } },
	})
	expect(ok, "max active test config must validate")
	local runtime, clock = newRuntime(normalized)
	runtime.start()
	local ticks = 0
	while runtime.status().state == "running" and ticks < 500 do
		runtime.tick()
		expect(runtime.status().active <= 3, "active mob count must never exceed the maximum")
		if runtime.status().active == 3 then
			local alive = {}
			for _, mob in ipairs(runtime.records()) do
				if mob.state == "alive" then
					table.insert(alive, mob)
				end
			end
			expect(#alive == 3, "status active count matches alive records")
			runtime.killMob(alive[1].id)
		elseif runtime.status().pending == 0 and runtime.status().active > 0 then
			local alive = {}
			for _, mob in ipairs(runtime.records()) do
				if mob.state == "alive" then
					table.insert(alive, mob)
				end
			end
			runtime.killMob(alive[1].id)
		end
		clock.advance(0.25)
		ticks += 1
	end
	expect(ticks < 500, "max active scenario must complete")
	expect(runtime.status().totalSpawned == 10, "all ten mobs spawn over time")
	expect(runtime.status().state == "completed", "single-wave config completes")
end)

test("spawn eligibility requires running state, wave delay and free capacity", function()
	local ok, normalized = Config.validate({
		maxActiveMobs = 3,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = {
			{ id = "only", capacity = 1, position = { x = 0, y = 0, z = 0 } },
		},
		waves = { { mobId = "dummy", count = 3, spawnInterval = 0, startDelay = 2 } },
	})
	expect(ok, "eligibility test config must validate")
	local runtime, clock = newRuntime(normalized)
	runtime.start()
	clock.advance(1)
	runtime.tick()
	expect(runtime.status().phase == "delay", "wave must stay in delay before startDelay elapses")
	expect(runtime.status().pending == 3, "nothing spawns during the delay")
	clock.advance(1.5)
	runtime.tick()
	expect(runtime.status().spawnedInWave == 1, "first eligible spawn happens")
	runtime.tick()
	expect(runtime.status().spawnedInWave == 1, "full spawn point blocks further spawns")
	local spawned = runtime.records()[1]
	expect(runtime.killMob(spawned.id), "server kill frees capacity")
	runtime.tick()
	expect(runtime.status().spawnedInWave == 2, "freed capacity allows the next spawn")
end)

test("duplicate death and duplicate rewards are prevented", function()
	local ok, normalized = Config.validate({
		maxActiveMobs = 4,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = {
			{ id = "only", capacity = 4, position = { x = 0, y = 0, z = 0 } },
		},
		waves = { { mobId = "dummy", count = 1, spawnInterval = 0 } },
	})
	expect(ok, "duplicate test config must validate")
	local runtime, clock, _, events = newRuntime(normalized)
	runtime.start()
	clock.advance(1)
	runtime.tick()
	local mob = runtime.records()[1]
	local damageOk, firstOutcome = runtime.damageMob(mob.id, 999)
	expect(damageOk, "server damage call succeeds")
	expect(firstOutcome == "died", "first lethal damage kills")
	expect(countEvents(events, "mob_died") == 1, "exactly one mob_died event")
	expect(countEvents(events, "reward_intent") == 1, "exactly one reward_intent event")
	local _, secondDamage = runtime.damageMob(mob.id, 999)
	expect(secondDamage == "ignored", "damage after death is ignored")
	local _, secondKill = runtime.killMob(mob.id)
	expect(secondKill == "ignored", "kill after death is ignored")
	expect(countEvents(events, "mob_died") == 1, "no second mob_died event")
	expect(countEvents(events, "reward_intent") == 1, "no second reward_intent event")
	runtime.tick()
	expect(runtime.status().state == "completed", "wave completes after the single death")
end)

test("wave completion progresses through all waves", function()
	local ok, normalized = Config.validate({
		maxActiveMobs = 4,
		interWaveDelay = 3,
		mobs = {
			dummy = ExampleConfig.mobs.dummy,
			crawler = ExampleConfig.mobs.crawler,
		},
		spawnPoints = {
			{ id = "a", capacity = 4, position = { x = 0, y = 0, z = 0 } },
		},
		waves = {
			{ mobId = "dummy", count = 2, spawnInterval = 0 },
			{ mobId = "crawler", count = 2, spawnInterval = 0 },
		},
	})
	expect(ok, "progression test config must validate")
	local runtime, clock, _, events = newRuntime(normalized)
	runtime.start()
	runtime.tick()
	for _, mob in ipairs(runtime.records()) do
		runtime.killMob(mob.id)
	end
	runtime.tick()
	expect(runtime.status().wavesCompleted == 1, "wave 1 completes when cleared")
	expect(runtime.status().phase == "intermission", "intermission begins after wave completion")
	expect(countEvents(events, "wave_started") == 1, "next wave does not start before interWaveDelay")
	clock.advance(3)
	runtime.tick()
	runtime.tick()
	expect(runtime.status().wave == 2, "wave 2 starts after intermission")
	expect(runtime.status().spawnedInWave == 2, "wave 2 spawns its mobs")
	expect(countEvents(events, "wave_started") == 2, "wave 2 emits its own wave_started")
	for _, mob in ipairs(runtime.records()) do
		if mob.state == "alive" then
			runtime.killMob(mob.id)
		end
	end
	runtime.tick()
	expect(runtime.status().state == "completed", "all waves complete")
	expect(runtime.status().wavesCompleted == 2, "both waves completed")
end)

test("cleanup after interruption and clean restart", function()
	local ok, normalized = Config.validate({
		maxActiveMobs = 10,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = {
			{ id = "a", capacity = 10, position = { x = 0, y = 0, z = 0 } },
		},
		waves = { { mobId = "dummy", count = 5, spawnInterval = 1 } },
	})
	expect(ok, "cleanup test config must validate")
	local runtime, clock, adapter, events = newRuntime(normalized)
	runtime.start()
	clock.advance(0.5)
	runtime.tick()
	clock.advance(1)
	runtime.tick()
	expect(runtime.status().totalSpawned == 2, "two mobs spawned before interruption")
	expect(runtime.stop("interrupted"), "interrupted stop succeeds")
	local stoppedEvent = events[#events]
	expect(stoppedEvent.type == "wave_stopped", "stop emits wave_stopped")
	expect(stoppedEvent.activeCleaned == 2, "stop reports both active mobs cleaned")
	expect(#adapter.despawns == 2, "adapter despawned both active mobs")
	for _, mob in ipairs(runtime.records()) do
		expect(mob.state ~= "alive", "no mob stays alive after stop")
	end
	expect(runtime.status().pending == 0, "pending spawn queue is cleared")
	expect(runtime.start(), "restart after interruption succeeds")
	clock.advance(1)
	runtime.tick()
	expect(countEvents(events, "wave_started") == 2, "restart begins a fresh wave 1")
	expect(runtime.status().totalSpawned == 1, "restart resets spawn accounting")
end)

test("untrusted client reward requests are always rejected", function()
	local standaloneEvents = {}
	local rewards = Rewards.new({ events = standaloneEvents })
	local result = rewards.handleClientRequest(11822718311, {
		mobId = "golem",
		points = 999999,
		killed = true,
	}, 5)
	expect(result == nil, "client reward requests return no intent")
	expect(#standaloneEvents == 1, "client request emits one rejection event")
	expect(standaloneEvents[1].type == "client_reward_rejected", "rejection event type")
	expect(countEvents(standaloneEvents, "reward_intent") == 0, "client requests never produce reward intents")
	local second = rewards.handleClientRequest("player-two", "i killed the golem", 6)
	expect(second == nil, "non-table client payloads are rejected too")
	expect(countEvents(standaloneEvents, "reward_intent") == 0, "still no reward intents")

	local ok, normalized = Config.validate({
		maxActiveMobs = 2,
		interWaveDelay = 0,
		mobs = { golem = ExampleConfig.mobs.golem },
		spawnPoints = {
			{ id = "a", capacity = 2, position = { x = 0, y = 0, z = 0 } },
		},
		waves = { { mobId = "golem", count = 1, spawnInterval = 0 } },
	})
	expect(ok, "client reward test config must validate")
	local runtime, clock, _, events = newRuntime(normalized)
	runtime.start()
	clock.advance(1)
	runtime.tick()
	local mob = runtime.records()[1]
	local sharedRewards = Rewards.new({ events = events })
	sharedRewards.handleClientRequest(mob.id, { mob = mob.id, killed = true }, clock.now())
	expect(countEvents(events, "client_reward_rejected") == 1, "shared log records rejection")
	expect(countEvents(events, "reward_intent") == 0, "client claims produce no intents in the runtime log")
	runtime.killMob(mob.id)
	expect(countEvents(events, "reward_intent") == 1, "only the server death produces a reward intent")
	local intent = findEvent(events, "reward_intent")
	expect(intent ~= nil and intent.points == 40, "reward points come from the server config only")
end)

test("deterministic replay with the same seed", function()
	local function runScenario(): { any }
		local runtime, clock, _, events = newRuntime(ExampleConfig, 424242)
		runtime.start()
		driveToCompletion(runtime, clock)
		return events
	end
	local first = runScenario()
	local second = runScenario()
	expect(#first > 0, "scenario must emit events")
	expect(deepEqual(first, second), "same seed reproduces the identical event log")
	local otherRuntime, otherClock, _, otherEvents = newRuntime(ExampleConfig, 777)
	otherRuntime.start()
	driveToCompletion(otherRuntime, otherClock)
	expect(not deepEqual(first, otherEvents), "different seed changes behavior")
end)

test("full example scenario completes with validated rewards", function()
	local runtime, clock, _, events = newRuntime(ExampleConfig)
	runtime.start()
	driveToCompletion(runtime, clock)
	local status = runtime.status()
	expect(status.state == "completed", "example scenario completes")
	expect(status.totalSpawned == 8, "eight mobs spawn in total")
	expect(status.totalKilled == 8, "eight mobs die in total")
	expect(status.wavesCompleted == 3, "three waves complete")
	expect(countEvents(events, "reward_intent") == 8, "one reward intent per dead mob")
	local points = 0
	for _, event in ipairs(events) do
		if event.type == "reward_intent" then
			points += event.points
		end
	end
	expect(points == 96, "total points match server config: 4*5 + 3*12 + 1*40")
end)

test("WaveRuntime rejects invalid config and deps", function()
	local ok = pcall(function()
		WaveRuntime.new({}, { clock = Clock.stepping(0) })
	end)
	expect(not ok, "empty config must be rejected")
	local bad = deepCopy(ExampleConfig)
	bad.maxActiveMobs = 0
	local badOk = pcall(function()
		WaveRuntime.new(bad, nil)
	end)
	expect(not badOk, "invalid maxActiveMobs must be rejected")
	local validConfig = Config.validate(ExampleConfig)
	expect(validConfig, "example config must validate for the deps test")
	local _, normalized = Config.validate(ExampleConfig)
	local depsOk = pcall(function()
		WaveRuntime.new(normalized, {})
	end)
	expect(not depsOk, "missing deps must be rejected")
end)

test("nonfinite configuration values are rejected", function()
	local paths = {
		{ "maxActiveMobs" },
		{ "interWaveDelay" },
		{ "mobs", "dummy", "maxHealth" },
		{ "mobs", "dummy", "reward", "points" },
		{ "spawnPoints", 1, "capacity" },
		{ "spawnPoints", 1, "position", "x" },
		{ "spawnPoints", 1, "position", "y" },
		{ "spawnPoints", 1, "position", "z" },
		{ "waves", 1, "count" },
		{ "waves", 1, "spawnInterval" },
		{ "waves", 1, "startDelay" },
	}
	for _, path in ipairs(paths) do
		for _, value in ipairs({ 0 / 0, math.huge, -math.huge }) do
			local config = deepCopy(ExampleConfig)
			local parent = config
			for index = 1, #path - 1 do
				parent = parent[path[index]]
			end
			parent[path[#path]] = value
			local ok = Config.validate(config)
			expect(not ok, "nonfinite config must be rejected")
		end
	end
	local sparse = deepCopy(ExampleConfig)
	sparse.waves = { [2] = ExampleConfig.waves[1] }
	expect(not Config.validate(sparse), "sparse arrays must be rejected")
end)

test("invalid damage cannot heal or poison health", function()
	local runtime, _, _, events = newRuntime(ExampleConfig)
	runtime.start()
	runtime.tick()
	local mob = runtime.records()[1]
	local health = mob.health
	for _, amount in ipairs({ -1, 0, 0 / 0, math.huge, "10", true }) do
		local ok, reason = runtime.damageMob(mob.id, amount)
		expect(not ok and reason == "invalid_damage", "invalid damage must be refused")
		expect(mob.health == health and mob.state == "alive", "health unchanged")
	end
	expect(countEvents(events, "reward_intent") == 0, "no rewards from invalid damage")
end)

test("dead instances are cleaned once before wave completion", function()
	local runtime, clock, adapter, events = newRuntime(ExampleConfig)
	runtime.start()
	driveToCompletion(runtime, clock)
	expect(#adapter.spawns == 8 and #adapter.despawns == 8, "all instances released")
	local cleaned = {}
	for _, call in ipairs(adapter.despawns) do
		expect(not cleaned[call.mob], "no duplicate cleanup")
		cleaned[call.mob] = true
	end
	for _, mob in ipairs(runtime.records()) do
		expect(mob.cleaned, "cleanup acknowledged")
	end
	expect(not runtime.stop(), "completed run is already clean")
	runtime.tick()
	expect(#adapter.despawns == 8, "cleanup remains idempotent")
	expect(countEvents(events, "all_waves_completed") == 1, "one completion event")
end)

test("restart rejects stale death callbacks", function()
	local runtime, _, _, events = newRuntime(ExampleConfig)
	runtime.start()
	runtime.tick()
	local oldId = runtime.records()[1].id
	runtime.stop("interrupted")
	runtime.start()
	runtime.tick()
	local mob = runtime.records()[1]
	expect(oldId ~= mob.id, "ids are not reused within a runtime")
	local ok, reason = runtime.killMob(oldId)
	expect(not ok and reason == "unknown_mob", "old callback refused")
	expect(mob.state == "alive", "new mob remains alive")
	expect(countEvents(events, "reward_intent") == 0, "no stale callback reward")
end)

test("adapter spawn failure is not a successful spawn", function()
	local runtime, _, adapter, events = newRuntime(ExampleConfig)
	adapter.spawn = function()
		return false
	end
	runtime.start()
	local ok = pcall(runtime.tick)
	expect(not ok, "spawn failure is raised")
	expect(countEvents(events, "mob_spawned") == 0, "no false spawn event")
	expect(runtime.status().totalSpawned == 0, "no successful spawn counted")
	expect(runtime.stop("adapter_failure"), "partial allocation cleaned by stop")
	expect(runtime.status().active == 0 and #adapter.despawns == 1, "partial record cleaned")
end)

test("cleanup failure prevents completion and can be retried", function()
	local config = deepCopy(ExampleConfig)
	config.waves = { { mobId = "dummy", count = 1, spawnInterval = 0, startDelay = 0 } }
	local runtime, _, adapter, events = newRuntime(config)
	runtime.start()
	runtime.tick()
	local mob = runtime.records()[1]
	runtime.killMob(mob.id)
	local originalDespawn = adapter.despawn
	adapter.despawn = function()
		return false
	end
	expect(not pcall(runtime.tick), "cleanup failure is raised")
	expect(not mob.cleaned, "failed cleanup is not acknowledged")
	expect(countEvents(events, "wave_completed") == 0, "no false completion")
	adapter.despawn = originalDespawn
	expect(runtime.stop("interrupted"), "stop retries cleanup")
	expect(mob.cleaned and #adapter.despawns == 1, "dead record cleaned once")
	expect(countEvents(events, "reward_intent") == 1, "reward not repeated")
end)

test("reward recorder rejects living invalid and duplicate deaths", function()
	local events = {}
	local rewards = Rewards.new({ events = events })
	local registry = Mobs.new()
	local definition = ExampleConfig.mobs.dummy
	local mob = Mobs.spawn(registry, definition, "dummy", "a", 0)
	expect(rewards.recordDeath(mob, definition, 0) == nil, "living mobs cannot reward")
	Mobs.kill(mob, 1)
	for _, points in ipairs({ -1, 1.5, 0 / 0, math.huge, true }) do
		expect(rewards.recordDeath(mob, { reward = { points = points } }, 1) == nil, "invalid reward")
		expect(not mob.rewarded, "no reward acknowledged")
	end
	expect(rewards.recordDeath(mob, definition, 1).points == 5, "valid config reward")
	expect(rewards.recordDeath(mob, definition, 1) == nil, "duplicate death refused")
	expect(countEvents(events, "reward_intent") == 1, "one intent")
end)

test("injected randomness and invalid RNG inputs", function()
	expect(Rng.new(function()
		return 0
	end).pick({ "a", "b" }) == "a", "lower endpoint")
	expect(Rng.new(function()
		return 0.999
	end).pick({ "a", "b" }) == "b", "upper endpoint")
	for _, value in ipairs({ -0.1, 1, 0 / 0, math.huge, true }) do
		local ok = pcall(function()
			Rng.new(function()
				return value
			end).pick({ "a" })
		end)
		expect(not ok, "invalid injected value refused")
	end
	expect(not pcall(function()
		Rng.new(1).pick({})
	end), "empty pick refused")
	for _, seed in ipairs({ 0 / 0, math.huge }) do
		expect(not pcall(function()
			Rng.new(seed)
		end), "nonfinite seed refused")
	end
end)

for _, failure in ipairs(failures) do
	print(("GF-001 FAIL: %s: %s"):format(failure.name, failure.error))
end
print(("GF-001: %d passed, %d failed"):format(passed, #failures))
if #failures > 0 then
	error("[GF001] Luau test suite failed", 0)
end
