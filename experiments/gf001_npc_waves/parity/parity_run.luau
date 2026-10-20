--!strict
-- GF-001-Q1 parity: executes the shared vectors against the real GF-001 Luau modules.
--
-- Part of experiments/gf001_npc_waves/parity/ (isolated, non-production). This
-- runner requires the actual reusable modules from ../luau/ (no stubs or fakes)
-- and prints one canonical JSON line per vector. The Python reference harness
-- (gf001_parity.py) executes the identical vectors against
-- experiments/gf001_npc_waves/python/gf001_core.py and compares the two outputs
-- structurally; see docs/GF_001_Q1_LUAU_PARITY_QUALIFICATION.md.
--
-- Ops: start, tick, advance, stop, killFirst, killAll, killById, damageFirst,
-- damageById, clientRequest, failSpawn, restoreSpawn, failDespawn, restoreDespawn.
-- Adapter-raised errors are caught and classified into stable markers so both
-- languages compare identically despite different exception text.

local Pjson = require("./pjson")
local Vectors = require("./vectors")

local Clock = require("../luau/Clock")
local Config = require("../luau/Config")
local ExampleConfig = require("../luau/ExampleConfig")
local MemoryAdapter = require("../luau/MemoryAdapter")
local Mobs = require("../luau/Mobs")
local Rewards = require("../luau/Rewards")
local Rng = require("../luau/Rng")
local SpawnPoints = require("../luau/SpawnPoints")
local WaveRuntime = require("../luau/WaveRuntime")

local RECORD_FIELDS = {
	"id",
	"mobId",
	"health",
	"state",
	"spawnPointId",
	"rewarded",
	"cleaned",
	"bornAt",
	"diedAt",
	"despawnedAt",
}

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

local function classifyRaised(message: string): string
	if string.find(message, "adapter spawn failed", 1, true) then
		return "adapter_spawn_failed"
	end
	if string.find(message, "adapter despawn failed", 1, true) then
		return "adapter_despawn_failed"
	end
	return "unclassified_error"
end

local function resolveMutationValue(mutation: any): any
	local special = mutation.special
	if special == "emptyTable" then
		return {}
	end
	if special == "nan" then
		return 0 / 0
	end
	if special == "inf" then
		return math.huge
	end
	if special == "-inf" then
		return -math.huge
	end
	return mutation.value
end

local function applyMutation(config: any, mutation: any)
	local special = mutation.special
	if special == "none" then
		return
	end
	local path = mutation.path
	local parent = config
	for index = 1, #path - 1 do
		parent = parent[path[index]]
	end
	if special == "remove" then
		parent[path[#path]] = nil
	else
		parent[path[#path]] = resolveMutationValue(mutation)
	end
end

local function projectStatus(status: any): any
	return {
		state = status.state,
		phase = status.phase,
		wave = status.wave,
		pending = status.pending,
		active = status.active,
		spawnedInWave = status.spawnedInWave,
		killedInWave = status.killedInWave,
		totalSpawned = status.totalSpawned,
		totalKilled = status.totalKilled,
		wavesCompleted = status.wavesCompleted,
	}
end

local function projectRecords(records: { any }): { any }
	local out = {}
	for _, record in ipairs(records) do
		local item = {}
		for _, field in ipairs(RECORD_FIELDS) do
			item[field] = record[field]
		end
		table.insert(out, item)
	end
	return out
end

local function projectEvents(events: { any }): { any }
	local out = {}
	for _, event in ipairs(events) do
		table.insert(out, table.clone(event))
	end
	return out
end

local function firstAliveRecord(runtime: any): any
	local records: { any } = runtime.records()
	for _, record in ipairs(records) do
		if record.state == "alive" then
			return record
		end
	end
	return nil
end

local function runValidateVector(vector: any): any
	local mutations = {}
	for _, mutation in ipairs(vector.mutations) do
		local config = deepCopy(ExampleConfig)
		applyMutation(config, mutation)
		local ok, result = Config.validate(config)
		local entry = { ok = ok }
		if ok then
			local normalized: any = result
			entry.waveCount = #normalized.waves
			entry.wave1StartDelay = normalized.waves[1].startDelay
		else
			local errors: { any } = result
			entry.errorCount = #errors
		end
		table.insert(mutations, entry)
	end
	return { name = vector.name, kind = "validate", mutations = mutations }
end

local function runRuntimeVector(vector: any): any
	local baseConfig = nil
	if vector.exampleConfig then
		baseConfig = ExampleConfig
	else
		baseConfig = vector.config
	end
	local valid, result = Config.validate(deepCopy(baseConfig))
	local events = {}
	if not valid then
		local errors: { any } = result
		return {
			name = vector.name,
			kind = "runtime",
			configValid = false,
			validateErrorCount = #errors,
			steps = {},
			events = {},
		}
	end
	local normalized: any = result
	local clock = Clock.stepping(0)
	local adapter = MemoryAdapter.new()
	local rewards = Rewards.new({ events = events })
	local runtime = WaveRuntime.new(normalized, {
		clock = clock,
		rng = Rng.new(vector.seed),
		adapter = adapter,
		events = events,
		mobs = Mobs,
		selectSpawn = SpawnPoints.select,
		rewards = rewards,
	})
	local originalSpawn = adapter.spawn
	local originalDespawn = adapter.despawn
	local steps = {}
	for _, step in ipairs(vector.steps) do
		local snapshot: any = { op = step.op }
		local op = step.op
		if op == "start" then
			local ok, reason = runtime.start()
			snapshot.ok = ok
			snapshot.reason = reason
		elseif op == "tick" then
			local called, first, second = pcall(runtime.tick)
			if not called then
				snapshot.raised = classifyRaised(tostring(first))
			else
				snapshot.ok = first
				snapshot.reason = second
			end
		elseif op == "advance" then
			clock.advance(step.delta)
			snapshot.applied = step.delta
		elseif op == "stop" then
			local ok = runtime.stop(step.reason)
			snapshot.ok = ok
		elseif op == "killFirst" then
			local target = firstAliveRecord(runtime)
			if target == nil then
				snapshot.skipped = true
			else
				local ok, outcome = runtime.killMob(target.id)
				snapshot.target = target.id
				snapshot.ok = ok
				snapshot.outcome = outcome
			end
		elseif op == "killAll" then
			local killed = 0
			local records: { any } = runtime.records()
			for _, record in ipairs(records) do
				if record.state == "alive" then
					runtime.killMob(record.id)
					killed += 1
				end
			end
			snapshot.killed = killed
		elseif op == "killById" then
			local ok, outcome = runtime.killMob(step.id)
			snapshot.ok = ok
			snapshot.outcome = outcome
		elseif op == "damageFirst" then
			local target = firstAliveRecord(runtime)
			if target == nil then
				snapshot.skipped = true
			else
				local ok, outcome = runtime.damageMob(target.id, step.amount)
				snapshot.target = target.id
				snapshot.amount = step.amount
				snapshot.ok = ok
				snapshot.outcome = outcome
			end
		elseif op == "damageById" then
			local ok, outcome = runtime.damageMob(step.id, step.amount)
			snapshot.ok = ok
			snapshot.outcome = outcome
		elseif op == "clientRequest" then
			rewards.handleClientRequest(step.player, step.payload, clock.now())
			snapshot.submitted = true
		elseif op == "failSpawn" then
			adapter.spawn = function()
				return false
			end
			snapshot.injected = "failing"
		elseif op == "restoreSpawn" then
			adapter.spawn = originalSpawn
			snapshot.injected = "restored"
		elseif op == "failDespawn" then
			adapter.despawn = function()
				return false
			end
			snapshot.injected = "failing"
		elseif op == "restoreDespawn" then
			adapter.despawn = originalDespawn
			snapshot.injected = "restored"
		else
			error("[GF001-Q1] unknown parity op: " .. tostring(op), 0)
		end
		snapshot.status = projectStatus(runtime.status())
		snapshot.records = projectRecords(runtime.records())
		snapshot.eventCount = #events
		table.insert(steps, snapshot)
	end
	return {
		name = vector.name,
		kind = "runtime",
		configValid = true,
		steps = steps,
		events = projectEvents(events),
	}
end

for _, vector in ipairs(Vectors.list) do
	local result = nil
	if vector.kind == "validate" then
		result = runValidateVector(vector)
	else
		result = runRuntimeVector(vector)
	end
	print(Pjson.encode(result))
end

return 0
