#!/usr/bin/env bash
# A throwaway local KaamSetu backend for building the UI without touching the deployed table:
# DynamoDB Local (:8100, in memory) + the demo dataset + the API (:8101) in demo mode with a
# local-only key. Restarting it gives the pristine dataset again.
#
#   scripts/local-stack.sh up      start (or restart) everything
#   scripts/local-stack.sh down    stop everything
#
# Needs Docker and services/api/.venv. With LLM=bedrock (default) intake calls Amazon Bedrock using
# the AWS profile in AWS_PROFILE (default: kaamsetu); LLM=disabled keeps everything offline.
set -euo pipefail

root="$(cd "$(dirname "$0")/../../.." && pwd)"
api="$root/services/api"
state="${TMPDIR:-/tmp}/kaamsetu-local-stack"
key="local-dev-key-not-a-secret-0123456789abcdef"   # only ever accepted by this local API
mkdir -p "$state"

stop() {
  [ -f "$state/api.pid" ] && kill "$(cat "$state/api.pid")" 2>/dev/null || true
  rm -f "$state/api.pid"
  docker rm -f kaamsetu-ddb >/dev/null 2>&1 || true
}

case "${1:-up}" in
  down) stop; echo "stopped"; exit 0 ;;
  up) ;;
  *) echo "usage: $0 up|down" >&2; exit 2 ;;
esac

stop
docker run -d --name kaamsetu-ddb -p 127.0.0.1:8100:8000 amazon/dynamodb-local:latest \
  -jar DynamoDBLocal.jar -inMemory -sharedDb >/dev/null

cd "$api"
# shellcheck disable=SC1091
source .venv/bin/activate
export DATA_PROVIDER=dynamodb DYNAMODB_TABLE=kaamsetu-local DYNAMODB_ENDPOINT_URL=http://127.0.0.1:8100
export AWS_REGION="${AWS_REGION:-us-east-1}" DEV_BUSINESS_ID=bus_demo

# Seeding needs no real credentials; DynamoDB Local accepts any.
AWS_ACCESS_KEY_ID=local AWS_SECRET_ACCESS_KEY=local python -m seed --create-table | tail -4

export APP_ENV=demo DEMO_API_KEY="$key"
if [ "${LLM:-bedrock}" = "bedrock" ]; then
  export AWS_PROFILE="${AWS_PROFILE:-kaamsetu}" LLM_PROVIDER=bedrock LLM_MODEL=amazon.nova-lite-v1:0
else
  export LLM_PROVIDER=disabled
fi
# own session, so the API outlives the shell that started it
launcher=$(command -v setsid || true)
${launcher:+$launcher }nohup uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8101 >"$state/api.log" 2>&1 &
echo $! >"$state/api.pid"
sleep 3
curl -fsS http://127.0.0.1:8101/api/v1/health && echo
echo "API http://127.0.0.1:8101/api/v1  (key: $key)   log: $state/api.log"
