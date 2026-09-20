import assert from "node:assert/strict";
import { test } from "node:test";

import { confidenceBand, knownText, missingLabel, parseExtraction } from "./extraction.ts";

// A stored extraction as the API returns it (the hero scenario, from a real intake response).
const HERO = {
  schema_version: "intake_extraction.v1",
  prompt_version: "intake_v1",
  model_id: "amazon.nova-lite-v1:0",
  safety_concern: false,
  image_supplied: false,
  warnings: [],
  data: {
    intent: "service_request",
    service_type: "repair",
    customer_reference: null,
    asset: { type: "air_conditioner", brand: "LG", model: null },
    problem: { description: "AC is not cooling again", urgency: null, symptoms: ["not cooling again"] },
    time_preference: { date: "2026-09-21", start: "17:00:00", end: null },
    confidence: { overall: 0.9, asset: 0.9, problem: 0.9, schedule: 0.9 },
    missing_information: [],
    sources: { "asset.brand": "explicit_text", "asset.model": "unknown", bogus: "made_up" },
  },
};

test("a real extraction is read into the shape the UI uses", () => {
  const parsed = parseExtraction(HERO);
  assert.ok(parsed);
  assert.equal(parsed.data.asset.brand, "LG");
  assert.equal(parsed.data.asset.model, null);
  assert.equal(parsed.data.problem.symptoms[0], "not cooling again");
  assert.deepEqual(parsed.data.sources, { "asset.brand": "explicit_text", "asset.model": "unknown" });
  assert.equal(parsed.isFixture, false);
});

test("placeholder words written by the model become 'not known'", () => {
  assert.equal(knownText("unknown"), null);
  assert.equal(knownText(" NULL "), null);
  assert.equal(knownText("N/A"), null);
  assert.equal(knownText("LG"), "LG");
  assert.equal(knownText("Unknown Brand X"), "Unknown Brand X");
  assert.equal(knownText(null), null);
  const messy = structuredClone(HERO);
  messy.data.asset.brand = "unknown" as never;
  messy.data.asset.model = "null" as never; // the model writes text where the schema says null
  const parsed = parseExtraction(messy);
  assert.equal(parsed?.data.asset.brand, null);
  assert.equal(parsed?.data.asset.model, null);
});

test("seeded fixtures are labelled as such", () => {
  assert.equal(parseExtraction({ ...HERO, model_id: "seed-fixture" })?.isFixture, true);
});

test("anything that is not an extraction is rejected instead of guessed at", () => {
  assert.equal(parseExtraction(null), null);
  assert.equal(parseExtraction("text"), null);
  assert.equal(parseExtraction({ model_id: "x" }), null);
  assert.equal(parseExtraction({ data: [] }), null);
});

test("out-of-range confidence is treated as no confidence, not as certainty", () => {
  const odd = structuredClone(HERO);
  odd.data.confidence.overall = 7;
  assert.equal(parseExtraction(odd)?.data.confidence.overall, 0);
});

test("labels and bands", () => {
  assert.equal(missingLabel("asset.model"), "Appliance model");
  assert.equal(missingLabel("some_field.x"), "Some field x");
  assert.equal(confidenceBand(0.9), "high");
  assert.equal(confidenceBand(0.6), "medium");
  assert.equal(confidenceBand(0.2), "low");
});
