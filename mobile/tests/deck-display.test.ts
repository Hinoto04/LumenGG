import { test } from "node:test";
import assert from "node:assert/strict";
import {
  bookmarkedDecks,
  mergeBookmarks,
  publicDeckPath,
  deckColumns,
  deckSections,
  deckDescription,
  matchingDecks,
  sortMyDecks,
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

test("my decks sort by version descending and keep recency within a version", () => {
  const make = (uuid: string, version: string) => ({ ...deck, uuid, version });
  const recent = [
    make("a", "AWL"),
    make("b", "LMI"),
    make("c", "AWL"),
    make("d", "LMI"),
  ];
  assert.deepEqual(
    sortMyDecks(recent, "version").map((d) => d.uuid),
    ["b", "d", "a", "c"],
  );
  assert.deepEqual(
    sortMyDecks(recent, "recent").map((d) => d.uuid),
    ["a", "b", "c", "d"],
  );
  assert.deepEqual(
    sortMyDecks(recent, "like").map((d) => d.uuid),
    ["a", "b", "c", "d"],
  );
});

test("bookmark filter keeps only bookmarked uploaded decks", () => {
  const decks = [{ id: 1 }, { id: 2 }, {}] as { id?: number }[];
  assert.deepEqual(bookmarkedDecks(decks, [2, 9], false), decks);
  assert.deepEqual(bookmarkedDecks(decks, [2, 9], true), [{ id: 2 }]);
  assert.deepEqual(bookmarkedDecks(decks, [], true), []);
});
test("public deck path adds bookmark and page only when requested", () => {
  assert.equal(
    publicDeckPath({ query: " 콤보 ", character: "3", sort: "like" }),
    "/decks?scope=public&q=%EC%BD%A4%EB%B3%B4&character_id=3&trait_card_id=&regulation_version_id=&sort=like",
  );
  assert.equal(
    publicDeckPath({
      query: "",
      character: "",
      trait: "7",
      regulation: "2",
      bookmarked: true,
      page: 2,
    }),
    "/decks?scope=public&q=&character_id=&trait_card_id=7&regulation_version_id=2&bookmarked=1&page=2",
  );
});
test("server bookmark flags update the local bookmark list", () => {
  assert.deepEqual(
    mergeBookmarks(
      [3, 1],
      [{ id: 2, bookmarked: true }, { id: 3, bookmarked: false }, { id: 4 }],
    ),
    [1, 2],
  );
  assert.equal(mergeBookmarks([2, 1], [{ id: 1, bookmarked: true }]), null);
});
