"""C1E-B offline read-only snapshot adapter for the Roblox Studio MCP seam.

This module extends the C1E-A skeleton with an **offline-only** identity and
Workspace snapshot path. It does not activate a live integration:

* construction performs no I/O and contacts no Roblox Studio;
* the only transport interactions are the guarded, read-only
  ``get_studio_state`` and a fixed-source ``execute_luau`` snapshot query;
* every Studio mutation raises :class:`McpAdapterNotImplemented`;
* the MCP tool allow-list is deny-by-default;
* the assumed MCP response envelopes are adapter-internal contracts. They are
  **not** verified against the real Roblox MCP server and are rejected when
  their shape differs.

The snapshot returned by :meth:`McpStudioAdapter.snapshot` reuses the existing
:class:`c1c_harness.StudioAdapter` shape and is validated with the existing
:func:`c1c_harness.validate_snapshot`. There is no competing snapshot schema.

Safety posture
--------------

The adapter fails closed on:

* a missing or contradictory expected identity;
* a wrong Studio ID, place label, place/game ID, creator or signed-in user;
* Team Create or a non-Edit DataModel;
* an unknown or malformed MCP response envelope;
* a truncated, incomplete or internally inconsistent hierarchy;
* missing descendants, orphaned nodes, duplicate paths, invalid parents,
  malformed attributes/tags, invalid camera data or missing viewport data.

Known integration limitation: a live MCP server response shape has never been
observed or tested. Passing mocked fixtures here proves only the adapter's
decoding and validation rules, not compatibility with the real server.

Authorization trust boundary
----------------------------

:class:`LiveRunAuthorization` and :class:`AuthorizationStore` are local
operator declarations plus a replay-resistant journal. They are **not**
authenticated proof that a human approved a run: anyone who can write the
store directory or construct the dataclass can forge a record. The store
prevents accidental, concurrent and cross-restart replay of the same nonce; it
cannot establish the identity of the approver or the independence of the
approval. A live run still needs a separately verified operator process.

The adapter is still mutation-blocked. A future live mutation implementation
must reserve the authorization, then call ``AuthorizationStore.consume()``
under the store lock immediately before the first mutation is dispatched. This
offline adapter never calls ``consume()`` because it never dispatches a
mutation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import threading
import time
import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, NoReturn, Protocol


# Tools documented in docs/C1D_INTEGRATION_PREFLIGHT.md section 5.2. Unknown
# tool names are rejected, so save/publish or any later upload path cannot be
# reached by name guessing.
ALLOWED_MCP_TOOLS = frozenset({
    "roblox_studio_list_roblox_studios",
    "roblox_studio_get_studio_state",
    "roblox_studio_execute_luau",
    "roblox_studio_screen_capture",
})

FORBIDDEN_MCP_TOOLS = frozenset({
    "roblox_studio_upload_image",
    "roblox_studio_insert_asset",
    "roblox_studio_start_stop_play",
})

# The mutation actions documented in the one-use operator authorization shape.
MUTATION_ACTIONS = frozenset({
    "create",
    "rename",
    "destroy",
    "camera",
    "screenshot",
})

# A local authorization record is not authenticated proof of human approval.
# It is an operator-authored declaration stored on the same filesystem as the
# code that consumes it; anyone with write access to that directory can forge
# it. The durable store prevents accidental or concurrent replay; it cannot
# establish who approved the record or that the approval was independent.
PINNED_TEST_ASSETS = {"rbxassetid://112705883084796": "test_only_unapproved"}

AUTHORIZATION_SCHEMA_VERSION = "1.0"
AUTHORIZATION_STATES = frozenset({
    "prepared",
    "validated",
    "reserved",
    "consumed",
    "expired",
    "refused",
})
TERMINAL_AUTHORIZATION_STATES = frozenset({"consumed", "expired", "refused"})
MAX_AUTHORIZED_OBJECTS = 128
MAX_AUTHORIZATION_LIFETIME = timedelta(hours=24)

AUTHORIZATION_FIELDS = frozenset({
    "authorization_id",
    "one_use_nonce",
    "actor",
    "approved_at",
    "expires_at",
    "studio_id",
    "place",
    "place_id",
    "game_id",
    "creator_id",
    "creator_type",
    "is_unsaved",
    "user_id",
    "run_id",
    "spec_sha256",
    "asset_id",
    "asset_status",
    "allowed_actions",
    "max_objects",
    "evidence_require_durable_files",
    "evidence_required_capture_ids",
    "acknowledge_no_save_publish_upload",
})

STATE_TOOL = "roblox_studio_get_studio_state"
LUAU_TOOL = "roblox_studio_execute_luau"

STATE_ENVELOPE_KEYS = frozenset({
    "studio_id",
    "mode",
    "place",
    "user",
    "team_create",
})

PLACE_IDENTITY_KEYS = frozenset({
    "name",
    "place_id",
    "game_id",
    "creator_id",
    "creator_type",
    "is_unsaved",
})

USER_IDENTITY_KEYS = frozenset({"id", "name"})

SNAPSHOT_PAYLOAD_KEYS = frozenset({
    "complete",
    "objects",
    "workspace",
    "selection",
    "camera",
    "tagged",
    "enumeration",
})

ENUMERATION_KEYS = frozenset({
    "root",
    "visited",
    "descendant_count",
    "truncated",
    "max_depth",
})

OBJECT_KEYS = frozenset({
    "path",
    "name",
    "class_name",
    "parent",
    "children",
    "attributes",
    "tags",
    "properties",
})

WORKSPACE_KEYS = frozenset({"attributes", "tags", "children"})
CAMERA_KEYS = frozenset({"cframe", "camera_type", "viewport"})

# Fixed, auditable read-only Luau. No operator, run or config value is ever
# interpolated into this source. The adapter sends the Studio ID separately in
# the MCP tool payload so the transport can route to the already-verified
# instance.
# C1E-C2A review: this source is NOT cleared for live execution. Enumeration
# and output are unbounded, attributes are not encoded, dot paths can alias,
# and no same-read identity is returned. See docs/C1E_C2_MCP_PREFLIGHT.md.
READ_ONLY_SNAPSHOT_LUAU = r"""
-- C1E-B fixed, read-only Workspace snapshot query.
-- It reads the Edit DataModel only. It never creates, clones, renames,
-- destroys, moves, saves, publishes or uploads anything.
local Workspace = game:GetService("Workspace")
local Selection = game:GetService("Selection")
local CollectionService = game:GetService("CollectionService")

local CURATED_PROPERTIES = {
    "Anchored", "CanCollide", "Size", "Position", "CFrame", "Transparency",
    "Material", "Texture", "Face", "StudsPerTileU", "StudsPerTileV",
    "OffsetStudsU", "OffsetStudsV", "Color", "BrickColor", "Shape",
    "Reflectance", "CameraType", "ViewportSize", "Text", "TextScaled",
    "StreamingEnabled",
}

local function encode(value)
    local kind = typeof(value)
    if kind == "Vector3" then
        return { value.X, value.Y, value.Z }
    elseif kind == "Vector2" then
        return { value.X, value.Y }
    elseif kind == "CFrame" then
        return { value:GetComponents() }
    elseif kind == "Color3" then
        return { value.R, value.G, value.B }
    elseif kind == "BrickColor" then
        return value.Name
    elseif kind == "EnumItem" then
        return value.Name
    elseif kind == "string" or kind == "number" or kind == "boolean" then
        return value
    end
    return nil
end

local objects = {}
local visited = {}
local tagged = {}
local maxDepth = 0

local function visit(instance, path, depth)
    visited[#visited + 1] = path
    if depth > maxDepth then
        maxDepth = depth
    end

    local properties = {}
    for _, propertyName in ipairs(CURATED_PROPERTIES) do
        local ok, value = pcall(function()
            return instance[propertyName]
        end)
        if ok then
            local encoded = encode(value)
            if encoded ~= nil then
                properties[propertyName] = encoded
            end
        end
    end

    local tags = CollectionService:GetTags(instance)
    for _, tag in ipairs(tags) do
        tagged[tag] = tagged[tag] or {}
        table.insert(tagged[tag], path)
    end

    local children = {}
    for _, child in ipairs(instance:GetChildren()) do
        children[#children + 1] = path .. "." .. child.Name
    end

    local parent = string.match(path, "^(.*)%.") or ""
    table.insert(objects, {
        path = path,
        name = instance.Name,
        class_name = instance.ClassName,
        parent = parent,
        children = children,
        attributes = instance:GetAttributes(),
        tags = tags,
        properties = properties,
    })

    for _, child in ipairs(instance:GetChildren()) do
        visit(child, path .. "." .. child.Name, depth + 1)
    end
end

visit(Workspace, "Workspace", 0)

local selection = {}
for _, instance in ipairs(Selection:Get()) do
    selection[#selection + 1] = instance:GetFullName()
end

local cameraPayload = nil
local currentCamera = Workspace.CurrentCamera
if currentCamera then
    cameraPayload = {
        cframe = { currentCamera.CFrame:GetComponents() },
        camera_type = currentCamera.CameraType.Name,
        viewport = { currentCamera.ViewportSize.X, currentCamera.ViewportSize.Y },
    }
end

return {
    complete = true,
    objects = objects,
    workspace = {
        attributes = Workspace:GetAttributes(),
        tags = CollectionService:GetTags(Workspace),
        children = objects[1].children,
    },
    selection = selection,
    camera = cameraPayload,
    tagged = tagged,
    enumeration = {
        root = "Workspace",
        visited = visited,
        descendant_count = #objects - 1,
        truncated = false,
        max_depth = maxDepth,
    },
}
""".strip()


class McpAdapterError(RuntimeError):
    """Base error for the C1E adapter."""


class ConfigurationError(McpAdapterError, ValueError):
    """The injected adapter configuration is missing or inconsistent."""


class AuthorizationError(McpAdapterError):
    """An operator authorization is absent or does not cover an action."""


class AuthorizationStateError(AuthorizationError):
    """The authorization is not in the lifecycle state required by the call."""


class AuthorizationExpired(AuthorizationError):
    """The authorization has expired and must never become usable again."""


class AuthorizationNotYetValid(AuthorizationError):
    """The approval timestamp is in the future for the supplied clock."""


class AuthorizationReplay(AuthorizationError):
    """A nonce or reservation is being replayed or reused."""


class AuthorizationMismatch(AuthorizationError):
    """The authorization does not match the run, spec, Studio or asset."""


class DuplicateAuthorization(AuthorizationError):
    """An authorization ID or one-use nonce already exists in the store."""


class AuthorizationStoreError(McpAdapterError):
    """Base error for the durable local authorization store."""


class AuthorizationStoreBusy(AuthorizationStoreError):
    """The store lock could not be acquired; the caller must fail closed."""


class AuthorizationStoreCorrupt(AuthorizationStoreError):
    """The store data is malformed, partial or internally inconsistent."""


class AuthorizationStoreAmbiguous(AuthorizationStoreCorrupt):
    """An interrupted transition must be recovered explicitly before use."""


class ToolPolicyError(McpAdapterError):
    """An MCP tool is not on the fail-closed allow-list."""


class TransportUnavailable(McpAdapterError):
    """No MCP transport was injected, so no Studio call can be made."""


class TransportResponseError(McpAdapterError):
    """The injected transport returned an unusable response."""


class UnsupportedEnvelopeError(TransportResponseError):
    """The MCP response envelope is unknown or not supported by this adapter."""


class IdentityError(McpAdapterError):
    """The connected Studio, place, creator or user identity is not accepted."""


class SnapshotNormalizationError(McpAdapterError):
    """A snapshot payload is malformed and cannot be normalized safely."""


class SnapshotIncompleteError(SnapshotNormalizationError):
    """The snapshot did not supply enough evidence to claim completeness."""


class SnapshotValidationError(SnapshotNormalizationError):
    """The normalized snapshot failed the existing validate_snapshot contract."""

    def __init__(self, issues: list[dict[str, Any]]):
        self.issues = copy.deepcopy(issues)
        super().__init__(
            "snapshot failed validate_snapshot: "
            + json.dumps(self.issues[:5], sort_keys=True, default=str)
        )


if TYPE_CHECKING:
    from c1c_harness import CaptureResult


class McpAdapterNotImplemented(NotImplementedError, McpAdapterError):
    """A live Studio mutation is intentionally not implemented."""


def _require_text(value: Any, field: str, error: type[McpAdapterError]) -> str:
    if not isinstance(value, str) or not value.strip():
        raise error(f"{field} must be a non-empty string")
    return value


def _require_bool(value: Any, field: str,
                  error: type[McpAdapterError]) -> bool:
    if not isinstance(value, bool):
        raise error(f"{field} must be a boolean")
    return value


def _require_int(value: Any, field: str, *,
                 minimum: int | None = None,
                 error: type[McpAdapterError]) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise error(f"{field} must be an integer")
    if minimum is not None and value < minimum:
        raise error(f"{field} must be at least {minimum}")
    return value


def _require_number(value: Any, field: str,
                    error: type[McpAdapterError]) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise error(f"{field} must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise error(f"{field} must be a finite number")
    return number


def _require_exact_keys(mapping: Mapping[Any, Any], expected: frozenset[str],
                        field: str,
                        error: type[McpAdapterError] = SnapshotNormalizationError
                        ) -> None:
    actual = set(mapping.keys())
    if actual == set(expected):
        return
    missing = sorted(str(key) for key in set(expected) - actual)
    unknown = sorted(str(key) for key in actual - set(expected))
    raise error(
        f"{field} has an unsupported shape; "
        f"missing keys={missing}, unknown keys={unknown}"
    )


def _json_safe(value: Any) -> bool:
    if value is None or isinstance(value, (str, bool, int)):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return all(_json_safe(item) for item in value)
    if isinstance(value, Mapping):
        return all(
            isinstance(key, str) and bool(key) and _json_safe(item)
            for key, item in value.items()
        )
    return False


def _require_json_mapping(value: Any, field: str,
                          error: type[McpAdapterError] = SnapshotNormalizationError
                          ) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise error(f"{field} must be a mapping")
    result: dict[str, Any] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise error(f"{field} keys must be non-empty strings")
        if not _json_safe(item):
            raise error(f"{field}[{key!r}] is not a JSON-safe value")
        result[key] = copy.deepcopy(item)
    return result


def _require_string_list(value: Any, field: str, *,
                         unique: bool = True,
                         allow_empty: bool = True,
                         error: type[McpAdapterError] = SnapshotNormalizationError
                         ) -> list[str]:
    if not isinstance(value, list):
        raise error(f"{field} must be a list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise error(f"{field} entries must be non-empty strings")
        if unique and item in result:
            raise error(f"{field} contains a duplicate entry: {item!r}")
        result.append(item)
    if not allow_empty and not result:
        raise error(f"{field} must not be empty")
    return result


_AUTHORIZATION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_NONCE_RE = re.compile(r"^[^\s]{1,512}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ASSET_ID_RE = re.compile(r"^rbxassetid://[1-9][0-9]*$")


def _require_authorization_id(value: Any, field: str) -> str:
    if not isinstance(value, str) or _AUTHORIZATION_ID_RE.fullmatch(value) is None:
        raise ConfigurationError(
            f"{field} must match {_AUTHORIZATION_ID_RE.pattern}"
        )
    return value


def _require_nonce(value: Any, field: str = "one_use_nonce") -> str:
    if not isinstance(value, str) or _NONCE_RE.fullmatch(value) is None:
        raise ConfigurationError(
            f"{field} must be a non-empty string without whitespace"
        )
    return value


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ConfigurationError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _require_asset_id(value: Any, field: str = "asset_id") -> str:
    if not isinstance(value, str) or _ASSET_ID_RE.fullmatch(value) is None:
        raise ConfigurationError(f"{field} must be an rbxassetid:// ID")
    return value


def _coerce_utc(value: Any, field: str) -> datetime:
    """Require an explicit UTC timestamp and normalize it to timezone.utc.

    Naive timestamps and non-UTC offsets are rejected: silently reinterpreting
    an operator timestamp could move an expiry window by hours.
    """
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str):
        text = value.strip()
        if text.endswith(("Z", "z")):
            text = text[:-1] + "+00:00"
        try:
            moment = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ConfigurationError(
                f"{field} must be an ISO-8601 timestamp"
            ) from exc
    else:
        raise ConfigurationError(
            f"{field} must be an ISO-8601 string or datetime"
        )
    if moment.tzinfo is None or moment.utcoffset() != timedelta(0):
        raise ConfigurationError(
            f"{field} must carry an explicit UTC timezone (Z or +00:00)"
        )
    return moment.astimezone(timezone.utc)


def _format_utc(value: Any, field: str) -> str:
    return _coerce_utc(value, field).replace(microsecond=0).isoformat()


def _require_utc(value: Any, field: str) -> datetime:
    if not isinstance(value, datetime):
        raise ConfigurationError(f"{field} must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ConfigurationError(f"{field} must be timezone-aware UTC")
    return value.astimezone(timezone.utc)


def _canonical_sha256(value: Any) -> str:
    from c1c_harness import canonical_sha256

    return canonical_sha256(value)


def _authorization_fingerprint_payload(authorization: "LiveRunAuthorization"
                                      ) -> dict[str, Any]:
    payload = authorization.structural_dict()
    return payload


@dataclass(frozen=True, kw_only=True)
class StudioIdentity:
    """Explicit expected Studio/place/creator/user identity for one run.

    Every field is operator-supplied and is compared exactly against the
    read-only ``get_studio_state`` response. An unspecified identity is not
    accepted by :meth:`McpStudioAdapter.snapshot`.

    ``is_unsaved`` distinguishes the historical local, unsaved place
    (``PlaceId=0``/``GameId=0``) from a saved or published place. A saved place
    with ``game_id=0`` is treated as ``saved_unpublished`` rather than
    ``published``.
    """

    studio_id: str
    place: str
    user_id: int
    is_unsaved: bool = True
    place_id: int = 0
    game_id: int = 0
    creator_id: int = 0
    creator_type: str = "User"
    mode: str = "edit"
    team_create: bool = False

    def __post_init__(self) -> None:
        _require_text(self.studio_id, "identity.studio_id", ConfigurationError)
        _require_text(self.place, "identity.place", ConfigurationError)
        _require_int(self.user_id, "identity.user_id", minimum=1,
                     error=ConfigurationError)
        _require_bool(self.is_unsaved, "identity.is_unsaved", ConfigurationError)
        _require_int(self.place_id, "identity.place_id", minimum=0,
                     error=ConfigurationError)
        _require_int(self.game_id, "identity.game_id", minimum=0,
                     error=ConfigurationError)
        _require_int(self.creator_id, "identity.creator_id", minimum=0,
                     error=ConfigurationError)
        _require_text(self.creator_type, "identity.creator_type",
                      ConfigurationError)
        creator_type = self.creator_type.strip().lower()
        if creator_type not in ("user", "group"):
            raise ConfigurationError(
                "identity.creator_type must be 'User' or 'Group'"
            )
        object.__setattr__(self, "creator_type", creator_type)
        _require_bool(self.team_create, "identity.team_create",
                      ConfigurationError)
        if self.team_create:
            raise ConfigurationError(
                "identity.team_create must be False; Team Create is not supported"
            )
        if not isinstance(self.mode, str) or self.mode.strip().lower() != "edit":
            raise ConfigurationError("identity.mode must be 'Edit'")
        object.__setattr__(self, "mode", "edit")
        if self.is_unsaved:
            if self.place_id != 0 or self.game_id != 0:
                raise ConfigurationError(
                    "an unsaved local place must have place_id=0 and game_id=0"
                )
        else:
            if self.place_id <= 0:
                raise ConfigurationError(
                    "a saved/published place must have a positive place_id"
                )
            if self.creator_id <= 0:
                raise ConfigurationError(
                    "a saved/published place must have a positive creator_id"
                )

    @property
    def place_kind(self) -> str:
        if self.is_unsaved:
            return "unsaved_local"
        if self.game_id > 0:
            return "published"
        return "saved_unpublished"


@dataclass(frozen=True)
class VerifiedStudioIdentity:
    """Identity decoded and checked from the read-only Studio state response."""

    studio_id: str
    place: str
    mode: str
    team_create: bool
    is_unsaved: bool
    place_id: int
    game_id: int
    creator_id: int
    creator_type: str
    user_id: int
    user_name: str

    @property
    def place_kind(self) -> str:
        if self.is_unsaved:
            return "unsaved_local"
        if self.game_id > 0:
            return "published"
        return "saved_unpublished"


def decode_mcp_payload(response: Any, *, context: str = "MCP tool") -> Any:
    """Decode a supported MCP tool response without trusting its envelope.

    Two shapes are accepted:

    * a direct JSON-like mapping (the adapter-internal contract used by tests);
    * exactly one MCP text content block containing JSON.

    Every other envelope is rejected with :class:`UnsupportedEnvelopeError`.
    The real Roblox MCP server's response shape has not been verified; this
    function deliberately does not guess or silently unwrap unknown keys.
    """
    if not isinstance(response, Mapping):
        raise TransportResponseError(f"{context} response must be a mapping")

    if "content" not in response:
        unknown = sorted(str(key) for key in response.keys())
        if "result" in response or "error" in response:
            raise UnsupportedEnvelopeError(
                f"{context} response envelope is unsupported; "
                f"preserve and inspect keys {unknown} before claiming live "
                "MCP compatibility"
            )
        return dict(response)

    _require_exact_keys(
        response, frozenset({"content"}), f"{context} envelope",
        UnsupportedEnvelopeError,
    )
    content = response["content"]
    if not isinstance(content, list) or len(content) != 1:
        raise UnsupportedEnvelopeError(
            f"{context} content must contain exactly one block"
        )
    block = content[0]
    if not isinstance(block, Mapping):
        raise UnsupportedEnvelopeError(
            f"{context} content block must be a mapping"
        )
    _require_exact_keys(
        block, frozenset({"type", "text"}), f"{context} content block",
        UnsupportedEnvelopeError,
    )
    if block["type"] != "text" or not isinstance(block["text"], str):
        raise UnsupportedEnvelopeError(
            f"{context} content block must be a text block"
        )
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON object key")
            result[key] = value
        return result

    def reject_constant(value: str) -> NoReturn:
        raise ValueError("non-finite JSON constant")

    try:
        payload = json.loads(
            block["text"], object_pairs_hook=unique_object,
            parse_constant=reject_constant,
        )
        # JSON exponent overflow (e.g. 1e999) also produces infinity in Python.
        if not _json_safe(payload):
            raise ValueError("non-JSON-safe payload")
        return payload
    except ValueError as exc:
        raise TransportResponseError(
            f"{context} text block is not unambiguous finite JSON"
        ) from exc


def verify_state_payload(payload: Any,
                         expected: StudioIdentity) -> VerifiedStudioIdentity:
    """Parse and strictly validate the read-only Studio state payload.

    Fails closed on missing, ambiguous, malformed or contradictory identity
    fields, and on any mismatch with the explicit expected identity.
    """
    if not isinstance(payload, Mapping):
        raise TransportResponseError(
            "get_studio_state payload must be a mapping"
        )
    if set(payload.keys()) != set(STATE_ENVELOPE_KEYS):
        missing = sorted(set(STATE_ENVELOPE_KEYS) - set(payload.keys()))
        unknown = sorted(str(key) for key in set(payload.keys())
                         - set(STATE_ENVELOPE_KEYS))
        raise IdentityError(
            "get_studio_state payload is missing or has unsupported identity "
            f"fields; missing={missing}, unknown={unknown}"
        )

    studio_id = payload["studio_id"]
    if not isinstance(studio_id, str) or not studio_id.strip():
        raise IdentityError(
            "get_studio_state is missing a valid studio_id"
        )
    if studio_id != expected.studio_id:
        raise IdentityError(
            "connected Studio instance does not match the expected studio_id"
        )

    mode = payload["mode"]
    if not isinstance(mode, str) or mode.strip().lower() != "edit":
        raise IdentityError(
            "get_studio_state does not report the required Edit DataModel"
        )
    if mode.strip().lower() != expected.mode:
        raise IdentityError(
            "connected Studio mode does not match the expected mode"
        )

    team_create = payload["team_create"]
    _require_bool(team_create, "get_studio_state.team_create", IdentityError)
    if team_create:
        raise IdentityError(
            "Team Create is active; temporary objects could reach another user"
        )

    place = payload["place"]
    if not isinstance(place, Mapping):
        raise IdentityError(
            "get_studio_state place identity must be a mapping"
        )
    if set(place.keys()) != set(PLACE_IDENTITY_KEYS):
        missing = sorted(set(PLACE_IDENTITY_KEYS) - set(place.keys()))
        unknown = sorted(str(key) for key in set(place.keys())
                         - set(PLACE_IDENTITY_KEYS))
        raise IdentityError(
            "get_studio_state place identity is missing or has unsupported "
            f"fields; missing={missing}, unknown={unknown}"
        )

    place_name = _require_text(place["name"], "place.name", IdentityError)
    place_id = _require_int(place["place_id"], "place.place_id", minimum=0,
                            error=IdentityError)
    game_id = _require_int(place["game_id"], "place.game_id", minimum=0,
                           error=IdentityError)
    creator_id = _require_int(place["creator_id"], "place.creator_id",
                              minimum=0, error=IdentityError)
    creator_type = _require_text(place["creator_type"], "place.creator_type",
                                 IdentityError).strip().lower()
    if creator_type not in ("user", "group"):
        raise IdentityError(
            "place.creator_type must be 'User' or 'Group'"
        )
    is_unsaved = _require_bool(place["is_unsaved"], "place.is_unsaved",
                               IdentityError)

    if is_unsaved:
        if place_id != 0 or game_id != 0:
            raise IdentityError(
                "an unsaved local place cannot report nonzero place_id/game_id"
            )
        place_label = "local-unsaved"
    else:
        if place_id <= 0:
            raise IdentityError(
                "a saved or published place must report a positive place_id"
            )
        place_label = place_name

    if is_unsaved != expected.is_unsaved:
        raise IdentityError(
            "connected place saved/unsaved state does not match the expectation"
        )
    if place_label != expected.place:
        raise IdentityError(
            "connected place identity does not match the expected place label"
        )
    if place_id != expected.place_id:
        raise IdentityError(
            "connected place_id does not match the expected place_id"
        )
    if game_id != expected.game_id:
        raise IdentityError(
            "connected game_id does not match the expected game_id"
        )
    if creator_id != expected.creator_id:
        raise IdentityError(
            "connected creator_id does not match the expected creator_id"
        )
    if creator_type != expected.creator_type:
        raise IdentityError(
            "connected creator_type does not match the expected creator_type"
        )

    user = payload["user"]
    if not isinstance(user, Mapping):
        raise IdentityError(
            "get_studio_state user identity must be a mapping"
        )
    if set(user.keys()) != set(USER_IDENTITY_KEYS):
        missing = sorted(set(USER_IDENTITY_KEYS) - set(user.keys()))
        unknown = sorted(str(key) for key in set(user.keys())
                         - set(USER_IDENTITY_KEYS))
        raise IdentityError(
            "get_studio_state user identity is missing or has unsupported "
            f"fields; missing={missing}, unknown={unknown}"
        )
    user_id = _require_int(user["id"], "user.id", minimum=1,
                           error=IdentityError)
    user_name = _require_text(user["name"], "user.name", IdentityError)
    if user_id != expected.user_id:
        raise IdentityError(
            "signed-in Studio user does not match the expected user_id"
        )

    return VerifiedStudioIdentity(
        studio_id=studio_id,
        place=place_label,
        mode="Edit",
        team_create=False,
        is_unsaved=is_unsaved,
        place_id=place_id,
        game_id=game_id,
        creator_id=creator_id,
        creator_type=creator_type,
        user_id=user_id,
        user_name=user_name,
    )


def normalize_snapshot_payload(payload: Any, identity: VerifiedStudioIdentity, *,
                               adapter_name: str) -> dict[str, Any]:
    """Convert a read-only hierarchy payload into the existing Snapshot shape.

    ``validate_snapshot`` is intentionally not called here; the adapter calls
    it after this function returns so response decoding, normalization and
    contract validation remain separate, testable stages.
    """
    if not isinstance(payload, Mapping):
        raise TransportResponseError("snapshot payload must be a mapping")
    if "complete" not in payload:
        raise SnapshotIncompleteError(
            "snapshot did not assert completeness"
        )
    complete = payload["complete"]
    if not isinstance(complete, bool):
        raise SnapshotNormalizationError(
            "snapshot complete must be a boolean"
        )
    if complete is not True:
        raise SnapshotIncompleteError(
            "adapter did not assert complete:true for the hierarchy snapshot"
        )
    if "enumeration" not in payload:
        raise SnapshotIncompleteError(
            "snapshot enumeration evidence is missing"
        )
    if set(payload.keys()) != set(SNAPSHOT_PAYLOAD_KEYS):
        missing = sorted(set(SNAPSHOT_PAYLOAD_KEYS) - set(payload.keys()))
        unknown = sorted(str(key) for key in set(payload.keys())
                         - set(SNAPSHOT_PAYLOAD_KEYS))
        raise UnsupportedEnvelopeError(
            "snapshot payload has an unsupported shape; "
            f"missing={missing}, unknown={unknown}"
        )

    enumeration = payload["enumeration"]
    if not isinstance(enumeration, Mapping):
        raise SnapshotIncompleteError(
            "snapshot enumeration evidence is missing"
        )
    if set(enumeration.keys()) != set(ENUMERATION_KEYS):
        missing = sorted(set(ENUMERATION_KEYS) - set(enumeration.keys()))
        unknown = sorted(str(key) for key in set(enumeration.keys())
                         - set(ENUMERATION_KEYS))
        raise SnapshotIncompleteError(
            "snapshot enumeration evidence is incomplete; "
            f"missing={missing}, unknown={unknown}"
        )
    if enumeration["root"] != "Workspace":
        raise SnapshotNormalizationError(
            "snapshot enumeration root must be 'Workspace'"
        )
    truncated = _require_bool(
        enumeration["truncated"], "enumeration.truncated",
        SnapshotNormalizationError,
    )
    if truncated:
        raise SnapshotIncompleteError(
            "snapshot enumeration was truncated; the hierarchy is not complete"
        )
    visited = _require_string_list(
        enumeration["visited"], "enumeration.visited",
        unique=True, allow_empty=False,
    )
    descendant_count = _require_int(
        enumeration["descendant_count"], "enumeration.descendant_count",
        minimum=0, error=SnapshotNormalizationError,
    )
    max_depth = _require_int(
        enumeration["max_depth"], "enumeration.max_depth",
        minimum=0, error=SnapshotNormalizationError,
    )

    raw_objects = payload["objects"]
    if not isinstance(raw_objects, list) or not raw_objects:
        raise SnapshotNormalizationError(
            "snapshot objects must be a non-empty list"
        )
    objects: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(raw_objects):
        if not isinstance(raw, Mapping):
            raise SnapshotNormalizationError(
                f"objects[{index}] must be a mapping"
            )
        if set(raw.keys()) != set(OBJECT_KEYS):
            missing = sorted(set(OBJECT_KEYS) - set(raw.keys()))
            unknown = sorted(str(key) for key in set(raw.keys())
                             - set(OBJECT_KEYS))
            raise SnapshotNormalizationError(
                f"objects[{index}] has an unsupported shape; "
                f"missing={missing}, unknown={unknown}"
            )
        path = _require_text(raw["path"], f"objects[{index}].path",
                             SnapshotNormalizationError)
        if path in objects:
            raise SnapshotNormalizationError(
                f"duplicate object path: {path}"
            )
        name = _require_text(raw["name"], f"objects[{index}].name",
                             SnapshotNormalizationError)
        class_name = _require_text(raw["class_name"],
                                   f"objects[{index}].class_name",
                                   SnapshotNormalizationError)
        parent = raw["parent"]
        if not isinstance(parent, str):
            raise SnapshotNormalizationError(
                f"objects[{index}].parent must be a string"
            )
        children = _require_string_list(
            raw["children"], f"objects[{index}].children",
            unique=True, allow_empty=True,
        )
        attributes = _require_json_mapping(
            raw["attributes"], f"objects[{index}].attributes",
            SnapshotNormalizationError,
        )
        tags = _require_string_list(
            raw["tags"], f"objects[{index}].tags",
            unique=True, allow_empty=True,
        )
        properties = _require_json_mapping(
            raw["properties"], f"objects[{index}].properties",
            SnapshotNormalizationError,
        )
        objects[path] = {
            "path": path,
            "name": name,
            "class_name": class_name,
            "parent": parent,
            "children": children,
            "attributes": attributes,
            "tags": tags,
            "properties": properties,
        }

    workspace_node = objects.get("Workspace")
    if workspace_node is None:
        raise SnapshotNormalizationError("Workspace node is missing")
    if workspace_node["name"] != "Workspace" or workspace_node["parent"] != "":
        raise SnapshotNormalizationError(
            "Workspace must be the root node with an empty parent"
        )
    if workspace_node["class_name"] not in ("Workspace", "DataModel"):
        raise SnapshotNormalizationError(
            "Workspace node has an invalid class"
        )

    workspace = payload["workspace"]
    if not isinstance(workspace, Mapping):
        raise SnapshotNormalizationError(
            "snapshot workspace summary is missing"
        )
    if set(workspace.keys()) != set(WORKSPACE_KEYS):
        missing = sorted(set(WORKSPACE_KEYS) - set(workspace.keys()))
        unknown = sorted(str(key) for key in set(workspace.keys())
                         - set(WORKSPACE_KEYS))
        raise SnapshotNormalizationError(
            "snapshot workspace summary has an unsupported shape; "
            f"missing={missing}, unknown={unknown}"
        )
    workspace_attributes = _require_json_mapping(
        workspace["attributes"], "workspace.attributes",
        SnapshotNormalizationError,
    )
    workspace_tags = _require_string_list(
        workspace["tags"], "workspace.tags", unique=True, allow_empty=True,
    )
    workspace_children = _require_string_list(
        workspace["children"], "workspace.children", unique=True,
        allow_empty=True,
    )
    if workspace_attributes != workspace_node["attributes"]:
        raise SnapshotNormalizationError(
            "workspace summary attributes do not match the Workspace node"
        )
    if sorted(workspace_tags) != sorted(workspace_node["tags"]):
        raise SnapshotNormalizationError(
            "workspace summary tags do not match the Workspace node"
        )
    if sorted(workspace_children) != sorted(workspace_node["children"]):
        raise SnapshotNormalizationError(
            "workspace summary children do not match the Workspace node"
        )

    tagged = payload["tagged"]
    if not isinstance(tagged, Mapping):
        raise SnapshotNormalizationError("snapshot tagged index must be a mapping")
    derived_tagged: dict[str, list[str]] = {}
    for path, node in objects.items():
        for tag in node["tags"]:
            derived_tagged.setdefault(tag, []).append(path)
    derived_tagged = {
        tag: sorted(paths) for tag, paths in sorted(derived_tagged.items())
    }
    normalized_tagged: dict[str, list[str]] = {}
    for tag, paths in tagged.items():
        if not isinstance(tag, str) or not tag:
            raise SnapshotNormalizationError(
                "tagged index keys must be non-empty strings"
            )
        normalized_tagged[tag] = sorted(_require_string_list(
            paths, f"tagged[{tag!r}]", unique=True, allow_empty=True,
        ))
    normalized_tagged = dict(sorted(normalized_tagged.items()))
    if normalized_tagged != derived_tagged:
        raise SnapshotNormalizationError(
            "tagged index does not agree with the object tags"
        )

    selection = payload["selection"]
    if not isinstance(selection, list):
        raise SnapshotNormalizationError("snapshot selection must be a list")
    selection = _require_string_list(
        selection, "selection", unique=True, allow_empty=True,
    )

    camera = payload["camera"]
    if not isinstance(camera, Mapping):
        raise SnapshotNormalizationError("snapshot camera state is missing")
    if set(camera.keys()) != set(CAMERA_KEYS):
        missing = sorted(set(CAMERA_KEYS) - set(camera.keys()))
        unknown = sorted(str(key) for key in set(camera.keys())
                         - set(CAMERA_KEYS))
        raise SnapshotNormalizationError(
            "snapshot camera state has an unsupported shape; "
            f"missing={missing}, unknown={unknown}"
        )
    cframe = camera["cframe"]
    if not isinstance(cframe, list) or len(cframe) != 12:
        raise SnapshotNormalizationError(
            "camera.cframe must be a list of exactly 12 numbers"
        )
    cframe = [
        _require_number(value, f"camera.cframe[{index}]",
                        SnapshotNormalizationError)
        for index, value in enumerate(cframe)
    ]
    camera_type = _require_text(
        camera["camera_type"], "camera.camera_type",
        SnapshotNormalizationError,
    )
    viewport = camera["viewport"]
    if not isinstance(viewport, list) or len(viewport) != 2:
        raise SnapshotNormalizationError(
            "camera.viewport must be a list of exactly 2 integers"
        )
    viewport = [
        _require_int(value, f"camera.viewport[{index}]", minimum=1,
                     error=SnapshotNormalizationError)
        for index, value in enumerate(viewport)
    ]

    camera_node = objects.get("Workspace.Camera")
    if camera_node is not None:
        if camera_node["class_name"] != "Camera":
            raise SnapshotNormalizationError(
                "Workspace.Camera must have class_name 'Camera'"
            )
        for key, expected_value in (
            ("CFrame", cframe),
            ("CameraType", camera_type),
            ("ViewportSize", viewport),
        ):
            if key not in camera_node["properties"]:
                raise SnapshotNormalizationError(
                    f"Workspace.Camera is missing the curated property {key}"
                )
            if camera_node["properties"][key] != expected_value:
                raise SnapshotNormalizationError(
                    f"Workspace.Camera {key} does not match the camera state"
                )

    if len(visited) != len(objects) or set(visited) != set(objects):
        raise SnapshotIncompleteError(
            "enumeration did not visit exactly the returned objects"
        )
    if descendant_count != len(objects) - 1:
        raise SnapshotIncompleteError(
            "enumeration descendant_count does not match the object inventory"
        )
    actual_depth = max((path.count(".") for path in objects), default=0)
    if max_depth < actual_depth:
        raise SnapshotIncompleteError(
            "enumeration max_depth is smaller than the returned hierarchy"
        )

    return {
        "adapter": adapter_name,
        "complete": True,
        "studio": {
            "studio_id": identity.studio_id,
            "place": identity.place,
            "mode": "Edit",
            "team_create": False,
        },
        "workspace": {
            "attributes": copy.deepcopy(workspace_attributes),
            "tags": list(workspace_tags),
            "children": list(workspace_children),
        },
        "objects": objects,
        "selection": list(selection),
        "camera": {
            "cframe": cframe,
            "camera_type": camera_type,
            "viewport": viewport,
        },
        "tagged": normalized_tagged,
    }


@dataclass(frozen=True)
class LiveRunAuthorization:
    """Operator-supplied, durable, single-run authorization declaration.

    The record extends the C1D section 5.7 shape. It binds one actor, one
    authorization ID, one nonce, one UTC approval window, one Studio/place/
    creator/user identity, one run, one spec SHA-256, one pinned test asset,
    one bounded action set, one temporary-object ceiling and one evidence
    requirement.

    This is still a local declaration, not authenticated proof that a human
    approved it. See the module docstring for that trust boundary.
    """

    authorization_id: str
    one_use_nonce: str
    actor: str
    approved_at: str | datetime
    expires_at: str | datetime
    studio_id: str
    place: str
    place_id: int
    game_id: int
    creator_id: int
    creator_type: str
    is_unsaved: bool
    user_id: int
    run_id: str
    spec_sha256: str
    asset_id: str
    asset_status: str
    allowed_actions: tuple[str, ...]
    max_objects: int
    evidence_require_durable_files: bool
    evidence_required_capture_ids: tuple[str, ...]
    acknowledge_no_save_publish_upload: bool

    def __post_init__(self) -> None:
        _require_authorization_id(self.authorization_id, "authorization_id")
        _require_nonce(self.one_use_nonce)
        _require_text(self.actor, "actor", ConfigurationError)
        _require_text(self.studio_id, "studio_id", ConfigurationError)
        _require_text(self.place, "place", ConfigurationError)
        _require_text(self.run_id, "run_id", ConfigurationError)
        _require_sha256(self.spec_sha256, "spec_sha256")
        _require_asset_id(self.asset_id)

        approved = _coerce_utc(self.approved_at, "approved_at")
        expires = _coerce_utc(self.expires_at, "expires_at")
        if expires <= approved:
            raise AuthorizationError(
                "authorization expires_at must be later than approved_at"
            )
        if expires - approved > MAX_AUTHORIZATION_LIFETIME:
            raise AuthorizationError(
                "authorization lifetime is too broad; the maximum is 24 hours"
            )
        object.__setattr__(
            self, "approved_at", approved.replace(microsecond=0).isoformat()
        )
        object.__setattr__(
            self, "expires_at", expires.replace(microsecond=0).isoformat()
        )

        _require_int(self.place_id, "place_id", minimum=0,
                     error=ConfigurationError)
        _require_int(self.game_id, "game_id", minimum=0,
                     error=ConfigurationError)
        _require_int(self.creator_id, "creator_id", minimum=0,
                     error=ConfigurationError)
        _require_int(self.user_id, "user_id", minimum=1,
                     error=ConfigurationError)
        _require_bool(self.is_unsaved, "is_unsaved", ConfigurationError)
        creator_type = _require_text(
            self.creator_type, "creator_type", ConfigurationError
        ).strip().lower()
        if creator_type not in ("user", "group"):
            raise ConfigurationError("creator_type must be 'User' or 'Group'")
        object.__setattr__(self, "creator_type", creator_type)
        if self.is_unsaved:
            if self.place_id != 0 or self.game_id != 0:
                raise AuthorizationError(
                    "an unsaved place authorization must use place_id=0 and "
                    "game_id=0"
                )
        else:
            if self.place_id <= 0 or self.creator_id <= 0:
                raise AuthorizationError(
                    "a saved/published place authorization needs positive "
                    "place_id and creator_id"
                )

        pinned = PINNED_TEST_ASSETS.get(self.asset_id)
        if pinned is None:
            raise AuthorizationError(
                "authorization asset_id is not on the pinned test-asset list"
            )
        if self.asset_status != pinned:
            raise AuthorizationError(
                f"authorization asset {self.asset_id} must have status {pinned!r}"
            )
        if self.asset_status != "test_only_unapproved":
            raise AuthorizationError(
                "only test_only_unapproved assets may be authorized"
            )

        actions = self.allowed_actions
        if not isinstance(actions, (tuple, list)):
            raise ConfigurationError("allowed_actions must be a tuple or list")
        actions = tuple(actions)
        if not actions:
            raise AuthorizationError("authorization grants no actions")
        seen: set[str] = set()
        for action in actions:
            if not isinstance(action, str) or action not in MUTATION_ACTIONS:
                raise AuthorizationError(
                    f"authorization grants an unknown action: {action!r}"
                )
            if action in seen:
                raise AuthorizationError(
                    f"authorization grants a duplicate action: {action!r}"
                )
            seen.add(action)
        object.__setattr__(self, "allowed_actions", actions)

        _require_int(self.max_objects, "max_objects", minimum=1,
                     error=ConfigurationError)
        if self.max_objects > MAX_AUTHORIZED_OBJECTS:
            raise AuthorizationError(
                "authorization temporary-object ceiling is too broad; the "
                f"maximum is {MAX_AUTHORIZED_OBJECTS}"
            )
        _require_bool(
            self.evidence_require_durable_files,
            "evidence_require_durable_files",
            ConfigurationError,
        )
        evidence_ids = self.evidence_required_capture_ids
        if not isinstance(evidence_ids, (tuple, list)):
            raise ConfigurationError(
                "evidence_required_capture_ids must be a tuple or list"
            )
        evidence_ids = tuple(evidence_ids)
        if not evidence_ids:
            raise AuthorizationError(
                "authorization must name at least one required capture"
            )
        if len(set(evidence_ids)) != len(evidence_ids):
            raise AuthorizationError(
                "evidence_required_capture_ids contains a duplicate"
            )
        for capture_id in evidence_ids:
            if not isinstance(capture_id, str) or not capture_id:
                raise ConfigurationError(
                    "evidence_required_capture_ids entries must be non-empty "
                    "strings"
                )
        object.__setattr__(
            self, "evidence_required_capture_ids", evidence_ids
        )

        if self.acknowledge_no_save_publish_upload is not True:
            raise AuthorizationError(
                "authorization must acknowledge that no save, publish or "
                "upload will occur"
            )

    @classmethod
    def from_dict(cls, value: Any) -> "LiveRunAuthorization":
        """Build from an exact authorization mapping.

        Missing and unknown keys are rejected so a typo cannot silently
        weaken the declaration.
        """
        if not isinstance(value, Mapping):
            raise ConfigurationError("authorization must be a mapping")
        actual = set(value.keys())
        if actual != set(AUTHORIZATION_FIELDS):
            missing = sorted(AUTHORIZATION_FIELDS - actual)
            unknown = sorted(str(key) for key in actual - AUTHORIZATION_FIELDS)
            raise ConfigurationError(
                "authorization has an unsupported shape; "
                f"missing keys={missing}, unknown keys={unknown}"
            )
        return cls(**dict(value))

    @property
    def nonce_sha256(self) -> str:
        return hashlib.sha256(self.one_use_nonce.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        """Return the complete operator-facing declaration.

        This contains the raw one-use nonce because it is the operator input
        format; the durable store never persists that field.
        """
        payload = self.structural_dict()
        payload.pop("schema_version", None)
        payload.pop("nonce_sha256", None)
        payload["one_use_nonce"] = self.one_use_nonce
        return payload

    def structural_dict(self) -> dict[str, Any]:
        """Return the non-secret authorization fields for storage/audit."""
        return {
            "schema_version": AUTHORIZATION_SCHEMA_VERSION,
            "authorization_id": self.authorization_id,
            "nonce_sha256": self.nonce_sha256,
            "actor": self.actor,
            "approved_at": self.approved_at,
            "expires_at": self.expires_at,
            "studio_id": self.studio_id,
            "place": self.place,
            "place_id": self.place_id,
            "game_id": self.game_id,
            "creator_id": self.creator_id,
            "creator_type": self.creator_type,
            "is_unsaved": self.is_unsaved,
            "user_id": self.user_id,
            "run_id": self.run_id,
            "spec_sha256": self.spec_sha256,
            "asset_id": self.asset_id,
            "asset_status": self.asset_status,
            "allowed_actions": list(self.allowed_actions),
            "max_objects": self.max_objects,
            "evidence_require_durable_files": (
                self.evidence_require_durable_files
            ),
            "evidence_required_capture_ids": list(
                self.evidence_required_capture_ids
            ),
            "acknowledge_no_save_publish_upload": (
                self.acknowledge_no_save_publish_upload
            ),
        }

    def covers(self, action: str) -> bool:
        if action not in MUTATION_ACTIONS:
            raise AuthorizationError(f"unknown mutation action: {action!r}")
        return action in self.allowed_actions

    def validate_for(self, config: "McpAdapterConfig") -> None:
        for field in ("studio_id", "place", "run_id"):
            if getattr(self, field) != getattr(config, field):
                raise AuthorizationMismatch(
                    f"authorization {field} does not match the adapter "
                    "configuration"
                )
        if config.spec_sha256 is not None and (
            self.spec_sha256 != config.spec_sha256
        ):
            raise AuthorizationMismatch(
                "authorization spec_sha256 does not match the adapter "
                "configuration"
            )
        if config.asset_id is not None and self.asset_id != config.asset_id:
            raise AuthorizationMismatch(
                "authorization asset_id does not match the adapter configuration"
            )
        identity = config.identity
        if identity is not None:
            for field, value in (
                ("studio_id", identity.studio_id),
                ("place", identity.place),
                ("place_id", identity.place_id),
                ("game_id", identity.game_id),
                ("creator_id", identity.creator_id),
                ("creator_type", identity.creator_type),
                ("is_unsaved", identity.is_unsaved),
                ("user_id", identity.user_id),
            ):
                if getattr(self, field) != value:
                    raise AuthorizationMismatch(
                        f"authorization {field} does not match the expected "
                        "Studio identity"
                    )

    def validate_for_spec(self, spec: Any, plan: Any, identity: Any,
                          now: datetime | None = None) -> None:
        """Bind the declaration to the exact spec, plan and live identity."""
        from c1c_harness import (
            PINNED_TEST_ASSETS as HARNESS_PINNED_TEST_ASSETS,
            TEST_ASSET_STATUS,
            canonical_sha256,
            utc_now,
        )

        if spec is None or plan is None:
            raise AuthorizationMismatch("spec and rig plan are required")
        if identity is None:
            raise AuthorizationMismatch(
                "a verified Studio identity is required to bind the "
                "authorization"
            )
        expected_spec_sha256 = canonical_sha256(spec.raw)
        if self.spec_sha256 != expected_spec_sha256:
            raise AuthorizationMismatch(
                "authorization spec_sha256 does not match the supplied spec"
            )
        if self.run_id != spec.run_id or plan.folder != spec.folder_path:
            raise AuthorizationMismatch(
                "authorization run_id does not match the supplied spec/plan"
            )
        if self.studio_id != spec.studio.studio_id:
            raise AuthorizationMismatch(
                "authorization studio_id does not match the supplied spec"
            )
        if self.place != spec.studio.place:
            raise AuthorizationMismatch(
                "authorization place does not match the supplied spec"
            )
        if spec.studio.mode != "edit" or spec.studio.team_create:
            raise AuthorizationMismatch(
                "spec must target Edit mode with Team Create disabled"
            )
        if self.asset_id != spec.asset.asset_id:
            raise AuthorizationMismatch(
                "authorization asset_id does not match the supplied spec"
            )
        if self.asset_status != spec.asset.status:
            raise AuthorizationMismatch(
                "authorization asset status does not match the supplied spec"
            )
        if spec.asset.status != TEST_ASSET_STATUS or spec.asset.upload is not False:
            raise AuthorizationMismatch(
                "spec asset must be test_only_unapproved and must not upload"
            )
        pinned = HARNESS_PINNED_TEST_ASSETS.get(spec.asset.numeric_id)
        if pinned is None or pinned != spec.asset.status:
            raise AuthorizationMismatch(
                "spec asset is not the pinned test-only asset"
            )
        object_count = len(plan.objects)
        if object_count > self.max_objects:
            raise AuthorizationMismatch(
                "authorization temporary-object ceiling is below the planned "
                f"object count ({object_count})"
            )
        required_captures = {
            capture.capture_id for capture in spec.screenshots if capture.required
        }
        if set(self.evidence_required_capture_ids) != required_captures:
            raise AuthorizationMismatch(
                "authorization evidence requirement does not exactly match the "
                "spec's required captures"
            )
        if (
            self.evidence_require_durable_files
            != spec.evidence.require_durable_files
        ):
            raise AuthorizationMismatch(
                "authorization durable-evidence requirement does not match the "
                "spec"
            )
        needed_actions = {"create", "destroy", "camera", "screenshot"}
        if spec.cleanup.allow_safe_rename:
            needed_actions.add("rename")
        missing = sorted(needed_actions - set(self.allowed_actions))
        if missing:
            raise AuthorizationMismatch(
                f"authorization does not cover required actions: {missing}"
            )
        if identity is not None:
            for field, value in (
                ("studio_id", identity.studio_id),
                ("place", identity.place),
                ("place_id", identity.place_id),
                ("game_id", identity.game_id),
                ("creator_id", identity.creator_id),
                ("creator_type", identity.creator_type),
                ("is_unsaved", identity.is_unsaved),
                ("user_id", identity.user_id),
            ):
                if getattr(self, field) != value:
                    raise AuthorizationMismatch(
                        f"authorization {field} does not match the verified "
                        "Studio identity"
                    )
        moment = _require_utc(
            now if now is not None else datetime.fromisoformat(utc_now()),
            "now",
        )
        approved = _coerce_utc(self.approved_at, "approved_at")
        expires = _coerce_utc(self.expires_at, "expires_at")
        if moment < approved:
            raise AuthorizationNotYetValid(
                "authorization approval timestamp is in the future"
            )
        if moment >= expires:
            raise AuthorizationExpired("authorization has expired")


@dataclass(frozen=True)
class RecoveryGrant:
    """Cleanup-only permission for the original authorized run.

    It deliberately cannot authorize new objects, captures, uploads or a new
    run. Live recovery is not activated by this milestone.
    """

    authorization_id: str
    run_id: str
    consumed: bool
    allow_cleanup: bool = True
    allow_new_objects: bool = False
    allow_new_captures: bool = False
    allow_uploads: bool = False
    allow_new_mutations: bool = False


_LOCAL_STORE_LOCKS: dict[str, threading.RLock] = {}
_LOCAL_STORE_LOCKS_GUARD = threading.Lock()


class _StoreLock:
    """Cross-process and intra-process exclusive lock for one store directory."""

    def __init__(self, path: Path, timeout: float):
        self.path = path
        self.timeout = timeout
        self._handle = None
        self._local: threading.RLock | None = None
        self._os_locked = False

    def __enter__(self) -> "_StoreLock":
        key = str(self.path.resolve())
        with _LOCAL_STORE_LOCKS_GUARD:
            local = _LOCAL_STORE_LOCKS.setdefault(key, threading.RLock())
        if not local.acquire(timeout=self.timeout):
            raise AuthorizationStoreBusy("authorization store is busy")
        self._local = local
        try:
            self._handle = self.path.open("a+b")
            if self._handle.seek(0, os.SEEK_END) == 0:
                self._handle.write(b"\0")
                self._handle.flush()
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    self._acquire_os()
                    self._os_locked = True
                    return self
                except OSError:
                    if time.monotonic() >= deadline:
                        raise AuthorizationStoreBusy(
                            "authorization store lock timed out"
                        )
                    time.sleep(0.01)
        except Exception:
            self._release()
            raise

    def _acquire_os(self) -> None:
        assert self._handle is not None
        if os.name == "nt":
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(self._handle.fileno(),
                        fcntl.LOCK_EX | fcntl.LOCK_NB)

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._release()

    def _release(self) -> None:
        handle = self._handle
        try:
            if handle is not None and self._os_locked:
                try:
                    if os.name == "nt":
                        import msvcrt

                        handle.seek(0)
                        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                finally:
                    self._os_locked = False
        finally:
            if handle is not None:
                handle.close()
                self._handle = None
            if self._local is not None:
                self._local.release()
                self._local = None


class AuthorizationStore:
    """Small durable local store for one-use authorizations.

    Guarantees
    ----------
    * Every transition is performed under an intra-process lock plus an OS
      file lock, then written with a same-directory atomic replace.
    * An append-only journal records an intent before the state change and an
      applied marker after it. A process restart that finds a trailing intent
      refuses to operate until :meth:`recover_interrupted` is called.
    * Nonces are stored only as SHA-256 digests and are never removed, so a
      consumed nonce can never be reset or reused.
    * Duplicate authorization IDs and nonces are rejected permanently.
    * Expiry, run, spec, Studio, identity and asset bindings are checked under
      the same lock that performs the reservation/consumption transition.

    Trust boundary
    --------------
    A local store cannot prove human approval. It prevents concurrent or
    restarted processes from reusing the same record; it does not protect
    against an attacker who can rewrite the store files directly.
    """

    _STATE_KEYS = frozenset({
        "schema_version",
        "authorizations",
        "nonce_index",
        "journal_sequence",
        "last_transition_id",
    })
    _RECORD_KEYS = frozenset({
        "schema_version",
        "authorization_id",
        "nonce_sha256",
        "actor",
        "approved_at",
        "expires_at",
        "studio_id",
        "place",
        "place_id",
        "game_id",
        "creator_id",
        "creator_type",
        "is_unsaved",
        "user_id",
        "run_id",
        "spec_sha256",
        "asset_id",
        "asset_status",
        "allowed_actions",
        "max_objects",
        "evidence_require_durable_files",
        "evidence_required_capture_ids",
        "acknowledge_no_save_publish_upload",
        "state",
        "created_at",
        "updated_at",
        "transitions",
        "reservation",
        "consumption",
        "terminal_reason",
        "recovery_grants",
    })

    def __init__(self, root: Path | str,
                 clock: Callable[[], datetime] | None = None,
                 lock_timeout: float = 10.0):
        self.root = Path(root)
        self.state_path = self.root / "state.json"
        self.journal_path = self.root / "journal.jsonl"
        self.lock_path = self.root / "store.lock"
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self.lock_timeout = float(lock_timeout)

    # -- public lifecycle ------------------------------------------------
    def prepare(self, authorization: LiveRunAuthorization, *,
                now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(authorization, LiveRunAuthorization):
            raise ConfigurationError("authorization must be a LiveRunAuthorization")
        moment = self._now(now)
        if moment >= _coerce_utc(authorization.expires_at, "expires_at"):
            raise AuthorizationExpired("authorization has expired")
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            self._assert_no_duplicate_locked(state, authorization)
            record = self._new_record(authorization, moment)
            self._transition_locked(
                state, journal, authorization.authorization_id,
                transition="prepare", to_state="prepared", now=moment,
                details={"record": copy.deepcopy(record)},
                mutate=lambda current: self._insert_record_locked(
                    current, record
                ),
            )
            return self._record_status(state, authorization.authorization_id)

    def validate(self, authorization: LiveRunAuthorization, spec: Any,
                 plan: Any, identity: Any, *,
                 now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(authorization, LiveRunAuthorization):
            raise ConfigurationError("authorization must be a LiveRunAuthorization")
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = self._require_record_locked(state, authorization)
            if record["state"] in ("prepared", "validated"):
                self._expire_if_needed_locked(
                    state, journal, record, moment
                )
            if record["state"] == "validated":
                return self._record_status(state, authorization.authorization_id)
            if record["state"] != "prepared":
                self._raise_for_state(record)
            authorization.validate_for_spec(spec, plan, identity, now=moment)
            self._transition_locked(
                state, journal, authorization.authorization_id,
                transition="validate", to_state="validated", now=moment,
                details={
                    "spec_sha256": authorization.spec_sha256,
                    "run_id": authorization.run_id,
                },
                mutate=lambda current: None,
            )
            return self._record_status(state, authorization.authorization_id)

    def reserve(self, authorization: LiveRunAuthorization, spec: Any,
                plan: Any, identity: Any, *,
                now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(authorization, LiveRunAuthorization):
            raise ConfigurationError("authorization must be a LiveRunAuthorization")
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = state["authorizations"].get(authorization.authorization_id)
            if record is None:
                if moment >= _coerce_utc(
                    authorization.expires_at, "expires_at"
                ):
                    raise AuthorizationExpired("authorization has expired")
                # Match prepare(): a deterministic duplicate must be refused
                # before the append-only journal receives an intent.
                self._assert_no_duplicate_locked(state, authorization)
                record = self._new_record(authorization, moment)
                self._transition_locked(
                    state, journal, authorization.authorization_id,
                    transition="prepare", to_state="prepared", now=moment,
                    details={"record": copy.deepcopy(record)},
                    mutate=lambda current: self._insert_record_locked(
                        current, record
                    ),
                )
            else:
                self._assert_authorization_matches_record(authorization, record)
                if record["state"] in ("prepared", "validated", "reserved"):
                    self._expire_if_needed_locked(
                        state, journal, record, moment
                    )
            if record["state"] in ("reserved", "consumed"):
                raise AuthorizationReplay(
                    "authorization has already been reserved or consumed"
                )
            if record["state"] in ("expired", "refused"):
                self._raise_for_state(record)
            if record["state"] == "prepared":
                authorization.validate_for_spec(spec, plan, identity, now=moment)
                self._transition_locked(
                    state, journal, authorization.authorization_id,
                    transition="validate", to_state="validated", now=moment,
                    details={
                        "spec_sha256": authorization.spec_sha256,
                        "run_id": authorization.run_id,
                    },
                    mutate=lambda current: None,
                )
            elif record["state"] != "validated":
                raise AuthorizationStateError(
                    f"cannot reserve from state {record['state']!r}"
                )
            authorization.validate_for_spec(spec, plan, identity, now=moment)
            reservation = {
                "reservation_id": uuid.uuid4().hex,
                "run_id": authorization.run_id,
                "spec_sha256": authorization.spec_sha256,
                "asset_id": authorization.asset_id,
                "studio_id": authorization.studio_id,
                "place": authorization.place,
                "place_id": authorization.place_id,
                "game_id": authorization.game_id,
                "creator_id": authorization.creator_id,
                "creator_type": authorization.creator_type,
                "is_unsaved": authorization.is_unsaved,
                "user_id": authorization.user_id,
                "max_objects": authorization.max_objects,
                "reserved_at": self._iso(moment),
            }
            self._transition_locked(
                state, journal, authorization.authorization_id,
                transition="reserve", to_state="reserved", now=moment,
                details={"reservation": copy.deepcopy(reservation)},
                mutate=lambda current: self._set_reservation_locked(
                    current, authorization.authorization_id, reservation
                ),
            )
            return self._record_status(state, authorization.authorization_id)

    def check_mutation(self, authorization: LiveRunAuthorization, action: str,
                       *, spec_sha256: str | None = None,
                       now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(authorization, LiveRunAuthorization):
            raise ConfigurationError("authorization must be a LiveRunAuthorization")
        if action not in MUTATION_ACTIONS:
            raise AuthorizationError(f"unknown mutation action: {action!r}")
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = self._require_record_locked(state, authorization)
            if record["state"] == "consumed":
                raise AuthorizationReplay(
                    "authorization was consumed and cannot authorize another run"
                )
            if record["state"] in ("expired", "refused"):
                self._raise_for_state(record)
            if record["state"] != "reserved":
                raise AuthorizationStateError(
                    "authorization is not reserved for a run"
                )
            self._expire_if_needed_locked(state, journal, record, moment)
            self._assert_action_locked(record, action)
            self._assert_reservation_binding_locked(
                record, authorization, spec_sha256
            )
            return self._record_status(state, authorization.authorization_id)

    def consume(self, authorization: LiveRunAuthorization, action: str,
                *, spec_sha256: str | None = None,
                now: datetime | None = None) -> dict[str, Any]:
        if not isinstance(authorization, LiveRunAuthorization):
            raise ConfigurationError("authorization must be a LiveRunAuthorization")
        if action not in MUTATION_ACTIONS:
            raise AuthorizationError(f"unknown mutation action: {action!r}")
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = self._require_record_locked(state, authorization)
            if record["state"] == "consumed":
                raise AuthorizationReplay(
                    "authorization was consumed and cannot be consumed twice"
                )
            if record["state"] in ("expired", "refused"):
                self._raise_for_state(record)
            if record["state"] != "reserved":
                raise AuthorizationStateError(
                    "authorization is not reserved for a run"
                )
            self._expire_if_needed_locked(state, journal, record, moment)
            self._assert_action_locked(record, action)
            self._assert_reservation_binding_locked(
                record, authorization, spec_sha256
            )
            consumption = {
                "consumed_at": self._iso(moment),
                "action": action,
                "run_id": record["run_id"],
                "spec_sha256": record["spec_sha256"],
            }
            self._transition_locked(
                state, journal, authorization.authorization_id,
                transition="consume", to_state="consumed", now=moment,
                details={"consumption": copy.deepcopy(consumption)},
                mutate=lambda current: self._set_consumption_locked(
                    current, authorization.authorization_id, consumption
                ),
            )
            return self._record_status(state, authorization.authorization_id)

    def expire(self, authorization_id: str, *, reason: str = "expired",
               now: datetime | None = None) -> dict[str, Any]:
        return self._terminal_transition(
            authorization_id, "expired", reason, now
        )

    def refuse(self, authorization_id: str, *, reason: str = "refused",
               now: datetime | None = None) -> dict[str, Any]:
        return self._terminal_transition(
            authorization_id, "refused", reason, now
        )

    def status(self, authorization_id: str) -> dict[str, Any]:
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, _ = self._read_state_unlocked()
            return self._record_status(state, authorization_id)

    def statuses(self) -> dict[str, dict[str, Any]]:
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, _ = self._read_state_unlocked()
            return {
                key: copy.deepcopy(value)
                for key, value in state["authorizations"].items()
            }

    def audit_log(self) -> list[dict[str, Any]]:
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            _, journal = self._read_state_unlocked()
            return copy.deepcopy(journal)

    def recovery_grant(self, authorization_id: str, one_use_nonce: str,
                       run_id: str, *, now: datetime | None = None
                       ) -> RecoveryGrant:
        """Return a cleanup-only grant bound to the original run.

        This does not change the authorization state and cannot start another
        run. It is intentionally not wired into the adapter in this milestone.
        """
        _require_nonce(one_use_nonce)
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = state["authorizations"].get(authorization_id)
            if record is None:
                raise AuthorizationStateError(
                    "authorization is not present in the store"
                )
            if record["nonce_sha256"] != hashlib.sha256(
                one_use_nonce.encode("utf-8")
            ).hexdigest():
                raise AuthorizationReplay("nonce does not match the authorization")
            if record["state"] not in ("reserved", "consumed"):
                self._raise_for_state(record)
            if record["run_id"] != run_id:
                raise AuthorizationMismatch(
                    "recovery run_id does not match the original authorization"
                )
            grant = RecoveryGrant(
                authorization_id=authorization_id,
                run_id=run_id,
                consumed=record["state"] == "consumed",
            )
            grant_event = {
                "at": self._iso(moment),
                "run_id": run_id,
                "allow_cleanup": True,
                "allow_new_objects": False,
                "allow_new_captures": False,
                "allow_uploads": False,
                "allow_new_mutations": False,
            }
            self._transition_locked(
                state, journal, authorization_id,
                transition="recovery_grant", to_state=record["state"],
                now=moment, details={"grant": copy.deepcopy(grant_event)},
                mutate=lambda current: current["authorizations"][authorization_id]
                ["recovery_grants"].append(copy.deepcopy(grant_event)),
            )
            return grant

    def recover_interrupted(self, *, now: datetime | None = None
                            ) -> dict[str, Any]:
        """Explicitly resolve one trailing intent, conservatively.

        Reservations are completed as reservations, consumptions as
        consumptions, and terminal states are never downgraded. A nonce is
        never removed. If the intent cannot be interpreted safely the store
        stays corrupt and this raises.
        """
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked(allow_ambiguous=True)
            if not journal or journal[-1]["phase"] != "intent":
                return {"recovered": False, "reason": "no_interrupted_transition"}
            intent = journal[-1]
            if state["last_transition_id"] == intent["intent_id"]:
                self._append_journal_locked({
                    "seq": int(state["journal_sequence"]),
                    "phase": "applied",
                    "intent_id": intent["intent_id"],
                    "authorization_id": intent["authorization_id"],
                    "transition": intent["transition"],
                    "to_state": intent["to_state"],
                    "at": self._iso(moment),
                    "recovered": True,
                })
                return {
                    "recovered": True,
                    "transition": intent["transition"],
                    "authorization_id": intent["authorization_id"],
                    "state": state["authorizations"].get(
                        intent["authorization_id"], {}
                    ).get("state"),
                    "note": "state was already applied; applied marker restored",
                }
            if state["journal_sequence"] != int(intent["seq"]) - 1:
                raise AuthorizationStoreCorrupt(
                    "state and journal sequence disagree around the interrupted "
                    "transition"
                )
            changed = self._apply_intent_locked(state, intent, moment)
            state["journal_sequence"] = int(intent["seq"]) + 1
            state["last_transition_id"] = intent["intent_id"]
            self._write_state_locked(state)
            self._append_journal_locked({
                "seq": int(intent["seq"]) + 1,
                "phase": "applied",
                "intent_id": intent["intent_id"],
                "authorization_id": intent["authorization_id"],
                "transition": intent["transition"],
                "to_state": intent["to_state"],
                "at": self._iso(moment),
                "recovered": True,
            })
            record = state["authorizations"].get(intent["authorization_id"], {})
            return {
                "recovered": True,
                "transition": intent["transition"],
                "authorization_id": intent["authorization_id"],
                "state": record.get("state"),
                "changed": changed,
            }

    # -- internals -------------------------------------------------------
    def _now(self, now: datetime | None) -> datetime:
        if now is None:
            value = self._clock()
        else:
            value = now
        return _require_utc(value, "now")

    @staticmethod
    def _iso(value: datetime) -> str:
        return value.astimezone(timezone.utc).replace(
            microsecond=0
        ).isoformat()

    def _ensure_root(self) -> None:
        if self.root.exists() and not self.root.is_dir():
            raise AuthorizationStoreCorrupt(
                "authorization store root exists but is not a directory"
            )
        self.root.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": AUTHORIZATION_SCHEMA_VERSION,
            "authorizations": {},
            "nonce_index": {},
            "journal_sequence": 0,
            "last_transition_id": None,
        }

    def _new_record(self, authorization: LiveRunAuthorization,
                    now: datetime) -> dict[str, Any]:
        record = authorization.structural_dict()
        record.update({
            "state": "prepared",
            "created_at": self._iso(now),
            "updated_at": self._iso(now),
            "transitions": [],
            "reservation": None,
            "consumption": None,
            "terminal_reason": None,
            "recovery_grants": [],
        })
        return record

    def _read_state_unlocked(self, *, allow_ambiguous: bool = False
                             ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        state_exists = self.state_path.exists()
        journal_exists = self.journal_path.exists()
        if not state_exists and not journal_exists:
            return self._default_state(), []
        if not state_exists:
            if allow_ambiguous:
                journal = self._load_journal_locked()
                if (
                    len(journal) == 1
                    and journal[0].get("phase") == "intent"
                    and journal[0].get("seq") == 1
                    and journal[0].get("transition") == "prepare"
                ):
                    return self._default_state(), journal
            raise AuthorizationStoreCorrupt(
                "authorization journal exists without a state file"
            )
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise AuthorizationStoreCorrupt(
                f"authorization state is unreadable: {exc}"
            ) from exc
        self._validate_state_shape(state)
        journal = self._load_journal_locked()
        if not journal and state["authorizations"]:
            raise AuthorizationStoreCorrupt(
                "authorization state exists without an audit journal"
            )
        if journal:
            last = journal[-1]
            if last["phase"] == "intent":
                if not allow_ambiguous:
                    raise AuthorizationStoreAmbiguous(
                        "authorization store has an interrupted transition; "
                        "call recover_interrupted() explicitly"
                    )
                if state["journal_sequence"] not in (
                    int(last["seq"]) - 1, int(last["seq"]) + 1
                ):
                    raise AuthorizationStoreCorrupt(
                        "interrupted transition is inconsistent with state"
                    )
            else:
                if state["journal_sequence"] != int(last["seq"]):
                    raise AuthorizationStoreCorrupt(
                        "authorization state and journal sequence disagree"
                    )
                if state["last_transition_id"] != last["intent_id"]:
                    raise AuthorizationStoreCorrupt(
                        "authorization state and journal transition disagree"
                    )
        elif state["journal_sequence"] != 0:
            raise AuthorizationStoreCorrupt(
                "authorization state has a sequence but no journal"
            )
        self._validate_state_semantics(state)
        return state, journal

    def _load_journal_locked(self) -> list[dict[str, Any]]:
        if not self.journal_path.exists():
            return []
        records: list[dict[str, Any]] = []
        try:
            lines = self.journal_path.read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise AuthorizationStoreCorrupt(
                f"authorization journal is unreadable: {exc}"
            ) from exc
        for line in lines:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise AuthorizationStoreCorrupt(
                    "authorization journal contains a partial record"
                ) from exc
            if not isinstance(record, dict):
                raise AuthorizationStoreCorrupt(
                    "authorization journal record must be an object"
                )
            records.append(record)
        for index, record in enumerate(records, start=1):
            if record.get("seq") != index:
                raise AuthorizationStoreCorrupt(
                    "authorization journal sequence is not continuous"
                )
            if record.get("phase") not in ("intent", "applied"):
                raise AuthorizationStoreCorrupt(
                    "authorization journal has an unknown phase"
                )
            for field in ("intent_id", "authorization_id", "transition",
                          "to_state", "at"):
                if not isinstance(record.get(field), str) or not record[field]:
                    raise AuthorizationStoreCorrupt(
                        f"authorization journal record is missing {field}"
                    )
        for index in range(0, len(records), 2):
            intent = records[index]
            if intent["phase"] != "intent":
                raise AuthorizationStoreCorrupt(
                    "authorization journal does not start with an intent"
                )
            if index + 1 < len(records):
                applied = records[index + 1]
                if applied["phase"] != "applied":
                    raise AuthorizationStoreCorrupt(
                        "authorization journal intent is not followed by applied"
                    )
                if (
                    applied["intent_id"] != intent["intent_id"]
                    or applied["authorization_id"] != intent["authorization_id"]
                    or applied["transition"] != intent["transition"]
                ):
                    raise AuthorizationStoreCorrupt(
                        "authorization journal intent/applied pair disagrees"
                    )
            elif index != len(records) - 1:
                raise AuthorizationStoreCorrupt(
                    "authorization journal ordering is invalid"
                )
        return records

    def _validate_state_shape(self, state: Any) -> None:
        if not isinstance(state, dict):
            raise AuthorizationStoreCorrupt("authorization state must be an object")
        if set(state.keys()) != set(self._STATE_KEYS):
            raise AuthorizationStoreCorrupt(
                "authorization state has an unsupported shape"
            )
        if state["schema_version"] != AUTHORIZATION_SCHEMA_VERSION:
            raise AuthorizationStoreCorrupt(
                "unsupported authorization store schema_version"
            )
        if not isinstance(state["authorizations"], dict):
            raise AuthorizationStoreCorrupt("authorizations must be an object")
        if not isinstance(state["nonce_index"], dict):
            raise AuthorizationStoreCorrupt("nonce_index must be an object")
        if (isinstance(state["journal_sequence"], bool)
                or not isinstance(state["journal_sequence"], int)
                or state["journal_sequence"] < 0):
            raise AuthorizationStoreCorrupt("journal_sequence must be a non-negative integer")
        if state["last_transition_id"] is not None and (
            not isinstance(state["last_transition_id"], str)
            or not state["last_transition_id"]
        ):
            raise AuthorizationStoreCorrupt(
                "last_transition_id must be null or a non-empty string"
            )
        for auth_id, record in state["authorizations"].items():
            if not isinstance(auth_id, str) or not auth_id:
                raise AuthorizationStoreCorrupt(
                    "authorization IDs must be non-empty strings"
                )
            if not isinstance(record, dict):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} must be an object"
                )
            if set(record.keys()) != set(self._RECORD_KEYS):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an unsupported shape"
                )
            if record["authorization_id"] != auth_id:
                raise AuthorizationStoreCorrupt(
                    "authorization record key does not match its ID"
                )
            if record["state"] not in AUTHORIZATION_STATES:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an unknown state"
                )

    def _validate_state_semantics(self, state: dict[str, Any]) -> None:
        seen_nonces: dict[str, str] = {}
        for auth_id, record in state["authorizations"].items():
            nonce_hash = record["nonce_sha256"]
            if not isinstance(nonce_hash, str) or _SHA256_RE.fullmatch(
                nonce_hash
            ) is None:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an invalid nonce digest"
                )
            if nonce_hash in seen_nonces:
                raise AuthorizationStoreCorrupt(
                    "two authorizations share a nonce digest"
                )
            seen_nonces[nonce_hash] = auth_id
            if state["nonce_index"].get(nonce_hash) != auth_id:
                raise AuthorizationStoreCorrupt(
                    f"nonce index does not point at {auth_id!r}"
                )
            if record["schema_version"] != AUTHORIZATION_SCHEMA_VERSION:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an unsupported schema"
                )
            for field in ("actor", "studio_id", "place", "run_id"):
                if not isinstance(record[field], str) or not record[field]:
                    raise AuthorizationStoreCorrupt(
                        f"authorization {auth_id!r} has an invalid {field}"
                    )
            if not isinstance(record["spec_sha256"], str) or _SHA256_RE.fullmatch(
                record["spec_sha256"]
            ) is None:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an invalid spec hash"
                )
            asset_id = record["asset_id"]
            if (not isinstance(asset_id, str)
                    or asset_id not in PINNED_TEST_ASSETS
                    or record["asset_status"] != PINNED_TEST_ASSETS[asset_id]):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an unpinned asset"
                )
            for field, minimum in (
                ("place_id", 0), ("game_id", 0), ("creator_id", 0),
                ("user_id", 1), ("max_objects", 1),
            ):
                value = record[field]
                if (isinstance(value, bool) or not isinstance(value, int)
                        or value < minimum):
                    raise AuthorizationStoreCorrupt(
                        f"authorization {auth_id!r} has an invalid {field}"
                    )
            if record["max_objects"] > MAX_AUTHORIZED_OBJECTS:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has a broad object ceiling"
                )
            if not isinstance(record["is_unsaved"], bool) or record[
                "creator_type"
            ] not in ("user", "group"):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an invalid identity"
                )
            if record["acknowledge_no_save_publish_upload"] is not True:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} lacks the no-save acknowledgement"
                )
            if not isinstance(record["evidence_require_durable_files"], bool):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has invalid evidence requirements"
                )
            evidence_ids = record["evidence_required_capture_ids"]
            if (not isinstance(evidence_ids, list) or not evidence_ids
                    or len(set(evidence_ids)) != len(evidence_ids)
                    or any(not isinstance(item, str) or not item
                           for item in evidence_ids)):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has invalid evidence requirements"
                )
            try:
                approved = _coerce_utc(record["approved_at"], "approved_at")
                expires = _coerce_utc(record["expires_at"], "expires_at")
            except ConfigurationError as exc:
                raise AuthorizationStoreCorrupt(str(exc)) from exc
            if expires <= approved:
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an invalid approval window"
                )
            actions = record["allowed_actions"]
            if (not isinstance(actions, list) or not actions
                    or len(set(actions)) != len(actions)
                    or any(not isinstance(action, str)
                           or action not in MUTATION_ACTIONS
                           for action in actions)):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} has an invalid action set"
                )
            if (not isinstance(record["transitions"], list)
                    or not record["transitions"]):
                raise AuthorizationStoreCorrupt(
                    f"authorization {auth_id!r} transitions are missing"
                )
            if record["state"] == "reserved" and not isinstance(
                record["reservation"], dict
            ):
                raise AuthorizationStoreCorrupt(
                    f"reserved authorization {auth_id!r} has no reservation"
                )
            if record["state"] == "consumed" and not isinstance(
                record["consumption"], dict
            ):
                raise AuthorizationStoreCorrupt(
                    f"consumed authorization {auth_id!r} has no consumption"
                )
            if record["transitions"]:
                last_transition = record["transitions"][-1]
                if not isinstance(last_transition, dict) or (
                    last_transition.get("state") != record["state"]
                ):
                    raise AuthorizationStoreCorrupt(
                        f"authorization {auth_id!r} transition history is "
                        "inconsistent"
                    )
        if set(state["nonce_index"]) != set(seen_nonces):
            raise AuthorizationStoreCorrupt(
                "nonce index contains an unknown digest"
            )
        for indexed_id in state["nonce_index"].values():
            if not isinstance(indexed_id, str) or (
                indexed_id not in state["authorizations"]
            ):
                raise AuthorizationStoreCorrupt(
                    "nonce index references a missing authorization"
                )
        if state["authorizations"] and state["last_transition_id"] is None:
            raise AuthorizationStoreCorrupt(
                "authorization state is missing its last transition"
            )

    def _assert_no_duplicate_locked(self, state: dict[str, Any],
                                    authorization: LiveRunAuthorization) -> None:
        if authorization.authorization_id in state["authorizations"]:
            raise DuplicateAuthorization(
                "authorization ID already exists in the store"
            )
        if authorization.nonce_sha256 in state["nonce_index"]:
            raise DuplicateAuthorization(
                "one-use nonce already exists in the store"
            )

    def _insert_record_locked(self, state: dict[str, Any],
                              record: dict[str, Any]) -> None:
        auth_id = record["authorization_id"]
        nonce_hash = record["nonce_sha256"]
        if auth_id in state["authorizations"]:
            raise DuplicateAuthorization(
                "authorization ID already exists in the store"
            )
        if nonce_hash in state["nonce_index"]:
            raise DuplicateAuthorization(
                "one-use nonce already exists in the store"
            )
        state["authorizations"][auth_id] = copy.deepcopy(record)
        state["nonce_index"][nonce_hash] = auth_id

    def _require_record_locked(self, state: dict[str, Any],
                               authorization: LiveRunAuthorization
                               ) -> dict[str, Any]:
        record = state["authorizations"].get(authorization.authorization_id)
        if record is None:
            raise AuthorizationStateError(
                "authorization is not present in the store"
            )
        if record["nonce_sha256"] != authorization.nonce_sha256:
            raise AuthorizationReplay("nonce does not match the authorization")
        self._assert_authorization_matches_record(authorization, record)
        return record

    @staticmethod
    def _assert_authorization_matches_record(
        authorization: LiveRunAuthorization, record: dict[str, Any]
    ) -> None:
        expected = authorization.structural_dict()
        actual = {key: record.get(key) for key in expected}
        if actual != expected:
            raise AuthorizationMismatch(
                "supplied authorization does not match the stored declaration"
            )

    def _expire_if_needed_locked(self, state: dict[str, Any],
                                 journal: list[dict[str, Any]],
                                 record: dict[str, Any],
                                 now: datetime) -> None:
        expires = _coerce_utc(record["expires_at"], "expires_at")
        if now < expires:
            return
        self._transition_locked(
            state, journal, record["authorization_id"],
            transition="expire", to_state="expired", now=now,
            details={"reason": "expired"},
            mutate=lambda current: self._set_terminal_locked(
                current, record["authorization_id"], "expired", "expired"
            ),
        )
        raise AuthorizationExpired("authorization has expired")

    def _raise_for_state(self, record: dict[str, Any]) -> NoReturn:
        state = record["state"]
        if state == "expired":
            raise AuthorizationExpired("authorization has expired")
        if state == "consumed":
            raise AuthorizationReplay(
                "authorization was consumed and cannot authorize another run"
            )
        if state == "refused":
            raise AuthorizationStateError("authorization was refused")
        raise AuthorizationStateError(
            f"authorization is in state {state!r}, not the required state"
        )

    @staticmethod
    def _assert_action_locked(record: dict[str, Any], action: str) -> None:
        if action not in record["allowed_actions"]:
            raise AuthorizationError(
                f"authorization does not cover {action!r}"
            )

    @staticmethod
    def _assert_reservation_binding_locked(
        record: dict[str, Any], authorization: LiveRunAuthorization,
        spec_sha256: str | None,
    ) -> None:
        reservation = record["reservation"]
        if not isinstance(reservation, dict):
            raise AuthorizationStoreCorrupt(
                "reserved authorization has no reservation record"
            )
        for field in (
            "run_id", "studio_id", "place", "place_id", "game_id",
            "creator_id", "creator_type", "is_unsaved", "user_id",
            "spec_sha256", "asset_id",
        ):
            if getattr(authorization, field) != reservation.get(field):
                raise AuthorizationMismatch(
                    f"authorization {field} does not match the reservation"
                )
            if record.get(field) != reservation.get(field):
                raise AuthorizationMismatch(
                    f"stored authorization {field} does not match the reservation"
                )
        if spec_sha256 is not None and spec_sha256 != reservation["spec_sha256"]:
            raise AuthorizationMismatch(
                "supplied spec_sha256 does not match the reservation"
            )

    def _set_reservation_locked(self, state: dict[str, Any], auth_id: str,
                                reservation: dict[str, Any]) -> None:
        record = state["authorizations"][auth_id]
        record["reservation"] = copy.deepcopy(reservation)
        record["state"] = "reserved"

    def _set_consumption_locked(self, state: dict[str, Any], auth_id: str,
                                consumption: dict[str, Any]) -> None:
        record = state["authorizations"][auth_id]
        record["consumption"] = copy.deepcopy(consumption)
        record["state"] = "consumed"

    def _set_terminal_locked(self, state: dict[str, Any], auth_id: str,
                             terminal_state: str, reason: str) -> None:
        record = state["authorizations"][auth_id]
        record["state"] = terminal_state
        record["terminal_reason"] = reason

    def _terminal_transition(self, authorization_id: str, target: str,
                             reason: str, now: datetime | None
                             ) -> dict[str, Any]:
        moment = self._now(now)
        self._ensure_root()
        with _StoreLock(self.lock_path, self.lock_timeout):
            state, journal = self._read_state_unlocked()
            record = state["authorizations"].get(authorization_id)
            if record is None:
                raise AuthorizationStateError(
                    "authorization is not present in the store"
                )
            if record["state"] == target:
                return self._record_status(state, authorization_id)
            if record["state"] == "consumed":
                raise AuthorizationStateError(
                    "a consumed authorization is terminal and cannot be changed"
                )
            if record["state"] in ("expired", "refused"):
                raise AuthorizationStateError(
                    f"authorization is already terminal ({record['state']})"
                )
            self._transition_locked(
                state, journal, authorization_id,
                transition=("expire" if target == "expired" else "refuse"),
                to_state=target, now=moment,
                details={"reason": reason},
                mutate=lambda current: self._set_terminal_locked(
                    current, authorization_id, target, reason
                ),
            )
            return self._record_status(state, authorization_id)

    def _transition_locked(self, state: dict[str, Any],
                           journal: list[dict[str, Any]],
                           authorization_id: str, *, transition: str,
                           to_state: str, now: datetime,
                           details: dict[str, Any],
                           mutate: Callable[[dict[str, Any]], None]) -> None:
        from_state = state["authorizations"].get(
            authorization_id, {}
        ).get("state")
        intent_id = uuid.uuid4().hex
        intent_seq = int(state["journal_sequence"]) + 1
        applied_seq = intent_seq + 1
        intent = {
            "seq": intent_seq,
            "phase": "intent",
            "intent_id": intent_id,
            "authorization_id": authorization_id,
            "transition": transition,
            "from_state": from_state,
            "to_state": to_state,
            "at": self._iso(now),
            "details": copy.deepcopy(details),
        }
        self._append_journal_locked(intent)
        state["journal_sequence"] = applied_seq
        state["last_transition_id"] = intent_id
        mutate(state)
        record = state["authorizations"].get(authorization_id)
        if record is not None:
            record["state"] = to_state
            record["transitions"].append({
                "state": to_state,
                "at": self._iso(now),
                "reason": details.get("reason", transition),
            })
            record["updated_at"] = self._iso(now)
        self._write_state_locked(state)
        self._append_journal_locked({
            "seq": applied_seq,
            "phase": "applied",
            "intent_id": intent_id,
            "authorization_id": authorization_id,
            "transition": transition,
            "to_state": to_state,
            "at": self._iso(now),
        })

    def _apply_intent_locked(self, state: dict[str, Any],
                             intent: dict[str, Any],
                             now: datetime) -> bool:
        auth_id = intent["authorization_id"]
        transition = intent["transition"]
        details = intent.get("details")
        if not isinstance(details, dict):
            raise AuthorizationStoreCorrupt(
                "interrupted transition has no recoverable details"
            )
        if transition == "prepare":
            record = details.get("record")
            if not isinstance(record, dict):
                raise AuthorizationStoreCorrupt(
                    "interrupted prepare has no record"
                )
            if auth_id in state["authorizations"]:
                return False
            nonce_hash = record.get("nonce_sha256")
            if nonce_hash in state["nonce_index"]:
                raise DuplicateAuthorization(
                    "interrupted prepare would duplicate a nonce"
                )
            state["authorizations"][auth_id] = copy.deepcopy(record)
            state["nonce_index"][nonce_hash] = auth_id
            record = state["authorizations"][auth_id]
            record["transitions"].append({
                "state": "prepared",
                "at": self._iso(now),
                "reason": "recovered prepare",
                "recovered": True,
            })
            record["updated_at"] = self._iso(now)
            return True
        record = state["authorizations"].get(auth_id)
        if record is None:
            raise AuthorizationStoreCorrupt(
                "interrupted transition references a missing authorization"
            )
        current = record["state"]
        if current in ("expired", "refused"):
            return False
        if transition == "validate":
            if current in ("prepared", "validated"):
                record["state"] = "validated"
            else:
                return False
        elif transition == "reserve":
            if current in ("prepared", "validated"):
                reservation = details.get("reservation")
                if not isinstance(reservation, dict):
                    raise AuthorizationStoreCorrupt(
                        "interrupted reserve has no reservation"
                    )
                record["reservation"] = copy.deepcopy(reservation)
                record["state"] = "reserved"
            elif current not in ("reserved", "consumed"):
                return False
            else:
                return False
        elif transition == "consume":
            if current == "reserved":
                consumption = details.get("consumption")
                if not isinstance(consumption, dict):
                    raise AuthorizationStoreCorrupt(
                        "interrupted consume has no consumption record"
                    )
                record["consumption"] = copy.deepcopy(consumption)
                record["state"] = "consumed"
            elif current == "consumed":
                return False
            else:
                raise AuthorizationStoreCorrupt(
                    "interrupted consume intent is not backed by a reservation"
                )
        elif transition == "recovery_grant":
            grant = details.get("grant")
            if current not in ("reserved", "consumed") or (
                not isinstance(grant, dict)
                or grant.get("run_id") != record["run_id"]
                or grant.get("allow_cleanup") is not True
                or any(grant.get(field) is not False for field in (
                    "allow_new_objects", "allow_new_captures", "allow_uploads",
                    "allow_new_mutations",
                ))
            ):
                raise AuthorizationStoreCorrupt(
                    "interrupted recovery grant is not cleanup-only and run-bound"
                )
            record["recovery_grants"].append(copy.deepcopy(grant))
        elif transition in ("expire", "refuse"):
            if current == "consumed":
                return False
            record["state"] = intent["to_state"]
            record["terminal_reason"] = details.get("reason", transition)
        else:
            raise AuthorizationStoreCorrupt(
                f"cannot recover unknown transition {transition!r}"
            )
        record["transitions"].append({
            "state": record["state"],
            "at": self._iso(now),
            "reason": f"recovered {transition}",
            "recovered": True,
        })
        record["updated_at"] = self._iso(now)
        return True

    def _write_state_locked(self, state: dict[str, Any]) -> None:
        document = json.dumps(
            state, sort_keys=True, indent=2, ensure_ascii=False
        ).encode("utf-8")
        temporary = self.root / f".state.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("wb") as stream:
                stream.write(document)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

    def _append_journal_locked(self, record: dict[str, Any]) -> None:
        line = json.dumps(
            record, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        )
        with self.journal_path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(line + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def _record_status(self, state: dict[str, Any],
                       authorization_id: str) -> dict[str, Any]:
        record = state["authorizations"].get(authorization_id)
        if record is None:
            raise AuthorizationStateError(
                "authorization is not present in the store"
            )
        return copy.deepcopy(record)


@dataclass(frozen=True)
class McpAdapterConfig:
    """Explicit target identity and optional authorization for one run.

    ``identity`` is required for :meth:`McpStudioAdapter.snapshot` and
    :meth:`McpStudioAdapter.read_verified_identity`. It is optional at
    construction so the read-only raw probe and the mutation-blocking skeleton
    remain usable without a full identity declaration, but no snapshot path
    will treat an unspecified identity as acceptable.
    """

    studio_id: str
    place: str
    mode: str = "Edit"
    run_id: str | None = None
    authorization: LiveRunAuthorization | None = None
    authorization_store: AuthorizationStore | None = None
    spec_sha256: str | None = None
    asset_id: str | None = None
    identity: StudioIdentity | None = None

    def __post_init__(self) -> None:
        _require_text(self.studio_id, "studio_id", ConfigurationError)
        _require_text(self.place, "place", ConfigurationError)
        if not isinstance(self.mode, str) or self.mode.strip().lower() != "edit":
            raise ConfigurationError("mode must be 'Edit' for a C1C run")
        object.__setattr__(self, "mode", "edit")
        if self.run_id is not None:
            _require_text(self.run_id, "run_id", ConfigurationError)
        if self.spec_sha256 is not None:
            _require_sha256(self.spec_sha256, "spec_sha256")
        if self.asset_id is not None:
            _require_asset_id(self.asset_id)
            if self.asset_id not in PINNED_TEST_ASSETS:
                raise ConfigurationError(
                    "asset_id is not on the pinned test-asset list"
                )
        if self.authorization_store is not None and not isinstance(
            self.authorization_store, AuthorizationStore
        ):
            raise ConfigurationError(
                "authorization_store must be an AuthorizationStore or None"
            )
        if self.identity is not None:
            if not isinstance(self.identity, StudioIdentity):
                raise ConfigurationError(
                    "identity must be a StudioIdentity or None"
                )
            if self.identity.studio_id != self.studio_id:
                raise ConfigurationError(
                    "identity studio_id does not match the adapter configuration"
                )
            if self.identity.place != self.place:
                raise ConfigurationError(
                    "identity place does not match the adapter configuration"
                )
            if self.identity.mode != self.mode:
                raise ConfigurationError(
                    "identity mode does not match the adapter configuration"
                )
        if self.authorization is not None:
            if not isinstance(self.authorization, LiveRunAuthorization):
                raise ConfigurationError(
                    "authorization must be a LiveRunAuthorization or None"
                )
            if self.run_id is None:
                raise ConfigurationError(
                    "run_id is required when an authorization is supplied"
                )
            self.authorization.validate_for(self)
        if self.authorization_store is not None:
            if self.authorization is None:
                raise ConfigurationError(
                    "an authorization_store requires an authorization"
                )
            if self.run_id is None:
                raise ConfigurationError(
                    "run_id is required when an authorization store is supplied"
                )


class McpTransport(Protocol):
    """Injection seam for Roblox Studio MCP tool calls.

    A real transport would forward to the connected MCP client. Tests inject a
    local recording double. The adapter validates the tool name before calling
    it; the transport is never contacted during construction.
    """

    def call(self, tool: str, payload: dict[str, Any]) -> Any: ...


class NoMcpTransport:
    """Fail-closed placeholder used when no transport is injected."""

    def call(self, tool: str, payload: dict[str, Any]) -> Any:
        raise TransportUnavailable(
            "no MCP transport injected; the offline adapter cannot contact Studio"
        )


class McpStudioAdapter:
    """Offline read-only snapshot implementation of the ``StudioAdapter``.

    The only implemented transport uses are read-only ``get_studio_state`` and
    a fixed-source ``execute_luau`` hierarchy query. Every protocol mutation is
    authorization-gated and then blocked with
    :class:`McpAdapterNotImplemented`. No upload, save or publish method
    exists, and no MCP tool outside :data:`ALLOWED_MCP_TOOLS` is accepted.
    """

    name = "mcp-c1c-skeleton"
    simulates_studio = False
    supports_viewport_restore = False

    def __init__(self, config: McpAdapterConfig,
                 transport: McpTransport | None = None):
        if not isinstance(config, McpAdapterConfig):
            raise ConfigurationError("config must be an McpAdapterConfig")
        self.config = config
        self._transport: McpTransport = (
            transport if transport is not None else NoMcpTransport()
        )
        if not callable(getattr(self._transport, "call", None)):
            raise ConfigurationError(
                "transport must provide a callable call(tool, payload)"
            )
        self.assert_tool_policy((STATE_TOOL,))

    # -- policy ----------------------------------------------------------
    @staticmethod
    def assert_tool_policy(tools: Iterable[str]) -> tuple[str, ...]:
        """Fail closed unless every named MCP tool is explicitly allowed."""
        checked = tuple(tools)
        for tool in checked:
            if not isinstance(tool, str) or not tool:
                raise ToolPolicyError("MCP tool name must be a non-empty string")
            if tool in FORBIDDEN_MCP_TOOLS:
                raise ToolPolicyError(f"MCP tool is permanently forbidden: {tool}")
            if tool not in ALLOWED_MCP_TOOLS:
                raise ToolPolicyError(f"MCP tool is not on the allow-list: {tool}")
        return checked

    def _require_mutation(self, action: str, operation: str) -> NoReturn:
        authorization = self.config.authorization
        if authorization is None:
            raise AuthorizationError(
                f"{operation} is blocked: no operator authorization is configured"
            )
        if not authorization.covers(action):
            raise AuthorizationError(
                f"{operation} is blocked: authorization does not cover {action!r}"
            )
        authorization.validate_for(self.config)
        store = self.config.authorization_store
        if store is not None:
            store.check_mutation(
                authorization, action, spec_sha256=self.config.spec_sha256
            )
        # Consumption is deliberately NOT performed here. This adapter never
        # dispatches a live mutation, so it cannot honestly claim that one
        # began. A future mutation implementation must call
        # AuthorizationStore.consume() under the store lock immediately before
        # the first dispatch. Consuming on a NotImplemented attempt would burn
        # an authorization without touching Studio.
        raise McpAdapterNotImplemented(
            f"{operation} is not implemented; "
            "no live Studio mutation is authorized by this adapter"
        )

    def _require_identity(self) -> StudioIdentity:
        if self.config.identity is None:
            raise ConfigurationError(
                "an explicit expected Studio identity is required for a "
                "snapshot or identity verification"
            )
        return self.config.identity

    # -- read-only seam --------------------------------------------------
    def read_studio_state(self) -> dict[str, Any]:
        """Call the allow-listed read-only state tool through the transport.

        Returns the raw decoded mapping. Envelope decoding and identity
        validation are separate steps performed by
        :meth:`read_verified_identity` and :meth:`snapshot`.
        """
        self.assert_tool_policy((STATE_TOOL,))
        result = self._transport.call(
            STATE_TOOL, {"studio_id": self.config.studio_id}
        )
        if not isinstance(result, Mapping):
            raise TransportResponseError(
                "get_studio_state must return a mapping for the adapter"
            )
        return dict(result)

    def read_verified_identity(self) -> VerifiedStudioIdentity:
        """Read and validate the connected Studio/place/creator/user identity."""
        expected = self._require_identity()
        raw = self.read_studio_state()
        payload = decode_mcp_payload(raw, context=STATE_TOOL)
        return verify_state_payload(payload, expected)

    def snapshot(self) -> dict[str, Any]:
        """Return the existing complete-snapshot contract, read-only and offline.

        Calls ``get_studio_state`` first and fails before any hierarchy query if
        the identity is missing, wrong or contradictory. Then sends the fixed
        read-only Luau source and normalizes the response into the
        ``c1c_harness`` snapshot shape. The result is passed through the
        existing :func:`c1c_harness.validate_snapshot`; any structural issue is
        rejected instead of returning a partially trusted snapshot.
        """
        expected = self._require_identity()
        from c1c_harness import validate_snapshot

        identity = self.read_verified_identity()

        self.assert_tool_policy((LUAU_TOOL,))
        result = self._transport.call(LUAU_TOOL, {
            "studio_id": expected.studio_id,
            "datamodel_type": "Edit",
            "code": READ_ONLY_SNAPSHOT_LUAU,
        })
        payload = decode_mcp_payload(result, context=LUAU_TOOL)
        snapshot = normalize_snapshot_payload(
            payload, identity, adapter_name=self.name
        )

        integrity = validate_snapshot(snapshot)
        if integrity.get("ok") is not True or integrity.get("complete") is not True:
            raise SnapshotValidationError(integrity.get("issues", []))
        return snapshot

    # -- StudioAdapter protocol -----------------------------------------
    def create_folder(self, name: str, attributes: dict[str, Any],
                      tags: list[str]) -> str:
        self._require_mutation("create", "create_folder")

    def create_part(self, folder_path: str, name: str, attributes: dict[str, Any],
                    tags: list[str], properties: dict[str, Any]) -> str:
        self._require_mutation("create", "create_part")

    def create_texture(self, parent_path: str, name: str,
                       attributes: dict[str, Any], tags: list[str],
                       properties: dict[str, Any]) -> str:
        self._require_mutation("create", "create_texture")

    def create_label(self, parent_path: str, name: str, text: str,
                     attributes: dict[str, Any], tags: list[str],
                     properties: dict[str, Any]) -> list[str]:
        self._require_mutation("create", "create_label")

    def preload(self, asset_id: str, paths: list[str]) -> dict[str, Any]:
        self._require_mutation("create", "preload")

    def set_camera(self, camera: dict[str, Any] | None) -> None:
        self._require_mutation("camera", "set_camera")

    def set_viewport_size(self, width: int, height: int) -> bool:
        """No verified MCP viewport restore exists; report it as unsupported."""
        return False

    def rename(self, path: str, new_name: str) -> str:
        self._require_mutation("rename", "rename")

    def destroy(self, path: str) -> None:
        self._require_mutation("destroy", "destroy")

    def screenshot(self, capture_id: str,
                   camera: dict[str, Any] | None) -> "CaptureResult":
        self._require_mutation("screenshot", "screenshot")
