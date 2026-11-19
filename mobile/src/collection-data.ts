import type { Catalog, CollectionItem, Pack } from "./types";
import { localized, normalizeSearch } from "./core";

/** 카드마다 붙이는 하트 분류. 0은 분류 없음, 1~5는 웹과 같은 하트 색이다. */
export const COLLECTION_CATEGORIES = [1, 2, 3, 4, 5] as const;
export const categoryColors: Record<number, string> = {
  1: "#ff5d73",
  2: "#ff9f43",
  3: "#f5c518",
  4: "#4cc38a",
  5: "#5aa9ff",
};
export function normalizeCategory(value: unknown): number {
  const n = Number(value);
  return Number.isInteger(n) && n >= 0 && n <= 5 ? n : 0;
}

export interface CollectionFilters {
  pack: string;
  character: string;
  rare: string;
  type: string;
  onlyZero: boolean;
  /** "" 전체, "any" 분류된 카드, "1"~"5" 해당 하트. */
  category: string;
  /** 정렬 기준. 필터 개수에는 세지 않는다. */
  sort: CollectionSort;
}
export const emptyCollectionFilters: CollectionFilters = {
  pack: "",
  character: "",
  rare: "",
  type: "",
  onlyZero: false,
  category: "",
  sort: "",
};
export function collectionFilterCount(filters: CollectionFilters): number {
  return (
    Number(!!filters.pack) +
    Number(!!filters.character) +
    Number(!!filters.rare) +
    Number(!!filters.type) +
    Number(filters.onlyZero) +
    Number(!!filters.category)
  );
}
export function collectionRows(
  catalog: Pick<Catalog, "collection" | "cards">,
  filters: CollectionFilters,
  query: string,
  amounts: Record<number, number>,
  language: string,
  categories: Record<number, number> = {},
): CollectionItem[] {
  const needle = normalizeSearch(query);
  const cards = new Map(catalog.cards.map((card) => [card.id, card]));
  return catalog.collection.filter((item) => {
    const card = item.card_id === null ? undefined : cards.get(item.card_id);
    return (
      (!needle ||
        normalizeSearch(
          item.name + item.code + (card ? localized(card, language) : ""),
        ).includes(needle)) &&
      (!filters.pack || String(item.pack_id) === filters.pack) &&
      (!filters.character || String(item.character_id) === filters.character) &&
      (!filters.rare || item.rare === filters.rare) &&
      (!filters.type || item.item_type === filters.type) &&
      (!filters.onlyZero || !amounts[item.id]) &&
      (!filters.category ||
        (filters.category === "any"
          ? !!categories[item.id]
          : String(categories[item.id] || 0) === filters.category))
    );
  });
}
export interface CardPrinting {
  key: string;
  code: string;
  pack?: Pack;
  items: CollectionItem[];
  rarities: string[];
}
export function cardPrintings(
  cardId: number,
  catalog: Pick<Catalog, "collection" | "packs">,
): CardPrinting[] {
  const packs = new Map(catalog.packs.map((pack) => [pack.id, pack]));
  const groups = new Map<string, CardPrinting>();
  for (const item of catalog.collection) {
    if (item.card_id !== cardId) continue;
    const key = JSON.stringify([item.pack_id, item.code, item.item_type]);
    let group = groups.get(key);
    if (!group) {
      group = {
        key,
        code: item.code,
        pack: item.pack_id === null ? undefined : packs.get(item.pack_id),
        items: [],
        rarities: [],
      };
      groups.set(key, group);
    }
    group.items.push(item);
    if (item.rare && !group.rarities.includes(item.rare))
      group.rarities.push(item.rare);
  }
  const order = new Intl.Collator("ko", { numeric: true });
  return [...groups.values()].sort(
    (a, b) =>
      (a.pack?.released || "9999").localeCompare(b.pack?.released || "9999") ||
      order.compare(a.code, b.code) ||
      a.items[0]!.id - b.items[0]!.id,
  );
}

/** "" 카탈로그(등록) 순, 나머지는 웹 컬렉션(`collection/views/views.py`)의 정렬과 같다. */
export type CollectionSort = "" | "speed" | "name" | "code";
export const COLLECTION_SORTS: CollectionSort[] = ["", "speed", "name", "code"];

/** 웹의 custom_order와 같은 레어도 순서. 목록에 없는 레어도는 맨 뒤다. */
const RARE_ORDER = ["N", "SR", "EXR", "AN", "AEX", "SAR", "SP"];
export function rareOrder(rare: string): number {
  const index = RARE_ORDER.indexOf(rare);
  return index < 0 ? RARE_ORDER.length : index;
}

/** 값이 없으면(null) 앞에 둔다. 웹이 쓰는 MySQL·SQLite 오름차순 정렬과 같다. */
function compareNullable<T>(
  a: T | null | undefined,
  b: T | null | undefined,
  compare: (a: T, b: T) => number,
): number {
  const aMissing = a === null || a === undefined;
  const bMissing = b === null || b === undefined;
  if (aMissing && bMissing) return 0;
  if (aMissing) return -1;
  if (bMissing) return 1;
  return compare(a as T, b as T);
}
const textOrder = new Intl.Collator("ko");

/**
 * 컬렉션 항목을 정렬한 새 배열을 돌려준다.
 * - speed: 카드 속도(frame) → 이름 → 팩 발매일 → 레어도. 카드가 없는 스킨·토큰은 속도가 없어 앞에 온다.
 * - name: 이름 → 팩 발매일 → 코드 → 레어도
 * - code: 코드 → 팩 발매일 → 레어도
 * 모든 기준이 같으면 등록(id) 순으로 둔다.
 */
export function sortCollectionRows(
  rows: CollectionItem[],
  catalog: Pick<Catalog, "cards" | "packs">,
  sort: CollectionSort,
): CollectionItem[] {
  if (!sort) return rows;
  const frames = new Map(catalog.cards.map((card) => [card.id, card.frame]));
  const released = new Map(
    catalog.packs.map((pack) => [pack.id, pack.released]),
  );
  const frameOf = (item: CollectionItem) =>
    item.card_id === null ? null : frames.get(item.card_id);
  const releasedOf = (item: CollectionItem) =>
    item.pack_id === null ? null : released.get(item.pack_id);
  const byFrame = (a: CollectionItem, b: CollectionItem) =>
    compareNullable(frameOf(a), frameOf(b), (x, y) => x - y);
  const byName = (a: CollectionItem, b: CollectionItem) =>
    textOrder.compare(a.name, b.name);
  const byCode = (a: CollectionItem, b: CollectionItem) =>
    textOrder.compare(a.code, b.code);
  const byReleased = (a: CollectionItem, b: CollectionItem) =>
    compareNullable(releasedOf(a), releasedOf(b), (x, y) => x.localeCompare(y));
  const byRare = (a: CollectionItem, b: CollectionItem) =>
    rareOrder(a.rare) - rareOrder(b.rare);
  const keys = {
    speed: [byFrame, byName, byReleased, byRare],
    name: [byName, byReleased, byCode, byRare],
    code: [byCode, byReleased, byRare],
  }[sort];
  return [...rows].sort((a, b) => {
    for (const compare of keys) {
      const result = compare(a, b);
      if (result) return result;
    }
    return a.id - b.id;
  });
}
