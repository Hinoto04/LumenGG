import assert from "node:assert/strict";
import { test } from "node:test";
import {
  mySeat,
  normalizeRoomCode,
  roomOptionsText,
  roomOutcome,
  seatDeckText,
  type RoomSeat,
  type RoomView,
} from "../src/battle-room";

const seat = (over: Partial<RoomSeat> = {}): RoomSeat => ({ present: true, name: "p", deck: null, ready: false, me: false, ...over });

const room = (over: Partial<RoomView> = {}): RoomView => ({
  code: "ABC234",
  kind: "room",
  status: "waiting",
  options: { mode: "automatic", ready_timeout_seconds: 30, effect_timeout_seconds: 60 },
  seat: "guest",
  seats: { host: seat(), guest: seat({ me: true, name: "me" }) },
  error: "",
  ...over,
});

test("room codes are cleaned up while typing", () => {
  assert.equal(normalizeRoomCode(" abc-23 4x "), "ABC234X");
  assert.equal(normalizeRoomCode("abcdefghijk"), "ABCDEFGH");
});

test("my seat follows the seat the server gave this device", () => {
  assert.equal(mySeat(room()).name, "me");
  assert.equal(mySeat(room({ seat: "host" })).name, "p");
});

test("room options summary", () => {
  assert.equal(roomOptionsText({ mode: "automatic", ready_timeout_seconds: 30, effect_timeout_seconds: 0 }), "자동 판정 · 레디 30초 · 효과 선택 제한 없음");
  assert.equal(roomOptionsText({ mode: "manual" }), "수동(샌드박스)");
});

test("the opponent's deck shows only its character", () => {
  assert.equal(seatDeckText(seat({ present: false })), "상대를 기다리는 중…");
  assert.equal(seatDeckText(seat()), "덱을 고르는 중");
  assert.equal(seatDeckText(seat({ deck: { character: "루나" } })), "루나 덱");
  assert.equal(seatDeckText(seat({ me: true, deck: { character: "루나", id: 1, name: "내 덱" } })), "루나 · 내 덱");
});

test("a started room opens my seat, a closed one ends the wait", () => {
  assert.deepEqual(roomOutcome(room()), { kind: "wait" });
  assert.deepEqual(roomOutcome(room({ status: "started" })), { kind: "wait" });
  assert.deepEqual(roomOutcome(room({ status: "started", play_url: "https://x/battlelog/play/?seat=p2" })), {
    kind: "play",
    url: "https://x/battlelog/play/?seat=p2",
  });
  assert.deepEqual(roomOutcome(room({ status: "closed" })), { kind: "closed" });
});
