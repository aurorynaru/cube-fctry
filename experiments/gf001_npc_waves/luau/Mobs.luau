--!strict
-- GF-001 offline NPC wave prototype: mob records and health/death transitions.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Pure Luau,
-- no Roblox engine APIs. Mob records are plain data: a record dies exactly once
-- and every later damage/kill on it is ignored, which is the foundation
-- for duplicate death/reward prevention in WaveRuntime and Rewards.

local Mobs = {}

function Mobs.new(nextId: number?): any
	return { nextId = nextId or 1, records = {} }
end

function Mobs.spawn(registry: any, mobDef: any, mobId: string, spawnPointId: string, now: number): any
	local record = {
		id = string.format("mob-%04d", registry.nextId),
		mobId = mobId,
		health = mobDef.maxHealth,
		maxHealth = mobDef.maxHealth,
		state = "alive",
		spawnPointId = spawnPointId,
		bornAt = now,
		diedAt = nil,
		rewarded = false,
		cleaned = false,
	}
	table.insert(registry.records, record)
	registry.nextId = registry.nextId + 1
	return record
end

function Mobs.damage(mob: any, amount: number, now: number): string
	if type(amount) ~= "number" or not (amount > 0 and amount < math.huge) then
		return "invalid_damage"
	end
	if mob.state ~= "alive" then
		return "ignored"
	end
	mob.health = mob.health - amount
	if mob.health <= 0 then
		mob.health = 0
		mob.state = "dead"
		mob.diedAt = now
		return "died"
	end
	return "damaged"
end

function Mobs.kill(mob: any, now: number): string
	if mob.state ~= "alive" then
		return "ignored"
	end
	mob.health = 0
	mob.state = "dead"
	mob.diedAt = now
	return "died"
end

function Mobs.despawn(mob: any, now: number): string
	if mob.state == "despawned" then
		return "ignored"
	end
	mob.state = "despawned"
	mob.despawnedAt = now
	return "despawned"
end

function Mobs.aliveCount(registry: any): number
	local count = 0
	for _, mob in ipairs(registry.records) do
		if mob.state == "alive" then
			count = count + 1
		end
	end
	return count
end

function Mobs.all(registry: any): { any }
	local records = {}
	for _, mob in ipairs(registry.records) do
		table.insert(records, mob)
	end
	return records
end

return Mobs
