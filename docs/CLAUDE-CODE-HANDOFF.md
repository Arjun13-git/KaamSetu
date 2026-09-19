# Claude Code Handoff

## Mission

Implement KaamSetu from the architecture and contracts in this repository. Do not redesign the product unless an explicit ADR is added.

## Read first

1. `README.md`
2. `docs/PRD.md`
3. `System-Design/README.md`
4. all files under `System-Design/`
5. `docs/IMPLEMENTATION-PLAN.md`
6. `docs/COMMIT-STRATEGY.md`

## Non-negotiables

- Preserve the `conversation → job → memory` core flow.
- Keep DynamoDB/structured storage authoritative.
- Treat LLM output as untrusted input.
- Enforce tenant isolation server-side.
- Unknown fields remain unknown.
- No AI diagnosis or safety-critical repair instructions.
- Local and AWS modes share application contracts.
- Keep commits small and milestone-oriented.
- Add tests with each meaningful feature.

## First implementation task

Implement Milestone 1 from `docs/IMPLEMENTATION-PLAN.md`: domain models, repository interfaces, deterministic job state machine, and tests. Do not implement the full UI or cloud deployment yet.
