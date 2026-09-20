import assert from "node:assert/strict";
import { test } from "node:test";

import type { Job } from "./api/types.ts";
import { buildQueue, workloadOf } from "./technician.ts";

const TZ = "Asia/Kolkata";
const NOW = new Date("2026-09-20T06:00:00Z"); // 11:30 on 20 Sep in India

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
    technician_id: "tec_1",
    status: "ASSIGNED",
    source: "manual",
    service_request_id: null,
    version: 1,
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
    completed_at: null,
    ...over,
  };
}

test("work in motion and work booked for today is 'today', busiest first", () => {
  const queue = buildQueue(
    [
      job("booked-late", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-20T11:30:00Z" } }),
      job("booked-early", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-20T05:30:00Z" } }),
      job("driving", { status: "ON_THE_WAY" }),
      job("working", { status: "IN_PROGRESS" }),
    ],
    TZ,
    NOW,
  );
  assert.deepEqual(queue.today.map((j) => j.job_id), ["working", "driving", "booked-early", "booked-late"]);
  assert.deepEqual(queue.later, []);
});

test("today is the business's day: 20:00 UTC on the 20th is already the 21st in India", () => {
  const queue = buildQueue([job("tomorrow", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-20T20:00:00Z" } })], TZ, NOW);
  assert.deepEqual(queue.today, []);
  assert.deepEqual(queue.later.map((j) => j.job_id), ["tomorrow"]);
});

test("later work is ordered by its visit, unscheduled work last", () => {
  const queue = buildQueue(
    [
      job("unscheduled"),
      job("day-after", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-22T05:00:00Z" } }),
      job("tomorrow", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-21T05:00:00Z" } }),
    ],
    TZ,
    NOW,
  );
  assert.deepEqual(queue.later.map((j) => j.job_id), ["tomorrow", "day-after", "unscheduled"]);
});

test("finished and cancelled work is not in the queue; the latest completions are listed", () => {
  const queue = buildQueue(
    [
      job("c1", { status: "COMPLETED", completed_at: "2026-09-18T10:00:00Z" }),
      job("c2", { status: "COMPLETED", completed_at: "2026-09-19T10:00:00Z" }),
      job("gone", { status: "CANCELLED" }),
      job("open"),
    ],
    TZ,
    NOW,
  );
  assert.deepEqual(queue.today.concat(queue.later).map((j) => j.job_id), ["open"]);
  assert.deepEqual(queue.recentlyCompleted.map((j) => j.job_id), ["c2", "c1"]);
});

test("workload counts open work per status and how much of it is today's", () => {
  const load = workloadOf(
    [
      job("a"),
      job("b", { status: "SCHEDULED", scheduled_slot: { start: "2026-09-20T09:00:00Z" } }),
      job("c", { status: "IN_PROGRESS" }),
      job("d", { status: "COMPLETED", completed_at: "2026-09-19T10:00:00Z" }),
    ],
    TZ,
    NOW,
  );
  assert.deepEqual(load, { open: 3, today: 2, byStatus: { ASSIGNED: 1, SCHEDULED: 1, ON_THE_WAY: 0, IN_PROGRESS: 1 } });
});
