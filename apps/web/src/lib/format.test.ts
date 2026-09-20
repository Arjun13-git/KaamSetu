import assert from "node:assert/strict";
import { test } from "node:test";

import {
  applianceLabel,
  dayWord,
  describeTimePreference,
  formatDateTime,
  formatPhone,
  formatSlot,
  relativeTime,
  utcToZonedInput,
  zonedToUtc,
} from "./format.ts";

const TZ = "Asia/Kolkata";
const NOW = new Date("2026-09-20T06:00:00Z"); // 11:30 on 20 Sep in India

test("dates are shown in the business timezone, not the server's", () => {
  assert.equal(formatDateTime("2026-09-21T11:30:00Z", TZ), "21 Sep, 5:00 pm");
  assert.equal(formatDateTime("2026-09-21T11:30:00Z", "UTC"), "21 Sep, 11:30 am");
});

test("day words follow the business calendar, across the UTC date boundary", () => {
  // 20:00 UTC on the 20th is already 01:30 on the 21st in India
  assert.equal(dayWord("2026-09-20T20:00:00Z", TZ, NOW), "Tomorrow");
  assert.equal(dayWord("2026-09-20T20:00:00Z", "UTC", NOW), "Today");
  assert.equal(dayWord("2026-09-19T06:00:00Z", TZ, NOW), "Yesterday");
});

test("slots read naturally and stay null when there is none", () => {
  assert.equal(formatSlot({ start: "2026-09-21T11:30:00Z" }, TZ, NOW), "Tomorrow, 5:00 pm");
  assert.equal(formatSlot({ start: "2026-09-21T11:30:00Z", end: "2026-09-21T13:30:00Z" }, TZ, NOW), "Tomorrow, 5:00 pm – 7:00 pm");
  assert.equal(formatSlot(null, TZ, NOW), null);
});

test("relative time uses honest, coarse units", () => {
  assert.equal(relativeTime("2026-09-20T05:59:40Z", NOW), "just now");
  assert.equal(relativeTime("2026-09-20T05:30:00Z", NOW), "30 min ago");
  assert.equal(relativeTime("2026-09-20T02:00:00Z", NOW), "4 h ago");
  assert.equal(relativeTime("2026-09-19T05:00:00Z", NOW), "yesterday");
  assert.equal(relativeTime("2026-08-06T11:30:00Z", NOW), "44 days ago");
  assert.equal(relativeTime("2026-02-22T11:30:00Z", NOW), "7 months ago");
});

test("a model's date and clock time are described without inventing missing parts", () => {
  assert.equal(describeTimePreference({ date: "2026-09-21", start: "17:00:00", end: null }, TZ, NOW), "Tomorrow, from 5:00 pm");
  assert.equal(describeTimePreference({ date: "2026-09-21", start: null, end: null }, TZ, NOW), "Tomorrow");
  assert.equal(describeTimePreference({ date: null, start: null, end: null }, TZ, NOW), null);
  assert.equal(describeTimePreference({ date: "2026-09-25", start: "09:00:00", end: "11:30:00" }, TZ, NOW), "Fri 25 Sep, 9:00 am – 11:30 am");
});

test("scheduling input round-trips through the business timezone", () => {
  assert.equal(zonedToUtc("2026-09-21T17:00", TZ), "2026-09-21T11:30:00.000Z");
  assert.equal(utcToZonedInput("2026-09-21T11:30:00Z", TZ), "2026-09-21T17:00");
  assert.equal(zonedToUtc("2026-01-15T12:00", "America/New_York"), "2026-01-15T17:00:00.000Z"); // EST
  assert.equal(zonedToUtc("2026-03-08T12:00", "America/New_York"), "2026-03-08T16:00:00.000Z"); // EDT
  assert.equal(zonedToUtc("garbage", TZ), null);
});

test("appliance labels use only what is recorded", () => {
  assert.equal(applianceLabel({ asset_type: "air_conditioner", brand: "LG" }), "LG air conditioner");
  assert.equal(applianceLabel({ asset_type: "washing_machine", brand: null }), "washing machine");
});

test("phone numbers are grouped only when they have the expected shape", () => {
  assert.equal(formatPhone("+919000020001"), "+91 90000 20001");
  assert.equal(formatPhone("12345"), "12345");
  assert.equal(formatPhone(null), null);
});
