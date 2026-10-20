"""Milestone B1 append-only asset registry. No network or Studio access.

The journal is the source of truth: a status in a standalone request is never
accepted as a transition. Local hash chaining detects accidental edits, not a
malicious operator who can rewrite the entire project and recalculate hashes.
"""

from copy import deepcopy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re

from jsonschema import Draft202012Validator, FormatChecker


STATES = ("draft", "art_approved", "generated", "qc_pending", "qc_passed", "imported", "approved")
NEXT = dict(zip(STATES, STATES[1:]))
GATES = ("originality", "rights", "style", "technical", "performance", "tiling")
SHA = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-z][a-z0-9-]*-[0-9]{4,}\Z")
SLUG = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*\Z")
ALLOWED = ("art/", "workflows/", "registry/evidence/", "outputs/")


class RegistryError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise RegistryError(message)


def exact(value, keys, label):
    require(isinstance(value, dict) and set(value) == set(keys), f"{label}: expected keys {sorted(keys)}")


def text(value, label):
    require(isinstance(value, str) and bool(value.strip()), f"{label}: nonempty text required")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class Registry:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.journal = self.root / "registry/events.jsonl"
        self.lock = self.root / "registry/events.lock"
        self.request_validator = Draft202012Validator(
            json.loads((self.root / "art/schemas/asset-request.schema.json").read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )
        self.profile_validator = Draft202012Validator(
            json.loads((self.root / "art/schemas/style-profile.schema.json").read_text(encoding="utf-8")),
            format_checker=FormatChecker(),
        )

    def path(self, name, prefixes=ALLOWED):
        require(isinstance(name, str) and name and "\\" not in name and not name.startswith("/")
                and all(part not in (".", "..", "") for part in name.split("/"))
                and PurePosixPath(name).as_posix() == name
                and any(name.startswith(prefix) for prefix in prefixes), f"unsafe project path: {name!r}")
        try:
            path = (self.root / name).resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise RegistryError(f"missing or invalid file: {name}") from exc
        require(path.is_file() and path.is_relative_to(self.root), f"missing or escaping file: {name}")
        return path

    def file(self, name, sha=None, size=None, prefixes=ALLOWED):
        path = self.path(name, prefixes)
        data = path.read_bytes()
        if sha is not None:
            require(isinstance(sha, str) and SHA.fullmatch(sha) and digest(data) == sha,
                    f"SHA-256 mismatch: {name}")
        if size is not None:
            require(type(size) is int and size > 0 and len(data) == size, f"size mismatch: {name}")
        return data

    def json_file(self, name, prefixes=ALLOWED):
        try:
            return json.loads(self.file(name, prefixes=prefixes))
        except (ValueError, UnicodeDecodeError) as exc:
            raise RegistryError(f"invalid JSON: {name}: {exc}") from exc

    def manifest(self, game):
        require(isinstance(game, str) and SLUG.fullmatch(game), "invalid game ID")
        name = f"art/games/{game}.json"
        config = self.json_file(name, ("art/games/",))
        exact(config, ("game_id", "actors", "art_bibles"), name)
        require(config["game_id"] == game, "manifest game mismatch")
        roles = ("creators", "art_owners", "qc_reviewers", "importers", "final_reviewers")
        exact(config["actors"], roles, "actors")
        for role in roles:
            people = config["actors"][role]
            require(isinstance(people, list) and len(people) == len(set(people)) and bool(people),
                    f"{role}: nonempty unique roster required")
            for person in people:
                text(person, role)
        require(isinstance(config["art_bibles"], list), "art_bibles must be a list")
        versions = set()
        for bible in config["art_bibles"]:
            exact(bible, ("version", "path", "sha256", "profile_id", "approval_evidence",
                          "approval_evidence_sha256", "approved_by", "approved_on"), "art bible")
            text(bible["version"], "bible version")
            require(bible["version"] not in versions, "duplicate Art Bible version")
            versions.add(bible["version"])
            require(bible["approved_by"] in config["actors"]["art_owners"], "unknown Art Bible approver")
            require(isinstance(bible["approved_on"], str), "missing Art Bible approval date")
            try:
                datetime.strptime(bible["approved_on"], "%Y-%m-%d")
            except ValueError as exc:
                raise RegistryError("invalid Art Bible approval date") from exc
            body = self.file(bible["path"], bible["sha256"], prefixes=("art/games/",))
            require(b"[game title]" not in body and b"[slug]" not in body, "Art Bible is a template")
            require(f"**Game ID:** {game}".encode() in body
                    and f"**Style profile:** {bible['profile_id']}".encode() in body
                    and f"**Version:** {bible['version']}".encode() in body,
                    "Art Bible contents do not match game, profile and version")
            approval = self.json_file(bible["approval_evidence"], ("registry/evidence/",))
            self.file(bible["approval_evidence"], bible["approval_evidence_sha256"],
                      prefixes=("registry/evidence/",))
            exact(approval, ("game_id", "version", "bible_sha256", "profile_id", "approved_by", "approved_on"),
                  "Art Bible approval evidence")
            require(approval == {"game_id": game, "version": bible["version"],
                                 "bible_sha256": bible["sha256"], "profile_id": bible["profile_id"],
                                 "approved_by": bible["approved_by"], "approved_on": bible["approved_on"]},
                    "Art Bible approval evidence mismatch")
        return config

    def profile(self, profile_id):
        require(isinstance(profile_id, str) and SLUG.fullmatch(profile_id), "invalid profile ID")
        paths = (f"art/profiles/{profile_id}.json", f"art/presets/{profile_id}.json")
        present = [name for name in paths if (self.root / name).exists()]
        require(len(present) == 1, f"missing or ambiguous style profile: {profile_id}")
        profile = self.json_file(present[0], ("art/profiles/", "art/presets/"))
        self.schema(self.profile_validator, profile)
        require(profile["id"] == profile_id, "style profile ID mismatch")

    @staticmethod
    def schema(validator, value):
        errors = sorted(validator.iter_errors(value), key=lambda error: str(error.path))
        require(not errors, f"schema: {errors[0].message}" if errors else "")

    def evidence(self, paths):
        require(isinstance(paths, list) and bool(paths) and len(paths) == len(set(paths)),
                "nonempty, unique evidence paths required")
        for name in paths:
            require(bool(self.file(name, prefixes=("registry/evidence/",))), f"empty evidence file: {name}")

    @staticmethod
    def evidence_paths(action, data):
        if action == "qc_passed":
            return [path for gate in data["gates"].values() for path in gate["evidence"]] + data["preimport_performance"]["evidence"]
        if action == "approved":
            return data["in_engine"]["evidence"] + data["measured_performance"]["evidence"] + data["final_evidence"]
        if action == "rejected":
            return data["evidence"]
        return []

    def actor(self, manifest, role, name):
        text(name, "actor")
        require(name in manifest["actors"][role], f"actor not authorized as {role}: {name}")

    def replay(self, events):
        records = {}
        previous = "0" * 64
        for index, event in enumerate(events, 1):
            exact(event, ("action", "id", "actor", "data", "at", "prev_hash", "hash", "evidence_hashes"), f"event {index}")
            require(event["prev_hash"] == previous and event["hash"] == digest(canonical({
                key: val for key, val in event.items() if key != "hash"})), f"event {index}: broken hash chain")
            previous = event["hash"]
            asset_id, action, data, actor = (event[key] for key in ("id", "action", "data", "actor"))
            require(isinstance(asset_id, str) and ID.fullmatch(asset_id), "invalid asset ID")
            try:
                require(datetime.fromisoformat(event["at"]).tzinfo is not None, "event needs timezone")
            except (TypeError, ValueError) as exc:
                raise RegistryError("invalid event timestamp") from exc
            paths = self.evidence_paths(action, data)
            require(isinstance(event["evidence_hashes"], dict) and set(event["evidence_hashes"]) == set(paths),
                    "evidence digest list mismatch")
            for path, sha in event["evidence_hashes"].items():
                self.file(path, sha, prefixes=("registry/evidence/",))
            if action == "create":
                require(asset_id not in records, f"duplicate asset ID: {asset_id}")
                exact(data, ("request",), "create")
                request = deepcopy(data["request"])
                self.schema(self.request_validator, request)
                require(request["id"] == asset_id and request["approval"] == {"status": "draft"},
                        "create requires matching draft request")
                require(all(gate == {"result": "pending", "evidence": []}
                            for gate in request["quality_gates"].values()), "create requires pending gates")
                require("artifact_sha256" not in request["delivery"], "draft has output hash")
                manifest = self.manifest(request["game_id"])
                self.profile(request["style_profile_id"])
                self.actor(manifest, "creators", actor)
                records[asset_id] = {"request": request, "creator": actor, "revision": 1,
                                     "candidates": [], "history": [], "bible": None,
                                     "output": None, "import": None, "performance": None}
            else:
                require(asset_id in records, f"unknown asset ID: {asset_id}")
                record = records[asset_id]
                request = record["request"]
                manifest = self.manifest(request["game_id"])
                self.profile(request["style_profile_id"])
                current = request["approval"]["status"]
                if action in STATES[1:]:
                    require(NEXT.get(current) == action, f"forbidden transition: {current} -> {action}")
                    self.transition(record, manifest, action, actor, data, asset_id, event["at"])
                    request["approval"]["status"] = action
                    if action == "imported":
                        require(not any(other_id != asset_id and other["request"]["approval"].get("roblox_asset_id")
                                        == data["roblox_asset_id"] for other_id, other in records.items()),
                                "duplicate Roblox asset ID")
                elif action == "rejected":
                    require(current not in ("approved", "rejected"), "cannot reject terminal state")
                    exact(data, ("reason", "evidence"), "rejection")
                    text(data["reason"], "rejection reason")
                    self.evidence(data["evidence"])
                    self.actor(manifest, "final_reviewers" if current == "imported" else "qc_reviewers", actor)
                    require(actor != record["creator"], "creator cannot reject own asset")
                    request["approval"]["status"] = "rejected"
                elif action == "rework":
                    require(current == "rejected", "rework requires rejection")
                    exact(data, ("request",), "rework")
                    new = deepcopy(data["request"])
                    self.schema(self.request_validator, new)
                    require(new["id"] == asset_id and new["game_id"] == request["game_id"]
                            and new["approval"] == {"status": "draft"}, "invalid rework draft")
                    require(all(gate == {"result": "pending", "evidence": []}
                                for gate in new["quality_gates"].values()), "rework requires pending gates")
                    require("artifact_sha256" not in new["delivery"], "rework draft has output hash")
                    self.profile(new["style_profile_id"])
                    self.actor(manifest, "creators", actor)
                    record["candidates"].append(deepcopy(request))
                    record.update(request=new, creator=actor, revision=record["revision"] + 1,
                                  bible=None, output=None, **{"import": None}, performance=None)
                else:
                    raise RegistryError(f"unsupported action: {action}")
            self.schema(self.request_validator, records[asset_id]["request"])
            records[asset_id]["history"].append(deepcopy(event))
        return records

    def transition(self, record, manifest, action, actor, data, asset_id, at):
        request = record["request"]
        approval = request["approval"]
        if action == "art_approved":
            exact(data, ("bible_version", "bible_sha256", "approval_evidence_sha256"), action)
            self.actor(manifest, "art_owners", actor)
            bible = next((b for b in manifest["art_bibles"] if b["version"] == data["bible_version"]), None)
            require(bible is not None and bible["profile_id"] == request["style_profile_id"],
                    "unknown game-specific Art Bible approval/profile")
            require(data["bible_sha256"] == bible["sha256"]
                    and data["approval_evidence_sha256"] == bible["approval_evidence_sha256"],
                    "Art Bible or approval hash mismatch")
            record["bible"] = deepcopy(bible)
        elif action == "generated":
            self.actor(manifest, "creators", actor)
            required = {"path", "sha256", "size_bytes"}
            if request["generation"]["method"] == "local_ai":
                required |= {"workflow_path", "workflow_sha256"}
                require("seed" in request["generation"], "local AI seed required")
                require(request["generation"]["workflow"] == data.get("workflow_path")
                        and request["generation"]["model"] != "none", "workflow provenance mismatch")
            exact(data, required, action)
            require(data["path"].lower().endswith("." + request["delivery"]["format"]), "output format mismatch")
            self.file(data["path"], data["sha256"], data["size_bytes"], ("outputs/", "workflows/"))
            if "workflow_path" in data:
                self.file(data["workflow_path"], data["workflow_sha256"], prefixes=("workflows/",))
            request["delivery"]["artifact_sha256"] = data["sha256"]
            record["output"] = deepcopy(data)
        elif action == "qc_pending":
            exact(data, (), action)
        elif action == "qc_passed":
            exact(data, ("gates", "preimport_performance"), action)
            self.actor(manifest, "qc_reviewers", actor)
            require(actor != record["creator"], "creator cannot QC own asset")
            exact(data["gates"], GATES, "QC gates")
            for gate_name, gate in data["gates"].items():
                self.schema(self.request_validator, {**request, "quality_gates": {
                    **request["quality_gates"], gate_name: gate}})
                if gate_name == "tiling" and not request["delivery"]["tiling_required"]:
                    require(gate["result"] in ("pass", "not_applicable"), "invalid optional tiling gate")
                else:
                    require(gate["result"] == "pass", f"{gate_name}: pass required")
                if gate["result"] == "pass":
                    self.evidence(gate["evidence"])
                    self.actor(manifest, "qc_reviewers", gate["reviewer"])
                    require(gate["reviewer"] != record["creator"], "creator cannot review own gate")
                else:
                    require(gate == {"result": "not_applicable", "evidence": []}, "invalid N/A gate")
            estimate = data["preimport_performance"]
            exact(estimate, ("kind", "notes", "evidence"), "pre-import performance")
            require(estimate["kind"] == "estimate", "pre-import performance is an estimate")
            text(estimate["notes"], "estimate notes")
            self.evidence(estimate["evidence"])
            request["quality_gates"].update(deepcopy(data["gates"]))
            approval.update(reviewer=actor, date=datetime.fromisoformat(at).date().isoformat())
            record["performance"] = deepcopy(estimate)
        elif action == "imported":
            exact(data, ("roblox_asset_id", "record_path", "record_sha256"), action)
            self.actor(manifest, "importers", actor)
            require(isinstance(data["roblox_asset_id"], str)
                    and re.fullmatch(r"[1-9][0-9]*", data["roblox_asset_id"]), "invalid Roblox asset ID")
            evidence = self.json_file(data["record_path"], ("registry/evidence/",))
            self.file(data["record_path"], data["record_sha256"], prefixes=("registry/evidence/",))
            exact(evidence, ("game_id", "asset_id", "revision", "output_sha256", "roblox_asset_id",
                             "imported_by", "imported_on"), "import record")
            require(evidence == {"game_id": request["game_id"], "asset_id": asset_id,
                                 "revision": record["revision"], "output_sha256": record["output"]["sha256"],
                                 "roblox_asset_id": data["roblox_asset_id"], "imported_by": actor,
                                 "imported_on": evidence["imported_on"]}, "import record mismatch")
            try:
                datetime.strptime(evidence["imported_on"], "%Y-%m-%d")
            except (TypeError, ValueError) as exc:
                raise RegistryError("invalid import date") from exc
            approval["roblox_asset_id"] = data["roblox_asset_id"]
            record["import"] = deepcopy(data)
        elif action == "approved":
            exact(data, ("in_engine", "measured_performance", "final_evidence"), action)
            self.actor(manifest, "final_reviewers", actor)
            require(actor != record["creator"], "creator cannot finally approve own asset")
            gate = data["in_engine"]
            require(isinstance(gate, dict) and gate.get("result") == "pass" and gate.get("reviewer") == actor,
                    "in-engine reviewer/sign-off required")
            self.evidence(gate.get("evidence"))
            measured = data["measured_performance"]
            exact(measured, ("kind", "device", "scene", "fps", "evidence"), "in-engine measurement")
            require(measured["kind"] == "in_engine_measurement" and type(measured["fps"]) in (float, int)
                    and measured["fps"] > 0, "measured in-engine FPS required")
            text(measured["device"], "device")
            text(measured["scene"], "scene")
            self.evidence(measured["evidence"])
            self.evidence(data["final_evidence"])
            request["quality_gates"]["in_engine"] = deepcopy(gate)
            approval.update(reviewer=actor, date=datetime.fromisoformat(at).date().isoformat(),
                            registry_path="registry/events.jsonl")
            record["performance"] = deepcopy(measured)

    def read_events(self):
        require(not self.journal.is_symlink(), "journal cannot be a symlink")
        if not self.journal.exists():
            return []
        try:
            lines = self.journal.read_text(encoding="utf-8").splitlines(keepends=True)
            require(all(line.endswith("\n") for line in lines), "incomplete journal line")
            return [json.loads(line) for line in lines]
        except (ValueError, UnicodeDecodeError) as exc:
            raise RegistryError(f"invalid journal: {exc}") from exc

    @contextmanager
    def exclusive(self):
        require(self.journal.parent.is_dir(), "registry/ directory must exist")
        require(self.journal.parent.resolve() == self.root / "registry", "registry directory escapes project")
        # O_EXCL rejects concurrent writers and stale locks; manual recovery after inspection.
        try:
            fd = os.open(self.lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise RegistryError("registry locked: concurrent write rejected") from exc
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as lock:
                lock.write(f"pid={os.getpid()}\n")
            yield
        finally:
            self.lock.unlink()

    def validate(self):
        with self.exclusive():
            return self.replay(self.read_events())

    def apply(self, action, asset_id, actor, data, dry_run=False):
        with self.exclusive():
            events = self.read_events()
            self.replay(events)
            event = {"action": action, "id": asset_id, "actor": actor, "data": data,
                     "at": datetime.now(timezone.utc).isoformat(),
                     "prev_hash": events[-1]["hash"] if events else "0" * 64}
            paths = self.evidence_paths(action, data)
            event["evidence_hashes"] = {path: digest(self.file(path, prefixes=("registry/evidence/",)))
                                        for path in paths}
            event["hash"] = digest(canonical(event))
            result = self.replay(events + [event])
            if not dry_run:
                with self.journal.open("ab") as stream:
                    stream.write(canonical(event) + b"\n")
                    stream.flush()
                    os.fsync(stream.fileno())
            return result[asset_id]
