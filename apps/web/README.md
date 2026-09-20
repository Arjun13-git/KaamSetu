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

| Route | What it shows |
|---|---|
| `/` | Job board: a column per active status, safety-critical jobs pinned in crimson, requests waiting for review, finished work in a collapsed lane |
| `/intake` | A customer's message becomes: customer → appliance → Service Memory → AI understanding → job |
| `/jobs/[id]` | Progress, the customer's words next to what the AI read, lifecycle actions, and the appliance's Service Memory |
| `/customers`, `/customers/[id]` | Customers, and each of their appliances with its own recorded service history |
| `/requests/[id]` | Review of a request KaamSetu would not turn into a job by itself: confirm the customer, the appliance, then create the job |
| `/technicians`, `/technicians/[id]` | Workload per technician, and a mobile-first queue with the moves a technician can make |

Colour has one meaning each: **teal** brand and progress, **blue** anything the AI produced,
**amber** recorded service (Service Memory), **crimson** safety-critical. Recorded history is shown
as history, never as a diagnosis.

### Review flow notes

The whole state of a review is in the URL (`?customer=&asset=&phone=`), and each step (add customer,
add appliance, create job) commits on its own, so retries cannot duplicate records. The API does not
store the phone typed at intake, so the app keeps it per request in an `httpOnly` cookie
(`ks_intake_phones`, 7 days, at most 12 requests) and in the review URL.

### Provenance labels

Labels state only what is recorded: `Seeded example` (a hand-written demo reading, model id
`seed-fixture`), `AI intake` (a real model reading), `No AI reading`. They are derived in the UI; the
API's `source` values are unchanged.
