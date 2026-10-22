import test from "node:test";
import assert from "node:assert/strict";
import {
  calculatorAppearance,
  defaultAppearance,
} from "../src/calculator-appearance";
test("old or malformed display preferences use a dark readable default", () => {
  for (const value of [
    undefined,
    null,
    "clean",
    { style: "unknown", brightness: "0" },
    { brightness: NaN },
  ])
    assert.deepEqual(calculatorAppearance(value), defaultAppearance);
  assert.deepEqual(calculatorAppearance({ style: "clean", brightness: 0 }), {
    style: "clean",
    brightness: 0,
  });
  assert.equal(calculatorAppearance({ brightness: 120 }).brightness, 100);
  assert.equal(calculatorAppearance({ brightness: -2 }).brightness, 0);
});
