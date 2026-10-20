--!strict
-- GF-001 offline NPC wave prototype: the wave state machine.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production, not mapped by
-- default.project.json). Pure Luau, no Roblox engine APIs: every collaborator
-- (clock, rng, adapter, events sink, mob registry module, spawn selector,
-- rewards) is injected through deps, so the whole wave lifecycle is testable
-- offline and reusable by any game mode. Only server-side damage/kill calls
-- advance mob death and reward state.
--
-- Phases per wave: delay -> spawning -> clearing; between waves:
-- intermission -> delay. Events (all appended to deps.events):
--   wave_started, mob_spawned, mob_died, mob_despawned,
--   reward_intent (via deps.rewards), wave_completed, wave_stopped,
--   all_waves_completed, client_reward_rejected (via deps.rewards).

local WaveRuntime = {}

local REQUIRED_DEPS = { "clock", "rng", "adapter", "events", "mobs", "selectSpawn", "rewards" }

function WaveRuntime.new(config: any, deps: any): any
	if type(config) ~= "table" then
		error("[GF001] WaveRuntime requires a config table", 0)
	end
	if
		type(config.maxActiveMobs) ~= "number"
		or config.maxActiveMobs < 1
		or type(config.interWaveDelay) ~= "number"
		or config.interWaveDelay < 0
		or type(config.mobs) ~= "table"
		or type(config.spawnPoints) ~= "table"
		or #config.spawnPoints < 1
		or type(config.waves) ~= "table"
		or #config.waves < 1
	then
		error("[GF001] WaveRuntime requires a config normalized by Config.validate", 0)
	end
	if type(deps) ~= "table" then
		error("[GF001] WaveRuntime requires a deps table", 0)
	end
	for _, name in ipairs(REQUIRED_DEPS) do
		if deps[name] == nil then
			error("[GF001] WaveRuntime deps." .. name .. " is required", 0)
		end
	end

	local state = "idle"
	local phase = "idle"
	local waveIndex = 0
	local pending = 0
	local spawnedInWave = 0
	local killedInWave = 0
	local totalSpawned = 0
	local totalKilled = 0
	local wavesCompleted = 0
	local registry = deps.mobs.new()
	local occupancy = {}
	local wave: any = nil
	local nextPhaseAt = nil
	local nextSpawnAt = nil

	local runtime = {}

	local function emit(eventType: string, fields: { [string]: any })
		local event = { type = eventType, at = deps.clock.now() }
		for key, value in pairs(fields) do
			event[key] = value
		end
		table.insert(deps.events, event)
	end

	local function releaseOccupancy(spawnPointId: string)
		local occupied = occupancy[spawnPointId]
		if occupied ~= nil and occupied > 0 then
			occupancy[spawnPointId] = occupied - 1
		end
	end

	local function findRecord(mobRecordId: string): any
		local allRecords: { any } = deps.mobs.all(registry)
		for _, mob in ipairs(allRecords) do
			if mob.id == mobRecordId then
				return mob
			end
		end
		return nil
	end

	local function onServerDeath(mob: any)
		emit("mob_died", { mob = mob.id, mobId = mob.mobId })
		killedInWave = killedInWave + 1
		totalKilled = totalKilled + 1
		releaseOccupancy(mob.spawnPointId)
		deps.rewards.recordDeath(mob, config.mobs[mob.mobId], deps.clock.now())
	end

	local function cleanup(mob: any)
		if not mob.cleaned then
			assert(deps.adapter.despawn(mob) == true, "[GF001] adapter despawn failed")
			mob.cleaned = true
		end
	end

	function runtime.start(): (boolean, string?)
		if state == "running" then
			return false, "already_running"
		end
		registry = deps.mobs.new(registry.nextId)
		occupancy = {}
		waveIndex = 1
		wave = config.waves[1]
		pending = wave.count
		spawnedInWave = 0
		killedInWave = 0
		totalSpawned = 0
		totalKilled = 0
		wavesCompleted = 0
		state = "running"
		phase = "delay"
		nextPhaseAt = deps.clock.now() + wave.startDelay
		return true, nil
	end

	function runtime.tick(): (boolean, string?)
		if state ~= "running" then
			return false, "not_running"
		end
		local now = deps.clock.now()
		local allRecords: { any } = deps.mobs.all(registry)
		for _, mob in ipairs(allRecords) do
			if mob.state == "dead" then
				cleanup(mob)
			end
		end
		if phase == "delay" then
			if now >= nextPhaseAt then
				emit("wave_started", { wave = waveIndex, mobId = wave.mobId, count = wave.count })
				phase = "spawning"
				nextSpawnAt = now
			end
		end
		if phase == "spawning" then
			local alive = deps.mobs.aliveCount(registry)
			while pending > 0 and alive < config.maxActiveMobs and now >= nextSpawnAt do
				local spawnPoint = deps.selectSpawn(config.spawnPoints, occupancy, deps.rng)
				if spawnPoint == nil then
					break
				end
				local mobDef = config.mobs[wave.mobId]
				local record = deps.mobs.spawn(registry, mobDef, wave.mobId, spawnPoint.id, now)
				assert(deps.adapter.spawn(record, spawnPoint) == true, "[GF001] adapter spawn failed")
				occupancy[spawnPoint.id] = (occupancy[spawnPoint.id] or 0) + 1
				emit("mob_spawned", { mob = record.id, mobId = record.mobId, spawnPoint = spawnPoint.id })
				pending = pending - 1
				spawnedInWave = spawnedInWave + 1
				totalSpawned = totalSpawned + 1
				alive = alive + 1
				nextSpawnAt = now + wave.spawnInterval
			end
			if pending == 0 then
				phase = "clearing"
			end
		end
		if phase == "clearing" then
			if pending == 0 and deps.mobs.aliveCount(registry) == 0 then
				emit("wave_completed", { wave = waveIndex, spawned = spawnedInWave, killed = killedInWave })
				wavesCompleted = wavesCompleted + 1
				if waveIndex < #config.waves then
					waveIndex = waveIndex + 1
					wave = config.waves[waveIndex]
					pending = wave.count
					spawnedInWave = 0
					killedInWave = 0
					phase = "intermission"
					nextPhaseAt = now + config.interWaveDelay
				else
					phase = "completed"
					state = "completed"
					emit("all_waves_completed", { waves = #config.waves })
				end
			end
		end
		if phase == "intermission" then
			if now >= nextPhaseAt then
				phase = "delay"
				nextPhaseAt = now + wave.startDelay
			end
		end
		return true, nil
	end

	function runtime.damageMob(mobRecordId: string, amount: number): (boolean, string?)
		if state ~= "running" then
			return false, "not_running"
		end
		local mob = findRecord(mobRecordId)
		if mob == nil then
			return false, "unknown_mob"
		end
		local outcome = deps.mobs.damage(mob, amount, deps.clock.now())
		if outcome == "invalid_damage" then
			return false, outcome
		end
		if outcome == "died" then
			onServerDeath(mob)
		end
		return true, outcome
	end

	function runtime.killMob(mobRecordId: string): (boolean, string?)
		if state ~= "running" then
			return false, "not_running"
		end
		local mob = findRecord(mobRecordId)
		if mob == nil then
			return false, "unknown_mob"
		end
		local outcome = deps.mobs.kill(mob, deps.clock.now())
		if outcome == "died" then
			onServerDeath(mob)
		end
		return true, outcome
	end

	function runtime.stop(reason: string?): boolean
		if state ~= "running" then
			return false
		end
		local now = deps.clock.now()
		local cleaned = 0
		local allRecords: { any } = deps.mobs.all(registry)
		for _, mob in ipairs(allRecords) do
			cleanup(mob)
			if mob.state == "alive" then
				local record = mob :: any
				deps.mobs.despawn(record, now)
				releaseOccupancy(record.spawnPointId)
				cleaned = cleaned + 1
				emit("mob_despawned", { mob = record.id, reason = reason or "manual" })
			end
		end
		emit("wave_stopped", { wave = waveIndex, activeCleaned = cleaned, reason = reason or "manual" })
		state = "stopped"
		phase = "idle"
		pending = 0
		return true
	end

	function runtime.records(): { any }
		return deps.mobs.all(registry)
	end

	function runtime.status(): any
		return {
			state = state,
			phase = phase,
			wave = waveIndex,
			pending = pending,
			active = deps.mobs.aliveCount(registry),
			spawnedInWave = spawnedInWave,
			killedInWave = killedInWave,
			totalSpawned = totalSpawned,
			totalKilled = totalKilled,
			wavesCompleted = wavesCompleted,
		}
	end

	return runtime
end

return WaveRuntime
