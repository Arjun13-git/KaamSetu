# Implementation Plan

## Milestone 0 — Foundation
- repo structure
- environment configuration
- lint/test baseline
- architecture docs

## Milestone 1 — Domain
- Pydantic models
- customer/asset/job/service-event services
- repository interfaces
- deterministic state machine

## Milestone 2 — API
- health
- customers
- assets
- jobs
- intake placeholder
- attachments

## Milestone 3 — AI intake
- extraction schema
- Strands workflow
- provider interface
- Bedrock adapter
- Ollama adapter
- validation/retry/fallback

## Milestone 4 — Memory
- exact asset history
- OpenSearch indexing
- semantic retrieval
- repeat-issue UI

## Milestone 5 — UI
- dashboard
- intake composer
- job board
- customer/asset history
- technician workspace

## Milestone 6 — Cloud
- S3
- DynamoDB
- Lambda
- API Gateway
- Bedrock
- deployment

## Milestone 7 — Local Build It
- LocalStack
- local OpenSearch
- Ollama
- one-command startup

## Milestone 8 — Demo hardening
- seeded demo data
- evaluation fixtures
- error states
- observability
- 3-minute demo recording

## Rule

Never begin the next milestone by abandoning a broken core path. A working `conversation → job → memory` flow is the priority.
