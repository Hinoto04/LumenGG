import { AnimatePresence, motion } from "motion/react";
import { isStateCounterToken, type BoardCard, type LegalAction, type PlayEnvelope, type VisibleCard, type ZoneName } from "../protocol";
import { zoneEntries } from "../counterTokens";
import { cardDetailText, cardText, useCardView } from "../catalog";
import { ZONE_LABELS } from "../labels";
import { cardActions, indexActions, usePlay, type InspectTarget } from "../store";
import { isManual } from "../net/live";
import { Card } from "./Card";
import { ManualCardActions } from "./Manual";
import { decisionCandidates, optionForCard, stagedIds, toggleDecisionPick } from "./Decision";
import { t, cardCount } from "../i18n";

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
            // 화면에 옮겨 보여 준 카드(콤보 1번째 카드 등)가 있으면 위치가 서버와 다르므로 카드 id로 찾는다.
            actions={cardActions(indexActions(envelope.legal_actions), inspect.ref, inspect.card)}
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
          {t("닫기")}
        </button>
      </div>
    </motion.div>
  );
}

/** 카드 이름·코드·수치·효과문(확대 보기와 PC 사이드 패널이 함께 쓴다) */
export function CardDetails({ card, zone }: { card: BoardCard; zone: ZoneName }) {
  const view = useCardView(card);
  if (!view) return <p className="muted">{t("비공개 카드입니다.")}</p>;
  const text = cardText(view);
  const detail = cardDetailText(view);
  // 효과로 바뀐 값은 "인쇄값→지금 값"으로 적는다(카드 이미지 위 표시와 같은 stat_changes).
  const changes = (card as VisibleCard).stat_changes ?? {};
  const changed = (field: string, fallback: unknown, format: (value: unknown) => string = String) => {
    const change = changes[field];
    return change ? `${format(change.base ?? "—")}→${format(change.current ?? "—")}` : fallback;
  };
  const meta = [
    view.type_label || view.type,
    view.frame != null ? t("속도 {speed}", { speed: String(changed("frame", view.frame)) }) : null,
    view.damage != null ? t("데미지 {damage}", { damage: String(changed("damage", view.damage)) }) : null,
    changed("pos", view.pos_label || view.pos, (value) => t(String(value))),
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
    ready_card: t("레디"),
    select_get_card: t("획득"),
    select_ultimate: t("얼티밋 획득"),
    play_catch_card: t("캐치"),
    select_combo_first: t("콤보 시작"),
    select_combo_followup: t("콤보 연결"),
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
  const entries = openZone
    ? zoneEntries(cards, (card, index) => !!optionForCard(candidates, { owner: openZone.owner, zone: openZone.zone, index }, card))
    : [];
  const shown = cards.filter((card) => !isStateCounterToken(card)).length;
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
                {mine ? t("내 {zone}", { zone: ZONE_LABELS[openZone.zone] }) : t("상대 {zone}", { zone: ZONE_LABELS[openZone.zone] })}{" "}
                <span className="muted">{cardCount(shown)}</span>
              </h2>
              <button type="button" className="btn-ghost" onClick={() => setOpenZone(null)}>
                {t("닫기")}
              </button>
            </header>
            <div className="zone-sheet-cards">
              {cards.length === 0 && <p className="muted">{t("카드가 없습니다.")}</p>}
              {entries.map(({ card, index, stacked }) => {
                const ref = { owner: openZone.owner, zone: openZone.zone, index };
                const optionId = optionForCard(candidates, ref, card)?.id;
                const isStaged = !!optionId && staged.has(String((card as { instance_id?: string }).instance_id));
                const view = (
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
                return stacked ? (
                  <span key={`sheet-stack-${index}`} className="counter-stack" data-count={`×${stacked}`}>
                    {view}
                  </span>
                ) : (
                  view
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
