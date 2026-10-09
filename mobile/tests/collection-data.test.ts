import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cardPrintings,
  collectionRows,
  emptyCollectionFilters,
} from "../src/collection-data";
import type { Card, CollectionItem, Pack } from "../src/types";

const item = (
  id: number,
  fields: Partial<CollectionItem> = {},
): CollectionItem => ({
  id,
  card_id: 39,
  character_id: 2,
  pack_id: 1,
  item_type: "card",
  rare: "N",
  code: "ST1-001",
  name: "번개",
  image: "",
  img_sm: "",
  ...fields,
});
const packs: Pack[] = [
  {
    id: 1,
    code: "ST1",
    released: "2024-02-20",
    localized: { ko: { name: "스타터" }, en: {}, ja: {} },
  },
  {
    id: 2,
    code: "PR",
    released: "2023-01-01",
    localized: { ko: { name: "프로모" }, en: {}, ja: {} },
  },
];
test("printing rows combine rarities but preserve reprints, skins and same-code packs", () => {
  const collection = [
    item(1),
    item(2, { rare: "R" }),
    item(3, { rare: "R" }),
    item(4, { pack_id: 2 }),
    item(5, { item_type: "skin" }),
    item(6, { card_id: 99 }),
  ];
  const before = JSON.stringify(collection);
  const rows = cardPrintings(39, { collection, packs });
  assert.equal(rows.length, 3);
  assert.equal(rows[0]!.pack?.id, 2);
  const main = rows.find(
    (row) => row.pack?.id === 1 && row.items[0]?.item_type === "card",
  )!;
  assert.deepEqual(main.rarities, ["N", "R"]);
  assert.equal(main.items.length, 3);
  assert.equal(JSON.stringify(collection), before);
});
test("missing printing references render as unknown packs and absent card links stay absent", () => {
  const rows = cardPrintings(39, {
    packs,
    collection: [
      item(1, { pack_id: null }),
      item(2, { pack_id: 404 }),
      item(3, { card_id: null }),
    ],
  });
  assert.equal(rows.length, 2);
  assert.ok(rows.every((row) => !row.pack));
  assert.deepEqual(cardPrintings(99, { packs, collection: [item(1)] }), []);
});
test("collection filter groups combine and unowned counts react to absolute quantities", () => {
  const catalog = {
    cards: [],
    collection: [
      item(1),
      item(2),
      item(3, { pack_id: 2 }),
      item(4, { character_id: 8 }),
      item(5, { rare: "R" }),
      item(6, { item_type: "skin" }),
    ],
  };
  const filters = {
    ...emptyCollectionFilters,
    pack: "1",
    character: "2",
    rare: "N",
    type: "card",
    onlyZero: true,
  };
  assert.deepEqual(
    collectionRows(catalog, filters, "", { 1: 3 }, "ko").map((row) => row.id),
    [2],
  );
  assert.deepEqual(
    collectionRows(catalog, filters, "", { 1: 0, 2: 1 }, "ko").map(
      (row) => row.id,
    ),
    [1],
  );
});
test("collection search uses displayed translations and preserves code normalization for non-card items", () => {
  const card: Card = {
    id: 39,
    code: "ST1-001",
    character_id: 2,
    type: "공격",
    ultimate: false,
    frame: 5,
    damage: 400,
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
    localized: {
      ko: { name: "번개" },
      en: { name: "Lightning Strike" },
      ja: {},
    },
  };
  const catalog = {
    cards: [card],
    collection: [
      item(1),
      item(2, {
        card_id: null,
        item_type: "skin",
        code: "PR-12",
        name: "스킨",
      }),
    ],
  };
  assert.deepEqual(
    collectionRows(catalog, emptyCollectionFilters, "LIGHTNING", {}, "en").map(
      (row) => row.id,
    ),
    [1],
  );
  assert.deepEqual(
    collectionRows(catalog, emptyCollectionFilters, "ＰＲ１２", {}, "ja").map(
      (row) => row.id,
    ),
    [2],
  );
});
