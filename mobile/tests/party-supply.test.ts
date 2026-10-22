import assert from "node:assert/strict";
import test from "node:test";
import { supplyCombo } from "../src/party-supply";

test("supply cards use strictly increasing speed with no card-count cap", () => {
  assert.deepEqual(supplyCombo("3, 5 → 8 > 12", "800"), {
    speeds: [3, 5, 8, 12],
    damage: 800,
  });
  const speeds = Array.from({ length: 100 }, (_, i) => i).join(",");
  assert.equal(supplyCombo(speeds, "99999").speeds.length, 100);
});
test("invalid speed order, repeated speeds and invalid damage cannot submit a supply combo", () => {
  for (const speeds of [
    "",
    "3,3",
    "5,2",
    "3.5,6",
    "3e1,40",
    "3,abc",
    "9007199254740993",
  ])
    assert.throws(() => supplyCombo(speeds, "800"));
  for (const damage of ["", "0", "-100", "800.5", "NaN", "Infinity"])
    assert.throws(() => supplyCombo("3,4", damage));
});
