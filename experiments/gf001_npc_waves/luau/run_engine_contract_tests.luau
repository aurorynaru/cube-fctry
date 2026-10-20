--!strict
-- GF-001-Q3 contract probes. Roblox-shaped TABLE MOCKS, not an engine adapter.
-- Observed mock state is not evidence of actual engine teardown.

local passed = 0
local failures: { any } = {}
local function test(name: string, fn: () -> ())
	local ok, err = pcall(fn)
	if ok then
		passed += 1
	else
		table.insert(failures, { name = name, error = tostring(err) })
	end
end

local function expect(value: boolean, message: string)
	if not value then
		error(message, 0)
	end
end

-- These methods deliberately require a receiver and have void returns.
local function mockObject(): (any, any)
	local connection: any = { Connected = true, calls = 0, fail = false }
	function connection.Disconnect(self: any)
		expect(self == connection, "connection receiver")
		self.calls += 1
		if self.fail then
			error("disconnect injected failure")
		end
		self.Connected = false
	end
	local object: any = { Parent = "owned-root", Name = "display", destroyCalls = 0, failDestroy = false }
	function object.Destroy(self: any)
		expect(self == object, "instance receiver")
		self.destroyCalls += 1
		if self.failDestroy then
			error("destroy injected failure")
		end
		self.Parent = nil
	end
	return object, connection
end

-- This tiny decision probe models a PRIVATE server issuance ledger and a
-- separate observation/uncertainty report. It never constructs an Instance.
local function probe(): any
	local run = {}
	local issued: { [any]: any } = {}
	local current: any = nil
	local uncertain = false
	local busy = false
	local deaths = 0
	local p: any = {}

	function p:allocate(id: string, point: string): any
		expect(not busy and current == nil and not uncertain, "serial allocation")
		busy = true
		local object, connection = mockObject()
		local binding: any = {
			run = run,
			id = id,
			point = point,
			object = object,
			connection = connection,
			active = false,
		}
		issued[object] = binding -- registered immediately after allocation
		current = binding
		busy = false
		return binding
	end

	function p:register(binding: any, connect: any): boolean
		expect(not busy and binding == current, "serial registration")
		busy = true
		local ok, listener = pcall(connect, function()
			if
				binding == current
				and issued[binding.object] == binding
				and binding.run == run
				and binding.active
				and not busy
			then
				binding.active = false
				deaths += 1
			end
		end)
		if not ok or listener == nil then
			uncertain = true -- Connect may have installed an unreturned listener
			busy = false
			return false
		end
		binding.listener = listener
		binding.active = true
		busy = false
		return true
	end

	function p:cleanup(binding: any): boolean
		expect(not busy, "serial cleanup")
		busy = true
		binding.active = false
		if binding ~= current or issued[binding.object] ~= binding or binding.run ~= run then
			uncertain = true
			busy = false
			return false
		end
		local ok = pcall(function()
			binding.connection:Disconnect()
		end)
		if not ok or binding.connection.Connected ~= false then
			busy = false
			return false
		end
		ok = pcall(function()
			binding.object:Destroy()
		end)
		if not ok or binding.object.Parent ~= nil then
			-- Parent=nil is an observation, never a universal proof of Destroy.
			uncertain = true
			busy = false
			return false
		end
		issued[binding.object] = nil
		current = nil
		busy = false
		return not uncertain
	end

	function p:deathCount(): number
		return deaths
	end

	function p:canRestart(): boolean
		return not uncertain and current == nil and not busy
	end

	function p:uncertain(): boolean
		return uncertain
	end

	return p
end

test("void methods need receiver and checked state, not return true", function()
	local object, connection = mockObject()
	expect(not pcall(connection.Disconnect), "dot call lacks receiver")
	expect(not pcall(object.Destroy), "dot call lacks receiver")
	local ok, result = pcall(function()
		return connection:Disconnect()
	end)
	expect(ok and result == nil and connection.Connected == false, "void disconnect checked separately")
	ok, result = pcall(function()
		return object:Destroy()
	end)
	expect(ok and result == nil and object.Parent == nil, "void destroy has no success flag")
end)

test("signal Connect requires its receiver and returns a handle", function()
	local signal: any = {}
	local _, connection = mockObject()
	function signal.Connect(self: any, callback: any): any
		expect(self == signal and type(callback) == "function", "signal receiver and callback")
		return connection
	end
	expect(not pcall(signal.Connect, function() end), "unbound Connect refused")
	expect(signal:Connect(function() end) == connection, "colon call returns exact handle")
end)

test("private issuance and point association ignore mutable display name", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	b.object.Name = "forged-name"
	expect(b.id == "mob-0001" and b.point == "north", "private identity remains")
	expect(p:cleanup(b) and p:canRestart(), "known mock allocation cleaned")
end)

test("known partial allocation remains a cleanup obligation", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	expect(not p:canRestart(), "allocation precedes listener registration")
	expect(p:cleanup(b) and p:canRestart(), "failed preparation can clean known allocation")
end)

test("foreign object with matching name is never destroyed", function()
	local p = probe()
	local owned = p:allocate("mob-0001", "north")
	local foreign = mockObject()
	foreign.Name = owned.object.Name
	local impostor = { run = owned.run, id = owned.id, point = owned.point, object = foreign }
	expect(not p:cleanup(impostor), "issuance mismatch refused")
	expect(foreign.Parent ~= nil and foreign.destroyCalls == 0, "foreign object untouched")
	expect(p:uncertain() and not p:canRestart(), "unknown binding quarantined")
end)

test("callback during registration is suppressed and later callback once", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	local callback: any = nil
	expect(
		p:register(b, function(fn: any)
			callback = fn
			fn() -- deliberately reentrant mock; no core call permitted
			return b.connection
		end),
		"registered"
	)
	expect(p:deathCount() == 0, "inline callback was suppressed")
	callback()
	callback()
	expect(p:deathCount() == 1, "one accepted callback")
	expect(p:cleanup(b), "cleanup")
	callback()
	expect(p:deathCount() == 1, "stale callback inert")
end)

test("callback during destruction and deferred delivery are inert", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	local callback: any = nil
	expect(
		p:register(b, function(fn: any)
			callback = fn
			return b.connection
		end),
		"registered"
	)
	local destroy = b.object.Destroy
	b.object.Destroy = function(self: any)
		callback()
		return destroy(self)
	end
	expect(p:cleanup(b), "cleanup with inline callback")
	callback() -- simulates an already captured/deferred callback
	expect(p:deathCount() == 0, "no death during or after cleanup")
end)

test("ambiguous connect remains uncertain even after known object removal", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	expect(not p:register(b, function(_fn: any)
		error("may have registered before throwing")
	end), "connect ambiguity")
	expect(not p:cleanup(b) and b.object.Parent == nil, "local removal does not resolve unknown listener")
	expect(p:uncertain() and not p:canRestart(), "restart refused")
end)

test("failed disconnect retains resource, retry checks Connected", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	b.connection.fail = true
	expect(not p:cleanup(b) and b.object.Parent ~= nil, "no destroy after failed disconnect")
	expect(not p:canRestart(), "outstanding resource")
	b.connection.fail = false
	expect(p:cleanup(b) and b.connection.Connected == false and p:canRestart(), "checked retry")
end)

test("destroy exception stays uncertain even if mock parent becomes nil", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	b.object.Destroy = function(self: any)
		self.Parent = nil
		error("failure after side effect")
	end
	expect(not p:cleanup(b), "no cleanup acknowledgment from pcall or parent alone")
	expect(p:uncertain() and not p:canRestart(), "ambiguous destruction blocks restart")
end)

test("void destroy with no observed removal cannot acknowledge cleanup", function()
	local p = probe()
	local b = p:allocate("mob-0001", "north")
	b.object.Destroy = function(self: any)
		expect(self == b.object, "receiver")
		-- Silent no-op: pcall succeeds and the return is nil.
	end
	expect(not p:cleanup(b) and b.object.Parent ~= nil, "no false success")
	expect(p:uncertain() and not p:canRestart(), "unresolved obligation")
end)

for _, failure in ipairs(failures) do
	print(("GF-001-Q3 FAIL: %s: %s"):format(failure.name, failure.error))
end
print(("GF-001-Q3 mock probes: %d passed, %d failed"):format(passed, #failures))
if #failures > 0 then
	error("GF-001-Q3 mock contract probes failed", 0)
end
