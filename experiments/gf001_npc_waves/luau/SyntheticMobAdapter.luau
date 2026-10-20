--!strict
-- GF-001-Q2 offline server-owned orchestration over the unchanged WaveRuntime.
-- Factory and events are trusted, synchronous, non-yielding server dependencies.

local SyntheticMobAdapter = {}

function SyntheticMobAdapter.new(config: any, deps: any): any
	assert(type(deps) == "table" and type(deps.factory) == "table", "synthetic factory required")
	local factory = deps.factory
	assert(type(factory.create) == "function" and type(factory.owns) == "function", "factory contract required")
	local bindings: { [string]: any } = {}
	local token: any = nil
	local uncertain = false
	local faulted = false
	local runtime: any = nil
	local session = {}
	local adapter = {}

	local function owned(binding: any): boolean
		local object = binding.object
		local owns = factory.owns :: (any, any) -> boolean
		return owns(object, binding.token)
			and object.synthetic == true
			and object.OwnerToken == binding.token
			and object.MobRecordId == binding.record.id
			and object.MobId == binding.record.mobId
			and object.Humanoid == binding.humanoid
	end

	local function disarm()
		for _, binding in pairs(bindings) do
			binding.active = false
		end
	end

	function adapter.spawn(record: any, point: any): boolean
		local ok, created, object = pcall(factory.create, record, point, token)
		if not ok then
			-- A throwing factory may have allocated an object without returning it.
			uncertain = true
			error("synthetic factory creation uncertain", 0)
		end
		if object == nil then
			if created == true then
				uncertain = true -- claimed success without an object is not a known-empty failure
			end
			return false
		end
		local binding: any = {
			record = record,
			object = object,
			humanoid = object.Humanoid,
			token = token,
			active = false,
			connection = nil,
		}
		bindings[record.id] = binding
		if not owned(binding) then
			uncertain = true
			error("synthetic object ownership unknown", 0)
		end
		if created ~= true then
			return false -- partial but verified-owned object is retained for stop cleanup
		end
		if
			type(binding.humanoid) ~= "table"
			or type(binding.humanoid.Died) ~= "table"
			or type(binding.humanoid.Died.Connect) ~= "function"
		then
			return false
		end
		local connected, connection = pcall(binding.humanoid.Died.Connect, function()
			if not binding.active or token ~= binding.token or bindings[record.id] ~= binding or not owned(binding) then
				return
			end
			if runtime.status().state ~= "running" or record.state ~= "alive" then
				return
			end
			local deathOk, accepted, outcome = pcall(runtime.killMob, record.id)
			if not deathOk then
				uncertain = true
				session.stop("death_callback_failure")
			elseif not accepted or outcome ~= "died" then
				binding.active = false
			end
		end)
		if not connected or type(connection) ~= "table" or type(connection.Disconnect) ~= "function" then
			-- A failed Connect could have registered a callback without returning it.
			uncertain = true
			return false
		end
		binding.connection = connection
		binding.active = true
		return true
	end

	function adapter.despawn(record: any): boolean
		local binding = bindings[record.id]
		if binding == nil then
			return true -- no object returned by the factory
		end
		binding.active = false
		if binding.record ~= record or not owned(binding) then
			uncertain = true
			return false -- never delete unknown/foreign resources
		end
		if binding.connection ~= nil then
			local ok, disconnected = pcall(binding.connection.Disconnect)
			if not ok or disconnected ~= true then
				return false
			end
			binding.connection = nil
		end
		local ok, destroyed = pcall(binding.object.Destroy)
		if not ok or destroyed ~= true or binding.object.Destroyed ~= true then
			return false
		end
		bindings[record.id] = nil
		return true
	end

	runtime = deps.waveRuntime.new(config, {
		clock = deps.clock,
		rng = deps.rng,
		adapter = adapter,
		events = deps.events,
		mobs = deps.mobs,
		selectSpawn = deps.selectSpawn,
		rewards = deps.rewards,
	})

	function session.start(): (boolean, string?)
		if uncertain or next(bindings) ~= nil then
			return false, "cleanup_unverified"
		end
		if runtime.status().state == "running" then
			return false, "already_running"
		end
		token = {} -- unique identity even across distinct runtime objects
		faulted = false
		return runtime.start()
	end

	function session.stop(reason: string?): (boolean, string?)
		disarm()
		local ok, stopped = pcall(runtime.stop, reason or "interrupted")
		if not ok then
			faulted = true
			return false, "cleanup_failed"
		end
		if uncertain or next(bindings) ~= nil then
			return false, "cleanup_unverified"
		end
		return stopped, nil
	end

	function session.tick(): (boolean, string?)
		if uncertain then
			session.stop("adapter_failure")
			return false, "cleanup_unverified"
		end
		if faulted then
			return false, "cleanup_failed"
		end
		local ok, accepted, reason = pcall(runtime.tick)
		if not ok then
			faulted = true
			local cleaned, cleanupReason = session.stop("adapter_failure")
			if not cleaned then
				return false, cleanupReason
			end
			return false, "adapter_failure"
		end
		if runtime.status().state == "completed" and (uncertain or next(bindings) ~= nil) then
			return false, "cleanup_unverified"
		end
		return accepted, reason
	end

	function session.clientRewardClaim(player: any, payload: any): any
		return deps.rewards.handleClientRequest(player, payload, deps.clock.now())
	end

	function session.status(): any
		return runtime.status()
	end

	return session
end

return SyntheticMobAdapter
