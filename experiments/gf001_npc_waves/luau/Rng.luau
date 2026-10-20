--!strict
-- GF-001 offline NPC wave prototype: injectable deterministic randomness.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Pure Luau,
-- no Roblox engine APIs and no use of the ambient math.random stream. A seeded
-- Lehmer generator (minstd) keeps spawn-point tie-breaks reproducible offline.

local Rng = {}

local MODULUS = 2147483647
local MULTIPLIER = 48271

local function makeRng(nextFloat: () -> number): any
	local rng = {}
	function rng.nextFloat(): number
		return nextFloat()
	end
	function rng.pick(items: { any }): any
		local count = #items
		if count == 0 then
			error("[GF001] Rng.pick requires a non-empty list", 0)
		end
		local index = math.floor(nextFloat() * count) + 1
		if index > count then
			index = count
		end
		return items[index]
	end
	return rng
end

function Rng.new(source: any): any
	if type(source) == "function" then
		local sourceFunction = source :: () -> any
		return makeRng(function(): number
			local value = sourceFunction()
			if type(value) ~= "number" or not (value >= 0 and value < 1) then
				error("[GF001] injected Rng source must return a number in [0, 1)", 0)
			end
			return value
		end)
	end
	local seed = 0
	if type(source) == "number" then
		if source ~= source or math.abs(source) == math.huge then
			error("[GF001] Rng seed must be finite", 0)
		end
		seed = source
	end
	local current = math.floor(math.abs(seed)) % (MODULUS - 1) + 1
	return makeRng(function(): number
		current = (current * MULTIPLIER) % MODULUS
		return current / MODULUS
	end)
end

return Rng
