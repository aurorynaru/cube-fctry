"""Fixed disposable R9 death fixture. Only synthetic pause checkpoints."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tool.c2b_restricted_frontend import Frontend
from tool.c2b_synthetic_review import SyntheticReview
from tests.fixtures.c2b_synthetic_client import SyntheticClient

directory, phase = Path(sys.argv[1]), sys.argv[2]
if phase not in ("before_checkpoint", "after_checkpoint"):
    raise ValueError("fixed death phase required")


def checkpoint(self, current, session):
    if current == phase:
        (directory / "ready.json").write_text(json.dumps({
            "process": session.process.boundary.handles["process"]}))
        while True:
            time.sleep(0.01)


SyntheticReview._test_checkpoint = checkpoint
frontend = Frontend(directory, "observation", review_seconds=30)
client = SyntheticClient(frontend)
client.initialize()
frontend.inject_launch(frontend.review.launch_token())
client.discovery()
while True:
    time.sleep(0.01)
