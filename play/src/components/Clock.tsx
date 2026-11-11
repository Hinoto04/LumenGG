import { useEffect, useState } from "react";
import { clockDeadline, clockSeen } from "../net/live";
import type { PlayEnvelope } from "../protocol";
import { perspective } from "../store";
import { playSound } from "../sound/sfx";

const CLOCK_LABELS: Record<string, string> = {
  ready: "레디",
  decision: "선택",
  rewind: "되감기 응답",
  action: "행동",
};

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

/** 진행 중인 제한 시간. 누구의 무슨 타이머인지와 남은 초, 10초 이하는 붉게 */
export function ClockBadge({ envelope }: { envelope: PlayEnvelope }) {
  const clock = envelope.clocks;
  const waiting = clock?.seen === false;
  const running = !!clock?.deadline && !clock.paused && !waiting && envelope.engine_status.status === "running";
  const now = useNow(running);
  const { me } = perspective(envelope);
  const mine = envelope.role !== "viewer" && (clock?.owner === me || clock?.owner === "both");
  // 이 화면에 표시된 순간을 서버에 알린다. 내 차례 제한 시간은 그때부터 흐른다.
  useEffect(() => {
    if (waiting && mine && clock?.id && envelope.engine_status.status === "running") clockSeen(String(clock.id));
  }, [waiting, mine, clock?.id, envelope.engine_status.status]);
  // 내 제한 시간이 5초 이하이면 1초마다 짧게 울린다.
  const secondsLeft =
    running && mine && clock ? Math.max(0, Math.ceil(((clockDeadline(clock) ?? now) - now) / 1000)) : null;
  useEffect(() => {
    if (secondsLeft != null && secondsLeft > 0 && secondsLeft <= 5) playSound("tick");
  }, [secondsLeft]);
  if (!clock || envelope.engine_status.status !== "running") return null;
  const owner =
    clock.owner === "both"
      ? ""
      : envelope.role === "viewer"
        ? `${String(clock.owner ?? "").toUpperCase()} `
        : clock.owner === me
          ? "내 "
          : "상대 ";
  const label = CLOCK_LABELS[String(clock.kind)] ?? "제한";
  const total = Number(clock.duration_seconds) || 0;
  const remaining = clock.paused
    ? Number(clock.remaining_seconds ?? 0)
    : waiting
      ? total
      : Math.min(total || Infinity, Math.max(0, Math.ceil(((clockDeadline(clock) ?? now) - now) / 1000)));
  const ratio = total ? Math.min(1, remaining / total) : 0;
  const urgent = !clock.paused && remaining <= 10;
  return (
    <span
      className={`clock-badge ${mine ? "is-mine" : ""} ${urgent ? "is-urgent" : ""} ${clock.paused ? "is-paused" : ""}`}
      role="timer"
      aria-label={`${owner}${label} 남은 시간 ${remaining}초`}
    >
      <i style={{ width: `${ratio * 100}%` }} />
      <span>
        {owner}
        {label} {clock.paused ? "일시정지" : `${remaining}초`}
      </span>
    </span>
  );
}
