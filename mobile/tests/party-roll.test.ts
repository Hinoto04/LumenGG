import assert from "node:assert/strict";
import test from "node:test";
import {
  partyRollStage,
  partyRollNumber,
  partyDieFace,
} from "../src/party-roll";

const state = {
  status: "running",
  expired: false,
  turn: 1,
  turn_number: 3,
  dice_roll: {
    seat: 1,
    turn_number: 3,
    version: 8,
    dice_values: [2, 5],
    bonus: 2,
    total: 9,
    started_at: 10000,
    settle_at: 10900,
    number_at: 11250,
    add_at: 11700,
    count_at: 12050,
    total_at: 12500,
    end_at: 13200,
  },
};
test("dice faces change in place and lock to the server result at settlement", () => {
  const roll = state.dice_roll;
  const faces = Array.from({ length: 12 }, (_, i) =>
    partyDieFace(roll, 0, roll.started_at + i * 75),
  );
  assert.ok(new Set(faces).size >= 4);
  assert.ok(faces.every((value) => value >= 1 && value <= 6));
  assert.notEqual(partyDieFace(roll, 0, 10000), partyDieFace(roll, 1, 10000));
  for (const time of [10900, 11200, 12500, 50000]) {
    assert.equal(partyDieFace(roll, 0, time), 2);
    assert.equal(partyDieFace(roll, 1, time), 5);
  }
  assert.equal(partyRollNumber(roll, 12500), 9);
  assert.deepEqual(roll.dice_values, [2, 5]);
});
test("dice roll and settle before their sum becomes a number, then bonus joins before movement", () => {
  assert.equal(partyRollStage(state, 10000), "rolling");
  assert.equal(partyRollStage(state, 10899), "rolling");
  assert.equal(partyRollStage(state, 10900), "settled");
  assert.equal(partyRollStage(state, 11250), "number");
  assert.equal(partyRollStage(state, 11700), "bonus");
  assert.equal(partyRollStage(state, 12050), "counting");
  assert.equal(partyRollStage(state, 12500), "total");
  assert.equal(partyRollStage(state, 13199), "total");
  assert.equal(partyRollStage(state, 13200), null);
});
test("reconnects skip elapsed stages and old turns never replay the roll", () => {
  assert.equal(partyRollStage(state, 11500), "number");
  assert.equal(partyRollStage(state, 12200), "counting");
  assert.equal(partyRollStage(state, 50000), null);
  assert.equal(partyRollStage({ ...state, turn_number: 4 }, 10500), null);
  assert.equal(partyRollStage({ ...state, turn: 2 }, 10500), null);
  assert.equal(partyRollStage({ ...state, status: "finished" }, 10500), null);
  assert.equal(partyRollStage({ ...state, expired: true }, 10500), null);
  assert.equal(partyRollStage(null, 10500), null);
});
test("two dice disappear into their sum and movement power counts into the final number", () => {
  assert.equal(partyRollNumber(state.dice_roll, 11250), 7);
  assert.equal(partyRollNumber(state.dice_roll, 11700), 7);
  assert.equal(partyRollNumber(state.dice_roll, 12275), 8);
  assert.equal(partyRollNumber(state.dice_roll, 12500), 9);
  assert.equal(
    partyRollNumber({ ...state.dice_roll, bonus: 0, total: 7 }, 12275),
    7,
  );
});
test("an already rolled room without the new phase timestamps can still finish", () => {
  const legacy = {
    ...state,
    dice_roll: {
      ...state.dice_roll,
      settle_at: undefined,
      number_at: undefined,
      count_at: undefined,
      total_at: undefined,
      end_at: 12400,
      add_at: 11000,
    },
  };
  assert.equal(partyRollStage(legacy, 10950), "number");
  assert.equal(partyRollStage(legacy, 12200), "total");
  assert.equal(partyRollNumber(legacy.dice_roll, 12200), 9);
});
