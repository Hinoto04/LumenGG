import { test } from "node:test";
import assert from "node:assert/strict";
import { addCopy, moveCopy, removeCopy, zoneCount } from "../src/deck-edit";
import { copyAvailability } from "../src/deck-rules";
import type { Card, Catalog, Deck } from "../src/types";

const card = (id: number, patch: Partial<Card> = {}): Card =>
  ({
    id,
    code: "C" + id,
    character_id: 2,
    type: "상단 공격",
    ultimate: false,
    original_name: "카드" + id,
    localized: { ko: { name: "카드" + id, text: "" } },
    ...patch,
  }) as Card;

const attack = card(1);
const special = card(2, { type: "특수" });
const ultimate = card(3, { type: "얼티밋", ultimate: true });
const otherUltimate = card(4, { type: "얼티밋", ultimate: true });
const triple = card(5, { deck_limit: 3 });
const printed = card(6, {
  localized: {
    ko: { name: "카드6", text: "이 기술은 2장까지 덱에 넣을 수 있다." },
  } as any,
});
const sameName = card(7, { original_name: "카드1" });

const catalog = {
  cards: [attack, special, ultimate, otherUltimate, triple, printed, sameName],
  characters: [{ id: 2, localized: { ko: { name: "테스트" } } }],
  rules: {},
} as unknown as Catalog;
const deckWith = (cards: Deck["cards"]): Deck => ({
  uuid: "d",
  name: "d",
  character_id: 2,
  description: "",
  keyword: "",
  tags: "",
  visibility: "private",
  cards,
});

test("카드를 넣으면 리스트로, 특수 기술은 사이드로 들어간다", () => {
  let cards = addCopy([], attack);
  cards = addCopy(cards, special);
  cards = addCopy(cards, special);
  assert.deepEqual(cards, [
    { card_id: 1, count: 1, hand: 0, side: 0 },
    { card_id: 2, count: 2, hand: 0, side: 2 },
  ]);
  assert.equal(zoneCount(cards[0]!, "list"), 1);
});

test("영역 이동은 한 장씩 옮기고 특수·얼티밋은 옮기지 않는다", () => {
  const start = [{ card_id: 5, count: 3, hand: 0, side: 0 }];
  let cards = moveCopy(start, triple, "list", "hand");
  cards = moveCopy(cards, triple, "list", "side");
  assert.deepEqual(cards, [{ card_id: 5, count: 3, hand: 1, side: 1 }]);
  cards = moveCopy(cards, triple, "hand", "side");
  assert.deepEqual(cards, [{ card_id: 5, count: 3, hand: 0, side: 2 }]);
  // 비어 있는 영역에서는 옮기지 않는다.
  assert.deepEqual(moveCopy(cards, triple, "hand", "list"), cards);
  const fixed = [{ card_id: 2, count: 1, hand: 0, side: 1 }];
  assert.equal(moveCopy(fixed, special, "side", "list"), fixed);
});

test("영역에서 한 장 빼면 그 영역 수량도 줄고 0장이면 항목이 사라진다", () => {
  const cards = [{ card_id: 5, count: 2, hand: 1, side: 0 }];
  assert.deepEqual(removeCopy(cards, 5, "hand"), [
    { card_id: 5, count: 1, hand: 0, side: 0 },
  ]);
  assert.deepEqual(removeCopy(removeCopy(cards, 5, "hand"), 5, "list"), []);
});

test("매수 제한만큼 넣은 카드는 더 넣을 수 없다", () => {
  const empty = copyAvailability(deckWith([]), catalog);
  assert.equal(empty(attack), 1);
  assert.equal(empty(triple), 3);
  assert.equal(empty(printed), 2);
  assert.equal(empty(ultimate), 1);
  const full = copyAvailability(
    deckWith([
      { card_id: 1, count: 1, hand: 0, side: 0 },
      { card_id: 5, count: 2, hand: 0, side: 0 },
      { card_id: 3, count: 1, hand: 0, side: 0 },
    ]),
    catalog,
  );
  assert.equal(full(attack), 0);
  // 이름이 같은 다른 카드도 같은 제한을 나눠 쓴다.
  assert.equal(full(sameName), 0);
  assert.equal(full(triple), 1);
  // 얼티밋은 종류와 관계없이 전체 1장까지다.
  assert.equal(full(otherUltimate), 0);
});
