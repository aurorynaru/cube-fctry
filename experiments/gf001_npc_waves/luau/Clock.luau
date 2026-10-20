--!strict
-- GF-001 offline NPC wave prototype: injectable monotonic clock.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Pure Luau,
-- no Roblox engine APIs and no ambient time source. WaveRuntime only reads
-- time through deps.clock.now() so tests and hosts can drive it deterministically.

local Clock = {}

function Clock.new(nowFunction: () -> number): any
	return { now = nowFunction }
end

function Clock.stepping(startAt: number?): any
	local t = startAt or 0
	return {
		now = function(): number
			return t
		end,
		advance = function(deltaTime: number)
			t = t + deltaTime
		end,
	}
end

return Clock
