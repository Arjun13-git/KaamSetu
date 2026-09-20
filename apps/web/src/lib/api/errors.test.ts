import assert from "node:assert/strict";
import { test } from "node:test";

import { failureFromBody, friendlyMessage, toFailure } from "./errors.ts";

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

test("a missing server setting is reported as configuration, without any value", () => {
  const error = new Error("KAAMSETU_API_URL is not set.");
  error.name = "ConfigError";
  const failure = toFailure(error);
  assert.equal(failure.code, "CONFIG_ERROR");
  assert.match(friendlyMessage(failure), /not set up to reach the KaamSetu service/);
});

test("credentials rejected by the API are described without naming the key", () => {
  const failure = failureFromBody(401, { error: { code: "UNAUTHORIZED", message: "Authentication required", details: {} } }, "req_1");
  assert.match(friendlyMessage(failure), /rejected this app's credentials/);
  assert.doesNotMatch(friendlyMessage(failure), /X-Demo-Key|secret/i);
});

test("network failures and timeouts read as recoverable", () => {
  const network = { code: "NETWORK_ERROR", message: "x", status: 0, requestId: null, fields: [] };
  const timeout = { ...network, code: "TIMEOUT" };
  assert.match(friendlyMessage(network), /try again/i);
  assert.match(friendlyMessage(timeout), /Nothing was lost/);
});
