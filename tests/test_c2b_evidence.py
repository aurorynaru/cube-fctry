import concurrent.futures
import json
import tempfile
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tool import c2b_evidence as evidence

REQUEST = b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"SYNTHETIC_ONLY"}}\n'


def frame(text="synthetic", **extra):
    return (json.dumps({"jsonrpc": "2.0", "id": 1, "result": {
        "content": [{"type": "text", "text": text}], **extra}}) + "\n").encode()


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.parent = Path(self.temp.name)

    def record(self, raw, **kwargs):
        events = kwargs.pop("events", (evidence.SyntheticEvent(1, raw, end=True),))
        dest = evidence.collect_synthetic(self.parent, "observation", REQUEST, events)
        return dest, evidence.verify_synthetic(dest)

    def test_exact_bytes_hashes_and_no_compatibility_claim(self):
        raw = frame("Unicode — 雪")
        dest, receipt = self.record(raw)
        self.assertEqual((dest / "response-prefix.bin").read_bytes(), raw)
        self.assertEqual(receipt["retained_response"], evidence._digest(raw))
        self.assertTrue(receipt["full_response_claim"])
        self.assertFalse(receipt["compatibility_pass"])
        self.assertFalse(receipt["utc_verified"])

    def test_exact_size_limit_including_newline(self):
        raw = frame("")
        raw = frame("x" * (evidence.LIMIT - len(raw)))
        self.assertEqual(len(raw), evidence.LIMIT)
        _, r = self.record(raw)
        self.assertTrue(r["full_response_claim"])

    def test_oversize_prefix_never_claims_total(self):
        _, r = self.record(frame("x" * evidence.LIMIT))
        self.assertEqual(r["status"], "oversized_prefix_only")
        self.assertEqual(r["retained_response"]["bytes"], evidence.LIMIT)
        self.assertIsNone(r["total_upstream_response_bytes"])

    def test_split_multibyte_preserved(self):
        raw = frame("雪")
        events = tuple(evidence.SyntheticEvent(i, bytes([b]), end=i == len(raw)-1)
                       for i, b in enumerate(raw))
        _, r = self.record(raw, events=events)
        self.assertTrue(r["full_response_claim"])

    def test_truncated_json(self):
        _, r = self.record(frame()[:-8])
        self.assertFalse(r["full_response_claim"])

    def test_declared_truncation(self):
        _, r = self.record(frame(truncated=True))
        self.assertEqual(r["status"], "declared_or_suspected_truncation")

    def test_display_truncation_marker(self):
        _, r = self.record(frame("Output capped at 50 KB"))
        self.assertFalse(r["full_response_claim"])

    def test_silent_semantic_truncation_cannot_be_detected(self):
        _, r = self.record(frame("plausible but silently shortened upstream"))
        self.assertEqual(r["status"], "transport_complete_semantics_unverified")
        self.assertFalse(r["compatibility_pass"])

    def test_deadline_exact_and_late(self):
        for offset in (evidence.WINDOW_NS, evidence.WINDOW_NS + 1):
            with self.subTest(offset=offset):
                dest = evidence.collect_synthetic(self.parent, f"time{offset}", REQUEST,
                    (evidence.SyntheticEvent(offset, frame(), end=True),))
                r = evidence.verify_synthetic(dest)
                self.assertEqual(r["status"], "timeout")
                self.assertEqual(r["retained_response"]["bytes"], 0)

    def test_before_deadline(self):
        _, r = self.record(b"", events=(evidence.SyntheticEvent(
            evidence.WINDOW_NS - 1, frame(), end=True),))
        self.assertTrue(r["full_response_claim"])

    def test_no_end(self):
        _, r = self.record(b"", events=(evidence.SyntheticEvent(1, frame()),))
        self.assertEqual(r["status"], "incomplete_stream")

    def test_transport_failure_retains_prefix(self):
        _, r = self.record(b"", events=(evidence.SyntheticEvent(4, b'{"jsonrpc":', failure=True),))
        self.assertEqual(r["status"], "transport_failure")
        self.assertEqual(r["retained_response"]["bytes"], 11)

    def test_malformed_envelopes(self):
        cases = [b'[]\n', b'{"jsonrpc":"2.0","id":true,"result":{}}\n',
                 b'{"jsonrpc":"2.0","id":1,"id":1,"result":{}}\n',
                 b'{"jsonrpc":"2.0","id":1,"result":{"content":[],"n":1e999}}\n',
                 b'\xff\n', frame()+frame(), b'null\n']
        for i, raw in enumerate(cases):
            dest = evidence.collect_synthetic(self.parent, f"bad{i}", REQUEST,
                (evidence.SyntheticEvent(1, raw, end=True),))
            self.assertFalse(evidence.verify_synthetic(dest)["full_response_claim"])

    def test_rpc_and_tool_errors(self):
        for i, raw in enumerate((b'{"jsonrpc":"2.0","id":1,"error":{}}\n', frame(isError=True))):
            dest = evidence.collect_synthetic(self.parent, f"error{i}", REQUEST,
                (evidence.SyntheticEvent(1, raw, end=True),))
            self.assertFalse(evidence.verify_synthetic(dest)["full_response_claim"])

    def test_incomplete_write_no_commit_and_no_reuse(self):
        original = evidence._write_new
        def fail(path, data):
            if path.name == "response-prefix.bin":
                with path.open("xb") as stream:
                    stream.write(data[:5])
                raise OSError("simulated disk failure")
            return original(path, data)
        with patch.object(evidence, "_write_new", side_effect=fail):
            with self.assertRaises(OSError):
                self.record(frame())
        dest = self.parent / "observation"
        self.assertFalse((dest / "COMMITTED.json").exists())
        with self.assertRaises(FileNotFoundError):
            evidence.verify_synthetic(dest)
        with self.assertRaises(FileExistsError):
            self.record(frame())

    def test_fsync_failure_no_commit(self):
        with patch.object(evidence.os, "fsync", side_effect=OSError("sync failure")):
            with self.assertRaises(OSError):
                self.record(frame())
        self.assertFalse((self.parent / "observation" / "COMMITTED.json").exists())

    def test_receipt_failure_leaves_raw_but_no_commit(self):
        original = evidence._write_new
        def fail(path, data):
            if path.name == "receipt.json":
                raise OSError("receipt disk failure")
            return original(path, data)
        with patch.object(evidence, "_write_new", side_effect=fail):
            with self.assertRaises(OSError):
                self.record(frame())
        dest = self.parent / "observation"
        self.assertEqual((dest / "response-prefix.bin").read_bytes(), frame())
        self.assertFalse((dest / "COMMITTED.json").exists())

    def test_short_and_zero_writes(self):
        class ShortWriter:
            def __init__(self, path, zero=False):
                self.stream = open(path, "xb")
                self.zero = zero
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.stream.close()
            def write(self, data):
                return 0 if self.zero else self.stream.write(data[:3])
            def flush(self):
                self.stream.flush()
            def fileno(self):
                return self.stream.fileno()
        original = Path.open
        def short(path, mode="r", *args, **kwargs):
            return ShortWriter(path) if mode == "xb" else original(path, mode, *args, **kwargs)
        with patch.object(Path, "open", short):
            dest, r = self.record(frame())
        self.assertEqual((dest / "response-prefix.bin").read_bytes(), frame())
        def zero(path, mode="r", *args, **kwargs):
            return ShortWriter(path, zero=True) if mode == "xb" else original(path, mode, *args, **kwargs)
        with patch.object(Path, "open", zero):
            with self.assertRaises(OSError):
                evidence._write_new(self.parent / "zero.bin", b"data")

    def test_readback_mismatch(self):
        with patch.object(Path, "read_bytes", return_value=b"wrong readback"):
            with self.assertRaises(OSError):
                self.record(frame())
        self.assertFalse((self.parent / "observation" / "COMMITTED.json").exists())

    def test_concurrent_processes_one_winner(self):
        code = '''import sys
from pathlib import Path
from tool.c2b_evidence import collect_synthetic
try:
    collect_synthetic(Path(sys.argv[1]), "process_race", bytes.fromhex(sys.argv[2]), ())
except FileExistsError:
    sys.exit(2)
'''
        processes = [subprocess.Popen([sys.executable, "-c", code, str(self.parent), REQUEST.hex()],
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                     for _ in range(4)]
        codes = []
        for process in processes:
            out, err = process.communicate(timeout=15)
            self.assertEqual(out, b"")
            self.assertEqual(err, b"")
            codes.append(process.returncode)
        self.assertEqual(sorted(codes), [0, 2, 2, 2])
        evidence.verify_synthetic(self.parent / "process_race")

    def test_receipt_tampering(self):
        dest, _ = self.record(frame())
        (dest / "receipt.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            evidence.verify_synthetic(dest)

    def test_concurrent_same_destination_one_winner(self):
        def run(_):
            try:
                evidence.collect_synthetic(self.parent, "race", REQUEST,
                    (evidence.SyntheticEvent(1, frame(), end=True),))
                return True
            except FileExistsError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(run, range(16))), 1)
        evidence.verify_synthetic(self.parent / "race")

    def test_tampering_detected(self):
        dest, _ = self.record(frame())
        (dest / "response-prefix.bin").write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            evidence.verify_synthetic(dest)

    def test_unsafe_names_and_timeline(self):
        for name in ("../escape", "a/b", "C:bad", "", "."):
            with self.assertRaises(ValueError):
                evidence.collect_synthetic(self.parent, name, REQUEST, ())
        with self.assertRaises(ValueError):
            evidence.collect_synthetic(self.parent, "bad", REQUEST,
                (evidence.SyntheticEvent(2), evidence.SyntheticEvent(1)))

    def test_existing_destination_untouched(self):
        dest, _ = self.record(frame())
        before = {p.name: p.read_bytes() for p in dest.iterdir()}
        with self.assertRaises(FileExistsError):
            self.record(frame("replacement"))
        self.assertEqual(before, {p.name: p.read_bytes() for p in dest.iterdir()})


if __name__ == "__main__":
    unittest.main()
