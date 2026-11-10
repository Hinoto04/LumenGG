import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { useFx, type PlaybackSpeed } from "../anim/fx";
import { eventText } from "../eventText";
import { FINISH_REASONS } from "../labels";
import { currentTarget, useLive } from "../net/live";
import type { PlayEnvelope } from "../protocol";
import { perspective } from "../store";
import { GameMenu, type SystemSubmit } from "./SystemUi";
import { sendPreparation } from "../prep/model";

const STATUS_TEXT = {
  connecting: "연결 중…",
  open: "",
  reconnecting: "다시 연결하는 중…",
  closed: "연결 끊김",
} as const;

const SPEEDS: { value: PlaybackSpeed; label: string }[] = [
  { value: 1, label: "연출 ×1" },
  { value: 2, label: "연출 ×2" },
];

/** 실제 대전 화면 위쪽의 작은 메뉴: 연결 상태, 연출 속도, 기록, 나가기 */
export function LiveBar({ envelope, onSubmit }: { envelope: PlayEnvelope | null; onSubmit: SystemSubmit }) {
  const status = useLive((s) => s.status);
  const presence = useLive((s) => s.presence);
  const [menuOpen, setMenuOpen] = useState(false);
  const speed = useFx((s) => s.speed);
  const setSpeed = useFx((s) => s.setSpeed);
  const [logOpen, setLogOpen] = useState(false);
  const speedIndex = SPEEDS.findIndex((item) => item.value === speed);
  return (
    <>
      <div className="live-bar">
        {STATUS_TEXT[status] && <span className={`live-status is-${status}`}>{STATUS_TEXT[status]}</span>}
        {status === "open" && envelope && <PresenceChip envelope={envelope} presence={presence} />}
        <button
          type="button"
          className="btn-chip"
          title="이벤트 연출 속도"
          onClick={() => setSpeed(SPEEDS[(speedIndex + 1) % SPEEDS.length].value)}
        >
          {SPEEDS[speedIndex]?.label ?? "연출 ×1"}
        </button>
        {envelope && (
          <button type="button" className="btn-chip" onClick={() => setLogOpen(true)}>
            기록
          </button>
        )}
        {envelope && (
          <button type="button" className="btn-chip" onClick={() => setMenuOpen(true)}>
            메뉴
          </button>
        )}
        <a className="btn-chip" href={location.pathname}>
          나가기
        </a>
      </div>
      {envelope && <LogSheet envelope={envelope} open={logOpen} onClose={() => setLogOpen(false)} />}
      {envelope && <GameMenu envelope={envelope} open={menuOpen} onClose={() => setMenuOpen(false)} onSubmit={onSubmit} />}
    </>
  );
}

/** 사람 상대의 접속 여부. AI 상대는 표시하지 않는다. 관전자에게는 관전 인원을 보여 준다. */
function PresenceChip({
  envelope,
  presence,
}: {
  envelope: PlayEnvelope;
  presence: Partial<Record<string, number>> | null;
}) {
  if (!presence) return null;
  if (envelope.role === "viewer") {
    return <span className="btn-chip is-static">관전 {presence.viewer ?? 0}</span>;
  }
  const { opp } = perspective(envelope);
  if (envelope.controllers?.[opp] !== "human") return null;
  const online = (presence[opp] ?? 0) > 0;
  return (
    <span className={`btn-chip is-static ${online ? "is-online" : "is-offline"}`}>
      {online ? "상대 접속 중" : "상대 연결 끊김"}
    </span>
  );
}

function LogSheet({ envelope, open, onClose }: { envelope: PlayEnvelope; open: boolean; onClose: () => void }) {
  const events = useLive((s) => s.events);
  const { me } = perspective(envelope);
  const lines = useMemo(
    () =>
      events
        .map((event) => ({ seq: event.seq, text: eventText(event, me) }))
        .filter((line): line is { seq: number; text: string } => !!line.text)
        .reverse(),
    [events, me],
  );
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="zone-sheet log-sheet"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2>기록</h2>
              <button type="button" className="btn-ghost" onClick={onClose}>
                닫기
              </button>
            </header>
            <ol className="log-lines">
              {lines.length === 0 && <li className="muted">아직 기록이 없습니다.</li>}
              {lines.map((line) => (
                <li key={line.seq}>{line.text}</li>
              ))}
            </ol>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

function ManualLink() {
  const target = currentTarget();
  if (!target) return null;
  const path = target.seat
    ? `/battlelog/simulator/${target.view}/${target.seat}/${target.token}/`
    : `/battlelog/simulator/${target.view}/`;
  return (
    <a className="btn-secondary" href={path}>
      수동 모드로 이어하기
    </a>
  );
}

/** 대전 종료·중단 화면 */
export function GameOver({ envelope }: { envelope: PlayEnvelope | null }) {
  const fatal = useLive((s) => s.fatal);
  const [nextError, setNextError] = useState<string | null>(null);
  const status = envelope?.engine_status;
  const finished = status?.status === "finished";
  if (!fatal && !finished) return null;
  let title = "대전 중단";
  if (!fatal && envelope && status) {
    const { me } = perspective(envelope);
    if (!status.winner) title = "무승부";
    else if (envelope.role === "viewer") title = `${status.winner.toUpperCase()} 승리`;
    else title = status.winner === me ? "승리" : "패배";
  }
  return (
    <motion.div className="game-over" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
      <div className="game-over-card">
        <h2>{title}</h2>
        {fatal ? <p>{fatal}</p> : status?.reason ? <p className="muted">{FINISH_REASONS[String(status.reason)] ?? String(status.reason)}</p> : null}
        {nextError && <p className="lobby-error">{nextError}</p>}
        <div className="lobby-row">
          {/* 덱 준비가 있는 대전은 같은 상대와 다음 게임을 이어 할 수 있다 */}
          {!fatal && envelope?.preparation && envelope.role !== "viewer" && (
            <button
              type="button"
              className="btn-primary"
              onClick={() => sendPreparation(envelope, "next_game").catch((error: Error) => setNextError(error.message))}
            >
              다음 게임
            </button>
          )}
          {/* 엔진 오류로 수동 모드가 된 대전은 예전 화면에서 손으로 이어 갈 수 있다 */}
          {fatal && envelope?.mode === "manual" && <ManualLink />}
          <a className={envelope?.preparation && !fatal ? "btn-secondary" : "btn-primary"} href={location.pathname}>
            새 대전
          </a>
        </div>
      </div>
    </motion.div>
  );
}
