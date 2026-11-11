import { requestCards } from "../catalog";
import { withPending } from "../net/optimistic";
import { PHASE_LABELS } from "../labels";
import type { BoardCard, GameEvent, PlayEnvelope, Side, VisibleCard, ZoneName } from "../protocol";
import { perspective, usePlay } from "../store";
import { addFloat, clearFx, shake, showBanner, showRibbon, useFx, type Tone } from "./fx";

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
  useFx.setState({ playing: false });
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
  odd: "홀수",
  even: "짝수",
  attack: "공격 기술",
  defense: "수비 기술",
  odd_attack: "홀수 공격",
  even_attack: "짝수 공격",
};

export const JUDGE_LABELS: Record<string, string> = {
  hit: "히트",
  counter: "카운터",
  countered: "카운터 당함",
  guard: "가드",
  guarded: "가드당함",
  dodge: "회피",
  opponent_dodge: "회피당함",
  clash: "상쇄",
  grabbed: "잡기",
  failed_defense: "방어 실패",
  none: "-",
};

const GOOD = new Set(["hit", "counter", "guard", "dodge", "clash"]);
const BAD = new Set(["countered", "guarded", "opponent_dodge", "failed_defense", "grabbed"]);

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

function applyEvent(base: PlayEnvelope, rawEvent: GameEvent, speed: number): { envelope: PlayEnvelope; ms: number } {
  const event = base.mode === "manual" ? adaptManual(rawEvent, base) : rawEvent;
  const envelope = clone(base, event.seq);
  const players = envelope.state.players;
  const { me } = perspective(envelope);
  const payload = event.payload as Record<string, unknown>;
  const actor = event.actor as Side;
  const dur = (ms: number) => ms / Math.max(speed, 1);

  switch (event.type) {
    case "phase_started": {
      const phase = String(payload.phase ?? "");
      const turnChanged = Number(payload.turn) !== Number(envelope.state.turn);
      envelope.state.phase = phase;
      if (payload.turn != null) envelope.state.turn = Number(payload.turn);
      showBanner(
        {
          kind: "phase",
          title: `${PHASE_LABELS[phase] ?? phase} 페이즈`,
          sub: turnChanged ? `턴 ${String(payload.turn)}` : undefined,
        },
        dur(turnChanged ? 1100 : 750),
      );
      return { envelope, ms: turnChanged ? 1000 : 650 };
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
      players[to].zones[toZone].push(moved);
      return { envelope, ms: 420 };
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
      const result = (payload.result ?? {}) as Record<Side, string>;
      const speeds = (payload.speed ?? null) as Record<Side, number> | null;
      const opp: Side = me === "p1" ? "p2" : "p1";
      const mine = result[me] ?? "";
      const tone: Tone = GOOD.has(mine) ? "good" : BAD.has(mine) ? "bad" : "neutral";
      showBanner(
        {
          kind: "judge",
          mine: JUDGE_LABELS[mine] ?? mine,
          theirs: JUDGE_LABELS[result[opp]] ?? result[opp] ?? "",
          tone: envelope.role === "viewer" ? "neutral" : tone,
          speeds: speeds ? [Number(speeds[me]), Number(speeds[opp])] : null,
        },
        dur(1400),
      );
      return { envelope, ms: 1300 };
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

    case "effect_resolved": {
      const text = String(payload.effect_label ?? "").replace(/\[\[[a-z_]+:([^\]]+)\]\]/g, "「$1」");
      if (!text) return { envelope, ms: 0 };
      showRibbon({ side: actor === "p1" || actor === "p2" ? actor : "system", card: String(payload.card_label ?? ""), text }, dur(1500));
      return { envelope, ms: 900 };
    }

    // 수동 모드: 신호(효과 발동·콤보 타임·캐치 타임)와 기록 메모
    case "signal":
      showBanner({ kind: "text", title: String(payload.label ?? payload.signal ?? ""), tone: actor === me ? "good" : "bad" }, dur(900));
      return { envelope, ms: 600 };

    case "log_note":
      showRibbon({ side: actor === "p1" || actor === "p2" ? actor : "system", card: actor === me ? "나" : "상대", text: String(payload.text ?? "") }, dur(1800));
      return { envelope, ms: 300 };

    case "combo_started":
      showBanner({ kind: "text", title: "콤보!", tone: actor === me ? "good" : "bad" }, dur(800));
      return { envelope, ms: 700 };

    case "catch_started":
      showBanner({ kind: "text", title: "캐치!", tone: actor === me ? "good" : "bad" }, dur(800));
      return { envelope, ms: 700 };

    case "card_broken":
      if (players[actor]) addFloat({ side: actor, text: "브레이크", tone: "info" });
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
          title: `${mine ? "내" : "상대"} 선언: ${guess}`,
          sub: correct ? "적중!" : "빗나감",
          card: { ...card, face_up: true, hidden: false },
          tone: envelope.role === "viewer" ? "neutral" : correct === mine ? "good" : "bad",
        },
        dur(2200),
      );
      return { envelope, ms: 2000 };
    }

    default:
      return { envelope, ms: 0 };
  }
}
