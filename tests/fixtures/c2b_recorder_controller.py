"""Disposable R7 controller: fixed fixture and native-to-CRT death checkpoint."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool.c2b_native_recorder import SyntheticRecorderProcess

directory = Path(sys.argv[1])
phase = sys.argv[2]
if phase not in {"crt", "resumed"}:
    raise ValueError("fixed death checkpoint required")
process = SyntheticRecorderProcess(directory, "eager_stdio")
descendant_observer = None


def hold():
    with (directory / "ready.json").open("x") as stream:
        handles = {"process": process.boundary.handles["process"]}
        if descendant_observer is not None:
            handles["descendant"] = descendant_observer.value
        json.dump(handles, stream)
    while True:
        time.sleep(0.02)


if phase == "crt":
    def checkpoint(current):
        if current == "crt":
            hold()  # First pipe transferred to CRT, root still suspended.
    process.stdin._checkpoint = checkpoint
if not process.start():
    raise RuntimeError(process.boundary.report)
if phase == "resumed":
    # Eager descendant runs before stdin. Duplicate its exact root-owned handle,
    # never open by PID. Neither controller observer nor test observer holds job.
    until = time.monotonic() + 5
    while not ((directory / "pipe-holder.marker").exists() and
               (directory / "pipe-holder-handle.json").exists()):
        if time.monotonic() >= until:
            raise RuntimeError("descendant did not run")
        time.sleep(0.005)
    import ctypes
    from ctypes import wintypes as w
    api = process.boundary.api
    api.dll.GetCurrentProcess.restype = w.HANDLE
    api.dll.DuplicateHandle.argtypes = [w.HANDLE, w.HANDLE, w.HANDLE,
                                       ctypes.POINTER(w.HANDLE), w.DWORD, w.BOOL, w.DWORD]
    api.dll.DuplicateHandle.restype = w.BOOL
    descendant_observer = w.HANDLE()
    handle = json.loads((directory / "pipe-holder-handle.json").read_text())["process"]
    api.checked(api.dll.DuplicateHandle(process.boundary.handles["process"], handle,
        api.dll.GetCurrentProcess(), ctypes.byref(descendant_observer), 0x100000, False, 0))
    hold()
