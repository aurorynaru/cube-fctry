"""GF-001-Q1 parity driver: reference execution and comparison against the Luau runner.

Part of experiments/gf001_npc_waves/parity/ (isolated, non-production). This
script executes the shared parity vectors (vectors.json, the canonical JSON dump
of vectors.luau) against the Python reference twin
experiments/gf001_npc_waves/python/gf001_core.py, writes its own canonical JSON
results, and compares them structurally with the Luau runner's results
(luau_results.jsonl, produced by parity_run.luau under the pinned standalone
Luau CLI). Both harnesses run the identical deterministic scenario/step
schedules against their own implementation; neither side sees the other's
output before producing its own.

Comparison semantics:
- Exact structural equality for all projected fields, with two deliberate,
  precisely-scoped equivalences: (1) the ``payloadType`` diagnostic string in
  ``client_reward_rejected`` events uses each language's own type names (Luau
  ``table``/``string``/... vs Python ``dict``/``str``/...); both sides are
  normalized to the Luau names. (2) A JSON ``null`` value and an absent key are
  equivalent, because Lua tables cannot store nil (an absent key *is* nil);
  nulls are dropped from both sides before comparison.
- Python ``int``/``float`` compare equal to a Luau number of the same value
  (textual 1 vs 1.0 formatting differences are irrelevant); booleans never
  compare equal to numbers.

Vector ``path`` indexes are 1-based (Luau semantics); this driver converts them
to 0-based Python list indexes. Mutation ``special`` values mirror
parity_run.luau: "none", "remove", "emptyTable", "nan", "inf", "-inf".

Usage:
    python gf001_parity.py [--vectors vectors.json]
                          [--luau-results luau_results.jsonl]
                          [--out python_results.jsonl]
Exit code 0 only when every vector matches.
"""

import argparse
import copy
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "python"))

import gf001_core as core  # noqa: E402

RECORD_FIELDS = (
    "id",
    "mobId",
    "health",
    "state",
    "spawnPointId",
    "rewarded",
    "cleaned",
    "bornAt",
    "diedAt",
    "despawnedAt",
)

PY_TYPE_TO_LUAU = {
    "dict": "table",
    "str": "string",
    "int": "number",
    "float": "number",
    "bool": "boolean",
    "NoneType": "nil",
}


def classify_raised(message):
    if "adapter spawn failed" in message:
        return "adapter_spawn_failed"
    if "adapter despawn failed" in message:
        return "adapter_despawn_failed"
    return "unclassified_error"


def resolve_mutation_value(mutation):
    special = mutation.get("special")
    if special == "emptyTable":
        return {}
    if special == "nan":
        return float("nan")
    if special == "inf":
        return math.inf
    if special == "-inf":
        return -math.inf
    return mutation.get("value")


def apply_mutation(config, mutation):
    if mutation.get("special") == "none":
        return
    path = mutation["path"]

    def descend(parent, key):
        if isinstance(parent, list):
            return parent[int(key) - 1]
        return parent[key]

    parent = config
    for key in path[:-1]:
        parent = descend(parent, key)
    last = path[-1]
    if mutation.get("special") == "remove":
        if isinstance(parent, list):
            del parent[int(last) - 1]
        else:
            del parent[last]
    else:
        value = resolve_mutation_value(mutation)
        if isinstance(parent, list):
            parent[int(last) - 1] = value
        else:
            parent[last] = value


def project_status(status):
    return dict(status)


def project_records(records):
    return [{field: record.get(field) for field in RECORD_FIELDS} for record in records]


def project_events(events):
    return [dict(event) for event in events]


def first_alive_record(runtime):
    for record in runtime.records():
        if record["state"] == "alive":
            return record
    return None


def run_validate_vector(vector):
    mutations = []
    for mutation in vector["mutations"]:
        config = copy.deepcopy(core.EXAMPLE_CONFIG)
        apply_mutation(config, mutation)
        ok, result = core.validate_config(config)
        entry = {"ok": ok}
        if ok:
            entry["waveCount"] = len(result["waves"])
            entry["wave1StartDelay"] = result["waves"][0]["startDelay"]
        else:
            entry["errorCount"] = len(result)
        mutations.append(entry)
    return {"name": vector["name"], "kind": "validate", "mutations": mutations}


def run_runtime_vector(vector):
    base_config = core.EXAMPLE_CONFIG if vector.get("exampleConfig") else vector["config"]
    valid, result = core.validate_config(copy.deepcopy(base_config))
    events = []
    if not valid:
        return {
            "name": vector["name"],
            "kind": "runtime",
            "configValid": False,
            "validateErrorCount": len(result),
            "steps": [],
            "events": [],
        }
    normalized = result
    clock = core.SteppingClock(0)
    adapter = core.MemoryAdapter()
    rewards = core.Rewards({"events": events})
    runtime = core.WaveRuntime(
        normalized,
        {
            "clock": clock,
            "rng": core.Rng(vector["seed"]),
            "adapter": adapter,
            "events": events,
            "mobs": core.MobsModule,
            "select_spawn": core.select_spawn,
            "rewards": rewards,
        },
    )
    original_spawn = adapter.spawn
    original_despawn = adapter.despawn
    steps = []
    for step in vector["steps"]:
        snapshot = {"op": step["op"]}
        op = step["op"]
        if op == "start":
            ok, reason = runtime.start()
            snapshot["ok"] = ok
            snapshot["reason"] = reason
        elif op == "tick":
            try:
                ok, reason = runtime.tick()
                snapshot["ok"] = ok
                snapshot["reason"] = reason
            except (RuntimeError, ValueError) as error:
                snapshot["raised"] = classify_raised(str(error))
        elif op == "advance":
            clock.advance(step["delta"])
            snapshot["applied"] = step["delta"]
        elif op == "stop":
            snapshot["ok"] = runtime.stop(step.get("reason"))
        elif op == "killFirst":
            target = first_alive_record(runtime)
            if target is None:
                snapshot["skipped"] = True
            else:
                ok, outcome = runtime.kill_mob(target["id"])
                snapshot["target"] = target["id"]
                snapshot["ok"] = ok
                snapshot["outcome"] = outcome
        elif op == "killAll":
            killed = 0
            for record in runtime.records():
                if record["state"] == "alive":
                    runtime.kill_mob(record["id"])
                    killed += 1
            snapshot["killed"] = killed
        elif op == "killById":
            ok, outcome = runtime.kill_mob(step["id"])
            snapshot["ok"] = ok
            snapshot["outcome"] = outcome
        elif op == "damageFirst":
            target = first_alive_record(runtime)
            if target is None:
                snapshot["skipped"] = True
            else:
                ok, outcome = runtime.damage_mob(target["id"], step["amount"])
                snapshot["target"] = target["id"]
                snapshot["amount"] = step["amount"]
                snapshot["ok"] = ok
                snapshot["outcome"] = outcome
        elif op == "damageById":
            ok, outcome = runtime.damage_mob(step["id"], step["amount"])
            snapshot["ok"] = ok
            snapshot["outcome"] = outcome
        elif op == "clientRequest":
            rewards.handle_client_request(step["player"], step["payload"], clock.now())
            snapshot["submitted"] = True
        elif op == "failSpawn":
            adapter.spawn = lambda mob, spawn_point: False
            snapshot["injected"] = "failing"
        elif op == "restoreSpawn":
            adapter.spawn = original_spawn
            snapshot["injected"] = "restored"
        elif op == "failDespawn":
            adapter.despawn = lambda mob: False
            snapshot["injected"] = "failing"
        elif op == "restoreDespawn":
            adapter.despawn = original_despawn
            snapshot["injected"] = "restored"
        else:
            raise ValueError("[GF001-Q1] unknown parity op: %r" % (op,))
        snapshot["status"] = project_status(runtime.status())
        snapshot["records"] = project_records(runtime.records())
        snapshot["eventCount"] = len(events)
        steps.append(snapshot)
    return {
        "name": vector["name"],
        "kind": "runtime",
        "configValid": True,
        "steps": steps,
        "events": project_events(events),
    }


def run_vectors(vectors):
    results = []
    for vector in vectors:
        if vector["kind"] == "validate":
            results.append(run_validate_vector(vector))
        else:
            results.append(run_runtime_vector(vector))
    return results


def normalize(value):
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if item is None:
                # Lua tables cannot store nil: an absent key and a nil value
                # are indistinguishable, so nulls are dropped on both sides.
                continue
            if key == "payloadType" and isinstance(item, str):
                out[key] = PY_TYPE_TO_LUAU.get(item, item)
            else:
                out[key] = normalize(item)
        return out
    return value


def deep_equal(left, right):
    left_type = type(left)
    right_type = type(right)
    if left_type is not right_type:
        if (
            left_type in (int, float)
            and right_type in (int, float)
        ):
            return left == right
        return False
    if left_type is dict:
        if set(left.keys()) != set(right.keys()):
            return False
        return all(deep_equal(left[key], right[key]) for key in left)
    if left_type is list:
        if len(left) != len(right):
            return False
        return all(deep_equal(a, b) for a, b in zip(left, right))
    return left == right


def first_difference(left, right, path="$"):
    if not deep_equal(left, right):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left.keys()) | set(right.keys())):
                if key not in left:
                    return "%s.%s: missing in Python result" % (path, key)
                if key not in right:
                    return "%s.%s: missing in Luau result" % (path, key)
                if not deep_equal(left[key], right[key]):
                    return first_difference(left[key], right[key], "%s.%s" % (path, key))
        if isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                return "%s: length %d (Python) vs %d (Luau)" % (path, len(left), len(right))
            for index, (a, b) in enumerate(zip(left, right)):
                if not deep_equal(a, b):
                    return first_difference(a, b, "%s[%d]" % (path, index))
        return "%s: %r (Python) vs %r (Luau)" % (path, left, right)
    return None


def main():
    parser = argparse.ArgumentParser(description="GF-001-Q1 Python parity driver/comparator")
    parser.add_argument("--vectors", default="vectors.json")
    parser.add_argument("--luau-results", default="luau_results.jsonl")
    parser.add_argument("--out", default="python_results.jsonl")
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    vectors_path = here / args.vectors if not Path(args.vectors).is_absolute() else Path(args.vectors)
    luau_path = (
        here / args.luau_results if not Path(args.luau_results).is_absolute() else Path(args.luau_results)
    )
    out_path = here / args.out if not Path(args.out).is_absolute() else Path(args.out)

    with vectors_path.open("r", encoding="utf-8") as handle:
        vectors = json.load(handle)

    python_results = run_vectors(vectors)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for result in python_results:
            handle.write(json.dumps(result, sort_keys=True, separators=(",", ":")))
            handle.write("\n")

    with luau_path.open("r", encoding="utf-8") as handle:
        luau_results = [json.loads(line) for line in handle if line.strip()]

    py_names = [result["name"] for result in python_results]
    luau_names = [result["name"] for result in luau_results]
    if py_names != luau_names:
        print("VECTOR MISMATCH: Python %r vs Luau %r" % (py_names, luau_names))
        return 1

    failures = 0
    for python_result, luau_result in zip(python_results, luau_results):
        normalized_python = normalize(python_result)
        normalized_luau = normalize(luau_result)
        if deep_equal(normalized_python, normalized_luau):
            print("PASS %s" % python_result["name"])
        else:
            failures += 1
            print("FAIL %s: %s" % (python_result["name"], first_difference(normalized_python, normalized_luau)))

    print("GF-001-Q1 parity: %d passed, %d failed" % (len(python_results) - failures, failures))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
