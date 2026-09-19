#!/usr/bin/env bash
# Build and deploy the KaamSetu demo stack with AWS SAM.
#
#   AWS_PROFILE=<profile> AWS_REGION=<region> infrastructure/aws/deploy.sh
#
# The demo API key is read from a local file (created on first use, mode 600, outside the
# repository) and passed to CloudFormation as a NoEcho parameter. It is never printed or saved
# to samconfig.toml.
set -euo pipefail

: "${AWS_PROFILE:?Set AWS_PROFILE to the AWS CLI profile to deploy with}"
: "${AWS_REGION:?Set AWS_REGION to the region to deploy to}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
sam="${KAAMSETU_SAM:-sam}"
stack="${KAAMSETU_STACK_NAME:-kaamsetu-demo}"
key_file="${KAAMSETU_DEMO_KEY_FILE:-$HOME/.config/kaamsetu/demo-api-key}"
# Passed explicitly on every deploy: SAM reuses an existing stack's previous parameter values, so a
# changed template default would otherwise be silently ignored. Keep in step with the template.
model_id="${KAAMSETU_BEDROCK_MODEL_ID:-amazon.nova-lite-v1:0}"
export PYTHON="${PYTHON:-python3}"
# Opt out of SAM CLI telemetry unless the caller has chosen otherwise.
export SAM_CLI_TELEMETRY="${SAM_CLI_TELEMETRY:-0}"

if [[ ! -s "$key_file" ]]; then
  mkdir -p "$(dirname "$key_file")"
  (umask 077 && "$PYTHON" -c 'import secrets; print(secrets.token_hex(32))' > "$key_file")
  echo "Created a new demo API key at $key_file"
fi
demo_key="$(<"$key_file")"

cd "$here"
"$sam" build --template-file template.yaml

# `sed` masks the key in case the SAM CLI echoes parameter overrides.
"$sam" deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name "$stack" \
  --region "$AWS_REGION" \
  --profile "$AWS_PROFILE" \
  --resolve-s3 \
  --capabilities CAPABILITY_IAM \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides "DemoApiKey=$demo_key" "BedrockModelId=$model_id" \
  --tags project=kaamsetu environment=demo 2>&1 | sed "s/$demo_key/[redacted]/g"

echo
echo "Stack outputs:"
aws cloudformation describe-stacks \
  --stack-name "$stack" --region "$AWS_REGION" --profile "$AWS_PROFILE" \
  --query 'Stacks[0].Outputs[].[OutputKey,OutputValue]' --output text
