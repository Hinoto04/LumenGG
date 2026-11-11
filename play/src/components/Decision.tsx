import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import type { BoardCard, CardRef, DecisionOption, LegalAction, PlayEnvelope, VisibleCard, ZoneName } from "../protocol";
import { moveCard } from "../net/optimistic";
import { ZONE_LABELS } from "../labels";
import { perspective, refKey, usePlay } from "../store";
import { Card } from "./Card";
import { ClockBadge } from "./Clock";

export type SubmitAction = (action: LegalAction, selections?: { selected?: string[]; reason?: string }) => void;

/**
 * 카드를 옮기는 선택(손패 제한 버리기, 효과로 카드 이동 …): 모든 선택지가 카드이고 도착 존을 알면
 * 선택 창을 띄우지 않고 보드에서 끌어 옮긴다. 옮긴 카드는 확정 전까지 도착 존에 노란 테두리로
 * 보이고(stageDecision), 다시 끌거나 눌러서 되돌릴 수 있다.
 */
export function movesOnBoard(options: DecisionOption[]): boolean {
  const cards = options.filter((option) => option.ui?.card);
  // 카드가 아닌 선택지(예: 사이드 보충의 "보충하지 않음")는 위쪽 안내의 버튼으로 고른다.
  return cards.length > 0 && cards.every((option) => option.ui.to_zone);
}

/** 옮긴 카드가 공개되는 존 */
const FACE_UP_ZONES = new Set<ZoneName>(["list", "break", "ultimate"]);

/**
 * 고른 카드들을 도착 존으로 옮긴 화면용 상태. 서버에는 확정할 때 한꺼번에 보낸다.
 * 보드 모드가 아니면(선택 창으로 고르는 선택) 그대로 돌려준다.
 */
export function stageDecision(envelope: PlayEnvelope, picks: string[]): PlayEnvelope {
  const candidates = decisionCandidates(envelope);
  if (!candidates.action || !picks.length || !movesOnBoard([...candidates.options.values()])) return envelope;
  const moving = [...candidates.options.values()]
    .filter((option) => picks.includes(option.id))
    // 같은 존에서 여러 장을 뺄 때 위치가 밀리지 않게 뒤에서부터
    .sort((a, b) => b.ui.card!.index - a.ui.card!.index);
  if (!moving.length) return envelope;
  const copy = structuredClone(envelope);
  for (const option of moving) {
    const ref = option.ui.card!;
    const zone = option.ui.to_zone!;
    moveCard(copy, { ref, instanceId: ref.instance_id }, { owner: ref.owner, zone }, FACE_UP_ZONES.has(zone) ? true : undefined);
  }
  return copy;
}

/** 확정 전에 옮겨 둔 카드들의 instance id */
export function stagedIds(envelope: PlayEnvelope | null, picks: string[]): Set<string> {
  const ids = new Set<string>();
  if (!envelope) return ids;
  const first = comboFirstId(envelope);
  if (first) ids.add(first);
  if (!picks.length) return ids;
  const candidates = decisionCandidates(envelope);
  if (!movesOnBoard([...candidates.options.values()])) return ids;
  for (const option of candidates.options.values()) {
    const id = option.ui.card?.instance_id;
    if (id && picks.includes(option.id)) ids.add(String(id));
  }
  return ids;
}

/**
 * 콤보: 1콤보 카드를 고르고 2콤보 카드를 고르기 전. 서버는 두 장을 함께 받을 때까지 1콤보 카드를
 * 손패에 두므로, 화면에서는 배틀 존에 놓아 두고(노란 테두리) 되돌리기(cancel_combo_first)를 받는다.
 */
export function comboFirstId(envelope: PlayEnvelope | null): string | null {
  const action = envelope?.legal_actions.find((item) => item.type === "select_combo_followup");
  const proposal = action?.payload?.proposal as { card_instance_ids?: string[] } | undefined;
  return proposal?.card_instance_ids?.[0] ?? null;
}

export function comboCancelAction(envelope: PlayEnvelope | null): LegalAction | null {
  return envelope?.legal_actions.find((item) => item.type === "cancel_combo_first") ?? null;
}

/** 고른 1콤보 카드를 배틀 존에 놓은 화면용 상태 */
export function stageCombo(envelope: PlayEnvelope): PlayEnvelope {
  const id = comboFirstId(envelope);
  if (!id) return envelope;
  const { me } = perspective(envelope);
  if (envelope.state.players[me].zones.battle.some((card) => !card.hidden && card.instance_id === id)) return envelope;
  const copy = structuredClone(envelope);
  moveCard(copy, { instanceId: id }, { owner: me, zone: "battle" }, true);
  return copy;
}

/** 끌어 놓기: 이미 고른 카드면 그대로 두고, 아니면 고른다(놓았는데 선택이 풀리지 않게). */
export function addDecisionPick(id: string, maximum: number) {
  if (!usePlay.getState().decisionPicks.includes(id)) toggleDecisionPick(id, maximum);
}

/** 선택 창과 보드가 함께 쓰는 선택 토글. 하나만 고르면 바꿔 끼운다. */
export function toggleDecisionPick(id: string, maximum: number) {
  const current = usePlay.getState().decisionPicks;
  let next: string[];
  if (current.includes(id)) next = current.filter((item) => item !== id);
  else if (maximum <= 1) next = [id];
  else next = current.length >= maximum ? current : [...current, id];
  usePlay.getState().setDecisionPicks(next);
}

export interface DecisionCandidates {
  /** refKey → 그 카드를 고르는 선택지 id */
  byRef: Map<string, string>;
  /** refKey → 선택지(도착 존 힌트 ui.to_zone 포함) */
  options: Map<string, DecisionOption>;
  /** 카드 instance id → 선택지. 옮겨 둔 카드(위치가 바뀜)도 찾을 수 있다. */
  byInstance: Map<string, DecisionOption>;
  minimum: number;
  maximum: number;
  action: LegalAction | null;
}

/** 보드 카드 → 그 카드를 고르는 선택지. 내가 고르는 선택이 있을 때만. */
export function decisionCandidates(envelope: PlayEnvelope): DecisionCandidates {
  const result: DecisionCandidates = { byRef: new Map(), options: new Map(), byInstance: new Map(), minimum: 1, maximum: 1, action: null };
  const action = envelope.legal_actions.find((item) => item.ui.kind === "decision");
  const decision = envelope.pending_decision;
  if (!action || (decision && decision.owner !== perspective(envelope).me)) return result;
  for (const option of action.options ?? decision?.options ?? []) {
    if (!option.ui?.card) continue;
    result.byRef.set(refKey(option.ui.card), option.id);
    result.options.set(refKey(option.ui.card), option);
    if (option.ui.card.instance_id) result.byInstance.set(String(option.ui.card.instance_id), option);
  }
  result.minimum = Number(action.minimum ?? decision?.minimum ?? 1);
  result.maximum = Number(action.maximum ?? decision?.maximum ?? 1);
  result.action = action;
  return result;
}

/** 보드에 보이는 카드(옮겨 둔 카드 포함) → 그 카드를 고르는 선택지 */
export function optionForCard(candidates: DecisionCandidates, ref: CardRef | Pick<CardRef, "owner" | "zone" | "index">, card: BoardCard): DecisionOption | undefined {
  if (!card.hidden && (card as VisibleCard).instance_id) {
    const found = candidates.byInstance.get(String((card as VisibleCard).instance_id));
    if (found) return found;
    if (candidates.byInstance.size) return undefined;
  }
  return candidates.options.get(refKey(ref));
}

/** "N From"의 N: 옮겨야 할 장 수 */
export function requiredText(minimum: number, maximum: number): string {
  return minimum === maximum || minimum <= 0 && maximum <= 1 ? String(maximum) : `${minimum}~${maximum}`;
}

/** 선택지를 카드가 있는 존별로 묶는다(내 손패, 상대 리스트 …). 카드가 아닌 선택지는 마지막에. */
function groupOptions(options: DecisionOption[], me: string): [string, DecisionOption[]][] {
  const groups = new Map<string, DecisionOption[]>();
  for (const option of options) {
    const ref = option.ui?.card;
    const key = ref ? `${ref.owner === me ? "내" : "상대"} ${ZONE_LABELS[ref.zone] ?? ref.zone}` : "";
    groups.set(key, [...(groups.get(key) ?? []), option]);
  }
  const entries = [...groups.entries()];
  // 한 존에서만 고르는 경우에도 어디서 고르는지 보이도록 제목을 단다.
  return entries.sort(([a], [b]) => (a === "" ? 1 : b === "" ? -1 : 0));
}

function optionCard(envelope: PlayEnvelope, option: DecisionOption): BoardCard | null {
  const ref = option.ui?.card;
  if (!ref) return null;
  return envelope.state.players[ref.owner]?.zones[ref.zone]?.[ref.index] ?? null;
}

/**
 * 효과 선택 창. 선택지가 카드면 카드로, 아니면 버튼으로 보여 준다.
 * minimum~maximum개를 고르면 확정할 수 있다. 보드를 보려고 잠시 접을 수 있다.
 */
export function DecisionPanel({
  envelope,
  action,
  busy,
  onSubmit,
}: {
  envelope: PlayEnvelope;
  action: LegalAction;
  busy: boolean;
  onSubmit: SubmitAction;
}) {
  const decision = envelope.pending_decision;
  const options = useMemo(() => action.options ?? decision?.options ?? [], [action, decision]);
  const minimum = Number(action.minimum ?? decision?.minimum ?? 1);
  const maximum = Number(action.maximum ?? decision?.maximum ?? 1);
  const decisionId = String(decision?.id ?? action.action_id);
  const selected = usePlay((s) => s.decisionPicks);
  const setSelected = usePlay((s) => s.setDecisionPicks);
  const collapsed = usePlay((s) => s.decisionCollapsed);
  const setCollapsed = usePlay((s) => s.setDecisionCollapsed);
  const setInspect = usePlay((s) => s.setInspect);

  // 카드를 옮기는 선택이면(예: 손패 제한 버리기 → 리스트) 선택 창으로 덮지 않고 보드에서 끌어 옮긴다.
  const onBoard = movesOnBoard(options);
  useEffect(() => {
    const valid = new Set(options.map((option) => option.id));
    setSelected(onBoard ? [] : (decision?.default ?? []).filter((id) => valid.has(id)).slice(0, maximum));
    setCollapsed(onBoard);
  }, [decisionId]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = (id: string) => toggleDecisionPick(id, maximum);

  const ready = selected.length >= minimum && selected.length <= maximum;

  // 빠른 확정(설정): 옮겨야 할 장 수(최대)를 다 옮기면 바로 보낸다. 같은 선택은 한 번만 보낸다.
  const quickConfirm = usePlay((s) => s.quickConfirm);
  const autoSent = useRef<string | null>(null);
  useEffect(() => {
    if (!quickConfirm || !onBoard || busy || autoSent.current === decisionId) return;
    if (selected.length === maximum && selected.length >= minimum && selected.length > 0) {
      autoSent.current = decisionId;
      onSubmit(action, { selected });
    }
  }, [quickConfirm, onBoard, busy, selected, maximum, minimum, decisionId, action, onSubmit]);
  const destination = options.find((option) => option.ui?.to_zone)?.ui.to_zone;
  const fromPile = options.some((option) => option.ui?.card && !["hand", "list", "battle"].includes(option.ui.card.zone));
  const hintText = onBoard
    ? "빨간 테두리(From)에서 파란 테두리(To)로 카드를 끌어 옮기세요" +
      (fromPile ? " · 더미의 카드는 펼친 패널에서 끌어 옵니다" : "") +
      (selected.length ? " · 노란 테두리 카드는 다시 끌거나 눌러 되돌립니다" : "")
    : options.some((option) => option.ui?.to_zone)
      ? `${ZONE_LABELS[destination!]}(으)로 끌어 놓거나 눌러서 고르세요`
      : "빛나는 카드를 눌러서 고르세요";
  const countHint =
    maximum <= 1 ? (minimum === 0 ? "고르지 않아도 됩니다" : "하나를 고르세요") : minimum === maximum ? `${minimum}개를 고르세요` : `${minimum}~${maximum}개를 고르세요`;

  return (
    <AnimatePresence>
      {collapsed && (
        <motion.div
          key="hint"
          className="decision-hint"
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          role="status"
        >
          <strong>{decision?.prompt || action.label}</strong>
          <span>{hintText}</span>
          {onBoard && (
            <span className="decision-hint-count">
              {selected.length} / {requiredText(minimum, maximum)}
            </span>
          )}
          <span className="decision-hint-buttons">
            {onBoard &&
              options
                .filter((option) => !option.ui?.card)
                .map((option) => (
                  <button
                    key={option.id}
                    type="button"
                    className="btn-ghost"
                    disabled={busy}
                    onClick={() => onSubmit(action, { selected: [option.id] })}
                  >
                    {option.label || option.id}
                  </button>
                ))}
            {onBoard && selected.length > 0 && (
              <button type="button" className="btn-ghost" onClick={() => setSelected([])}>
                모두 되돌리기
              </button>
            )}
            <button type="button" className="btn-ghost" onClick={() => setCollapsed(false)}>
              목록으로 보기
            </button>
            {onBoard && (
              <button
                type="button"
                className="btn-primary"
                disabled={!ready || busy}
                onClick={() => onSubmit(action, { selected })}
              >
                {busy ? "보내는 중…" : "확정"}
              </button>
            )}
          </span>
        </motion.div>
      )}
      {!collapsed && (
        <motion.div
          className="decision-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.section
            className="decision"
            role="dialog"
            aria-label="효과 선택"
            initial={{ y: 40, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 40, opacity: 0 }}
            transition={{ type: "spring", stiffness: 420, damping: 34 }}
          >
            <header>
              <h2>{decision?.prompt || action.label}</h2>
              <span className="muted">
                {countHint}
                {maximum > 1 ? ` · ${selected.length}개 선택` : ""}
              </span>
              <ClockBadge envelope={envelope} />
            </header>
            {groupOptions(options, perspective(envelope).me).map(([group, groupOptions]) => (
            <div key={group} className="decision-group">
            {group && <h3 className="decision-group-title">{group}</h3>}
            <div className="decision-options">
              {groupOptions.map((option) => {
                const card = optionCard(envelope, option);
                const isOn = selected.includes(option.id);
                const ref = option.ui?.card;
                return (
                  <div key={option.id} className={`decision-option ${isOn ? "is-selected" : ""} ${card ? "has-card" : ""}`}>
                    {card && ref && (
                      <Card
                        card={card}
                        size="board"
                        selected={isOn}
                        detached
                        onClick={() => toggle(option.id)}
                      />
                    )}
                    <button type="button" className="decision-label" onClick={() => toggle(option.id)}>
                      {option.label || option.id}
                    </button>
                    {card && ref && (
                      <button type="button" className="decision-info" onClick={() => setInspect({ card, ref })}>
                        카드 보기
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
            </div>
            ))}
            {!!decision?.unavailable_options?.length && (
              <div className="decision-group decision-unavailable">
                <h3 className="decision-group-title">고를 수 없음</h3>
                <div className="decision-options">
                  {decision.unavailable_options.map((option) => (
                    <div key={option.id} className="decision-option is-disabled">
                      <button type="button" className="decision-label" disabled aria-disabled>
                        {option.label}
                      </button>
                      <span className="decision-reason">{option.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <footer>
              <button type="button" className="btn-ghost" onClick={() => setCollapsed(true)}>
                {options.some((option) => option.ui?.card) ? "보드에서 고르기" : "보드 보기"}
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={!ready || busy}
                onClick={() => onSubmit(action, { selected })}
              >
                {busy ? "보내는 중…" : "확정"}
              </button>
            </footer>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
