import { test } from "node:test";
import assert from "node:assert/strict";
import {
  newCalculator,
  reduceCalculator,
  normalizeSearch,
  deckError,
  adjustEntry,
  passiveActions,
  conditionMet,
} from "../src/core";
import type { Character, Card, Catalog, Deck } from "../src/types";
const character: Character = {
  id: 1,
  color: "#fff",
  img: "",
  img_sm: "",
  localized: {
    ko: { name: "루트" },
    en: { name: "Root" },
    ja: { name: "ルート" },
  },
  initial_hp: 5000,
  hand_table: { "5000": 5 },
  initial_passive_state: { charge: { value: false } },
};
const card: Card = {
  id: 1,
  code: "A",
  character_id: 1,
  type: "공격",
  ultimate: false,
  frame: 1,
  damage: 100,
  pos: "상단",
  body: "손",
  special: "",
  hit: "",
  guard: "",
  counter: "",
  g_top: "",
  g_mid: "",
  g_bot: "",
  img: "",
  img_mid: "",
  img_sm: "",
  localized: { ko: { name: "테스트" }, en: {}, ja: {} },
};
test("search handles code punctuation, full-width Latin, Japanese and casefold", () => {
  assert.equal(normalizeSearch(" CB０１-ＡＴ 001! "), "cb01at001");
  assert.equal(normalizeSearch("Straße"), "strasse");
  assert.equal(normalizeSearch("루트 · チャージ"), "루트チャージ");
});
test("HP/FP, undo and reset preserve the web calculators numeric semantics", () => {
  let state = newCalculator(character, character, "en");
  state = reduceCalculator(
    state,
    { action: "hp", target: "p1", amount: -6000 },
    100,
  );
  assert.equal(state.players.p1.hp, -1000);
  state = reduceCalculator(state, { action: "undo" }, 200);
  assert.equal(state.players.p1.hp, 5000);
  state = reduceCalculator(
    state,
    { action: "hp", target: "p1", amount: 200 },
    300,
  );
  assert.equal(state.players.p1.hp, 5200);
  state = reduceCalculator(
    state,
    { action: "fp", target: "p1", amount: -2 },
    400,
  );
  assert.equal(state.players.p1.fp, -2);
  state = reduceCalculator(
    state,
    { action: "passive", target: "p1", key: "charge", value: true },
    500,
  );
  state = reduceCalculator(state, { action: "reset_session" }, 600);
  assert.equal(state.players.p1.passive_state.charge?.value, false);
  assert.equal(state.players.p1.fp, 0);
});
test("timer toggles against deadline and sudden death resets both players", () => {
  let state = newCalculator(character, character, "ko");
  state = reduceCalculator(state, { action: "timer" }, 1000);
  assert.equal(state.timer.ends_at, new Date(11000).toISOString());
  state = reduceCalculator(state, { action: "timer" }, 2000);
  assert.equal(state.timer.is_running, false);
  state = reduceCalculator(
    state,
    { action: "sudden_death", enabled: true },
    3000,
  );
  assert.equal(state.players.p1.hp, 1000);
  assert.equal(state.players.p2.hp, 1000);
  assert.equal(state.sudden_death_turns_remaining, 3);
});
test("Tao harmony batches dependent changes and removes effect below threshold", () => {
  const player = newCalculator(character, character, "ko").players.p1;
  player.passive_state = {
    yang_counter: { value: 3 },
    yin_counter: { value: 4 },
  };
  const action = passiveActions(
    player,
    { adapter: "tao" },
    "p1",
    "yang_counter",
    4,
    "양",
  );
  assert.equal(action.action, "batch");
  assert.equal(action.actions?.[1]?.key, "harmony");
  player.passive_state.harmony = { value: true };
  player.passive_state.yang_counter = { value: 4 };
  const lowered = passiveActions(
    player,
    { adapter: "tao" },
    "p1",
    "yang_counter",
    2,
    "양",
  );
  assert.equal(lowered.actions?.length, 3);
  assert.equal(
    conditionMet(
      { type: "allAtLeast", keys: ["yang_counter", "yin_counter"], value: 3 },
      player,
    ),
    true,
  );
});
test("deck drafts retain unavailable references and forced sides match web", () => {
  let deck: Deck = {
    uuid: "test",
    name: "deck",
    character_id: 1,
    description: "",
    keyword: "",
    tags: "",
    visibility: "private",
    cards: [],
  };
  deck = adjustEntry(deck, { ...card, type: "특수 기술" }, "count", 1, {});
  assert.equal(deck.cards[0]?.hand, 0);
  assert.equal(deck.cards[0]?.side, 1);
  const catalog = {
    characters: [character],
    cards: [card],
    rules: { max_hand: 5, min_deck_size: 5, max_deck_sizes: { "1": 21 } },
  } as unknown as Catalog;
  deck.cards = [{ card_id: 999, count: 5, hand: 0, side: 0 }];
  assert.equal(deckError(deck, catalog), "사용할 수 없는 카드가 있습니다.");
});
