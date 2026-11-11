import {
  addDecisionPick,
  comboCancelAction,
  comboFirstId,
  decisionCandidates,
  movesOnBoard,
  optionForCard,
  toggleDecisionPick,
} from "./components/Decision";
import { ZONE_LABELS } from "./labels";
import { isManual, sendManual, submitAction } from "./net/live";
import type { BoardCard, CardRef, LegalAction, PlayEnvelope, Side, VisibleCard, ZoneName } from "./protocol";
import { cardActions, indexActions, perspective, usePlay } from "./store";

/**
 * 끌어 놓기: 카드 한 장이 옮겨 갈 수 있는 영역(B)과, 같은 B로 옮길 수 있는 카드가 있는 영역(A).
 *
 * - 자동 판정: 행동 종류로 정한다(레디·캐치·콤보 → 내 배틀존, 겟 → 내 손패).
 *   효과 선택은 서버가 준 도착 존 힌트(option.ui.to_zone)가 있을 때만.
 * - 수동 모드: 내 카드는 내 모든 존과 상대 배틀·루멘으로 옮길 수 있다(B가 여럿).
 * 놓으면 그 B로 옮기는 행동을 실행한다. 같은 B로 가는 행동이 여럿이면 카드를 선택해 고르게 한다.
 */

export interface ZoneRef {
  owner: Side;
  zone: ZoneName;
}

export interface DropTarget extends ZoneRef {
  label: string;
  /** 작은 영역(더미)에 쓰는 짧은 이름 */
  shortLabel: string;
  /** 이 영역 대신 놓아도 되는 더 넓은 자리(CSS 선택자). 손패 → 배틀 존은 내 필드 전체. */
  area?: string;
  run: () => void;
}

export interface DragPlan {
  card: ZoneRef & { index: number };
  /** 마스크에서 열어 둘 출발 영역들 */
  sources: ZoneRef[];
  targets: DropTarget[];
}

const zoneKey = (ref: ZoneRef) => `${ref.owner}:${ref.zone}`;

const TO_BATTLE = new Set(["ready_card", "play_catch_card", "select_combo_first", "select_combo_followup"]);
const TO_HAND = new Set(["select_get_card", "select_ultimate"]);

function actionTarget(action: LegalAction, me: Side): ZoneRef | null {
  if (TO_BATTLE.has(action.type) || action.type.startsWith("play_combo")) return { owner: me, zone: "battle" };
  if (TO_HAND.has(action.type)) return { owner: me, zone: "hand" };
  return null;
}

/** 마스크에 적는 도착 영역 이름 */
const DROP_LABELS: Partial<Record<ZoneName, string>> = {
  battle: "배틀 존",
  hand: "손패",
  list: "리스트",
  side: "사이드 덱",
  lumen: "루멘 존",
  break: "브레이크 존",
  ultimate: "얼티밋 존",
};

function shortLabel(target: ZoneRef, me: Side): string {
  return `${target.owner === me ? "" : "상대 "}${ZONE_LABELS[target.zone]}`;
}

function targetLabel(target: ZoneRef, me: Side): string {
  return `${target.owner === me ? "" : "상대 "}${DROP_LABELS[target.zone] ?? ZONE_LABELS[target.zone]}`;
}

const MANUAL_ZONES: ZoneName[] = ["battle", "hand", "list", "side", "lumen", "break", "ultimate"];
const MANUAL_CROSS: ZoneName[] = ["battle", "lumen"];

/** 이 카드를 놓을 수 있는 영역들(같은 영역으로 가는 행동은 한데 묶는다) */
function targetsFor(
  envelope: PlayEnvelope,
  ref: CardRef,
  card: BoardCard,
  onAction: (action: LegalAction) => void,
  select: () => void,
): DropTarget[] {
  const { me } = perspective(envelope);

  // 고른 1콤보 카드(2콤보를 고르기 전): 손패로 끌면 첫 카드 선택을 취소한다.
  const cancelCombo = !card.hidden && (card as VisibleCard).instance_id === comboFirstId(envelope) ? comboCancelAction(envelope) : null;
  if (cancelCombo) {
    const home = { owner: me, zone: "hand" as ZoneName };
    return [{ ...home, label: `되돌리기 · ${targetLabel(home, me)}`, shortLabel: shortLabel(home, me), run: () => onAction(cancelCombo) }];
  }

  // 효과 선택의 후보 카드
  const candidates = decisionCandidates(envelope);
  const option = optionForCard(candidates, ref, card);
  if (option) {
    const zone = option.ui.to_zone;
    if (!zone || !option.ui.card) return [];
    const picked = usePlay.getState().decisionPicks.includes(option.id);
    const staging = movesOnBoard([...candidates.options.values()]);
    if (picked && staging) {
      // 옮겨 둔 카드: 원래 자리로 끌면 되돌린다.
      const home = { owner: option.ui.card.owner, zone: option.ui.card.zone };
      return [
        {
          ...home,
          label: `되돌리기 · ${targetLabel(home, me)}`,
          shortLabel: shortLabel(home, me),
          run: () => toggleDecisionPick(option.id, candidates.maximum),
        },
      ];
    }
    const owner = option.ui.card.owner;
    const target = { owner, zone };
    return [
      {
        ...target,
        label: targetLabel(target, me),
        shortLabel: shortLabel(target, me),
        run: () => {
          addDecisionPick(option.id, candidates.maximum);
          if (staging) return; // 확정은 따로(되돌릴 수 있게)
          const picks = usePlay.getState().decisionPicks;
          // 고를 수를 다 채우면 바로 확정한다(하나만 고르는 선택은 놓자마자 확정).
          if (candidates.action && picks.length >= candidates.maximum && picks.length >= candidates.minimum) {
            submitAction(candidates.action, { selected: picks });
          }
        },
      },
    ];
  }

  // 수동 모드: 내 카드는 어디로든
  if (isManual(envelope)) {
    if (!envelope.can_control || card.hidden) return [];
    const owner = ((card as VisibleCard).owner ?? ref.owner) as Side;
    if (owner !== me || card.kind === "character" || ref.zone === "passive") return [];
    const move = (target: ZoneRef) => () =>
      sendManual("move_card", { card_instance_id: (card as VisibleCard).instance_id, to_zone: target.zone, to_player: target.owner });
    const opp: Side = me === "p1" ? "p2" : "p1";
    return [
      ...MANUAL_ZONES.filter((zone) => zone !== ref.zone || ref.owner !== me).map((zone) => ({ owner: me, zone })),
      ...MANUAL_CROSS.map((zone) => ({ owner: opp, zone })),
    ].map((target) => ({ ...target, label: targetLabel(target, me), shortLabel: shortLabel(target, me), run: move(target) }));
  }

  // 자동 판정: 이 카드의 행동들
  const bound = cardActions(indexActions(envelope.legal_actions), ref, card);
  const groups = new Map<string, { target: ZoneRef; actions: LegalAction[] }>();
  for (const action of bound) {
    const target = actionTarget(action, me);
    if (!target || (target.zone === ref.zone && target.owner === ref.owner)) continue;
    const group = groups.get(zoneKey(target)) ?? { target, actions: [] };
    group.actions.push(action);
    groups.set(zoneKey(target), group);
  }
  return [...groups.values()].map(({ target, actions }) => ({
    ...target,
    label: targetLabel(target, me),
    shortLabel: shortLabel(target, me),
    run: actions.length === 1 ? () => onAction(actions[0]) : select,
  }));
}

/**
 * 끌기 시작할 때의 계획. B가 하나면 같은 B로 갈 수 있는 다른 카드들의 영역도 A로 열어 둔다.
 */
export function dragPlan(
  envelope: PlayEnvelope,
  ref: CardRef,
  card: BoardCard,
  onAction: (action: LegalAction) => void,
  select: () => void,
): DragPlan | null {
  const targets = targetsFor(envelope, ref, card, onAction, select);
  if (!targets.length) return null;
  const sources = new Map<string, ZoneRef>([[zoneKey(ref), { owner: ref.owner, zone: ref.zone }]]);
  if (targets.length === 1 && !isManual(envelope)) {
    const wanted = zoneKey(targets[0]);
    const refs = [
      ...indexActions(envelope.legal_actions).byCard.values(),
    ].flatMap((actions) => actions.flatMap((action) => action.ui.cards));
    for (const option of decisionCandidates(envelope).options.values()) if (option.ui.card) refs.push(option.ui.card);
    for (const other of refs) {
      const otherCard = envelope.state.players[other.owner]?.zones[other.zone]?.[other.index];
      if (!otherCard) continue;
      const otherTargets = targetsFor(envelope, other, otherCard, () => undefined, () => undefined);
      if (otherTargets.some((target) => zoneKey(target) === wanted)) {
        sources.set(zoneKey(other), { owner: other.owner, zone: other.zone });
      }
    }
  }
  // 손패에서 배틀 존으로만 갈 수 있는 카드(레디·콤보·캐치)는 내 필드 어디에 놓아도 배틀 존으로 친다.
  // 작은 화면에서 배틀 존을 정확히 맞히기 어렵기 때문이다.
  const { me } = perspective(envelope);
  if (
    !isManual(envelope) &&
    ref.zone === "hand" &&
    targets.length === 1 &&
    targets[0].zone === "battle" &&
    targets[0].owner === me
  ) {
    targets[0] = { ...targets[0], area: ".field-me" };
  }
  return { card: { ...ref }, sources: [...sources.values()], targets };
}

/** 넓은 놓는 자리(area)의 사각형 */
export function areaRect(selector?: string): DOMRect | null {
  if (!selector) return null;
  const rect = document.querySelector(selector)?.getBoundingClientRect();
  return rect && rect.width > 0 ? rect : null;
}

// ---------------------------------------------------------------------------
// 화면 위치: 영역 요소(data-drop-owner/zone)의 사각형

/**
 * 같은 영역을 가리키는 요소가 여럿일 수 있다(더미 버튼과 펼친 더미 패널 ZoneDock).
 * 놓기 판정은 모두 쓰고, 테두리·마스크는 가장 큰 요소에 그린다.
 */
export function zoneRects(ref: ZoneRef): DOMRect[] {
  return [...document.querySelectorAll(`[data-drop-owner="${ref.owner}"][data-drop-zone="${ref.zone}"]`)]
    .map((node) => node.getBoundingClientRect())
    .filter((rect) => rect.width > 0 && rect.height > 0);
}

export function zoneRect(ref: ZoneRef): DOMRect | null {
  let best: DOMRect | null = null;
  for (const rect of zoneRects(ref)) if (!best || rect.width * rect.height > best.width * best.height) best = rect;
  return best;
}

/** B가 여럿이면 놓기 쉽게 사각형을 조금씩 키운다. */
export const MULTI_TARGET_PAD = 14;

export function inflate(rect: DOMRect, pad: number): DOMRect {
  return new DOMRect(rect.x - pad, rect.y - pad, rect.width + pad * 2, rect.height + pad * 2);
}

export function targetAt(plan: DragPlan, point: { x: number; y: number }): DropTarget | null {
  const pad = plan.targets.length > 1 ? MULTI_TARGET_PAD : 0;
  let best: DropTarget | null = null;
  let bestArea = Infinity;
  for (const target of plan.targets) {
    const area = areaRect(target.area);
    for (const rect of area ? [...zoneRects(target), area] : zoneRects(target)) {
      const box = inflate(rect, pad);
      if (point.x >= box.left && point.x <= box.right && point.y >= box.top && point.y <= box.bottom) {
        // 키운 사각형이 겹치면 더 작은(더 구체적인) 영역을 고른다.
        const area = box.width * box.height;
        if (area < bestArea) {
          best = target;
          bestArea = area;
        }
      }
    }
  }
  return best;
}

export function insideSource(plan: DragPlan, point: { x: number; y: number }): boolean {
  return zoneRects(plan.card).some(
    (rect) => point.x >= rect.left && point.x <= rect.right && point.y >= rect.top && point.y <= rect.bottom,
  );
}
