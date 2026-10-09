import { localized } from "./core";
import type { Card, Catalog, Language } from "./types";

export const CARD_SORT_OPTIONS = [
  { key: "code_asc", label: "번호 오름차순" },
  { key: "code_desc", label: "번호 내림차순" },
  { key: "name_asc", label: "이름 오름차순" },
  { key: "name_desc", label: "이름 내림차순" },
  { key: "frame_asc", label: "속도 오름차순" },
  { key: "frame_desc", label: "속도 내림차순" },
  { key: "damage_asc", label: "대미지 오름차순" },
  { key: "damage_desc", label: "대미지 내림차순" },
  { key: "hit_asc", label: "히트 오름차순" },
  { key: "hit_desc", label: "히트 내림차순" },
  { key: "counter_asc", label: "카운터 오름차순" },
  { key: "counter_desc", label: "카운터 내림차순" },
  { key: "guard_asc", label: "가드 오름차순" },
  { key: "guard_desc", label: "가드 내림차순" },
  { key: "release_desc", label: "출시일 최신순" },
  { key: "release_asc", label: "출시일 오래된순" },
] as const;
export type CardSort = (typeof CARD_SORT_OPTIONS)[number]["key"];
export type CardDisplay = "grid" | "detail";
export function isCardSort(value: unknown): value is CardSort {
  return CARD_SORT_OPTIONS.some((option) => option.key === value);
}
function numeric(value: unknown): number | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  if (typeof value !== "string") return null;
  const normalized = value.trim().replace(/[−–]/g, "-");
  return /^[+-]?\d+(?:\.\d+)?$/.test(normalized) ? Number(normalized) : null;
}
export function sortCards(
  cards: Card[],
  sort: CardSort,
  language: Language,
  catalog: Pick<Catalog, "packs" | "collection">,
): Card[] {
  const collator = new Intl.Collator(language, {
    numeric: true,
    sensitivity: "base",
  });
  const releases = new Map<number, number>();
  if (sort.startsWith("release")) {
    const dates = new Map(
      catalog.packs.map((pack) => [
        pack.id,
        pack.released ? Date.parse(pack.released) : NaN,
      ]),
    );
    for (const item of catalog.collection) {
      const date = item.pack_id === null ? NaN : dates.get(item.pack_id);
      if (item.card_id !== null && date !== undefined && Number.isFinite(date))
        releases.set(
          item.card_id,
          Math.min(releases.get(item.card_id) ?? Infinity, date),
        );
    }
  }
  const [field, direction] = sort.split("_");
  const sign = direction === "desc" ? -1 : 1;
  const tie = (a: Card, b: Card) =>
    collator.compare(a.code || "", b.code || "") || a.id - b.id;
  return [...cards].sort((a, b) => {
    if (field === "name")
      return (
        sign *
          collator.compare(localized(a, language), localized(b, language)) ||
        tie(a, b)
      );
    if (field === "code") {
      if (!a.code || !b.code)
        return !a.code && !b.code ? a.id - b.id : !a.code ? 1 : -1;
      return sign * collator.compare(a.code, b.code) || a.id - b.id;
    }
    const left =
      field === "release"
        ? (releases.get(a.id) ?? null)
        : numeric(a[field as "frame" | "damage" | "hit" | "counter" | "guard"]);
    const right =
      field === "release"
        ? (releases.get(b.id) ?? null)
        : numeric(b[field as "frame" | "damage" | "hit" | "counter" | "guard"]);
    if (left === null || right === null)
      return left === null && right === null
        ? tie(a, b)
        : left === null
          ? 1
          : -1;
    return sign * (left - right) || tie(a, b);
  });
}
