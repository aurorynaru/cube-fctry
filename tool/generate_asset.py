"""B3 local image generation CLI; see art/GENERATION_B3.md.

Examples:
    python tool/generate_asset.py --request art/requests/example-0001.json --dry-run
    python tool/generate_asset.py --request art/requests/example-0001.json
"""

import argparse
import json
from pathlib import Path
import sys

from asset_registry import RegistryError
from image_generation import (
    DEFAULT_BASE_URL,
    ComfyUIClient,
    GenerationError,
    ROOT,
    dry_run_report,
    execute_generation,
    prepare_request,
)


def _print_dry_run(report):
    planned = report["planned"]
    print(f"VALID: {report['request_id']} ({report['mode']}); no generation enqueued")
    print(f"Profile: {report['profile']['path']} sha256={report['profile']['sha256']}")
    print(f"Workflow: {report['workflow']['version']} -> {planned['workflow']}")
    print(f"Image destination: {planned['image']}")
    print(f"Prompt SHA-256: {report['workflow']['prompt_sha256']}")
    if report.get("comfy"):
        comfy = report["comfy"]
        print(f"ComfyUI: {comfy['server_url']} available; {comfy['object_info_nodes']} node classes")
        print(f"Models: {comfy['workflow_checks']['models']}")
    else:
        print("ComfyUI: not queried (--no-comfy-check)")
    for warning in report.get("warnings", []):
        print(f"WARNING: {warning}")


def _print_result(result):
    output = result["output"]
    print(f"GENERATED: {output['path']} ({output['width']}x{output['height']} {output['format']}, "
          f"{output['size_bytes']} bytes)")
    print(f"SHA-256: {output['sha256']}")
    print(f"ComfyUI prompt_id: {result['generation']['prompt_id']} "
          f"client_id: {result['generation']['client_id']}")
    print(f"Elapsed: {result['generation']['elapsed_seconds']} s; status: {result['status']}")
    for qa in result["qa"]:
        print(f"B2 QA {qa['role']}: {qa['overall_result']} "
              f"(automated {qa['automated_result']}) -> {qa['path']}")
        if qa.get("evidence", {}).get("json"):
            print(f"  evidence: {qa['evidence']['json']} | {qa['evidence'].get('markdown')}")
    recommendation = result.get("candidate_recommendation") or {}
    print(f"Recommendation: {recommendation.get('role')} {recommendation.get('path')} "
          f"({recommendation.get('overall_result')}); not an approval")
    print(f"QA outcome: {result.get('qa_outcome')}; candidate preserved: "
          f"{result['candidate']['preserved']}")
    for warning in result.get("warnings", []):
        print(f"WARNING: {warning}")
    for error in result.get("qa_errors", []):
        print(f"QA ERROR ({error.get('stage')}): {error.get('message')}")
    print("B1: no registry event written; human gates remain pending.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate and run one local B3 image generation")
    parser.add_argument("--request", required=True, help="project-relative B3 request JSON")
    parser.add_argument("--root", type=Path, default=ROOT, help="project root")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="local ComfyUI URL")
    parser.add_argument("--timeout", type=float, default=600.0, help="generation timeout in seconds")
    parser.add_argument("--connect-timeout", type=float, default=15.0, help="HTTP timeout")
    parser.add_argument("--poll-interval", type=float, default=1.0, help="history poll interval")
    parser.add_argument("--dry-run", action="store_true",
                        help="validate and optionally preflight ComfyUI without enqueueing")
    parser.add_argument("--no-comfy-check", action="store_true",
                        help="dry-run only: skip the ComfyUI preflight")
    parser.add_argument("--json", action="store_true", help="print the full structured result")
    args = parser.parse_args(argv)
    if args.no_comfy_check and not args.dry_run:
        print("FAIL: --no-comfy-check is only valid with --dry-run", file=sys.stderr)
        return 2
    if args.timeout <= 0 or args.poll_interval <= 0 or args.connect_timeout <= 0:
        print("FAIL: timeout values must be positive", file=sys.stderr)
        return 2
    try:
        prepared = prepare_request(args.root, args.request)
        if args.dry_run:
            client = None
            if not args.no_comfy_check:
                client = ComfyUIClient(args.base_url, timeout=args.connect_timeout,
                                       poll_interval=args.poll_interval)
            report = dry_run_report(prepared, client, check_comfy=not args.no_comfy_check)
            if args.json:
                print(json.dumps(report, indent=2))
            else:
                _print_dry_run(report)
            return 0
        client = ComfyUIClient(args.base_url, timeout=args.connect_timeout,
                               poll_interval=args.poll_interval)
        result = execute_generation(prepared, client, timeout_seconds=args.timeout,
                                    poll_interval=args.poll_interval)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            _print_result(result)
        return 0 if result["status"] == "completed" and result.get("qa_outcome") in (
            "PASS", "REVIEW_REQUIRED") else 1
    except (GenerationError, RegistryError, OSError, ValueError, KeyError, TypeError) as exc:
        if isinstance(exc, GenerationError):
            error = exc.as_dict()
        else:
            error = {"code": "unexpected_error", "message": str(exc), "detail": None}
        if args.json:
            print(json.dumps({"status": "error", "error": error}, indent=2))
        else:
            print(f"FAIL [{error['code']}]: {error['message']}", file=sys.stderr)
            if error.get("detail"):
                print(f"DETAIL: {json.dumps(error['detail'], ensure_ascii=False)[:2000]}",
                      file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
