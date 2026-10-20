--!strict
-- GF-001-Q4 offline server-owned composition/binding module over the
-- UNCHANGED GF-001 wave core (WaveRuntime/Mobs/Rewards/SpawnPoints), behind
-- an injected, narrow engine-operations interface.
--
-- This is a reusable module, not a test probe: a future Roblox-specific
-- engine-operations implementation can replace the standalone Luau mock
-- without touching this composition root or the wave core. The composition
-- root privately owns the validated server-held wave configuration, the
-- WaveRuntime instance, the exact run identity token, mob-record-to-object
-- bindings, the reverse lookup by exact object reference, model/Humanoid
-- references, every returned event connection handle, spawn-point
-- association, cleanup obligations and failure state, and the bounded
-- serial death-event queue.
--
-- Ownership is established ONLY by the engine-operations issuance ledger and
-- exact captured references: never by mutable display names, attributes,
-- tags, client IDs or mock-only fields. Engine Disconnect/Destroy are void:
-- acknowledgment uses the exact issued handle/instance plus connection- and
-- hierarchy-specific observations, never a return value or pcall success
-- alone. Unknown allocation/listener state faults the run and prohibits
-- automatic restart; known partially allocated resources remain cleanup
-- obligations. All engine access is synchronous and non-yielding in this
-- offline model; a real engine implementation must additionally serialize
-- or refuse yields at these boundaries.

local Config = require("./Config")
local Rewards = require("./Rewards")

local ServerOwnedBinding = {}

local MAX_PENDING_DEATHS = 8

-- Plain data only: never apply this to opaque engine values. No metatables or
-- caller-held nested tables cross the server configuration/snapshot boundary.
local function copyData(value: any): any
	if type(value) ~= "table" then
		return value
	end
	assert(getmetatable(value) == nil, "plain data required")
	local result = {}
	for key, child in pairs(value) do
		result[key] = copyData(child)
	end
	return result
end

local function freezeData(value: any): any
	if type(value) == "table" then
		for _, child in pairs(value) do
			freezeData(child)
		end
		table.freeze(value)
	end
	return value
end

function ServerOwnedBinding.new(rawConfig: any, deps: any): any
	if type(deps) ~= "table" then
		error("[GF001-Q4] ServerOwnedBinding requires a deps table", 0)
	end
	for _, name in ipairs({ "clock", "rng", "waveRuntime", "mobs", "selectSpawn", "engineOps" }) do
		if deps[name] == nil then
			error("[GF001-Q4] ServerOwnedBinding deps." .. name .. " is required", 0)
		end
	end
	local engineOps: any = deps.engineOps
	for _, name in ipairs({
		"createRunContainer",
		"createMob",
		"describeIssue",
		"isModel",
		"isHumanoid",
		"humanoidOf",
		"humanoidDead",
		"connectDeath",
		"disconnect",
		"isConnected",
		"destroy",
		"parentOf",
		"isDescendantOf",
		"ownsContainer",
		"containerEmpty",
		"connectionIssued",
		"teardownObserved",
		"containerTeardownObserved",
	}) do
		if type(engineOps[name]) ~= "function" then
			error("[GF001-Q4] engineOps." .. name .. " must be a function", 0)
		end
	end
	if type(engineOps.contract) ~= "table" then
		error("[GF001-Q4] engineOps.contract is required", 0)
	end
	local validConfig, config = Config.validate(copyData(rawConfig))
	if not validConfig then
		error("[GF001-Q4] ServerOwnedBinding requires a validated config: " .. table.concat(config, "; "), 0)
	end
	freezeData(config)
	local points: { [string]: any } = {}
	for _, point in ipairs(config.spawnPoints :: { any }) do
		points[point.id] = point
	end

	-- Private, server-held run state.
	local events: { any } = {}
	local rewards = Rewards.new({ events = events })
	local token: any = nil
	local container: any = nil
	local bindings: { [string]: any } = {}
	local byModel: { [any]: any } = {}
	local queue: { any } = {}
	local obligations: { any } = {}
	local unresolvedAllocations: { [string]: any } = {}
	local runSerial = 0
	local uncertain = false
	local faulted = false
	local stopping = false
	local draining = false
	local overflowObserved = false
	local reentrancyObserved = false
	local teardownEventsRefused = 0
	local staleEventsRefused = 0
	local forgedEventsRefused = 0
	local earlyDeathsRefused = 0
	local runtime: any = nil
	local busy = false
	local lastFailure: any = nil
	local cleanupFailed = false
	local contract: any = nil

	-- Every engine operation is run to completion on one private coroutine.
	-- A suspension is an unknown operation outcome, never an acknowledgment.
	-- The suspended thread is neither returned nor resumed by this module.
	local rawOps = engineOps
	engineOps = {}
	for name, fn in pairs(rawOps) do
		if type(fn) == "function" then
			local operation = fn :: (...any) -> ...any
			local operationName = tostring(name)
			engineOps[name] = function(...: any): ...any
				local thread = coroutine.create(operation)
				local result = table.pack(coroutine.resume(thread, ...))
				if coroutine.status(thread) ~= "dead" then
					uncertain = true
					faulted = true
					lastFailure = "unexpected_yield:" .. operationName
					error(lastFailure, 0)
				end
				if not result[1] then
					lastFailure = "operation_error:" .. operationName
					if name ~= "disconnect" and name ~= "destroy" then
						uncertain = true
					end
					error(result[2], 0)
				end
				return table.unpack(result, 2, result.n)
			end
		end
	end

	local function recordObligation(recordId: string, reason: string)
		table.insert(obligations, { record = recordId, reason = reason })
	end

	local function countBindings(): number
		local count = 0
		for _ in pairs(bindings) do
			count += 1
		end
		return count
	end

	local function issueReceiptMatches(binding: any): boolean
		if not engineOps.isModel(binding.model) then
			return false
		end
		local receipt = engineOps.describeIssue(binding.model)
		if receipt == nil then
			return false -- never issued for this run: foreign object
		end
		if receipt.runToken ~= binding.runToken then
			return false
		end
		if receipt.recordId ~= binding.recordId or receipt.mobId ~= binding.mobId then
			return false
		end
		if receipt.spawnPointId ~= binding.spawnPointId then
			return false
		end
		if engineOps.ownsContainer(container, binding.runToken) ~= true then
			return false
		end
		if binding.humanoid ~= nil then
			if receipt.humanoid ~= binding.humanoid then
				return false
			end
			if engineOps.humanoidOf(binding.model) ~= binding.humanoid then
				return false -- humanoid replaced after issuance
			end
		end
		return true
	end

	local function makeDeathCallback(binding: any)
		return function()
			if binding.runToken ~= token then
				staleEventsRefused += 1
				return
			end
			if stopping then
				teardownEventsRefused += 1
				return
			end
			if draining then
				-- Reentrant delivery during the serialized drain boundary:
				-- unresolved event ordering is refused, never replayed.
				reentrancyObserved = true
				return
			end
			if binding.phase ~= "active" or not binding.active then
				if binding.phase == "connecting" then
					-- Delivery during registration is held for explicit
					-- reconciliation before activation, never authorized inline.
					binding.earlyDeath = true
				end
				return
			end
			if #queue >= MAX_PENDING_DEATHS then
				overflowObserved = true
				return
			end
			table.insert(queue, {
				runToken = binding.runToken,
				binding = binding,
				model = binding.model,
				humanoid = binding.humanoid,
			})
		end
	end

	local function disarmAll()
		for _, binding in pairs(bindings) do
			binding.active = false
		end
	end

	-- Conservative teardown of exactly the issued resources of one binding.
	-- Returns true only when the defined scoped teardown observations hold for
	-- every positively identified resource; otherwise the obligation is
	-- retained (retryable "cleanup_failed") or the run becomes uncertain
	-- ("uncertain": foreign/ambiguous identity, restart prohibited).
	local function teardownBinding(binding: any): (boolean, string?)
		binding.active = false
		if binding.cleaned then
			return true, nil
		end
		binding.phase = "teardown"
		if bindings[binding.recordId] ~= binding or byModel[binding.model] ~= binding then
			uncertain = true
			return false, "uncertain"
		end
		if not issueReceiptMatches(binding) then
			uncertain = true
			return false, "uncertain" -- never delete a foreign or re-issued object
		end
		if binding.modelTeardownObserved and binding.listenerUnknown then
			return false, "uncertain" -- known model cleaned; unreturned listener remains unaccounted
		end
		if not binding.destructionAttempted and engineOps.parentOf(binding.model) ~= container then
			uncertain = true -- externally moved/unparented: quarantine
			return false, "uncertain"
		end
		if binding.connection ~= nil then
			if engineOps.connectionIssued(binding.connection, binding.humanoid) ~= true then
				uncertain = true
				return false, "uncertain"
			end
			local disconnectOk = pcall(engineOps.disconnect, binding.connection)
			if not disconnectOk then
				return false, "cleanup_failed" -- exact handle retained for guarded retry
			end
			if engineOps.isConnected(binding.connection) ~= false then
				return false, "cleanup_failed" -- observation: still connected, retained
			end
		end
		binding.destructionAttempted = true
		local destroyOk = pcall(engineOps.destroy, binding.model)
		if not destroyOk then
			if engineOps.parentOf(binding.model) == nil and not engineOps.isDescendantOf(binding.model, container) then
				uncertain = true
				return false, "uncertain" -- ambiguous: possibly destroyed, then thrown
			end
			return false, "cleanup_failed" -- intact and still ours: retryable
		end
		if engineOps.isDescendantOf(binding.model, container) then
			return false, "cleanup_failed" -- silent no-op or silent failure: no false success
		end
		if engineOps.teardownObserved(binding.model, binding.humanoid, container) ~= true then
			-- Removal/unparenting is not proof of the agreed scoped teardown.
			uncertain = true
			return false, "uncertain"
		end
		binding.modelTeardownObserved = true
		if binding.listenerUnknown then
			-- The model is torn down, but a listener that was possibly
			-- installed without a returned handle can never be accounted.
			uncertain = true
			recordObligation(binding.recordId, "unknown_listener")
			return false, "uncertain" -- withhold the core record.cleaned acknowledgment too
		end
		binding.cleaned = true
		bindings[binding.recordId] = nil
		byModel[binding.model] = nil
		return true, nil
	end

	local function adapterSpawn(record: any, point: any): boolean
		if uncertain or faulted or stopping or token == nil then
			return false
		end
		if
			points[point.id] ~= point
			or record.spawnPointId ~= point.id
			or config.mobs[record.mobId] == nil
			or record.state ~= "alive"
			or bindings[record.id] ~= nil
			or runtime.status().state ~= "running"
		then
			uncertain = true
			return false
		end
		-- Only an immutable allocation descriptor crosses the trusted ops seam;
		-- the mutable core record remains private to this composition root.
		local allocation = freezeData({ id = record.id, mobId = record.mobId, maxHealth = record.maxHealth })
		local createOk, created, model, returnedHumanoid =
			pcall(engineOps.createMob, allocation, point, container, token)
		if not createOk then
			-- A thrown allocation may have created resources without
			-- returning them: unknown allocation faults the run.
			uncertain = true
			unresolvedAllocations[record.id] = { record = record }
			recordObligation(record.id, "unknown_allocation")
			error("[GF001-Q4] engine allocation threw: unknown allocation state", 0)
		end
		if model == nil then
			if created == false and returnedHumanoid == nil and contract.failedCreateGuaranteesNoAllocation == true then
				return false -- allocation-free failure per the declared contract
			end
			uncertain = true
			-- Any returned child is registered even if the root was omitted;
			-- no ownership/destruction inference is made for that opaque value.
			unresolvedAllocations[record.id] = { record = record, humanoid = returnedHumanoid }
			recordObligation(record.id, "unknown_allocation")
			error("[GF001-Q4] nil allocation without a no-allocation guarantee", 0)
		end
		-- Register every returned resource reference BEFORE subsequent
		-- fallible work.
		local binding: any = {
			runToken = token,
			record = record,
			recordId = record.id,
			mobId = record.mobId,
			spawnPointId = point.id,
			model = model,
			humanoid = returnedHumanoid,
			connection = nil,
			phase = "allocated",
			active = false,
			earlyDeath = false,
			deathAccepted = false,
			listenerUnknown = false,
			cleaned = false,
		}
		if byModel[model] ~= nil then
			uncertain = true
			unresolvedAllocations[record.id] = { record = record, model = model, humanoid = returnedHumanoid }
			recordObligation(record.id, "duplicate_model_reference")
			return false
		end
		bindings[record.id] = binding
		byModel[model] = binding
		local humanoid = engineOps.humanoidOf(model)
		local receipt = engineOps.describeIssue(model)
		if receipt == nil then
			uncertain = true
			error("[GF001-Q4] engine returned a foreign allocation", 0)
		end
		if
			receipt.runToken ~= token
			or receipt.recordId ~= record.id
			or receipt.mobId ~= record.mobId
			or receipt.spawnPointId ~= point.id
		then
			uncertain = true
			error("[GF001-Q4] allocation identity does not match the run", 0)
		end
		if returnedHumanoid ~= humanoid then
			uncertain = true
			error("[GF001-Q4] allocation returned a different Humanoid", 0)
		end
		if created ~= true then
			return false
		end -- known partial remains a teardown obligation
		if humanoid == nil and receipt.humanoid == nil then
			return false -- known-owned incomplete allocation: retained, cleanable
		end
		if not engineOps.isHumanoid(humanoid) or receipt.humanoid ~= humanoid then
			uncertain = true
			error("[GF001-Q4] humanoid association is missing or was replaced", 0)
		end
		binding.humanoid = humanoid
		if
			not engineOps.isModel(model)
			or engineOps.isDescendantOf(model, container) ~= true
			or engineOps.humanoidDead(humanoid)
		then
			return false
		end
		binding.phase = "connecting"
		local connectOk, connection = pcall(engineOps.connectDeath, humanoid, makeDeathCallback(binding))
		if not connectOk then
			-- The subscription may have installed a listener without
			-- returning its handle: unknown listener state.
			binding.listenerUnknown = true
			uncertain = true
			error("[GF001-Q4] engine event subscription threw: unknown listener state", 0)
		end
		if connection == nil then
			if contract.connectNilGuaranteesNoListener == true then
				return false -- no listener installed, per the declared contract
			end
			binding.listenerUnknown = true
			uncertain = true
			error("[GF001-Q4] nil connection handle without a no-listener guarantee", 0)
		end
		-- Register the exact connection handle actually returned.
		binding.connection = connection
		if engineOps.connectionIssued(connection, humanoid) ~= true or engineOps.isConnected(connection) ~= true then
			uncertain = true
			return false
		end
		if not issueReceiptMatches(binding) then
			uncertain = true
			return false
		end
		if engineOps.humanoidDead(humanoid) then
			binding.earlyDeath = true
		end
		if binding.earlyDeath then
			-- Conservative refusal: an event arrived during registration and
			-- cannot be safely reconciled into an authorized spawn.
			earlyDeathsRefused += 1
			cleanupFailed = true
			local cleaned = teardownBinding(binding)
			cleanupFailed = not cleaned
			return false
		end
		binding.phase = "active"
		binding.active = true
		return true
	end

	local function adapterDespawn(record: any): boolean
		local binding = bindings[record.id]
		if binding == nil then
			if unresolvedAllocations[record.id] ~= nil then
				return false
			end
			return true -- no resource was ever issued for this record
		end
		if binding.record ~= record then
			uncertain = true
			return false -- forged record: never touch the bound resource
		end
		cleanupFailed = true -- kept true on exceptions as well as false returns
		local ok, reason = teardownBinding(binding)
		cleanupFailed = not ok
		if not ok then
			if reason == "uncertain" then
				uncertain = true
			end
			return false
		end
		return true
	end

	runtime = deps.waveRuntime.new(config, {
		clock = deps.clock,
		rng = deps.rng,
		adapter = { spawn = adapterSpawn, despawn = adapterDespawn },
		events = events,
		mobs = deps.mobs,
		selectSpawn = deps.selectSpawn,
		rewards = rewards,
	})

	-- Serial, validated drain of the bounded death queue. Revalidates run
	-- identity, exact binding/model/Humanoid identity, issuance state,
	-- record state, server-held death eligibility and duplicate-death status
	-- before forwarding into the unchanged WaveRuntime death transition.
	local function drainDeaths(): (boolean, string?)
		if draining then
			return false, "reentrant_drain_refused"
		end
		if overflowObserved then
			return false, "death_queue_overflow"
		end
		draining = true
		while #queue > 0 do
			local candidate = table.remove(queue, 1)
			local binding = candidate.binding
			if candidate.runToken ~= token then
				staleEventsRefused += 1
				continue
			end
			if bindings[binding.recordId] ~= binding or byModel[binding.model] ~= binding then
				if bindings[binding.recordId] ~= nil then
					uncertain = true -- binding replaced under the run
				end
				continue
			end
			if
				binding.phase ~= "active"
				or not binding.active
				or binding.deathAccepted
				or binding.record.state ~= "alive"
			then
				continue -- disarmed, duplicate or already dead
			end
			if
				candidate.model ~= binding.model
				or candidate.humanoid ~= binding.humanoid
				or not issueReceiptMatches(binding)
				or engineOps.isDescendantOf(binding.model, container) ~= true
			then
				uncertain = true
				lastFailure = "death_binding_mismatch"
				break
			end
			if not engineOps.humanoidDead(binding.humanoid) then
				forgedEventsRefused += 1 -- engine state does not corroborate death
				continue
			end
			if runtime.status().state ~= "running" then
				continue
			end
			local killOk, accepted, outcome = pcall(runtime.killMob, binding.recordId)
			if not killOk then
				uncertain = true
				break
			elseif accepted and outcome == "died" then
				binding.deathAccepted = true
			end
		end
		draining = false
		if uncertain then
			return false, "cleanup_unverified"
		end
		if reentrancyObserved then
			return false, "reentrant_death_event"
		end
		return true, nil
	end

	local function teardownContainer(): boolean
		if container == nil then
			return true
		end
		if engineOps.ownsContainer(container, token) ~= true or engineOps.containerEmpty(container) ~= true then
			uncertain = true -- never destroy a container with unverified descendants
			return false
		end
		local destroyOk = pcall(engineOps.destroy, container)
		if not destroyOk then
			if engineOps.parentOf(container) == nil then
				uncertain = true -- ambiguous: possibly destroyed, then thrown
			end
			return false -- retained: guarded retry or uncertain
		end
		if engineOps.parentOf(container) ~= nil then
			return false -- silent no-op: retained, no false success
		end
		if engineOps.containerTeardownObserved(container, token) ~= true then
			uncertain = true
			return false
		end
		container = nil
		return true
	end

	local function finishRun(): boolean
		if next(bindings) ~= nil then
			uncertain = true
			return false
		end
		if not teardownContainer() then
			faulted = true
			lastFailure = "container_cleanup_unverified"
			return false
		end
		token = nil
		queue = {}
		return true
	end

	local session: any = {}

	function session.start(): (boolean, string?)
		if uncertain then
			return false, "cleanup_unverified"
		end
		if next(bindings) ~= nil or #obligations > 0 then
			return false, "cleanup_unverified" -- outstanding adapter obligations
		end
		if runtime.status().state == "running" then
			return false, "already_running"
		end
		if container ~= nil then
			return false, "cleanup_unverified" -- run container not torn down
		end
		overflowObserved = false
		reentrancyObserved = false
		contract = copyData(rawOps.contract)
		token = {} -- minted BEFORE allocation so the container is issued to this run
		local containerOk, newContainer = pcall(engineOps.createRunContainer, token)
		if not containerOk then
			uncertain = true
			return false, "cleanup_unverified" -- unknown container allocation
		end
		if newContainer == nil then
			if contract.failedCreateGuaranteesNoAllocation == true then
				return false, "engine_unavailable" -- allocation-free per contract
			end
			uncertain = true
			return false, "cleanup_unverified"
		end
		container = newContainer
		if engineOps.ownsContainer(container, token) ~= true then
			uncertain = true
			return false, "cleanup_unverified"
		end
		runSerial += 1
		faulted = false
		queue = {} -- stale candidates from any prior run are dropped
		return runtime.start()
	end

	function session.stop(reasonArg: string?): (boolean, string?)
		local reason = reasonArg or "interrupted"
		if stopping then
			return false, "stopping"
		end
		if draining then
			return false, "drain_in_progress" -- serialized boundary: refuse, never stop mid-drain
		end
		stopping = true
		disarmAll() -- disarm event forwarding FIRST
		local ok, stopped = pcall(runtime.stop, reason)
		if not ok then
			stopping = false
			faulted = true
			return false, if uncertain then "cleanup_unverified" else "cleanup_failed"
		end
		local outstanding = next(bindings) ~= nil
		if not outstanding and not uncertain and container ~= nil then
			outstanding = not teardownContainer()
		end
		stopping = false
		if uncertain then
			return false, "cleanup_unverified"
		end
		if outstanding then
			return false, "cleanup_unverified"
		end
		token = nil
		queue = {} -- queued events after an interrupted run are never accepted
		return stopped, nil
	end

	function session.tick(): (boolean, string?)
		if faulted then
			return false, "cleanup_failed"
		end
		if stopping then
			return false, "stopping"
		end
		if draining then
			return false, "drain_in_progress" -- serialized boundary: refuse reentry
		end
		if uncertain then
			session.stop("adapter_failure")
			return false, "cleanup_unverified"
		end
		if overflowObserved then
			session.stop("death_queue_overflow")
			return false, "death_queue_overflow"
		end
		if reentrancyObserved then
			session.stop("reentrant_death_event")
			return false, "reentrant_death_event"
		end
		cleanupFailed = false
		local tickOk, accepted, tickReason = pcall(runtime.tick)
		if not tickOk then
			faulted = true
			disarmAll()
			if cleanupFailed then
				-- Failed teardown is never automatically retried by another
				-- stop inside this tick. Only a subsequent explicit stop may retry.
				return false, if uncertain then "cleanup_unverified" else "cleanup_failed"
			end
			local stopOk, stopReason = session.stop("adapter_failure")
			if not stopOk then
				return false, stopReason or "cleanup_unverified"
			end
			return false, "adapter_failure"
		end
		if not accepted then
			return false, tickReason
		end
		local drainOk, drainReason = drainDeaths()
		if not drainOk then
			session.stop(drainReason or "adapter_failure")
			return false, drainReason
		end
		if uncertain then
			session.stop("adapter_failure")
			return false, "cleanup_unverified"
		end
		if runtime.status().state == "completed" then
			if not finishRun() then
				return false, "cleanup_unverified"
			end
		end
		return true, nil
	end

	function session.drain(): (boolean, string?)
		if stopping then
			return false, "stopping"
		end
		local ok, reason = drainDeaths()
		if not ok then
			if reason ~= "reentrant_drain_refused" then
				session.stop(reason or "adapter_failure")
			end
			return false, reason
		end
		return true, nil
	end

	function session.clientRewardClaim(playerId: any, payload: any): any
		-- Client claims are never authoritative; no payout path exists.
		local player = if type(playerId) == "string" or type(playerId) == "number" then playerId else "untrusted"
		return rewards.handleClientRequest(player, payload, deps.clock.now())
	end

	function session.status(): any
		local status = runtime.status()
		status.pendingDeaths = #queue
		status.activeBindings = countBindings()
		status.deathQueueLimit = MAX_PENDING_DEATHS
		status.uncertain = uncertain
		status.bindingState = if uncertain then "uncertain" elseif faulted then "faulted" else status.state
		status.faulted = faulted
		status.runSerial = runSerial
		status.restartAllowed = not uncertain and next(bindings) == nil and #obligations == 0 and container == nil
		return status
	end

	function session.eventLog(): { any }
		return copyData(events)
	end

	function session.recordsSnapshot(): { any }
		return copyData(runtime.records()) -- scalar/plain data only; no engine references
	end

	function session.report(): any
		local retained = {}
		for _, binding in pairs(bindings) do
			table.insert(retained, {
				record = binding.recordId,
				phase = binding.phase,
				listenerUnknown = binding.listenerUnknown,
				active = binding.active,
			})
		end
		return {
			state = runtime.status().state,
			runSerial = runSerial,
			pendingDeaths = #queue,
			deathQueueLimit = MAX_PENDING_DEATHS,
			activeBindings = countBindings(),
			retainedObligations = copyData(obligations),
			lastFailure = lastFailure,
			bindings = retained,
			containerOutstanding = container ~= nil,
			uncertain = uncertain,
			faulted = faulted,
			overflowObserved = overflowObserved,
			reentrancyObserved = reentrancyObserved,
			teardownEventsRefused = teardownEventsRefused,
			staleEventsRefused = staleEventsRefused,
			forgedEventsRefused = forgedEventsRefused,
			earlyDeathsRefused = earlyDeathsRefused,
			restartAllowed = not uncertain and next(bindings) == nil and #obligations == 0 and container == nil,
		}
	end

	-- The returned controls serialize ALL lifecycle entry points, including
	-- reentry from a trusted injected operation while tick is spawning/cleaning.
	local public: any = {}
	for name, fn in pairs(session) do
		if name == "start" or name == "tick" or name == "stop" or name == "drain" then
			local control = fn :: (...any) -> ...any
			public[name] = function(...: any): (boolean, string?)
				if busy then
					reentrancyObserved = true
					return false,
						if name == "drain" and draining then "reentrant_drain_refused" else "reentrant_control_refused"
				end
				busy = true
				local thread = coroutine.create(control)
				local result: any = table.pack(coroutine.resume(thread, ...))
				busy = false
				if coroutine.status(thread) ~= "dead" or not result[1] then
					uncertain = true
					faulted = true
					stopping = false
					draining = false
					disarmAll()
					lastFailure = if result[1] then "unexpected_control_yield" else tostring(result[2])
					return false, "cleanup_unverified"
				end
				if result[2] == true and reentrancyObserved then
					faulted = true
					disarmAll()
					return false, "reentrant_control_refused"
				end
				return result[2], result[3]
			end
		else
			public[name] = fn
		end
	end
	return table.freeze(public)
end

return ServerOwnedBinding
