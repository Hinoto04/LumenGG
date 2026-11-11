import { AnimatePresence, motion } from "motion/react";
import { useMemo } from "react";
import { logEntries, type LogCard, type LogEntry } from "../logEntries";
import type { PlayEnvelope, VisibleCard } from "../protocol";
import { useLive } from "../net/live";
import { showCardInfo } from "../store";
import { Card } from "./Card";
import { useCompact } from "./Selection";

/**
 * 기록. PC는 오른쪽 사이드 패널, 좁은 화면은 아래에서 올라오는 모달.
 * 항목마다 관련 카드 그림을 붙이고, 내 일은 옅은 초록, 상대 일은 옅은 빨강 배경, +수치는 초록 · -수치는 빨강.
 */
export function LogPanel({ envelope, open, onClose }: { envelope: PlayEnvelope; open: boolean; onClose: () => void }) {
  const events = useLive((s) => s.events);
  const compact = useCompact();
  // 최신 항목이 위로 온다.
  const entries = useMemo(() => logEntries(events, envelope).reverse(), [events, envelope]);
  const body = (
    <>
      <header className="log-head">
        <h2>기록</h2>
        <span className="log-legend">
          <i className="is-me" /> 나 <i className="is-opp" /> 상대
        </span>
        <button type="button" className="btn-ghost" onClick={onClose}>
          닫기
        </button>
      </header>
      <ol className="log-list">
        {entries.length === 0 && <li className="muted log-empty">아직 기록이 없습니다.</li>}
        {entries.map((entry) => (
          <LogRow key={entry.seq} entry={entry} />
        ))}
      </ol>
    </>
  );
  return (
    <AnimatePresence>
      {open && !compact && (
        <motion.aside
          key="log-side"
          className="log-panel"
          aria-label="기록"
          initial={{ opacity: 0, x: 32 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 32 }}
          transition={{ type: "spring", stiffness: 420, damping: 38 }}
        >
          {body}
        </motion.aside>
      )}
      {open && compact && (
        <motion.div key="log-modal" className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="zone-sheet log-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            {body}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function LogRow({ entry }: { entry: LogEntry }) {
  if (entry.divider) {
    return (
      <li className="log-divider">
        <span>{entry.title}</span>
      </li>
    );
  }
  return (
    <li className={`log-item is-${entry.side}`}>
      {entry.cards.length > 0 && (
        <span className="log-cards">
          {entry.cards.map((card, index) => (
            <LogCardThumb key={index} card={card} seq={entry.seq} index={index} />
          ))}
        </span>
      )}
      <span className="log-text">
        <strong>{entry.title}</strong>
        {entry.detail && <small>{entry.detail}</small>}
      </span>
      {entry.deltas.length > 0 && (
        <span className="log-deltas">
          {entry.deltas.map((delta, index) => (
            <b key={index} className={delta.amount > 0 ? "is-plus" : delta.amount < 0 ? "is-minus" : ""}>
              {delta.label} {delta.amount > 0 ? "+" : ""}
              {delta.amount}
            </b>
          ))}
        </span>
      )}
    </li>
  );
}

/** 기록 속 카드 그림. 누르거나 우클릭하면 카드 정보를 연다. */
function LogCardThumb({ card, seq, index }: { card: LogCard; seq: number; index: number }) {
  const board = {
    hidden: false,
    instance_id: `log-${seq}-${index}`,
    kind: "card",
    owner: card.owner ?? "p1",
    zone: "list",
    face_up: true,
    card_id: card.card_id ?? null,
    code: card.code ?? null,
    name: card.name,
  } as VisibleCard;
  const ref = { owner: board.owner, zone: board.zone, index: 0, instance_id: board.instance_id };
  return <Card card={board} size="mini" detached onClick={() => showCardInfo({ card: board, ref })} />;
}
