# KaamSetu API

FastAPI service implementing the domain/application layer.

## Run

```bash
cd services/api
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn app.main:app --reload
```

Health: `GET /api/v1/health`

Implementation must follow `../../System-Design/`.
