"""Offline C1C harness CLI: validate/plan and manual capture import.

This CLI never connects to Roblox Studio, never uploads, saves or publishes,
and never writes a B1 registry event. The lifecycle itself runs only through a
separately authorized adapter.
"""

import argparse
import json
from pathlib import Path
import sys

from c1c_harness import (
    AssetManifest,
    HarnessError,
    build_rig_plan,
    import_capture_file,
    load_spec,
    registry_fingerprint,
    verify_b2_evidence,
)


ROOT = Path(__file__).resolve().parents[1]


def _summary(root, spec, asset_info, b2) -> dict:
    return {
        "result": "PASS",
        "run_id": spec.run_id,
        "folder": spec.folder_path,
        "asset": {
            "asset_id": spec.asset.asset_id,
            "asset_type": spec.asset.asset_type,
            "status": spec.asset.status,
            "upload": False,
            "source_path": asset_info["source_path"],
            "source_sha256": asset_info["source_sha256"],
        },
        "b2": b2,
        "b1": registry_fingerprint(root),
        "evidence_out_dir": spec.evidence.out_dir,
        "captures": [capture.capture_id for capture in spec.screenshots],
    }


def command_validate(args):
    root = Path(args.root).resolve()
    spec = load_spec(root, args.spec)
    manifest = AssetManifest(root, spec.asset.manifest_path).load()
    asset_info = manifest.resolve(spec.asset)
    b2 = verify_b2_evidence(root, spec, asset_info["source_sha256"])
    print(json.dumps(_summary(root, spec, asset_info, b2), indent=2, sort_keys=True))
    return 0


def command_plan(args):
    root = Path(args.root).resolve()
    spec = load_spec(root, args.spec)
    plan = build_rig_plan(spec)
    print(json.dumps({
        "result": "PASS",
        "run_id": spec.run_id,
        "folder": plan.folder,
        "requires_studio": True,
        "uploads_assets": False,
        "saves_or_publishes": False,
        "writes_b1_events": False,
        "rig": plan.as_dict(),
        "luau_plan": {
            "run_id": spec.run_id,
            "rig": plan.as_dict(),
        },
        "captures": [
            {
                "capture_id": capture.capture_id,
                "phase": capture.phase,
                "required": capture.required,
                "purpose": capture.purpose,
                "camera": capture.camera.as_dict() if capture.camera else None,
            }
            for capture in spec.screenshots
        ],
        "cleanup": {
            "verify_baseline": spec.cleanup.verify_baseline,
            "allow_safe_rename": spec.cleanup.allow_safe_rename,
            "preserve_failure_evidence": spec.cleanup.preserve_failure_evidence,
        },
    }, indent=2, sort_keys=True))
    return 0


def command_import_capture(args):
    camera = json.loads(args.camera) if args.camera else None
    if camera is not None and not isinstance(camera, dict):
        raise HarnessError("--camera must be a JSON object")
    record = import_capture_file(Path(args.root).resolve(), args.spec, args.run_id,
                                 args.capture_id, args.image, camera=camera)
    print(json.dumps(record, indent=2, sort_keys=True))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(ROOT), help="project root (default: repo root)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a spec, manifest and B2 link; write nothing")
    validate.add_argument("--spec", required=True, help="project-relative harness spec")
    validate.set_defaults(func=command_validate)

    plan = subparsers.add_parser("plan", help="print the deterministic rig/capture plan; write nothing")
    plan.add_argument("--spec", required=True, help="project-relative harness spec")
    plan.set_defaults(func=command_plan)

    importer = subparsers.add_parser(
        "import-capture",
        help="manually import a real operator-supplied PNG into an existing run",
    )
    importer.add_argument("--spec", required=True,
                          help="project-relative harness spec that produced the run")
    importer.add_argument("--run-id", required=True)
    importer.add_argument("--capture-id", required=True)
    importer.add_argument("--image", required=True, help="absolute path to a real PNG")
    importer.add_argument("--camera", help="optional JSON object describing the capture camera")
    importer.set_defaults(func=command_import_capture)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (HarnessError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
