"""GF-001 offline NPC wave prototype: Python reference twin of the Luau modules.

Reference transcription of experiments/gf001_npc_waves/luau/ for deterministic
offline verification (tests/test_gf001_npc_waves.py). The Luau modules are the
reusable deliverable; this twin exists only because no standalone Luau runtime
is installed in this environment. Both are written from one specification and
use the same Lehmer generator constants and lifecycle algorithm, but cross-
language equality is NOT verified here (see docs/GF_001_OFFLINE_NPC_WAVES.md).
Non-production, not mapped by default.project.json, no Roblox engine calls.
"""

import math

MODULUS = 2147483647
MULTIPLIER = 48271
DEFAULT_SEED = 20261018

REQUIRED_DEPS = ("clock", "rng", "adapter", "events", "mobs", "select_spawn", "rewards")


class Rng:
    def __init__(self, source):
        if callable(source):
            self._next_float_source = source
        else:
            seed = source if isinstance(source, (int, float)) and not isinstance(source, bool) else 0
            current = int(abs(seed)) % (MODULUS - 1) + 1

            def seeded():
                nonlocal current
                current = (current * MULTIPLIER) % MODULUS
                return current / MODULUS

            self._next_float_source = seeded

    def next_float(self):
        value = self._next_float_source()
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not (0 <= value < 1):
            raise ValueError("[GF001] injected Rng source must return a number in [0, 1)")
        return value

    def pick(self, items):
        if len(items) == 0:
            raise ValueError("[GF001] Rng.pick requires a non-empty list")
        index = math.floor(self.next_float() * len(items)) + 1
        if index > len(items):
            index = len(items)
        return items[index - 1]


class Clock:
    def __init__(self, now_function):
        self._now = now_function

    def now(self):
        return self._now()


class SteppingClock:
    def __init__(self, start=0):
        self._t = start

    def now(self):
        return self._t

    def advance(self, delta):
        self._t = self._t + delta


class MobsModule:
    @staticmethod
    def new(next_id=1):
        return {"nextId": next_id, "records": []}

    @staticmethod
    def spawn(registry, mob_def, mob_id, spawn_point_id, now):
        record = {
            "id": "mob-%04d" % registry["nextId"],
            "mobId": mob_id,
            "health": mob_def["maxHealth"],
            "maxHealth": mob_def["maxHealth"],
            "state": "alive",
            "spawnPointId": spawn_point_id,
            "bornAt": now,
            "diedAt": None,
            "rewarded": False,
            "cleaned": False,
        }
        registry["records"].append(record)
        registry["nextId"] += 1
        return record

    @staticmethod
    def damage(mob, amount, now):
        if not _is_positive_number(amount):
            return "invalid_damage"
        if mob["state"] != "alive":
            return "ignored"
        mob["health"] = mob["health"] - amount
        if mob["health"] <= 0:
            mob["health"] = 0
            mob["state"] = "dead"
            mob["diedAt"] = now
            return "died"
        return "damaged"

    @staticmethod
    def kill(mob, now):
        if mob["state"] != "alive":
            return "ignored"
        mob["health"] = 0
        mob["state"] = "dead"
        mob["diedAt"] = now
        return "died"

    @staticmethod
    def despawn(mob, now):
        if mob["state"] == "despawned":
            return "ignored"
        mob["state"] = "despawned"
        mob["despawnedAt"] = now
        return "despawned"

    @staticmethod
    def aliveCount(registry):
        count = 0
        for mob in registry["records"]:
            if mob["state"] == "alive":
                count += 1
        return count

    @staticmethod
    def all(registry):
        return list(registry["records"])


def select_spawn(spawn_points, occupancy, rng):
    minimum = None
    for spawn_point in spawn_points:
        occupied = occupancy.get(spawn_point["id"], 0)
        if occupied < spawn_point["capacity"]:
            if minimum is None or occupied < minimum:
                minimum = occupied
    if minimum is None:
        return None
    eligible = [
        spawn_point
        for spawn_point in spawn_points
        if occupancy.get(spawn_point["id"], 0) < spawn_point["capacity"]
        and occupancy.get(spawn_point["id"], 0) == minimum
    ]
    return rng.pick(eligible)


class MemoryAdapter:
    def __init__(self):
        self.spawns = []
        self.despawns = []

    def spawn(self, mob, spawn_point):
        self.spawns.append(
            {
                "mob": mob["id"],
                "mobId": mob["mobId"],
                "spawnPoint": spawn_point["id"],
                "position": spawn_point["position"],
            }
        )
        return True

    def despawn(self, mob):
        self.despawns.append({"mob": mob["id"]})
        return True


class Rewards:
    def __init__(self, deps):
        if not isinstance(deps, dict) or not isinstance(deps.get("events"), list):
            raise ValueError("[GF001] Rewards.new requires deps.events")
        self._events = deps["events"]

    def record_death(self, mob, mob_def, now):
        if mob["state"] != "dead":
            return None
        if mob["rewarded"]:
            return None
        points = None
        if isinstance(mob_def, dict) and isinstance(mob_def.get("reward"), dict):
            points = mob_def["reward"].get("points")
        if (
            not isinstance(points, (int, float))
            or isinstance(points, bool)
            or not (0 <= points < math.inf)
            or points % 1 != 0
        ):
            return None
        mob["rewarded"] = True
        event = {
            "type": "reward_intent",
            "mob": mob["id"],
            "mobId": mob["mobId"],
            "points": points,
            "at": now,
        }
        self._events.append(event)
        return event

    def handle_client_request(self, player_id, payload, now):
        event = {
            "type": "client_reward_rejected",
            "player": player_id,
            "payloadType": type(payload).__name__,
            "reason": "client_reward_claims_are_not_authoritative",
            "at": now,
        }
        self._events.append(event)
        return None


def _is_non_empty_string(value):
    return isinstance(value, str) and len(value) > 0


def _is_positive_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 < value < math.inf


def _is_positive_integer(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 < value < math.inf
        and value % 1 == 0
    )


def _is_non_negative_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and 0 <= value < math.inf


def _is_non_negative_integer(value):
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and 0 <= value < math.inf
        and value % 1 == 0
    )


def validate_config(config):
    if not isinstance(config, dict):
        return False, ["config must be a table"]
    errors = []
    if not _is_positive_integer(config.get("maxActiveMobs")):
        errors.append("maxActiveMobs must be a positive integer")
    if not _is_non_negative_number(config.get("interWaveDelay")):
        errors.append("interWaveDelay must be a number >= 0")
    mobs = config.get("mobs")
    mobs_valid = True
    if not isinstance(mobs, dict):
        errors.append("mobs must be a table of mob definitions")
        mobs_valid = False
    elif len(mobs) == 0:
        errors.append("mobs must define at least one mob")
        mobs_valid = False
    else:
        for mob_id, mob_def in mobs.items():
            label = "mobs.%s" % mob_id
            if not _is_non_empty_string(mob_id):
                errors.append("mob ids must be non-empty strings")
                mobs_valid = False
            if not isinstance(mob_def, dict):
                errors.append("%s must be a table" % label)
                mobs_valid = False
                continue
            if not _is_non_empty_string(mob_def.get("displayName")):
                errors.append("%s.displayName must be a non-empty string" % label)
                mobs_valid = False
            if not _is_positive_number(mob_def.get("maxHealth")):
                errors.append("%s.maxHealth must be a number > 0" % label)
                mobs_valid = False
            reward = mob_def.get("reward")
            if not isinstance(reward, dict) or not _is_non_negative_integer(reward.get("points")):
                errors.append("%s.reward.points must be an integer >= 0" % label)
                mobs_valid = False
    spawn_points = config.get("spawnPoints")
    spawn_points_valid = True
    if not isinstance(spawn_points, list):
        errors.append("spawnPoints must be an array of spawn point definitions")
        spawn_points_valid = False
    elif len(spawn_points) < 1:
        errors.append("spawnPoints must define at least one spawn point")
        spawn_points_valid = False
    else:
        seen_ids = set()
        for index, spawn_point in enumerate(spawn_points):
            label = "spawnPoints[%d]" % index
            if not isinstance(spawn_point, dict):
                errors.append("%s must be a table" % label)
                spawn_points_valid = False
                continue
            point_id = spawn_point.get("id")
            if not _is_non_empty_string(point_id):
                errors.append("%s.id must be a non-empty string" % label)
                spawn_points_valid = False
            elif point_id in seen_ids:
                errors.append("%s.id duplicates an earlier spawn point id" % label)
                spawn_points_valid = False
            else:
                seen_ids.add(point_id)
            if not _is_positive_integer(spawn_point.get("capacity")):
                errors.append("%s.capacity must be a positive integer" % label)
                spawn_points_valid = False
            position = spawn_point.get("position")
            if (
                not isinstance(position, dict)
                or not isinstance(position.get("x"), (int, float))
                or isinstance(position.get("x"), bool)
                or not isinstance(position.get("y"), (int, float))
                or isinstance(position.get("y"), bool)
                or not isinstance(position.get("z"), (int, float))
                or isinstance(position.get("z"), bool)
                or not all(math.isfinite(position[axis]) for axis in ("x", "y", "z"))
            ):
                errors.append("%s.position must have numeric x, y and z" % label)
                spawn_points_valid = False
    waves = config.get("waves")
    waves_valid = True
    if not isinstance(waves, list):
        errors.append("waves must be an array of wave definitions")
        waves_valid = False
    elif len(waves) < 1:
        errors.append("waves must define at least one wave")
        waves_valid = False
    else:
        for index, wave in enumerate(waves):
            label = "waves[%d]" % index
            if not isinstance(wave, dict):
                errors.append("%s must be a table" % label)
                waves_valid = False
                continue
            mob_id = wave.get("mobId")
            if not _is_non_empty_string(mob_id):
                errors.append("%s.mobId must be a non-empty string" % label)
                waves_valid = False
            elif not isinstance(mobs, dict) or not isinstance(mobs.get(mob_id), dict):
                errors.append("%s.mobId does not reference a defined mob" % label)
                waves_valid = False
            if not _is_positive_integer(wave.get("count")):
                errors.append("%s.count must be a positive integer" % label)
                waves_valid = False
            if not _is_non_negative_number(wave.get("spawnInterval")):
                errors.append("%s.spawnInterval must be a number >= 0" % label)
                waves_valid = False
            if wave.get("startDelay") is not None and not _is_non_negative_number(wave.get("startDelay")):
                errors.append("%s.startDelay must be a number >= 0" % label)
                waves_valid = False
    if not (mobs_valid and spawn_points_valid and waves_valid) or errors:
        return False, errors
    normalized = {
        "maxActiveMobs": config["maxActiveMobs"],
        "interWaveDelay": config["interWaveDelay"],
        "mobs": config["mobs"],
        "spawnPoints": config["spawnPoints"],
        "waves": [
            {
                "mobId": wave["mobId"],
                "count": wave["count"],
                "spawnInterval": wave["spawnInterval"],
                "startDelay": wave.get("startDelay") or 0,
            }
            for wave in config["waves"]
        ],
    }
    return True, normalized


class WaveRuntime:
    def __init__(self, config, deps):
        if not isinstance(config, dict):
            raise ValueError("[GF001] WaveRuntime requires a config table")
        if (
            not isinstance(config.get("maxActiveMobs"), (int, float))
            or isinstance(config.get("maxActiveMobs"), bool)
            or config["maxActiveMobs"] < 1
            or not isinstance(config.get("interWaveDelay"), (int, float))
            or isinstance(config.get("interWaveDelay"), bool)
            or config["interWaveDelay"] < 0
            or not isinstance(config.get("mobs"), dict)
            or not isinstance(config.get("spawnPoints"), list)
            or len(config["spawnPoints"]) < 1
            or not isinstance(config.get("waves"), list)
            or len(config["waves"]) < 1
        ):
            raise ValueError("[GF001] WaveRuntime requires a config normalized by Config.validate")
        if not isinstance(deps, dict):
            raise ValueError("[GF001] WaveRuntime requires a deps table")
        for name in REQUIRED_DEPS:
            if deps.get(name) is None:
                raise ValueError("[GF001] WaveRuntime deps.%s is required" % name)
        self._config = config
        self._deps = deps
        self._state = "idle"
        self._phase = "idle"
        self._wave_index = 0
        self._wave = None
        self._pending = 0
        self._spawned_in_wave = 0
        self._killed_in_wave = 0
        self._total_spawned = 0
        self._total_killed = 0
        self._waves_completed = 0
        self._registry = deps["mobs"].new()
        self._occupancy = {}
        self._next_phase_at = None
        self._next_spawn_at = None

    def _emit(self, event_type, fields):
        event = {"type": event_type, "at": self._deps["clock"].now()}
        event.update(fields)
        self._deps["events"].append(event)

    def _release_occupancy(self, spawn_point_id):
        occupied = self._occupancy.get(spawn_point_id)
        if occupied is not None and occupied > 0:
            self._occupancy[spawn_point_id] = occupied - 1

    def _find_record(self, mob_record_id):
        for mob in self._deps["mobs"].all(self._registry):
            if mob["id"] == mob_record_id:
                return mob
        return None

    def _on_server_death(self, mob):
        self._emit("mob_died", {"mob": mob["id"], "mobId": mob["mobId"]})
        self._killed_in_wave += 1
        self._total_killed += 1
        self._release_occupancy(mob["spawnPointId"])
        self._deps["rewards"].record_death(mob, self._config["mobs"][mob["mobId"]], self._deps["clock"].now())

    def _cleanup(self, mob):
        if not mob["cleaned"]:
            if self._deps["adapter"].despawn(mob) is not True:
                raise RuntimeError("[GF001] adapter despawn failed")
            mob["cleaned"] = True

    def start(self):
        if self._state == "running":
            return False, "already_running"
        self._registry = self._deps["mobs"].new(self._registry["nextId"])
        self._occupancy = {}
        self._wave_index = 1
        self._wave = self._config["waves"][0]
        self._pending = self._wave["count"]
        self._spawned_in_wave = 0
        self._killed_in_wave = 0
        self._total_spawned = 0
        self._total_killed = 0
        self._waves_completed = 0
        self._state = "running"
        self._phase = "delay"
        self._next_phase_at = self._deps["clock"].now() + self._wave["startDelay"]
        return True, None

    def tick(self):
        if self._state != "running":
            return False, "not_running"
        now = self._deps["clock"].now()
        for mob in self.records():
            if mob["state"] == "dead":
                self._cleanup(mob)
        if self._phase == "delay":
            if now >= self._next_phase_at:
                self._emit(
                    "wave_started",
                    {"wave": self._wave_index, "mobId": self._wave["mobId"], "count": self._wave["count"]},
                )
                self._phase = "spawning"
                self._next_spawn_at = now
        if self._phase == "spawning":
            alive = self._deps["mobs"].aliveCount(self._registry)
            while self._pending > 0 and alive < self._config["maxActiveMobs"] and now >= self._next_spawn_at:
                spawn_point = self._deps["select_spawn"](self._config["spawnPoints"], self._occupancy, self._deps["rng"])
                if spawn_point is None:
                    break
                mob_def = self._config["mobs"][self._wave["mobId"]]
                record = self._deps["mobs"].spawn(self._registry, mob_def, self._wave["mobId"], spawn_point["id"], now)
                if self._deps["adapter"].spawn(record, spawn_point) is not True:
                    raise RuntimeError("[GF001] adapter spawn failed")
                self._occupancy[spawn_point["id"]] = self._occupancy.get(spawn_point["id"], 0) + 1
                self._emit(
                    "mob_spawned",
                    {"mob": record["id"], "mobId": record["mobId"], "spawnPoint": spawn_point["id"]},
                )
                self._pending -= 1
                self._spawned_in_wave += 1
                self._total_spawned += 1
                alive += 1
                self._next_spawn_at = now + self._wave["spawnInterval"]
            if self._pending == 0:
                self._phase = "clearing"
        if self._phase == "clearing":
            if self._pending == 0 and self._deps["mobs"].aliveCount(self._registry) == 0:
                self._emit(
                    "wave_completed",
                    {"wave": self._wave_index, "spawned": self._spawned_in_wave, "killed": self._killed_in_wave},
                )
                self._waves_completed += 1
                if self._wave_index < len(self._config["waves"]):
                    self._wave_index += 1
                    self._wave = self._config["waves"][self._wave_index - 1]
                    self._pending = self._wave["count"]
                    self._spawned_in_wave = 0
                    self._killed_in_wave = 0
                    self._phase = "intermission"
                    self._next_phase_at = now + self._config["interWaveDelay"]
                else:
                    self._phase = "completed"
                    self._state = "completed"
                    self._emit("all_waves_completed", {"waves": len(self._config["waves"])})
        if self._phase == "intermission":
            if now >= self._next_phase_at:
                self._phase = "delay"
                self._next_phase_at = now + self._wave["startDelay"]
        return True, None

    def damage_mob(self, mob_record_id, amount):
        if self._state != "running":
            return False, "not_running"
        mob = self._find_record(mob_record_id)
        if mob is None:
            return False, "unknown_mob"
        outcome = self._deps["mobs"].damage(mob, amount, self._deps["clock"].now())
        if outcome == "invalid_damage":
            return False, outcome
        if outcome == "died":
            self._on_server_death(mob)
        return True, outcome

    def kill_mob(self, mob_record_id):
        if self._state != "running":
            return False, "not_running"
        mob = self._find_record(mob_record_id)
        if mob is None:
            return False, "unknown_mob"
        outcome = self._deps["mobs"].kill(mob, self._deps["clock"].now())
        if outcome == "died":
            self._on_server_death(mob)
        return True, outcome

    def stop(self, reason=None):
        if self._state != "running":
            return False
        now = self._deps["clock"].now()
        cleaned = 0
        for mob in self._deps["mobs"].all(self._registry):
            self._cleanup(mob)
            if mob["state"] == "alive":
                self._deps["mobs"].despawn(mob, now)
                self._release_occupancy(mob["spawnPointId"])
                cleaned += 1
                self._emit("mob_despawned", {"mob": mob["id"], "reason": reason or "manual"})
        self._emit(
            "wave_stopped",
            {"wave": self._wave_index, "activeCleaned": cleaned, "reason": reason or "manual"},
        )
        self._state = "stopped"
        self._phase = "idle"
        self._pending = 0
        return True

    def records(self):
        return self._deps["mobs"].all(self._registry)

    def status(self):
        return {
            "state": self._state,
            "phase": self._phase,
            "wave": self._wave_index,
            "pending": self._pending,
            "active": self._deps["mobs"].aliveCount(self._registry),
            "spawnedInWave": self._spawned_in_wave,
            "killedInWave": self._killed_in_wave,
            "totalSpawned": self._total_spawned,
            "totalKilled": self._total_killed,
            "wavesCompleted": self._waves_completed,
        }


EXAMPLE_CONFIG = {
    "maxActiveMobs": 6,
    "interWaveDelay": 1.5,
    "mobs": {
        "dummy": {
            "displayName": "Training Dummy",
            "maxHealth": 30,
            "reward": {"points": 5},
        },
        "crawler": {
            "displayName": "Stone Crawler",
            "maxHealth": 60,
            "reward": {"points": 12},
        },
        "golem": {
            "displayName": "Vein Golem",
            "maxHealth": 150,
            "reward": {"points": 40},
        },
    },
    "spawnPoints": [
        {"id": "north-gate", "capacity": 2, "position": {"x": 0, "y": 1, "z": -40}},
        {"id": "east-gate", "capacity": 2, "position": {"x": 40, "y": 1, "z": 0}},
        {"id": "south-gate", "capacity": 2, "position": {"x": 0, "y": 1, "z": 40}},
        {"id": "west-gate", "capacity": 2, "position": {"x": -40, "y": 1, "z": 0}},
    ],
    "waves": [
        {"mobId": "dummy", "count": 4, "spawnInterval": 0.5, "startDelay": 0},
        {"mobId": "crawler", "count": 3, "spawnInterval": 1, "startDelay": 1},
        {"mobId": "golem", "count": 1, "spawnInterval": 1, "startDelay": 2},
    ],
}
