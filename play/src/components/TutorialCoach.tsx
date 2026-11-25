import { AnimatePresence, motion } from "motion/react";
import { useEffect, useLayoutEffect, useMemo, useState, type CSSProperties } from "react";
import { create } from "zustand";
import { useFx } from "../anim/fx";
import { t } from "../i18n";
import { liveUrl } from "../mode";
import { postJson } from "../net/http";
import type { AnatomyPart, BoardCard, CardDesign, CardRef, LegalAction, PlayEnvelope, TutorialFocus, TutorialView } from "../protocol";
import { usePlay } from "../store";
import { Card } from "./Card";
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

/** 튜토리얼 단원을 새로 만들고 그 대전으로 옮겨 간다. 실패하면 서버 메시지를 던진다. */
export async function startTutorial(lesson: string): Promise<void> {
  const data = await postJson<{ view_token: string; seats: { p1: string } }>("/battlelog/play/api/tutorial/", { lesson });
  location.assign(liveUrl({ view: data.view_token, seat: "p1", token: data.seats.p1 }));
}

type PartBox = { left: number; top: number; width: number; height: number };

/**
 * 카드 이미지에서 각 부분의 자리(카드 너비·높이에 대한 %). 실제 카드 인쇄 배치 기준이며
 * 서버의 lessons.ANATOMY_PARTS와 이름이 같다. 디자인은 서버가 카드 코드로 정해 보낸다(lessons.card_design).
 * - current(신규): 속도를 감싼 마름모의 빛나는 꼭짓점이 위치, 이름 아래 대사, 오른쪽 위 손/발 아이콘, 효과 위 특수 판정 띠
 * - classic(예전, 스타터 덱 등): 왼쪽 위 동그라미 속도, 오른쪽 위 위치 마크, 이름 아래 손/발 글자,
 *   일러스트 아래 가운데 특수 판정 띠
 * 이미지가 없는 카드(그린 앞면)는 테두리를 그리지 않는다.
 */
const ANATOMY_BOXES: Record<CardDesign, Record<AnatomyPart, PartBox>> = {
  current: {
    name: { left: 25, top: 4, width: 50, height: 12.5 },
    speed: { left: 5, top: 4, width: 19.5, height: 15 },
    pos: { left: 5, top: 4, width: 19.5, height: 15 },
    body: { left: 78, top: 7.5, width: 15, height: 7 },
    damage: { left: 35, top: 87, width: 30, height: 10 },
    fp: { left: 6, top: 50, width: 31, height: 23.5 },
    special: { left: 30, top: 63, width: 60, height: 6.5 },
    guard: { left: 5, top: 50, width: 40, height: 21 },
    text: { left: 8, top: 69.5, width: 84, height: 13 },
  },
  classic: {
    name: { left: 31, top: 4.5, width: 38, height: 10.5 },
    speed: { left: 6.5, top: 5.5, width: 17, height: 13 },
    pos: { left: 76, top: 5, width: 18, height: 13.5 },
    body: { left: 42, top: 9.5, width: 16, height: 5.5 },
    damage: { left: 35, top: 86, width: 30, height: 11 },
    fp: { left: 6, top: 49.5, width: 32, height: 23 },
    // 일러스트 바로 아래 가운데 띠(예: "중단 상쇄").
    special: { left: 30, top: 62, width: 40, height: 7.5 },
    guard: { left: 6, top: 49.5, width: 34, height: 22 },
    text: { left: 8, top: 69.5, width: 84, height: 12 },
  },
};

function findCard(envelope: PlayEnvelope, ref: CardRef): BoardCard | null {
  const cards = envelope.state.players[ref.owner]?.zones[ref.zone] ?? [];
  if (ref.instance_id) {
    const byId = cards.find((card) => !card.hidden && String(card.instance_id) === String(ref.instance_id));
    if (byId) return byId;
  }
  return cards[ref.index] ?? null;
}

/** 말풍선 안에 크게 띄운 카드와 지금 설명하는 부분의 테두리 */
function AnatomyCard({ envelope, focus }: { envelope: PlayEnvelope; focus: Extract<TutorialFocus, { kind: "anatomy" }> }) {
  const card = findCard(envelope, focus.card);
  if (!card || card.hidden) return null;
  const boxes = ANATOMY_BOXES[focus.design ?? "current"] ?? ANATOMY_BOXES.current;
  const box = boxes[focus.part] ?? boxes.name;
  return (
    <div className="tutorial-anatomy" data-part={focus.part} data-design={focus.design ?? "current"}>
      <Card card={card} size="large" detached />
      <motion.i
        key={focus.part}
        className="tutorial-anatomy-mark"
        style={{ left: `${box.left}%`, top: `${box.top}%`, width: `${box.width}%`, height: `${box.height}%` }}
        initial={{ opacity: 0, scale: 1.25 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.25 }}
      />
    </div>
  );
}

export function tutorialOf(envelope: PlayEnvelope | null): TutorialView | null {
  return envelope?.role === "p1" && envelope.tutorial ? envelope.tutorial : null;
}

function playableActions(envelope: PlayEnvelope): LegalAction[] {
  return envelope.legal_actions.filter((action) => !SYSTEM_ACTIONS.has(action.type));
}

/**
 * 보이는 카드는 instance_id로 찾는다. 화면이 서버와 다른 자리에 카드를 보여 줄 때가 있어서다
 * (콤보 첫 카드는 서버에선 손패에 있지만 화면에선 배틀 존에 놓여 손패 순번이 당겨진다).
 */
function refSelector(ref: Pick<CardRef, "owner" | "zone" | "index"> & { instance_id?: string }): string {
  return ref.instance_id
    ? `[data-instance-id="${ref.instance_id}"]`
    : `[data-select-key="${ref.owner}:${ref.zone}:${ref.index}"]`;
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
  const decisionOpen = usePlay((s) => !s.decisionCollapsed);
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
  // 선택 창(그랩 무효, 브레이크 보충 등)이 열려 있으면 덮개만 창 아래로 내리고 말풍선은 창 위에 둔다.
  const deciding = passThrough && !choosing && decisionOpen && playable.some((action) => action.type === "submit_decision");
  const next = () => {
    if (!last) setIndex(index + 1);
    else if (view.status === "completed") setFinishSeen(true);
  };
  const hole = box
    ? { x: box.left - PAD, y: box.top - PAD, w: box.right - box.left + PAD * 2, h: box.bottom - box.top + PAD * 2 }
    : null;
  const width = window.innerWidth;
  const height = window.innerHeight;
  const anatomy = message.focus?.kind === "anatomy" ? message.focus : null;
  const bubbleWidth = Math.min(anatomy ? 560 : 380, width - 32);
  let bubbleStyle: CSSProperties;
  if (anatomy && !compact) {
    // 카드를 크게 띄운 설명은 화면 가운데에 둔다(보드는 전부 어둡게).
    bubbleStyle = { top: Math.max(60, height / 2 - 220), left: (width - bubbleWidth) / 2, width: bubbleWidth };
  } else if (compact || !hole) {
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
      <div
        className={`tutorial-coach ${passThrough ? "is-pass-through" : ""} ${yieldToSelection ? "is-yield" : ""} ${deciding ? "is-deciding" : ""}`}
      >
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
            className={`tutorial-bubble ${compact ? "is-sheet" : ""} ${failed ? "is-failed" : ""} ${anatomy ? "is-anatomy" : ""}`}
            style={bubbleStyle}
            role="dialog"
            aria-live="polite"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            {anatomy && <AnatomyCard envelope={envelope} focus={anatomy} />}
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
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const next = view.next ?? null;
  const goNext = async () => {
    if (!next) return;
    setStarting(true);
    setError(null);
    try {
      await startTutorial(next.lesson);
    } catch (exception) {
      setError((exception as Error).message);
      setStarting(false);
    }
  };
  return (
    <motion.div className="game-over" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="game-over-card tutorial-finished">
        <span className="lobby-kicker">{t("튜토리얼")}</span>
        <h2>{t("튜토리얼 완료!")}</h2>
        <p className="muted">{view.title}</p>
        <div className="lobby-row">
          {next && (
            <button type="button" className="btn-primary" disabled={starting} onClick={goNext}>
              {starting ? t("만드는 중…") : t("다음 단원: {title}", { title: next.title })}
            </button>
          )}
          <a className={next ? "btn-secondary" : "btn-primary"} href={location.pathname}>
            {next ? t("로비로") : t("AI와 대전하기")}
          </a>
          <a className="btn-secondary" href="/rules/" target="_blank" rel="noreferrer">
            {t("룰북 읽기")}
          </a>
        </div>
        {error && <p className="lobby-error">{error}</p>}
      </div>
    </motion.div>
  );
}
