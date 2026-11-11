import { motion } from "motion/react";
import { useState } from "react";
import { useFx, type PlaybackSpeed } from "../anim/fx";
import { LogPanel } from "./LogPanel";
import { SoundSettings } from "./SoundSettings";
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

/**
 * '나가기': 사이트의 시뮬레이터 시작 화면(/battlelog/simulator/)으로 돌아간다.
 * 앱(WebView)에서는 예전처럼 대전 클라이언트 로비 주소로 보내, 이미 배포된 앱도 대전 화면을 닫게 한다.
 */
function exitUrl(): string {
  const inApp = typeof window !== "undefined" && "ReactNativeWebView" in window;
  return inApp ? location.pathname : "/battlelog/simulator/";
}

/**
 * 실제 대전 화면 위쪽의 메뉴 버튼 하나. 보드를 가리지 않도록 버튼만 두고
 * 연결 상태·연출 속도·효과음·기록·나가기와 게임 메뉴는 누르면 열리는 시트에 모았다.
 * 연결이 끊겼거나 상대가 나갔으면 버튼에 점을 띄운다.
 */
export function LiveBar({ envelope, onSubmit }: { envelope: PlayEnvelope | null; onSubmit: SystemSubmit }) {
  const status = useLive((s) => s.status);
  const presence = useLive((s) => s.presence);
  const [menuOpen, setMenuOpen] = useState(false);
  const [logOpen, setLogOpen] = useState(false);
  const away = opponentAway(envelope, presence);
  const alert = status !== "open" || away;
  return (
    <>
      <button
        type="button"
        className={`live-menu-btn ${alert ? "has-alert" : ""} ${status === "closed" ? "is-closed" : ""}`}
        aria-label={alert ? `메뉴 (${STATUS_TEXT[status] || "상대 연결 끊김"})` : "메뉴"}
        title={STATUS_TEXT[status] || (away ? "상대 연결 끊김" : "메뉴")}
        onClick={() => setMenuOpen(true)}
      >
        <span aria-hidden="true" className="live-menu-icon">
          <i />
          <i />
          <i />
        </span>
        {alert && <span className="live-menu-dot" aria-hidden="true" />}
      </button>
      {envelope && <LogPanel envelope={envelope} open={logOpen} onClose={() => setLogOpen(false)} />}
      <GameMenu
        envelope={envelope}
        open={menuOpen}
        onClose={() => setMenuOpen(false)}
        onSubmit={onSubmit}
        screen={
          <ScreenSection
            envelope={envelope}
            onLog={() => {
              setMenuOpen(false);
              setLogOpen(true);
            }}
          />
        }
      />
    </>
  );
}

function opponentAway(envelope: PlayEnvelope | null, presence: Partial<Record<string, number>> | null): boolean {
  if (!envelope || !presence || envelope.role === "viewer") return false;
  const { opp } = perspective(envelope);
  return envelope.controllers?.[opp] === "human" && (presence[opp] ?? 0) === 0;
}

/** 메뉴 맨 위: 연결 상태, 연출 속도, 효과음, 기록, 나가기 */
function ScreenSection({ envelope, onLog }: { envelope: PlayEnvelope | null; onLog: () => void }) {
  const status = useLive((s) => s.status);
  const presence = useLive((s) => s.presence);
  const speed = useFx((s) => s.speed);
  const setSpeed = useFx((s) => s.setSpeed);
  return (
    <>
      <section className="menu-screen">
        <div className="menu-status">
          <span className={`live-status is-${status}`}>{STATUS_TEXT[status] || "연결됨"}</span>
          {status === "open" && envelope && <PresenceChip envelope={envelope} presence={presence} />}
        </div>
        <div className="menu-buttons">
          {envelope && (
            <button type="button" className="btn-secondary" onClick={onLog}>
              기록 보기
            </button>
          )}
          <a className="btn-secondary" href={exitUrl()}>
            나가기
          </a>
        </div>
      </section>
      <section>
        <div className="menu-row menu-toggle is-static">
          <span>연출 속도</span>
          <div className="segmented menu-speed" role="radiogroup" aria-label="연출 속도">
            {SPEEDS.map((item) => (
              <button
                key={item.value}
                type="button"
                role="radio"
                aria-checked={speed === item.value}
                className={speed === item.value ? "is-active" : ""}
                onClick={() => setSpeed(item.value)}
              >
                {item.label.replace("연출 ", "")}
              </button>
            ))}
          </div>
        </div>
        <SoundSettings />
      </section>
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
