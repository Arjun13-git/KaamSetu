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

## Model notes

The deployed model is Amazon Nova Lite (`amazon.nova-lite-v1:0`), chosen by configuration only. It
accepts the exact interaction (forced tool call, the full inlined schema, `temperature` 0, image
input) and follows the prompt's safety and injection rules. Observed limitations, measured over 20
varied messages:

- About 15% of answers (3 of 20) contain the literal string `"null"` instead of JSON `null` in
  optional fields, mostly for messages that name a person or mix languages. These fail schema
  validation, are retried once, and then fall back to manual entry; nothing is lost.
- It often sets `problem.urgency` to `normal` and confidence near 1.0 without a stated reason, so
  its confidence is less informative than a larger model's.
