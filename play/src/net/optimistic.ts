import { usePlay } from "../store";
import type { BoardCard, CardRef, LegalAction, PlayEnvelope, Side, VisibleCard, ZoneName } from "../protocol";

/**
 * 내 행동의 즉시 반영(낙관적 갱신).
 *
 * 행동을 보내는 순간 결과를 예측해서 화면에 먼저 반영한다(카드 이동, HP 변화 등).
 * 예측은 서버가 그 요청을 받았다고 알려 줄 때(command_ack / action_ack)까지 유지하고,
 * 그 뒤에 오는 서버 상태가 진짜 결과로 대신한다. 거절되면 예측을 버리고 서버 상태로 되돌린다.
 *
 * 서버 상태가 화면에 오를 때마다(withPending) 아직 확인되지 않은 예측을 다시 얹으므로,
 * 수동 모드에서 행동을 빠르게 여러 번 해도 앞의 응답이 뒤의 예측을 지우지 않는다.
 */

type Mutator = (envelope: PlayEnvelope) => void;

interface PendingOp {
  id: string;
  apply: Mutator;
  acked: boolean;
}

let ops: PendingOp[] = [];
/** 마지막으로 받은 서버 상태(예측을 얹기 전) */
let lastServer: PlayEnvelope | null = null;

function applyAll(envelope: PlayEnvelope, list: PendingOp[]): PlayEnvelope {
  if (!list.length) return envelope;
  const copy = structuredClone(envelope);
  // 예측 상태에서는 다음 행동을 고를 수 없다. 서버 상태가 오면 다시 생긴다.
  copy.legal_actions = [];
  for (const op of list) {
    try {
      op.apply(copy);
    } catch (error) {
      console.warn("[play] prediction failed", error);
    }
  }
  return copy;
}

/** 서버 상태를 화면에 올리기 직전에 부른다. 확인된 예측은 버리고 남은 것만 얹는다. */
export function withPending(envelope: PlayEnvelope): PlayEnvelope {
  lastServer = envelope;
  ops = ops.filter((op) => !op.acked);
  return applyAll(envelope, ops);
}

/** 행동을 보내기 직전에 예측을 등록하고 바로 화면에 반영한다. */
export function predict(id: string, apply: Mutator | null) {
  if (!apply) return;
  const op: PendingOp = { id, apply, acked: false };
  ops.push(op);
  const current = usePlay.getState().envelope;
  if (current) usePlay.getState().setEnvelope(applyAll(current, [op]));
}

export function acknowledge(id: string | null | undefined) {
  const op = ops.find((item) => item.id === id);
  if (op) op.acked = true;
}

/** 거절·시간 초과: 그 예측을 버리고 마지막 서버 상태에 남은 예측만 얹어 다시 보여 준다. */
export function reject(id: string | null | undefined) {
  const before = ops.length;
  ops = id ? ops.filter((op) => op.id !== id) : [];
  if (ops.length !== before && lastServer) usePlay.getState().setEnvelope(applyAll(lastServer, ops));
}

export function resetPredictions() {
  ops = [];
  lastServer = null;
}

// ---------------------------------------------------------------------------
// 예측 규칙

function locate(envelope: PlayEnvelope, ref: CardRef | null, instanceId?: string | null) {
  for (const side of ["p1", "p2"] as const) {
    const zones = envelope.state.players[side].zones;
    for (const zone of Object.keys(zones) as ZoneName[]) {
      const index = zones[zone].findIndex(
        (card) => !card.hidden && !!instanceId && (card as VisibleCard).instance_id === instanceId,
      );
      if (index >= 0) return { side, zone, index };
    }
  }
  if (ref && envelope.state.players[ref.owner]?.zones[ref.zone]?.[ref.index]) return { side: ref.owner, zone: ref.zone, index: ref.index };
  return null;
}

/** 카드를 다른 존으로 옮긴다. faceUp을 주면 공개 상태도 바꾼다. */
export function moveCard(
  envelope: PlayEnvelope,
  card: { ref?: CardRef | null; instanceId?: string | null },
  to: { owner: Side; zone: ZoneName },
  faceUp?: boolean,
) {
  const found = locate(envelope, card.ref ?? null, card.instanceId);
  if (!found) return;
  const zones = envelope.state.players[found.side].zones;
  const [moved] = zones[found.zone].splice(found.index, 1);
  const next: BoardCard = moved.hidden
    ? { ...moved, owner: to.owner, zone: to.zone }
    : { ...moved, owner: (moved as VisibleCard).owner, zone: to.zone, ...(faceUp === undefined ? {} : { face_up: faceUp }) };
  envelope.state.players[to.owner].zones[to.zone].push(next);
}

const TO_BATTLE = new Set(["ready_card", "play_catch_card", "select_combo_first", "select_combo_followup"]);
const TO_HAND = new Set(["select_get_card", "select_ultimate"]);

/** 자동 판정 행동의 예측. 규칙 판정이 필요한 결과(HP, 효과)는 예측하지 않는다. */
export function predictCommand(
  envelope: PlayEnvelope,
  action: LegalAction,
  selections?: { selected?: string[] },
): Mutator {
  const me: Side = envelope.role === "p2" ? "p2" : "p1";
  const ref = action.ui.cards[0] ?? null;
  return (draft) => {
    if (action.ui.kind === "decision") {
      // 고른 카드에 도착 존 힌트가 있으면 옮겨 놓고, 선택 창은 닫는다.
      for (const option of action.options ?? []) {
        if (!selections?.selected?.includes(option.id) || !option.ui.card || !option.ui.to_zone) continue;
        moveCard(draft, { ref: option.ui.card, instanceId: option.ui.card.instance_id }, { owner: option.ui.card.owner, zone: option.ui.to_zone });
      }
      draft.pending_decision = null;
      return;
    }
    if (!ref) return;
    const card = { ref, instanceId: ref.instance_id };
    if (action.type === "select_combo_followup") {
      // 1·2콤보를 함께 배틀 존에 놓는다(1콤보 카드는 그동안 화면에서만 배틀 존에 있었다).
      const proposal = action.payload?.proposal as { card_instance_ids?: string[] } | undefined;
      const first = proposal?.card_instance_ids?.[0];
      if (first) moveCard(draft, { instanceId: first }, { owner: me, zone: "battle" }, true);
    }
    if (action.type === "ready_card") moveCard(draft, card, { owner: me, zone: "battle" }, false);
    else if (TO_BATTLE.has(action.type) || action.type.startsWith("play_combo")) moveCard(draft, card, { owner: me, zone: "battle" }, true);
    else if (TO_HAND.has(action.type)) moveCard(draft, card, { owner: me, zone: "hand" }, true);
  };
}

const PUBLIC_ZONES = new Set<ZoneName>(["character", "passive", "list", "break", "ultimate"]);

/** 수동 모드 행동의 예측(서버가 그대로 적용하는 것들) */
export function predictManual(action: string, payload: Record<string, unknown>): Mutator | null {
  const target = payload.target as Side | undefined;
  switch (action) {
    case "move_card":
      return (draft) => {
        const zone = payload.to_zone as ZoneName;
        moveCard(
          draft,
          { instanceId: String(payload.card_instance_id) },
          { owner: payload.to_player as Side, zone },
          PUBLIC_ZONES.has(zone) ? true : undefined,
        );
      };
    case "set_visibility":
      return (draft) => {
        const found = locate(draft, null, String(payload.card_instance_id));
        if (found) {
          const card = draft.state.players[found.side].zones[found.zone][found.index] as VisibleCard;
          card.face_up = !!payload.face_up;
        }
      };
    case "hp":
    case "fp":
      return (draft) => {
        if (target && draft.state.players[target]) draft.state.players[target][action] += Number(payload.amount ?? 0);
      };
    case "fp_reset":
      return (draft) => {
        if (target && draft.state.players[target]) draft.state.players[target].fp = 0;
      };
    case "passive":
      return (draft) => {
        if (!target || !draft.state.players[target]) return;
        const key = String(payload.key);
        const states = (draft.state.players[target].passive_state ??= {});
        states[key] = { ...(states[key] ?? {}), value: payload.value as boolean | number | string, label: String(payload.label ?? key) };
      };
    case "set_phase":
      return (draft) => {
        draft.state.phase = String(payload.phase);
      };
    default:
      return null;
  }
}
