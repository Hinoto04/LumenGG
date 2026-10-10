import { test } from "node:test";
import assert from "node:assert/strict";
import {
  deckColumns,
  deckSections,
  deckDescription,
  matchingDecks,
} from "../src/deck-display";
import type { Catalog, Deck } from "../src/types";
const deck: Deck = {
  uuid: "one",
  id: 1,
  name: "테스트 덱",
  character_id: 2,
  visibility: "public",
  description: "",
  keyword: "콤보",
  tags: "",
  author: { id: 1, username: "Player" },
  cards: [
    { card_id: 1, count: 4, hand: 1, side: 1 },
    { card_id: 2, count: 1, hand: 0, side: 0 },
    { card_id: 3, count: 2, hand: 0, side: 2 },
  ],
};
const catalog = {
  cards: [
    { id: 1, type: "공격", frame: 1 },
    { id: 2, type: "얼티밋", ultimate: true },
    { id: 3, type: "특수" },
  ],
} as unknown as Catalog;
test("sizes use exactly nine, six and three columns", () => {
  assert.deepEqual(deckColumns, { small: 9, medium: 6, large: 3 });
});
test("physical copies appear in list, hand and side order without double counting", () => {
  const sections = deckSections(deck, catalog);
  assert.deepEqual(
    sections.map((s) => s.title),
    ["리스트", "손패", "사이드"],
  );
  assert.deepEqual(
    sections.map((s) => s.tiles.length),
    [3, 1, 3],
  );
  assert.equal(sections[0]!.tiles.filter((t) => t.card_id === 2).length, 1);
  assert.equal(sections[2]!.tiles.filter((t) => t.card_id === 3).length, 2);
  sections.forEach((s) =>
    assert.equal(new Set(s.tiles.map((t) => t.key)).size, s.tiles.length),
  );
});
test("missing catalog cards retain their copies and IDs", () => {
  const sections = deckSections(deck, null);
  assert.deepEqual(
    sections.map((s) => s.tiles.length),
    [3, 1, 3],
  );
  assert.equal(sections[0]!.tiles[0]!.card, undefined);
});
test("my decks exclude deleted decks and drafts and match author and character", () => {
  const data = [
    deck,
    { ...deck, id: 2, deleted: true },
    { ...deck, id: undefined },
  ];
  assert.equal(matchingDecks(data, "Ｐｌａｙｅｒ", "2").length, 1);
  assert.equal(matchingDecks(data, "콤보").length, 1);
  assert.equal(matchingDecks(data, "", "3").length, 0);
});
test("web descriptions preserve paragraphs and decode entities without executable markup", () => {
  assert.equal(
    deckDescription(
      "<p>A &amp; B</p><p>설명<br>둘째 줄 &#xD55C;</p><script>alert(1)</script>",
    ),
    "A & B\n설명\n둘째 줄 한",
  );
});
