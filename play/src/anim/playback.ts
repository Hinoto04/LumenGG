import { requestCards, useCatalog } from "../catalog";
import { withPending } from "../net/optimistic";
import { PHASE_LABELS, ZONE_LABELS } from "../labels";
import type { BoardCard, GameEvent, PlayEnvelope, Side, VisibleCard, ZoneName } from "../protocol";
import { perspective, usePlay } from "../store";
import { addFloat, clearFx, shake, showActivation, showBanner, showRibbon, useFx } from "./fx";
import { CLASH_MS, clashPlan, clearClash, playClash, settleClash } from "./clash";
import { soundForEvent } from "../sound/events";
import { plainMarkup } from "../markup";
import { t } from "../i18n";

/**
 * 이벤트 재생기.
 *
 * 서버는 행동 하나(와 이어지는 AI 행동)의 최종 상태만 보낸다. 대신 그 사이 이벤트에
 * 카드 이동·HP 변화·배틀 공개·판정이 다 들어 있으므로, 지금 보이는 상태에 이벤트를
 * 하나씩 적용한 중간 상태를 차례로 보여 주고 마지막에 서버 상태로 맞춘다.
 * 중간 상태는 화면용일 뿐이라 틀려도 마지막 맞춤에서 바로잡힌다.
 *
 * 기준: 보이는 envelope의 event_count = 이미 반영된 마지막 이벤트 seq.
 */

const WAIT_FOR_EVENTS_MS = 1500;
const FAST_FORWARD_BACKLOG = 40;
const SKIP_BACKLOG = 160;

let target: PlayEnvelope | null = null;
let queue: GameEvent[] = [];
let lastQueued = 0;
let running = false;
let generation = 0;

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/** 재생 세대가 바뀌면(초기화) 실행하지 않는 지연 호출 */
function later(ms: number, run: () => void) {
  const runGeneration = generation;
  setTimeout(() => {
    if (runGeneration === generation) run();
  }, ms);
}

function displayed(): PlayEnvelope | null {
  return usePlay.getState().envelope;
}

function show(envelope: PlayEnvelope) {
  usePlay.getState().setEnvelope(envelope);
}

/** 서버 상태를 올릴 때는 아직 확인되지 않은 내 행동 예측을 다시 얹는다(net/optimistic.ts). */
function showServer(envelope: PlayEnvelope) {
  show(withPending(envelope));
}

/** 연출 없이 바로 이 상태를 보여 준다(첫 접속, 시점 전환 등). */
export function resetPlayback(envelope: PlayEnvelope | null) {
  generation++;
  target = null;
  queue = [];
  lastQueued = envelope?.event_count ?? 0;
  running = false;
  clearFx();
  useFx.setState({ playing: false, behind: false });
  usePlay.getState().setEnvelope(envelope ? withPending(envelope) : envelope);
}

/** 서버가 보낸 새 상태. 앞선 이벤트를 다 재생한 뒤에 보여 준다. */
/** 덱 준비와 대전, 게임 번호가 바뀌면 이어서 재생할 것이 없다. */
function stageKey(envelope: PlayEnvelope): string {
  const preparation = envelope.preparation;
  return preparation ? `${preparation.game_number}:${preparation.status}` : "";
}

export function pushEnvelope(envelope: PlayEnvelope) {
  const current = displayed();
  if (!current || current.id !== envelope.id || current.role !== envelope.role || stageKey(current) !== stageKey(envelope)) {
    resetPlayback(envelope);
    return;
  }
  if (target && envelope.version < target.version) return;
  if (!target && envelope.version < current.version) return;
  target = envelope;
  useFx.setState({ behind: true });
  kick();
}

/** 새 이벤트. 이미 반영됐거나 대기열에 있는 것은 버린다. */
export function pushEvents(events: GameEvent[]) {
  const baseline = Math.max(lastQueued, displayed()?.event_count ?? 0);
  const fresh = events.filter((event) => event.seq > baseline).sort((a, b) => a.seq - b.seq);
  if (!fresh.length) return;
  queue.push(...fresh);
  lastQueued = fresh[fresh.length - 1].seq;
  requestCards(fresh.flatMap(eventCardIds));
  kick();
}

function kick() {
  if (running) return;
  running = true;
  void run(generation);
}

async function run(runGeneration: number) {
  let waitedForEvents = 0;
  const alive = () => runGeneration === generation;
  try {
    while (alive()) {
      const current = displayed();
      if (!current) break;
      const next = queue.shift();
      if (next) {
        waitedForEvents = 0;
        if (next.seq <= current.event_count) continue;
        const speed = useFx.getState().speed;
        if (queue.length > SKIP_BACKLOG) {
          if (target) {
            resetPlayback(target);
            return;
          }
          continue;
        }
        useFx.setState({ playing: true });
        const fast = queue.length > FAST_FORWARD_BACKLOG ? 4 : 1;
        const { envelope, ms } = applyEvent(current, next, speed * fast);
        show(envelope);
        if (ms > 0) await sleep(ms / (speed * fast));
        continue;
      }
      if (!target) break;
      // 상태가 이벤트보다 먼저 오면 이벤트를 잠시 기다린다.
      if (target.event_count > current.event_count && waitedForEvents < WAIT_FOR_EVENTS_MS) {
        await sleep(100);
        waitedForEvents += 100;
        continue;
      }
      const final = target;
      target = null;
      useFx.setState({ behind: false });
      showServer(final);
      lastQueued = Math.max(lastQueued, final.event_count);
      break;
    }
  } finally {
    if (alive()) {
      running = false;
      useFx.setState({ playing: false });
      // 기다리는 동안 새로 들어온 것이 있으면 이어서 처리한다.
      if (queue.length || target) kick();
    }
  }
}

// ---------------------------------------------------------------------------
// 이벤트 → 중간 상태 + 연출

const GUESS_LABELS: Record<string, string> = {
  odd: t("홀수"),
  even: t("짝수"),
  attack: t("공격 기술"),
  defense: t("수비 기술"),
  odd_attack: t("홀수 공격"),
  even_attack: t("짝수 공격"),
};

export const JUDGE_LABELS: Record<string, string> = {
  hit: t("히트"),
  counter: t("카운터"),
  countered: t("카운터 당함"),
  guard: t("가드"),
  guarded: t("가드당함"),
  dodge: t("회피"),
  opponent_dodge: t("회피당함"),
  clash: t("상쇄"),
  grabbed: t("잡기"),
  failed_defense: t("방어 실패"),
  none: "-",
};


function eventCardIds(event: GameEvent): (number | null | undefined)[] {
  const payload = event.payload as Record<string, unknown>;
  const ids = [payload.card_id as number | undefined];
  for (const side of ["p1", "p2"] as const) {
    const entry = payload[side] as { card_id?: number } | undefined;
    if (entry && typeof entry === "object") ids.push(entry.card_id);
  }
  return ids;
}

function clone(envelope: PlayEnvelope, seq: number): PlayEnvelope {
  const copy = structuredClone(envelope);
  // 재생 중에는 조작할 수 없다. 최종 상태가 오면 다시 생긴다.
  copy.legal_actions = [];
  copy.pending_decision = null;
  copy.event_count = seq;
  return copy;
}

function locate(envelope: PlayEnvelope, instanceId: unknown) {
  if (!instanceId) return null;
  for (const side of ["p1", "p2"] as const) {
    const zones = envelope.state.players[side].zones;
    for (const zone of Object.keys(zones) as ZoneName[]) {
      const index = zones[zone].findIndex((card) => !card.hidden && card.instance_id === instanceId);
      if (index >= 0) return { side, zone, index };
    }
  }
  return null;
}

/** 효과를 발동한 카드. 보드에 공개된 카드가 있으면 그것을, 없으면 카드 번호로 카탈로그에서 그린다. */
function activationCard(envelope: PlayEnvelope, payload: Record<string, unknown>, side: Side | "system"): VisibleCard | null {
  const found = locate(envelope, payload.card_instance_id);
  if (found) {
    const card = envelope.state.players[found.side].zones[found.zone][found.index] as VisibleCard;
    const { stat_changes: _ignored, ...rest } = card;
    return { ...rest, face_up: true };
  }
  if (payload.card_id == null) return null;
  requestCards([payload.card_id as number]);
  return {
    hidden: false,
    instance_id: String(payload.card_instance_id ?? `effect-${payload.card_id}`),
    kind: "card",
    owner: side === "system" ? "p1" : side,
    zone: "battle",
    face_up: true,
    card_id: Number(payload.card_id),
    code: (payload.card_code as string | undefined) ?? null,
  };
}

/** 보드 위 카드의 화면 위치(가운데·너비). 카드가 보이지 않으면 없음. */
function boardRect(instanceId: string) {
  const element = document.querySelector<HTMLElement>(`[data-instance-id="${CSS.escape(instanceId)}"]`);
  const rect = element?.getBoundingClientRect();
  if (!rect || !rect.width) return undefined;
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width };
}

function takeFrom(envelope: PlayEnvelope, side: Side, zone: ZoneName, preferHidden: boolean): BoardCard | null {
  const cards = envelope.state.players[side]?.zones[zone];
  if (!cards?.length) return null;
  let index = cards.length - 1;
  if (preferHidden) {
    const hidden = cards.map((card) => card.hidden).lastIndexOf(true);
    if (hidden >= 0) index = hidden;
  }
  return cards.splice(index, 1)[0];
}

function hiddenStub(side: Side, zone: ZoneName): BoardCard {
  return { hidden: true, kind: "card", owner: side, zone, face_up: false, name: "" };
}

function visibleStub(side: Side, zone: ZoneName, payload: Record<string, unknown>): VisibleCard {
  return {
    hidden: false,
    kind: "card",
    owner: side,
    zone,
    face_up: true,
    instance_id: String(payload.card_instance_id),
    card_id: (payload.card_id as number) ?? null,
    code: (payload.card_code as string) ?? null,
    name: String(payload.card_label ?? ""),
    type: (payload.card_type as string) ?? null,
  };
}

/** 이 역할에게 상대 손패 등은 뒷면이다. 이동한 카드를 도착 존에 맞게 보여 준다. */
function placeVisible(card: VisibleCard, to: Side, zone: ZoneName, me: Side, role: string): BoardCard {
  if (zone === "hand" && to !== me) return hiddenStub(to, zone);
  if (zone === "hand" && role === "viewer") return hiddenStub(to, zone);
  return { ...card, owner: to, zone };
}

/**
 * 수동 모드 이벤트(move_card, hp, set_phase ...)를 자동 엔진 이벤트 모양으로 바꿔
 * 같은 연출을 쓴다. 대상이 actor가 아니라 payload.target인 것에 주의.
 */
function adaptManual(event: GameEvent, base: PlayEnvelope): GameEvent {
  const payload = event.payload as Record<string, unknown>;
  const target = payload.target as Side;
  const delta = (before: unknown, after: unknown) => Number(after ?? 0) - Number(before ?? 0);
  switch (event.type) {
    case "move_card":
      return { ...event, type: "card_moved" };
    case "hp":
      return { ...event, type: "hp_changed", actor: target };
    case "fp":
    case "fp_reset":
      return { ...event, type: "fp_changed", actor: target, payload: { ...payload, amount: delta(payload.before, payload.after) } };
    case "set_phase":
    case "phase_advance":
      if (!payload.to_phase) return event;
      return { ...event, type: "phase_started", payload: { phase: payload.to_phase, turn: payload.to_turn ?? base.state.turn } };
    case "next_turn":
      return { ...event, type: "phase_started", payload: { phase: "lumen", turn: Number(base.state.turn) + 1 } };
    default:
      return event;
  }
}

// ---------------------------------------------------------------------------
// 효과로 바뀐 속도·대미지·판정(stat_changes)
//
// 배틀 중 수정자는 대개 그 배틀 동안만 있어(duration: battle) 서버가 보내는 최종 상태에는 남지 않는다.
// 그래서 재생 중에 modifier_added·speed_fixed·judgment_modified 이벤트로 중간 상태의 카드에 붙여
// 판정 전에 바뀐 값을 보여 준다. 카드가 다른 존으로 옮겨지면 떼고, 최종 상태가 오면 서버 값으로 맞춘다.

type StatChangeMap = NonNullable<VisibleCard["stat_changes"]>;

/** 카드의 인쇄값. 배틀 공개 때 만든 사본에는 수치가 없으므로 카탈로그로 채운다. */
function printedValue(card: VisibleCard, field: string): unknown {
  const own = (card as Record<string, unknown>)[field];
  if (own !== undefined && own !== null && own !== "") return own;
  const meta = card.card_id != null ? useCatalog.getState().cards[String(card.card_id)] : undefined;
  return meta ? (meta as Record<string, unknown>)[field] : undefined;
}

function updateStatChange(
  envelope: PlayEnvelope,
  instanceId: unknown,
  field: string,
  next: (change: StatChangeMap[string]) => Partial<Omit<StatChangeMap[string], "base">> | null,
  baseOverride?: unknown,
): boolean {
  const found = locate(envelope, instanceId);
  if (!found) return false;
  const cards = envelope.state.players[found.side].zones[found.zone];
  const card = cards[found.index] as VisibleCard;
  const changes: StatChangeMap = { ...(card.stat_changes ?? {}) };
  const previous = changes[field];
  const base = (previous ? previous.base : baseOverride !== undefined ? baseOverride : printedValue(card, field)) as
    | string
    | number
    | null
    | undefined;
  if (base === undefined) return false;
  const result = next(previous ?? { base, current: base });
  if (!result) return false;
  // 고정 여부는 이어 간다. FP 표시·설명은 이번에 돌려준 값만 쓴다.
  const value: StatChangeMap[string] = { base, current: result.current ?? null };
  if (result.fixed ?? previous?.fixed) value.fixed = true;
  if (result.fp_reference != null) value.fp_reference = result.fp_reference;
  if (result.note) value.note = result.note;
  if (String(value.current ?? "") === String(base ?? "") && !value.note) delete changes[field];
  else changes[field] = value;
  cards[found.index] = { ...card, stat_changes: changes };
  return true;
}

/** 수정자가 걸린 카드: where.instance_id가 있으면 그 카드, 없으면 대상 플레이어의 배틀 카드. */
function modifierTargets(envelope: PlayEnvelope, modifier: Record<string, unknown>): string[] {
  const where = (modifier.where ?? {}) as Record<string, unknown>;
  if (where.instance_id) return [String(where.instance_id)];
  if (Object.keys(where).length) return [];
  const side = (modifier.player ?? modifier.controller) as Side;
  const battle = envelope.state.players[side]?.zones.battle ?? [];
  return battle.filter((card) => !card.hidden).map((card) => String((card as VisibleCard).instance_id));
}

function applyStatEvent(envelope: PlayEnvelope, type: string, payload: Record<string, unknown>): boolean {
  if (type === "modifier_added") {
    const modifier = (payload.modifier ?? {}) as Record<string, unknown>;
    const stat = String(modifier.stat ?? "");
    if (stat !== "frame" && stat !== "damage") return false;
    const fixes = modifier.op === "fix_speed" || !!modifier.fixed;
    let changed = false;
    for (const id of modifierTargets(envelope, modifier)) {
      changed =
        updateStatChange(envelope, id, stat, (change) => {
          if (fixes) return modifier.value == null ? null : { current: Number(modifier.value), fixed: true };
          // 고정된 속도에는 증감이 더해지지 않는다(엔진 card_stat과 같다).
          if (change.fixed) return null;
          const value = Number(change.current) + Number(modifier.amount ?? 0);
          return { current: stat === "frame" ? Math.max(1, value) : value, note: change.note };
        }) || changed;
    }
    return changed;
  }
  if (type === "speed_fixed") {
    if (payload.speed == null) return false;
    return updateStatChange(envelope, payload.card_instance_id, "frame", () => ({ current: Number(payload.speed), fixed: true }));
  }
  if (type === "judgment_modified") {
    const field = String(payload.field ?? "");
    if (!field) return false;
    return updateStatChange(envelope, payload.card_instance_id, field, () => ({ current: (payload.after ?? null) as string | null }), payload.before ?? null);
  }
  if (type === "battle_judged") {
    // 모든 효과를 처리한 뒤의 판정 속도(FP 반영). FP로 달라졌으면 카드에 보여 준다.
    const cards = (payload.cards ?? {}) as Partial<Record<Side, { card_instance_id?: string }>>;
    const reference = (payload.reference_speed ?? {}) as Partial<Record<Side, number>>;
    const final = (payload.speed ?? {}) as Partial<Record<Side, number>>;
    let changed = false;
    for (const side of ["p1", "p2"] as const) {
      const id = cards[side]?.card_instance_id;
      const after = final[side];
      const before = reference[side];
      if (!id || after == null || before == null || Number(after) === Number(before)) continue;
      changed =
        updateStatChange(envelope, id, "frame", () => ({ current: Number(after), fp_reference: Number(before), note: "FP" })) ||
        changed;
    }
    return changed;
  }
  if (type === "combo_started") {
    // 콤보 타임: FP로 줄인 속도는 판정에만 쓰였으므로 FP 전 속도로 되돌린다.
    let changed = false;
    for (const side of ["p1", "p2"] as const) {
      for (const card of envelope.state.players[side]?.zones.battle ?? []) {
        if (card.hidden) continue;
        const reference = card.stat_changes?.frame?.fp_reference;
        if (reference == null) continue;
        changed = updateStatChange(envelope, card.instance_id, "frame", () => ({ current: reference })) || changed;
      }
    }
    return changed;
  }
  if (type === "combo_card_used") {
    // 콤보로 잇는 기술의 대미지(콤보 보정·효과 포함). 엔진이 계산한 값을 그대로 쓴다.
    if (payload.damage == null) return false;
    return updateStatChange(envelope, payload.card_instance_id, "damage", () => ({ current: Number(payload.damage) }));
  }
  return false;
}

function applyEvent(base: PlayEnvelope, rawEvent: GameEvent, speed: number): { envelope: PlayEnvelope; ms: number } {
  const event = base.mode === "manual" ? adaptManual(rawEvent, base) : rawEvent;
  const envelope = clone(base, event.seq);
  const players = envelope.state.players;
  const { me } = perspective(envelope);
  const payload = event.payload as Record<string, unknown>;
  const actor = event.actor as Side;
  const dur = (ms: number) => ms / Math.max(speed, 1);
  // 4배속으로 밀린 이벤트를 따라잡을 때는 소리를 내지 않는다.
  if (speed < 4) soundForEvent(event, base, me);

  switch (event.type) {
    case "phase_started": {
      // 판정 연출의 흑백 등은 그 배틀까지만 남긴다.
      clearClash();
      const phase = String(payload.phase ?? "");
      const turnChanged = Number(payload.turn) !== Number(envelope.state.turn);
      envelope.state.phase = phase;
      if (payload.turn != null) envelope.state.turn = Number(payload.turn);
      showBanner(
        {
          kind: "phase",
          title: t("{phase} 페이즈", { phase: PHASE_LABELS[phase] ?? phase }),
          sub: turnChanged ? t("턴 {turn}", { turn: String(payload.turn) }) : undefined,
        },
        // 페이즈·턴 전환 연출은 1초 안에 끝낸다(AI는 그사이·그 뒤에 생각해도 된다).
        dur(turnChanged ? 950 : 750),
      );
      return { envelope, ms: turnChanged ? 900 : 650 };
    }

    case "card_moved":
    case "private_event": {
      const isPrivate = event.type === "private_event";
      if (isPrivate && payload.event_type !== "card_moved") return { envelope, ms: 0 };
      const from = payload.from_player as Side;
      const to = payload.to_player as Side;
      const fromZone = payload.from_zone as ZoneName;
      const toZone = payload.to_zone as ZoneName;
      if (!players[from] || !players[to] || !players[from].zones[fromZone] || !players[to].zones[toZone]) {
        return { envelope, ms: 0 };
      }
      const found = isPrivate ? null : locate(envelope, payload.card_instance_id);
      // 겟: 상대가 가져간 카드를 효과 발동처럼 화면 가운데에 한 번 띄운다(리스트·얼티밋은 공개 영역).
      const opponentGet = !isPrivate && payload.reason === "get" && to !== me && toZone === "hand" && speed < 4;
      const getCard = opponentGet ? activationCard(envelope, payload, to) : null;
      if (getCard) {
        showActivation(
          {
            side: to,
            card: getCard,
            label: t("겟"),
            text: t("상대가 {zone}에서 패로 가져간 카드", { zone: ZONE_LABELS[fromZone] ?? t("리스트") }),
            from: found ? boardRect(String(payload.card_instance_id)) : undefined,
          },
          dur(1700),
        );
      }
      // 패로 들어가는 카드는 공개된다. 내 화면에서 보이지 않던 카드(사이드·뒷면 카드 등)였다면
      // 상대(관전자 포함)에게 잠시 보여 준다. 이미 보이던 카드는 기록으로 충분하다.
      if (!getCard && !isPrivate && payload.revealed && to !== me && !found) {
        showBanner(
          {
            kind: "card",
            title: t("상대가 {zone}에서 패로 가져간 카드", { zone: ZONE_LABELS[fromZone] ?? t("비공개 영역") }),
            card: { ...visibleStub(to, toZone, payload), face_up: true, hidden: false },
            tone: "neutral",
          },
          dur(1800),
        );
      }
      let moved: BoardCard | null;
      if (found) {
        moved = players[found.side].zones[found.zone].splice(found.index, 1)[0];
        if (!moved.hidden) moved = placeVisible(moved, to, toZone, me, envelope.role);
        else moved = hiddenStub(to, toZone);
      } else {
        const taken = takeFrom(envelope, from, fromZone, true);
        if (!taken && isPrivate) return { envelope, ms: 0 };
        moved =
          isPrivate || !payload.card_instance_id
            ? hiddenStub(to, toZone)
            : placeVisible(visibleStub(to, toZone, payload), to, toZone, me, envelope.role);
      }
      if (moved.hidden === false && toZone === "battle" && payload.reason === "ready") moved = { ...moved, face_up: false };
      // 존을 옮기면 걸려 있던 효과(배틀 동안 등)는 끝난다. 남아 있으면 최종 상태가 다시 붙인다.
      if (moved.hidden === false && fromZone !== toZone && moved.stat_changes) {
        const { stat_changes: _dropped, ...rest } = moved;
        moved = rest as VisibleCard;
      }
      // 거미·단검처럼 개수로만 보여 주는 토큰(Q-AUTO-012)은 카드를 날리지 않고 체력 아래 개수만 바꾼다.
      const counterKey = typeof payload.counter_token === "string" ? payload.counter_token : "";
      if (counterKey) {
        const bump = (side: Side, delta: number) => {
          const state = (players[side].passive_state ??= {});
          const entry = state[counterKey] ?? { label: t("{card} 토큰", { card: String(payload.card_label ?? t("토큰")).replace(/[「」]/g, "") }), derived: true };
          state[counterKey] = { ...entry, count: Math.max(0, Number(entry.count ?? 0) + delta) };
        };
        if (fromZone === "lumen") bump(from, -1);
        if (toZone === "lumen") {
          bump(to, 1);
          if (!moved.hidden) moved = { ...moved, state_counter_token: counterKey };
        }
        players[to].zones[toZone].push(moved);
        return { envelope, ms: 200 };
      }
      players[to].zones[toZone].push(moved);
      return { envelope, ms: getCard ? 1250 : 420 };
    }

    case "card_visibility_changed": {
      // 효과로 공개된 손패(요한 예지 등): 카드를 효과 발동처럼 한 번 띄워 강조하고, 손패에도 앞면으로 둔다.
      const owner = actor as Side;
      if (!payload.face_up || payload.was_face_up || !players[owner]) return { envelope, ms: 0 };
      const detail = { ...((payload.card as Record<string, unknown> | undefined) ?? {}) };
      const found = locate(envelope, payload.card_instance_id);
      if (found?.zone && found.zone !== "hand") return { envelope, ms: 0 };
      const hand = players[owner].zones.hand;
      if (found) {
        const card = hand[found.index];
        if (!card.hidden) hand[found.index] = { ...card, face_up: true };
      } else {
        // 상대 손패는 뒷면 자리만 있으므로 그중 하나를 공개된 카드로 바꾼다(최종 상태가 다시 맞춘다).
        const slot = hand.map((card) => card.hidden).lastIndexOf(true);
        const shown = { ...visibleStub(owner, "hand", payload), ...detail, face_up: true } as VisibleCard;
        if (slot >= 0) hand[slot] = shown;
      }
      const popup = speed < 4 ? activationCard(envelope, payload, owner) : null;
      if (!popup) return { envelope, ms: 0 };
      const handRect = owner === me ? undefined : document.querySelector(".opp-hand")?.getBoundingClientRect();
      showActivation(
        {
          side: owner,
          card: { ...popup, ...(found ? {} : detail), face_up: true } as VisibleCard,
          label: t("공개"),
          text: owner === me ? t("상대에게 공개된 내 손패") : t("공개된 상대 손패"),
          from: found
            ? boardRect(String(payload.card_instance_id))
            : handRect && { x: handRect.left + handRect.width / 2, y: handRect.top + handRect.height / 2, width: handRect.height * 0.7 },
        },
        dur(1700),
      );
      return { envelope, ms: 1250 };
    }

    case "battle_revealed": {
      for (const side of ["p1", "p2"] as const) {
        const entry = payload[side] as Record<string, unknown> | undefined;
        if (!entry) continue;
        const battle = players[side].zones.battle;
        const index = battle.findIndex((card) => !card.hidden && card.instance_id === entry.card_instance_id);
        if (index >= 0) {
          battle[index] = { ...(battle[index] as VisibleCard), face_up: true };
          continue;
        }
        const hidden = battle.findIndex((card) => card.hidden);
        const stub = visibleStub(side, "battle", entry);
        if (hidden >= 0) battle[hidden] = stub;
        else battle.push(stub);
      }
      return { envelope, ms: 900 };
    }

    case "battle_judged": {
      // 1) 판정 속도(FP 반영)를 카드에 보여 주고, 2) 잠시 뒤 두 카드가 돌진하는 연출을 한다.
      const showedSpeed = applyStatEvent(envelope, event.type, payload);
      const plan = clashPlan((payload.result ?? {}) as Partial<Record<Side, string>>);
      const pause = showedSpeed ? 700 : 150;
      if (plan) {
        const cards = (payload.cards ?? {}) as Partial<Record<Side, { card_instance_id?: string }>>;
        const ids = { p1: cards.p1?.card_instance_id, p2: cards.p2?.card_instance_id };
        // 4배속으로 밀린 이벤트를 따라잡을 때는 소리를 내지 않는다.
        const quiet = speed >= 4;
        later(dur(pause), () => playClash(plan, ids, speed, quiet));
        later(dur(pause + CLASH_MS), settleClash);
      }
      return { envelope, ms: pause + (plan ? CLASH_MS + 250 : 400) };
    }

    case "hp_changed": {
      if (!players[actor]) return { envelope, ms: 0 };
      const amount = Number(payload.amount ?? 0);
      players[actor].hp = Number(payload.after ?? players[actor].hp);
      addFloat({ side: actor, text: `${amount > 0 ? "+" : ""}${amount}`, tone: amount < 0 ? "damage" : "heal" });
      if (amount < 0) shake(actor);
      return { envelope, ms: 650 };
    }

    case "fp_changed": {
      if (!players[actor]) return { envelope, ms: 0 };
      const amount = Number(payload.amount ?? 0);
      players[actor].fp = Number(payload.after ?? players[actor].fp);
      addFloat({ side: actor, text: `FP ${amount > 0 ? "+" : ""}${amount}`, tone: "fp" });
      return { envelope, ms: 380 };
    }

    case "modifier_added":
    case "speed_fixed":
    case "judgment_modified":
      // 카드 위 표시가 튀어나오는 것을 볼 수 있게 잠시 머문다.
      return { envelope, ms: applyStatEvent(envelope, event.type, payload) ? 900 : 0 };

    case "effect_resolved": {
      const text = plainMarkup(payload.effect_label);
      const side = actor === "p1" || actor === "p2" ? actor : "system";
      const label = String(payload.card_label ?? "");
      // 발동한 카드를 잠깐 크게 띄운다. 따라잡는 중(4배속)이거나 카드를 알 수 없으면 효과문 띠만 보여 준다.
      const card = speed < 4 ? activationCard(envelope, payload, side) : null;
      if (card) {
        showActivation({ side, card, label, text, from: boardRect(card.instance_id) }, dur(1700));
        return { envelope, ms: 1250 };
      }
      if (!text) return { envelope, ms: 0 };
      showRibbon({ side, card: label, text }, dur(1500));
      return { envelope, ms: 900 };
    }

    // 수동 모드: 신호(효과 발동·콤보 타임·캐치 타임)와 기록 메모
    case "signal":
      showBanner({ kind: "text", title: String(payload.label ?? payload.signal ?? ""), tone: actor === me ? "good" : "bad" }, dur(900));
      return { envelope, ms: 600 };

    case "log_note":
      showRibbon({ side: actor === "p1" || actor === "p2" ? actor : "system", card: actor === me ? t("나") : t("상대"), text: String(payload.text ?? "") }, dur(1800));
      return { envelope, ms: 300 };

    case "combo_started":
      applyStatEvent(envelope, event.type, payload);
      showBanner({ kind: "text", title: t("콤보!"), tone: actor === me ? "good" : "bad" }, dur(800));
      return { envelope, ms: 700 };

    case "combo_card_used":
      return { envelope, ms: applyStatEvent(envelope, event.type, payload) ? 900 : 0 };

    case "catch_started":
      showBanner({ kind: "text", title: t("캐치!"), tone: actor === me ? "good" : "bad" }, dur(800));
      return { envelope, ms: 700 };

    case "card_broken":
      if (players[actor]) addFloat({ side: actor, text: t("브레이크"), tone: "info" });
      return { envelope, ms: 350 };

    // 요한 선언(디제스터 원·판도라 박스 등): 고른 상대 패를 양쪽이 잠시 함께 확인한다.
    case "card_guess_resolved": {
      const card = payload.card as VisibleCard | undefined;
      if (!card || card.hidden) return { envelope, ms: 0 };
      const guess = GUESS_LABELS[String(payload.guess ?? "")] ?? String(payload.guess ?? "");
      const correct = !!(payload.correct ?? payload.guess_correct);
      const mine = actor === me;
      showBanner(
        {
          kind: "card",
          title: mine ? t("내 선언: {guess}", { guess }) : t("상대 선언: {guess}", { guess }),
          sub: correct ? t("적중!") : t("빗나감"),
          card: { ...card, face_up: true, hidden: false },
          tone: envelope.role === "viewer" ? "neutral" : correct === mine ? "good" : "bad",
        },
        dur(2200),
      );
      return { envelope, ms: 1200 };
    }

    default:
      return { envelope, ms: 0 };
  }
}
