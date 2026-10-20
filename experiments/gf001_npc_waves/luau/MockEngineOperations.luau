--!strict
-- GF-001-Q4 standalone Luau mock of the narrow engine-operations interface
-- consumed by ServerOwnedBinding.
--
-- Roblox-shaped TABLE MOCKS, not the Roblox engine: receiver-required
-- Connect/Disconnect/Die/Destroy with VOID returns for Disconnect/Destroy, a
-- `Connected` property as the only connection-specific observation, an
-- engine-private issuance ledger keyed by exact object reference (never by
-- mutable display names, attributes or forgeable fields), and immediate or
-- deferred death delivery. Deferred deliveries can additionally resume at
-- mock "resumption points" (any engine operation), modeling the documented
-- deferred-signal hazard that a handler may run during unrelated server work.
-- Mock-observed state is NOT evidence of actual Roblox engine teardown.

local MockEngineOperations = {}

function MockEngineOperations.new(): any
	local issued: { [any]: any } = {} -- exact model reference -> issuance receipt
	local issuedContainers: { [any]: any } = {}
	local handles: { [any]: any } = {}
	local destroyed: { [any]: boolean } = {} -- mock-private destruction ledger
	local created: { any } = {} -- chronological allocations, test inspection only
	local orphans: { any } = {} -- allocated, then thrown away by createMob
	local containers: { any } = {}
	local foreignCreated: { any } = {}
	local pending: { any } = {} -- deferred death deliveries
	local delivery = "immediate"
	local resumptionDelivery = false
	local resuming = false

	local controls = {
		createReturnsNil = false,
		createPartial = false,
		createThrowsAfterAllocation = false,
		createReturnsForeign = false,
		reuseFirstAllocation = false,
		createWithZeroHealth = false,
		humanoidMissingAtCreate = false,
		fireOnceOnNextConnect = false,
		connectThrowsAfterInstall = false,
		connectReturnsNil = false,
		disconnectThrows = false,
		destroyThrows = false,
		destroyThrowsAfterDetach = false,
		destroySilentNoOp = false,
		destroyOnlyUnparents = false,
		destroyContainerOnlyNoOp = false,
		observationThrows = false,
		observationYields = false,
		deathEligible = true,
		containerThrowsAfterAllocation = false,
		onModelCreated = nil :: any,
		onDestroy = nil :: any,
	}

	local mockRoot = {
		className = "Folder",
		Name = "MockRunHost",
		Parent = nil :: any,
		Attributes = {},
		children = {} :: { any },
	}

	local function maybeResume()
		-- Simulates deferred handlers resuming at a resumption point during
		-- other server work. Guarded against recursive resumption.
		if resuming or not resumptionDelivery or delivery ~= "deferred" or #pending == 0 then
			return
		end
		resuming = true
		local queued = pending
		pending = {}
		for _, entry in ipairs(queued) do
			entry.signal:Fire()
		end
		resuming = false
	end

	local function newSignal(): any
		local listeners: { any } = {}
		local signal: any = nil
		signal = {}
		function signal.Connect(self: any, callback: any): any
			if self ~= signal then
				error("Connect requires its receiver", 0)
			end
			if type(callback) ~= "function" then
				error("Died callback must be a function", 0)
			end
			if controls.connectReturnsNil then
				return nil -- this mock path genuinely installs no listener
			end
			local connection: any = nil
			connection = {
				Connected = true,
				Disconnect = function(receiver: any)
					if receiver ~= connection then
						error("Disconnect requires its receiver", 0)
					end
					if controls.disconnectThrows then
						error("disconnect injected failure", 0)
					end
					receiver.Connected = false
					for index, entry in ipairs(listeners) do
						if entry.connection == connection then
							table.remove(listeners, index)
							break
						end
					end
				end,
			}
			table.insert(listeners, { connection = connection, callback = callback })
			handles[connection] = signal
			if controls.fireOnceOnNextConnect then
				controls.fireOnceOnNextConnect = false
				local onDeath = callback :: () -> ()
				onDeath() -- immediate delivery during registration
			end
			if controls.connectThrowsAfterInstall then
				error("connect may have installed a listener before throwing", 0)
			end
			return connection
		end
		function signal.Fire(self: any)
			if self ~= signal then
				error("Fire requires its receiver", 0)
			end
			for _, entry in ipairs(table.clone(listeners)) do
				if entry.connection.Connected then
					entry.callback()
				end
			end
		end
		function signal._snapshot(self: any): { any }
			if self ~= signal then
				error("internal receiver required", 0)
			end
			local snapshot = {}
			for _, entry in ipairs(listeners) do
				table.insert(snapshot, entry.connection)
			end
			return snapshot
		end
		function signal._callbacks(self: any): { any }
			if self ~= signal then
				error("internal receiver required", 0)
			end
			local callbacks = {}
			for _, entry in ipairs(listeners) do
				table.insert(callbacks, entry.callback)
			end
			return callbacks
		end
		function signal._disconnectAll(self: any)
			if self ~= signal then
				error("internal receiver required", 0)
			end
			for _, entry in ipairs(listeners) do
				entry.connection.Connected = false
			end
			listeners = {}
		end
		return signal
	end

	local function newHumanoid(health: number): any
		local signal = newSignal()
		local humanoid: any = nil
		humanoid = {
			className = "Humanoid",
			Name = "Humanoid",
			Health = health,
			MaxHealth = health,
			Died = signal,
			Die = function(self: any)
				if self ~= humanoid then
					error("Die requires its receiver", 0)
				end
				self.Health = 0
				if delivery == "immediate" then
					signal:Fire()
				else
					table.insert(pending, { signal = signal })
				end
			end,
		}
		return humanoid
	end

	local function newDestroyable(className: string, name: string): any
		local instance: any = nil
		instance = {
			className = className,
			Name = name,
			Parent = nil :: any,
			Attributes = {},
			destroyCalls = 0, -- mock-only counter; the binding never reads it
			Destroy = function(self: any)
				if self ~= instance then
					error("Destroy requires its receiver", 0)
				end
				self.destroyCalls += 1
				if controls.onDestroy ~= nil then
					local onDestroy = controls.onDestroy :: (any) -> ()
					onDestroy(instance)
				end
				if controls.destroyContainerOnlyNoOp and className == "Folder" then
					return
				end
				if controls.destroyOnlyUnparents then
					self.Parent = nil -- explicitly NOT a destruction receipt
					return
				end
				if controls.destroySilentNoOp then
					return -- silent no-op: void return proves nothing either way
				end
				if controls.destroyThrows then
					error("destroy injected failure", 0)
				end
				if controls.destroyThrowsAfterDetach then
					self.Parent = nil
					error("destroy failed after detaching", 0)
				end
				local parent = self.Parent
				if parent ~= nil and type(parent.children) == "table" then
					for index, child in ipairs(parent.children) do
						if child == instance then
							table.remove(parent.children, index)
							break
						end
					end
				end
				self.Parent = nil
				destroyed[instance] = true
				if className == "Model" then
					local humanoid = instance.Humanoid
					if humanoid ~= nil and type(humanoid.Died) == "table" then
						humanoid.Died:_disconnectAll()
					end
				end
			end,
		}
		return instance
	end

	local function attach(parent: any, instance: any)
		instance.Parent = parent
		table.insert(parent.children, instance)
	end

	local function foreignModel(record: any): any
		local foreignContainer = newDestroyable("Folder", "ForeignContainer")
		foreignContainer.children = {}
		local humanoid = newHumanoid(record.maxHealth)
		local model = newDestroyable("Model", "GF001Mob")
		model.Humanoid = humanoid
		attach(foreignContainer, model)
		table.insert(foreignCreated, { model = model, humanoid = humanoid, container = foreignContainer })
		return model
	end

	local function createRunContainer(runToken: any): any
		maybeResume()
		local container = newDestroyable("Folder", "GF001RunContainer")
		container.children = {}
		attach(mockRoot, container)
		table.insert(containers, container)
		issuedContainers[container] = runToken
		if controls.containerThrowsAfterAllocation then
			error("createRunContainer threw after allocating", 0)
		end
		return container
	end

	local function createMob(record: any, point: any, container: any, runToken: any): (boolean, any, any)
		maybeResume()
		local spawnPointId = point.id
		if controls.createReturnsNil then
			return false, nil, nil
		end
		if controls.reuseFirstAllocation and #created > 0 then
			return true, created[1].model, created[1].humanoid
		end
		if controls.createReturnsForeign then
			local foreign = foreignModel(record)
			return true, foreign, foreign.Humanoid
		end
		local humanoid: any = nil
		if not controls.humanoidMissingAtCreate then
			local health = record.maxHealth
			if controls.createWithZeroHealth then
				health = 0
			end
			humanoid = newHumanoid(health)
		end
		local model = newDestroyable("Model", "GF001Mob")
		model.Humanoid = humanoid
		attach(container, model)
		table.insert(created, {
			model = model,
			humanoid = humanoid,
			recordId = record.id,
			mobId = record.mobId,
			spawnPointId = spawnPointId,
			point = point,
			allocation = record,
		})
		issued[model] = {
			runToken = runToken,
			recordId = record.id,
			mobId = record.mobId,
			spawnPointId = spawnPointId,
			humanoid = humanoid,
		}
		if controls.createThrowsAfterAllocation then
			table.insert(orphans, model)
			error("createMob threw after allocating", 0)
		end
		if controls.onModelCreated ~= nil then
			local onCreated = controls.onModelCreated :: (any, any) -> ()
			onCreated(model, humanoid)
		end
		return not controls.createPartial, model, humanoid
	end

	local function isDescendantOf(instance: any, ancestor: any): boolean
		local current = instance.Parent
		while current ~= nil do
			if current == ancestor then
				return true
			end
			current = current.Parent
		end
		return false
	end

	local ops = {
		-- Declared factory contract. `(false, nil)`-style allocation-free
		-- failure and nil listener returns are trusted ONLY through these
		-- explicit declarations; a future Roblox implementation must only set
		-- them if it can actually establish the invariant.
		contract = {
			failedCreateGuaranteesNoAllocation = true,
			connectNilGuaranteesNoListener = false,
		},
		createRunContainer = createRunContainer,
		createMob = createMob,
		ownsContainer = function(value: any, runToken: any): boolean
			return issuedContainers[value] == runToken and runToken ~= nil
		end,
		containerEmpty = function(value: any): boolean
			return #value.children == 0
		end,
		connectionIssued = function(handle: any, humanoid: any): boolean
			return handles[handle] == humanoid.Died
		end,
		teardownObserved = function(model: any, humanoid: any, runContainer: any): boolean
			-- Mock-private destruction AND scoped census, not Parent=nil alone.
			if controls.observationThrows then
				error("teardown observation unavailable", 0)
			end
			if controls.observationYields then
				coroutine.yield("unexpected observation yield")
			end
			if destroyed[model] ~= true or model.Parent ~= nil then
				return false
			end
			for _, child in ipairs(runContainer.children) do
				if child == model then
					return false
				end
			end
			if humanoid ~= nil and #humanoid.Died:_snapshot() ~= 0 then
				return false
			end
			return true
		end,
		containerTeardownObserved = function(value: any, runToken: any): boolean
			return issuedContainers[value] == runToken
				and destroyed[value] == true
				and value.Parent == nil
				and #value.children == 0
		end,
		describeIssue = function(model: any): any
			maybeResume()
			local receipt = issued[model]
			if receipt == nil then
				return nil
			end
			return {
				runToken = receipt.runToken,
				recordId = receipt.recordId,
				mobId = receipt.mobId,
				spawnPointId = receipt.spawnPointId,
				humanoid = receipt.humanoid,
			}
		end,
		isModel = function(value: any): boolean
			return type(value) == "table" and value.className == "Model"
		end,
		isHumanoid = function(value: any): boolean
			return type(value) == "table" and value.className == "Humanoid"
		end,
		humanoidOf = function(model: any): any
			maybeResume()
			return model.Humanoid
		end,
		humanoidDead = function(humanoid: any): boolean
			return controls.deathEligible and humanoid.Health <= 0
		end,
		healthOf = function(humanoid: any): number
			return humanoid.Health
		end,
		connectDeath = function(humanoid: any, callback: any): any
			maybeResume()
			return humanoid.Died:Connect(callback)
		end,
		disconnect = function(connection: any)
			maybeResume()
			connection:Disconnect() -- void: returns no success boolean
		end,
		isConnected = function(connection: any): boolean
			maybeResume()
			return connection.Connected
		end,
		destroy = function(instance: any)
			maybeResume()
			instance:Destroy() -- void: returns no success boolean
		end,
		parentOf = function(instance: any): any
			maybeResume()
			return instance.Parent
		end,
		isDescendantOf = isDescendantOf,
	}

	local mock = {
		ops = ops,
		controls = controls,
		created = created,
		orphans = orphans,
		containers = containers,
		foreignCreated = foreignCreated,
		root = mockRoot,
		setDelivery = function(mode: string)
			delivery = mode
		end,
		setResumptionDelivery = function(enabled: boolean)
			resumptionDelivery = enabled
		end,
		setContract = function(key: string, value: boolean)
			ops.contract[key] = value
		end,
		pump = function(count: number?)
			local remaining = count or #pending
			while remaining > 0 and #pending > 0 do
				local entry = table.remove(pending, 1)
				entry.signal:Fire()
				remaining -= 1
			end
		end,
		pendingCount = function(): number
			return #pending
		end,
		connect = function(humanoid: any, callback: any): any
			return humanoid.Died:Connect(callback)
		end,
		kill = function(humanoid: any)
			humanoid:Die()
		end,
		fireDeathSignal = function(humanoid: any)
			humanoid.Died:Fire() -- forged delivery: no health change
		end,
		replaceHumanoidOf = function(model: any)
			local maxHealth = 100
			if model.Humanoid ~= nil then
				maxHealth = model.Humanoid.MaxHealth
			end
			model.Humanoid = newHumanoid(maxHealth)
		end,
		rename = function(instance: any, name: string)
			instance.Name = name
		end,
		isDestroyed = function(instance: any): boolean
			return destroyed[instance] == true
		end,
		connectionsOf = function(humanoid: any): { any }
			return humanoid.Died:_snapshot()
		end,
		callbacksOf = function(humanoid: any): { any }
			return humanoid.Died:_callbacks()
		end,
		childrenOf = function(container: any): { any }
			return table.clone(container.children)
		end,
	}

	return mock
end

return MockEngineOperations
