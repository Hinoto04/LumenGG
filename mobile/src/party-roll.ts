import type { PartyState, PartyRollResult } from "./party";

export type PartyRollStage =
  "rolling" | "settled" | "number" | "bonus" | "counting" | "total";
export function partyRollTimes(roll: PartyRollResult) {
  const at = (ms: number) =>
    roll.started_at + ((roll.end_at - roll.started_at) * ms) / 3200;
  return {
    settle: roll.settle_at ?? at(900),
    number: roll.number_at ?? at(1250),
    add: roll.add_at,
    count: roll.count_at ?? at(2050),
    total: roll.total_at ?? at(2500),
  };
}
export function partyRollNumber(roll: PartyRollResult, serverNow: number) {
  const base = roll.dice_values.reduce((sum, value) => sum + value, 0),
    times = partyRollTimes(roll);
  const progress = Math.max(
    0,
    Math.min(
      1,
      (serverNow - times.count) / Math.max(1, times.total - times.count),
    ),
  );
  return base + Math.round(roll.bonus * progress);
}

export function partyDieFace(
  roll: PartyRollResult,
  index: number,
  serverNow: number,
) {
  if (serverNow >= partyRollTimes(roll).settle) return roll.dice_values[index]!;
  const faces = [1, 5, 2, 6, 3, 4];
  return faces[
    (Math.floor(Math.max(0, serverNow - roll.started_at) / 75) + index * 2) % 6
  ]!;
}

// The server clock keeps spectators, reconnects, and devices with different clocks in phase.
export function partyRollStage(
  state: Pick<
    PartyState,
    "dice_roll" | "status" | "expired" | "turn" | "turn_number"
  > | null,
  serverNow: number,
): PartyRollStage | null {
  const roll = state?.dice_roll;
  if (
    !roll ||
    state?.status !== "running" ||
    state.expired ||
    roll.seat !== state.turn ||
    roll.turn_number !== state.turn_number ||
    serverNow >= roll.end_at
  )
    return null;
  const times = partyRollTimes(roll);
  if (serverNow < times.settle) return "rolling";
  if (serverNow < times.number) return "settled";
  if (serverNow < times.add) return "number";
  if (serverNow < times.count) return "bonus";
  if (serverNow < times.total) return "counting";
  return "total";
}
