# AI artifacts

- `schemas/intake_extraction.v1.json` is the JSON Schema of the record the intake model must
  produce. It is **generated** from the typed schema in `services/api/app/ai/schemas.py` (the single
  source of truth); a test fails if the two drift. Regenerate with
  `cd services/api && python -m app.ai.schemas > ../../ai/schemas/intake_extraction.v1.json`.
- The versioned prompt lives beside the code that loads it, in
  `services/api/app/ai/prompts/intake_v1.md`, so it is packaged with the Lambda function. Its
  version is recorded on every extraction.
- `evaluation/` is reserved for the hand-reviewed golden dataset (see `data/evaluation/`).

The model only proposes structured data. Validation, guards, entity resolution and every write are
deterministic application code.
