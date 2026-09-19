# Demo dataset

A small, fully fictional service business, built to show KaamSetu's core loop end to end:
**conversation → understanding → job → technician → service event → memory.**

Every name, phone number (`90000 xxxxx`), address and message here is invented. Nothing is
random and nothing depends on when it runs.

## Commands

```bash
cd services/api
export AWS_PROFILE=<profile> AWS_REGION=<region> DATA_PROVIDER=dynamodb DYNAMODB_TABLE=<table>

python -m seed              # load (idempotent), then verify what is stored
python -m seed --verify     # read-only: verify only, write nothing
python -m seed --manifest   # print every id and the scenarios; needs no AWS access
python -m seed --as-of 2026-09-19T10:00:00+00:00   # anchor relative times (default shown)
```

Add `--create-table` against a local endpoint (`DYNAMODB_ENDPOINT_URL`) to create the table first.
In AWS the table comes from the infrastructure template; the script refuses to create one.

`--verify` checks the *pristine* dataset. Once people use the demo (new requests, jobs, events) it
reports the differences as FAIL lines and a different fingerprint; that is its job.

To reset a demo table, delete its items and load again: the result is identical
(same ids, same times, same fingerprint).

## Guarantees

- **Deterministic.** Records are built in memory from one fixed instant (`--as-of`) using the real
  domain workflow. Ids are readable and stable (`cus_demo_ravi_kumar`,
  `job_demo_gas_refill_ravi_lg_ac_0`). Two loads, into any storage, have the same fingerprint, and
  a test pins it.
- **Idempotent.** Each write first checks whether it was already applied (existence for creates,
  the stored version for updates). Running the seed again writes nothing and never undoes a change
  someone made afterwards, such as assigning a job.
- **Resumable.** An interrupted load is completed, not duplicated: tests crash it at several
  points and check the result equals a clean load.
- **Real data shape.** Every job comes from a ServiceRequest, linked atomically. Completed jobs
  have exactly one service event, and every job change has an audit record.
- **Honest fixtures.** The two AI-intake requests carry hand-written extractions labelled
  `model_id: "seed-fixture"`; no model produced them.

## What is in it

1 business, 4 technicians, 7 customers, 12 assets, 14 service requests, 13 jobs, 6 service events
and 78 audit records (the `--verify` output prints the live counts and the fingerprint).

### Technicians

| Name | Id | Skills | |
|---|---|---|---|
| Imran Sheikh | `tec_demo_imran` | air_conditioner, refrigerator | active |
| Suresh Patil | `tec_demo_suresh` | washing_machine, water_purifier, electrical | active |
| Kavitha Nair | `tec_demo_kavitha` | air_conditioner, television, computer, printer | active |
| Anil Deshpande | `tec_demo_anil` | plumbing | inactive |

### Customers and their appliances (unknown model, serial and warranty stay unknown)

| Customer | Phone | Appliances |
|---|---|---|
| Ravi Kumar | `90000 20001` | LG air conditioner, Samsung refrigerator |
| Ravi Verma | `90000 20002` | Voltas air conditioner |
| Meena Iyer | `90000 20003` | LG air conditioner, Samsung air conditioner, Kent water purifier, IFB washing machine |
| Farhan Qureshi | `90000 20004` | Samsung refrigerator |
| Lakshmi Prasad | `90000 20005` | Bosch washing machine |
| Gopal Reddy | `90000 20006` | HP printer, Dell computer |
| Nisha Bhat | `90000 20007` | Sony television |

### Jobs

| Status | Customer | Job | Technician | Urgency | Key |
|---|---|---|---|---|---|
| `NEW` | Meena Iyer | Water purifier flow is low | none | normal | `ro_flow_low_meena` |
| `NEW` | Farhan Qureshi | Refrigerator has a burning smell and sparks | none | safety_critical | `fridge_burning_smell_farhan` |
| `ASSIGNED` | Gopal Reddy | Printer not printing | Kavitha | normal | `printer_not_printing_gopal` |
| `SCHEDULED` | Lakshmi Prasad | Washing machine drum not spinning | Suresh | normal | `washer_drum_lakshmi` |
| `ON_THE_WAY` | Meena Iyer | AC not cooling in the hall | Imran | normal | `samsung_ac_hall_meena` |
| `IN_PROGRESS` | Gopal Reddy | Computer restarts randomly | Kavitha | normal | `laptop_restarts_gopal` |
| `COMPLETED` | Ravi Kumar | Annual AC service (210 days ago) | Imran | normal | `annual_service_ravi_lg_ac` |
| `COMPLETED` | Ravi Kumar | AC not cooling (45 days ago) | Imran | normal | `gas_refill_ravi_lg_ac` |
| `COMPLETED` | Ravi Kumar | Fridge door not sealing properly | Imran | normal | `gasket_ravi_samsung_fridge` |
| `COMPLETED` | Ravi Verma | Water leaking from indoor unit | Imran | normal | `drain_verma_voltas_ac` |
| `COMPLETED` | Meena Iyer | Filter set due for replacement | Suresh | normal | `filters_meena_kent_ro` |
| `COMPLETED` | Meena Iyer | AC making a rattling noise | Kavitha | normal | `rattle_meena_lg_ac` |
| `CANCELLED` | Nisha Bhat | TV shows no display | Kavitha | normal | `tv_no_display_nisha` |

Plus one request waiting for review, `new_customer_deepak` (no job).

## The five scenarios

Send each message to `POST /api/v1/intake` with the phone number shown (an `Idempotency-Key`
header makes retries safe).

1. **Repeat AC complaint with service history.** Ravi Kumar's LG AC was serviced twice (annual
   service, then a gas refill).
   Phone `90000 20001`: *"Bhaiya LG AC phir se thanda nahi kar raha. Kal 5 ke baad aa sakte ho?"*
   Expect a job, and prior service showing exactly those two recorded services (not the fridge's).
2. **Multiple assets per customer.** Meena Iyer owns two air conditioners.
   Phone `90000 20003`: *"AC thanda nahi kar raha"* is ambiguous, so it goes to review with no job.
   *"LG AC not cooling properly"* selects the LG unit. A name alone stays ambiguous too: "Ravi"
   matches two customers.
3. **New customer requiring review.** `new_customer_deepak` is already waiting. Phone
   `90000 29999`: *"Namaste, mera naam Deepak hai. Mere Godrej fridge ka compressor start nahi ho
   raha. Indiranagar mein hoon. Kal aa sakte ho?"* gives customer and asset NEW, needing review,
   and creates no job and no customer.
4. **Safety-critical request.** Farhan Qureshi's fridge job is already on the board, unassigned.
   Phone `90000 20004`: *"Fridge se chingari nikal rahi hai aur jalne ki smell aa rahi hai"* is
   flagged, creates a second job on the fridge with urgency `safety_critical`, and the description
   stays the customer's report, never a diagnosis.
5. **Technician and job lifecycle.** Every job status is on the board across three technicians.
   Try assigning Anil (inactive): it is refused. Drive `ro_flow_low_meena` through
   assign, start and complete, and its water purifier's history gains a second event.

## Extending it

Add records in `dataset.py` using the builder helpers, run the tests, and update the pinned
fingerprint (`GOLDEN_DIGEST` in `tests/integration/test_seed.py`) deliberately. A test fails if a job,
technician or the review request is missing from this file.
