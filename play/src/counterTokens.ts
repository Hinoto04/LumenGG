import { isStateCounterToken, type BoardCard } from "./protocol";

export interface ZoneEntry {
  card: BoardCard;
  /** 존 안의 실제 위치. 카드 참조(owner/zone/index)에 그대로 쓴다. */
  index: number;
  /** 같은 토큰을 한 장으로 묶어 보일 때 묶인 장 수(묶지 않으면 없음) */
  stacked?: number;
}

/**
 * 거미처럼 무한히 쌓이는 토큰은 플레이어 상태에 개수로 보이므로(Q-AUTO-012),
 * 더미를 펼친 화면에서는 같은 토큰을 한 장(×장 수)으로 묶는다.
 * 고르거나 쓸 수 있는 토큰이 있으면(`active`) 그 종류는 한 장씩 펼쳐서 고를 수 있게 둔다.
 */
export function zoneEntries(cards: BoardCard[], active: (card: BoardCard, index: number) => boolean): ZoneEntry[] {
  const groups = new Map<string, ZoneEntry[]>();
  const entries: ZoneEntry[] = [];
  cards.forEach((card, index) => {
    if (!isStateCounterToken(card)) {
      entries.push({ card, index });
      return;
    }
    const key = String((card as { state_counter_token?: string }).state_counter_token);
    groups.set(key, [...(groups.get(key) ?? []), { card, index }]);
  });
  for (const group of groups.values()) {
    if (group.some(({ card, index }) => active(card, index))) entries.push(...group);
    else entries.push({ ...group[0], stacked: group.length });
  }
  return entries;
}
