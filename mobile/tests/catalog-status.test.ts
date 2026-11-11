import { test } from "node:test";
import assert from "node:assert/strict";
import { isCatalogUnavailable } from "../src/catalog-status";

test("only the server's no-catalog response is treated as a quiet no-update", () => {
  assert.equal(
    isCatalogUnavailable({
      status: 503,
      detail: { code: "catalog_unavailable" },
    }),
    true,
  );
  // 다른 503·네트워크 오류·404는 그대로 오류로 알린다.
  assert.equal(
    isCatalogUnavailable({ status: 503, detail: "Service Unavailable" }),
    false,
  );
  assert.equal(
    isCatalogUnavailable({
      status: 404,
      detail: { code: "catalog_unavailable" },
    }),
    false,
  );
  assert.equal(
    isCatalogUnavailable(new Error("Network request failed")),
    false,
  );
  assert.equal(isCatalogUnavailable(null), false);
});
