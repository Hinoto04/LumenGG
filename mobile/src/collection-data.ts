import type { Catalog, CollectionItem, Pack } from "./types";
import { localized, normalizeSearch } from "./core";

export interface CollectionFilters {
  pack: string;
  character: string;
  rare: string;
  type: string;
  onlyZero: boolean;
}
export const emptyCollectionFilters: CollectionFilters = {
  pack: "",
  character: "",
  rare: "",
  type: "",
  onlyZero: false,
};
export function collectionFilterCount(filters: CollectionFilters): number {
  return (
    Number(!!filters.pack) +
    Number(!!filters.character) +
    Number(!!filters.rare) +
    Number(!!filters.type) +
    Number(filters.onlyZero)
  );
}
export function collectionRows(
  catalog: Pick<Catalog, "collection" | "cards">,
  filters: CollectionFilters,
  query: string,
  amounts: Record<number, number>,
  language: string,
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
      (!filters.onlyZero || !amounts[item.id])
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
