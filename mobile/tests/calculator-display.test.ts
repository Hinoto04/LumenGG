import { test } from "node:test";
import assert from "node:assert/strict";
import {
  hpAppearance,
  nextTaoEffect,
  passiveActive,
} from "../src/calculator-display";

test("HP background follows the web's continuous initial-HP ratio rather than fixed thresholds", () => {
  assert.equal(hpAppearance(5000, 5000).hue, 140);
  assert.equal(hpAppearance(2500, 5000).hue, 72);
  assert.equal(hpAppearance(500, 5000).hue, 18);
  assert.equal(hpAppearance(0, 5000).hue, 4);
  assert.equal(hpAppearance(-100, 5000).ratio, 0);
  assert.equal(hpAppearance(7000, 5000).ratio, 1);
  assert.equal(
    hpAppearance(4000, 8000).background,
    hpAppearance(2500, 5000).background,
  );
});
test("Tao effect buttons toggle off on a second tap and switch the single selected effect", () => {
  let selected = nextTaoEffect("", "damage_100");
  assert.equal(selected, "damage_100");
  selected = nextTaoEffect(selected, "damage_100");
  assert.equal(selected, "");
  selected = nextTaoEffect(selected, "fp_1");
  assert.equal(nextTaoEffect(selected, "damage_100"), "damage_100");
  assert.equal(passiveActive("false"), false);
  assert.equal(passiveActive("OFF"), false);
  assert.equal(passiveActive("on"), true);
});
