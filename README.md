# KaamSetu

> **Give local service businesses a memory.**

KaamSetu turns messy customer conversations into structured service jobs, preserves customer and asset history, and helps small service businesses execute work without relying on WhatsApp, notebooks, spreadsheets, or memory.

## Project Status

**Hackathon:** WeMakeDevs × AWS First Commit — September 17–20, 2026
**Current phase:** Base architecture + artifacts

## Core flow

`Conversation / Photo → AI Intake → Customer & Asset Resolution → Job → Technician Workflow → Service Memory`

## Repository layout

```text
KaamSetu/
├── System-Design/          # Complete system-design package
├── docs/                   # Product, hackathon, and implementation docs
├── apps/web/               # Next.js frontend (skeleton)
├── services/api/           # Python/FastAPI backend (skeleton)
├── ai/                     # Agent prompts, schemas, evaluation
├── infrastructure/         # AWS + local deployment definitions
├── data/                    # Seed and evaluation datasets
└── tests/                   # Cross-layer tests
```

## Architecture principle

KaamSetu is **unstructured-first**: the system starts from the way service businesses actually receive work (natural-language messages, photos, and eventually voice) and converts that into structured operational state.

AWS/cloud and local/open-source environments share the same application contracts through provider interfaces.

## Hackathon compliance

This repository is being built during the First Commit hackathon window. AI coding tools are permitted by the event rules and will be disclosed in the submission. Third-party dependencies and assets must retain compatible licenses and attribution.
