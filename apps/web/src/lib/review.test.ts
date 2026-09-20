import assert from "node:assert/strict";
import { test } from "node:test";

import { parseExtraction } from "./extraction.ts";
import { assetFormDefaults, customerFormDefaults, jobFormDefaults, reviewUrl } from "./review.ts";

function reading(over: Record<string, unknown> = {}) {
  return parseExtraction({
    model_id: "m",
    data: {
      intent: "service_request",
      service_type: "repair",
      customer_reference: "Deepak",
      asset: { type: "refrigerator", brand: "Godrej", model: null },
      problem: { description: "Compressor not starting", urgency: null, symptoms: [] },
      time_preference: { date: "2026-09-21", start: "17:00:00", end: null },
      confidence: { overall: 0.9, asset: 0.9, problem: 0.9, schedule: 0.5 },
      missing_information: [],
      sources: {},
      ...over,
    },
  });
}

test("the job form starts from the AI's reading, and from the customer's words without one", () => {
  assert.deepEqual(jobFormDefaults(reading(), "raw words"), { description: "Compressor not starting", visitInput: "2026-09-21T17:00" });
  assert.deepEqual(jobFormDefaults(null, "raw words"), { description: "raw words", visitInput: "" });
});

test("a date without a time is not turned into a visit time", () => {
  const parsed = reading({ time_preference: { date: "2026-09-21", start: null, end: null } });
  assert.equal(jobFormDefaults(parsed, "x").visitInput, "");
});

test("a message too long to be a description leaves the field empty for a person to write", () => {
  assert.equal(jobFormDefaults(null, "x".repeat(2001)).description, "");
});

test("customer and appliance defaults keep unknown as empty", () => {
  assert.deepEqual(customerFormDefaults(reading()), { name: "Deepak" });
  assert.deepEqual(customerFormDefaults(null), { name: "" });
  assert.deepEqual(assetFormDefaults(reading()), { assetType: "refrigerator", brand: "Godrej", model: "" });
  assert.deepEqual(assetFormDefaults(reading({ asset: { type: "unknown", brand: "unknown", model: null } })), {
    assetType: "",
    brand: "",
    model: "",
  });
});

test("review URLs carry the whole context and nothing empty", () => {
  assert.equal(reviewUrl("srq_1"), "/requests/srq_1");
  assert.equal(
    reviewUrl("srq_1", { customer: "cus_1", asset: "ast_1", phone: "+91 90000 29999" }),
    "/requests/srq_1?customer=cus_1&asset=ast_1&phone=%2B91+90000+29999",
  );
  assert.equal(reviewUrl("srq_1", { customer: "", q: null, change: "asset" }), "/requests/srq_1?change=asset");
});
