--!strict
-- GF-001 offline NPC wave prototype: server-authoritative reward intents.
--
-- Part of experiments/gf001_npc_waves/ (isolated, non-production). Pure Luau,
-- no Roblox engine APIs. Reward intents are emitted ONLY from server-verified
-- mob deaths and are validated against the server-held mob definition: the
-- points value always comes from config, never from a client. Client reward
-- requests are always rejected and never produce reward intents. There is no
-- currency balance, DataStore write, purchase flow or client grant here.

local Rewards = {}

function Rewards.new(deps: any): any
	if type(deps) ~= "table" or type(deps.events) ~= "table" then
		error("[GF001] Rewards.new requires deps.events", 0)
	end
	local events = deps.events
	local rewards = {}

	function rewards.recordDeath(mob: any, mobDef: any, now: number): any
		if mob.state ~= "dead" then
			return nil
		end
		if mob.rewarded then
			return nil
		end
		local points = nil
		if type(mobDef) == "table" and type(mobDef.reward) == "table" then
			points = mobDef.reward.points
		end
		if type(points) ~= "number" or not (points >= 0 and points < math.huge) or points % 1 ~= 0 then
			return nil
		end
		mob.rewarded = true
		local event = {
			type = "reward_intent",
			mob = mob.id,
			mobId = mob.mobId,
			points = points,
			at = now,
		}
		table.insert(events, event)
		return event
	end

	function rewards.handleClientRequest(playerId: any, payload: any, now: number): any
		local event = {
			type = "client_reward_rejected",
			player = playerId,
			payloadType = type(payload),
			reason = "client_reward_claims_are_not_authoritative",
			at = now,
		}
		table.insert(events, event)
		return nil
	end

	return rewards
end

return Rewards
