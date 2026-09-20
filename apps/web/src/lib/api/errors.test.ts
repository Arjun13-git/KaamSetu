import assert from "node:assert/strict";
import { test } from "node:test";

import { failureFromBody, friendlyMessage } from "./errors.ts";

test("validation problems keep the field path and drop the request-body prefix", () => {
  const failure = failureFromBody(
    422,
    {
      error: {
        code: "VALIDATION_ERROR",
        message: "The request is not valid",
        details: { fields: [{ loc: ["body", "text"], message: "String should have at least 1 character", type: "x" }] },
      },
      request_id: "req_1",
    },
    null,
  );
  assert.deepEqual(failure.fields, [{ path: "text", message: "String should have at least 1 character" }]);
  assert.equal(failure.requestId, "req_1");
  assert.match(friendlyMessage(failure), /text: String should have/);
});

test("the API's own message is passed through for state conflicts", () => {
  const failure = failureFromBody(409, { error: { code: "INVALID_STATE_TRANSITION", message: "A NEW job cannot move to COMPLETED", details: {} } }, "req_9");
  assert.equal(failure.requestId, "req_9");
  assert.equal(friendlyMessage(failure), "A NEW job cannot move to COMPLETED");
});

test("a non-JSON failure still becomes a usable message", () => {
  const failure = failureFromBody(502, null, null);
  assert.equal(failure.code, "HTTP_502");
  assert.match(friendlyMessage(failure), /had a problem/);
});
