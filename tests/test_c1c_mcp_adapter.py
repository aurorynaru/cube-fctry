"""C1E-B offline tests for the read-only MCP snapshot adapter.

No test connects to Roblox Studio, calls ComfyUI, uploads an asset, touches the
registry or writes outside a temporary directory. Every transport interaction
is a local mock. The fixtures are synthetic and deliberately small.
"""

from pathlib import Path
import copy
import json
import pickle
import subprocess
import sys
import tempfile
import threading
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tool"))
from c1c_harness import (  # noqa: E402
    build_rig_plan,
    canonical_sha256,
    load_spec,
    registry_fingerprint,
    validate_snapshot,
)
from c1c_mcp_adapter import (  # noqa: E402
    ALLOWED_MCP_TOOLS,
    AUTHORIZATION_FIELDS,
    FORBIDDEN_MCP_TOOLS,
    LUAU_TOOL,
    MAX_AUTHORIZED_OBJECTS,
    MUTATION_ACTIONS,
    READ_ONLY_SNAPSHOT_LUAU,
    STATE_TOOL,
    AuthorizationError,
    AuthorizationExpired,
    AuthorizationMismatch,
    AuthorizationNotYetValid,
    AuthorizationReplay,
    AuthorizationStateError,
    AuthorizationStore,
    AuthorizationStoreAmbiguous,
    AuthorizationStoreCorrupt,
    ConfigurationError,
    DuplicateAuthorization,
    IdentityError,
    LiveRunAuthorization,
    McpAdapterConfig,
    McpAdapterNotImplemented,
    McpStudioAdapter,
    SnapshotIncompleteError,
    SnapshotNormalizationError,
    SnapshotValidationError,
    StudioIdentity,
    ToolPolicyError,
    TransportResponseError,
    TransportUnavailable,
    UnsupportedEnvelopeError,
    decode_mcp_payload,
)


STUDIO_ID = "577768ad-49d8-42f5-ac96-8c66cd12a144"
PLACE = "local-unsaved"
USER_ID = 11822718311
RUN_ID = "c1c-20261017-01"
ASSET_ID = "rbxassetid://112705883084796"
EXAMPLE_SPEC_PATH = "tool/c1c/example-spec.json"
FIXED_NOW = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)
APPROVED_AT = "2026-10-17T23:00:00Z"
EXPIRES_AT = "2026-10-18T01:00:00Z"
CFRAME = [
    -25.210203170776367, 33.48590087890625, -41.345703125,
    -0.8648608326911926, 0.24052149057388306, -0.4406419098377228,
    -0.0, 0.8777521252632141, 0.4791151285171509,
    0.5020118951797485, 0.4143679141998291, -0.7591332793235779,
]
VIEWPORT = [1219, 793]


class RecordingTransport:
    """Deterministic local MCP double. Never contacts Studio."""

    def __init__(self, response=None, failure=None, by_tool=None,
                 fail_tool=None):
        self.response = {"mode": "Edit"} if response is None else response
        self.failure = failure
        self.by_tool = dict(by_tool or {})
        self.fail_tool = fail_tool
        self.calls = []

    def call(self, tool, payload):
        self.calls.append((tool, copy.deepcopy(payload)))
        if self.failure is not None and (
            self.fail_tool is None or self.fail_tool == tool
        ):
            raise self.failure
        if tool in self.by_tool:
            return copy.deepcopy(self.by_tool[tool])
        return copy.deepcopy(self.response)


def identity(**overrides):
    values = {
        "studio_id": STUDIO_ID,
        "place": PLACE,
        "user_id": USER_ID,
        "is_unsaved": True,
        "place_id": 0,
        "game_id": 0,
        "creator_id": 0,
        "creator_type": "User",
        "mode": "edit",
        "team_create": False,
    }
    values.update(overrides)
    return StudioIdentity(**values)


def published_identity(**overrides):
    values = {
        "studio_id": STUDIO_ID,
        "place": "Published Place",
        "user_id": USER_ID,
        "is_unsaved": False,
        "place_id": 123,
        "game_id": 456,
        "creator_id": 789,
        "creator_type": "Group",
        "mode": "edit",
        "team_create": False,
    }
    values.update(overrides)
    return StudioIdentity(**values)


def state_payload(**overrides):
    values = {
        "studio_id": STUDIO_ID,
        "mode": "Edit",
        "place": {
            "name": "Place1",
            "place_id": 0,
            "game_id": 0,
            "creator_id": 0,
            "creator_type": "User",
            "is_unsaved": True,
        },
        "user": {"id": USER_ID, "name": "aurory_naru"},
        "team_create": False,
    }
    values.update(overrides)
    return values


def published_state(**overrides):
    values = {
        "studio_id": STUDIO_ID,
        "mode": "Edit",
        "place": {
            "name": "Published Place",
            "place_id": 123,
            "game_id": 456,
            "creator_id": 789,
            "creator_type": "Group",
            "is_unsaved": False,
        },
        "user": {"id": USER_ID, "name": "aurory_naru"},
        "team_create": False,
    }
    values.update(overrides)
    return values


_EXAMPLE_SPEC_CACHE = {}


def example_spec():
    if "spec" not in _EXAMPLE_SPEC_CACHE:
        spec = load_spec(ROOT, EXAMPLE_SPEC_PATH)
        _EXAMPLE_SPEC_CACHE["spec"] = spec
        _EXAMPLE_SPEC_CACHE["plan"] = build_rig_plan(spec)
        _EXAMPLE_SPEC_CACHE["sha256"] = canonical_sha256(spec.raw)
    return _EXAMPLE_SPEC_CACHE["spec"]


def example_plan():
    example_spec()
    return _EXAMPLE_SPEC_CACHE["plan"]


def example_spec_sha256():
    example_spec()
    return _EXAMPLE_SPEC_CACHE["sha256"]


def required_capture_ids():
    return tuple(
        capture.capture_id
        for capture in example_spec().screenshots
        if capture.required
    )


def authorization(**overrides):
    values = {
        "authorization_id": "c1e-c1-auth-001",
        "one_use_nonce": "nonce-c1e-c1-001",
        "actor": "tester",
        "approved_at": APPROVED_AT,
        "expires_at": EXPIRES_AT,
        "studio_id": STUDIO_ID,
        "place": PLACE,
        "place_id": 0,
        "game_id": 0,
        "creator_id": 0,
        "creator_type": "User",
        "is_unsaved": True,
        "user_id": USER_ID,
        "run_id": RUN_ID,
        "spec_sha256": example_spec_sha256(),
        "asset_id": ASSET_ID,
        "asset_status": "test_only_unapproved",
        "allowed_actions": tuple(sorted(MUTATION_ACTIONS)),
        "max_objects": len(example_plan().objects),
        "evidence_require_durable_files": False,
        "evidence_required_capture_ids": required_capture_ids(),
        "acknowledge_no_save_publish_upload": True,
    }
    values.update(overrides)
    return LiveRunAuthorization(**values)


def config(**overrides):
    values = {
        "studio_id": STUDIO_ID,
        "place": PLACE,
        "run_id": RUN_ID,
        "identity": identity(),
    }
    values.update(overrides)
    return McpAdapterConfig(**values)


def fixed_clock():
    return FIXED_NOW


def new_store(temporary=None, **overrides):
    root = Path(temporary) if temporary is not None else Path(
        tempfile.mkdtemp(prefix="c1e-c1-store-")
    )
    values = {"clock": fixed_clock}
    values.update(overrides)
    return AuthorizationStore(root, **values)


def reserved_store(auth=None, *, store=None):
    auth = authorization() if auth is None else auth
    store = new_store() if store is None else store
    store.reserve(auth, example_spec(), example_plan(), identity())
    return store, auth


def object_node(path, class_name, *, parent=None, children=None,
                attributes=None, tags=None, properties=None):
    if parent is None:
        parent = path.rsplit(".", 1)[0] if "." in path else ""
    return {
        "path": path,
        "name": path.rsplit(".", 1)[-1],
        "class_name": class_name,
        "parent": parent,
        "children": list(children or []),
        "attributes": copy.deepcopy(attributes or {}),
        "tags": list(tags or []),
        "properties": copy.deepcopy(properties or {}),
    }


def camera_payload():
    return {
        "cframe": list(CFRAME),
        "camera_type": "Fixed",
        "viewport": list(VIEWPORT),
    }


def baseline_objects():
    return [
        object_node(
            "Workspace", "Workspace", parent="", children=[
                "Workspace.Camera",
                "Workspace.Baseplate",
                "Workspace.Terrain",
                "Workspace.SpawnLocation",
            ], properties={"StreamingEnabled": True},
        ),
        object_node(
            "Workspace.Camera", "Camera", properties={
                "CFrame": list(CFRAME),
                "CameraType": "Fixed",
                "ViewportSize": list(VIEWPORT),
            },
        ),
        object_node(
            "Workspace.Baseplate", "Part", children=["Workspace.Baseplate.Texture"],
            attributes={"TestAttribute": "value"}, tags=["TestTag"],
            properties={
                "Position": [0, -8, 0], "Size": [2048, 16, 2048],
                "Anchored": True, "CanCollide": True, "Transparency": 0,
                "Material": "Plastic",
            },
        ),
        object_node(
            "Workspace.Baseplate.Texture", "Texture", properties={
                "Texture": "rbxassetid://112705883084796", "Face": "Top",
                "StudsPerTileU": 8, "StudsPerTileV": 8,
                "OffsetStudsU": 0, "OffsetStudsV": 0, "Transparency": 0.8,
            },
        ),
        object_node("Workspace.Terrain", "Terrain"),
        object_node(
            "Workspace.SpawnLocation", "SpawnLocation",
            children=["Workspace.SpawnLocation.Decal"],
            properties={
                "Position": [0, 0.5, 0], "Size": [12, 1, 12],
                "Anchored": True, "CanCollide": True, "Transparency": 0,
            },
        ),
        object_node(
            "Workspace.SpawnLocation.Decal", "Decal", properties={
                "Texture": "rbxasset://textures/SpawnLocation.png",
                "Face": "Top", "Transparency": 0,
            },
        ),
    ]


def snapshot_payload(**overrides):
    objects = baseline_objects()
    value = {
        "complete": True,
        "objects": objects,
        "workspace": {
            "attributes": {},
            "tags": [],
            "children": [
                item["path"] for item in objects
                if item["parent"] == "Workspace"
            ],
        },
        "selection": ["Workspace.Baseplate"],
        "camera": camera_payload(),
        "tagged": {"TestTag": ["Workspace.Baseplate"]},
        "enumeration": {
            "root": "Workspace",
            "visited": [item["path"] for item in objects],
            "descendant_count": len(objects) - 1,
            "truncated": False,
            "max_depth": 2,
        },
    }
    value.update(overrides)
    return value


def find(objects, path):
    for item in objects:
        if item["path"] == path:
            return item
    raise AssertionError(f"fixture path not found: {path}")


def sync_enumeration(payload):
    paths = [item["path"] for item in payload["objects"]]
    payload["enumeration"]["visited"] = list(paths)
    payload["enumeration"]["descendant_count"] = len(paths) - 1
    return payload


def make_adapter(state=None, snapshot=None, **config_overrides):
    state = state_payload() if state is None else state
    snapshot = snapshot_payload() if snapshot is None else snapshot
    transport = RecordingTransport(by_tool={
        STATE_TOOL: state,
        LUAU_TOOL: snapshot,
    })
    adapter = McpStudioAdapter(config(**config_overrides), transport)
    return adapter, transport


def mutation_calls(adapter):
    return {
        "create_folder": lambda: adapter.create_folder("C1C_TextureTest_x", {}, []),
        "create_part": lambda: adapter.create_part(
            "Workspace.C1C_TextureTest_x", "C1C_Panel", {}, [], {}),
        "create_texture": lambda: adapter.create_texture(
            "Workspace.C1C_TextureTest_x.C1C_Panel", "C1C_Texture", {}, [], {}),
        "create_label": lambda: adapter.create_label(
            "Workspace.C1C_TextureTest_x", "C1C_Label", "text", {}, [], {}),
        "preload": lambda: adapter.preload(
            "rbxassetid://112705883084796", []),
        "set_camera": lambda: adapter.set_camera(None),
        "rename": lambda: adapter.rename("Workspace.C1C_TextureTest_x", "C1C_Other"),
        "destroy": lambda: adapter.destroy("Workspace.C1C_TextureTest_x"),
        "screenshot": lambda: adapter.screenshot("capture-1", None),
    }


class InitializationTests(unittest.TestCase):
    def test_construction_is_offline_and_declares_not_simulated(self):
        transport = RecordingTransport()
        adapter = McpStudioAdapter(config(), transport)

        self.assertFalse(adapter.simulates_studio)
        self.assertFalse(adapter.supports_viewport_restore)
        self.assertEqual("mcp-c1c-skeleton", adapter.name)
        self.assertEqual([], transport.calls)

    def test_construction_creates_no_files_and_makes_no_studio_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            transport = RecordingTransport()
            McpStudioAdapter(config(authorization=authorization()), transport)

            self.assertEqual([], list(root.iterdir()))
            self.assertEqual([], transport.calls)

    def test_missing_studio_id_is_rejected(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    McpAdapterConfig(studio_id=value, place=PLACE)

    def test_missing_place_is_rejected(self):
        for value in ("", "   ", None):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    McpAdapterConfig(studio_id=STUDIO_ID, place=value)

    def test_non_edit_mode_is_rejected(self):
        for value in ("Play", "Server", "", None):
            with self.subTest(value=value):
                with self.assertRaises(ConfigurationError):
                    McpAdapterConfig(studio_id=STUDIO_ID, place=PLACE, mode=value)

    def test_identity_must_match_the_configuration(self):
        for field, value in (
            ("studio_id", "00000000-0000-0000-0000-000000000000"),
            ("place", "some-other-place"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(ConfigurationError):
                    config(identity=identity(**{field: value}))

    def test_identity_rejects_invalid_or_contradictory_fields(self):
        cases = (
            {"user_id": 0},
            {"creator_type": "Team"},
            {"mode": "Play"},
            {"team_create": True},
            {"is_unsaved": True, "place_id": 1},
            {"is_unsaved": True, "game_id": 1},
            {"is_unsaved": False, "place_id": 0},
            {"is_unsaved": False, "place_id": 1, "game_id": 1, "creator_id": 0},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                with self.assertRaises(ConfigurationError):
                    identity(**overrides)

    def test_identity_place_kind_distinguishes_local_and_published(self):
        self.assertEqual("unsaved_local", identity().place_kind)
        self.assertEqual("published", published_identity().place_kind)
        self.assertEqual(
            "saved_unpublished",
            identity(
                place="Saved Place", is_unsaved=False,
                place_id=123, game_id=0, creator_id=789,
            ).place_kind,
        )

    def test_authorization_identity_mismatch_is_rejected(self):
        for field, value in (
            ("studio_id", "00000000-0000-0000-0000-000000000000"),
            ("place", "some-other-place"),
            ("run_id", "another-run"),
        ):
            with self.subTest(field=field):
                with self.assertRaises(AuthorizationError):
                    config(authorization=authorization(**{field: value}))

    def test_authorization_requires_no_save_publish_upload_acknowledgement(self):
        for value in (False, None, 1):
            with self.subTest(value=value):
                with self.assertRaises(AuthorizationError):
                    authorization(acknowledge_no_save_publish_upload=value)

    def test_authorization_requires_known_actions(self):
        with self.assertRaises(AuthorizationError):
            authorization(allowed_actions=())
        with self.assertRaises(AuthorizationError):
            authorization(allowed_actions=("create", "publish"))
        with self.assertRaises(ConfigurationError):
            authorization(allowed_actions="create")

    def test_authorization_requires_a_run_id_in_configuration(self):
        with self.assertRaises(ConfigurationError):
            config(run_id=None, authorization=authorization())

    def test_injected_transport_must_be_callable(self):
        with self.assertRaises(ConfigurationError):
            McpStudioAdapter(config(), transport=object())

    def test_default_transport_fails_closed(self):
        adapter = McpStudioAdapter(config())
        with self.assertRaises(TransportUnavailable):
            adapter.read_studio_state()
        with self.assertRaises(TransportUnavailable):
            adapter.read_verified_identity()

    def test_snapshot_without_an_explicit_identity_is_rejected(self):
        transport = RecordingTransport(by_tool={
            STATE_TOOL: state_payload(),
            LUAU_TOOL: snapshot_payload(),
        })
        adapter = McpStudioAdapter(config(identity=None), transport)
        with self.assertRaises(ConfigurationError):
            adapter.snapshot()
        self.assertEqual([], transport.calls)


class ToolPolicyTests(unittest.TestCase):
    def test_documented_tools_are_allowed(self):
        self.assertEqual(
            tuple(sorted(ALLOWED_MCP_TOOLS)),
            tuple(sorted(McpStudioAdapter.assert_tool_policy(ALLOWED_MCP_TOOLS))),
        )

    def test_unknown_tool_is_rejected(self):
        for tool in ("", "roblox_studio_save", "roblox_studio_publish", "anything"):
            with self.subTest(tool=tool):
                with self.assertRaises(ToolPolicyError):
                    McpStudioAdapter.assert_tool_policy((tool,))

    def test_forbidden_tools_are_rejected(self):
        for tool in FORBIDDEN_MCP_TOOLS:
            with self.subTest(tool=tool):
                with self.assertRaises(ToolPolicyError):
                    McpStudioAdapter.assert_tool_policy((tool,))

    def test_adapter_has_no_upload_save_or_publish_surface(self):
        adapter = McpStudioAdapter(config())
        for name in ("upload", "upload_asset", "insert_asset", "save",
                     "save_place", "publish", "publish_place"):
            with self.subTest(name=name):
                self.assertFalse(hasattr(adapter, name))

    def test_read_studio_state_uses_the_allowlisted_tool_deterministically(self):
        transport = RecordingTransport({"mode": "Edit", "datamodel": "Edit"})
        adapter = McpStudioAdapter(config(), transport)

        first = adapter.read_studio_state()
        second = adapter.read_studio_state()
        first["mode"] = "mutated by caller"

        self.assertEqual({"mode": "Edit", "datamodel": "Edit"}, second)
        self.assertEqual(
            [
                (STATE_TOOL, {"studio_id": STUDIO_ID}),
                (STATE_TOOL, {"studio_id": STUDIO_ID}),
            ],
            transport.calls,
        )

    def test_read_studio_state_rejects_a_non_mapping_response(self):
        adapter = McpStudioAdapter(config(), RecordingTransport(["not", "a", "mapping"]))
        with self.assertRaises(TransportResponseError):
            adapter.read_studio_state()

    def test_transport_failure_propagates(self):
        adapter = McpStudioAdapter(
            config(), RecordingTransport(failure=RuntimeError("transport down")))
        with self.assertRaisesRegex(RuntimeError, "transport down"):
            adapter.read_studio_state()

    def test_fixed_luau_source_is_read_only_and_not_interpolated(self):
        self.assertTrue(READ_ONLY_SNAPSHOT_LUAU)
        for forbidden in (
            STUDIO_ID, RUN_ID, PLACE, str(USER_ID),
        ):
            with self.subTest(value=forbidden):
                self.assertNotIn(forbidden, READ_ONLY_SNAPSHOT_LUAU)
        for mutation in (
            "Destroy(", ":Destroy", "Clone(", "Instance.new",
            "SetAttribute", "AddTag", "RemoveTag", "Parent =",
            "PivotTo", "SetPrimaryPartCFrame", "ClearAllChildren",
            "Selection:Set", "Remove(", "::",
        ):
            with self.subTest(mutation=mutation):
                self.assertNotIn(mutation, READ_ONLY_SNAPSHOT_LUAU)
        for read_only in ("GetChildren", "GetTags", "GetAttributes", "CurrentCamera"):
            with self.subTest(read_only=read_only):
                self.assertIn(read_only, READ_ONLY_SNAPSHOT_LUAU)


class IdentityValidationTests(unittest.TestCase):
    def test_correct_target_identity_is_accepted(self):
        adapter, transport = make_adapter()
        verified = adapter.read_verified_identity()

        self.assertEqual(STUDIO_ID, verified.studio_id)
        self.assertEqual(PLACE, verified.place)
        self.assertEqual("unsaved_local", verified.place_kind)
        self.assertEqual(0, verified.place_id)
        self.assertEqual(0, verified.game_id)
        self.assertEqual(0, verified.creator_id)
        self.assertEqual("user", verified.creator_type)
        self.assertEqual(USER_ID, verified.user_id)
        self.assertEqual("aurory_naru", verified.user_name)
        self.assertEqual([(STATE_TOOL, {"studio_id": STUDIO_ID})], transport.calls)

    def test_published_place_identity_is_distinguished_from_unsaved(self):
        expected = published_identity()
        transport = RecordingTransport(by_tool={
            STATE_TOOL: published_state(),
        })
        adapter = McpStudioAdapter(
            McpAdapterConfig(
                studio_id=STUDIO_ID, place="Published Place", identity=expected
            ),
            transport,
        )

        verified = adapter.read_verified_identity()
        self.assertEqual("published", verified.place_kind)
        self.assertEqual("Published Place", verified.place)
        self.assertFalse(verified.is_unsaved)

    def test_saved_unpublished_place_is_not_called_published(self):
        expected = published_identity(game_id=0)
        state = published_state()
        state["place"]["game_id"] = 0
        transport = RecordingTransport(by_tool={STATE_TOOL: state})
        adapter = McpStudioAdapter(
            McpAdapterConfig(
                studio_id=STUDIO_ID, place="Published Place", identity=expected
            ),
            transport,
        )

        verified = adapter.read_verified_identity()
        self.assertEqual("saved_unpublished", verified.place_kind)

    def test_wrong_studio_id_is_rejected_before_the_hierarchy_query(self):
        adapter, transport = make_adapter(
            state=state_payload(studio_id="00000000-0000-0000-0000-000000000000")
        )
        with self.assertRaises(IdentityError):
            adapter.snapshot()
        self.assertEqual([STATE_TOOL], [call[0] for call in transport.calls])

    def test_missing_studio_id_is_rejected(self):
        state = state_payload()
        del state["studio_id"]
        adapter, _ = make_adapter(state=state)
        with self.assertRaises(IdentityError):
            adapter.snapshot()

    def test_wrong_place_label_is_rejected(self):
        expected = published_identity(place="Expected Place")
        state = published_state()
        state["place"]["name"] = "Other Place"
        transport = RecordingTransport(by_tool={
            STATE_TOOL: state,
            LUAU_TOOL: snapshot_payload(),
        })
        adapter = McpStudioAdapter(
            McpAdapterConfig(
                studio_id=STUDIO_ID, place="Expected Place", identity=expected
            ),
            transport,
        )
        with self.assertRaises(IdentityError):
            adapter.snapshot()

    def test_wrong_place_id_is_rejected(self):
        expected = published_identity()
        state = published_state()
        state["place"]["place_id"] = 124
        transport = RecordingTransport(by_tool={STATE_TOOL: state})
        adapter = McpStudioAdapter(
            McpAdapterConfig(
                studio_id=STUDIO_ID, place="Published Place", identity=expected
            ),
            transport,
        )
        with self.assertRaises(IdentityError):
            adapter.read_verified_identity()

    def test_wrong_game_id_is_rejected(self):
        expected = published_identity()
        state = published_state()
        state["place"]["game_id"] = 457
        transport = RecordingTransport(by_tool={STATE_TOOL: state})
        adapter = McpStudioAdapter(
            McpAdapterConfig(
                studio_id=STUDIO_ID, place="Published Place", identity=expected
            ),
            transport,
        )
        with self.assertRaises(IdentityError):
            adapter.read_verified_identity()

    def test_wrong_creator_identity_is_rejected(self):
        expected = published_identity()
        for field, value in (("creator_id", 790), ("creator_type", "User")):
            with self.subTest(field=field):
                state = published_state()
                state["place"][field] = value
                transport = RecordingTransport(by_tool={STATE_TOOL: state})
                adapter = McpStudioAdapter(
                    McpAdapterConfig(
                        studio_id=STUDIO_ID, place="Published Place",
                        identity=expected,
                    ),
                    transport,
                )
                with self.assertRaises(IdentityError):
                    adapter.read_verified_identity()

    def test_wrong_signed_in_user_is_rejected(self):
        state = state_payload()
        state["user"]["id"] = USER_ID + 1
        adapter, _ = make_adapter(state=state)
        with self.assertRaises(IdentityError):
            adapter.read_verified_identity()

    def test_malformed_state_responses_are_rejected(self):
        cases = (
            (["not", "a", "mapping"], TransportResponseError),
            (state_payload(place="not-a-mapping"), IdentityError),
            (state_payload(place={"name": "Place1"}), IdentityError),
        )
        for response, expected_error in cases:
            with self.subTest(response=response):
                adapter, _ = make_adapter(state=response)
                with self.assertRaises(expected_error):
                    adapter.read_verified_identity()
        for field, value in (("place_id", "0"), ("game_id", -1),
                             ("is_unsaved", "true")):
            with self.subTest(field=field):
                state = state_payload()
                state["place"][field] = value
                adapter, _ = make_adapter(state=state)
                with self.assertRaises(IdentityError):
                    adapter.read_verified_identity()

    def test_contradictory_saved_state_is_rejected(self):
        cases = (
            {"is_unsaved": True, "place_id": 5},
            {"is_unsaved": True, "game_id": 5},
            {"is_unsaved": False, "place_id": 0},
        )
        for overrides in cases:
            with self.subTest(overrides=overrides):
                state = state_payload()
                state["place"].update(overrides)
                adapter, _ = make_adapter(state=state)
                with self.assertRaises(IdentityError):
                    adapter.read_verified_identity()

    def test_team_create_and_non_edit_state_are_rejected(self):
        cases = (
            (state_payload(team_create=True), "Team Create"),
            (state_payload(mode="Play"), "Edit"),
        )
        for state, label in cases:
            with self.subTest(label=label):
                adapter, _ = make_adapter(state=state)
                with self.assertRaises(IdentityError):
                    adapter.read_verified_identity()

    def test_unknown_state_response_envelope_is_rejected(self):
        adapter, _ = make_adapter(state={"result": state_payload()})
        with self.assertRaises(UnsupportedEnvelopeError):
            adapter.read_verified_identity()

    def test_mcp_text_envelope_is_supported(self):
        envelope = {
            "content": [{
                "type": "text",
                "text": json.dumps(state_payload()),
            }]
        }
        transport = RecordingTransport(by_tool={
            STATE_TOOL: envelope,
            LUAU_TOOL: snapshot_payload(),
        })
        adapter = McpStudioAdapter(config(), transport)

        verified = adapter.read_verified_identity()
        self.assertEqual(STUDIO_ID, verified.studio_id)
        self.assertTrue(validate_snapshot(adapter.snapshot())["ok"])


class SnapshotNormalizationTests(unittest.TestCase):
    def test_valid_complete_hierarchy_is_normalized(self):
        adapter, transport = make_adapter()
        snapshot = adapter.snapshot()

        integrity = validate_snapshot(snapshot)
        self.assertTrue(integrity["ok"], integrity["issues"])
        self.assertTrue(integrity["complete"])
        self.assertEqual(7, integrity["object_count"])
        self.assertEqual("mcp-c1c-skeleton", snapshot["adapter"])
        self.assertEqual({
            "studio_id": STUDIO_ID,
            "place": PLACE,
            "mode": "Edit",
            "team_create": False,
        }, snapshot["studio"])
        self.assertEqual(
            ["Workspace.Camera", "Workspace.Baseplate",
             "Workspace.Terrain", "Workspace.SpawnLocation"],
            snapshot["workspace"]["children"],
        )
        self.assertEqual(["TestTag"], list(snapshot["tagged"]))
        self.assertEqual(["Workspace.Baseplate"],
                         snapshot["tagged"]["TestTag"])
        self.assertEqual("value",
                         snapshot["objects"]["Workspace.Baseplate"]["attributes"]["TestAttribute"])
        self.assertEqual(["Workspace.Baseplate"], snapshot["selection"])
        self.assertEqual(list(CFRAME), snapshot["camera"]["cframe"])
        self.assertEqual("Fixed", snapshot["camera"]["camera_type"])
        self.assertEqual(list(VIEWPORT), snapshot["camera"]["viewport"])
        self.assertEqual([STATE_TOOL, LUAU_TOOL],
                         [call[0] for call in transport.calls])
        self.assertEqual({"studio_id": STUDIO_ID}, transport.calls[0][1])
        self.assertEqual({
            "studio_id": STUDIO_ID,
            "datamodel_type": "Edit",
            "code": READ_ONLY_SNAPSHOT_LUAU,
        }, transport.calls[1][1])

    def test_mcp_text_envelope_snapshot_is_supported(self):
        envelope = {
            "content": [{
                "type": "text",
                "text": json.dumps(snapshot_payload()),
            }]
        }
        adapter, _ = make_adapter(snapshot=envelope)
        snapshot = adapter.snapshot()
        self.assertTrue(validate_snapshot(snapshot)["ok"])

    def test_missing_descendant_is_rejected(self):
        payload = snapshot_payload()
        payload["objects"] = [
            item for item in payload["objects"]
            if item["path"] not in ("Workspace.Baseplate",
                                    "Workspace.Baseplate.Texture")
        ]
        sync_enumeration(payload)
        payload["workspace"]["children"] = [
            "Workspace.Camera", "Workspace.Baseplate",
            "Workspace.Terrain", "Workspace.SpawnLocation",
        ]
        find(payload["objects"], "Workspace")["children"] = [
            "Workspace.Camera", "Workspace.Baseplate",
            "Workspace.Terrain", "Workspace.SpawnLocation",
        ]
        payload["tagged"] = {}
        adapter, _ = make_adapter(snapshot=payload)

        with self.assertRaises(SnapshotValidationError):
            adapter.snapshot()

    def test_enumeration_omission_is_rejected(self):
        payload = snapshot_payload()
        payload["enumeration"]["visited"].remove("Workspace.Baseplate")
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotIncompleteError):
            adapter.snapshot()

    def test_orphaned_child_is_rejected(self):
        payload = snapshot_payload()
        payload["objects"].append(object_node(
            "Missing.Orphan", "Part", parent="Missing",
        ))
        sync_enumeration(payload)
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotValidationError):
            adapter.snapshot()

    def test_invalid_parent_path_is_rejected(self):
        payload = snapshot_payload()
        find(payload["objects"], "Workspace.Baseplate")["parent"] = \
            "Workspace.SpawnLocation"
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotValidationError):
            adapter.snapshot()

    def test_duplicate_object_path_is_rejected(self):
        payload = snapshot_payload()
        payload["objects"].append(copy.deepcopy(
            find(payload["objects"], "Workspace.Baseplate")))
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotNormalizationError):
            adapter.snapshot()

    def test_invalid_attributes_are_rejected(self):
        cases = ("missing", "not_a_mapping", "non_json", "non_string_key")
        for case in cases:
            with self.subTest(case=case):
                payload = snapshot_payload()
                node = find(payload["objects"], "Workspace.Baseplate")
                if case == "missing":
                    del node["attributes"]
                elif case == "not_a_mapping":
                    node["attributes"] = []
                elif case == "non_json":
                    node["attributes"] = {"bad": object()}
                else:
                    node["attributes"] = {1: "bad"}
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_invalid_tags_and_tag_index_are_rejected(self):
        cases = ("duplicate", "empty", "tagged_missing", "tagged_extra",
                 "workspace_mismatch")
        for case in cases:
            with self.subTest(case=case):
                payload = snapshot_payload()
                node = find(payload["objects"], "Workspace.Baseplate")
                if case == "duplicate":
                    node["tags"] = ["TestTag", "TestTag"]
                elif case == "empty":
                    node["tags"] = [""]
                elif case == "tagged_missing":
                    payload["tagged"] = {}
                elif case == "tagged_extra":
                    payload["tagged"]["ExtraTag"] = ["Workspace.Terrain"]
                else:
                    payload["workspace"]["tags"] = ["OtherTag"]
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_invalid_camera_cframe_is_rejected(self):
        cases = (
            list(CFRAME[:-1]),
            list(CFRAME[:-1]) + ["not-a-number"],
            list(CFRAME[:-1]) + [float("nan")],
        )
        for cframe in cases:
            with self.subTest(cframe=cframe):
                payload = snapshot_payload()
                payload["camera"]["cframe"] = cframe
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_missing_or_invalid_viewport_is_rejected(self):
        cases = ("missing", "short", "zero", "string")
        for case in cases:
            with self.subTest(case=case):
                payload = snapshot_payload()
                if case == "missing":
                    del payload["camera"]["viewport"]
                elif case == "short":
                    payload["camera"]["viewport"] = [1219]
                elif case == "zero":
                    payload["camera"]["viewport"] = [0, 793]
                else:
                    payload["camera"]["viewport"] = ["1219", 793]
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_missing_camera_type_is_rejected(self):
        payload = snapshot_payload()
        payload["camera"]["camera_type"] = ""
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotNormalizationError):
            adapter.snapshot()

    def test_camera_object_must_agree_with_camera_state(self):
        payload = snapshot_payload()
        find(payload["objects"], "Workspace.Camera")["properties"]["CFrame"] = \
            [0] * 12
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotNormalizationError):
            adapter.snapshot()

    def test_missing_or_contradictory_completeness_is_rejected(self):
        cases = (
            ("missing_complete", SnapshotIncompleteError),
            ("complete_false", SnapshotIncompleteError),
            ("complete_not_bool", SnapshotNormalizationError),
            ("missing_enumeration", SnapshotIncompleteError),
            ("truncated", SnapshotIncompleteError),
            ("truncated_not_bool", SnapshotNormalizationError),
            ("count_mismatch", SnapshotIncompleteError),
            ("visited_missing", SnapshotIncompleteError),
            ("visited_duplicate", SnapshotNormalizationError),
            ("depth_too_small", SnapshotIncompleteError),
            ("root_wrong", SnapshotNormalizationError),
        )
        for case, expected_error in cases:
            with self.subTest(case=case):
                payload = snapshot_payload()
                if case == "missing_complete":
                    del payload["complete"]
                elif case == "complete_false":
                    payload["complete"] = False
                elif case == "complete_not_bool":
                    payload["complete"] = 1
                elif case == "missing_enumeration":
                    del payload["enumeration"]
                elif case == "truncated":
                    payload["enumeration"]["truncated"] = True
                elif case == "truncated_not_bool":
                    payload["enumeration"]["truncated"] = "false"
                elif case == "count_mismatch":
                    payload["enumeration"]["descendant_count"] = 99
                elif case == "visited_missing":
                    payload["enumeration"]["visited"].remove(
                        "Workspace.SpawnLocation")
                elif case == "visited_duplicate":
                    payload["enumeration"]["visited"].append("Workspace")
                elif case == "depth_too_small":
                    payload["enumeration"]["max_depth"] = 0
                else:
                    payload["enumeration"]["root"] = "DataModel"
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(expected_error):
                    adapter.snapshot()

    def test_workspace_summary_must_match_the_workspace_node(self):
        cases = ("attributes", "children")
        for case in cases:
            with self.subTest(case=case):
                payload = snapshot_payload()
                if case == "attributes":
                    payload["workspace"]["attributes"] = {"Other": True}
                else:
                    payload["workspace"]["children"] = ["Workspace.Camera"]
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_invalid_selection_is_rejected(self):
        for selection in ([1], "Workspace.Baseplate",
                          ["Workspace.Baseplate", "Workspace.Baseplate"]):
            with self.subTest(selection=selection):
                payload = snapshot_payload()
                payload["selection"] = selection
                adapter, _ = make_adapter(snapshot=payload)
                with self.assertRaises(SnapshotNormalizationError):
                    adapter.snapshot()

    def test_unknown_snapshot_response_envelope_is_rejected(self):
        cases = (
            {"result": snapshot_payload()},
            {"content": [{"type": "text", "text": "{}", "extra": True}]},
            {"content": [
                {"type": "text", "text": "{}"},
                {"type": "text", "text": "{}"},
            ]},
        )
        for response in cases:
            with self.subTest(response=response):
                adapter, _ = make_adapter(snapshot=response)
                with self.assertRaises(UnsupportedEnvelopeError):
                    adapter.snapshot()

    def test_invalid_json_in_a_text_block_is_rejected(self):
        adapter, _ = make_adapter(snapshot={
            "content": [{"type": "text", "text": "{not json"}],
        })
        with self.assertRaises(TransportResponseError):
            adapter.snapshot()

    def test_unknown_snapshot_payload_keys_are_rejected(self):
        payload = snapshot_payload()
        payload["unexpected"] = True
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(UnsupportedEnvelopeError):
            adapter.snapshot()

    def test_transport_failure_during_identity_or_snapshot_is_rejected(self):
        state_failure = RecordingTransport(failure=RuntimeError("state down"))
        adapter = McpStudioAdapter(config(), state_failure)
        with self.assertRaisesRegex(RuntimeError, "state down"):
            adapter.snapshot()
        self.assertEqual([STATE_TOOL], [call[0] for call in state_failure.calls])

        luau_failure = RecordingTransport(
            failure=RuntimeError("luau down"), fail_tool=LUAU_TOOL,
            by_tool={STATE_TOOL: state_payload()},
        )
        adapter = McpStudioAdapter(config(), luau_failure)
        with self.assertRaisesRegex(RuntimeError, "luau down"):
            adapter.snapshot()
        self.assertEqual([STATE_TOOL, LUAU_TOOL],
                         [call[0] for call in luau_failure.calls])

    def test_snapshot_works_without_mutation_authorization(self):
        adapter, _ = make_adapter()
        self.assertIsNone(adapter.config.authorization)
        self.assertTrue(validate_snapshot(adapter.snapshot())["ok"])
        with self.assertRaises(AuthorizationError):
            adapter.create_folder("C1C_TextureTest_x", {}, [])

    def test_snapshot_has_no_filesystem_or_mutation_side_effects(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            before = sorted(root.iterdir())
            adapter, transport = make_adapter()
            adapter.snapshot()
            self.assertEqual(before, sorted(root.iterdir()))

        self.assertEqual([STATE_TOOL, LUAU_TOOL],
                         [call[0] for call in transport.calls])
        for tool, _ in transport.calls:
            self.assertIn(tool, ALLOWED_MCP_TOOLS)
            self.assertNotIn(tool, FORBIDDEN_MCP_TOOLS)


class OfflinePreflightTests(unittest.TestCase):
    """Synthetic contract checks, never evidence of real-server compatibility."""

    @staticmethod
    def text_envelope(payload):
        return {"content": [{"type": "text", "text": json.dumps(payload)}]}

    def test_both_existing_envelopes_pass_the_entire_snapshot_pipeline(self):
        for wrap in (copy.deepcopy, self.text_envelope):
            with self.subTest(wrapper=wrap):
                adapter, transport = make_adapter(
                    state=wrap(state_payload()), snapshot=wrap(snapshot_payload()),
                )
                self.assertTrue(validate_snapshot(adapter.snapshot())["ok"])
                self.assertEqual([STATE_TOOL, LUAU_TOOL],
                                 [tool for tool, _ in transport.calls])

    def test_ambiguous_and_nonfinite_json_is_rejected_before_identity(self):
        valid = json.dumps(state_payload())
        texts = [
            '{"studio_id":"wrong",' + valid[1:],
            valid.replace('"place_id": 0', '"place_id": 1, "place_id": 0'),
            valid.replace('"creator_id": 0', '"creator_id": NaN'),
            valid.replace('"creator_id": 0', '"creator_id": Infinity'),
            valid.replace('"creator_id": 0', '"creator_id": -Infinity'),
            valid.replace('"creator_id": 0', '"creator_id": 1e999'),
        ]
        for text in texts:
            with self.subTest(text=text):
                adapter, transport = make_adapter(state={
                    "content": [{"type": "text", "text": text}],
                })
                with self.assertRaises(TransportResponseError):
                    adapter.snapshot()
                self.assertEqual([STATE_TOOL], [tool for tool, _ in transport.calls])

    def test_existing_unknown_wrapper_shapes_remain_rejected(self):
        # Negative variations of existing internal fixtures, not observed wrappers.
        for response in (
            {"result": state_payload()},
            {"error": "synthetic error"},
            {"content": []},
            {"content": [{"type": "text", "text": "{}"},
                         {"type": "text", "text": "{}"}]},
            {"content": [{"type": "text", "text": "{}", "extra": True}]},
        ):
            with self.subTest(response=response):
                with self.assertRaises(UnsupportedEnvelopeError):
                    decode_mcp_payload(response)

    def test_missing_camera_is_rejected_without_repair(self):
        for omitted in (False, True):
            with self.subTest(omitted=omitted):
                payload = snapshot_payload(camera=None)
                if omitted:
                    del payload["camera"]
                adapter, transport = make_adapter(snapshot=payload)
                with self.assertRaises((SnapshotNormalizationError,
                                        UnsupportedEnvelopeError)):
                    adapter.snapshot()
                self.assertEqual([STATE_TOOL, LUAU_TOOL],
                                 [tool for tool, _ in transport.calls])

    def test_dotted_name_with_query_derived_parent_is_rejected(self):
        payload = snapshot_payload()
        path = "Workspace.Odd.Name"
        payload["objects"].append(object_node(path, "Folder"))
        payload["objects"][-1]["name"] = "Odd.Name"
        find(payload["objects"], "Workspace")["children"].append(path)
        payload["workspace"]["children"].append(path)
        sync_enumeration(payload)
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(SnapshotValidationError):
            adapter.snapshot()

    def test_continuity_gap_hierarchy_has_no_independently_observed_identity(self):
        # Characterize the blocker honestly: a structurally valid hierarchy
        # from an unknown origin is accepted and stamped with the earlier state.
        payload = snapshot_payload()
        self.assertNotIn("studio_id", payload)
        self.assertNotIn("place_id", payload)
        adapter, _ = make_adapter(snapshot=payload)
        self.assertEqual(STUDIO_ID, adapter.snapshot()["studio"]["studio_id"])
        # Adding a caller identity echo is not a supported continuity solution.
        payload["studio_id"] = STUDIO_ID
        adapter, _ = make_adapter(snapshot=payload)
        with self.assertRaises(UnsupportedEnvelopeError):
            adapter.snapshot()


class MutationBlockingTests(unittest.TestCase):
    def test_every_mutation_is_blocked_without_authorization(self):
        transport = RecordingTransport()
        adapter = McpStudioAdapter(config(), transport)

        for name, call in mutation_calls(adapter).items():
            with self.subTest(operation=name):
                with self.assertRaises(AuthorizationError):
                    call()
        self.assertEqual([], transport.calls)

    def test_authorized_mutations_are_still_explicitly_unimplemented(self):
        transport = RecordingTransport()
        adapter = McpStudioAdapter(config(authorization=authorization()), transport)

        for name, call in mutation_calls(adapter).items():
            with self.subTest(operation=name):
                with self.assertRaises(McpAdapterNotImplemented):
                    call()
        self.assertEqual([], transport.calls)

    def test_action_not_granted_by_authorization_is_rejected(self):
        adapter = McpStudioAdapter(
            config(authorization=authorization(allowed_actions=("create",))),
            RecordingTransport(),
        )

        with self.assertRaises(McpAdapterNotImplemented):
            adapter.create_folder("C1C_TextureTest_x", {}, [])
        with self.assertRaises(AuthorizationError):
            adapter.destroy("Workspace.C1C_TextureTest_x")

    def test_viewport_restore_is_reported_unsupported_without_mutation(self):
        transport = RecordingTransport()
        adapter = McpStudioAdapter(config(), transport)
        self.assertFalse(adapter.set_viewport_size(800, 600))
        self.assertEqual([], transport.calls)

    def test_protocol_surface_is_present(self):
        adapter = McpStudioAdapter(config())
        for name in (
            "snapshot", "create_folder", "create_part", "create_texture",
            "create_label", "preload", "set_camera", "set_viewport_size",
            "rename", "destroy", "screenshot",
        ):
            with self.subTest(name=name):
                self.assertTrue(callable(getattr(adapter, name, None)))


class AuthorizationContractTests(unittest.TestCase):
    def test_valid_authorization_is_accepted_and_covers_actions(self):
        auth = authorization()
        self.assertEqual(RUN_ID, auth.run_id)
        self.assertEqual(example_spec_sha256(), auth.spec_sha256)
        self.assertEqual(ASSET_ID, auth.asset_id)
        for action in MUTATION_ACTIONS:
            self.assertTrue(auth.covers(action))
        self.assertNotIn(auth.one_use_nonce, json.dumps(auth.structural_dict()))

    def test_missing_and_unknown_fields_are_rejected(self):
        data = authorization().to_dict()
        self.assertEqual(set(data), set(AUTHORIZATION_FIELDS))
        self.assertEqual(authorization(), LiveRunAuthorization.from_dict(data))
        for key in sorted(data):
            with self.subTest(missing=key):
                partial = dict(data)
                del partial[key]
                with self.assertRaises(ConfigurationError):
                    LiveRunAuthorization.from_dict(partial)
        extra = dict(data)
        extra["extra_scope"] = "everything"
        with self.assertRaises(ConfigurationError):
            LiveRunAuthorization.from_dict(extra)

    def test_utc_timestamps_are_required_and_z_is_accepted(self):
        for approved, expires in (
            ("2026-10-17T23:00:00Z", "2026-10-18T01:00:00+00:00"),
            ("2026-10-17T23:00:00+00:00", "2026-10-18T01:00:00Z"),
        ):
            with self.subTest(approved=approved):
                auth = authorization(approved_at=approved, expires_at=expires)
                self.assertTrue(auth.approved_at.endswith("+00:00"))
        for approved, expires in (
            ("2026-10-17T23:00:00", "2026-10-18T01:00:00+00:00"),
            ("2026-10-17T23:00:00+02:00", "2026-10-18T01:00:00+00:00"),
        ):
            with self.subTest(approved=approved):
                with self.assertRaises(ConfigurationError):
                    authorization(approved_at=approved, expires_at=expires)

    def test_invalid_or_broad_windows_are_rejected(self):
        with self.assertRaises(AuthorizationError):
            authorization(expires_at=APPROVED_AT)
        with self.assertRaises(AuthorizationError):
            authorization(
                expires_at=(datetime(2026, 10, 19, 0, 0, 0,
                                     tzinfo=timezone.utc)).isoformat()
            )
        with self.assertRaises(AuthorizationError):
            authorization(max_objects=MAX_AUTHORIZED_OBJECTS + 1)

    def test_asset_must_be_pinned_and_test_only(self):
        with self.assertRaises(AuthorizationError):
            authorization(asset_id="rbxassetid://999")
        with self.assertRaises(AuthorizationError):
            authorization(asset_status="approved")
        with self.assertRaises(ConfigurationError):
            authorization(asset_id="112705883084796")

    def test_actions_must_be_known_unique_and_non_empty(self):
        with self.assertRaises(AuthorizationError):
            authorization(allowed_actions=())
        with self.assertRaises(AuthorizationError):
            authorization(allowed_actions=("create", "publish"))
        with self.assertRaises(AuthorizationError):
            authorization(allowed_actions=("create", "create"))
        with self.assertRaises(ConfigurationError):
            authorization(allowed_actions="create")

    def test_acknowledgement_must_be_exactly_true(self):
        for value in (False, None, 1, "true"):
            with self.subTest(value=value):
                with self.assertRaises(AuthorizationError):
                    authorization(acknowledge_no_save_publish_upload=value)

    def test_place_and_creator_identity_is_contradictory_when_unsaved(self):
        with self.assertRaises(AuthorizationError):
            authorization(is_unsaved=True, place_id=1)
        with self.assertRaises(AuthorizationError):
            authorization(is_unsaved=True, game_id=1)
        with self.assertRaises(AuthorizationError):
            authorization(is_unsaved=False, place_id=0)

    def test_spec_binding_rejects_wrong_run_studio_hash_and_evidence(self):
        spec = example_spec()
        plan = example_plan()
        cases = {
            "run": authorization(run_id="other-run"),
            "studio": authorization(
                studio_id="00000000-0000-0000-0000-000000000000"
            ),
            "hash": authorization(spec_sha256="0" * 64),
            "evidence": authorization(
                evidence_required_capture_ids=("not-a-real-capture",)
            ),
            "objects": authorization(max_objects=1),
        }
        for label, auth in cases.items():
            with self.subTest(label=label):
                with self.assertRaises(AuthorizationMismatch):
                    auth.validate_for_spec(spec, plan, identity(), FIXED_NOW)

    def test_spec_binding_rejects_wrong_asset_and_status(self):
        auth = authorization()
        wrong_asset = replace(
            example_spec(),
            asset=replace(example_spec().asset, asset_id="rbxassetid://999"),
        )
        with self.assertRaises(AuthorizationMismatch):
            auth.validate_for_spec(wrong_asset, example_plan(), identity(),
                                   FIXED_NOW)
        wrong_status = replace(
            example_spec(),
            asset=replace(example_spec().asset, status="approved"),
        )
        with self.assertRaises(AuthorizationMismatch):
            auth.validate_for_spec(wrong_status, example_plan(), identity(),
                                   FIXED_NOW)

    def test_spec_binding_rejects_wrong_identity(self):
        auth = authorization()
        with self.assertRaises(AuthorizationMismatch):
            auth.validate_for_spec(
                example_spec(), example_plan(),
                published_identity(), FIXED_NOW,
            )

    def test_future_approval_and_expiry_are_time_checked(self):
        future = authorization(
            approved_at="2026-10-18T01:00:00Z",
            expires_at="2026-10-18T02:00:00Z",
        )
        with self.assertRaises(AuthorizationNotYetValid):
            future.validate_for_spec(
                example_spec(), example_plan(), identity(), FIXED_NOW
            )
        expired = authorization(
            approved_at="2026-10-17T20:00:00Z",
            expires_at="2026-10-17T22:00:00Z",
        )
        with self.assertRaises(AuthorizationExpired):
            expired.validate_for_spec(
                example_spec(), example_plan(), identity(), FIXED_NOW
            )


class AuthorizationStoreLifecycleTests(unittest.TestCase):
    def test_lifecycle_transitions_and_audit_log(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            self.assertEqual("prepared", store.prepare(auth)["state"])
            self.assertEqual(
                "validated",
                store.validate(auth, example_spec(), example_plan(),
                               identity())["state"],
            )
            reserved = store.reserve(
                auth, example_spec(), example_plan(), identity()
            )
            self.assertEqual("reserved", reserved["state"])
            consumed = store.consume(auth, "create")
            self.assertEqual("consumed", consumed["state"])
            self.assertEqual("create", consumed["consumption"]["action"])

            states = [item["state"] for item in consumed["transitions"]]
            self.assertEqual(
                ["prepared", "validated", "reserved", "consumed"], states
            )
            log = store.audit_log()
            self.assertEqual(
                ["prepare", "validate", "reserve", "consume"],
                [item["transition"] for item in log if item["phase"] == "intent"],
            )
            self.assertTrue(all("one_use_nonce" not in item
                                for item in log))

    def test_duplicate_authorization_id_and_nonce_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            store.prepare(authorization())
            with self.assertRaises(DuplicateAuthorization):
                store.prepare(authorization(one_use_nonce="another-nonce"))
            with self.assertRaises(DuplicateAuthorization):
                store.prepare(authorization(authorization_id="other-auth"))

    def test_implicit_prepare_duplicate_nonce_does_not_poison_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            first = authorization()
            store.prepare(first)
            before_state = store.state_path.read_bytes()
            before_journal = store.journal_path.read_bytes()
            duplicate = authorization(authorization_id="other-auth")
            with self.assertRaises(DuplicateAuthorization):
                store.reserve(duplicate, example_spec(), example_plan(), identity())
            self.assertEqual(before_state, store.state_path.read_bytes())
            self.assertEqual(before_journal, store.journal_path.read_bytes())
            self.assertEqual("prepared", store.status(first.authorization_id)["state"])
            self.assertEqual({first.authorization_id}, set(store.statuses()))
            self.assertFalse(store.recover_interrupted()["recovered"])

            valid = authorization(authorization_id="valid-auth",
                                  one_use_nonce="fresh-nonce")
            self.assertEqual("reserved", store.reserve(
                valid, example_spec(), example_plan(), identity()
            )["state"])

    def test_implicit_prepare_duplicate_id_does_not_change_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            first = authorization()
            store.prepare(first)
            before_state = store.state_path.read_bytes()
            before_journal = store.journal_path.read_bytes()
            duplicate_id = authorization(one_use_nonce="different-nonce")
            with self.assertRaises(AuthorizationMismatch):
                store.reserve(duplicate_id, example_spec(), example_plan(), identity())
            self.assertEqual(before_state, store.state_path.read_bytes())
            self.assertEqual(before_journal, store.journal_path.read_bytes())
            self.assertEqual("prepared", store.status(first.authorization_id)["state"])
            self.assertFalse(store.recover_interrupted()["recovered"])

    def test_validation_refusal_after_prepare_leaves_no_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.prepare(auth)
            before = store.state_path.read_bytes(), store.journal_path.read_bytes()
            with self.assertRaises(AuthorizationMismatch):
                store.reserve(auth, replace(example_spec(), run_id="wrong-run"),
                              example_plan(), identity())
            self.assertEqual(before, (store.state_path.read_bytes(),
                                      store.journal_path.read_bytes()))
            self.assertFalse(store.recover_interrupted()["recovered"])
            self.assertEqual("prepared", store.status(auth.authorization_id)["state"])

    def test_nonce_reuse_after_reservation_and_consumption_is_refused(self):
        for consumed in (False, True):
            with self.subTest(consumed=consumed), tempfile.TemporaryDirectory() as temporary:
                store = new_store(temporary)
                original = authorization()
                store.reserve(original, example_spec(), example_plan(), identity())
                if consumed:
                    store.consume(original, "create")
                before = store.state_path.read_bytes(), store.journal_path.read_bytes()
                reuse = authorization(authorization_id="reused-nonce")
                with self.assertRaises(DuplicateAuthorization):
                    store.reserve(reuse, example_spec(), example_plan(), identity())
                self.assertEqual(before, (store.state_path.read_bytes(),
                                          store.journal_path.read_bytes()))
                self.assertEqual("consumed" if consumed else "reserved",
                                 new_store(temporary).status(original.authorization_id)["state"])

    def test_reserve_is_one_use_and_cannot_start_two_runs(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            with self.assertRaises(AuthorizationReplay):
                store.reserve(auth, example_spec(), example_plan(), identity())
            changed_run = authorization(run_id="another-run")
            with self.assertRaises(AuthorizationMismatch):
                store.check_mutation(changed_run, "create")
            self.assertEqual("reserved", store.status(auth.authorization_id)["state"])

    def test_replay_after_consumption_and_restart_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            store.consume(auth, "create")
            with self.assertRaises(AuthorizationReplay):
                store.consume(auth, "create")
            with self.assertRaises(AuthorizationReplay):
                store.reserve(auth, example_spec(), example_plan(), identity())

            restarted = new_store(temporary)
            self.assertEqual(
                "consumed", restarted.status(auth.authorization_id)["state"]
            )
            with self.assertRaises(AuthorizationReplay):
                restarted.reserve(
                    auth, example_spec(), example_plan(), identity()
                )
            with self.assertRaises(AuthorizationReplay):
                restarted.check_mutation(auth, "create")

    def test_replay_after_an_actual_process_restart_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            store.consume(auth, "create")
            payload = root / "restart-payload.pickle"
            payload.write_bytes(pickle.dumps(
                (root, auth, example_spec(), example_plan(), identity())
            ))
            script = """
import pickle
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from c1c_mcp_adapter import AuthorizationReplay, AuthorizationStore
root, auth, spec, plan, identity = pickle.loads(
    Path(sys.argv[2]).read_bytes()
)
store = AuthorizationStore(root)
try:
    store.reserve(auth, spec, plan, identity)
except AuthorizationReplay:
    print("replay-refused")
    raise SystemExit(0)
raise SystemExit(3)
"""
            completed = subprocess.run(
                [sys.executable, "-c", script, str(ROOT / "tool"),
                 str(payload)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(
                0, completed.returncode,
                f"stdout={completed.stdout!r} stderr={completed.stderr!r}",
            )
            self.assertIn("replay-refused", completed.stdout)

    def test_expired_authorization_is_refused_and_recorded(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization(
                approved_at="2026-10-17T20:00:00Z",
                expires_at="2026-10-17T22:00:00Z",
            )
            store.prepare(auth, now=datetime(2026, 10, 17, 21, 0,
                                             tzinfo=timezone.utc))
            with self.assertRaises(AuthorizationExpired):
                store.reserve(
                    auth, example_spec(), example_plan(), identity(),
                    now=FIXED_NOW,
                )
            self.assertEqual(
                "expired", store.status(auth.authorization_id)["state"]
            )
            with self.assertRaises(AuthorizationExpired):
                store.reserve(
                    auth, example_spec(), example_plan(), identity(),
                    now=FIXED_NOW,
                )

    def test_future_approval_is_refused_at_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization(
                approved_at="2026-10-18T01:00:00Z",
                expires_at="2026-10-18T02:00:00Z",
            )
            with self.assertRaises(AuthorizationNotYetValid):
                store.reserve(
                    auth, example_spec(), example_plan(), identity()
                )
            self.assertEqual(
                "prepared", store.status(auth.authorization_id)["state"]
            )

    def test_mismatched_spec_and_identity_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            with self.assertRaises(AuthorizationMismatch):
                store.reserve(
                    auth,
                    replace(example_spec(), run_id="other-run"),
                    example_plan(), identity(),
                )
            with self.assertRaises(AuthorizationMismatch):
                store.reserve(
                    auth, example_spec(), example_plan(), published_identity()
                )
            self.assertEqual(
                "prepared", store.status(auth.authorization_id)["state"]
            )

    def test_action_must_be_granted_by_the_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization(allowed_actions=("create", "camera"),
                                 evidence_required_capture_ids=required_capture_ids())
            # Constructing this record succeeds, but the spec binding rejects
            # it because destroy/screenshot/rename are required.
            store.prepare(auth)
            with self.assertRaises(AuthorizationMismatch):
                store.reserve(
                    auth, example_spec(), example_plan(), identity()
                )

    def test_recovery_grant_is_cleanup_only_and_run_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, auth = reserved_store(store=new_store(temporary))
            before = store.journal_path.read_bytes()
            grant = store.recovery_grant(
                auth.authorization_id, auth.one_use_nonce, RUN_ID
            )
            self.assertNotEqual(before, store.journal_path.read_bytes())
            self.assertEqual("recovery_grant", store.audit_log()[-2]["transition"])
            self.assertEqual("intent", store.audit_log()[-2]["phase"])
            self.assertEqual("applied", store.audit_log()[-1]["phase"])
            self.assertNotIn(auth.one_use_nonce, store.journal_path.read_text())
            self.assertEqual(1, len(store.status(auth.authorization_id)["recovery_grants"]))
            self.assertTrue(grant.allow_cleanup)
            self.assertFalse(grant.allow_new_objects)
            self.assertFalse(grant.allow_new_captures)
            self.assertFalse(grant.allow_uploads)
            self.assertFalse(grant.allow_new_mutations)
            with self.assertRaises(AuthorizationMismatch):
                store.recovery_grant(
                    auth.authorization_id, auth.one_use_nonce, "other-run"
                )
            store.consume(auth, "create")
            grant = store.recovery_grant(
                auth.authorization_id, auth.one_use_nonce, RUN_ID
            )
            self.assertTrue(grant.consumed)
            self.assertFalse(grant.allow_new_mutations)
            self.assertEqual(2, len(store.status(auth.authorization_id)["recovery_grants"]))
            self.assertEqual("recovery_grant", store.audit_log()[-1]["transition"])

    def test_rejected_recovery_grants_do_not_change_store(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, auth = reserved_store(store=new_store(temporary))
            before = (store.state_path.read_bytes(), store.journal_path.read_bytes())
            for nonce, run_id in (("wrong-nonce", RUN_ID),
                                  (auth.one_use_nonce, "wrong-run")):
                with self.subTest(nonce=nonce, run_id=run_id):
                    with self.assertRaises((AuthorizationReplay, AuthorizationMismatch)):
                        store.recovery_grant(auth.authorization_id, nonce, run_id)
                    self.assertEqual(before, (store.state_path.read_bytes(),
                                              store.journal_path.read_bytes()))

    def test_consume_requires_reservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.prepare(auth)
            with self.assertRaises(AuthorizationStateError):
                store.consume(auth, "create")
            store.validate(auth, example_spec(), example_plan(), identity())
            with self.assertRaises(AuthorizationStateError):
                store.consume(auth, "create")


class AuthorizationStoreConcurrencyTests(unittest.TestCase):
    def test_concurrent_reservations_exactly_one_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            auth = authorization()
            barrier = threading.Barrier(8)
            results = []
            lock = threading.Lock()

            def worker():
                store = AuthorizationStore(root, clock=fixed_clock)
                barrier.wait()
                try:
                    store.reserve(
                        auth, example_spec(), example_plan(), identity()
                    )
                    outcome = "reserved"
                except AuthorizationError as exc:
                    outcome = type(exc).__name__
                with lock:
                    results.append(outcome)

            threads = [threading.Thread(target=worker) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(1, results.count("reserved"), results)
            self.assertEqual(
                "reserved",
                AuthorizationStore(root, clock=fixed_clock)
                .status(auth.authorization_id)["state"],
            )

    def test_concurrent_duplicate_nonce_authorizations_only_one_succeeds(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            barrier = threading.Barrier(4)
            results = []
            lock = threading.Lock()

            def worker(index):
                store = AuthorizationStore(root, clock=fixed_clock)
                auth = authorization(
                    authorization_id=f"c1e-c1-auth-{index}",
                    one_use_nonce="shared-nonce-c1e-c1",
                )
                barrier.wait()
                try:
                    store.prepare(auth)
                    outcome = "prepared"
                except AuthorizationError as exc:
                    outcome = type(exc).__name__
                with lock:
                    results.append(outcome)

            threads = [
                threading.Thread(target=worker, args=(index,))
                for index in range(4)
            ]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(1, results.count("prepared"), results)

    def test_concurrent_implicit_duplicate_nonce_reservations_keep_store_usable(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = authorization()
            new_store(temporary).prepare(first)
            before = (root / "state.json").read_bytes(), (root / "journal.jsonl").read_bytes()
            barrier = threading.Barrier(6)
            results = []
            lock = threading.Lock()

            def worker(index):
                store = new_store(temporary)
                duplicate = authorization(authorization_id=f"duplicate-{index}")
                barrier.wait()
                try:
                    store.reserve(duplicate, example_spec(), example_plan(), identity())
                    outcome = "reserved"
                except DuplicateAuthorization:
                    outcome = "duplicate"
                with lock:
                    results.append(outcome)

            threads = [threading.Thread(target=worker, args=(index,))
                       for index in range(6)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=20)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(["duplicate"] * 6, sorted(results))
            store = new_store(temporary)
            self.assertEqual(before, (store.state_path.read_bytes(),
                                      store.journal_path.read_bytes()))
            self.assertEqual("prepared", store.status(first.authorization_id)["state"])
            valid = authorization(authorization_id="valid-after-race",
                                  one_use_nonce="fresh-after-race")
            self.assertEqual("reserved", store.reserve(
                valid, example_spec(), example_plan(), identity()
            )["state"])


class _CrashAfterIntentStore(AuthorizationStore):
    """Test double that crashes after the journal intent is durable."""

    def __init__(self, *args, crash: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.crash = crash

    def _write_state_locked(self, state):
        if self.crash:
            self.crash = False
            raise RuntimeError("simulated crash before state write")
        return super()._write_state_locked(state)


class _CrashAfterStateStore(AuthorizationStore):
    """Test double that crashes after the state write, before applied marker."""

    def __init__(self, *args, crash: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.crash = crash

    def _append_journal_locked(self, record):
        if self.crash and record.get("phase") == "applied":
            self.crash = False
            raise RuntimeError("simulated crash before applied marker")
        return super()._append_journal_locked(record)


class AuthorizationStoreRecoveryTests(unittest.TestCase):
    def test_crash_after_reservation_intent_recovers_without_second_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            auth = authorization()
            store = new_store(temporary)
            store.prepare(auth)
            store.validate(auth, example_spec(), example_plan(), identity())

            crashing = _CrashAfterIntentStore(
                root, clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.reserve(
                    auth, example_spec(), example_plan(), identity()
                )

            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.status(auth.authorization_id)
            recovered = fresh.recover_interrupted()
            self.assertTrue(recovered["recovered"])
            self.assertEqual("reserved", recovered["state"])
            with self.assertRaises(AuthorizationReplay):
                fresh.reserve(
                    auth, example_spec(), example_plan(), identity()
                )
            self.assertEqual(
                "reserved", fresh.status(auth.authorization_id)["state"]
            )

    def test_crash_before_first_state_file_is_recovered_as_prepared(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            auth = authorization()
            crashing = _CrashAfterIntentStore(
                root, clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.prepare(auth)

            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreCorrupt):
                fresh.status(auth.authorization_id)
            recovered = fresh.recover_interrupted()
            self.assertTrue(recovered["recovered"])
            self.assertEqual("prepared", recovered["state"])
            self.assertEqual(
                "prepared", fresh.status(auth.authorization_id)["state"]
            )

    def test_crash_after_state_before_applied_marker_is_recovered(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            auth = authorization()
            store = new_store(temporary)
            store.prepare(auth)
            store.validate(auth, example_spec(), example_plan(), identity())

            crashing = _CrashAfterStateStore(
                root, clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.reserve(
                    auth, example_spec(), example_plan(), identity()
                )

            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.status(auth.authorization_id)
            recovered = fresh.recover_interrupted()
            self.assertTrue(recovered["recovered"])
            self.assertEqual("reserved", recovered["state"])
            with self.assertRaises(AuthorizationReplay):
                fresh.reserve(
                    auth, example_spec(), example_plan(), identity()
                )

    def test_crash_after_consumption_intent_recovery_prevents_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store, auth = reserved_store(store=new_store(temporary))

            crashing = _CrashAfterIntentStore(
                root, clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.consume(auth, "create")

            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.status(auth.authorization_id)
            recovered = fresh.recover_interrupted()
            self.assertEqual("consumed", recovered["state"])
            with self.assertRaises(AuthorizationReplay):
                fresh.consume(auth, "create")
            with self.assertRaises(AuthorizationReplay):
                fresh.reserve(
                    auth, example_spec(), example_plan(), identity()
                )

    def test_crash_during_recovery_grant_is_ambiguous_then_audited(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, auth = reserved_store(store=new_store(temporary))
            crashing = _CrashAfterIntentStore(
                Path(temporary), clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.recovery_grant(auth.authorization_id,
                                        auth.one_use_nonce, RUN_ID)
            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.status(auth.authorization_id)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.recovery_grant(auth.authorization_id,
                                     auth.one_use_nonce, RUN_ID)
            result = fresh.recover_interrupted()
            self.assertTrue(result["recovered"])
            self.assertEqual("recovery_grant", result["transition"])
            self.assertEqual("reserved", result["state"])
            self.assertEqual(1, len(fresh.status(auth.authorization_id)["recovery_grants"]))
            self.assertEqual("applied", fresh.audit_log()[-1]["phase"])
            self.assertEqual("reserved", fresh.status(auth.authorization_id)["state"])

    def test_grant_state_written_before_applied_marker_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as temporary:
            store, auth = reserved_store(store=new_store(temporary))
            crashing = _CrashAfterStateStore(
                Path(temporary), clock=fixed_clock, crash=True
            )
            with self.assertRaisesRegex(RuntimeError, "simulated crash"):
                crashing.recovery_grant(auth.authorization_id,
                                        auth.one_use_nonce, RUN_ID)
            fresh = new_store(temporary)
            with self.assertRaises(AuthorizationStoreAmbiguous):
                fresh.status(auth.authorization_id)
            self.assertTrue(fresh.recover_interrupted()["recovered"])
            self.assertEqual(1, len(fresh.status(auth.authorization_id)["recovery_grants"]))
            self.assertEqual("applied", fresh.audit_log()[-1]["phase"])

    def test_corrupt_state_fails_closed_without_reset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = new_store(temporary)
            store.prepare(authorization())
            before = store.state_path.read_bytes()
            store.state_path.write_text("{not json", encoding="utf-8")
            corrupt = store.state_path.read_bytes()
            with self.assertRaises(AuthorizationStoreCorrupt):
                new_store(temporary).status("c1e-c1-auth-001")
            self.assertEqual(corrupt, store.state_path.read_bytes())
            self.assertNotEqual(before, corrupt)

    def test_partial_state_and_missing_state_are_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "state.json").write_text(
                json.dumps({"schema_version": "1.0"}), encoding="utf-8"
            )
            with self.assertRaises(AuthorizationStoreCorrupt):
                new_store(temporary).statuses()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "journal.jsonl").write_text(
                json.dumps({"seq": 1}) + "\n", encoding="utf-8"
            )
            with self.assertRaises(AuthorizationStoreCorrupt):
                new_store(temporary).statuses()

    def test_truncated_journal_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            store.prepare(authorization())
            with store.journal_path.open("a", encoding="utf-8") as stream:
                stream.write('{"seq": 3, "phase": "intent"')
            with self.assertRaises(AuthorizationStoreCorrupt):
                new_store(temporary).status("c1e-c1-auth-001")


class AdapterAuthorizationIntegrationTests(unittest.TestCase):
    def _config(self, store, auth, **overrides):
        values = {
            "authorization": auth,
            "authorization_store": store,
            "spec_sha256": auth.spec_sha256,
            "asset_id": auth.asset_id,
        }
        values.update(overrides)
        return config(**values)

    def test_read_only_snapshot_needs_no_mutation_authorization(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            adapter, transport = make_adapter(
                authorization_store=store,
                authorization=authorization(),
                spec_sha256=authorization().spec_sha256,
                asset_id=ASSET_ID,
            )
            self.assertTrue(validate_snapshot(adapter.snapshot())["ok"])
            self.assertEqual([STATE_TOOL, LUAU_TOOL],
                             [call[0] for call in transport.calls])

    def test_unprepared_authorization_cannot_mutate(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            adapter = McpStudioAdapter(
                self._config(store, auth), RecordingTransport()
            )
            with self.assertRaises(AuthorizationStateError):
                adapter.create_folder("C1C_TextureTest_x", {}, [])

    def test_prepared_but_unreserved_authorization_cannot_mutate(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.prepare(auth)
            adapter = McpStudioAdapter(
                self._config(store, auth), RecordingTransport()
            )
            with self.assertRaises(AuthorizationStateError):
                adapter.create_folder("C1C_TextureTest_x", {}, [])

    def test_reserved_authorization_is_checked_then_still_unimplemented(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            transport = RecordingTransport()
            adapter = McpStudioAdapter(self._config(store, auth), transport)
            with self.assertRaises(McpAdapterNotImplemented):
                adapter.create_folder("C1C_TextureTest_x", {}, [])
            self.assertEqual([], transport.calls)
            self.assertEqual(
                "reserved", store.status(auth.authorization_id)["state"]
            )

    def test_consumed_authorization_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            store.consume(auth, "create")
            adapter = McpStudioAdapter(
                self._config(store, auth), RecordingTransport()
            )
            with self.assertRaises(AuthorizationReplay):
                adapter.create_folder("C1C_TextureTest_x", {}, [])

    def test_store_mismatch_with_adapter_config_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            with self.assertRaises(AuthorizationMismatch):
                McpAdapterConfig(
                    studio_id=STUDIO_ID,
                    place=PLACE,
                    run_id=RUN_ID,
                    authorization=auth,
                    authorization_store=store,
                    spec_sha256="0" * 64,
                    identity=identity(),
                )

    def test_authorization_store_never_calls_the_mcp_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            transport = RecordingTransport()
            adapter = McpStudioAdapter(self._config(store, auth), transport)
            for name, call in mutation_calls(adapter).items():
                with self.subTest(operation=name):
                    with self.assertRaises(McpAdapterNotImplemented):
                        call()
            self.assertEqual([], transport.calls)

    def test_authorization_work_does_not_touch_the_registry(self):
        before = registry_fingerprint(ROOT)
        with tempfile.TemporaryDirectory() as temporary:
            store = new_store(temporary)
            auth = authorization()
            store.reserve(auth, example_spec(), example_plan(), identity())
            transport = RecordingTransport(by_tool={
                STATE_TOOL: state_payload(),
                LUAU_TOOL: snapshot_payload(),
            })
            adapter = McpStudioAdapter(self._config(store, auth), transport)
            adapter.snapshot()
            with self.assertRaises(McpAdapterNotImplemented):
                adapter.create_folder("C1C_TextureTest_x", {}, [])
        self.assertEqual(before, registry_fingerprint(ROOT))


if __name__ == "__main__":
    unittest.main()
