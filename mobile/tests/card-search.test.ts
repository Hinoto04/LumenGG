import { test } from "node:test";
import assert from "node:assert/strict";
import { sortCards } from "../src/card-search";
import type { Card, Catalog } from "../src/types";

const catalog: Pick<Catalog, "packs" | "collection"> = {
  packs: [],
  collection: [],
};
const card = (id: number, values: Partial<Card> = {}): Card =>
  ({
    id,
    code: `CB-${id}`,
    localized: {
      ko: { name: `카드 ${id}` },
      en: { name: `Card ${id}` },
      ja: { name: `カード ${id}` },
    },
    frame: null,
    damage: null,
    hit: "",
    guard: "",
    counter: "",
    ...values,
  }) as Card;
const ids = (cards: Card[]) => cards.map((c) => c.id);

test("numeric sorting keeps missing values last in both directions and preserves source array", () => {
  const cards = [
    card(1),
    card(2, { damage: 100 }),
    card(3, { damage: 0 }),
    card(4, { damage: 1000 }),
  ];
  assert.deepEqual(
    ids(sortCards(cards, "damage_asc", "ko", catalog)),
    [3, 2, 4, 1],
  );
  assert.deepEqual(
    ids(sortCards(cards, "damage_desc", "ko", catalog)),
    [4, 2, 3, 1],
  );
  assert.deepEqual(ids(cards), [1, 2, 3, 4]);
});
test("signed frame advantage is numeric while non-numeric rulings remain searchable at the end", () => {
  const cards = [
    card(1, { hit: "콤보" }),
    card(2, { hit: "+10" }),
    card(3, { hit: "−3" }),
    card(4, { hit: "+2" }),
  ];
  assert.deepEqual(
    ids(sortCards(cards, "hit_asc", "ko", catalog)),
    [3, 4, 2, 1],
  );
  assert.deepEqual(
    ids(sortCards(cards, "hit_desc", "ko", catalog)),
    [2, 4, 3, 1],
  );
});
test("card numbers use natural ordering and equal values have stable code/id ties", () => {
  const cards = [
    card(10, { frame: 5 }),
    card(2, { frame: 5 }),
    card(1, { code: null, frame: 5 }),
    card(3, { code: "CB-2", frame: 5 }),
  ];
  assert.deepEqual(
    ids(sortCards(cards, "code_asc", "en", catalog)),
    [2, 3, 10, 1],
  );
  assert.deepEqual(
    ids(sortCards(cards, "code_desc", "en", catalog)),
    [10, 2, 3, 1],
  );
});
test("name sorting follows selected translation and falls back to Korean", () => {
  const cards = [
    card(1, {
      localized: { ko: { name: "가" }, en: { name: "Zulu" }, ja: {} },
    }),
    card(2, {
      localized: { ko: { name: "나" }, en: { name: "Alpha" }, ja: {} },
    }),
  ];
  assert.deepEqual(ids(sortCards(cards, "name_asc", "en", catalog)), [2, 1]);
  assert.deepEqual(ids(sortCards(cards, "name_asc", "ko", catalog)), [1, 2]);
  assert.deepEqual(ids(sortCards(cards, "name_desc", "ja", catalog)), [2, 1]);
});
test("release sorting uses the first printing date even when later reprints exist", () => {
  const releases = {
    packs: [
      { id: 1, released: "2024-01-01" },
      { id: 2, released: "2026-01-01" },
      { id: 3, released: "2025-01-01" },
    ],
    collection: [
      { card_id: 1, pack_id: 2 },
      { card_id: 1, pack_id: 1 },
      { card_id: 2, pack_id: 3 },
    ],
  } as Pick<Catalog, "packs" | "collection">;
  assert.deepEqual(
    ids(sortCards([card(1), card(2), card(3)], "release_desc", "ko", releases)),
    [2, 1, 3],
  );
  assert.deepEqual(
    ids(sortCards([card(1), card(2), card(3)], "release_asc", "ko", releases)),
    [1, 2, 3],
  );
});
