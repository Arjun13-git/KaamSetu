# KaamSetu web

The operator and technician interface: **customer conversation → AI understanding → structured
service request → job → technician → service history**, with Service Memory shown wherever a
request meets an appliance that has been serviced before.

Next.js 16 (App Router) · React 19 · TypeScript (strict) · Tailwind CSS 4 · lucide-react.

## How it talks to the API

The browser never calls the KaamSetu API and never sees its key. Pages are Server Components that
read through `src/lib/api` (a `server-only` client that adds the `X-Demo-Key` header), and changes
go through Server Actions. There is no generic proxy route. Configuration is server-side only;
nothing is prefixed `NEXT_PUBLIC_`.

```bash
cp .env.example .env.local      # KAAMSETU_API_URL, KAAMSETU_DEMO_KEY, KAAMSETU_TIMEZONE
npm install
npm run dev                     # http://localhost:3000
```

## Develop against a throwaway backend

`scripts/local-stack.sh up` starts DynamoDB Local, loads the demo dataset and runs the API in demo
mode on `:8101` (requires Docker and `services/api/.venv`); point `.env.local` at it:

```text
KAAMSETU_API_URL=http://127.0.0.1:8101/api/v1
KAAMSETU_DEMO_KEY=local-dev-key-not-a-secret-0123456789abcdef
```

Running it again restores the pristine dataset. Use `LLM=disabled` to stay offline (intake then
falls back to manual entry).

## Checks

```bash
npm run typecheck && npm run lint && npm test && npm run build
```

`npm test` runs the pure-logic tests (formatting, status rules, extraction parsing, error mapping)
with Node's built-in test runner.

## Screens

Board · New request (AI intake) · Job detail · Customers with per-appliance Service Memory. The
technician queue and the review flows for ambiguous and new customers follow.
