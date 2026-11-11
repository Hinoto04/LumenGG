import { AnimatePresence, motion } from "motion/react";
import type { LegalAction, PlayEnvelope, VisibleCard } from "../protocol";
import { perspective, showCardInfo } from "../store";
import { Card } from "./Card";

/**
 * 자동 판정의 "상대 시작 패 확인" 단계. 서버가 이 단계에서만 상대 손패를 공개하므로
 * 화면 위쪽에 작게 깔린 상대 손패 대신 크게 펼쳐 보여 주고, 확인 완료 버튼을 함께 둔다.
 */
export function OpeningReview({
  envelope,
  onAction,
}: {
  envelope: PlayEnvelope;
  onAction: (action: LegalAction) => void;
}) {
  const confirm = envelope.legal_actions.find((action) => action.type === "confirm_opening_review") ?? null;
  const stage = (envelope.engine_status as { startup_stage?: string } | undefined)?.startup_stage;
  const reviewing = !!confirm || stage === "opening_review";
  const { opp } = perspective(envelope);
  const cards = envelope.state.players[opp].zones.hand;
  const visible = cards.filter((card) => !card.hidden) as VisibleCard[];
  const open = reviewing && envelope.role !== "viewer" && visible.length > 0;
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="opening-review-backdrop" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <motion.section
            className="opening-review"
            role="dialog"
            aria-label="상대 시작 패"
            initial={{ y: 24, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 24, opacity: 0 }}
          >
            <header>
              <h2>상대 시작 패</h2>
              <span className="muted">{cards.length}장 · 카드를 누르면 자세히 볼 수 있습니다</span>
            </header>
            <div className="opening-review-cards">
              {visible.map((card, index) => (
                <Card
                  key={card.instance_id}
                  card={card}
                  size="board"
                  detached
                  onClick={() => showCardInfo({ card, ref: { owner: opp, zone: "hand", index, instance_id: card.instance_id } })}
                />
              ))}
            </div>
            <footer>
              {confirm ? (
                <button type="button" className="btn-primary" onClick={() => onAction(confirm)}>
                  {confirm.label || "상대 시작 패 확인 완료"}
                </button>
              ) : (
                <span className="muted">상대가 확인하기를 기다리는 중…</span>
              )}
            </footer>
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
