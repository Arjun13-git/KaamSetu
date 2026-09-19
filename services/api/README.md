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
the service behaves as `production`: it refuses the development identity and the in-memory provider.

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

Implementation must follow the engineering specification kept locally by the project owner.
