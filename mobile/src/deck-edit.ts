import type { Card, DeckEntry } from "./types";

/** 덱 작성 화면의 시작 배치 영역. 리스트 = 매수 − 손패 − 사이드. */
export type DeckZone = "list" | "hand" | "side";
export const DECK_ZONES: DeckZone[] = ["list", "hand", "side"];

/** 특수 기술(얼티밋 제외)은 항상 사이드에 둔다. */
export const isSpecial = (card: Pick<Card, "type" | "ultimate">) =>
  !card.ultimate && card.type.includes("특수");

/** 영역을 옮길 수 있는 카드인지. 얼티밋은 리스트, 특수 기술은 사이드에 고정된다. */
export const isMovable = (card: Pick<Card, "type" | "ultimate">) =>
  !card.ultimate && !isSpecial(card);

export function zoneCount(entry: DeckEntry, zone: DeckZone) {
  if (zone === "hand") return entry.hand;
  if (zone === "side") return entry.side;
  return Math.max(0, entry.count - entry.hand - entry.side);
}

/** 카드 1장을 덱에 넣는다. 특수 기술은 사이드, 나머지는 리스트로 들어간다. */
export function addCopy(entries: DeckEntry[], card: Card): DeckEntry[] {
  const special = isSpecial(card);
  const found = entries.some((e) => e.card_id === card.id);
  if (!found)
    return [
      ...entries,
      { card_id: card.id, count: 1, hand: 0, side: special ? 1 : 0 },
    ];
  return entries.map((e) =>
    e.card_id === card.id
      ? { ...e, count: e.count + 1, side: e.side + (special ? 1 : 0) }
      : e,
  );
}

/** 지정한 영역에서 카드 1장을 뺀다. 매수가 0이 되면 항목을 지운다. */
export function removeCopy(
  entries: DeckEntry[],
  cardId: number,
  zone: DeckZone,
): DeckEntry[] {
  return entries
    .map((e) => {
      if (e.card_id !== cardId || zoneCount(e, zone) <= 0) return e;
      return {
        ...e,
        count: e.count - 1,
        hand: e.hand - (zone === "hand" ? 1 : 0),
        side: e.side - (zone === "side" ? 1 : 0),
      };
    })
    .filter((e) => e.count > 0);
}

/** 카드 1장을 다른 영역으로 옮긴다. 옮길 수 없으면 그대로 돌려준다. */
export function moveCopy(
  entries: DeckEntry[],
  card: Pick<Card, "id" | "type" | "ultimate">,
  from: DeckZone,
  to: DeckZone,
): DeckEntry[] {
  if (from === to || !isMovable(card)) return entries;
  return entries.map((e) => {
    if (e.card_id !== card.id || zoneCount(e, from) <= 0) return e;
    const next = { ...e };
    if (from === "hand") next.hand--;
    if (from === "side") next.side--;
    if (to === "hand") next.hand++;
    if (to === "side") next.side++;
    return next;
  });
}
