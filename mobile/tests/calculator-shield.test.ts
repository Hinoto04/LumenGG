import test from "node:test";
import assert from "node:assert/strict";
import { reduceCalculator } from "../src/core";
import { shieldAmount, setShield } from "../src/calculator-shield";
import type { CalcState, Action } from "../src/types";

function state(): CalcState {
  const player = (finf: boolean) => ({
    name: finf ? "핀프" : "루트",
    hp: 5000,
    fp: 0,
    initial_hp: 5000,
    passive_state: {},
    character: {
      name: finf ? "핀프" : "루트",
      calculator_ui: { theme_key: finf ? "finf" : "root" },
      initial_passive_state: {},
    },
  });
  return {
    version: 1,
    players: { p1: player(true), p2: player(false) },
    timer: { is_running: false, duration_seconds: 10 },
    events: [],
    sudden_death: false,
    sudden_death_turns_remaining: 0,
    can_control: true,
  } as CalcState;
}
const apply = (s: CalcState, action: string, amount?: number) =>
  reduceCalculator(s, { action, target: "p1", amount });
test("shield absorbs all, equal and excess damage before HP; healing never restores shield", () => {
  for (const [damage, hp, shield] of [
    [100, 5000, 200],
    [300, 5000, 0],
    [500, 4800, 0],
  ]) {
    const next = apply(apply(state(), "shield", 300), "hp", -damage!);
    assert.equal(next.players.p1.hp, hp);
    assert.equal(shieldAmount(next.players.p1), shield);
    const undone = apply(next, "undo");
    assert.equal(undone.players.p1.hp, 5000);
    assert.equal(shieldAmount(undone.players.p1), 300);
    const healed = apply(next, "hp", 100);
    assert.equal(healed.players.p1.hp, hp! + 100);
    assert.equal(shieldAmount(healed.players.p1), shield);
  }
});
test("shield has no gameplay cap and undo preserves later shield gains", () => {
  assert.equal(shieldAmount(apply(apply(state(), "shield", 30000), "shield", 30000).players.p1), 60000);
  let s = apply(apply(state(), "shield", 300), "hp", -500);
  s = apply(s, "shield", 200);
  s = apply(s, "undo");
  assert.equal(s.players.p1.hp, 5000);
  assert.equal(shieldAmount(s.players.p1), 500);
  assert.equal(s.events.find((e) => e.type === "hp")?.undone, true);
});
test("manual shield reset, nonnegative subtraction, FP reset, full reset and legacy saves", () => {
  let s = apply(state(), "shield", 300);
  s = apply(s, "fp_reset");
  assert.equal(shieldAmount(s.players.p1), 300);
  s = apply(s, "shield", -500);
  assert.equal(shieldAmount(s.players.p1), 0);
  s = apply(apply(s, "shield", 200), "shield_reset");
  assert.equal(shieldAmount(s.players.p1), 0);
  s = apply(apply(s, "shield", 200), "reset_session");
  assert.equal(shieldAmount(s.players.p1), 0);
  s = reduceCalculator(apply(s, "shield", 200), {
    action: "sudden_death",
    enabled: true,
  });
  assert.equal(s.players.p1.hp, 1000);
  assert.equal(shieldAmount(s.players.p1), 0);
  const old = state();
  assert.equal(shieldAmount(old.players.p1), 0);
  const restored = JSON.parse(JSON.stringify(apply(old, "shield", 300)));
  assert.equal(shieldAmount(apply(restored, "hp", -400).players.p1), 0);
});
test("other characters cannot gain or consume a shield, and malformed deltas are ignored", () => {
  const s = state();
  setShield(s.players.p2, 300);
  const hit = reduceCalculator(s, { action: "hp", target: "p2", amount: -500 });
  assert.equal(hit.players.p2.hp, 4500);
  assert.equal(
    reduceCalculator(s, { action: "shield", target: "p2", amount: 100 }),
    s,
  );
  for (const amount of [0, 0.5, NaN, 50001])
    assert.equal(apply(s, "shield", amount), s);
});
