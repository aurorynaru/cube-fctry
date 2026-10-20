"""Reviewed R9 candidate client, not reverse-engineered installed OpenCode."""
import json
import queue

from tool.c2b_recording_supervisor import PROTOCOL, _json_frame


class SyntheticClient:
    def __init__(self, frontend):
        self.frontend = frontend
        self.sequence = 0

    def request(self, method, params=None, *, request_id=None):
        self.sequence += 1
        request = {"jsonrpc": "2.0", "id": self.sequence if request_id is None else request_id,
                   "method": method}
        if params is not None:
            request["params"] = params
        return json.loads(self.frontend.handle(_json_frame(request)))

    def notify(self, method, params=None):
        message = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            message["params"] = params
        return self.frontend.handle(_json_frame(message))

    def initialize(self):
        result = self.request("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                    "clientInfo": {"name": "R9 synthetic candidate client", "version": "1"}})
        if "result" in result:
            self.notify("notifications/initialized")
        return result

    def discovery(self):
        return self.request("tools/call", {"name": "list_roblox_studios", "arguments": {}})

    def state(self, target):
        return self.request("tools/call", {"name": "get_studio_state", "arguments": {"studio_id": target}})


class SyntheticStdio:
    """Bounded synthetic byte streams for the real serve loop; no authority data."""
    def __init__(self):
        self.input = queue.Queue(maxsize=8)
        self.output = queue.Queue(maxsize=8)
        self.closed = False

    def readline(self, limit):
        raw = self.input.get(timeout=5)
        if len(raw) > limit:
            raise ValueError("synthetic fixture frame exceeds read bound")
        return raw

    def write(self, data):
        self.output.put(bytes(data), timeout=5)
        return len(data)

    def flush(self):
        pass

    def send(self, method, params=None, *, request_id=None):
        message = {"jsonrpc": "2.0", "method": method}
        if request_id is not None:
            message["id"] = request_id
        if params is not None:
            message["params"] = params
        self.input.put(_json_frame(message), timeout=2)

    def receive(self):
        return json.loads(self.output.get(timeout=5))
