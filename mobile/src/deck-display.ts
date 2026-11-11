import type { Card, Deck, Catalog } from "./types";
import { normalizeSearch } from "./core";

export const deckColumns = { small: 9, medium: 6, large: 3 } as const;
export type DeckSize = keyof typeof deckColumns;
export interface DeckTile {
  card_id: number;
  card?: Card;
  key: string;
}

export function deckSections(deck: Deck, catalog: Catalog | null) {
  const cards = new Map(catalog?.cards.map((c) => [c.id, c]) || []);
  const sections = ["리스트", "손패", "사이드"].map((title) => ({
    title,
    tiles: [] as DeckTile[],
  }));
  const entries = [...deck.cards].sort((a, b) => {
    const ca = cards.get(a.card_id),
      cb = cards.get(b.card_id);
    return (
      (cb?.type || "").localeCompare(ca?.type || "", "ko") ||
      (ca?.frame ?? Infinity) - (cb?.frame ?? Infinity) ||
      a.card_id - b.card_id
    );
  });
  for (const entry of entries) {
    const card = cards.get(entry.card_id);
    const counts = card?.ultimate
      ? [entry.count, 0, 0]
      : [
          Math.max(0, entry.count - entry.hand - entry.side),
          entry.hand,
          entry.side,
        ];
    counts.forEach((count, zone) => {
      for (let copy = 0; copy < count; copy++)
        sections[zone]!.tiles.push({
          card_id: entry.card_id,
          card,
          key: `${entry.card_id}:${copy}`,
        });
    });
  }
  if (deck.trait_card_id)
    sections.push({
      title: "특성",
      tiles: [
        {
          card_id: deck.trait_card_id,
          card: cards.get(deck.trait_card_id),
          key: `trait:${deck.trait_card_id}`,
        },
      ],
    });
  if (deck.reserve_cards?.length)
    sections.push({
      title: "교체 덱",
      tiles: deck.reserve_cards.flatMap((e) =>
        Array.from({ length: e.count }, (_, i) => ({
          card_id: e.card_id,
          card: cards.get(e.card_id),
          key: `reserve:${e.card_id}:${i}`,
        })),
      ),
    });
  return sections;
}

export function matchingDecks(
  decks: Deck[],
  query: string,
  character: string = "",
  trait: string = "",
  regulation: string = "",
) {
  const needle = normalizeSearch(query);
  return decks.filter(
    (d) =>
      !d.deleted &&
      (!!d.id || d.schema_version === 2) &&
      (!character || String(d.character_id) === character) &&
      (!trait || String(d.trait_card_id) === trait) &&
      (!regulation || String(d.regulation_version_id) === regulation) &&
      (!needle ||
        normalizeSearch(
          [d.name, d.keyword, d.tags, d.author?.username || ""].join(" "),
        ).includes(needle)),
  );
}

/** 북마크 필터가 켜져 있으면 북마크한 덱 ID만 남긴다. */
export function bookmarkedDecks<T extends { id?: number }>(
  decks: T[],
  bookmarks: readonly number[],
  only: boolean,
): T[] {
  if (!only) return decks;
  const ids = new Set(bookmarks);
  return decks.filter((d) => d.id !== undefined && ids.has(d.id));
}

/** 서버가 알려 준 북마크 상태(bookmarked)를 로컬 북마크 목록에 반영한다. 바뀌지 않으면 null. */
export function mergeBookmarks(
  current: readonly number[],
  decks: readonly { id?: number; bookmarked?: boolean }[],
): number[] | null {
  const next = new Set(current);
  for (const deck of decks) {
    if (deck.id === undefined || typeof deck.bookmarked !== "boolean") continue;
    if (deck.bookmarked) next.add(deck.id);
    else next.delete(deck.id);
  }
  const list = [...next].sort((a, b) => a - b);
  const same =
    list.length === current.length &&
    [...current].sort((a, b) => a - b).every((id, n) => id === list[n]);
  return same ? null : list;
}

/** 공개 덱 목록 요청 경로. 북마크 필터는 로그인했을 때만 보낸다. */
export function publicDeckPath(params: {
  query: string;
  character: string;
  trait?: string;
  regulation?: string;
  sort?: string;
  bookmarked?: boolean;
  page?: number;
}) {
  return (
    `/decks?scope=public&q=${encodeURIComponent(params.query.trim())}` +
    `&character_id=${params.character}&trait_card_id=${params.trait || ""}` +
    `&regulation_version_id=${params.regulation || ""}` +
    (params.sort ? `&sort=${params.sort}` : "") +
    (params.bookmarked ? "&bookmarked=1" : "") +
    (params.page ? `&page=${params.page}` : "")
  );
}

// Web descriptions contain editor HTML. Display readable text without running HTML.
export function deckDescription(value: string) {
  return value
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<br\s*\/?\s*>|<\/(?:p|div|li|h[1-6])>/gi, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(
      /&(#x[\da-f]+|#\d+|nbsp|amp|lt|gt|quot|apos);/gi,
      (match, key: string) => {
        const names: Record<string, string> = {
          nbsp: " ",
          amp: "&",
          lt: "<",
          gt: ">",
          quot: '"',
          apos: "'",
        };
        if (key[0] !== "#") return names[key.toLowerCase()] || match;
        const code =
          key[1]?.toLowerCase() === "x"
            ? parseInt(key.slice(2), 16)
            : Number(key.slice(1));
        return code >= 0 && code <= 0x10ffff
          ? String.fromCodePoint(code)
          : match;
      },
    )
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

/** 웹 덱 목록과 같은 정렬 키(서버 /api/mobile/v1/decks?sort=). */
export type DeckSort = "recent" | "version" | "like";
export const DECK_SORTS: { key: DeckSort; label: string }[] = [
  { key: "recent", label: "최신순" },
  { key: "version", label: "버전순" },
  { key: "like", label: "좋아요순" },
];
export function isDeckSort(value: unknown): value is DeckSort {
  return value === "recent" || value === "version" || value === "like";
}
/**
 * 내 덱(기기에 저장된 목록)의 정렬. 입력은 이미 최신순이다.
 * 버전순은 웹과 같이 버전 문자열 내림차순이고 같은 버전은 최신순을 유지한다.
 * 좋아요 수는 기기에 없으므로 좋아요순은 최신순으로 둔다.
 */
export function sortMyDecks(decks: Deck[], sort: DeckSort): Deck[] {
  if (sort !== "version") return decks;
  return decks
    .map((deck, index) => ({ deck, index }))
    .sort(
      (a, b) =>
        (b.deck.version || "").localeCompare(a.deck.version || "") ||
        a.index - b.index,
    )
    .map((row) => row.deck);
}
