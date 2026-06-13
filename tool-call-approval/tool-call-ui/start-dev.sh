#!/usr/bin/env bash
set -e

echo "Starting minikube tunnel for tool-call-api..."

TMPFILE=$(mktemp)
minikube service tool-call-api --url >"$TMPFILE" 2>/dev/null &
TUNNEL_PID=$!

# Wait up to 15s for the URL to appear
TUNNEL_URL=""
for i in $(seq 1 30); do
  TUNNEL_URL=$(head -1 "$TMPFILE" 2>/dev/null || true)
  [[ "$TUNNEL_URL" == http* ]] && break
  sleep 0.5
done
rm -f "$TMPFILE"

if [[ "$TUNNEL_URL" != http* ]]; then
  echo "ERROR: could not get minikube service URL"
  kill "$TUNNEL_PID" 2>/dev/null
  exit 1
fi

echo "Proxying /api → $TUNNEL_URL"
export API_TARGET="$TUNNEL_URL"

trap 'kill "$TUNNEL_PID" 2>/dev/null' EXIT

npx ng serve --proxy-config proxy.conf.mjs
