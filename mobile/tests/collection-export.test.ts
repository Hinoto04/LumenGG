import { test } from "node:test";
import assert from "node:assert/strict";
import { rareOrder, sortCollectionRows } from "../src/collection-data";
import {
  collectionExportFileName,
  csvField,
  defaultExportOptions,
  favoriteExportEntries,
  formatCollectionExport,
  type ExportEntry,
} from "../src/collection-export";
import type { Card, CollectionItem, Pack } from "../src/types";

const item = (
  id: number,
  fields: Partial<CollectionItem> = {},
): CollectionItem => ({
  id,
  card_id: 1,
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
const card = (id: number, frame: number | null, ko: string, en = "") =>
  ({
    id,
    frame,
    localized: { ko: { name: ko }, en: { name: en }, ja: {} },
  }) as unknown as Card;
const pack = (id: number, released: string | null) =>
  ({
    id,
    code: "P" + id,
    released,
    localized: { ko: {}, en: {}, ja: {} },
  }) as Pack;

const catalog = {
  cards: [
    card(1, 5, "번개", "Lightning"),
    card(2, 3, "가드"),
    card(3, 5, "가속"),
  ],
  packs: [pack(1, "2024-02-20"), pack(2, "2023-01-01"), pack(3, null)],
  collection: [
    item(1, { card_id: 1, name: "번개", rare: "SR" }),
    item(2, { card_id: 1, name: "번개", rare: "N" }),
    item(3, { card_id: 2, name: "가드", code: "ST1-002" }),
    item(4, { card_id: 3, name: "가속", code: "ST1-003" }),
    item(5, { card_id: null, name: "스킨", item_type: "skin", code: "PR-1" }),
    item(6, { card_id: 1, name: "번개", rare: "N", pack_id: 2, code: "PR-2" }),
  ],
};

test("rarity order follows the web custom_order and unknown rarities go last", () => {
  assert.deepEqual(
    ["SP", "X", "N", "AEX", "SR"].sort((a, b) => rareOrder(a) - rareOrder(b)),
    ["N", "SR", "AEX", "SP", "X"],
  );
});

test("speed sort matches the web order: frame, name, pack release, rarity", () => {
  const ids = sortCollectionRows(catalog.collection, catalog, "speed").map(
    (row) => row.id,
  );
  // 속도가 없는 스킨(null)이 먼저, 속도 3 → 속도 5. 속도 5끼리는 이름(가속 < 번개),
  // 같은 번개는 먼저 발매된 팩(PR) → 레어도(N < SR).
  assert.deepEqual(ids, [5, 3, 4, 6, 2, 1]);
});

test("name and code sorts and the default keep their own order without mutating", () => {
  const before = catalog.collection.map((row) => row.id);
  assert.deepEqual(
    sortCollectionRows(catalog.collection, catalog, "name").map((r) => r.id),
    [3, 4, 6, 2, 1, 5],
  );
  assert.deepEqual(
    sortCollectionRows(catalog.collection, catalog, "code").map((r) => r.id),
    [5, 6, 2, 1, 3, 4],
  );
  assert.equal(
    sortCollectionRows(catalog.collection, catalog, ""),
    catalog.collection,
  );
  assert.deepEqual(
    catalog.collection.map((row) => row.id),
    before,
  );
});

test("favorite entries keep hearted prints only, sorted by speed with localized names", () => {
  const categories = { 1: 2, 3: 1, 5: 4, 2: 0 };
  const amounts = { 1: 3, 5: 1 };
  assert.deepEqual(favoriteExportEntries(catalog, categories, amounts, "en"), [
    { name: "스킨", code: "PR-1", rare: "N", amount: 1 },
    { name: "가드", code: "ST1-002", rare: "N", amount: 0 },
    { name: "Lightning", code: "ST1-001", rare: "SR", amount: 3 },
  ]);
  assert.deepEqual(
    favoriteExportEntries(catalog, categories, amounts, "ko", "2").map(
      (e) => e.name,
    ),
    ["번개"],
  );
});

const entries: ExportEntry[] = [
  { name: "번개", code: "ST1-001", rare: "SR", amount: 2 },
  { name: 'Say "Hi", ok', code: "PR-1", rare: "", amount: 0 },
];

test("csv starts with a UTF-8 BOM, has a header and escapes quotes and commas", () => {
  const csv = formatCollectionExport(entries, {
    ...defaultExportOptions,
    format: "csv",
  });
  assert.equal(
    csv,
    '\uFEFF카드명,코드,레어도,갯수\r\n번개,ST1-001,SR,2\r\n"Say ""Hi"", ok",PR-1,,0\r\n',
  );
  assert.equal(csvField("a\nb"), '"a\nb"');
  assert.equal(csvField("plain"), "plain");
});

test("turned off columns disappear but the card name always stays", () => {
  const csv = formatCollectionExport(entries, {
    format: "csv",
    code: false,
    rare: true,
    amount: false,
  });
  assert.equal(csv, '\uFEFF카드명,레어도\r\n번개,SR\r\n"Say ""Hi"", ok",\r\n');
  const txt = formatCollectionExport(entries, {
    format: "txt",
    code: false,
    rare: false,
    amount: false,
  });
  assert.equal(txt, '번개\nSay "Hi", ok\n');
});

test("txt writes one readable line per entry", () => {
  assert.equal(
    formatCollectionExport(entries, defaultExportOptions),
    '번개 [ST1-001] (SR) x2\nSay "Hi", ok [PR-1] x0\n',
  );
  assert.equal(formatCollectionExport([], defaultExportOptions), "");
});

test("file names carry the date and format", () => {
  assert.equal(
    collectionExportFileName("csv", new Date(2026, 10, 9)),
    "lumen-favorites-20261109.csv",
  );
});
