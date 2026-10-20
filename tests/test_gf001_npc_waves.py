import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "experiments" / "gf001_npc_waves" / "python"),
)

import gf001_core as core


def count_events(events, event_type):
    return sum(1 for event in events if event["type"] == event_type)


def find_event(events, event_type):
    for event in events:
        if event["type"] == event_type:
            return event
    return None


def new_runtime(config, seed=None):
    events = []
    clock = core.SteppingClock(0)
    rng = core.Rng(seed if seed is not None else core.DEFAULT_SEED)
    adapter = core.MemoryAdapter()
    rewards = core.Rewards({"events": events})
    runtime = core.WaveRuntime(
        config,
        {
            "clock": clock,
            "rng": rng,
            "adapter": adapter,
            "events": events,
            "mobs": core.MobsModule,
            "select_spawn": core.select_spawn,
            "rewards": rewards,
        },
    )
    return runtime, clock, adapter, events


def drive_to_completion(runtime, clock):
    ticks = 0
    while runtime.status()["state"] == "running" and ticks < 1000:
        runtime.tick()
        for mob in runtime.records():
            if mob["state"] == "alive":
                runtime.damage_mob(mob["id"], 15)
        clock.advance(0.25)
        ticks += 1
    assert ticks < 1000, "scenario did not complete within the tick budget"


class Gf001NpcWaveTests(unittest.TestCase):
    def assertRejected(self, config, index):
        ok, errors = core.validate_config(config)
        self.assertFalse(ok, "invalid case %s must be rejected" % (index,))
        self.assertIsInstance(errors, list)
        self.assertTrue(len(errors) > 0, "invalid case %s must list errors" % (index,))

    def test_example_config_validates_and_fills_start_delay_defaults(self):
        ok, normalized = core.validate_config(core.EXAMPLE_CONFIG)
        self.assertTrue(ok)
        self.assertEqual(len(normalized["waves"]), 3)
        self.assertEqual(normalized["waves"][2]["startDelay"], 2)
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 2,
                "interWaveDelay": 0,
                "mobs": {"dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"]},
                "spawnPoints": [core.EXAMPLE_CONFIG["spawnPoints"][0]],
                "waves": [{"mobId": "dummy", "count": 1, "spawnInterval": 0}],
            }
        )
        self.assertTrue(ok)
        self.assertIsInstance(normalized, dict)
        self.assertEqual(normalized["waves"][0]["startDelay"], 0)

    def test_invalid_configurations_are_rejected(self):
        cases = [
            lambda config: config.__setitem__("maxActiveMobs", 0),
            lambda config: config.__setitem__("maxActiveMobs", 1.5),
            lambda config: config.__setitem__("interWaveDelay", -1),
            lambda config: config.__setitem__("mobs", {}),
            lambda config: config["mobs"]["dummy"].__setitem__("maxHealth", 0),
            lambda config: config["mobs"]["dummy"]["reward"].__setitem__("points", -5),
            lambda config: config["mobs"]["dummy"]["reward"].__setitem__("points", 1.5),
            lambda config: config.__setitem__("spawnPoints", []),
            lambda config: config["spawnPoints"][0].__setitem__("capacity", 0),
            lambda config: config["spawnPoints"][1].__setitem__("id", config["spawnPoints"][0]["id"]),
            lambda config: config.__setitem__("waves", []),
            lambda config: config["waves"][0].__setitem__("mobId", "unknown-mob"),
            lambda config: config["waves"][0].__setitem__("count", 0),
            lambda config: config["waves"][0].__setitem__("spawnInterval", -0.5),
            lambda config: config["waves"][0].__setitem__("startDelay", -1),
        ]
        for index, mutate in enumerate(cases):
            config = copy.deepcopy(core.EXAMPLE_CONFIG)
            mutate(config)
            self.assertRejected(config, index)
        self.assertRejected(None, "nil")

    def test_wave_start_and_stop_transitions(self):
        runtime, clock, adapter, events = new_runtime(core.EXAMPLE_CONFIG)
        ok, _ = runtime.tick()
        self.assertFalse(ok)
        ok, _ = runtime.start()
        self.assertTrue(ok)
        self.assertEqual(runtime.status()["state"], "running")
        self.assertEqual(runtime.status()["wave"], 1)
        self.assertEqual(runtime.status()["phase"], "delay")
        again, _ = runtime.start()
        self.assertFalse(again)
        clock.advance(1)
        runtime.tick()
        self.assertEqual(runtime.status()["phase"], "spawning")
        self.assertTrue(runtime.stop())
        self.assertEqual(runtime.status()["state"], "stopped")
        self.assertFalse(runtime.stop())
        ok, _ = runtime.tick()
        self.assertFalse(ok)
        ok, _ = runtime.start()
        self.assertTrue(ok)

    def test_maximum_active_mob_enforcement(self):
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 3,
                "interWaveDelay": 0,
                "mobs": {"dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"]},
                "spawnPoints": [
                    {"id": "a", "capacity": 5, "position": {"x": 0, "y": 0, "z": 0}},
                    {"id": "b", "capacity": 5, "position": {"x": 1, "y": 0, "z": 0}},
                ],
                "waves": [{"mobId": "dummy", "count": 10, "spawnInterval": 0.5}],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        ticks = 0
        while runtime.status()["state"] == "running" and ticks < 500:
            runtime.tick()
            self.assertLessEqual(runtime.status()["active"], 3)
            if runtime.status()["active"] == 3:
                alive = [mob for mob in runtime.records() if mob["state"] == "alive"]
                self.assertEqual(len(alive), 3)
                runtime.kill_mob(alive[0]["id"])
            elif runtime.status()["pending"] == 0 and runtime.status()["active"] > 0:
                alive = [mob for mob in runtime.records() if mob["state"] == "alive"]
                runtime.kill_mob(alive[0]["id"])
            clock.advance(0.25)
            ticks += 1
        self.assertLess(ticks, 500)
        self.assertEqual(runtime.status()["totalSpawned"], 10)
        self.assertEqual(runtime.status()["state"], "completed")

    def test_spawn_eligibility_requires_running_state_delay_and_capacity(self):
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 3,
                "interWaveDelay": 0,
                "mobs": {"dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"]},
                "spawnPoints": [
                    {"id": "only", "capacity": 1, "position": {"x": 0, "y": 0, "z": 0}},
                ],
                "waves": [{"mobId": "dummy", "count": 3, "spawnInterval": 0, "startDelay": 2}],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        clock.advance(1)
        runtime.tick()
        self.assertEqual(runtime.status()["phase"], "delay")
        self.assertEqual(runtime.status()["pending"], 3)
        clock.advance(1.5)
        runtime.tick()
        self.assertEqual(runtime.status()["spawnedInWave"], 1)
        runtime.tick()
        self.assertEqual(runtime.status()["spawnedInWave"], 1)
        spawned = runtime.records()[0]
        ok, _ = runtime.kill_mob(spawned["id"])
        self.assertTrue(ok)
        runtime.tick()
        self.assertEqual(runtime.status()["spawnedInWave"], 2)

    def test_duplicate_death_and_duplicate_rewards_are_prevented(self):
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 4,
                "interWaveDelay": 0,
                "mobs": {"dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"]},
                "spawnPoints": [
                    {"id": "only", "capacity": 4, "position": {"x": 0, "y": 0, "z": 0}},
                ],
                "waves": [{"mobId": "dummy", "count": 1, "spawnInterval": 0}],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        clock.advance(1)
        runtime.tick()
        mob = runtime.records()[0]
        damage_ok, outcome = runtime.damage_mob(mob["id"], 999)
        self.assertTrue(damage_ok)
        self.assertEqual(outcome, "died")
        self.assertEqual(count_events(events, "mob_died"), 1)
        self.assertEqual(count_events(events, "reward_intent"), 1)
        _, second_damage = runtime.damage_mob(mob["id"], 999)
        self.assertEqual(second_damage, "ignored")
        _, second_kill = runtime.kill_mob(mob["id"])
        self.assertEqual(second_kill, "ignored")
        self.assertEqual(count_events(events, "mob_died"), 1)
        self.assertEqual(count_events(events, "reward_intent"), 1)
        runtime.tick()
        self.assertEqual(runtime.status()["state"], "completed")

    def test_wave_completion_progresses_through_all_waves(self):
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 4,
                "interWaveDelay": 3,
                "mobs": {
                    "dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"],
                    "crawler": core.EXAMPLE_CONFIG["mobs"]["crawler"],
                },
                "spawnPoints": [
                    {"id": "a", "capacity": 4, "position": {"x": 0, "y": 0, "z": 0}},
                ],
                "waves": [
                    {"mobId": "dummy", "count": 2, "spawnInterval": 0},
                    {"mobId": "crawler", "count": 2, "spawnInterval": 0},
                ],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        runtime.tick()
        for mob in runtime.records():
            runtime.kill_mob(mob["id"])
        runtime.tick()
        self.assertEqual(runtime.status()["wavesCompleted"], 1)
        self.assertEqual(runtime.status()["phase"], "intermission")
        self.assertEqual(count_events(events, "wave_started"), 1)
        clock.advance(3)
        runtime.tick()
        runtime.tick()
        self.assertEqual(runtime.status()["wave"], 2)
        self.assertEqual(runtime.status()["spawnedInWave"], 2)
        self.assertEqual(count_events(events, "wave_started"), 2)
        for mob in runtime.records():
            if mob["state"] == "alive":
                runtime.kill_mob(mob["id"])
        runtime.tick()
        self.assertEqual(runtime.status()["state"], "completed")
        self.assertEqual(runtime.status()["wavesCompleted"], 2)

    def test_cleanup_after_interruption_and_clean_restart(self):
        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 10,
                "interWaveDelay": 0,
                "mobs": {"dummy": core.EXAMPLE_CONFIG["mobs"]["dummy"]},
                "spawnPoints": [
                    {"id": "a", "capacity": 10, "position": {"x": 0, "y": 0, "z": 0}},
                ],
                "waves": [{"mobId": "dummy", "count": 5, "spawnInterval": 1}],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        clock.advance(0.5)
        runtime.tick()
        clock.advance(1)
        runtime.tick()
        self.assertEqual(runtime.status()["totalSpawned"], 2)
        self.assertTrue(runtime.stop("interrupted"))
        stopped_event = events[-1]
        self.assertEqual(stopped_event["type"], "wave_stopped")
        self.assertEqual(stopped_event["activeCleaned"], 2)
        self.assertEqual(len(adapter.despawns), 2)
        for mob in runtime.records():
            self.assertNotEqual(mob["state"], "alive")
        self.assertEqual(runtime.status()["pending"], 0)
        ok, _ = runtime.start()
        self.assertTrue(ok)
        clock.advance(1)
        runtime.tick()
        self.assertEqual(count_events(events, "wave_started"), 2)
        self.assertEqual(runtime.status()["totalSpawned"], 1)

    def test_untrusted_client_reward_requests_are_always_rejected(self):
        standalone_events = []
        rewards = core.Rewards({"events": standalone_events})
        result = rewards.handle_client_request(
            11822718311, {"mobId": "golem", "points": 999999, "killed": True}, 5
        )
        self.assertIsNone(result)
        self.assertEqual(len(standalone_events), 1)
        self.assertEqual(standalone_events[0]["type"], "client_reward_rejected")
        self.assertEqual(count_events(standalone_events, "reward_intent"), 0)
        second = rewards.handle_client_request("player-two", "i killed the golem", 6)
        self.assertIsNone(second)
        self.assertEqual(count_events(standalone_events, "reward_intent"), 0)

        ok, normalized = core.validate_config(
            {
                "maxActiveMobs": 2,
                "interWaveDelay": 0,
                "mobs": {"golem": core.EXAMPLE_CONFIG["mobs"]["golem"]},
                "spawnPoints": [
                    {"id": "a", "capacity": 2, "position": {"x": 0, "y": 0, "z": 0}},
                ],
                "waves": [{"mobId": "golem", "count": 1, "spawnInterval": 0}],
            }
        )
        self.assertTrue(ok)
        runtime, clock, adapter, events = new_runtime(normalized)
        runtime.start()
        clock.advance(1)
        runtime.tick()
        mob = runtime.records()[0]
        shared_rewards = core.Rewards({"events": events})
        shared_rewards.handle_client_request(mob["id"], {"mob": mob["id"], "killed": True}, clock.now())
        self.assertEqual(count_events(events, "client_reward_rejected"), 1)
        self.assertEqual(count_events(events, "reward_intent"), 0)
        runtime.kill_mob(mob["id"])
        self.assertEqual(count_events(events, "reward_intent"), 1)
        intent = find_event(events, "reward_intent")
        self.assertIsNotNone(intent)
        self.assertEqual(intent["points"], 40)

    def test_deterministic_replay_with_the_same_seed(self):
        def run_scenario():
            runtime, clock, adapter, events = new_runtime(core.EXAMPLE_CONFIG, 424242)
            runtime.start()
            drive_to_completion(runtime, clock)
            return events

        first = run_scenario()
        second = run_scenario()
        self.assertGreater(len(first), 0)
        self.assertEqual(first, second)

        other_runtime, other_clock, other_adapter, other_events = new_runtime(core.EXAMPLE_CONFIG, 777)
        other_runtime.start()
        drive_to_completion(other_runtime, other_clock)
        self.assertNotEqual(first, other_events)

    def test_full_example_scenario_completes_with_validated_rewards(self):
        runtime, clock, adapter, events = new_runtime(core.EXAMPLE_CONFIG)
        runtime.start()
        drive_to_completion(runtime, clock)
        status = runtime.status()
        self.assertEqual(status["state"], "completed")
        self.assertEqual(status["totalSpawned"], 8)
        self.assertEqual(status["totalKilled"], 8)
        self.assertEqual(status["wavesCompleted"], 3)
        self.assertEqual(count_events(events, "reward_intent"), 8)
        points = sum(event["points"] for event in events if event["type"] == "reward_intent")
        self.assertEqual(points, 96)

    def test_wave_runtime_rejects_invalid_config_and_deps(self):
        with self.assertRaises(ValueError):
            core.WaveRuntime({}, {"clock": None})
        bad = copy.deepcopy(core.EXAMPLE_CONFIG)
        bad["maxActiveMobs"] = 0
        with self.assertRaises(ValueError):
            core.WaveRuntime(bad, None)
        good = core.validate_config(core.EXAMPLE_CONFIG)[1]
        with self.assertRaises(ValueError):
            core.WaveRuntime(good, {})

    def test_nonfinite_configuration_values_are_rejected(self):
        paths = [
            ("maxActiveMobs",), ("interWaveDelay",),
            ("mobs", "dummy", "maxHealth"), ("mobs", "dummy", "reward", "points"),
            ("spawnPoints", 0, "capacity"), ("spawnPoints", 0, "position", "x"),
            ("spawnPoints", 0, "position", "y"), ("spawnPoints", 0, "position", "z"),
            ("waves", 0, "count"), ("waves", 0, "spawnInterval"), ("waves", 0, "startDelay"),
        ]
        for path in paths:
            for value in (float("nan"), float("inf"), -float("inf")):
                with self.subTest(path=path, value=value):
                    config = copy.deepcopy(core.EXAMPLE_CONFIG)
                    parent = config
                    for key in path[:-1]:
                        parent = parent[key]
                    parent[path[-1]] = value
                    self.assertRejected(config, path)

    def test_invalid_damage_cannot_heal_or_poison_health(self):
        runtime, _, _, events = new_runtime(core.EXAMPLE_CONFIG)
        runtime.start()
        runtime.tick()
        mob = runtime.records()[0]
        health = mob["health"]
        for amount in (-1, 0, float("nan"), float("inf"), "10", None, True):
            self.assertEqual(runtime.damage_mob(mob["id"], amount), (False, "invalid_damage"))
            self.assertEqual(mob["health"], health)
            self.assertEqual(mob["state"], "alive")
        self.assertEqual(count_events(events, "reward_intent"), 0)

    def test_dead_instances_are_cleaned_once_before_wave_completion(self):
        runtime, clock, adapter, events = new_runtime(core.EXAMPLE_CONFIG)
        runtime.start()
        drive_to_completion(runtime, clock)
        self.assertEqual(len(adapter.spawns), 8)
        self.assertEqual(len(adapter.despawns), 8)
        self.assertEqual(len({item["mob"] for item in adapter.despawns}), 8)
        self.assertTrue(all(mob["cleaned"] for mob in runtime.records()))
        self.assertFalse(runtime.stop())
        runtime.tick()
        self.assertEqual(len(adapter.despawns), 8)
        self.assertEqual(count_events(events, "all_waves_completed"), 1)

    def test_restart_does_not_reuse_ids_for_stale_death_callbacks(self):
        runtime, _, _, events = new_runtime(core.EXAMPLE_CONFIG)
        runtime.start()
        runtime.tick()
        old_id = runtime.records()[0]["id"]
        runtime.stop("interrupted")
        runtime.start()
        runtime.tick()
        new_mob = runtime.records()[0]
        self.assertNotEqual(old_id, new_mob["id"])
        self.assertEqual(runtime.kill_mob(old_id), (False, "unknown_mob"))
        self.assertEqual(new_mob["state"], "alive")
        self.assertEqual(count_events(events, "reward_intent"), 0)

    def test_adapter_spawn_failure_is_not_a_successful_spawn(self):
        runtime, _, adapter, events = new_runtime(core.EXAMPLE_CONFIG)
        adapter.spawn = lambda mob, point: False
        runtime.start()
        with self.assertRaisesRegex(RuntimeError, "spawn failed"):
            runtime.tick()
        self.assertEqual(count_events(events, "mob_spawned"), 0)
        self.assertEqual(runtime.status()["totalSpawned"], 0)
        self.assertTrue(runtime.stop("adapter_failure"))
        self.assertEqual(runtime.status()["active"], 0)
        self.assertEqual(len(adapter.despawns), 1)

    def test_cleanup_failure_prevents_completion_and_can_be_retried(self):
        config = copy.deepcopy(core.EXAMPLE_CONFIG)
        config["waves"] = [{"mobId": "dummy", "count": 1, "spawnInterval": 0, "startDelay": 0}]
        runtime, _, adapter, events = new_runtime(config)
        runtime.start()
        runtime.tick()
        mob = runtime.records()[0]
        runtime.kill_mob(mob["id"])
        original_despawn = adapter.despawn
        adapter.despawn = lambda record: False
        with self.assertRaisesRegex(RuntimeError, "despawn failed"):
            runtime.tick()
        self.assertFalse(mob["cleaned"])
        self.assertEqual(count_events(events, "wave_completed"), 0)
        adapter.despawn = original_despawn
        self.assertTrue(runtime.stop("interrupted"))
        self.assertTrue(mob["cleaned"])
        self.assertEqual(len(adapter.despawns), 1)
        self.assertEqual(count_events(events, "reward_intent"), 1)

    def test_reward_recorder_rejects_living_invalid_and_duplicate_deaths(self):
        events = []
        rewards = core.Rewards({"events": events})
        registry = core.MobsModule.new()
        definition = core.EXAMPLE_CONFIG["mobs"]["dummy"]
        mob = core.MobsModule.spawn(registry, definition, "dummy", "a", 0)
        self.assertIsNone(rewards.record_death(mob, definition, 0))
        core.MobsModule.kill(mob, 1)
        for points in (-1, 1.5, float("nan"), float("inf"), None, True):
            self.assertIsNone(rewards.record_death(mob, {"reward": {"points": points}}, 1))
            self.assertFalse(mob["rewarded"])
        self.assertEqual(rewards.record_death(mob, definition, 1)["points"], 5)
        self.assertIsNone(rewards.record_death(mob, definition, 1))
        self.assertEqual(count_events(events, "reward_intent"), 1)

    def test_injected_randomness_and_invalid_rng_inputs(self):
        self.assertEqual(core.Rng(lambda: 0).pick(["a", "b"]), "a")
        self.assertEqual(core.Rng(lambda: 0.999).pick(["a", "b"]), "b")
        for value in (-0.1, 1, float("nan"), float("inf"), None, True):
            with self.assertRaises(ValueError):
                core.Rng(lambda: value).pick(["a"])
        with self.assertRaises(ValueError):
            core.Rng(1).pick([])
        for seed in (float("nan"), float("inf")):
            with self.assertRaises((ValueError, OverflowError)):
                core.Rng(seed)


if __name__ == "__main__":
    unittest.main()
