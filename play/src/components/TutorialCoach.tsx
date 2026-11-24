import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useState, type CSSProperties } from "react";
import { create } from "zustand";
import { useFx } from "../anim/fx";
import { t } from "../i18n";
import type { CardRef, LegalAction, PlayEnvelope, TutorialFocus, TutorialView } from "../protocol";
import { usePlay } from "../store";
import { useCompact } from "./Selection";

/**
 * 튜토리얼 코치 레이어(docs/TUTORIAL.md 5절).
 *
 * 서버가 보낸 envelope.tutorial의 메시지를 차례로 보여 준다. "다음"은 화면에서만 넘긴다.
 * 화면을 어둡게 덮고 focus 대상만 구멍을 내 비춘다. 마지막 메시지가 행동(action)을 가리키면
 * 구멍 부분은 아래 보드로 눌림이 통과한다. 허용되지 않은 행동은 서버가 이미 legal_actions에서 뺐다.
 * 연출(배틀 공개·판정)이 끝난 뒤에 말풍선을 띄운다.
 */

const SYSTEM_ACTIONS = new Set(["concede", "pause_clock", "resume_clock"]);
const PROGRESS_KEY = "lumen-play-tutorial";
const PAD = 10;

interface TutorialStore {
  /** 완료 메시지를 다 보았다(그 뒤에 완료 화면을 띄운다) */
  finishSeen: boolean;
  setFinishSeen: (seen: boolean) => void;
}

export const useTutorial = create<TutorialStore>((set) => ({
  finishSeen: false,
  setFinishSeen: (finishSeen) => set({ finishSeen }),
}));

/** 이 기기에서 마친 단원(로비의 "다시 하기" 표시용) */
export function completedLessons(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(PROGRESS_KEY) || "{}") as Record<string, string>;
  } catch {
    return {};
  }
}

function rememberCompleted(lesson: string) {
  try {
    localStorage.setItem(PROGRESS_KEY, JSON.stringify({ ...completedLessons(), [lesson]: new Date().toISOString() }));
  } catch {
    // 저장소를 못 쓰면 기록만 남기지 않는다.
  }
}

export function tutorialOf(envelope: PlayEnvelope | null): TutorialView | null {
  return envelope?.role === "p1" && envelope.tutorial ? envelope.tutorial : null;
}

function playableActions(envelope: PlayEnvelope): LegalAction[] {
  return envelope.legal_actions.filter((action) => !SYSTEM_ACTIONS.has(action.type));
}

function refSelector(ref: Pick<CardRef, "owner" | "zone" | "index">): string {
  return `[data-select-key="${ref.owner}:${ref.zone}:${ref.index}"]`;
}

/** focus가 가리키는 화면 요소들의 CSS 선택자 */
function focusSelectors(focus: TutorialFocus | null, envelope: PlayEnvelope): string[] {
  if (!focus) return [];
  switch (focus.kind) {
    case "card":
      return [refSelector(focus.card)];
    case "zone": {
      const [owner, zone] = focus.zone.split(".");
      return [`[data-drop-owner="${owner}"][data-drop-zone="${zone}"]`];
    }
    case "hud":
      return [`[data-tutorial="${focus.hud}"]`];
    case "action":
      return playableActions(envelope).flatMap((action) =>
        action.ui.kind === "card" && action.ui.cards.length
          ? action.ui.cards.map(refSelector)
          : action.ui.kind === "decision"
            ? [".action-dock .is-decision"]
            : [".action-dock .btn-primary:not(.is-waiting)"],
      );
    default:
      return [];
  }
}

interface Box {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

function unionRect(selectors: string[]): Box | null {
  let box: Box | null = null;
  for (const selector of selectors) {
    document.querySelectorAll(selector).forEach((element) => {
      const rect = element.getBoundingClientRect();
      if (!rect.width && !rect.height) return;
      box = box
        ? {
            left: Math.min(box.left, rect.left),
            top: Math.min(box.top, rect.top),
            right: Math.max(box.right, rect.right),
            bottom: Math.max(box.bottom, rect.bottom),
          }
        : { left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom };
    });
  }
  return box;
}

function sameBox(a: Box | null, b: Box | null): boolean {
  if (!a || !b) return a === b;
  return (
    Math.abs(a.left - b.left) < 1 && Math.abs(a.top - b.top) < 1 && Math.abs(a.right - b.right) < 1 && Math.abs(a.bottom - b.bottom) < 1
  );
}

/** 대상 위치를 따라간다(카드 애니메이션·화면 크기 변화). */
function useFocusBox(selectors: string[], active: boolean): Box | null {
  const [box, setBox] = useState<Box | null>(null);
  const key = selectors.join("|");
  useLayoutEffect(() => {
    if (!active || !selectors.length) {
      setBox(null);
      return;
    }
    let frame = 0;
    let last: Box | null = null;
    const tick = () => {
      const next = unionRect(selectors);
      if (!sameBox(next, last)) {
        last = next;
        setBox(next);
      }
      frame = window.setTimeout(tick, 200);
    };
    tick();
    return () => window.clearTimeout(frame);
    // selectors는 key로 비교한다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, active]);
  return box;
}

function Progress({ view, onQuit }: { view: TutorialView; onQuit: (() => void) | null }) {
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="tutorial-progress">
      <span className="tutorial-title">
        {t("튜토리얼")} · {view.title}
      </span>
      <ol aria-label={t("{n} / {total} 단계", { n: Math.min(view.step + 1, view.steps), total: view.steps })}>
        {Array.from({ length: view.steps }, (_, index) => (
          <li key={index} className={index < view.step ? "is-done" : index === view.step ? "is-current" : ""} />
        ))}
      </ol>
      {onQuit && (
        <button
          type="button"
          className="btn-ghost tutorial-quit"
          onClick={() => (confirming ? onQuit() : setConfirming(true))}
          onBlur={() => setConfirming(false)}
        >
          {confirming ? t("정말 그만둘까요?") : t("그만두기")}
        </button>
      )}
    </div>
  );
}

export function TutorialCoach({ envelope, onAction }: { envelope: PlayEnvelope; onAction: (action: LegalAction) => void }) {
  const view = tutorialOf(envelope);
  const playing = useFx((s) => s.playing);
  const dragging = usePlay((s) => !!s.drag?.active);
  const choosing = usePlay((s) => !!s.selected || !!s.inspect);
  const finishSeen = useTutorial((s) => s.finishSeen);
  const setFinishSeen = useTutorial((s) => s.setFinishSeen);
  const compact = useCompact();
  const [index, setIndex] = useState(0);
  const stepKey = view ? `${view.status}:${view.step_id}` : "";

  // 단계가 바뀌면 그 단계의 첫 메시지부터.
  useEffect(() => setIndex(0), [stepKey]);
  useEffect(() => {
    if (view?.status === "completed") rememberCompleted(view.lesson);
  }, [view?.status, view?.lesson]);

  const messages = view?.messages ?? [];
  const message = messages[Math.min(index, messages.length - 1)] ?? null;
  const last = index >= messages.length - 1;
  const playable = useMemo(() => playableActions(envelope), [envelope]);
  const actionStep = message?.focus?.kind === "action";
  const visible =
    !!view &&
    !!message &&
    !playing &&
    !dragging &&
    view.status !== "ended" &&
    !(view.status === "completed" && finishSeen);
  const selectors = useMemo(
    () => (message ? focusSelectors(actionStep && !playable.length ? null : message.focus, envelope) : []),
    [message, actionStep, playable.length, envelope],
  );
  const box = useFocusBox(selectors, visible);
  const [, setViewport] = useState(0);
  useEffect(() => {
    const onResize = () => setViewport((n) => n + 1);
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  if (!view) return null;
  const concede = envelope.legal_actions.find((action) => action.type === "concede") ?? null;
  const quit = view.status === "running" && concede ? () => onAction(concede) : null;
  if (!visible || !message) return <Progress view={view} onQuit={quit} />;

  const failed = view.status === "failed";
  // 행동 메시지: 비춘 곳은 눌러서 바로 해 본다("다음" 대신). 행동이 아직 없으면(상대 차례) 기다린다.
  const passThrough = last && actionStep && playable.length > 0 && view.status === "running";
  const waitingOpponent = last && actionStep && !playable.length && view.status === "running";
  // 카드를 골라 사용 버튼(선택 팝오버)·카드 정보가 뜨면 그 아래로 내려가고 말풍선을 잠시 숨긴다.
  const yieldToSelection = passThrough && choosing;
  const next = () => {
    if (!last) setIndex(index + 1);
    else if (view.status === "completed") setFinishSeen(true);
  };
  const hole = box
    ? { x: box.left - PAD, y: box.top - PAD, w: box.right - box.left + PAD * 2, h: box.bottom - box.top + PAD * 2 }
    : null;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const bubbleWidth = Math.min(380, width - 32);
  let bubbleStyle: CSSProperties;
  if (compact || !hole) {
    bubbleStyle = hole && hole.y + hole.h / 2 > height * 0.55 ? { top: 16 + 44, left: 16, right: 16 } : { bottom: 16, left: 16, right: 16 };
    if (!compact) bubbleStyle = { ...bubbleStyle, left: (width - bubbleWidth) / 2, right: undefined, width: bubbleWidth };
  } else {
    const left = Math.max(16, Math.min(width - bubbleWidth - 16, hole.x + hole.w / 2 - bubbleWidth / 2));
    bubbleStyle =
      hole.y + hole.h + 200 < height
        ? { top: hole.y + hole.h + 12, left, width: bubbleWidth }
        : { bottom: height - hole.y + 12, left, width: bubbleWidth };
  }

  return (
    <>
      <Progress view={view} onQuit={quit} />
      <div className={`tutorial-coach ${passThrough ? "is-pass-through" : ""} ${yieldToSelection ? "is-yield" : ""}`}>
        {!waitingOpponent && (
          <svg className="tutorial-dim" width={width} height={height} aria-hidden="true">
            <path
              fillRule="evenodd"
              d={
                `M0 0H${width}V${height}H0Z` +
                (hole
                  ? `M${hole.x + 8} ${hole.y}H${hole.x + hole.w - 8}Q${hole.x + hole.w} ${hole.y} ${hole.x + hole.w} ${hole.y + 8}` +
                    `V${hole.y + hole.h - 8}Q${hole.x + hole.w} ${hole.y + hole.h} ${hole.x + hole.w - 8} ${hole.y + hole.h}` +
                    `H${hole.x + 8}Q${hole.x} ${hole.y + hole.h} ${hole.x} ${hole.y + hole.h - 8}V${hole.y + 8}Q${hole.x} ${hole.y} ${hole.x + 8} ${hole.y}Z`
                  : "")
              }
            />
            {hole && <rect className="tutorial-ring" x={hole.x} y={hole.y} width={hole.w} height={hole.h} rx={8} />}
          </svg>
        )}
        <AnimatePresence mode="wait">
          {!yieldToSelection && (
          <motion.div
            key={`${stepKey}:${index}`}
            className={`tutorial-bubble ${compact ? "is-sheet" : ""} ${failed ? "is-failed" : ""}`}
            style={bubbleStyle}
            role="dialog"
            aria-live="polite"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <p>{message.text}</p>
            <div className="tutorial-bubble-foot">
              {messages.length > 1 && (
                <span className="tutorial-count">
                  {Math.min(index + 1, messages.length)} / {messages.length}
                </span>
              )}
              {failed ? (
                <a className="btn-primary" href={location.pathname}>
                  {t("로비로")}
                </a>
              ) : passThrough ? (
                <span className="tutorial-hint">{t("빛나는 카드를 눌러 보세요")}</span>
              ) : waitingOpponent ? (
                <span className="tutorial-hint">{t("상대를 기다리는 중")}</span>
              ) : (
                <button type="button" className="btn-primary" onClick={next} autoFocus>
                  {last && view.status === "completed" ? t("마치기") : t("다음")}
                </button>
              )}
            </div>
          </motion.div>
          )}
        </AnimatePresence>
      </div>
    </>
  );
}

/** 튜토리얼 완료 화면(GameOver 대신). 완료 메시지를 다 본 뒤에 뜬다. */
export function TutorialFinished({ view }: { view: TutorialView }) {
  return (
    <motion.div className="game-over" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="game-over-card tutorial-finished">
        <span className="lobby-kicker">{t("튜토리얼")}</span>
        <h2>{t("튜토리얼 완료!")}</h2>
        <p className="muted">{view.title}</p>
        <div className="lobby-row">
          <a className="btn-primary" href={location.pathname}>
            {t("AI와 대전하기")}
          </a>
          <a className="btn-secondary" href="/rules/" target="_blank" rel="noreferrer">
            {t("룰북 읽기")}
          </a>
        </div>
      </div>
    </motion.div>
  );
}
