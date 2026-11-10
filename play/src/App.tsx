import { LayoutGroup } from "motion/react";
import { useCallback, useEffect, useMemo } from "react";
import { Board } from "./components/Board";
import { DecisionPanel, stageCombo, stageDecision, type SubmitAction } from "./components/Decision";
import { DecisionFrames } from "./components/DecisionFrames";
import { DragMask } from "./components/DragMask";
import { FxLayer } from "./components/FxLayer";
import { PlayerSheet } from "./components/Manual";
import { CardSidePanel, SelectionPopover, useCompact } from "./components/Selection";
import { GameOver, LiveBar } from "./components/GameChrome";
import { PauseNotice, RewindPrompt } from "./components/SystemUi";
import { CardInspector, Notice, ZoneSheet } from "./components/Overlays";
import { isEmbedded } from "./dev/DevicePreview";
import { FixtureBar } from "./dev/FixtureBar";
import { Lobby } from "./Lobby";
import type { AppMode } from "./mode";
import { connectLive, isPreparing, submitAction, useLive } from "./net/live";
import { PreparationScreen } from "./prep/PreparationScreen";
import { indexActions, perspective, usePlay } from "./store";

export function App({ mode }: { mode: AppMode }) {
  if (mode.kind === "lobby") return <Lobby />;
  return <GameScreen mode={mode} />;
}

function GameScreen({ mode }: { mode: Exclude<AppMode, { kind: "lobby" }> }) {
  const envelope = usePlay((s) => s.envelope);
  const picks = usePlay((s) => s.decisionPicks);
  // 카드를 옮기는 선택: 고른 카드를 확정 전에 도착 존으로 옮겨 보여 준다.
  // 콤보: 고른 1콤보 카드를 2콤보를 고를 때까지 배틀 존에 놓아 보여 준다.
  const board = useMemo(() => (envelope ? stageCombo(stageDecision(envelope, picks)) : null), [envelope, picks]);
  const flash = usePlay((s) => s.flash);
  const busy = useLive((s) => s.busy);
  const compact = useCompact();
  const live = mode.kind === "live";

  useEffect(() => {
    if (mode.kind !== "live") return;
    return connectLive(mode.target);
  }, [mode]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const { setInspect, setOpenZone, setPlayerSheet, setSelected } = usePlay.getState();
      setSelected(null); // 우클릭 정보(peek)도 함께 닫힌다
      setInspect(null);
      setOpenZone(null);
      setPlayerSheet(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const onSubmit: SubmitAction = useCallback(
    (action, selections) => {
      if (live) {
        submitAction(action, selections);
        return;
      }
      console.info("[play] action", action.type, action.action_id, action.payload, selections);
      flash(`픽스처 모드: "${action.label}" 행동은 보내지 않습니다`);
    },
    [flash, live],
  );
  const onAction = useCallback((action: Parameters<SubmitAction>[0]) => onSubmit(action), [onSubmit]);

  const decision = useMemo(() => {
    if (!envelope) return null;
    const action = indexActions(envelope.legal_actions).decision;
    const pending = envelope.pending_decision;
    return action && (!pending || pending.owner === perspective(envelope).me) ? action : null;
  }, [envelope]);

  return (
    <div className="app">
      {mode.kind === "fixtures" && import.meta.env.DEV && <FixtureBar headless={isEmbedded()} />}
      {live && <LiveBar envelope={envelope} onSubmit={onSubmit} />}
      {envelope && isPreparing(envelope) ? (
        <PreparationScreen key={`${envelope.preparation?.game_number}`} envelope={envelope} />
      ) : envelope ? (
        <LayoutGroup>
          {/* 시점이 바뀌면 같은 카드가 다른 진영으로 옮겨 가므로 보드를 새로 그린다 */}
          <Board key={envelope.role} envelope={board ?? envelope} onAction={onAction} busy={busy} />
          {decision && <DecisionPanel envelope={envelope} action={decision} busy={busy} onSubmit={onSubmit} />}
          <DecisionFrames envelope={envelope} />
          <DragMask />
          {!compact && <CardSidePanel />}
          {!compact && <SelectionPopover envelope={envelope} onAction={onAction} />}
          <FxLayer me={perspective(envelope).me} />
          <PauseNotice envelope={envelope} onSubmit={onSubmit} />
          <RewindPrompt envelope={envelope} onSubmit={onSubmit} />
          <CardInspector envelope={envelope} onAction={onAction} />
          <ZoneSheet envelope={board ?? envelope} />
          <PlayerSheet envelope={envelope} />
        </LayoutGroup>
      ) : (
        <p className="loading">불러오는 중…</p>
      )}
      {live && <GameOver envelope={envelope} />}
      <Notice />
    </div>
  );
}
