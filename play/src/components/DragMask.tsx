import { useEffect, useState } from "react";
import { inflate, MULTI_TARGET_PAD, zoneRect, type ZoneRef } from "../dragMoves";
import { usePlay } from "../store";

interface Hole {
  key: string;
  rect: DOMRect;
  label?: string;
  /** 작은 영역(더미 등)은 짧은 이름을 작게 쓴다 */
  compact?: boolean;
}

const COMPACT_WIDTH = 120;

function sameHoles(a: Hole[], b: Hole[]): boolean {
  return (
    a.length === b.length &&
    a.every(
      (hole, index) =>
        hole.key === b[index].key &&
        Math.abs(hole.rect.x - b[index].rect.x) < 0.5 &&
        Math.abs(hole.rect.y - b[index].rect.y) < 0.5 &&
        Math.abs(hole.rect.width - b[index].rect.width) < 0.5 &&
        Math.abs(hole.rect.height - b[index].rect.height) < 0.5,
    )
  );
}

/**
 * 끌기 중 마스크. 카드가 출발 영역 밖으로 나가면 출발 영역(A)들과 도착 영역(B)만 남기고 어둡게 덮고,
 * B에는 영역 이름을 적는다. B가 여럿이면 놓기 쉽게 B를 조금씩 키운다(그만큼 놓는 범위도 넓다).
 */
export function DragMask() {
  const drag = usePlay((s) => s.drag);
  const [holes, setHoles] = useState<Hole[]>([]);
  const active = !!drag?.active;

  useEffect(() => {
    if (!drag?.active) {
      setHoles([]);
      return;
    }
    let frame = 0;
    const measure = () => {
      const pad = drag.targets.length > 1 ? MULTI_TARGET_PAD : 0;
      const next: Hole[] = [];
      const add = (ref: ZoneRef, grow = 0, label?: string, short?: string) => {
        const rect = zoneRect(ref);
        if (!rect) return;
        const compact = rect.width < COMPACT_WIDTH;
        next.push({
          key: `${ref.owner}:${ref.zone}:${label ? "b" : "a"}`,
          rect: inflate(rect, grow),
          label: compact ? short : label,
          compact,
        });
      };
      drag.sources.forEach((source) => add(source));
      drag.targets.forEach((target) => add(target, pad, target.label, target.shortLabel));
      // 위치가 바뀔 때만 다시 그린다(끄는 카드의 움직임을 방해하지 않게).
      setHoles((previous) => (sameHoles(previous, next) ? previous : next));
      frame = requestAnimationFrame(measure);
    };
    measure();
    return () => cancelAnimationFrame(frame);
  }, [drag]);

  if (!active) return null;
  const width = window.innerWidth;
  const height = window.innerHeight;
  return (
    <div className="drag-mask" aria-hidden>
      <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
        <defs>
          <mask id="drag-mask-holes">
            <rect width={width} height={height} fill="white" />
            {holes.map((hole) => (
              <rect key={hole.key} x={hole.rect.x} y={hole.rect.y} width={hole.rect.width} height={hole.rect.height} rx={12} fill="black" />
            ))}
          </mask>
        </defs>
        <rect width={width} height={height} fill="rgba(2, 5, 12, 0.72)" mask="url(#drag-mask-holes)" />
        {holes
          .filter((hole) => hole.label)
          .map((hole) => (
            <rect
              key={`${hole.key}-frame`}
              x={hole.rect.x}
              y={hole.rect.y}
              width={hole.rect.width}
              height={hole.rect.height}
              rx={12}
              className="drag-target-frame"
            />
          ))}
      </svg>
      {holes
        .filter((hole) => hole.label)
        .map((hole) => (
          <span
            key={`${hole.key}-label`}
            className={`drag-target-label ${hole.compact ? "is-compact" : ""}`}
            style={{ left: hole.rect.x + hole.rect.width / 2, top: hole.rect.y + hole.rect.height / 2 }}
          >
            {hole.label}
          </span>
        ))}
    </div>
  );
}
