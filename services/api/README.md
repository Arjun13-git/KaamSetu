# KaamSetu API

FastAPI service implementing the domain/application layer.

## Run

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cp ../../.env.example .env        # development identity + in-memory storage
uvicorn app.main:create_app --factory --reload
```

Health: `GET /api/v1/health` returns `{"data": {"status": "ok", "version": "..."}, "request_id": "req_..."}`.
Errors use `{"error": {"code", "message", "details"}, "request_id"}`.

Configuration is read from environment variables (see `../../.env.example`). If `APP_ENV` is unset
the service behaves as `production`: it accepts no caller and refuses the in-memory provider.

## Endpoints

All under `/api/v1`. Bodies never carry a business id (they are rejected if they do).

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness (open) |
| `POST /customers`, `GET /customers?q=&phone=`, `GET /customers/{id}` | Customers; search within the business |
| `POST/GET /customers/{id}/assets`, `GET /assets/{id}` | Assets (appliances) of a customer |
| `POST /technicians`, `GET /technicians?active_only=`, `GET /technicians/{id}` | Technicians |
| `POST /jobs` | Create a job from operator-entered fields. Send `Idempotency-Key` to make retries safe |
| `GET /jobs?status=&technician_id=`, `GET /jobs/{id}` | List jobs; the technician job card (customer, asset, prior service) |
| `PATCH /jobs/{id}` | Change description, urgency or preferred slot only. Never status |
| `POST /jobs/{id}/assign`, `POST /jobs/{id}/transition` | Assign or reassign; move forward or cancel |
| `POST /jobs/{id}/complete` | The only route to `COMPLETED`: stores job, service event and audit atomically |
| `GET /assets/{id}/history`, `GET /customers/{id}/history` | Recorded service, newest first |
| `POST /intake` | Customer text (and optional photo) to a ServiceRequest, and to a job when unambiguous |
| `GET /service-requests?status=`, `GET /service-requests/{id}` | The preserved intake records |
| `POST /service-requests/{id}/job` | A person confirms a request as a job (also the fallback when AI is unavailable) |

### Intake

`POST /intake` stores the request first, then asks the model for a structured extraction that is
validated against `ai/schemas/intake_extraction.v1.json`. Customers resolve only from explicit
evidence (an operator-selected `customer_id`, or a phone number matching exactly one customer); a
name alone yields candidates for a person to confirm. A job is created without a person only when
the customer and asset are both resolved, the request has a known type and a problem, and the
model's overall confidence is at least 0.7. Otherwise the request is `NEEDS_REVIEW` with the
extraction and candidates visible. If the model is unavailable or answers invalidly, the request is
`EXTRACTION_FAILED` and nothing is lost. An `Idempotency-Key` makes a retry return the same result
without calling the model again. Safety wording (sparking, smoke, burning smell, ...) is detected
without the model and only ever raises urgency.

Configure the model with `LLM_PROVIDER=bedrock` and `LLM_MODEL=<Bedrock model id>` (the deployed
stack uses `amazon.nova-lite-v1:0`). The application is model-agnostic: only the adapter in
`app/ai/bedrock.py` knows the provider.

## Authentication

Until real authentication exists there is one fixed identity (`DEV_BUSINESS_ID`, `DEV_ACTOR_ID`),
chosen by `APP_ENV`: open in `development`/`test`, only for holders of `DEMO_API_KEY` (sent as
`X-Demo-Key`) in `demo`, and refused in `production`. The tenant is never read from a header, query
string or body.

## Checks

```bash
pytest
ruff check .
ruff format --check .
```

## Layout

```text
app/core/         config, ids, clock, errors, request context
app/domain/       entities, job state machine + workflow, repository ports
app/providers/    persistence adapters: memory, dynamodb (behind app/domain/repositories.py)
app/api/          HTTP layer: envelope, error mapping, dependencies, routes
app/lambda_handler.py  AWS Lambda entry point (Mangum)
scripts/          Lambda package build (used by `sam build`)
seed/             synthetic demo data
tests/            unit tests + an adapter-agnostic persistence contract suite
```

## Persistence

Two adapters implement the same ports and pass the same contract suite
(`tests/integration/persistence/test_repository_contract.py`):

- `DATA_PROVIDER=memory` for tests and quick local runs (state is lost on exit).
- `DATA_PROVIDER=dynamodb` for LocalStack, DynamoDB Local or AWS. Set `DYNAMODB_TABLE`, and
  `DYNAMODB_ENDPOINT_URL` for a local endpoint (leave it empty for AWS). The table layout lives in
  `app/providers/persistence/dynamodb/keys.py` and `table.py`.

Load the fictional demo dataset (idempotent) into a local table:

```bash
DATA_PROVIDER=dynamodb DYNAMODB_ENDPOINT_URL=http://localhost:8000 python -m seed --create-table
```

## Invariants worth knowing

- Every repository call is scoped by `business_id`; another business's record looks like a missing one.
- A job reaches `COMPLETED` only through `complete_job`, which stores the job, its service event and
  an audit record atomically. `PATCH`-style amendments cannot change status, technician or schedule.
- Tenant identity comes from the server-side `Actor`, never from a client-supplied header or body.
  Until real authentication exists that actor is a fixed development identity.

## Deployment

The same app runs on AWS Lambda behind API Gateway; see `../../infrastructure/aws/README.md`.

Implementation must follow the engineering specification kept locally by the project owner.
