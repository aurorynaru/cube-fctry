"""Exact-owned disposable R12 subprocess only; no vendor/service/client execution."""
import os
from pathlib import Path
import sys

# -I -S worker uses only repository code and the standard library.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool.c2b_authorization_gate import Denied, digest, prepare_action
from tool.c2b_durable_storage import CATEGORIES, Limits, OfflineLedger
from tests.fixtures.c2b_r11_fakes import FakeApprovalVerifier


CHECKPOINT = b"fixture-discovery-checkpoint"
POLICY = b"fixture-policy-deployment-lifecycle-budgets"


def limits():
    # Explicit invented fixture values, NOT adopted R8 or production policy.
    return Limits(16384, tuple((c, 300000) for c in CATEGORIES),
                  500000, 1500000, 3, 200, 12000)


def action(**changes):
    fields = dict(observation="fixture-observation", session="fixture-session",
                  target={"id": "synthetic-target-only"}, details={"query": "synthetic-summary"},
                  checkpoint_digest=digest(CHECKPOINT), policy_digest=digest(POLICY),
                  destination="fixture-private-store-reference")
    return prepare_action(**(fields | changes))


class CrashLedger(OfflineLedger):
    crash = ""

    def _test_point(self, phase):
        if self.crash == "hold_evidence" and phase == "after_reservation":
            print("HELD", flush=True)
            if sys.stdin.readline() != "CONTINUE\n":
                os._exit(75)
        if phase == self.crash:
            os._exit(73)  # actual abrupt exit of THIS disposable worker only

    def _write(self, name, raw):
        if self.crash == "during_data" and name.endswith(".bin"):
            with (self.root / name).open("xb", buffering=0) as stream:
                stream.write(raw[:7])
                os.fsync(stream.fileno())
                os._exit(74)
        return super()._write(name, raw)


def main():
    if len(sys.argv) != 4:
        raise SystemExit(2)
    root, token, operation = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    if operation not in ("consume", "changed_session", "changed_action", "changed_target", "read", "evidence", "hold_evidence",
                          "after_reservation", "during_data", "before_consumption_ack"):
        raise SystemExit(2)
    # No path resolution into arbitrary protected namespaces; fixtures must be a
    # direct unique child of the harness's explicitly approved temporary parent.
    parent = Path(os.environ["LOCALAPPDATA"]) / "Temp" / "opencode"
    if root.parent != parent or not root.name.startswith("c2b-r12-"):
        raise SystemExit(2)
    ledger = CrashLedger(root, limits(), namespace_token=token)
    print("READY", flush=True)
    if sys.stdin.readline() != "GO\n":
        raise SystemExit(2)
    ledger.crash = operation
    try:
        if operation == "read":
            ledger.snapshot()
        elif operation in ("evidence", "hold_evidence"):
            ledger.append("partial", "worker-partial", "fixture-session", b"incomplete-prefix\r\n")
        else:
            prepared = action()
            if operation == "changed_session":
                prepared = action(session="other-session")
            if operation == "changed_action":
                prepared = action(details={"query": "other-action"})
            if operation == "changed_target":
                prepared = action(target={"id": "other-target"})
            approval = FakeApprovalVerifier(prepared.binding).claim
            ack = ledger.consume(approval, "worker-attempt")
            if ack.attempt != "worker-attempt" or ack.binding_digest != prepared.binding.digest:
                raise SystemExit(3)
        print("OK", flush=True)
    except (Denied, OSError):
        print("DENIED", flush=True)


if __name__ == "__main__":
    main()
