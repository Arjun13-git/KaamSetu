import assert from "node:assert/strict";
import { test } from "node:test";

import { cleanPhone, parsePhoneMap, rememberPhoneIn } from "./phone-map.ts";

test("a remembered phone survives a round trip", () => {
  const map = rememberPhoneIn({}, "srq_abc123", "90000 29999");
  assert.deepEqual(parsePhoneMap(JSON.stringify(map)), { srq_abc123: "90000 29999" });
});

test("the map is bounded: the oldest entries go first", () => {
  let map = {};
  for (let i = 0; i < 20; i += 1) map = rememberPhoneIn(map, `srq_${String(i).padStart(3, "0")}`, "90000 20001");
  const ids = Object.keys(map);
  assert.equal(ids.length, 12);
  assert.equal(ids[0], "srq_008");
  assert.equal(ids.at(-1), "srq_019");
});

test("remembering a request again moves it to the newest position", () => {
  let map = rememberPhoneIn({}, "srq_one", "90000 20001");
  map = rememberPhoneIn(map, "srq_two", "90000 20002");
  map = rememberPhoneIn(map, "srq_one", "90000 20009");
  assert.deepEqual(Object.keys(map), ["srq_two", "srq_one"]);
  assert.equal(map.srq_one, "90000 20009");
});

test("anything that does not look like an id or a phone number is refused", () => {
  assert.deepEqual(rememberPhoneIn({}, "../etc", "90000 20001"), {});
  assert.deepEqual(rememberPhoneIn({}, "srq_ok1", "<script>"), {});
  assert.equal(cleanPhone("<b>1</b>"), "");
  assert.equal(cleanPhone(" +919000020001 "), "+919000020001");
  assert.equal(cleanPhone(undefined), "");
});

test("a damaged cookie reads as empty instead of breaking the page", () => {
  assert.deepEqual(parsePhoneMap("not json"), {});
  assert.deepEqual(parsePhoneMap("[1,2]"), {});
  assert.deepEqual(parsePhoneMap('{"srq_ok1":"90000 20001","bad key":"1","srq_x9":{"a":1}}'), { srq_ok1: "90000 20001" });
  assert.deepEqual(parsePhoneMap(undefined), {});
});
