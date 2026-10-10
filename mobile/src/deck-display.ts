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
  return sections;
}

export function matchingDecks(
  decks: Deck[],
  query: string,
  character: string = "",
) {
  const needle = normalizeSearch(query);
  return decks.filter(
    (d) =>
      !d.deleted &&
      !!d.id &&
      (!character || String(d.character_id) === character) &&
      (!needle ||
        normalizeSearch(
          [d.name, d.keyword, d.tags, d.author?.username || ""].join(" "),
        ).includes(needle)),
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
