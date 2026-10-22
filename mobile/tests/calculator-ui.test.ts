import test from "node:test";
import assert from "node:assert/strict";
import {
  calculatorUi,
  calculatorLink,
  linkedCalculatorUi,
  calculatorTheme,
} from "../src/calculator-ui";
import { newCalculator, reduceCalculator } from "../src/core";
import type { Character } from "../src/types";

test("UI links preserve role tokens, queries and fragments; old links default to classic", () => {
  assert.equal(calculatorUi(undefined), "classic");
  assert.equal(calculatorUi("unknown"), "classic");
  const source = "/battlelog/session/view/control/secret/?lang=ja#history";
  const selected = calculatorLink(source, "character");
  assert.equal(
    selected,
    "/battlelog/session/view/control/secret/?lang=ja&ui=character#history",
  );
  assert.equal(linkedCalculatorUi(selected), "character");
  assert.equal(linkedCalculatorUi(source), undefined);
  assert.equal(calculatorLink(selected, "classic"), source);
});
test("older local characters resolve packaged themes while unknown characters use the neutral skin", () => {
  assert.equal(calculatorTheme({ id: 3 }).theme_key, "root");
  assert.equal(calculatorTheme({ id: 99999 }).theme_key, "default");
  assert.equal(
    calculatorTheme({
      id: 3,
      calculator_ui: {
        theme_key: "unknown",
        accent: "red",
        secondary: "red",
        motif: "none",
      },
    }).theme_key,
    "default",
  );
});
test("local theme metadata survives calculator actions without changing resource semantics", () => {
  const c = {
    id: 3,
    color: "#ff0000",
    img: "",
    localized: { ko: { name: "루트", passive: { controls: [] } } },
    initial_hp: 5000,
    hand_table: { 5000: 6 },
    initial_passive_state: {},
    calculator_ui: calculatorTheme({ id: 3 }),
  } as unknown as Character;
  const original = newCalculator(c, c, "ko");
  assert.equal(original.players.p1.character.color, "#ff0000");
  const changed = reduceCalculator(original, {
    action: "hp",
    target: "p1",
    amount: -100,
  });
  assert.equal(changed.players.p1.hp, 4900);
  assert.deepEqual(
    changed.players.p1.character.calculator_ui,
    original.players.p1.character.calculator_ui,
  );
  assert.equal(original.players.p1.hp, 5000);
});
