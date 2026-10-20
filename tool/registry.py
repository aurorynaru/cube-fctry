"""Local Milestone B1 registry CLI; run `python tool/registry.py --help`."""

import argparse
import json
from pathlib import Path
import sys

from asset_registry import Registry, RegistryError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate or append an asset-registry event")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="project root (defaults to this script's project)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="validate all events and live referenced files without writing")
    change = sub.add_parser("record", help="validate and append one controlled event")
    change.add_argument("action", choices=("create", "art_approved", "generated", "qc_pending",
                                            "qc_passed", "imported", "approved", "rejected", "rework"))
    change.add_argument("--id", required=True, help="immutable asset ID")
    change.add_argument("--actor", required=True, help="actor ID in game roster")
    change.add_argument("--data", required=True, type=Path, help="JSON event data; see art/REGISTRY_B1.md")
    change.add_argument("--dry-run", action="store_true", help="replay without appending to journal")
    args = parser.parse_args(argv)
    try:
        registry = Registry(args.root)
        if args.command == "validate":
            records = registry.validate()
            print(f"PASS: {len(records)} unique assets, {sum(len(r['history']) for r in records.values())} events")
        else:
            payload = json.loads(args.data.read_text(encoding="utf-8"))
            record = registry.apply(args.action, args.id, args.actor, payload, args.dry_run)
            print(f"PASS: {args.id} revision {record['revision']} -> {record['request']['approval']['status']}"
                  + (" (dry-run, no event written)" if args.dry_run else ""))
        return 0
    except (RegistryError, OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
