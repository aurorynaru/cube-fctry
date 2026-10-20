--!strict
-- GF-001-Q2: actual standalone Luau tests; all engine-like objects synthetic.
local Clock = require("./Clock")
local Config = require("./Config")
local ExampleConfig = require("./ExampleConfig")
local Mobs = require("./Mobs")
local Rewards = require("./Rewards")
local Rng = require("./Rng")
local SpawnPoints = require("./SpawnPoints")
local SyntheticMobAdapter = require("./SyntheticMobAdapter")
local SyntheticMobFactory = require("./SyntheticMobFactory")
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

local function setup(mobCount: number?, interval: number?, rawConfig: any?): (any, any, any, { any })
	local ok, config = Config.validate(rawConfig or {
		maxActiveMobs = 4,
		interWaveDelay = 0,
		mobs = { dummy = ExampleConfig.mobs.dummy },
		spawnPoints = { { id = "synthetic-point", capacity = 4, position = { x = 0, y = 0, z = 0 } } },
		waves = { { mobId = "dummy", count = mobCount or 1, spawnInterval = interval or 0 } },
	})
	expect(ok, "fixture config validates")
	local clock = Clock.stepping(0)
	local factory = SyntheticMobFactory.new()
	local events = {}
	local session = SyntheticMobAdapter.new(config, {
		clock = clock,
		rng = Rng.new(5),
		factory = factory,
		events = events,
		mobs = Mobs,
		selectSpawn = SpawnPoints.select,
		rewards = Rewards.new({ events = events }),
		waveRuntime = WaveRuntime,
	})
	return session, factory, clock, events
end

local function spawn(session: any)
	expect(session.start(), "start")
	expect(session.tick(), "spawn tick")
end

test("successful creation and exact mob identity", function()
	local session, factory, _, events = setup()
	spawn(session)
	local object = factory.created[1]
	expect(#factory.created == 1 and object.synthetic and object.Humanoid.synthetic, "synthetic objects created")
	expect(object.MobRecordId == "mob-0001" and object.MobId == "dummy", "GF-001 identity associated")
	expect(object.SpawnPointId == "synthetic-point" and object.Humanoid.Health == 30, "spawn properties")
	expect(factory.owns(object, object.OwnerToken) and count(events, "mob_spawned") == 1, "owned spawn")
end)

test("multiple simultaneous mobs and independent deaths", function()
	local session, factory, _, events = setup(3)
	spawn(session)
	expect(#factory.created == 3 and session.status().active == 3, "three live objects")
	local first, second, third = factory.created[1], factory.created[2], factory.created[3]
	expect(first ~= second and second ~= third and first.MobRecordId ~= third.MobRecordId, "distinct identity")
	second.Humanoid.Die()
	expect(session.status().active == 2 and count(events, "reward_intent") == 1, "only second death forwarded")
	expect(first.Humanoid.Health == 30 and not third.Destroyed, "other objects unaffected")
	first.Humanoid.Die()
	third.Humanoid.Die()
	expect(session.tick() and session.status().state == "completed", "completion after owned deaths")
	expect(count(events, "reward_intent") == 3 and count(events, "all_waves_completed") == 1, "one intent per mob")
	for _, object in ipairs(factory.created) do
		expect(object.Destroyed and object.destroyCalls == 1, "each owned object destroyed once")
	end
end)

test("existing three-wave example completes through synthetic events", function()
	local session, factory, clock, events = setup(nil, nil, ExampleConfig)
	expect(session.start(), "start example")
	local steps = 0
	while session.status().state == "running" and steps < 200 do
		expect(session.tick(), "example tick")
		for _, object in ipairs(factory.created) do
			if not object.Destroyed and object.Humanoid.Health > 0 then
				object.Humanoid.Die()
			end
		end
		clock.advance(0.25)
		steps += 1
	end
	expect(steps < 200 and session.status().state == "completed", "three waves finish")
	expect(#factory.created == 8 and count(events, "wave_completed") == 3, "existing scheduling reused")
	expect(count(events, "reward_intent") == 8, "exactly eight synthetic intents")
	local points = 0
	for _, event in ipairs(events) do
		if event.type == "reward_intent" then
			points += event.points
		end
	end
	expect(points == 96 and count(events, "all_waves_completed") == 1, "server definitions and one completion")
	for _, object in ipairs(factory.created) do
		expect(object.Destroyed and object.destroyCalls == 1, "all objects cleaned")
	end
end)

test("duplicate death and disconnected callback cannot repeat intent", function()
	local session, factory, _, events = setup()
	spawn(session)
	local object = factory.created[1]
	local oldCallback = object.Humanoid.Died.Snapshot()[1]
	object.Humanoid.Die()
	object.Humanoid.Died.Fire()
	expect(count(events, "mob_died") == 1 and count(events, "reward_intent") == 1, "duplicates refused")
	expect(session.tick() and object.Destroyed, "dead object cleaned")
	oldCallback()
	expect(count(events, "reward_intent") == 1, "disconnected callback inert")
end)

test("unknown callbacks and foreign objects cannot cause death or deletion", function()
	local session, factory, _, events = setup()
	spawn(session)
	local object = factory.created[1]
	local foreign = { synthetic = true, Destroyed = false }
	expect(not factory.owns(foreign, object.OwnerToken), "unknown object not owned")
	object.MobRecordId = "forged-record"
	object.Humanoid.Die()
	expect(session.status().active == 1 and count(events, "reward_intent") == 0, "identity mismatch refuses callback")
	local ok, reason = session.stop("interrupted")
	expect(not ok and reason == "cleanup_failed", "ownership mismatch refuses deletion")
	expect(not object.Destroyed and not foreign.Destroyed, "no unknown deletion")
	expect(not session.start(), "unverified cleanup blocks restart")
	object.MobRecordId = "mob-0001"
	local retried, retryReason = session.stop("retry")
	expect(not retried and retryReason == "cleanup_unverified", "uncertain ownership cannot be promoted to success")
	expect(object.Destroyed and not foreign.Destroyed, "only reverified owned object destroyed")
end)

test("spawn failure does not report success", function()
	local session, factory, _, events = setup()
	factory.failCreate = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "spawn failure stops run")
	expect(#factory.created == 0 and count(events, "mob_spawned") == 0, "no created or reported mob")
	expect(session.status().state == "stopped" and session.status().totalSpawned == 0, "no successful accounting")
end)

test("partial creation is cleaned but not reported as spawn", function()
	local session, factory, _, events = setup()
	factory.failPartial = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "adapter_failure", "partial failure refused")
	expect(#factory.created == 1 and factory.created[1].Destroyed, "known owned partial object cleaned")
	expect(factory.created[1].destroyCalls == 1 and count(events, "mob_spawned") == 0, "no false success")
	expect(session.status().active == 0 and count(events, "reward_intent") == 0, "no reward")
end)

test("throwing creation is uncertain and blocks restart", function()
	local session, factory = setup()
	factory.create = function()
		error("allocation may have happened", 0)
	end
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "unknown allocation not called success")
	expect(not session.start(), "uncertain run cannot restart")
end)

test("foreign factory return refuses deletion and restart", function()
	local session, factory, _, events = setup()
	local foreignFactory = SyntheticMobFactory.new()
	factory.create = function(record: any, point: any, token: any)
		return foreignFactory.create(record, point, token)
	end
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_failed", "foreign object not accepted")
	expect(#foreignFactory.created == 1 and not foreignFactory.created[1].Destroyed, "foreign allocation never deleted")
	expect(count(events, "mob_spawned") == 0 and count(events, "reward_intent") == 0, "no success or reward")
	expect(not session.start(), "unknown ownership prevents restart")
end)

test("claimed successful creation without object is uncertain", function()
	local session, factory, _, events = setup()
	factory.create = function()
		return true, nil
	end
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "missing identity cannot complete")
	expect(count(events, "mob_spawned") == 0 and not session.start(), "no success and restart blocked")
end)

test("connection failure is uncertain and not a spawn", function()
	local session, factory, _, events = setup()
	factory.failConnect = true
	expect(session.start(), "start")
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_unverified", "unknown listener registration blocks restart")
	expect(factory.created[1].Destroyed and count(events, "mob_spawned") == 0, "known object cleaned")
end)

test("destroy failure withholds completion and retries on stop", function()
	local session, factory, _, events = setup()
	spawn(session)
	local object = factory.created[1]
	object.Humanoid.Die()
	factory.failDestroy = true
	local ok, reason = session.tick()
	expect(not ok and reason == "cleanup_failed", "failed destroy stops completion")
	expect(not object.Destroyed and count(events, "all_waves_completed") == 0, "no false completion")
	expect(not session.tick(), "failed cleanup cannot resume progression")
	expect(not session.start(), "cannot restart while owned object retained")
	factory.failDestroy = false
	expect(session.stop("retry"), "retry destroys")
	expect(object.Destroyed and count(events, "reward_intent") == 1, "reward not repeated")
end)

test("disconnect failure retains owned object until retry", function()
	local session, factory = setup()
	spawn(session)
	factory.failDisconnect = true
	local ok, reason = session.stop("interrupted")
	expect(not ok and reason == "cleanup_failed" and not factory.created[1].Destroyed, "no destroy before disconnect")
	factory.created[1].Humanoid.Die()
	expect(session.status().active == 1, "disarmed listener cannot kill while cleanup failed")
	factory.failDisconnect = false
	expect(session.stop("retry") and factory.created[1].Destroyed, "retry disconnects and destroys")
end)

test("interruption disarms and cleans all objects idempotently", function()
	local session, factory, _, events = setup(3)
	spawn(session)
	local callbacks = factory.created[1].Humanoid.Died.Snapshot()
	expect(session.stop("interrupted"), "stop")
	expect(session.status().state == "stopped" and session.status().active == 0, "stopped")
	for _, object in ipairs(factory.created) do
		expect(object.Destroyed and object.destroyCalls == 1, "all owned objects cleaned once")
		object.Humanoid.Die()
	end
	callbacks[1]()
	expect(count(events, "reward_intent") == 0, "stale events inert")
	expect(not session.stop("repeat"), "second cleanup makes no mutations")
	for _, object in ipairs(factory.created) do
		expect(object.destroyCalls == 1, "repeat stop does not destroy twice")
	end
end)

test("restart rejects old callback even with a new active run", function()
	local session, factory, _, events = setup()
	spawn(session)
	local old = factory.created[1]
	local stale = old.Humanoid.Died.Snapshot()[1]
	expect(session.stop("interrupted"), "clean stop")
	spawn(session)
	local fresh = factory.created[2]
	expect(old.OwnerToken ~= fresh.OwnerToken and old.MobRecordId ~= fresh.MobRecordId, "run and record differ")
	stale()
	old.Humanoid.Die()
	expect(session.status().active == 1 and count(events, "reward_intent") == 0, "old run inert")
	fresh.Humanoid.Die()
	expect(count(events, "reward_intent") == 1 and session.tick(), "new run death forwarded")
end)

test("client reward claim rejected without payout", function()
	local session, factory, _, events = setup()
	spawn(session)
	expect(
		session.clientRewardClaim("forged-player", { mob = factory.created[1].MobRecordId, points = 999999 }) == nil,
		"no client grant"
	)
	expect(count(events, "client_reward_rejected") == 1 and count(events, "reward_intent") == 0, "no client intent")
	factory.created[1].Humanoid.Die()
	expect(count(events, "reward_intent") == 1, "trusted death only")
	expect(events[#events].points == 5, "server-config synthetic points, no currency")
end)

for _, failure in ipairs(failures) do
	print(("GF-001-Q2 FAIL: %s: %s"):format(failure.name, failure.error))
end
print(("GF-001-Q2: %d passed, %d failed"):format(passed, #failures))
if #failures > 0 then
	error("GF-001-Q2 Luau adapter suite failed", 0)
end
