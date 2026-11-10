import { AnimatePresence, motion } from "motion/react";
import type { BoardCard, LegalAction, PlayEnvelope, ZoneName } from "../protocol";
import { cardDetailText, cardText, useCardView } from "../catalog";
import { ZONE_LABELS } from "../labels";
import { refKey, usePlay, type InspectTarget } from "../store";
import { isManual } from "../net/live";
import { Card } from "./Card";
import { ManualCardActions } from "./Manual";
import { decisionCandidates, optionForCard, stagedIds, toggleDecisionPick } from "./Decision";

/** 카드 확대 보기. 그 카드에 묶인 행동이 여러 개면 여기서 고른다. */
export function CardInspector({
  envelope,
  onAction,
}: {
  envelope: PlayEnvelope;
  onAction: (action: LegalAction) => void;
}) {
  const inspect = usePlay((s) => s.inspect);
  const setInspect = usePlay((s) => s.setInspect);
  return (
    <AnimatePresence>
      {inspect && (
        <motion.div
          className="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setInspect(null)}
        >
          <InspectorPanel
            envelope={envelope}
            target={inspect}
            actions={envelope.legal_actions.filter(
              (action) =>
                action.ui.kind === "card" && action.ui.cards.some((ref) => refKey(ref) === refKey(inspect.ref)),
            )}
            onClose={() => setInspect(null)}
            onAction={(action) => {
              setInspect(null);
              onAction(action);
            }}
          />
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function InspectorPanel({
  envelope,
  target,
  actions,
  onClose,
  onAction,
}: {
  envelope: PlayEnvelope;
  target: InspectTarget;
  actions: LegalAction[];
  onClose: () => void;
  onAction: (action: LegalAction) => void;
}) {
  return (
    <motion.div
      className="inspector"
      initial={{ scale: 0.9, y: 20 }}
      animate={{ scale: 1, y: 0 }}
      exit={{ scale: 0.9, y: 20 }}
      onClick={(event) => event.stopPropagation()}
    >
      <Card card={target.card} size="large" />
      <div className="inspector-body">
        <CardDetails card={target.card} zone={target.ref.zone} />
        {actions.length > 0 && (
          <div className="inspector-actions">
            {actions.map((action) => (
              <button key={action.action_id} type="button" className="btn-primary" onClick={() => onAction(action)}>
                {actionVerb(action)}
              </button>
            ))}
          </div>
        )}
        {isManual(envelope) && (
          <ManualCardActions envelope={envelope} card={target.card} zone={target.ref.zone} onDone={onClose} />
        )}
        <button type="button" className="btn-ghost" onClick={onClose}>
          닫기
        </button>
      </div>
    </motion.div>
  );
}

/** 카드 이름·코드·수치·효과문(확대 보기와 PC 사이드 패널이 함께 쓴다) */
export function CardDetails({ card, zone }: { card: BoardCard; zone: ZoneName }) {
  const view = useCardView(card);
  if (!view) return <p className="muted">비공개 카드입니다.</p>;
  const text = cardText(view);
  const detail = cardDetailText(view);
  const meta = [
    view.type,
    view.frame != null ? `속도 ${view.frame}` : null,
    view.damage != null ? `데미지 ${view.damage}` : null,
    view.pos,
    ZONE_LABELS[zone],
  ].filter(Boolean);
  return (
    <>
      <h2>{view.name}</h2>
      {view.code && <span className="inspector-code">{view.code}</span>}
      <p className="inspector-meta">{meta.join(" · ")}</p>
      {text && <p className="inspector-text">{text}</p>}
      {detail && <p className="inspector-detail">{detail}</p>}
    </>
  );
}

export function actionVerb(action: LegalAction): string {
  const verbs: Record<string, string> = {
    ready_card: "레디",
    select_get_card: "획득",
    select_ultimate: "얼티밋 획득",
    play_catch_card: "캐치",
    select_combo_first: "콤보 시작",
    select_combo_followup: "콤보 연결",
  };
  const verb = verbs[action.type];
  return verb ? `${verb} · ${action.label}` : action.label;
}

/** 더미로 접힌 존의 카드 목록 */
export function ZoneSheet({ envelope }: { envelope: PlayEnvelope }) {
  const openZone = usePlay((s) => s.openZone);
  const setOpenZone = usePlay((s) => s.setOpenZone);
  const setInspect = usePlay((s) => s.setInspect);
  const picks = usePlay((s) => s.decisionPicks);
  const candidates = decisionCandidates(envelope);
  const staged = stagedIds(envelope, picks);
  const cards: BoardCard[] = openZone ? envelope.state.players[openZone.owner].zones[openZone.zone] : [];
  const mine = openZone && openZone.owner === (envelope.role === "p2" ? "p2" : "p1");
  return (
    <AnimatePresence>
      {openZone && (
        <motion.div
          className="overlay"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={() => setOpenZone(null)}
        >
          <motion.div
            className="zone-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2>
                {mine ? "내" : "상대"} {ZONE_LABELS[openZone.zone]} <span className="muted">{cards.length}장</span>
              </h2>
              <button type="button" className="btn-ghost" onClick={() => setOpenZone(null)}>
                닫기
              </button>
            </header>
            <div className="zone-sheet-cards">
              {cards.length === 0 && <p className="muted">카드가 없습니다.</p>}
              {cards.map((card, index) => {
                const ref = { owner: openZone.owner, zone: openZone.zone, index };
                const optionId = optionForCard(candidates, ref, card)?.id;
                const isStaged = !!optionId && staged.has(String((card as { instance_id?: string }).instance_id));
                return (
                  <Card
                    key={card.hidden ? `sheet-${index}` : `sheet-${String(card.instance_id)}`}
                    card={card}
                    size="board"
                    detached
                    playable={!!optionId && !picks.includes(optionId)}
                    selected={!!optionId && !isStaged && picks.includes(optionId)}
                    staged={isStaged}
                    onClick={() =>
                      optionId ? toggleDecisionPick(optionId, candidates.maximum) : setInspect({ card, ref })
                    }
                  />
                );
              })}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function Notice() {
  const notice = usePlay((s) => s.notice);
  return (
    <AnimatePresence>
      {notice && (
        <motion.div className="notice" initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
          {notice}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
