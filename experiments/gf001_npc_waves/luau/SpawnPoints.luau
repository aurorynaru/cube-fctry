--!strict
-- GF-001 offline NPC wave prototype: spawn point selection.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Pure Luau,
-- no Roblox engine APIs. Selection is deterministic: only points below capacity
-- are eligible, the least-occupied points are preferred and ties are broken by
-- the injected Rng.

local SpawnPoints = {}

function SpawnPoints.select(spawnPoints: { any }, occupancy: any, rng: any): any
	local minimum = nil
	for _, spawnPoint in ipairs(spawnPoints) do
		local occupied = occupancy[spawnPoint.id] or 0
		if occupied < spawnPoint.capacity then
			if minimum == nil or occupied < minimum then
				minimum = occupied
			end
		end
	end
	if minimum == nil then
		return nil
	end
	local eligible = {}
	for _, spawnPoint in ipairs(spawnPoints) do
		local occupied = occupancy[spawnPoint.id] or 0
		if occupied < spawnPoint.capacity and occupied == minimum then
			table.insert(eligible, spawnPoint)
		end
	end
	return rng.pick(eligible)
end

return SpawnPoints
