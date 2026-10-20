--!strict
-- GF-001 offline NPC wave prototype: pure in-memory runtime adapter.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Records
-- spawn/despawn calls as plain data and always succeeds. It exists so the
-- deterministic tests can observe the adapter seam without any Roblox engine
-- API. A future authorized Studio milestone replaces this with an adapter that
-- creates and destroys real NPC instances.

local MemoryAdapter = {}

function MemoryAdapter.new(): any
	local adapter = { spawns = {}, despawns = {} }

	function adapter.spawn(mob: any, spawnPoint: any): boolean
		table.insert(adapter.spawns, {
			mob = mob.id,
			mobId = mob.mobId,
			spawnPoint = spawnPoint.id,
			position = spawnPoint.position,
		})
		return true
	end

	function adapter.despawn(mob: any): boolean
		table.insert(adapter.despawns, { mob = mob.id })
		return true
	end

	return adapter
end

return MemoryAdapter
