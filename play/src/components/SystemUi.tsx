import { AnimatePresence, motion } from "motion/react";
import { useState } from "react";
import { liveUrl } from "../mode";
import type { Selections } from "../net/live";
import { reportIssue } from "../net/report";
import type { LegalAction, PlayEnvelope } from "../protocol";
import { perspective, usePlay } from "../store";

export type SystemSubmit = (action: LegalAction, selections?: Selections) => void;

const PAUSE_REASONS = ["룰 확인", "자리 비움", "연결 문제"];

function systemActions(envelope: PlayEnvelope, type: string) {
  return envelope.legal_actions.filter((action) => action.type === type);
}

/** 기존 사이트 좌석 주소(/battlelog/simulator/<view>/<seat>/<token>/)를 새 클라이언트 주소로 바꾼다. */
function seatLink(envelope: PlayEnvelope, key: "player1_url" | "player2_url"): string | null {
  const match = String(envelope[key] ?? "").match(/simulator\/([^/]+)\/(p[12])\/([^/]+)\/?$/);
  if (!match) return null;
  return location.origin + liveUrl({ view: match[1], seat: match[2] as "p1" | "p2", token: match[3] });
}

/** 수동 대전을 예전 시뮬레이터 화면으로 연다(전용 패시브, 운영진 도구 등). */
function LegacyLink() {
  const query = new URLSearchParams(location.search);
  const view = query.get("game");
  const seat = query.get("seat");
  const token = query.get("token");
  if (!view) return null;
  const path = seat && token ? `/battlelog/simulator/${view}/${seat}/${token}/?legacy=1` : `/battlelog/simulator/${view}/?legacy=1`;
  return (
    <a className="btn-secondary menu-legacy" href={path}>
      예전 화면으로 보기
    </a>
  );
}

function viewToken(): string {
  return new URLSearchParams(location.search).get("game") ?? "";
}

/** 자동 판정이 이상할 때 서버에 남기는 제보. 관리자 검수 화면에서 본다. */
function IssueReport() {
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [sending, setSending] = useState(false);
  const send = async () => {
    if (!text.trim()) return;
    setSending(true);
    try {
      const id = await reportIssue(text.trim());
      setText("");
      setStatus(`제보했습니다 · ${id}`);
    } catch (error) {
      setStatus((error as Error).message);
    } finally {
      setSending(false);
    }
  };
  return (
    <div className="menu-row">
      <span>판정 문제 제보</span>
      <textarea
        className="menu-textarea"
        rows={3}
        maxLength={4000}
        value={text}
        placeholder="어떤 상황에서 무엇이 기대와 달랐는지 적어 주세요."
        onChange={(event) => setText(event.target.value)}
      />
      <div className="menu-buttons">
        <button type="button" className="btn-secondary" disabled={sending || !text.trim()} onClick={send}>
          {sending ? "보내는 중…" : "제보 보내기"}
        </button>
        {status && <span className="muted">{status}</span>}
      </div>
    </div>
  );
}

function CopyRow({ label, url }: { label: string; url: string }) {
  const flash = usePlay((s) => s.flash);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      flash(`${label} 주소를 복사했습니다`);
    } catch {
      flash("복사하지 못했습니다. 주소를 직접 선택해 주세요");
    }
  };
  return (
    <div className="menu-copy">
      <span>{label}</span>
      <code>{url}</code>
      <button type="button" className="btn-secondary" onClick={copy}>
        복사
      </button>
    </div>
  );
}

/** 대전 메뉴: 초대·관전 주소, 타이머 일시정지·재개, 되감기 요청, 기권 */
export function GameMenu({
  envelope,
  open,
  onClose,
  onSubmit,
}: {
  envelope: PlayEnvelope;
  open: boolean;
  onClose: () => void;
  onSubmit: SystemSubmit;
}) {
  const [confirmConcede, setConfirmConcede] = useState(false);
  const pause = systemActions(envelope, "pause_clock")[0];
  const resume = systemActions(envelope, "resume_clock")[0];
  const rewind = systemActions(envelope, "request_rewind")[0];
  const concede = systemActions(envelope, "concede")[0];
  const opponentLink = envelope.role === "p1" ? seatLink(envelope, "player2_url") : null;
  const spectate = location.origin + liveUrl({ view: viewToken(), seat: "", token: "" });
  const run = (action: LegalAction, selections?: Selections) => {
    onSubmit(action, selections);
    setConfirmConcede(false);
    onClose();
  };
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="overlay" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
          <motion.div
            className="zone-sheet game-menu"
            initial={{ y: "100%" }}
            animate={{ y: 0 }}
            exit={{ y: "100%" }}
            transition={{ type: "spring", stiffness: 380, damping: 36 }}
            onClick={(event) => event.stopPropagation()}
          >
            <header>
              <h2>메뉴</h2>
              <button type="button" className="btn-ghost" onClick={onClose}>
                닫기
              </button>
            </header>
            <section>
              {opponentLink && <CopyRow label="상대 좌석" url={opponentLink} />}
              <CopyRow label="관전" url={spectate} />
              {envelope.mode === "manual" && <LegacyLink />}
            </section>
            {(pause || resume || rewind) && (
              <section>
                {pause && (
                  <div className="menu-row">
                    <span>상대 타이머 일시정지</span>
                    <div className="menu-buttons">
                      {PAUSE_REASONS.map((reason) => (
                        <button key={reason} type="button" className="btn-secondary" onClick={() => run(pause, { reason })}>
                          {reason}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
                {resume && (
                  <button type="button" className="btn-secondary" onClick={() => run(resume)}>
                    타이머 재개
                  </button>
                )}
                {rewind && (
                  <button type="button" className="btn-secondary" onClick={() => run(rewind)}>
                    직전 행동 되감기 요청
                  </button>
                )}
              </section>
            )}
            {envelope.role !== "viewer" && envelope.mode === "automatic" && (
              <section>
                <IssueReport />
              </section>
            )}
            {concede && (
              <section>
                {confirmConcede ? (
                  <div className="menu-row is-danger">
                    <span>정말 기권할까요? 되돌릴 수 없습니다.</span>
                    <div className="menu-buttons">
                      <button type="button" className="btn-ghost" onClick={() => setConfirmConcede(false)}>
                        취소
                      </button>
                      <button type="button" className="btn-danger" onClick={() => run(concede)}>
                        기권
                      </button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className="btn-danger" onClick={() => setConfirmConcede(true)}>
                    기권하기
                  </button>
                )}
              </section>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** 타이머가 일시정지된 동안 보드 위에 띄운다. 재개는 양쪽 모두 할 수 있다. */
export function PauseNotice({ envelope, onSubmit }: { envelope: PlayEnvelope; onSubmit: SystemSubmit }) {
  const clock = envelope.clocks;
  const resume = systemActions(envelope, "resume_clock")[0];
  if (!clock?.paused || envelope.engine_status.status !== "running") return null;
  const { me } = perspective(envelope);
  const who = envelope.role === "viewer" ? String(clock.paused_by ?? "").toUpperCase() : clock.paused_by === me ? "내가" : "상대가";
  return (
    <div className="pause-notice" role="status">
      <strong>타이머 일시정지</strong>
      <span>
        {who} 멈춤{clock.pause_reason ? ` · ${clock.pause_reason}` : ""} · 남은 {Number(clock.remaining_seconds ?? 0)}초
      </span>
      {resume && (
        <button type="button" className="btn-primary" onClick={() => onSubmit(resume)}>
          재개
        </button>
      )}
    </div>
  );
}

/** 상대가 되감기를 요청하면 수락·거절을 묻는다. */
export function RewindPrompt({ envelope, onSubmit }: { envelope: PlayEnvelope; onSubmit: SystemSubmit }) {
  const answers = systemActions(envelope, "answer_rewind");
  if (!answers.length) return null;
  const accept = answers.find((action) => action.payload.accept === true);
  const decline = answers.find((action) => action.payload.accept === false);
  return (
    <div className="decision-backdrop">
      <section className="decision rewind-prompt" role="dialog" aria-label="되감기 요청">
        <header>
          <h2>상대가 직전 행동 되감기를 요청했습니다</h2>
        </header>
        <footer>
          {decline && (
            <button type="button" className="btn-ghost" onClick={() => onSubmit(decline)}>
              거절
            </button>
          )}
          {accept && (
            <button type="button" className="btn-primary" onClick={() => onSubmit(accept)}>
              수락
            </button>
          )}
        </footer>
      </section>
    </div>
  );
}
