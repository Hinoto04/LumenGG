import { useEffect, useMemo, useState } from "react";
import { zoneRect, type ZoneRef } from "../dragMoves";
import type { PlayEnvelope } from "../protocol";
import { usePlay } from "../store";
import { decisionCandidates, movesOnBoard, requiredText } from "./Decision";

interface Frame {
  key: string;
  kind: "from" | "to";
  rect: DOMRect;
  text: string;
}

const PAD = 5;

function sameFrames(a: Frame[], b: Frame[]) {
  return (
    a.length === b.length &&
    a.every(
      (frame, index) =>
        frame.key === b[index].key &&
        frame.text === b[index].text &&
        Math.abs(frame.rect.x - b[index].rect.x) < 0.5 &&
        Math.abs(frame.rect.y - b[index].rect.y) < 0.5 &&
        Math.abs(frame.rect.width - b[index].rect.width) < 0.5 &&
        Math.abs(frame.rect.height - b[index].rect.height) < 0.5,
    )
  );
}

/**
 * 카드를 옮기는 선택 중에 출발 영역(빨강, "N From": 옮겨야 할 장 수)과
 * 도착 영역(파랑, "M To": 옮긴 장 수)을 테두리로 표시한다.
 */
export function DecisionFrames({ envelope }: { envelope: PlayEnvelope }) {
  const picks = usePlay((s) => s.decisionPicks);
  const plan = useMemo(() => {
    const candidates = decisionCandidates(envelope);
    const options = [...candidates.options.values()];
    if (!candidates.action || !movesOnBoard(options)) return null;
    const from = new Map<string, ZoneRef>();
    const to = new Map<string, ZoneRef & { moved: number }>();
    for (const option of options) {
      const card = option.ui.card!;
      from.set(`${card.owner}:${card.zone}`, { owner: card.owner, zone: card.zone });
      const target = { owner: card.owner, zone: option.ui.to_zone! };
      const key = `${target.owner}:${target.zone}`;
      const entry = to.get(key) ?? { ...target, moved: 0 };
      if (picks.includes(option.id)) entry.moved += 1;
      to.set(key, entry);
    }
    return { from: [...from.values()], to: [...to.values()], need: requiredText(candidates.minimum, candidates.maximum) };
  }, [envelope, picks]);
  const [frames, setFrames] = useState<Frame[]>([]);

  useEffect(() => {
    if (!plan) {
      setFrames([]);
      return;
    }
    let frame = 0;
    const measure = () => {
      const next: Frame[] = [];
      const add = (ref: ZoneRef, kind: Frame["kind"], text: string) => {
        const rect = zoneRect(ref);
        if (!rect || !rect.width) return;
        next.push({
          key: `${kind}:${ref.owner}:${ref.zone}`,
          kind,
          rect: new DOMRect(rect.x - PAD, rect.y - PAD, rect.width + PAD * 2, rect.height + PAD * 2),
          text,
        });
      };
      plan.from.forEach((ref) => add(ref, "from", `${plan.need} From`));
      plan.to.forEach((ref) => add(ref, "to", `${ref.moved} To`));
      setFrames((previous) => (sameFrames(previous, next) ? previous : next));
      frame = requestAnimationFrame(measure);
    };
    measure();
    return () => cancelAnimationFrame(frame);
  }, [plan]);

  if (!plan) return null;
  return (
    <div className="decision-frames" aria-hidden>
      {frames.map((frame) => (
        <div
          key={frame.key}
          className={`decision-frame is-${frame.kind}`}
          style={{ left: frame.rect.x, top: frame.rect.y, width: frame.rect.width, height: frame.rect.height }}
        >
          <span className="decision-frame-tag">{frame.text}</span>
        </div>
      ))}
    </div>
  );
}
