import { getJson, postJson, RequestError, uid } from "../net/http";
import { applyEnvelope, currentTarget } from "../net/live";
import type { PlayEnvelope, PrepActive, PrepCatalogCard, PrepCardRow, PrepRegistered } from "../protocol";

/**
 * 덱 준비 편집 모델. 서버(deck/validation.py validate)가 최종 판정하고,
 * 여기서는 버튼을 켜고 끌 수 있을 만큼만 같은 규칙으로 센다.
 */

export const isTrait = (card?: PrepCatalogCard) =>
  !!card && (card.type === "특성" || /PS/i.test(String(card.code ?? "")));

export const isUltimate = (card?: PrepCatalogCard) => !!card?.ultimate;

function addCount(map: Map<number, number>, id: number | null | undefined, count: number) {
  if (id == null) return;
  map.set(id, (map.get(id) ?? 0) + count);
}

/** 등록한 카드 전부(메인 + 교체 덱 + 등록 특성)의 장수 */
export function pool(registered: PrepRegistered): Map<number, number> {
  const result = new Map<number, number>();
  registered.cards.forEach((row) => addCount(result, row.card_id, row.count));
  registered.reserve_cards.forEach((row) => addCount(result, row.card_id, row.count));
  addCount(result, registered.trait_card_id, 1);
  return result;
}

function counts(rows: PrepCardRow[]): Map<number, number> {
  const result = new Map<number, number>();
  rows.forEach((row) => addCount(result, row.card_id, row.count));
  return result;
}

export interface SwapCounts {
  technique: number;
  trait: number;
  ultimate: number;
}

/** validate()의 swap_counts와 같은 계산 */
export function swapCounts(registered: PrepRegistered, active: PrepActive): SwapCounts {
  const catalog = registered.catalog;
  const technique = (map: Map<number, number>) =>
    new Map([...map].filter(([id]) => !isUltimate(catalog[id]) && !isTrait(catalog[id])));
  const ultimate = (map: Map<number, number>) =>
    JSON.stringify([...map].filter(([id]) => isUltimate(catalog[id])).sort((a, b) => a[0] - b[0]));
  const base = counts(registered.cards);
  const used = counts(active.cards);
  const oldTech = technique(base);
  const newTech = technique(used);
  let added = 0;
  let removed = 0;
  for (const id of new Set([...oldTech.keys(), ...newTech.keys()])) {
    const diff = (newTech.get(id) ?? 0) - (oldTech.get(id) ?? 0);
    if (diff > 0) added += diff;
    else removed -= diff;
  }
  return {
    technique: Math.max(added, removed),
    trait: Number(active.trait_card_id !== registered.trait_card_id),
    ultimate: Number(ultimate(base) !== ultimate(used)),
  };
}

/** 지금 덱에 넣을 수 있는 남은 장수(등록 장수 - 사용 중) */
export function available(registered: PrepRegistered, active: PrepActive): Map<number, number> {
  const total = pool(registered);
  const used = counts(active.cards);
  const result = new Map<number, number>();
  for (const [id, count] of total) {
    if (isTrait(registered.catalog[id])) continue;
    const left = count - (used.get(id) ?? 0);
    if (left > 0) result.set(id, left);
  }
  return result;
}

export function traitChoices(registered: PrepRegistered): number[] {
  return [...pool(registered).keys()].filter((id) => isTrait(registered.catalog[id]));
}

function clampRow(row: PrepCardRow): PrepCardRow {
  const hand = Math.min(row.hand ?? 0, row.count);
  const side = Math.min(row.side ?? 0, row.count - hand);
  return { ...row, hand, side };
}

export function removeCard(active: PrepActive, cardId: number): PrepActive {
  const cards = active.cards
    .map((row) => (row.card_id === cardId ? clampRow({ ...row, count: row.count - 1 }) : row))
    .filter((row) => row.count > 0);
  return { ...active, cards };
}

export function addCard(active: PrepActive, cardId: number): PrepActive {
  const exists = active.cards.some((row) => row.card_id === cardId);
  const cards = exists
    ? active.cards.map((row) => (row.card_id === cardId ? { ...row, count: row.count + 1 } : row))
    : [...active.cards, { card_id: cardId, count: 1, hand: 0, side: 0 }];
  return { ...active, cards };
}

export type Placement = "list" | "hand" | "side";

/** 한 장짜리 카드의 시작 위치 */
export function placementOf(row: PrepCardRow): Placement {
  if ((row.hand ?? 0) > 0) return "hand";
  if ((row.side ?? 0) > 0) return "side";
  return "list";
}

export function setPlacement(active: PrepActive, cardId: number, hand: number, side: number): PrepActive {
  return {
    ...active,
    cards: active.cards.map((row) => (row.card_id === cardId ? clampRow({ ...row, hand, side }) : row)),
  };
}

/** 준비 화면의 영역. ultimate는 얼티밋 카드의 자리, reserve는 교체 덱이다. */
export type PrepZone = Placement | "ultimate" | "reserve";

/** 카드 한 장을 from에서 to로 옮길 수 있는지(얼티밋은 얼티밋 자리와 교체 덱 사이만) */
export function canMove(card: PrepCatalogCard | undefined, from: PrepZone, to: PrepZone): boolean {
  if (from === to || !card) return false;
  if (isUltimate(card)) return (from === "ultimate" || from === "reserve") && (to === "ultimate" || to === "reserve");
  return from !== "ultimate" && to !== "ultimate";
}

/** 카드 한 장을 옮긴다. 교체 덱에서 오면 덱에 넣고, 교체 덱으로 가면 덱에서 뺀다. */
export function moveCopy(active: PrepActive, cardId: number, from: PrepZone, to: PrepZone): PrepActive {
  if (from === to) return active;
  let next = from === "reserve" ? addCard(active, cardId) : active;
  const row = next.cards.find((item) => item.card_id === cardId);
  if (!row) return active;
  let hand = row.hand ?? 0;
  let side = row.side ?? 0;
  if (from === "hand") hand -= 1;
  if (from === "side") side -= 1;
  if (to === "hand") hand += 1;
  if (to === "side") side += 1;
  next = setPlacement(next, cardId, Math.max(0, hand), Math.max(0, side));
  return to === "reserve" ? removeCard(next, cardId) : next;
}

export function totals(active: PrepActive, registered: PrepRegistered) {
  let hand = 0;
  let side = 0;
  let deck = 0;
  for (const row of active.cards) {
    if (isUltimate(registered.catalog[row.card_id])) continue;
    hand += row.hand ?? 0;
    side += row.side ?? 0;
    deck += row.count;
  }
  return { hand, side, deck };
}

// ---------------------------------------------------------------------------
// 서버 요청

export interface ValidationIssue {
  code: string;
  severity: "error" | "warning";
  message: string;
  card_ids: number[];
}

export interface ValidationReport {
  is_valid: boolean;
  issues: ValidationIssue[];
  swap_counts: SwapCounts;
}

function seatBody() {
  const target = currentTarget();
  if (!target?.seat) throw new Error("좌석 정보가 없습니다.");
  return { target, seat: target.seat, seat_token: target.token };
}

export async function checkPreparation(active: PrepActive): Promise<ValidationReport> {
  const { target, ...seat } = seatBody();
  const data = await postJson<{ report: ValidationReport }>(
    `/battlelog/simulator/${encodeURIComponent(target.view)}/preparation/check/`,
    { ...seat, active },
  );
  return data.report;
}

export type PreparationAction = "save" | "ready" | "cancel" | "next_game";

export async function sendPreparation(
  envelope: PlayEnvelope,
  action: PreparationAction,
  active?: PrepActive,
): Promise<void> {
  const { target, ...seat } = seatBody();
  const base = `/battlelog/simulator/${encodeURIComponent(target.view)}`;
  const post = (version: number | undefined) =>
    postJson<{ state: PlayEnvelope }>(`${base}/preparation/`, {
      ...seat,
      request_id: uid(),
      expected_version: version,
      preparation_action: action,
      ...(active ? { active } : {}),
    });
  let data: { state: PlayEnvelope };
  try {
    data = await post(envelope.preparation?.version);
  } catch (error) {
    // 상대가 같은 때 준비 상태를 바꾸면 버전이 어긋난다. 최신 상태로 한 번만 다시 보낸다.
    if (!(error instanceof RequestError) || !error.message.includes("준비 정보가 변경")) throw error;
    const query = new URLSearchParams({ seat: seat.seat, seat_token: seat.seat_token });
    const latest = await getJson<PlayEnvelope>(`${base}/state/?${query}`);
    applyEnvelope(latest);
    data = await post(latest.preparation?.version);
  }
  if (data.state) applyEnvelope(data.state);
}
