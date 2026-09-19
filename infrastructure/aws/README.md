# AWS deployment (demo stack)

A single SAM stack: an HTTP API in front of one Lambda (the same FastAPI app that runs locally,
via Mangum) backed by one DynamoDB table.

```text
client ──► API Gateway (HTTP API, throttled) ──► Lambda (python3.14, x86_64) ──► DynamoDB
                                                       └─► CloudWatch Logs (14-day retention)
```

| Resource | Notes |
|---|---|
| `AWS::DynamoDB::Table` | On-demand; key layout mirrors `services/api/app/providers/persistence/dynamodb/table.py` (a test enforces it) |
| `AWS::Lambda::Function` | Handler `app.lambda_handler.handler`, 28 s timeout. Policy: `GetItem`, `PutItem`, `Query` on the table and its indexes, and `bedrock:InvokeModel` on the one configured foundation model in this region (no wildcards) |
| `AWS::ApiGatewayV2::Api` + stage | `$default` stage, 10 req/s steady, burst 20 |
| `AWS::Logs::LogGroup` | Finite retention |

Deploying with `--resolve-s3` also creates the SAM CLI's own `aws-sam-cli-managed-default` stack
(one S3 bucket that holds the uploaded package).

## Prerequisites

- An AWS CLI profile with permission to create CloudFormation, IAM, Lambda, API Gateway, DynamoDB,
  CloudWatch Logs and S3 resources.
- [SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html),
  `make`, and Python 3 with `pip`. Docker is not required.

## Deploy

```bash
AWS_PROFILE=<profile> AWS_REGION=<region> infrastructure/aws/deploy.sh
```

The script builds the package (Linux wheels, so it can be built from any OS), deploys the stack
`kaamsetu-demo`, and prints the outputs (`ApiUrl`, `TableName`, ...). Set `KAAMSETU_SAM` to a `sam`
that is not on `PATH`, and `PYTHON` to the interpreter used for the build.

## Demo access

The deployed API runs with `APP_ENV=demo`. Callers must send the shared key in an `X-Demo-Key`
header; a valid key acts as one fixed demo business and cannot select a tenant. Health is open.

- The key is generated on first deploy into `~/.config/kaamsetu/demo-api-key` (mode 600, outside the
  repository) and passed to CloudFormation as a `NoEcho` parameter. It is not printed or committed.
- Do not put the key in a browser bundle. A browser cannot keep it secret: the web app must call the
  API from a server-side route that holds the key.
- The key is stored as a Lambda environment variable, readable by anyone in the account who can call
  `lambda:GetFunctionConfiguration`. Rotate it by deleting the file and redeploying.

This is a stand-in for real authentication, intended for a demo with synthetic data.

## Verify a deployment

```bash
python infrastructure/aws/smoke_test.py <ApiUrl>
```

It walks the whole vertical slice against the live endpoint: access control, directory records,
idempotent job creation, assignment, transitions, completion, history, and AI intake through the
configured model (resolution, idempotent replay, safety wording, hostile text). FAIL lines are
application invariants; NOTE lines describe what the model chose and never fail the run. Each run
uses its own keys and phone numbers, and leaves labelled records behind that must be removed
before loading demo data.

Load the fictional demo dataset into the deployed table (from your machine, with your own
credentials, not the function's). It is deterministic and idempotent; see `services/api/seed/README.md`
for what it contains and the five demo scenarios:

```bash
cd services/api
AWS_PROFILE=<profile> AWS_REGION=<region> DATA_PROVIDER=dynamodb \
  DYNAMODB_TABLE=<TableName> python -m seed            # load, then verify
AWS_PROFILE=<profile> AWS_REGION=<region> DATA_PROVIDER=dynamodb \
  DYNAMODB_TABLE=<TableName> python -m seed --verify   # read-only check
```

## Tear down

```bash
aws cloudformation delete-stack --stack-name kaamsetu-demo --profile <profile> --region <region>
```

This deletes the table and its data. The SAM bucket stack can be removed separately once nothing
else uses it.

## Known limits

- No real authentication, roles or per-user identity yet.
- The table is on-demand with no point-in-time recovery and is deleted with the stack.
- The 28 s Lambda timeout covers two bounded model attempts (12 s each); API Gateway cuts requests
  off at 30 s, so it cannot be raised further.
- Intake uses Amazon Nova Lite (`amazon.nova-lite-v1:0`). Anthropic models on Bedrock need an AWS
  Marketplace subscription with a valid payment method and were not used. Set the `BedrockModelId`
  parameter to change the model; the grant follows it.
- Nova Lite sometimes writes the string `"null"` instead of JSON `null`; the adapter repairs that
  narrowly (see `ai/README.md`). Any other invalid answer is retried once and then falls back to
  manual entry with the request kept.
- OpenSearch and S3 attachments are not part of this stack yet, so photos are shown to the model and
  not stored.
