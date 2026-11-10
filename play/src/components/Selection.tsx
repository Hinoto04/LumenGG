import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useState } from "react";
import { isManual } from "../net/live";
import type { LegalAction, PlayEnvelope } from "../protocol";
import { cardActions, indexActions, refKey, usePlay } from "../store";
import { Card } from "./Card";
import { ManualCardActions } from "./Manual";
import { actionVerb, CardDetails } from "./Overlays";

/**
 * PC의 카드 선택(마스터 듀얼과 비슷하게):
 * - 한 번 누르면 카드 위에 사용 버튼(SelectionPopover)이 뜨고
 * - 화면 왼쪽 사이드 패널(CardSidePanel)에 카드 정보가 나온다.
 * 좁은 화면(모바일)은 대신 확대 보기 모달(CardInspector)을 연다.
 */

const COMPACT_QUERY = "(orientation: portrait), (max-width: 760px)";

export function useCompact(): boolean {
  const [compact, setCompact] = useState(() => window.matchMedia(COMPACT_QUERY).matches);
  useEffect(() => {
    const query = window.matchMedia(COMPACT_QUERY);
    const update = () => setCompact(query.matches);
    query.addEventListener("change", update);
    return () => query.removeEventListener("change", update);
  }, []);
  return compact;
}

/** 선택한 카드가 상태가 바뀌어 다른 카드가 되면 선택을 푼다. */
function useSelectedStillValid(envelope: PlayEnvelope) {
  const selected = usePlay((s) => s.selected);
  useEffect(() => {
    if (!selected) return;
    const current = envelope.state.players[selected.ref.owner]?.zones[selected.ref.zone]?.[selected.ref.index];
    const same =
      current &&
      current.hidden === selected.card.hidden &&
      (current.hidden || current.instance_id === (selected.card as { instance_id?: string }).instance_id);
    if (!same) usePlay.getState().setSelected(null);
  }, [envelope, selected]);
}

function useAnchor(key: string | null) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useLayoutEffect(() => {
    if (!key) {
      setRect(null);
      return;
    }
    let frame = 0;
    const tick = () => {
      const node = document.querySelector(`[data-select-key="${key}"]`);
      setRect((previous) => {
        const next = node?.getBoundingClientRect() ?? null;
        if (!next || !previous) return next;
        return Math.abs(next.x - previous.x) < 0.5 && Math.abs(next.y - previous.y) < 0.5 ? previous : next;
      });
      frame = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(frame);
  }, [key]);
  return rect;
}

export function SelectionPopover({ envelope, onAction }: { envelope: PlayEnvelope; onAction: (action: LegalAction) => void }) {
  useSelectedStillValid(envelope);
  const selected = usePlay((s) => s.selected);
  const key = selected ? refKey(selected.ref) : null;
  const rect = useAnchor(key);
  const close = () => usePlay.getState().setSelected(null);
  const actions = selected ? cardActions(indexActions(envelope.legal_actions), selected.ref, selected.card) : [];
  const manual = isManual(envelope);
  const visible = !!selected && !!rect && (actions.length > 0 || manual);
  // 카드 위쪽 가운데. 화면 위에 붙으면 카드 아래로 내린다.
  const above = rect ? rect.top > 160 : true;
  return (
    <AnimatePresence>
      {visible && selected && rect && (
        <motion.div
          key={key}
          className={`selection-popover ${above ? "is-above" : "is-below"}`}
          style={{
            left: Math.min(window.innerWidth - 12, Math.max(12, rect.left + rect.width / 2)),
            top: above ? rect.top - 8 : rect.bottom + 8,
          }}
          initial={{ opacity: 0, y: above ? 8 : -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.12 }}
        >
          {actions.map((action) => (
            <button
              key={action.action_id}
              type="button"
              className="btn-primary"
              onClick={() => {
                close();
                onAction(action);
              }}
            >
              {actionVerb(action)}
            </button>
          ))}
          {manual && <ManualCardActions envelope={envelope} card={selected.card} zone={selected.ref.zone} onDone={close} />}
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function CardSidePanel() {
  const selectedCard = usePlay((s) => s.selected);
  const peek = usePlay((s) => s.peek);
  // 우클릭으로 띄운 카드가 있으면 그쪽을 먼저 보여 준다.
  const selected = peek ?? selectedCard;
  return (
    <AnimatePresence>
      {selected && (
        <motion.aside
          key={`${peek ? "peek" : "sel"}:${refKey(selected.ref)}`}
          className="card-side-panel"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ duration: 0.15 }}
          aria-label="카드 정보"
        >
          <Card card={selected.card} size="large" detached />
          <div className="inspector-body">
            <CardDetails card={selected.card} zone={selected.ref.zone} />
            <button
              type="button"
              className="btn-ghost"
              onClick={() => (peek ? usePlay.getState().setPeek(null) : usePlay.getState().setSelected(null))}
            >
              닫기
            </button>
          </div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
