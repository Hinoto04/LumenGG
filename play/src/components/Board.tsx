import { AnimatePresence, motion, useAnimate } from "motion/react";
import { useEffect, useMemo, type CSSProperties } from "react";
import type { BoardCard, LegalAction, PlayEnvelope, PlayerState, Side, ZoneName } from "../protocol";
import { PHASE_LABELS, PHASE_ORDER, PILE_ZONES, ZONE_LABELS } from "../labels";
import { cardActions, indexActions, perspective, refKey, showCardInfo, usePlay, type ActionIndex } from "../store";
import { useFx } from "../anim/fx";
import { Card } from "./Card";
import { dragPlan, insideSource, targetAt } from "../dragMoves";
import { isManual, submitAction, useLive } from "../net/live";
import { ClockBadge } from "./Clock";
import { ManualDock, manualStatusText } from "./Manual";
import { useCompact } from "./Selection";
import {
  comboCancelAction,
  comboFirstId,
  decisionCandidates,
  movesOnBoard,
  optionForCard,
  stagedIds,
  toggleDecisionPick,
} from "./Decision";
import { Floats } from "./FxLayer";
import { ZoneDock } from "./ZoneDock";
import { passiveItems } from "../passives";

interface BoardProps {
  envelope: PlayEnvelope;
  onAction: (action: LegalAction) => void;
  /** 명령 결과를 기다리는 중이면 조작을 막는다. */
  busy?: boolean;
}

export function Board({ envelope, onAction, busy }: BoardProps) {
  const { me, opp } = perspective(envelope);
  const actions = useMemo(() => indexActions(envelope.legal_actions), [envelope.legal_actions]);
  const state = envelope.state;
  return (
    <div
      className={`board role-${envelope.role} ${busy ? "is-busy" : ""}`}
      aria-busy={busy || undefined}
      onPointerDown={(event) => {
        // 빈 곳을 누르면 카드 선택을 푼다.
        if (!(event.target as HTMLElement).closest(".card, button")) usePlay.getState().setSelected(null);
      }}
    >
      <OpponentHand player={state.players[opp]} side={opp} />
      <Field side={opp} player={state.players[opp]} actions={actions} envelope={envelope} onAction={onAction} />
      <MidLine envelope={envelope} me={me} actions={actions} />
      <Field side={me} player={state.players[me]} actions={actions} envelope={envelope} onAction={onAction} mine />
      <MyHand side={me} player={state.players[me]} actions={actions} onAction={onAction} />
      <ZoneDock envelope={envelope} actions={actions} onAction={onAction} />
      {isManual(envelope) ? <ManualDock envelope={envelope} /> : <ActionDock envelope={envelope} actions={actions} onAction={onAction} />}
    </div>
  );
}

// ---------------------------------------------------------------------------

/**
 * 카드 누르기·끌기.
 * - 누르기: PC는 선택(위에 사용 버튼, 왼쪽에 정보), 모바일은 확대 보기 모달. 효과 선택 후보는 고르기.
 * - 끌기: 출발 영역 밖으로 나가면 도착 영역(B)과 출발 영역(A)만 남기고 어둡게 덮는다(DragMask).
 *   B에 놓으면 항상 그 영역으로 옮기는 행동을 실행한다(dragMoves.ts).
 */
export function useCardHandlers(side: Side, zone: ZoneName, actions: ActionIndex, onAction: (action: LegalAction) => void) {
  const compact = useCompact();
  const selected = usePlay((s) => s.selected);
  const picks = usePlay((s) => s.decisionPicks);
  const envelope = usePlay((s) => s.envelope);
  const candidates = useMemo(() => (envelope ? decisionCandidates(envelope) : null), [envelope]);
  const staged = useMemo(() => stagedIds(envelope, picks), [envelope, picks]);
  const selectedKey = selected ? refKey(selected.ref) : null;
  return (card: BoardCard, index: number) => {
    const ref = { owner: side, zone, index };
    const key = refKey(ref);
    const select = () => {
      if (compact) usePlay.getState().setInspect({ card, ref });
      else usePlay.getState().setSelected(selectedKey === key ? null : { card, ref });
    };
    const optionId = candidates ? optionForCard(candidates, ref, card)?.id : undefined;
    const cancelCombo = envelope && !card.hidden && card.instance_id === comboFirstId(envelope) ? comboCancelAction(envelope) : null;
    const plan = envelope ? dragPlan(envelope, ref, card, onAction, select) : null;
    const dragHandlers = plan
      ? {
          start: () => {
            usePlay.getState().setSelected(null);
            usePlay.getState().setDrag({ ...plan, active: false });
          },
          move: (point: { x: number; y: number }) => {
            const drag = usePlay.getState().drag;
            if (drag && !drag.active && !insideSource(drag, point)) usePlay.getState().setDrag({ ...drag, active: true });
          },
          end: (point: { x: number; y: number }) => {
            const drag = usePlay.getState().drag;
            usePlay.getState().setDrag(null);
            if (!drag || useLive.getState().busy) return;
            targetAt(drag, point)?.run();
          },
        }
      : undefined;
    if (cancelCombo) {
      // 고른 1콤보 카드: 눌러서(또는 손패로 끌어서) 다시 고른다.
      return { playable: false, selected: false, staged: true, selectKey: key, onClick: () => onAction(cancelCombo), dragHandlers };
    }
    if (optionId && candidates) {
      // 효과 선택의 후보 카드: 누르면 고르고, 도착 존 힌트가 있으면 끌어 놓아도 고른다.
      return {
        playable: !picks.includes(optionId),
        selected: false,
        staged: !card.hidden && staged.has(String(card.instance_id)),
        selectKey: key,
        onClick: () => toggleDecisionPick(optionId, candidates.maximum),
        dragHandlers,
      };
    }
    return {
      playable: cardActions(actions, ref, card).length > 0,
      selected: selectedKey === key,
      selectKey: key,
      onClick: select,
      dragHandlers,
    };
  };
}

function OpponentHand({ player, side }: { player: PlayerState; side: Side }) {
  const cards = player.zones.hand;
  return (
    <div className="opp-hand" data-drop-owner={side} data-drop-zone="hand" aria-label={`상대 손패 ${cards.length}장`}>
      {cards.map((card, index) => (
        <Card
          key={card.hidden ? `${side}-hand-${index}` : String(card.instance_id)}
          card={card}
          size="mini"
          style={{ rotate: (index - (cards.length - 1) / 2) * -4 }}
          // 공개된 상대 손패(시작 패 확인, 예지)는 눌러서도 정보를 본다. onClick이 없으면 버튼이 비활성이 된다.
          onClick={card.hidden ? undefined : () => showCardInfo({ card, ref: { owner: side, zone: "hand", index, instance_id: card.instance_id } })}
          selectKey={`${side}:hand:${index}`}
        />
      ))}
      <span className="count-badge">{cards.length}</span>
    </div>
  );
}

/** 패시브 전부: 카운터는 수치(상한이 있으면 n/상한), 상태는 켜짐·꺼짐(꺼짐은 흐리게) */
function PassiveBadges({ player, manual }: { player: PlayerState; manual: boolean }) {
  const items = passiveItems(player, manual);
  if (!items.length) return null;
  return (
    <span className="passive-badges">
      {items.map((item) => (
        <i
          key={item.key}
          className={`is-${item.kind} ${item.kind === "state" && !item.value ? "is-off" : ""} ${
            item.kind === "counter" && !item.value ? "is-zero" : ""
          } ${item.active ? "is-active" : ""}`}
          title={item.active ? `${item.label} (활성)` : item.label}
        >
          {item.label}
          {item.kind === "counter" && <b>{item.max ? `${item.value}/${item.max}` : String(item.value)}</b>}
          {item.kind === "value" && <b>{String(item.value)}</b>}
        </i>
      ))}
    </span>
  );
}

function Portrait({
  player,
  side,
  active,
  onOpen,
}: {
  player: PlayerState;
  side: Side;
  active: boolean;
  onOpen?: () => void;
}) {
  const hit = useFx((s) => s.shake[side]);
  const [scope, animate] = useAnimate<HTMLDivElement>();
  useEffect(() => {
    if (hit && scope.current) void animate(scope.current, { x: [0, -9, 8, -5, 3, 0] }, { duration: 0.42 });
  }, [hit, animate, scope]);
  const character = player.character ?? {};
  const maxHp = Number(player.initial_hp ?? 5000) || 5000;
  const hpRatio = Math.max(0, Math.min(1, player.hp / maxHp));
  const color = character.color ? String(character.color) : undefined;
  const face = character.icon_img || character.img;
  return (
    <div
      ref={scope}
      className={`portrait side-${side} ${active ? "is-active" : ""} ${onOpen ? "is-clickable" : ""}`}
      style={{ "--char-color": color } as CSSProperties}
      role={onOpen ? "button" : undefined}
      tabIndex={onOpen ? 0 : undefined}
      aria-label={onOpen ? "HP·FP·패시브 조정" : undefined}
      onClick={onOpen}
      onKeyDown={onOpen ? (event) => (event.key === "Enter" || event.key === " ") && onOpen() : undefined}
    >
      {hit && (
        <motion.i
          key={hit}
          className="portrait-hit"
          initial={{ opacity: 0.75 }}
          animate={{ opacity: 0 }}
          transition={{ duration: 0.6 }}
        />
      )}
      <Floats side={side} />
      {character.img && <img className="portrait-body" src={String(character.img)} alt="" draggable={false} />}
      <div className="portrait-face">
        {face ? (
          <img src={String(face)} alt="" draggable={false} />
        ) : (
          <span>{String(character.name ?? side).slice(0, 1)}</span>
        )}
      </div>
      <div className="portrait-info">
        <span className="portrait-name">{String(character.name ?? player.name)}</span>
        <div className="hp-bar" aria-label={`HP ${player.hp}`}>
          <motion.i animate={{ width: `${hpRatio * 100}%` }} transition={{ duration: 0.5 }} />
          <b>{player.hp}</b>
        </div>
        <span className="fp" title="FP">
          FP <b>{player.fp}</b>
        </span>
        <PassiveBadges player={player} manual={!!onOpen} />
      </div>
    </div>
  );
}

interface FieldProps {
  side: Side;
  player: PlayerState;
  actions: ActionIndex;
  envelope: PlayEnvelope;
  onAction: (action: LegalAction) => void;
  mine?: boolean;
}

function Field({ side, player, actions, envelope, onAction, mine }: FieldProps) {
  const battleHandlers = useCardHandlers(side, "battle", actions, onAction);
  const listHandlers = useCardHandlers(side, "list", actions, onAction);
  const priority = envelope.state.priority_player === side;
  return (
    <section className={`field ${mine ? "field-me" : "field-opp"}`} aria-label={mine ? "내 필드" : "상대 필드"}>
      <Portrait
        player={player}
        side={side}
        active={priority}
        onOpen={isManual(envelope) ? () => usePlay.getState().setPlayerSheet(side) : undefined}
      />
      <div className="battle-zone" data-drop-owner={side} data-drop-zone="battle" aria-label="배틀존">
        <AnimatePresence>
          {player.zones.battle.map((card, index) => (
            <Card
              key={card.hidden ? `${side}-battle-${index}` : String(card.instance_id)}
              card={card}
              enter={!mine || envelope.role === "viewer" ? "flip" : undefined}
              {...battleHandlers(card, index)}
            />
          ))}
        </AnimatePresence>
        {!player.zones.battle.length && <span className="zone-hint">배틀존</span>}
      </div>
      <div className="field-side">
        <div className="list-zone" data-drop-owner={side} data-drop-zone="list" aria-label="리스트">
          <span className="zone-title">리스트</span>
          <div className="list-cards" style={listGrid(player.zones.list.length)}>
            {player.zones.list.map((card, index) => (
              <Card
                key={card.hidden ? `${side}-list-${index}` : String(card.instance_id)}
                card={card}
                size="mini"
                {...listHandlers(card, index)}
              />
            ))}
          </div>
        </div>
        <Piles side={side} player={player} actions={actions} />
      </div>
    </section>
  );
}

/**
 * 리스트는 겹치지 않게 여러 줄로 놓는다: 6장까지 1줄, 12장까지 2줄, 그 이상 3줄.
 * 줄이 늘면 카드를 조금 줄이고, 그래도 폭이 모자라면 --list-len 안에 맞춘다(styles.css).
 */
function listGrid(count: number): CSSProperties {
  const rows = count <= 6 ? 1 : count <= 12 ? 2 : 3;
  const cols = Math.max(1, Math.ceil(count / rows));
  return { "--rows": rows, "--cols": cols } as CSSProperties;
}

function Piles({ side, player, actions }: { side: Side; player: PlayerState; actions: ActionIndex }) {
  const setOpenZone = usePlay((s) => s.setOpenZone);
  const envelope = usePlay((s) => s.envelope);
  const picks = usePlay((s) => s.decisionPicks);
  const candidates = useMemo(() => (envelope ? decisionCandidates(envelope) : null), [envelope]);
  const staged = useMemo(() => stagedIds(envelope, picks), [envelope, picks]);
  return (
    <div className="piles">
      {PILE_ZONES.map((zone) => {
        const cards = player.zones[zone];
        const playable = cards.some((card, index) => {
          const ref = { owner: side, zone, index };
          return cardActions(actions, ref, card).length > 0 || (!!candidates && !!optionForCard(candidates, ref, card));
        });
        const hasStaged = cards.some((card) => !card.hidden && staged.has(String(card.instance_id)));
        const top = cards[cards.length - 1];
        return (
          <button
            key={zone}
            type="button"
            className={`pile ${cards.length ? "" : "is-empty"} ${playable ? "is-playable" : ""} ${hasStaged ? "is-staged" : ""}`}
            data-drop-owner={side}
            data-drop-zone={zone}
            onClick={() => setOpenZone({ owner: side, zone })}
            aria-label={`${ZONE_LABELS[zone]} ${cards.length}장`}
          >
            <span className={`pile-thumb ${top && !top.hidden ? "is-face" : ""}`}>{cards.length}</span>
            <span className="pile-label">{ZONE_LABELS[zone]}</span>
          </button>
        );
      })}
    </div>
  );
}

function MidLine({ envelope, me, actions }: { envelope: PlayEnvelope; me: Side; actions: ActionIndex }) {
  const phase = envelope.state.phase;
  const playing = useFx((s) => s.playing);
  return (
    <div className="midline">
      <span className="turn">턴 {envelope.state.turn}</span>
      <ol className="phases">
        {PHASE_ORDER.map((item) => (
          <li key={item} className={item === phase ? "is-current" : ""}>
            {PHASE_LABELS[item]}
          </li>
        ))}
      </ol>
      <span className="status-line">
        {playing ? "진행 중…" : isManual(envelope) ? manualStatusText(envelope) : statusText(envelope, me, actions)}
      </span>
      <ClockBadge envelope={envelope} />
    </div>
  );
}

function statusText(envelope: PlayEnvelope, me: Side, actions: ActionIndex): string {
  const status = envelope.engine_status;
  if (status.status === "finished") {
    if (!status.winner) return "무승부";
    return envelope.role === "viewer" ? `${status.winner.toUpperCase()} 승리` : status.winner === me ? "승리!" : "패배";
  }
  if (envelope.role === "viewer") return "관전 중";
  if (envelope.pending_decision && envelope.pending_decision.owner !== me) return "상대가 선택 중입니다";
  if (actions.decision) return "효과를 선택하세요";
  if (actions.byCard.size) {
    const step = status.step;
    if (step === "ready_actions") return "레디할 카드를 고르세요";
    if (step === "get_actions")
      return actions.primary.length ? "획득할 카드를 고르세요" : "겟: 카드 1장을 가져와야 합니다(손패가 상한 미만)";
    if (step === "combo") return "콤보를 이어가세요";
    if (step === "catch") return "캐치할 카드를 고르세요";
    return "사용할 카드를 고르세요";
  }
  if (actions.primary.length) return "준비가 끝나면 진행하세요";
  return "상대를 기다리는 중";
}

function MyHand({
  side,
  player,
  actions,
  onAction,
}: {
  side: Side;
  player: PlayerState;
  actions: ActionIndex;
  onAction: (action: LegalAction) => void;
}) {
  const handlers = useCardHandlers(side, "hand", actions, onAction);
  const cards = player.zones.hand;
  const limit = player.character?.hand_limit;
  return (
    <div className="my-hand" data-drop-owner={side} data-drop-zone="hand" aria-label="내 손패">
      <div className="hand-cards" style={{ "--n": cards.length } as CSSProperties}>
        <AnimatePresence>
          {cards.map((card, index) => {
            const offset = index - (cards.length - 1) / 2;
            return (
              <Card
                key={card.hidden ? `${side}-hand-${index}` : String(card.instance_id)}
                card={card}
                size="hand"
                style={{ rotate: offset * 2, marginTop: Math.abs(offset) * 5 }}
                {...handlers(card, index)}
              />
            );
          })}
        </AnimatePresence>
      </div>
      <span className="hand-count">
        손패 {cards.length}
        {limit != null ? ` / ${limit}` : ""}
      </span>
    </div>
  );
}

function ActionDock({
  envelope,
  actions,
  onAction,
}: {
  envelope: PlayEnvelope;
  actions: ActionIndex;
  onAction: (action: LegalAction) => void;
}) {
  const setDecisionCollapsed = usePlay((s) => s.setDecisionCollapsed);
  const decisionPicks = usePlay((s) => s.decisionPicks);
  const decisionPicksCount = decisionPicks.length;
  const boardMoves = useMemo(() => {
    const candidates = decisionCandidates(envelope);
    return movesOnBoard([...candidates.options.values()]) ? candidates : null;
  }, [envelope]);
  const boardReady =
    !!boardMoves && decisionPicksCount >= boardMoves.minimum && decisionPicksCount <= boardMoves.maximum;
  const playing = useFx((s) => s.playing);
  const primary = actions.primary[0];
  const waiting = envelope.role !== "viewer" && !primary && !actions.byCard.size && !actions.decision;
  return (
    <div className="action-dock">
      {actions.secondary.map((action) => (
        <button key={action.action_id} type="button" className="btn-secondary" onClick={() => onAction(action)}>
          {action.label}
        </button>
      ))}
      {actions.decision && (
        <button
          type="button"
          className="btn-primary is-decision"
          onClick={() =>
            boardReady && actions.decision
              ? submitAction(actions.decision, { selected: decisionPicks })
              : setDecisionCollapsed(false)
          }
        >
          {boardMoves
            ? boardReady
              ? `${decisionPicksCount}장 옮김 · 확정`
              : "목록으로 보기"
            : decisionPicksCount
              ? `${decisionPicksCount}개 고름 · 확정하기`
              : "선택하기"}
        </button>
      )}
      {primary && (
        <button
          type="button"
          className={`btn-primary ${actions.byCard.size ? "is-quiet" : ""}`}
          onClick={() => onAction(primary)}
        >
          {primary.label}
        </button>
      )}
      {waiting && envelope.engine_status.status === "running" && (
        <span className="btn-primary is-waiting">{playing ? "진행 중…" : "상대 차례"}</span>
      )}
    </div>
  );
}
