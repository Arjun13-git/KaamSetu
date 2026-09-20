import assert from "node:assert/strict";
import { test } from "node:test";

import type { ServiceEvent } from "./api/types.ts";
import { parseExtraction } from "./extraction.ts";
import { reviewReasons, toMemory, understoodAs } from "./views.ts";

const TZ = "Asia/Kolkata";
const NOW = new Date("2026-09-20T06:00:00Z");

function event(id: string, timestamp: string, work: string): ServiceEvent {
  return {
    event_id: id,
    asset_id: "ast_1",
    customer_id: "cus_1",
    job_id: `job_${id}`,
    technician_id: "tec_imran",
    summary: "",
    work_performed: work,
    technician_notes: null,
    parts_used: [],
    observed_symptoms: [],
    follow_up_required: false,
    attachments: [],
    timestamp,
  };
}

test("service memory is newest first and names only what was recorded", () => {
  const memory = toMemory(
    "ast_1",
    "LG air conditioner",
    [event("old", "2026-02-22T11:30:00Z", "Filter cleaned"), event("new", "2026-08-06T11:30:00Z", "Gas refilled")],
    new Map([["tec_imran", "Imran Sheikh"]]),
    TZ,
    NOW,
  );
  assert.deepEqual(memory.events.map((e) => e.id), ["new", "old"]);
  assert.equal(memory.events[0].dateLabel, "6 Aug 2026");
  assert.equal(memory.events[0].technician, "Imran Sheikh");
  assert.equal(memory.lastServiceAgo, "44 days ago");
});

test("a technician who is no longer listed does not break the record", () => {
  const memory = toMemory("a", "x", [event("e", "2026-08-06T11:30:00Z", "w")], new Map(), TZ, NOW);
  assert.equal(memory.events[0].technician, null);
});

test("an appliance with no history has an empty memory, not an invented one", () => {
  const memory = toMemory("a", "x", [], new Map(), TZ, NOW);
  assert.deepEqual(memory.events, []);
  assert.equal(memory.lastServiceAgo, null);
});

test("'understood as' uses only extracted fields, and skips what is unknown", () => {
  const parsed = parseExtraction({
    model_id: "m",
    data: {
      intent: "service_request",
      service_type: "repair",
      customer_reference: null,
      asset: { type: "air_conditioner", brand: "LG", model: "unknown" },
      problem: { description: "AC is not cooling again", urgency: null, symptoms: [] },
      time_preference: { date: "2026-09-21", start: "17:00:00", end: null },
      confidence: { overall: 0.9, asset: 0.9, problem: 0.9, schedule: 0.9 },
      missing_information: [],
      sources: {},
    },
  });
  assert.equal(understoodAs(parsed, TZ, NOW), "LG air conditioner · AC is not cooling again · Tomorrow, from 5:00 pm");
  assert.equal(understoodAs(null, TZ, NOW), null);
});

test("review reasons follow the recorded resolution states", () => {
  assert.deepEqual(reviewReasons("job_created", "existing", "existing"), []);
  assert.deepEqual(reviewReasons("needs_review", "existing", "ambiguous"), ["Choose which appliance this is about"]);
  assert.deepEqual(reviewReasons("needs_review", "new", "new"), [
    "This looks like a new customer: add them before a job is created",
  ]);
  assert.deepEqual(reviewReasons("needs_review", "ambiguous", "unresolved"), ["Choose which customer this is"]);
  assert.deepEqual(reviewReasons("needs_review", "existing", "existing"), [
    "The AI was not confident enough to create the job unattended",
  ]);
});
