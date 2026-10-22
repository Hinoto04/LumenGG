import assert from "node:assert/strict";
import test from "node:test";
import { partyEventStage } from "../src/party-event";

const state = {
  status: "running" as const,
  expired: false,
  event: {
    id: "rich",
    label: "부자가 될거야",
    description: "모든 플레이어가 2코인씩 얻습니다.",
    seat: 0,
    version: 12,
    pending: true,
    show_at: 1000,
    reveal_until: 3400,
  },
};

test("event card waits for arrival and shows before the server applies the effect", () => {
  assert.equal(partyEventStage(state, 999), "waiting");
  assert.equal(partyEventStage(state, 1000), "card");
  assert.equal(partyEventStage(state, 3399), "card");
  assert.equal(partyEventStage(state, 3400), "waiting");
});
test("effect disappears and old or legacy events are never displayed persistently", () => {
  const applied = {
    ...state,
    event: { ...state.event, pending: false, effect_until: 5200 },
  };
  assert.equal(partyEventStage(applied, 3500), "effect");
  assert.equal(partyEventStage(applied, 5200), null);
  assert.equal(partyEventStage(applied, 100000), null);
  assert.equal(
    partyEventStage(
      { ...state, event: { ...state.event, pending: false } },
      1000,
    ),
    null,
  );
  assert.equal(partyEventStage({ ...applied, expired: true }, 3500), null);
  assert.equal(partyEventStage({ ...applied, status: "finished" }, 3500), null);
});
