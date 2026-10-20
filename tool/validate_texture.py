"""Offline B2 texture QA CLI; see art/TEXTURE_QA_B2.md."""

import argparse
import json
from pathlib import Path
import sys

from asset_registry import Registry, RegistryError
from texture_qa import QAError, evaluate, write_evidence


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate B2 texture QA evidence without registry transitions")
    parser.add_argument("paths", nargs="*", help="project-relative image paths")
    parser.add_argument("--batch", help="project-relative JSON array of image paths")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--profile", required=True, help="B1 style profile ID")
    parser.add_argument("--request", help="project-relative B1 request JSON (one image only)")
    parser.add_argument("--asset-id", help="read existing B1 record/request (one image only)")
    parser.add_argument("--expected-sha256", help="expected deliverable SHA-256 (one image only)")
    parser.add_argument("--seamless", action="store_true", help="check tiling and generate preview evidence")
    parser.add_argument("--out-dir", default="registry/evidence/texture-qa", help="project-relative evidence directory")
    parser.add_argument("--dry-run", action="store_true", help="JSON report on stdout; write no evidence or journal")
    args = parser.parse_args(argv)
    try:
        from texture_qa import safe_path
        root = args.root.resolve()
        registry = Registry(root)
        records = registry.validate()  # Read/replay B1 contracts; its temporary lock is removed.
        paths = list(args.paths)
        if args.batch:
            if paths:
                raise QAError("choose positional images or --batch")
            paths = json.loads(safe_path(root, args.batch).read_text(encoding="utf-8"))
        if not isinstance(paths, list) or not paths or not all(isinstance(p, str) for p in paths):
            raise QAError("provide one or more project-relative texture paths")
        if len(set(paths)) != len(paths):
            raise QAError("duplicate image path in batch")
        if len(paths) != 1 and (args.request or args.asset_id or args.expected_sha256):
            raise QAError("request, asset ID and expected hash apply to one image only")
        if args.request and args.asset_id:
            raise QAError("choose --request or --asset-id")
        request = None
        if args.request:
            payload = json.loads(safe_path(root, args.request).read_text(encoding="utf-8"))
            request = payload.get("request", payload)
        if args.asset_id:
            if args.asset_id not in records:
                raise QAError("asset ID not in B1 registry")
            record = records[args.asset_id]
            if not record["output"] or record["output"]["path"] != paths[0]:
                raise QAError("B1 recorded output does not match source")
            request = record["request"]
        # Preflight all source paths before writing any evidence.
        reports = [evaluate(root, name, args.profile, seamless=args.seamless, request=request,
                            expected_sha256=args.expected_sha256) for name in paths]
        if not args.dry_run:
            for report, images in reports:
                write_evidence(root, args.out_dir, report, images)
        for report, _ in reports:
            print(json.dumps(report, sort_keys=True))
        return 1 if any(report["overall_result"] == "FAIL" for report, _ in reports) else 0
    except (QAError, RegistryError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
