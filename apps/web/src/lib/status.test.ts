import assert from "node:assert/strict";
import { test } from "node:test";

import { isTerminal, nextActions } from "./status.ts";

// Mirrors the API's legal-transition table (services/api/app/domain/job_state_machine.py).
const LEGAL: Record<string, string[]> = {
  NEW: ["ASSIGNED", "CANCELLED"],
  ASSIGNED: ["SCHEDULED", "ON_THE_WAY", "IN_PROGRESS", "CANCELLED"],
  SCHEDULED: ["ON_THE_WAY", "IN_PROGRESS", "CANCELLED"],
  ON_THE_WAY: ["IN_PROGRESS", "CANCELLED"],
  IN_PROGRESS: ["COMPLETED", "CANCELLED"],
};

test("every suggested action is one the API's state machine allows", () => {
  for (const [status, allowed] of Object.entries(LEGAL)) {
    for (const action of nextActions(status as never, true)) {
      if (action.kind === "transition") assert.ok(allowed.includes(action.to), `${status} -> ${action.to}`);
      if (action.kind === "schedule") assert.ok(allowed.includes("SCHEDULED"), `${status} schedule`);
      if (action.kind === "complete") assert.ok(allowed.includes("COMPLETED"), `${status} complete`);
      if (action.kind === "cancel") assert.ok(allowed.includes("CANCELLED"), `${status} cancel`);
    }
  }
});

test("completion is offered only while the work is in progress", () => {
  for (const status of ["NEW", "ASSIGNED", "SCHEDULED", "ON_THE_WAY"] as const) {
    assert.equal(nextActions(status, true).some((a) => a.kind === "complete"), false, status);
  }
  assert.equal(nextActions("IN_PROGRESS", true).some((a) => a.kind === "complete"), true);
});

test("finished jobs offer no actions", () => {
  assert.deepEqual(nextActions("COMPLETED", true), []);
  assert.deepEqual(nextActions("CANCELLED", false), []);
  assert.equal(isTerminal("COMPLETED") && isTerminal("CANCELLED") && !isTerminal("NEW"), true);
});
