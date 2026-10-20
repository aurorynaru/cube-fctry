"""Data-only exact-source retrieval for R10. Never executes retrieved code."""
import datetime
import hashlib
import json
import pathlib
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
OC = "733b2c627e5aec39cb33cc22373bdce33053ef2c"
PREFIXES = (
    f"https://raw.githubusercontent.com/anomalyco/opencode/{OC}/",
    "https://api.github.com/repos/anomalyco/opencode/git/ref/tags/v1.19.0",
    f"https://api.github.com/repos/anomalyco/opencode/git/commits/{OC}",
    "https://api.github.com/repos/anomalyco/opencode/releases/tags/v1.19.0",
    "https://api.github.com/repos/modelcontextprotocol/typescript-sdk/git/ref/tags/1.29.0",
    "https://api.github.com/repos/modelcontextprotocol/typescript-sdk/git/ref/tags/v1.29.0",
    "https://api.github.com/repos/modelcontextprotocol/typescript-sdk/git/commits/e12cbd7078db388152f6e839abdbe09ba01f3f32",
    "https://raw.githubusercontent.com/modelcontextprotocol/typescript-sdk/e12cbd7078db388152f6e839abdbe09ba01f3f32/",
)

def main():
    batch, *items = sys.argv[1:]
    if not ROOT.is_dir() or not batch.isdecimal():
        raise ValueError("existing evidence root and numeric batch required")
    manifest = ROOT / f"acquisition-{batch}.json"
    if manifest.exists():
        raise ValueError("new batch required")
    records = []
    for item in items:
        name, url = item.split("=", 1)
        if pathlib.Path(name).name != name or not url.startswith(PREFIXES):
            raise ValueError("only reviewed source URLs and flat names allowed")
        dest = ROOT / name
        if dest.exists():
            raise ValueError("source snapshots are new-only")
        record = {"file": name, "requested_url": url,
                  "acquired_at_host_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  "method": "Python standard-library urllib.request HTTPS GET; response body saved unchanged"}
        try:
            request = urllib.request.Request(url, headers={
                "User-Agent": "R10-static-source-review",
                "Accept": "application/vnd.github+json" if "api.github.com" in url else "text/plain"})
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read(4000001)
                if len(data) > 4000000:
                    raise ValueError("source response exceeds bound")
                record.update(final_url=response.url, status=response.status,
                              etag=response.headers.get("ETag"), length=len(data),
                              sha256=hashlib.sha256(data).hexdigest())
            with dest.open("xb") as out:
                out.write(data)
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
        records.append(record)
    with manifest.open("x", encoding="utf-8", newline="\n") as out:
        json.dump({"scope": "R10 public pinned source, data only; installed binary correlation unverified",
                   "files": records}, out, indent=2)
        out.write("\n")
    print(json.dumps(records, indent=2))
    return int(any("error" in record for record in records))

if __name__ == "__main__":
    raise SystemExit(main())
