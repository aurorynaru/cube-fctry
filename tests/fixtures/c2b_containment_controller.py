"""R6 disposable controller; fixed synthetic child and fixed death checkpoints."""
import ctypes
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool.c2b_windows_containment import SyntheticBoundary

directory = Path(sys.argv[1])
phase = sys.argv[2]
if phase not in {"before_create", "create_return_gap", "created", "verified", "resumed", "nested"}:
    raise ValueError("fixed test checkpoint required")


class Controller(SyntheticBoundary):
    def hold(self, handles):
        with (directory / "ready.json").open("x") as stream:
            json.dump(handles, stream)
        while True:
            time.sleep(0.02)

    def _checkpoint(self, current):
        if current == phase:
            self.hold(self.handles)


if phase == "nested":
    sys.stdin.buffer.read(1)  # Outer owned restrictive job assigned before creation.
with Controller(directory, "eager" if phase == "resumed" else "marker") as boundary:
    if phase == "create_return_gap":
        original = boundary.api.CreateProcessW
        def intercepted(*args):
            result = original(*args)
            if result:
                info = ctypes.cast(args[-1], ctypes.POINTER(boundary.api.ProcessInfo)).contents
                boundary.hold({"process": info.process, "thread": info.thread})
            return result
        boundary.api.CreateProcessW = intercepted
    created = boundary.create()
    if phase == "nested":
        boundary.close()
        with (directory / "result.json").open("x") as stream:
            json.dump(boundary.report, stream)
    elif created:
        boundary.resume()
        raise RuntimeError("checkpoint unexpectedly returned")
