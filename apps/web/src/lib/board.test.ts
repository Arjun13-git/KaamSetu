import assert from "node:assert/strict";
import { test } from "node:test";

import type { Asset, Customer, Job, ServiceRequest, Technician } from "./api/types.ts";
import { buildBoard, reviewReason } from "./board.ts";

const TZ = "Asia/Kolkata";
const NOW = new Date("2026-09-20T06:00:00Z");

function job(id: string, over: Partial<Job> = {}): Job {
  return {
    job_id: id,
    customer_id: "cus_1",
    asset_id: "ast_1",
    service_type: "repair",
    description: id,
    urgency: "normal",
    preferred_slot: null,
    scheduled_slot: null,
    technician_id: null,
    status: "NEW",
    source: "intake",
    service_request_id: null,
    version: 1,
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
    completed_at: null,
    ...over,
  };
}

const lookups = {
  customers: new Map([["cus_1", { customer_id: "cus_1", name: "Ravi Kumar" } as Customer]]),
  assets: new Map([["ast_1", { asset_id: "ast_1", asset_type: "air_conditioner", brand: "LG" } as Asset]]),
  technicians: new Map([["tec_1", { technician_id: "tec_1", name: "Imran Sheikh" } as Technician]]),
};

test("cards are grouped by status, safety-critical first, then oldest first", () => {
  const board = buildBoard(
    [
      job("newer", { created_at: "2026-09-19T12:00:00Z" }),
      job("older", { created_at: "2026-09-19T09:00:00Z" }),
      job("urgent", { urgency: "safety_critical", created_at: "2026-09-19T15:00:00Z" }),
      job("moving", { status: "ON_THE_WAY", technician_id: "tec_1" }),
    ],
    [],
    lookups,
    { tz: TZ, now: NOW },
  );
  const byStatus = Object.fromEntries(board.columns.map((c) => [c.status, c.cards.map((x) => x.id)]));
  assert.deepEqual(byStatus.NEW, ["urgent", "older", "newer"]);
  assert.deepEqual(byStatus.ON_THE_WAY, ["moving"]);
  assert.equal(board.openCount, 4);
});

test("finished jobs leave the columns and appear in the finished lane", () => {
  const board = buildBoard(
    [job("done", { status: "COMPLETED", technician_id: "tec_1" }), job("gone", { status: "CANCELLED" }), job("open")],
    [],
    lookups,
    { tz: TZ, now: NOW },
  );
  assert.equal(board.columns.flatMap((c) => c.cards).length, 1);
  assert.deepEqual(board.finished.completed.map((c) => c.id), ["done"]);
  assert.deepEqual(board.finished.cancelled.map((c) => c.id), ["gone"]);
  assert.equal(board.openCount, 1);
});

test("the service-memory count is completed jobs for the same appliance, from the list alone", () => {
  const board = buildBoard(
    [
      job("a", { status: "COMPLETED" }),
      job("b", { status: "COMPLETED" }),
      job("c", { status: "COMPLETED", asset_id: "ast_2" }),
      job("now"),
    ],
    [],
    lookups,
    { tz: TZ, now: NOW },
  );
  assert.equal(board.columns[0].cards[0].pastServices, 2);
});

test("safety-critical open jobs are listed in the attention strip; finished ones are not", () => {
  const board = buildBoard(
    [job("s1", { urgency: "safety_critical" }), job("s2", { urgency: "safety_critical", status: "COMPLETED" })],
    [],
    lookups,
    { tz: TZ, now: NOW },
  );
  assert.deepEqual(board.attention.safety.map((c) => c.id), ["s1"]);
});

test("filtering by technician narrows the columns but not the safety strip", () => {
  const board = buildBoard(
    [job("mine", { technician_id: "tec_1", status: "ASSIGNED" }), job("other", { urgency: "safety_critical" })],
    [],
    lookups,
    { tz: TZ, now: NOW, technicianId: "tec_1" },
  );
  assert.deepEqual(board.columns.flatMap((c) => c.cards.map((x) => x.id)), ["mine"]);
  assert.deepEqual(board.attention.safety.map((c) => c.id), ["other"]);
});

test("names come from lookups and never fail the card when a lookup is missing", () => {
  const board = buildBoard([job("x", { customer_id: "cus_9", asset_id: "ast_9", technician_id: "tec_9", status: "ASSIGNED" })], [], lookups, {
    tz: TZ,
    now: NOW,
  });
  const card = board.columns[1].cards[0];
  assert.equal(card.customerName, "Unknown customer");
  assert.equal(card.technician?.name, "Technician");
});

test("a scheduled slot wins over the customer's preferred slot", () => {
  const board = buildBoard(
    [
      job("s", {
        status: "SCHEDULED",
        scheduled_slot: { start: "2026-09-21T11:30:00Z" },
        preferred_slot: { start: "2026-09-22T04:30:00Z" },
      }),
    ],
    [],
    lookups,
    { tz: TZ, now: NOW },
  );
  assert.deepEqual(board.columns[2].cards[0].slot, { label: "Tomorrow, 5:00 pm", kind: "scheduled" });
});

test("review reasons are readable", () => {
  const base = { status: "NEEDS_REVIEW" } as ServiceRequest;
  const res = (state: string) => ({ state, entity_id: null, candidates: [] }) as never;
  assert.equal(reviewReason({ ...base, customer_resolution: res("new"), asset_resolution: res("new") }), "New customer");
  assert.equal(reviewReason({ ...base, customer_resolution: res("existing"), asset_resolution: res("ambiguous") }), "Which appliance?");
  assert.equal(reviewReason({ ...base, status: "EXTRACTION_FAILED", customer_resolution: res("new"), asset_resolution: res("new") }), "The AI could not read this");
});

test("review rows say when the reading is a seeded fixture, never presenting it as AI output", () => {
  const request = (modelId: string) =>
    ({
      service_request_id: `srq_${modelId.length}`,
      status: "NEEDS_REVIEW",
      raw_text: "hi",
      extraction: { model_id: modelId, data: { intent: "service_request", asset: {}, problem: {}, time_preference: {}, confidence: {} } },
      customer_resolution: { state: "new", entity_id: null, candidates: [] },
      asset_resolution: { state: "new", entity_id: null, candidates: [] },
      created_at: "2026-09-19T10:00:00Z",
    }) as unknown as ServiceRequest;
  const board = buildBoard([], [request("seed-fixture"), request("amazon.nova-lite-v1:0")], lookups, { tz: TZ, now: NOW });
  assert.deepEqual(
    board.attention.review.map((r) => r.seeded).sort(),
    [false, true],
  );
});
