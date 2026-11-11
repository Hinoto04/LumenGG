import { JUDGE_LABELS } from "./anim/playback";
import { eventText } from "./eventText";
import { PHASE_LABELS, ZONE_LABELS } from "./labels";
import { labelFor } from "./passives";
import type { GameEvent, PlayEnvelope, Side, VisibleCard, ZoneName } from "./protocol";

/**
 * 기록 창의 한 항목. 텍스트만 늘어놓지 않고, 관련 카드(그림), 누구의 일인지(배경색),
 * 수치 변화(+초록 / -빨강)를 따로 담는다.
 */
export interface LogCard {
  card_id?: number | null;
  code?: string | null;
  name?: string;
  owner?: Side;
}

export interface LogEntry {
  seq: number;
  /** 배경색: 나(초록) · 상대(빨강) · 시스템(무색) */
  side: "me" | "opp" | "system";
  /** 페이즈 시작 등 구분선으로 보여 줄 항목 */
  divider?: boolean;
  title: string;
  detail?: string;
  cards: LogCard[];
  /** 수치 변화(HP, FP, 데미지) */
  deltas: { label: string; amount: number }[];
}

/** 화면에 굳이 보여 주지 않는 내부 이벤트 */
const HIDDEN = new Set([
  "command",
  "decision_requested",
  "priority_calculated",
  "get_completed",
  "phase_auto_advanced",
  "catch_skipped",
  "hand_limit_adjusted",
  "setup_completed",
  "battle_revealed",
  "clock_started",
  "clock_stopped",
  "combo_proposed",
  "combo_first_selected",
  // 요한의 추측: card_guess_resolved 한 항목으로 보여 준다(같은 카드를 확인한 기록)
  "card_inspected",
  "modifier_added",
]);

/** 요한 등 손패 추측의 선언 */
const GUESS_LABELS: Record<string, string> = {
  odd: "홀수",
  even: "짝수",
  attack: "공격 기술",
  odd_attack: "홀수 속도 공격 기술",
  even_attack: "짝수 속도 공격 기술",
  defense: "수비 기술",
};

const REASON_LABELS: Record<string, string> = {
  ready: "레디",
  combo: "콤보",
  combo_presented: "콤보",
  catch: "캐치",
  get: "겟",
  draw: "드로우",
  discard: "버리기",
  effect: "효과",
  play_cost: "비용",
  battle_cleanup: "배틀 정리",
  break_replenish: "사이드 보충",
  hand_limit: "손패 제한",
};

type Payload = Record<string, unknown>;

function cardFrom(payload: Payload | undefined, owner?: Side): LogCard | null {
  if (!payload) return null;
  const card_id = (payload.card_id as number | null | undefined) ?? null;
  const code = (payload.card_code as string | undefined) ?? (payload.code as string | undefined) ?? null;
  if (card_id == null && !code) return null;
  return { card_id, code, name: String(payload.card_label ?? payload.name ?? ""), owner };
}

/** instance id만 있는 이벤트: 지금 보드에서 그 카드를 찾아 그림을 붙인다(비공개 카드는 찾지 못한다). */
function cardByInstance(envelope: PlayEnvelope, instanceId: unknown): LogCard | null {
  if (!instanceId) return null;
  for (const side of ["p1", "p2"] as const) {
    for (const cards of Object.values(envelope.state.players[side].zones)) {
      for (const card of cards) {
        if (!card.hidden && (card as VisibleCard).instance_id === instanceId) {
          const visible = card as VisibleCard;
          return { card_id: visible.card_id, code: visible.code, name: visible.name, owner: visible.owner };
        }
      }
    }
  }
  return null;
}

function sideOf(player: unknown, me: Side): LogEntry["side"] {
  if (player === me) return "me";
  if (player === "p1" || player === "p2") return "opp";
  return "system";
}

const zone = (name: unknown) => ZONE_LABELS[name as ZoneName] ?? String(name ?? "");

export function logEntry(event: GameEvent, envelope: PlayEnvelope, me: Side): LogEntry | null {
  if (HIDDEN.has(event.type)) return null;
  const p = event.payload as Payload;
  const base = { seq: event.seq, side: sideOf(event.actor, me), cards: [] as LogCard[], deltas: [] as LogEntry["deltas"] };
  const one = (card: LogCard | null) => (card ? [card] : []);
  switch (event.type) {
    case "phase_started":
      return {
        ...base,
        side: "system",
        divider: true,
        title: `턴 ${String(p.turn ?? "")} · ${PHASE_LABELS[String(p.phase)] ?? String(p.phase)}`,
      };
    case "card_moved": {
      // 레디는 card_readied 항목으로 이미 보여 준다.
      if (p.reason === "ready") return null;
      const reason = REASON_LABELS[String(p.reason ?? "")];
      return {
        ...base,
        side: sideOf(p.to_player ?? event.actor, me),
        title: String(p.card_label ?? "카드"),
        detail: `${zone(p.from_zone)} → ${zone(p.to_zone)}${reason ? ` · ${reason}` : ""}`,
        cards: one(cardFrom(p, p.to_player as Side)),
      };
    }
    case "card_readied": {
      const card = cardFrom(p, event.actor as Side);
      return { ...base, title: card ? `레디 · ${card.name}` : "레디", cards: one(card) };
    }
    case "battle_judged": {
      const result = (p.result ?? {}) as Record<string, string>;
      const speed = (p.speed ?? {}) as Record<string, number>;
      const opp: Side = me === "p1" ? "p2" : "p1";
      const cards = (p.cards ?? {}) as Record<string, Payload>;
      const mine = result[me];
      return {
        ...base,
        side: "system",
        title: `배틀 판정 · ${JUDGE_LABELS[mine] ?? mine ?? "-"}`,
        detail: `나 ${speed[me] ?? "-"}속도 vs 상대 ${speed[opp] ?? "-"}속도 (${JUDGE_LABELS[result[opp]] ?? result[opp] ?? "-"})`,
        cards: [...one(cardFrom(cards[me], me)), ...one(cardFrom(cards[opp], opp))],
      };
    }
    case "hp_changed": {
      // FP와 같은 모양: 제목 HP, 설명에 이전 → 이후, 오른쪽에 HP ±
      const amount = Number(p.amount ?? 0);
      return { ...base, title: "HP", detail: `${String(p.before)} → ${String(p.after)}`, deltas: [{ label: "HP", amount }] };
    }
    case "fp_changed": {
      const amount = Number(p.amount ?? 0);
      return { ...base, title: "FP", detail: p.after != null ? `${String(p.before ?? "")} → ${String(p.after)}` : undefined, deltas: [{ label: "FP", amount }] };
    }
    case "damage_dealt":
      // 체력 변화는 hp_changed 항목(HP -수치)으로 보여 준다.
      return null;
    case "effect_resolved":
      return {
        ...base,
        title: String(p.card_label ?? "효과"),
        detail: String(p.effect_label ?? ""),
        cards: one(cardFrom(p, event.actor as Side) ?? cardByInstance(envelope, p.card_instance_id)),
      };
    case "decision_resolved": {
      const selected = (p.selected_options ?? []) as Payload[];
      const labels = selected.map((option) => String(option.label ?? option.id ?? "")).filter(Boolean);
      return {
        ...base,
        title: `선택 · ${labels.join(", ") || "없음"}${p.timed_out ? " (시간 초과)" : ""}`,
        detail: String(p.prompt ?? ""),
        cards: selected
          .map((option) => cardFrom(option) ?? cardByInstance(envelope, option.card_instance_id))
          .filter((card): card is LogCard => !!card)
          .slice(0, 4),
      };
    }
    case "combo_card_used": {
      const card = cardByInstance(envelope, p.card_instance_id);
      return { ...base, title: `콤보 · ${card?.name ?? "카드"}`, detail: p.damage != null ? `데미지 ${String(p.damage)}` : undefined, cards: one(card) };
    }
    case "card_broken":
    case "card_discarded": {
      const card = cardFrom(p) ?? cardByInstance(envelope, p.card_instance_id);
      return { ...base, title: `${event.type === "card_broken" ? "브레이크" : "버리기"} · ${card?.name ?? "카드"}`, cards: one(card) };
    }
    case "state_gained":
    case "state_lost":
      return { ...base, title: `${event.type === "state_gained" ? "상태 획득" : "상태 해제"} · ${String(p.label ?? p.state ?? "")}` };
    case "card_guess_resolved": {
      // 손패 추측(요한): 무엇을 선언했고 맞았는지, 확인한 카드. 이어서 적용된 효과는 바로 뒤 항목들로 남는다.
      const guess = GUESS_LABELS[String(p.guess)] ?? String(p.guess ?? "");
      const source = p.source_card as Payload | undefined;
      const card = p.card as Payload | undefined;
      return {
        ...base,
        title: `추측 · ${guess} → ${p.correct ? "적중" : "빗나감"}`,
        detail: [source?.name ? String(source.name) : "", card?.name ? `확인한 카드: ${String(card.name)}` : ""].filter(Boolean).join(" · ") || undefined,
        cards: one(cardFrom(card ? { ...card, card_code: card.code } : undefined, (card?.owner as Side | undefined))),
      };
    }
    case "card_guess_skipped":
      return { ...base, title: "추측할 손패가 없어 넘어감" };
    case "card_visibility_changed": {
      const card = (p.card as Payload | undefined) ?? p;
      return {
        ...base,
        title: `${p.face_up ? "공개" : "비공개"} · ${String(p.card_label ?? card.name ?? "카드")}`,
        cards: p.face_up ? one(cardFrom({ ...card, card_code: card.code ?? p.card_code, card_id: card.card_id ?? p.card_id }, event.actor as Side)) : [],
      };
    }
    case "counter_changed": {
      const player = envelope.state.players[event.actor as Side];
      const label = player ? labelFor(player, String(p.counter)) : String(p.counter ?? "");
      const amount = Number(p.amount ?? 0);
      if (!amount) return null;
      return { ...base, title: `${label} 카운터 ${String(p.before)} → ${String(p.count)}`, deltas: [{ label, amount }] };
    }
    case "effect_log":
      return { ...base, title: String(p.text ?? "") };
    case "ready_first_forced":
      return { ...base, title: "레디 페이즈에 먼저 레디해야 함" };
    case "speed_fixed":
      return { ...base, title: `속도 고정 · ${String(p.speed ?? "")}`, cards: one(cardByInstance(envelope, p.card_instance_id)) };
    case "judgment_modified":
      return {
        ...base,
        title: `판정 변경 · ${String(p.before ?? "-")} → ${String(p.after ?? "-")}`,
        cards: one(cardByInstance(envelope, p.card_instance_id)),
      };
    case "shield_gained":
      return { ...base, title: `실드 ${String(p.amount ?? p.value ?? "")}` };
    case "state_expired":
      return { ...base, title: `상태 종료 · ${String(p.label ?? p.state ?? "")}` };
    case "hp":
    case "fp": {
      const amount = Number(p.amount ?? 0);
      return {
        ...base,
        side: sideOf(p.target, me),
        title: event.type.toUpperCase(),
        detail: `${String(p.before)} → ${String(p.after)}`,
        deltas: [{ label: event.type.toUpperCase(), amount }],
      };
    }
    case "move_card":
      return {
        ...base,
        side: sideOf(p.to_player ?? event.actor, me),
        title: String(p.card_label ?? "카드"),
        detail: `${zone(p.from_zone)} → ${zone(p.to_zone)}`,
        cards: one(cardFrom(p) ?? cardByInstance(envelope, p.card_instance_id)),
      };
    default: {
      const text = eventText(event, me);
      if (!text) return null;
      return { ...base, title: text.replace(/^(나|상대): /, "") };
    }
  }
}

export function logEntries(events: GameEvent[], envelope: PlayEnvelope): LogEntry[] {
  const me: Side = envelope.role === "p2" ? "p2" : "p1";
  return events.map((event) => logEntry(event, envelope, me)).filter((entry): entry is LogEntry => !!entry);
}
