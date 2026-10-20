"""Fixed OFFLINE R6 child. Earliest observable Python action is a marker.

This marker is not a claim of instrumentation at the native PE entry point.
All descendants run this same file with one fixed internal role.
"""
import os

with open("first-instruction.marker", "xb") as marker:
    marker.write(b"earliest observable Python fixture action\n")

import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes as w

scenario = sys.argv[1]
if scenario == "exit":
    sys.exit(0)
if scenario in ("eager", "inherited_pipe"):
    # No stdin handshake before eager creation. Explicit std handles keep the
    # output pipe open even after the root exits in inherited_pipe mode.
    child = subprocess.Popen([sys.executable, "-I", "-S", "-u", __file__, "descendant"],
                             cwd="descendant", stdin=sys.stdin, stdout=sys.stdout,
                             stderr=sys.stderr, close_fds=True)
    with open("descendant-handle.json", "x") as stream:
        json.dump({"process": int(child._handle)}, stream)
    if scenario == "inherited_pipe":
        sys.exit(0)
elif scenario == "descendant":
    with open("descendant.marker", "xb") as marker:
        marker.write(b"descendant ran\n")
elif scenario != "marker":
    raise ValueError("fixed synthetic scenario only")

# Enumerate handle *values* only inside this controlled child, not threads/PIDs.
# Test's inheritable sentinel is excluded by HANDLE_LIST; no handle is closed here.
api = ctypes.WinDLL("kernel32", use_last_error=True)
api.GetHandleInformation.argtypes = [w.HANDLE, ctypes.POINTER(w.DWORD)]
api.GetHandleInformation.restype = w.BOOL
api.GetStdHandle.argtypes = [w.DWORD]
api.GetStdHandle.restype = w.HANDLE
api.GetFileType.argtypes = [w.HANDLE]
api.GetFileType.restype = w.DWORD
sentinel = int(os.environ.get("C2B_R6_SENTINEL", "0"))
flags = w.DWORD()
os.write(1, json.dumps({"sentinel_open": bool(sentinel and api.GetHandleInformation(
    sentinel, ctypes.byref(flags))), "standard_handles_are_pipes": all(
        api.GetFileType(api.GetStdHandle(value & 0xFFFFFFFF)) == 3
        for value in (-10, -11, -12))}).encode() + b"\n")
os.write(2, b"synthetic stderr\n")
if scenario == "marker":
    if sys.stdin.buffer.read(1) == b"Q":
        with open("stdin-received.marker", "xb") as marker:
            marker.write(b"explicit stdin worked\n")
time.sleep(60)
