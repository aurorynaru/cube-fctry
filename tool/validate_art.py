"""Read-only Milestone A JSON Schema and approval invariant checks.

Run from the project root: python tool/validate_art.py
Requires the existing jsonschema package; does not create files or assets.
"""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker


ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def check(validator, instance, label, expected_valid=True):
    errors = sorted(validator.iter_errors(instance), key=lambda error: str(error.path))
    if bool(errors) == expected_valid:
        detail = "; ".join(error.message for error in errors[:2])
        raise AssertionError(f"{label}: unexpected validity; {detail}")


def draft_request():
    return {
        "schema_version": "1.0", "id": "example-stone-0001",
        "asset_type": "tileable_texture", "game_id": "example-game",
        "style_profile_id": "adventure-fantasy",
        "description": "Synthetic validation fixture, not a generated asset.",
        "roblox_usage": "Hypothetical repeating stone wall surface.",
        "delivery": {"width_px": 1024, "height_px": 1024, "format": "png", "tiling_required": True},
        "generation": {"model": "fixture", "workflow": "fixture", "method": "local_ai", "seed": 1},
        "provenance": {"source": "fixture only", "license": "fixture only", "derivations": []},
        "quality_gates": {name: {"result": "pending", "evidence": []} for name in
                          ("originality", "rights", "style", "technical", "performance", "tiling", "in_engine")},
        "approval": {"status": "draft"},
    }


def main():
    profile_schema = load(ART / "schemas/style-profile.schema.json")
    request_schema = load(ART / "schemas/asset-request.schema.json")
    for schema in (profile_schema, request_schema):
        Draft202012Validator.check_schema(schema)
    profile_validator = Draft202012Validator(profile_schema, format_checker=FormatChecker())
    request_validator = Draft202012Validator(request_schema, format_checker=FormatChecker())

    preset_paths = sorted((ART / "presets").glob("*.json"))
    expected = {"playful-cartoon", "adventure-fantasy", "atmospheric-survival",
                "competitive-clean", "cozy-social"}
    assert {path.stem for path in preset_paths} == expected, "Unexpected or missing preset"
    for path in preset_paths:
        preset = load(path)
        assert preset["id"] == path.stem, f"ID/filename mismatch: {path}"
        check(profile_validator, preset, path.name)

    draft = draft_request()
    check(request_validator, draft, "synthetic draft")
    check(request_validator, {**draft, "asset_type": "mesh"}, "mismatched mesh format", False)
    check(request_validator, {**draft, "delivery": {**draft["delivery"], "tiling_required": False}},
          "tileable texture without tiling", False)

    approved = deepcopy(draft)
    for gate in approved["quality_gates"].values():
        gate.update(result="pass", evidence=["fixture evidence"], reviewer="fixture reviewer")
    approved["delivery"]["artifact_sha256"] = "a" * 64
    approved["approval"] = {"status": "approved", "reviewer": "fixture reviewer",
                            "date": "2026-10-17", "roblox_asset_id": "123456",
                            "registry_path": "fixture/registry"}
    check(request_validator, approved, "synthetic complete approval")

    negatives = 0
    for name in approved["quality_gates"]:
        for change in ("missing", "pending", "no_evidence", "no_reviewer"):
            candidate = deepcopy(approved)
            if change == "missing":
                del candidate["quality_gates"][name]
            elif change == "pending":
                candidate["quality_gates"][name]["result"] = "pending"
            elif change == "no_evidence":
                candidate["quality_gates"][name]["evidence"] = []
            else:
                del candidate["quality_gates"][name]["reviewer"]
            check(request_validator, candidate, f"{name} {change}", False)
            negatives += 1
    for field, section in (("reviewer", "approval"), ("date", "approval"),
                           ("roblox_asset_id", "approval"), ("registry_path", "approval"),
                           ("artifact_sha256", "delivery")):
        candidate = deepcopy(approved)
        del candidate[section][field]
        check(request_validator, candidate, f"approved missing {field}", False)
        negatives += 1
    candidate = deepcopy(approved)
    candidate["approval"]["date"] = "not-a-date"
    check(request_validator, candidate, "invalid approval date", False)
    negatives += 1
    candidate = deepcopy(approved)
    candidate["delivery"]["tiling_required"] = False
    candidate["asset_type"] = "image"
    candidate["quality_gates"]["tiling"] = {"result": "not_applicable", "evidence": []}
    check(request_validator, candidate, "approved non-tiling image")

    print(f"PASS: 2 metaschemas, {len(preset_paths)} presets, 3 positive request fixtures, "
          f"{negatives + 2} negative request fixtures; no files written")


if __name__ == "__main__":
    main()
