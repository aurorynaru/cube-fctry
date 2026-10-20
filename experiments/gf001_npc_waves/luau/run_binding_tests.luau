--!strict
-- GF-001-Q4: actual standalone Luau integration suite. Composes the real
-- unchanged GF-001 core (WaveRuntime/Mobs/Rewards/SpawnPoints) with the
-- reusable ServerOwnedBinding module through the mock engine-operations
-- interface. All engine-like objects are offline mocks; mock observations are
-- NOT evidence of actual Roblox engine behavior.

local Clock = require("./Clock")
local Config = require("./Config")
local ExampleConfig = require("./ExampleConfig")
local Mobs = require("./Mobs")
local MockEngineOperations = require("./MockEngineOperations")
local Rng = require("./Rng")
local ServerOwnedBinding = require("./ServerOwnedBinding")
local SpawnPoints = require("./SpawnPoints")
local WaveRuntime = require("./WaveRuntime")

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

local function expect(condition: boolean, message: string)
	if not condition then
		error(message, 0)
	end
end

local function count(events: { any }, kind: string): number
	local n = 0
	for _, event in ipairs(events) do
		if event.type == kind then
			n += 1
		end
	end
	return n
end

local function totalPoints(events: { any }): number
	local points = 0
	for _, event in ipairs(events) do
		if event.type == "reward_intent" then
			points += event.points
		end
	end
	return points
end

local function setup(mobCount: number?, interval: number?, rawConfig: any?): (any, any, any)
	local ok, config = Config.validate(rawConfig or {
		maxActiveMobs = mobCount or 4,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = {
			{ id = "synthetic-point", capacity = mobCount or 4, position = { x = 0, y = 0, z = 0 } },
		},
		waves = { { mobId = "dummy", count = mobCount or 1, spawnInterval = interval or 0 } },
	})
	expect(ok, "fixture config validates")
	local mock = MockEngineOperations.new()
	local clock = Clock.stepping(0)
	local session = ServerOwnedBinding.new(config, {
		clock = clock,
		rng = Rng.new(5),
		waveRuntime = WaveRuntime,
		mobs = Mobs,
		selectSpawn = SpawnPoints.select,
		engineOps = mock.ops,
	})
	return session, mock, clock
end

local function eventsOf(session: any): { any }
	return session.eventLog()
end

local function spawnWave(session: any)
	expect(session.start(), "start")
	expect(session.tick(), "spawn tick")
end

test("multiple simultaneous mobs live and die independently", function()
	local session, mock = setup(3)
	spawnWave(session)
	expect(#mock.created == 3 and session.status().active == 3, "three live mobs")
	local first, second, third = mock.created[1], mock.created[2], mock.created[3]
	expect(first.model ~= second.model and second.model ~= third.model, "distinct exact model references")
	expect(
		first.humanoid ~= second.humanoid and second.humanoid ~= third.humanoid,
		"distinct exact humanoid references"
	)
	mock.kill(second.humanoid)
	expect(session.tick(), "tick forwards queued death")
	expect(session.status().active == 2, "second dead, not yet torn down")
	expect(session.tick(), "tick cleans the dead record")
	expect(mock.isDestroyed(second.model), "dead record torn down")
	mock.kill(first.humanoid)
	mock.kill(third.humanoid)
	expect(session.tick(), "tick forwards remaining deaths")
	expect(session.tick() and session.status().state == "completed", "completion after owned deaths")
	local events = eventsOf(session)
	expect(count(events, "mob_spawned") == 3, "three spawns acknowledged")
	expect(count(events, "mob_died") == 3, "three server deaths")
	expect(count(events, "reward_intent") == 3 and totalPoints(events) == 15, "one intent per mob")
	for _, entry in ipairs(mock.created) do
		expect(mock.isDestroyed(entry.model) and entry.model.destroyCalls == 1, "each model destroyed once")
	end
	expect(mock.isDestroyed(mock.containers[1]), "run container torn down")
	expect(session.report().restartAllowed, "clean completion allows restart")
end)

test("three-wave example completes and restarts with a fresh identity", function()
	local session, mock, clock = setup(nil, nil, ExampleConfig)
	expect(session.start(), "start example")
	local oldCallback: any = nil
	local steps = 0
	while session.status().state == "running" and steps < 200 do
		expect(session.tick(), "example tick")
		for _, entry in ipairs(mock.created) do
			if not mock.isDestroyed(entry.model) and entry.humanoid ~= nil then
				if entry.humanoid.Health > 0 then
					if oldCallback == nil then
						oldCallback = mock.callbacksOf(entry.humanoid)[1]
					end
					mock.kill(entry.humanoid)
				end
			end
		end
		clock.advance(0.25)
		steps += 1
	end
	expect(steps < 200 and session.status().state == "completed", "three waves finish")
	local events = eventsOf(session)
	expect(#mock.created == 8 and count(events, "wave_completed") == 3, "existing scheduling reused")
	expect(count(events, "reward_intent") == 8 and totalPoints(events) == 96, "eight intents, 96 points")
	expect(count(events, "all_waves_completed") == 1, "one completion")
	for _, entry in ipairs(mock.created) do
		expect(mock.isDestroyed(entry.model) and entry.model.destroyCalls == 1, "all models cleaned once")
	end
	expect(mock.isDestroyed(mock.containers[1]) and #mock.containers == 1, "container torn down")
	local started, reason = session.start()
	expect(started and reason == nil, "restart after completion")
	expect(session.status().runSerial == 2, "fresh run serial")
	expect(session.tick(), "new run ticks")
	oldCallback()
	expect(session.status().active == #mock.created - 8, "old callback inert after restart")
end)

test("exact run, mob and spawn-point identity through private issuance", function()
	local session, mock = setup(3)
	spawnWave(session)
	for index, entry in ipairs(mock.created) do
		local receipt = mock.ops.describeIssue(entry.model)
		expect(receipt ~= nil, "issued model has a receipt")
		expect(receipt.recordId == ("mob-%04d"):format(index), "exact record identity")
		expect(receipt.mobId == "dummy", "exact mob definition identity")
		expect(receipt.spawnPointId == "synthetic-point", "exact spawn-point association")
		expect(receipt.humanoid == entry.humanoid, "exact humanoid association")
		expect(mock.ops.isModel(entry.model) and mock.ops.isHumanoid(entry.humanoid), "engine shapes")
	end
	mock.kill(mock.created[2].humanoid)
	expect(session.tick(), "death forwarded")
	expect(session.tick(), "dead record cleaned")
	expect(mock.isDestroyed(mock.created[2].model), "only the dying record is torn down")
	expect(
		not mock.isDestroyed(mock.created[1].model) and not mock.isDestroyed(mock.created[3].model),
		"others untouched"
	)
	expect(session.stop("interrupted"), "clean stop of the remaining run")
	expect(session.start(), "restart after the clean stop")
	expect(session.status().runSerial == 2, "run serial advanced")
end)

test("ownership ignores mutable names, attributes and forged fields", function()
	local session, mock = setup()
	spawnWave(session)
	local entry = mock.created[1]
	mock.rename(entry.model, "forged-display-name")
	entry.model.OwnerToken = "forged-token"
	entry.model.MobRecordId = "forged-record"
	entry.model.Destroyed = true -- mock-only field the binding must never read
	entry.model.Attributes.GF001Owner = "forged"
	mock.kill(entry.humanoid)
	expect(session.tick(), "death forwarded despite forged metadata")
	expect(session.tick(), "dead record cleaned despite forged metadata")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 1 and count(events, "reward_intent") == 1, "identity held")
	expect(session.status().state == "completed", "completed")
	expect(mock.isDestroyed(entry.model), "verified teardown despite forged fields")
	expect(session.report().restartAllowed, "restart allowed")
end)

test("preexisting handle is never confused with the binding's returned handle", function()
	local session, mock = setup()
	local preCalls = 0
	local preHandle: any = nil
	mock.controls.onModelCreated = function(_model: any, humanoid: any)
		preHandle = mock.connect(humanoid, function()
			preCalls += 1
		end)
	end
	spawnWave(session)
	local humanoid = mock.created[1].humanoid
	local handles = mock.connectionsOf(humanoid)
	expect(#handles == 2 and handles[1] ~= handles[2], "preexisting and binding handles distinct")
	expect(handles[1] == preHandle, "preexisting handle registered first")
	mock.kill(humanoid)
	expect(session.tick(), "death forwarded with both listeners live")
	expect(preCalls == 1, "preexisting listener delivered once")
	mock.controls.destroyThrows = true
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_failed", "destroy failure withholds completion")
	local snapshot = mock.connectionsOf(humanoid)
	expect(
		#snapshot == 1 and snapshot[1] == preHandle and snapshot[1].Connected == true,
		"only the binding's own listener was disconnected; the preexisting handle is untouched"
	)
	expect(not mock.isDestroyed(mock.created[1].model), "model retained")
	local restarted, restartReason = session.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart refused while retained")
	mock.controls.destroyThrows = false
	expect(session.stop("retry"), "guarded retry completes teardown")
	expect(mock.isDestroyed(mock.created[1].model), "model destroyed on retry")
	expect(session.report().restartAllowed, "restart allowed after retry")
end)

test("void Disconnect and Destroy acknowledge only via observations", function()
	local session, mock = setup()
	spawnWave(session)
	local entry = mock.created[1]
	local coHandle = mock.connect(entry.humanoid, function() end)
	expect(not pcall(coHandle.Disconnect), "dot Disconnect lacks the receiver")
	expect(not pcall(entry.model.Destroy), "dot Destroy lacks the receiver")
	local voidDisconnect = mock.ops.disconnect(coHandle)
	expect(voidDisconnect == nil and coHandle.Connected == false, "void disconnect observed separately")
	local standalone = MockEngineOperations.new()
	local runToken = {}
	local runContainer = standalone.ops.createRunContainer(runToken)
	local allocated, model = standalone.ops.createMob(
		{ id = "probe", mobId = "dummy", maxHealth = 30 },
		{ id = "point" },
		runContainer,
		runToken
	)
	expect(allocated, "extra mock resource allocated")
	local voidDestroy = standalone.ops.destroy(model)
	expect(voidDestroy == nil, "void destroy returns no success boolean")
	expect(standalone.isDestroyed(model), "destruction observed through the mock ledger")
	expect(session.stop("interrupted"), "stop acknowledges through observations")
	expect(session.report().restartAllowed, "no boolean was required from the engine")
end)

test("immediate death during setup is conservatively refused", function()
	local session, mock = setup()
	mock.controls.fireOnceOnNextConnect = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "spawn with an inline death is refused")
	local events = eventsOf(session)
	expect(count(events, "mob_spawned") == 0, "no spawn acknowledgment")
	expect(count(events, "mob_died") == 0 and count(events, "reward_intent") == 0, "no authorized death")
	local entry = mock.created[1]
	expect(mock.isDestroyed(entry.model) and entry.model.destroyCalls == 1, "refused model torn down")
	expect(#mock.connectionsOf(entry.humanoid) == 0, "handle disconnected before teardown")
	expect(session.report().earlyDeathsRefused == 1, "refusal recorded")
	expect(session.report().restartAllowed, "fully cleaned refusal allows restart")
	expect(session.start() and session.tick(), "fresh run works")
	expect(session.status().active == 1, "new mob alive")
end)

test("deferred death after stop stays inert", function()
	local session, mock = setup()
	mock.setDelivery("deferred")
	spawnWave(session)
	local humanoid = mock.created[1].humanoid
	mock.kill(humanoid)
	expect(mock.pendingCount() == 1, "death deferred, not yet delivered")
	expect(session.stop("interrupted"), "clean stop before delivery")
	mock.pump()
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 0 and count(events, "reward_intent") == 0, "post-stop death inert")
	expect(mock.pendingCount() == 0, "delivery consumed")
	expect(session.report().restartAllowed, "restart allowed")
	expect(session.start() and session.tick(), "fresh run works")
end)

test("death callback during cleanup is refused", function()
	local session, mock = setup()
	mock.setDelivery("deferred")
	mock.setResumptionDelivery(true)
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(mock.pendingCount() == 1, "death pending")
	local ok, reason = session.stop("interrupted")
	expect(ok and reason == nil, "stop completes")
	local events = eventsOf(session)
	expect(
		count(events, "mob_died") == 0 and count(events, "reward_intent") == 0,
		"no death authorized during teardown"
	)
	expect(mock.isDestroyed(mock.created[1].model), "scoped teardown observed")
	expect(session.report().teardownEventsRefused == 1, "teardown refusal recorded")
	expect(session.report().restartAllowed, "restart allowed")
end)

test("duplicate death, once-only intent and forged signal refused", function()
	local session, mock = setup(2)
	spawnWave(session)
	local first, second = mock.created[1], mock.created[2]
	mock.kill(first.humanoid)
	mock.kill(first.humanoid) -- duplicate delivery
	local staleCallback = mock.callbacksOf(first.humanoid)[1]
	mock.fireDeathSignal(second.humanoid) -- forged: no health change
	expect(session.drain(), "serialized drain")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 1 and count(events, "reward_intent") == 1, "one accepted death only")
	expect(session.status().active == 1, "forged death did not kill the second mob")
	expect(session.report().forgedEventsRefused == 1, "forged signal recorded")
	expect(session.tick(), "tick cleans the dead record")
	staleCallback()
	expect(count(eventsOf(session), "reward_intent") == 1, "stale callback cannot repeat the intent")
	expect(session.stop("interrupted"), "clean stop")
	expect(count(eventsOf(session), "reward_intent") == 1, "still one intent")
end)

test("foreign allocation and humanoid replacement are quarantined", function()
	local session, mock = setup()
	mock.controls.createReturnsForeign = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "foreign allocation faults the run")
	expect(#mock.foreignCreated == 1, "foreign object allocated by the engine")
	local foreign = mock.foreignCreated[1]
	expect(not mock.isDestroyed(foreign.model), "foreign resource never destroyed")
	expect(foreign.model.Parent == foreign.container, "foreign parent intact")
	local restarted, restartReason = session.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart prohibited")

	local session2, mock2 = setup()
	spawnWave(session2)
	mock2.replaceHumanoidOf(mock2.created[1].model)
	mock2.kill(mock2.created[1].model.Humanoid)
	local ok2, reason2 = session2.stop("interrupted")
	expect(not ok2 and reason2 == "cleanup_unverified", "replaced humanoid quarantined")
	expect(not mock2.isDestroyed(mock2.created[1].model), "quarantined model not destroyed")
	local events2 = eventsOf(session2)
	expect(count(events2, "mob_died") == 0, "replacement death never forwarded")
	expect(not session2.start(), "restart prohibited after quarantine")

	local session3, mock3 = setup(2)
	mock3.controls.reuseFirstAllocation = true
	expect(session3.start(), "start duplicate-reference case")
	local ok3, reason3 = session3.tick()
	expect(not ok3 and reason3 == "cleanup_unverified", "same object cannot bind two records")
	expect(#mock3.created == 1 and count(session3.eventLog(), "mob_spawned") == 1, "second spawn not acknowledged")
	expect(
		not session3.recordsSnapshot()[2].cleaned and not session3.start(),
		"duplicate reference obligation retained"
	)
end)

test("partial allocation before listener registration stays cleanable", function()
	local session, mock = setup()
	mock.controls.humanoidMissingAtCreate = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "incomplete spawn refused")
	local events = eventsOf(session)
	expect(count(events, "mob_spawned") == 0, "no spawn acknowledgment")
	expect(#mock.created == 1 and mock.isDestroyed(mock.created[1].model), "known partial allocation cleaned")
	expect(mock.created[1].model.destroyCalls == 1, "destroyed exactly once")
	expect(session.report().restartAllowed, "restart allowed after clean stop")
	mock.controls.humanoidMissingAtCreate = false
	expect(session.start() and session.tick(), "fresh run works")

	local session2, mock2 = setup()
	mock2.setContract("connectNilGuaranteesNoListener", true)
	mock2.controls.connectReturnsNil = true
	expect(session2.start(), "start")
	local ok2, reason2 = session2.tick()
	expect(not ok2 and reason2 == "adapter_failure", "guaranteed nil handle refuses spawn")
	expect(mock2.isDestroyed(mock2.created[1].model), "no-listener model cleaned")
	expect(session2.report().restartAllowed, "restart allowed")
end)

test("connect failure with unknown listener state is never promoted", function()
	local session, mock = setup()
	mock.controls.connectThrowsAfterInstall = true
	mock.controls.destroyThrows = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "unknown listener state faults the run")
	local events = eventsOf(session)
	expect(count(events, "mob_spawned") == 0 and count(events, "mob_died") == 0, "no success or death")
	local entry = mock.created[1]
	expect(not mock.isDestroyed(entry.model), "conservative teardown retains the model")
	expect(#mock.connectionsOf(entry.humanoid) == 1, "an unaccounted listener remains installed")
	mock.fireDeathSignal(entry.humanoid)
	expect(count(eventsOf(session), "mob_died") == 0, "unknown listener cannot authorize a death")
	local restarted, restartReason = session.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart refused while retained")
	mock.controls.destroyThrows = false
	local stopped, stopReason = session.stop("retry")
	expect(not stopped and stopReason == "cleanup_unverified", "uncertainty never resolves")
	expect(mock.isDestroyed(entry.model) and entry.model.destroyCalls >= 1, "known model torn down on retry")
	local report = session.report()
	expect(#report.retainedObligations == 1, "obligation retained")
	local restarted2, restartReason2 = session.start()
	expect(not restarted2 and restartReason2 == "cleanup_unverified", "restart prohibited")
end)

test("disconnect failure retains the handle for a guarded retry", function()
	local session, mock = setup()
	spawnWave(session)
	local entry = mock.created[1]
	mock.controls.disconnectThrows = true
	local ok, reason = session.stop("interrupted")
	expect(not ok and reason == "cleanup_failed", "disconnect failure withholds cleanup")
	expect(not mock.isDestroyed(entry.model), "no destroy before a verified disconnect")
	expect(entry.model.Parent ~= nil, "model still in the run container")
	mock.kill(entry.humanoid)
	expect(session.status().active == 1, "death during a failed teardown is inert")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 0 and count(events, "reward_intent") == 0, "no death accepted")
	local restarted, restartReason = session.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart refused while retained")
	mock.controls.disconnectThrows = false
	local ok2, reason2 = session.stop("retry")
	expect(ok2 and reason2 == nil, "guarded retry completes")
	expect(mock.isDestroyed(entry.model) and entry.model.destroyCalls == 1, "retry destroys exactly once")
	expect(session.report().activeBindings == 0, "no outstanding bindings")
	expect(session.report().restartAllowed, "restart allowed after retry")
end)

test("destroy failure, silent no-op and ambiguous side effects", function()
	local session, mock = setup()
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(session.tick(), "death forwarded")
	mock.controls.destroyThrows = true
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_failed", "failed destroy withholds completion")
	local events = eventsOf(session)
	expect(count(events, "all_waves_completed") == 0, "no fabricated completion")
	expect(not mock.isDestroyed(mock.created[1].model), "model retained")
	mock.controls.destroyThrows = false
	expect(session.stop("retry"), "retry completes")
	expect(mock.isDestroyed(mock.created[1].model), "destroyed on retry")
	expect(count(eventsOf(session), "reward_intent") == 1, "intent never repeated")

	local session2, mock2 = setup()
	spawnWave(session2)
	mock2.kill(mock2.created[1].humanoid)
	expect(session2.tick(), "death forwarded")
	mock2.controls.destroySilentNoOp = true
	local ok2, reason2 = session2.tick()
	expect(not ok2 and reason2 == "cleanup_failed", "void no-op never acknowledges cleanup")
	expect(not mock2.isDestroyed(mock2.created[1].model), "silent no-op destroyed nothing")
	expect(mock2.created[1].model.destroyCalls == 1, "failed teardown was not automatically retried")
	expect(not session2.start(), "restart refused without observation")
	mock2.controls.destroySilentNoOp = false
	expect(session2.stop("retry"), "retry completes")
	expect(mock2.isDestroyed(mock2.created[1].model), "destroyed on retry")

	local session3, mock3 = setup()
	spawnWave(session3)
	mock3.kill(mock3.created[1].humanoid)
	expect(session3.tick(), "death forwarded")
	mock3.controls.destroyThrowsAfterDetach = true
	local ok3, reason3 = session3.tick()
	expect(not ok3 and reason3 == "cleanup_unverified", "ambiguous destroy withholds cleanup")
	local model3 = mock3.created[1].model
	expect(model3.Parent == nil, "the throw detached the model")
	expect(not mock3.isDestroyed(model3), "detached is not destroyed")
	local ok4, reason4 = session3.stop("retry")
	expect(not ok4 and reason4 == "cleanup_unverified", "ambiguous state never resolves")
	local restarted, restartReason = session3.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart prohibited")
end)

test("failed spawn withholds acknowledgment; contract decides nil semantics", function()
	local session, mock = setup()
	mock.controls.createReturnsNil = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "allocation-free failure refused")
	local events = eventsOf(session)
	expect(count(events, "mob_spawned") == 0, "no spawn acknowledgment")
	expect(#mock.created == 0, "no allocation made")
	expect(session.status().totalSpawned == 0, "no successful accounting")
	mock.controls.createReturnsNil = false
	expect(session.start() and session.tick(), "restart allowed: nothing outstanding")

	local session2, mock2 = setup()
	mock2.setContract("failedCreateGuaranteesNoAllocation", false)
	mock2.controls.createReturnsNil = true
	expect(session2.start(), "start")
	local ok2, reason2 = session2.tick()
	expect(not ok2 and reason2 == "cleanup_unverified", "nil without guarantee is uncertain")
	local restarted, restartReason = session2.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart prohibited")
end)

test("container allocation failure refuses start", function()
	local session, mock = setup()
	mock.controls.containerThrowsAfterAllocation = true
	local ok, reason = session.start()
	expect(not ok and reason == "cleanup_unverified", "unknown container allocation refuses start")
	expect(#mock.containers == 1, "an orphaned container exists")
	expect(not mock.isDestroyed(mock.containers[1]), "orphan never destroyed")
	local ok2, reason2 = session.start()
	expect(not ok2 and reason2 == "cleanup_unverified", "restart still prohibited")
end)

test("queued events after an interrupted run are never accepted", function()
	local session, mock = setup(2)
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(session.report().pendingDeaths == 1, "one candidate queued")
	expect(session.stop("interrupted"), "interrupted before drain")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 0 and count(events, "reward_intent") == 0, "queued death never accepted")
	expect(session.drain(), "drain after stop is inert")
	expect(count(eventsOf(session), "mob_died") == 0, "no replay after stop")
	expect(session.start() and session.tick(), "restart works")
	expect(#mock.created == 4, "two more mobs in the fresh run")
	mock.kill(mock.created[4].humanoid)
	expect(session.tick(), "new-run death forwarded")
	local finalEvents = eventsOf(session)
	expect(count(finalEvents, "mob_died") == 1 and count(finalEvents, "reward_intent") == 1, "only the new run's death")
end)

test("nil connection without a guarantee leaves a permanent obligation", function()
	local session, mock = setup()
	mock.controls.connectReturnsNil = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "nil handle without guarantee faults the run")
	local entry = mock.created[1]
	expect(mock.isDestroyed(entry.model), "known model torn down")
	local stopped, stopReason = session.stop("retry")
	expect(not stopped and stopReason == "cleanup_unverified", "uncertain listener never resolves")
	local report = session.report()
	expect(
		#report.retainedObligations == 1 and report.retainedObligations[1].reason == "unknown_listener",
		"obligation"
	)
	local restarted, restartReason = session.start()
	expect(not restarted and restartReason == "cleanup_unverified", "restart refused with remaining obligation")
end)

test("clean restart with a fresh token leaves old callbacks inert", function()
	local session, mock = setup()
	spawnWave(session)
	local oldIssue = mock.ops.describeIssue(mock.created[1].model)
	local oldCallback = mock.callbacksOf(mock.created[1].humanoid)[1]
	mock.kill(mock.created[1].humanoid)
	expect(session.tick(), "death forwarded")
	expect(session.tick(), "dead record cleaned")
	expect(session.status().state == "completed", "completed")
	expect(session.start(), "clean restart")
	expect(session.status().runSerial == 2, "fresh run identity")
	expect(session.tick(), "new run spawns")
	local freshIssue = mock.ops.describeIssue(mock.created[2].model)
	expect(
		oldIssue.runToken ~= freshIssue.runToken and oldIssue.recordId ~= freshIssue.recordId,
		"exact fresh token and monotonic mob identity"
	)
	oldCallback()
	expect(session.status().active == 1, "old callback inert in the new run")
	mock.kill(mock.created[2].humanoid)
	expect(session.tick(), "new death forwarded")
	expect(session.tick(), "new dead record cleaned")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 2 and count(events, "reward_intent") == 2, "one intent per run")
	expect(session.report().staleEventsRefused >= 1, "stale event counted")
end)

test("queue overflow faults the run conservatively", function()
	local session, mock = setup(9)
	spawnWave(session)
	expect(#mock.created == 9, "nine live mobs")
	for _, entry in ipairs(mock.created) do
		mock.kill(entry.humanoid)
	end
	local ok, reason = session.tick()
	expect(not ok and reason == "death_queue_overflow", "overflow is never success")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 0 and count(events, "reward_intent") == 0, "no death accepted")
	expect(session.status().state == "stopped", "run stopped")
	for _, entry in ipairs(mock.created) do
		expect(mock.isDestroyed(entry.model), "all known resources torn down")
	end
	expect(session.report().restartAllowed, "clean teardown allows a fresh run")
	expect(session.start() and session.tick(), "fresh run works")
end)

test("reentrancy and nested drains are refused", function()
	local session, mock = setup(2)
	mock.setDelivery("deferred")
	mock.setResumptionDelivery(true)
	local nestedReason: any = nil
	spawnWave(session)
	local second = mock.created[2].humanoid
	mock.connect(second, function()
		local ok, reason = session.drain()
		expect(not ok, "nested drain did not succeed")
		nestedReason = reason
	end)
	mock.kill(mock.created[1].humanoid)
	mock.kill(second)
	mock.pump(1) -- delivers only the first death
	expect(session.report().pendingDeaths == 1, "one candidate queued")
	local ok, reason = session.drain()
	expect(not ok and reason == "reentrant_death_event", "reentrancy refused")
	expect(nestedReason == "reentrant_drain_refused", "nested drain refused")
	local events = eventsOf(session)
	expect(count(events, "mob_died") == 1 and count(events, "reward_intent") == 1, "first death accepted once")
	expect(session.status().state == "stopped", "run stopped conservatively")
	expect(session.report().reentrancyObserved, "reentrancy recorded")
	expect(mock.pendingCount() == 0, "no pending replay")
end)

test("forged client reward claim rejected without payout", function()
	local session, mock = setup()
	spawnWave(session)
	local entry = mock.created[1]
	local claim = session.clientRewardClaim("forged-player", { mob = entry.recordId, points = 999999 })
	expect(claim == nil, "no client grant")
	local events = eventsOf(session)
	expect(count(events, "client_reward_rejected") == 1 and count(events, "reward_intent") == 0, "no client intent")
	mock.kill(entry.humanoid)
	expect(session.tick(), "trusted death forwarded")
	local finalEvents = eventsOf(session)
	expect(count(finalEvents, "reward_intent") == 1, "server intent only")
	expect(finalEvents[#finalEvents].points == 5, "server-config points, no currency")
end)

test("configuration and observation snapshots cannot mutate private core state", function()
	local raw = {
		maxActiveMobs = 1,
		interWaveDelay = 0,
		mobs = { dummy = { displayName = "Dummy", maxHealth = 30, reward = { points = 5 } } },
		spawnPoints = { { id = "private", capacity = 1, position = { x = 2, y = 3, z = 4 } } },
		waves = { { mobId = "dummy", count = 1, spawnInterval = 0 } },
	}
	local session, mock = setup(nil, nil, raw)
	raw.mobs.dummy.reward.points = 99999
	raw.spawnPoints[1].position.x = 99999
	spawnWave(session)
	local snapshot = session.recordsSnapshot()
	expect(snapshot[1].state == "alive" and not snapshot[1].cleaned, "actual record projection")
	snapshot[1].state = "dead"
	snapshot[1].rewarded = true
	expect(session.recordsSnapshot()[1].state == "alive", "record snapshot is detached")
	local log = session.eventLog()
	log[1].type = "forged"
	expect(session.eventLog()[1].type == "wave_started", "events are detached")
	expect(mock.created[1].point.position.x == 2, "private point position unaffected")
	expect(
		table.isfrozen(mock.created[1].point.position) and table.isfrozen(mock.created[1].allocation),
		"immutable descriptors"
	)
	expect(not pcall(function()
		mock.created[1].allocation.id = "forged"
	end), "ops cannot mutate the core through descriptor")
	expect(session.killMob == nil and session.damageMob == nil and session.records == nil, "no mutable core endpoints")
	mock.kill(mock.created[1].humanoid)
	expect(session.drain(), "death accepted")
	expect(totalPoints(session.eventLog()) == 5, "private original reward definition")
end)

test("thrown allocation retains unknown resources and permanently refuses restart", function()
	local session, mock = setup()
	mock.controls.createThrowsAfterAllocation = true
	expect(session.start(), "start")
	local ok = session.tick()
	expect(not ok and session.report().uncertain, "throw is unknown allocation")
	expect(#mock.orphans == 1 and not mock.isDestroyed(mock.orphans[1]), "unreturned object not guessed or deleted")
	expect(mock.orphans[1].Parent == mock.containers[1], "orphan retained in run scope")
	expect(not session.recordsSnapshot()[1].rewarded, "failed spawn cannot reward")
	expect(not session.recordsSnapshot()[1].cleaned, "unknown allocation cleanup not acknowledged")
	expect(count(session.eventLog(), "mob_spawned") == 0, "no spawn acknowledgment")
	expect(not session.start() and not session.stop("retry"), "container removal cannot resolve unknown allocation")
end)

test("false allocation with returned resources is a known partial, never a spawn", function()
	local session, mock = setup()
	mock.controls.createPartial = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "partial refused")
	local record = session.recordsSnapshot()[1]
	expect(
		record.cleaned == true and record.state == "despawned" and not record.rewarded,
		"actual partial record cleaned"
	)
	expect(count(session.eventLog(), "mob_spawned") == 0, "acknowledgment withheld")
	expect(
		mock.isDestroyed(mock.created[1].model) and #mock.connectionsOf(mock.created[1].humanoid) == 0,
		"partial resources cleaned before listener"
	)
	expect(session.report().restartAllowed, "known cleanup permits restart")
end)

test("callback while another mob is allocated waits until the spawn tick returns", function()
	local session, mock, clock = setup(2, 1)
	spawnWave(session)
	mock.controls.onModelCreated = function()
		mock.kill(mock.created[1].humanoid)
		expect(session.recordsSnapshot()[1].state == "alive", "callback did not enter killMob mid-spawn")
		expect(count(session.eventLog(), "mob_died") == 0, "no inline core death")
	end
	clock.advance(1)
	expect(session.tick(), "spawn and subsequent serial drain")
	expect(#mock.created == 2, "second mob spawned")
	local records = session.recordsSnapshot()
	expect(records[1].state == "dead" and records[2].state == "alive", "only queued owned death forwarded after tick")
	expect(count(session.eventLog(), "reward_intent") == 1, "once-only intent")
end)

test("nested lifecycle controls during allocation are refused and fault the run", function()
	local session, mock = setup()
	local refused = 0
	mock.controls.onModelCreated = function()
		for _, name in ipairs({ "start", "tick", "stop", "drain" }) do
			local accepted, reason = session[name]()
			expect(not accepted and reason == "reentrant_control_refused", "nested " .. name .. " refused")
			refused += 1
		end
	end
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "reentrant_death_event", "reentry cannot become success")
	expect(refused == 4 and mock.isDestroyed(mock.created[1].model), "serialized cleanup after refusal")
	expect(session.status().state == "stopped", "run stopped")
end)

test("observation failure retains the actual uncleaned core record", function()
	local session, mock = setup()
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(session.drain(), "death accepted")
	mock.controls.observationThrows = true
	expect(not session.tick(), "observation failure not success")
	local record = session.recordsSnapshot()[1]
	expect(
		record.state == "dead" and record.rewarded and not record.cleaned,
		"cleanup acknowledgment withheld on actual record"
	)
	expect(count(session.eventLog(), "all_waves_completed") == 0, "completion withheld")
	expect(session.report().uncertain and session.report().activeBindings == 1, "obligation retained")
	expect(not session.start(), "restart refused")
	mock.controls.observationThrows = false
	expect(not session.stop("known-resource-retry"), "retry cannot erase prior observation uncertainty")
	expect(session.recordsSnapshot()[1].cleaned, "identifiable known resource may be accounted on explicit retry")
	expect(not session.start(), "uncertainty remains")
end)

test("unexpected allocation yield is not resumed or acknowledged", function()
	local session, mock = setup()
	local continued = false
	mock.controls.onModelCreated = function()
		coroutine.yield("unexpected allocation suspension")
		continued = true
	end
	expect(session.start(), "start")
	expect(not session.tick(), "yielded operation refused")
	expect(
		not continued and #mock.created == 1 and not mock.isDestroyed(mock.created[1].model),
		"unreturned allocation retained, thread not resumed"
	)
	expect(session.report().uncertain and not session.start(), "restart prohibited")
	expect(count(session.eventLog(), "mob_spawned") == 0, "no spawn acknowledgment")
end)

test("unexpected teardown yield never acknowledges cleanup", function()
	local session, mock = setup()
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(session.drain(), "death accepted")
	mock.controls.observationYields = true
	expect(not session.tick(), "yield refused")
	expect(not session.recordsSnapshot()[1].cleaned, "actual cleanup not acknowledged")
	expect(session.report().uncertain and not session.start(), "restart refused")
	expect(count(session.eventLog(), "all_waves_completed") == 0, "completion withheld")
end)

test("nonthrowing unparent-only Destroy is not a teardown receipt", function()
	local session, mock = setup()
	spawnWave(session)
	mock.controls.destroyOnlyUnparents = true
	expect(not session.stop("interrupt"), "pcall success and Parent=nil do not prove cleanup")
	expect(
		mock.created[1].model.Parent == nil and not mock.isDestroyed(mock.created[1].model),
		"unparented but not destroyed"
	)
	expect(not session.recordsSnapshot()[1].cleaned and not session.start(), "acknowledgment and restart withheld")
end)

test("foreign descendants prevent container teardown and are never destroyed", function()
	local session, mock = setup()
	spawnWave(session)
	local foreign = { Name = "foreign", Parent = mock.containers[1], destroyCalls = 0 }
	table.insert(mock.containers[1].children, foreign)
	expect(not session.stop("interrupt"), "unverified child refuses container teardown")
	expect(mock.isDestroyed(mock.created[1].model), "known issued model cleaned")
	expect(
		not mock.isDestroyed(mock.containers[1]) and foreign.destroyCalls == 0,
		"container and foreign resource untouched"
	)
	expect(not session.start(), "restart refused")
end)

test("core completion cannot bypass a retained container obligation", function()
	local session, mock = setup()
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	expect(session.drain(), "death accepted")
	mock.controls.destroyContainerOnlyNoOp = true
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "wrapper completion withheld")
	expect(
		session.status().state == "completed" and session.status().bindingState == "faulted",
		"raw core completion distinguished from wrapper fault"
	)
	expect(session.report().containerOutstanding and not session.start(), "core restart cannot bypass the wrapper")
	mock.controls.destroyContainerOnlyNoOp = false
	session.stop("explicit-container-retry")
	expect(session.report().restartAllowed and session.start(), "explicit observed retry permits fresh run")
end)

test("server-held death eligibility is rechecked at drain time", function()
	local session, mock = setup()
	spawnWave(session)
	mock.kill(mock.created[1].humanoid)
	mock.controls.deathEligible = false
	expect(session.drain(), "candidate processed")
	expect(
		session.recordsSnapshot()[1].state == "alive" and count(session.eventLog(), "reward_intent") == 0,
		"ineligible death not accepted"
	)
end)

test("deferred candidates after an interrupted failed stop stay inert", function()
	local session, mock = setup()
	mock.setDelivery("deferred")
	spawnWave(session)
	local callback = mock.callbacksOf(mock.created[1].humanoid)[1]
	mock.kill(mock.created[1].humanoid)
	mock.controls.disconnectThrows = true
	expect(not session.stop("interrupt"), "cleanup retained")
	mock.pump()
	callback() -- already captured invocation, independent of cancellation assumptions
	expect(count(session.eventLog(), "mob_died") == 0, "disarmed callbacks inert during failed cleanup")
	mock.controls.disconnectThrows = false
	expect(session.stop("retry") and session.start(), "known resource retry, then fresh token")
	callback()
	expect(count(session.eventLog(), "reward_intent") == 0, "no stale reward after restart")
end)

test("reentry during cleanup is refused without reporting a successful control", function()
	local session, mock = setup()
	spawnWave(session)
	local refused = 0
	mock.controls.onDestroy = function()
		local accepted, reason = session.stop("nested")
		expect(not accepted and reason == "reentrant_control_refused", "nested teardown refused")
		refused += 1
	end
	local accepted, reason = session.stop("interrupt")
	expect(not accepted and reason == "reentrant_control_refused", "reentrant cleanup not classified as success")
	expect(refused == 2, "model and container teardown both stayed serialized")
	expect(
		mock.isDestroyed(mock.created[1].model) and mock.isDestroyed(mock.containers[1]),
		"known resources accounted"
	)
	expect(session.report().restartAllowed, "clean resource outcome permits an explicitly requested fresh run")
end)

for _, failure in ipairs(failures) do
	print(("GF-001-Q4 FAIL: %s: %s"):format(failure.name, failure.error))
end
print(("GF-001-Q4: %d passed, %d failed"):format(passed, #failures))
if #failures > 0 then
	error("GF-001-Q4 Luau binding suite failed", 0)
end
