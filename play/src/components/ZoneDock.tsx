import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, type CSSProperties } from "react";
import { ZONE_LABELS } from "../labels";
import type { LegalAction, PlayEnvelope, Side, ZoneName } from "../protocol";
import { perspective, usePlay, type ActionIndex } from "../store";
import { Card } from "./Card";
import { useCardHandlers } from "./Board";
import { decisionCandidates, movesOnBoard } from "./Decision";

/** 장 수만 보이는 더미 */
const DOCK_ZONES = new Set<ZoneName>(["lumen", "break", "ultimate", "side"]);
/** 끄는 동안에만 펼칠 때, 도착 더미가 이보다 많으면(수동 모드) 펼치지 않는다 */
const MAX_DRAG_DOCKS = 2;

interface DockZone {
  owner: Side;
  zone: ZoneName;
  role: "from" | "to";
}

/**
 * 카드를 더미(루멘·브레이크·얼티밋·사이드)로 옮기거나 더미에서 꺼내야 할 때 그 더미의 카드를 펼쳐 보여 준다.
 * 펼친 패널도 그 영역의 놓을 자리다(더미 버튼에 놓아도 된다).
 * - 카드 옮기기 선택 중에는 계속, 그 밖에는 카드를 끄는 동안 도착 더미가 있을 때만 펼친다.
 * - PC는 왼쪽 빈 곳(위아래로), 모바일은 상대 필드 아래쪽(좌우로)에 더미마다 같은 크기의 패널을 따로 놓는다.
 *   From/To 테두리와 이름표가 겹치지 않게 패널 사이를 띄운다. "가리기"로 접을 수 있다.
 */
export function ZoneDock({
  envelope,
  actions,
  onAction,
}: {
  envelope: PlayEnvelope;
  actions: ActionIndex;
  onAction: (action: LegalAction) => void;
}) {
  const drag = usePlay((s) => s.drag);
  const hidden = usePlay((s) => s.dockHidden);
  const setHidden = usePlay((s) => s.setDockHidden);
  const { me } = perspective(envelope);

  const decision = useMemo(() => {
    const candidates = decisionCandidates(envelope);
    const options = [...candidates.options.values()];
    if (!candidates.action || !movesOnBoard(options)) return null;
    return { id: String(envelope.pending_decision?.id ?? candidates.action.action_id), options };
  }, [envelope]);

  // 새 선택이 오면 다시 펼친다.
  const decisionId = decision?.id;
  useEffect(() => {
    if (decisionId) setHidden(false);
  }, [decisionId, setHidden]);

  const zones = useMemo(() => {
    const found = new Map<string, DockZone>();
    const add = (owner: Side, zone: ZoneName, role: DockZone["role"]) => {
      if (DOCK_ZONES.has(zone) && !found.has(`${owner}:${zone}`)) found.set(`${owner}:${zone}`, { owner, zone, role });
    };
    for (const option of decision?.options ?? []) {
      const card = option.ui.card!;
      add(card.owner, card.zone, "from");
      add(card.owner, option.ui.to_zone!, "to");
    }
    if (drag?.active) {
      const piles = drag.targets.filter((target) => DOCK_ZONES.has(target.zone));
      if (piles.length <= MAX_DRAG_DOCKS) piles.forEach((target) => add(target.owner, target.zone, "to"));
    }
    return [...found.values()];
  }, [decision, drag]);

  const title = (zone: DockZone) => `${zone.owner === me ? "내" : "상대"} ${ZONE_LABELS[zone.zone]}`;

  return (
    <AnimatePresence>
      {zones.length > 0 && hidden && (
        <motion.button
          key="dock-tab"
          type="button"
          className="zone-dock-tab"
          initial={{ opacity: 0, x: -20 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0 }}
          onClick={() => setHidden(false)}
        >
          펼치기 · {zones.map(title).join(", ")}
        </motion.button>
      )}
      {zones.length > 0 && !hidden && (
        <motion.aside
          key="dock"
          className={`zone-dock ${drag?.active ? "is-dragging" : ""}`}
          // 더미마다 따로 같은 크기의 패널(겹치지 않게)
          style={{ "--docks": zones.length } as CSSProperties}
          aria-label="펼친 더미"
          initial={{ opacity: 0, x: -24 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -24 }}
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
        >
          <header className="zone-dock-head">
            <span>더미 펼쳐 보기</span>
            <button type="button" className="btn-ghost" onClick={() => setHidden(true)}>
              가리기
            </button>
          </header>
          {zones.map((zone) => (
            <DockSection
              key={`${zone.owner}:${zone.zone}`}
              zone={zone}
              title={title(zone)}
              envelope={envelope}
              actions={actions}
              onAction={onAction}
            />
          ))}
        </motion.aside>
      )}
    </AnimatePresence>
  );
}

function DockSection({
  zone,
  title,
  envelope,
  actions,
  onAction,
}: {
  zone: DockZone;
  title: string;
  envelope: PlayEnvelope;
  actions: ActionIndex;
  onAction: (action: LegalAction) => void;
}) {
  const handlers = useCardHandlers(zone.owner, zone.zone, actions, onAction);
  const cards = envelope.state.players[zone.owner].zones[zone.zone];
  return (
    <section className={`zone-dock-section is-${zone.role}`} data-drop-owner={zone.owner} data-drop-zone={zone.zone}>
      <h3>
        {title} <span className="muted">{cards.length}장</span>
      </h3>
      <div className="zone-dock-cards">
        {cards.map((card, index) => (
          <Card
            key={card.hidden ? `dock-${zone.owner}-${zone.zone}-${index}` : String(card.instance_id)}
            card={card}
            size="mini"
            {...handlers(card, index)}
          />
        ))}
        {!cards.length && <span className="zone-dock-empty">{zone.role === "to" ? "여기에 놓으세요" : "비어 있음"}</span>}
      </div>
    </section>
  );
}
