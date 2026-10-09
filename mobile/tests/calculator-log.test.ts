import { test } from "node:test";
import assert from "node:assert/strict";
import { newCalculator, reduceCalculator } from "../src/core";
import { calculatorLogRows } from "../src/calculator-log";
import type { Character } from "../src/types";
const character: Character = {
  id: 1,
  img: "",
  img_sm: "",
  color: "",
  initial_hp: 5000,
  hand_table: {},
  initial_passive_state: {
    yang: { count: 2 },
    charge: { value: false },
    effect: { value: "" },
  },
  localized: {
    ko: {
      name: "루트",
      passive: {
        controls: [
          { key: "yang", label: "양", type: "counter" },
          { key: "charge", label: "차지", type: "toggle" },
          {
            key: "effect",
            label: "조화 효과",
            type: "choice",
            choices: [{ value: "damage_100", label: "+100DMG" }],
          },
        ],
      },
    },
    en: {},
    ja: {},
  },
};
const identity = (key: string) => key;
test("new passive logs capture numeric and boolean before/after values and the affected player", () => {
  let state = newCalculator(character, character, "ko");
  state = reduceCalculator(
    state,
    { action: "passive", target: "p2", key: "yang", value: 3 },
    100,
  );
  state = reduceCalculator(
    state,
    { action: "passive", target: "p1", key: "charge", value: true },
    200,
  );
  const rows = calculatorLogRows(state, identity);
  assert.equal(rows[0]!.title, "차지");
  assert.equal(rows[0]!.detail, "비활성 → 활성");
  assert.equal(rows[0]!.target, "p1");
  assert.equal(rows[1]!.title, "양");
  assert.equal(rows[1]!.detail, "2 → 3");
  assert.equal(rows[1]!.target, "p2");
  assert.match(rows[1]!.player, /플레이어2/);
});
test("FP deltas and reset logs preserve zero and old/new quantities", () => {
  let state = newCalculator(character, character, "ko");
  state = reduceCalculator(
    state,
    { action: "fp", target: "p1", amount: 3 },
    100,
  );
  state = reduceCalculator(state, { action: "fp_reset", target: "p1" }, 200);
  assert.deepEqual(
    calculatorLogRows(state, identity).map((row) => row.detail),
    ["3 → 0", "0 → 3"],
  );
});
test("shared event payloads and choice values display meaningful names rather than internal values", () => {
  const state = newCalculator(character, character, "ko");
  state.events = [
    {
      id: 8,
      type: "passive",
      target: "p2",
      created_at: "2026-10-10T01:00:00Z",
      payload: {
        key: "effect",
        label: "조화 효과",
        before_state: { value: "" },
        after_state: { value: "damage_100" },
      },
    },
    {
      id: 9,
      type: "fp",
      target: "p2",
      created_at: "2026-10-10T01:00:01Z",
      payload: { before: 4, after: 2 },
    },
  ];
  const rows = calculatorLogRows(state, identity);
  assert.equal(rows[0]!.detail, "4 → 2");
  assert.equal(rows[1]!.detail, "선택 없음 → +100DMG");
});
test("timer actions keep working without creating local logs and old shared timers are hidden before limiting history", () => {
  let state = newCalculator(character, character, "ko");
  state = reduceCalculator(state, { action: "timer" }, 1000);
  assert.equal(state.events.length, 0);
  assert.equal(state.timer.ends_at, new Date(11000).toISOString());
  state.events = [
    ...Array.from({ length: 120 }, (_, id) => ({ id, type: "timer" })),
    { id: 121, type: "hp", target: "p1", hp_before: 5000, hp_after: 4900 },
  ];
  assert.equal(calculatorLogRows(state, identity).length, 1);
});
test("legacy passive events with missing values are marked unknown instead of inventing a zero change", () => {
  const state = newCalculator(character, character, "ko");
  state.events = [{ type: "passive", target: "p1", amount: 0 }];
  assert.equal(
    calculatorLogRows(state, identity)[0]!.detail,
    "기록 없음 → 기록 없음",
  );
});
test("undo is attributed to the player whose HP changed", () => {
  let state = newCalculator(character, character, "ko");
  state = reduceCalculator(
    state,
    { action: "hp", target: "p2", amount: -100 },
    100,
  );
  state = reduceCalculator(state, { action: "undo" }, 200);
  const rows = calculatorLogRows(state, identity);
  assert.equal(rows[0]!.target, "p2");
  assert.equal(rows[0]!.detail, "4900 → 5000");
  assert.equal(rows[1]!.undone, true);
});
test("legacy binary passive counts are formatted as inactive/active rather than a numeric zero", () => {
  const state = newCalculator(character, character, "ko");
  state.events = [
    {
      type: "passive",
      target: "p1",
      payload: {
        key: "charge",
        label: "차지",
        before_state: { count: 0 },
        after_state: { value: true },
      },
    },
  ];
  assert.equal(calculatorLogRows(state, identity)[0]!.detail, "비활성 → 활성");
});
