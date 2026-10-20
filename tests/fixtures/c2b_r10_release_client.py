"""R10 source-derived Python fake; never imports or runs OpenCode/the JS SDK.

OpenCode 733b2c627e5aec39cb33cc22373bdce33053ef2c:
  src/mcp/index.ts:39-80, src/mcp/catalog.ts:42-82,117-119.
SDK e12cbd7078db388152f6e839abdbe09ba01f3f32:
  src/types.ts:4-6, src/shared/protocol.ts:1128-1143,
  src/client/index.ts:483-534, src/shared/stdio.ts:37-39.
Paths are relative to their packages; snapshots/provenance: docs/evidence/r10-source.
Only the selected serial stdio/text-result profile is modeled. This is not the SDK.
Literals are deliberately independent of the frontend/recorder's own constants.
"""
import json
import re

TARGET = "577768ad-49d8-42f5-ac96-8c66cd12a144"


def frame(message):
    return (json.dumps(message, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


class ReleaseClient:
    def __init__(self, exchange):
        self.exchange = exchange
        self.sequence = 0
        self.sent = []
        self.aliases = {}

    def request(self, method, params=None, *, progress=False):
        # SDK spreads the request first, then appends JSON-RPC version and ID.
        message = {"method": method}
        if params is not None:
            message["params"] = params.copy()
        message.update(jsonrpc="2.0", id=self.sequence)
        self.sequence += 1
        if progress:
            message.setdefault("params", {})["_meta"] = {"progressToken": message["id"]}
        self.sent.append(message)
        raw = self.exchange(frame(message))
        response = json.loads(raw)
        if (response.get("jsonrpc") != "2.0" or type(response.get("id")) is not int or
                response["id"] != message["id"] or
                ("result" in response) == ("error" in response)):
            raise ValueError("fake release client: uncorrelated response")
        return response

    def notify(self, method, params=None):
        message = {"method": method}
        if params is not None:
            message["params"] = params
        message["jsonrpc"] = "2.0"
        self.sent.append(message)
        return self.exchange(frame(message))

    def initialize(self):
        result = self.request("initialize", {
            "protocolVersion": "2025-11-25", "capabilities": {"roots": {}},
            "clientInfo": {"name": "opencode", "version": "1.19.0"}})
        if "result" in result:
            if result["result"]["protocolVersion"] not in (
                    "2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05", "2024-10-07"):
                raise ValueError("fake release client: unsupported negotiated version")
            self.notify("notifications/initialized")
        return result

    def catalog(self, server="roblox_studio"):
        response = self.request("tools/list")
        if "result" in response:
            sanitize = lambda value: re.sub(r"[^a-zA-Z0-9_-]", "_", value)
            self.aliases = {sanitize(server) + "_" + sanitize(tool["name"]): tool["name"]
                            for tool in response["result"]["tools"]}
        return response

    def call(self, alias, arguments=None):
        return self.request("tools/call", {"name": self.aliases[alias], "arguments": arguments or {}}, progress=True)

    @staticmethod
    def text_result(response):
        """Selected text subset of SDK result validation + catalog conversion.

        Not a reimplementation of Zod/Ajv, provider transforms or plugin hooks.
        """
        if "error" in response:
            raise ValueError("MCP JSON-RPC error: " + response["error"]["message"])
        result = response["result"]
        content = result.get("content", [])
        if (type(content) is not list or type(result.get("isError", False)) is not bool or
                any(type(block) is not dict or block.get("type") != "text" or
                    type(block.get("text")) is not str for block in content)):
            raise ValueError("fake release client: outside selected text-result profile")
        if result.get("isError"):
            raise ValueError("\n\n".join(block["text"] for block in content if block["text"].strip()) or
                             "MCP tool returned an error")
        if not content and result.get("structuredContent") is not None:
            return json.dumps(result["structuredContent"], separators=(",", ":"), ensure_ascii=False)
        return "\n\n".join(block["text"] for block in content)
