import { useEffect, useState } from "react";
import type { PlayEnvelope } from "../protocol";
import { perspective } from "../store";

const CLOCK_LABELS: Record<string, string> = {
  ready: "레디",
  decision: "선택",
  rewind: "되감기 응답",
};

function useNow(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(timer);
  }, [active]);
  return now;
}

/** 진행 중인 제한 시간. 누구의 무슨 타이머인지와 남은 초, 10초 이하는 붉게 */
export function ClockBadge({ envelope }: { envelope: PlayEnvelope }) {
  const clock = envelope.clocks;
  const running = !!clock?.deadline && !clock.paused && envelope.engine_status.status === "running";
  const now = useNow(running);
  if (!clock || envelope.engine_status.status !== "running") return null;
  const { me } = perspective(envelope);
  const owner = envelope.role === "viewer" ? `${String(clock.owner ?? "").toUpperCase()} ` : clock.owner === me ? "내 " : "상대 ";
  const label = CLOCK_LABELS[String(clock.kind)] ?? "제한";
  const total = Number(clock.duration_seconds) || 0;
  const remaining = clock.paused
    ? Number(clock.remaining_seconds ?? 0)
    : Math.max(0, Math.ceil((Date.parse(String(clock.deadline)) - now) / 1000));
  const ratio = total ? Math.min(1, remaining / total) : 0;
  const urgent = !clock.paused && remaining <= 10;
  return (
    <span
      className={`clock-badge ${clock.owner === me && envelope.role !== "viewer" ? "is-mine" : ""} ${urgent ? "is-urgent" : ""} ${clock.paused ? "is-paused" : ""}`}
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
