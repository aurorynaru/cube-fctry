#!/usr/bin/env bash
#
# Build the Rojo project and upload it to Roblox via Open Cloud.
#
#   tool/publish.sh              # build, lint, publish live
#   tool/publish.sh --saved      # upload as a saved version instead of live
#   tool/publish.sh --no-lint    # skip the stylua/selene gate
#   tool/publish.sh --build-only # build the .rbxl and stop
#
# IDs and PLACE_FILE come from tool/publish.env (committed, not secret).
# The API key comes from, in order:
#   1. $ROBLOX_API_KEY (GitHub Actions sets this from the GarfGames org secret)
#   2. the macOS Keychain, service "roblox-open-cloud":
#      $ROBLOX_KEYCHAIN_ACCOUNT, then PLACE_NAME from publish.env, then default
#      security add-generic-password -s roblox-open-cloud -a default -w 'KEY'
#   3. .env.publish in the repo root (gitignored), as ROBLOX_API_KEY=...

set -euo pipefail

cd "$(dirname "$0")/.."

VERSION_TYPE=Published
RUN_LINT=1
BUILD_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --saved)      VERSION_TYPE=Saved ;;
    --publish)    VERSION_TYPE=Published ;;
    --no-lint)    RUN_LINT=0 ;;
    --build-only) BUILD_ONLY=1 ;;
    -h|--help)    sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)            echo "unknown option: $1" >&2; exit 2 ;;
  esac
  shift
done

die() { echo "publish: $*" >&2; exit 1; }

# --- config -----------------------------------------------------------------

if [ -f tool/publish.env ]; then
  # shellcheck source=/dev/null
  . tool/publish.env
fi

check_target() {
  [ -n "${UNIVERSE_ID:-}" ] && [ "$UNIVERSE_ID" != "0" ] || die "set UNIVERSE_ID in tool/publish.env"
  [ -n "${PLACE_ID:-}" ] && [ "$PLACE_ID" != "0" ] || die "set PLACE_ID in tool/publish.env"
}

# --- lint gate --------------------------------------------------------------

if [ "$RUN_LINT" = 1 ]; then
  echo "==> stylua --check"
  stylua --check src/ || die "stylua found unformatted files (run: stylua src/)"
  echo "==> selene"
  # selene exits nonzero on warnings too; only errors should block a publish.
  SELENE_OUT=$(selene src/ 2>&1) || true
  ERRORS=$(printf '%s\n' "$SELENE_OUT" | awk '/^[0-9]+ (parse )?errors$/ { e += $1 } END { print e + 0 }')
  if [ "${ERRORS:-0}" != "0" ]; then
    printf '%s\n' "$SELENE_OUT" >&2
    die "selene found ${ERRORS} error(s)"
  fi
  printf '    %s\n' "$(printf '%s' "$SELENE_OUT" | grep -c '^warning' | tr -d ' ') warning(s), 0 errors"
fi

# --- build ------------------------------------------------------------------

mkdir -p build
OUT="${PLACE_FILE:-build/place.rbxl}"
echo "==> rojo build"
rojo build default.project.json -o "$OUT"
SIZE=$(wc -c < "$OUT" | tr -d ' ')
[ "$SIZE" -gt 10000 ] || die "built place is suspiciously small (${SIZE} bytes)"
echo "    $OUT (${SIZE} bytes)"

[ "$BUILD_ONLY" = 1 ] && exit 0

check_target

# --- credentials ------------------------------------------------------------

API_KEY="${ROBLOX_API_KEY:-}"

if [ -z "$API_KEY" ] && command -v security >/dev/null 2>&1; then
  accts=()
  [ -n "${ROBLOX_KEYCHAIN_ACCOUNT:-}" ] && accts+=("$ROBLOX_KEYCHAIN_ACCOUNT")
  [ -n "${PLACE_NAME:-}" ] && accts+=("$PLACE_NAME")
  accts+=(default)
  for acct in "${accts[@]}"; do
    API_KEY=$(security find-generic-password -s roblox-open-cloud -a "$acct" -w 2>/dev/null || true)
    [ -n "$API_KEY" ] && break
  done
fi

if [ -z "$API_KEY" ] && [ -f .env.publish ]; then
  # shellcheck source=/dev/null
  . .env.publish
  API_KEY="${ROBLOX_API_KEY:-}"
fi

[ -n "$API_KEY" ] || die "no Open Cloud API key found (see the header of this script)"

# --- upload -----------------------------------------------------------------

URL="https://apis.roblox.com/universes/v1/${UNIVERSE_ID}/places/${PLACE_ID}/versions?versionType=${VERSION_TYPE}"
echo "==> upload (${VERSION_TYPE}) -> universe ${UNIVERSE_ID}, place ${PLACE_ID}"

RESPONSE=$(curl -sS -w $'\n%{http_code}' -X POST "$URL" \
  -H "x-api-key: ${API_KEY}" \
  -H "Content-Type: application/octet-stream" \
  --data-binary "@${OUT}")

STATUS=$(printf '%s' "$RESPONSE" | tail -n1)
BODY=$(printf '%s' "$RESPONSE" | sed '$d')

if [ "$STATUS" != "200" ]; then
  echo "$BODY" >&2
  case "$STATUS" in
    401|403) die "HTTP $STATUS — API key rejected. Check the key's universe scope (universe-places:write) and its IP allowlist." ;;
    404)     die "HTTP $STATUS — universe/place not found. Check the ids in tool/publish.env." ;;
    *)       die "HTTP $STATUS — upload failed." ;;
  esac
fi

VERSION=$(printf '%s' "$BODY" | sed -n 's/.*"versionNumber"[: ]*\([0-9]*\).*/\1/p')
echo "    ok — version ${VERSION:-?} (${VERSION_TYPE})"
echo "    https://www.roblox.com/games/${PLACE_ID}/"
