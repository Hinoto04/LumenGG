import { animate, motion, useMotionValue, type MotionStyle } from "motion/react";
import { useRef, useState } from "react";
import type { BoardCard, CardRef, Side, VisibleCard, ZoneName } from "../protocol";
import { showCardInfo } from "../store";
import { cardImage, useCardView, type CardView, type ImageSize } from "../catalog";
import { cardTypeClass } from "../labels";

export type CardSize = "hand" | "board" | "mini" | "large";

interface CardProps {
  card: BoardCard;
  size?: CardSize;
  playable?: boolean;
  selected?: boolean;
  /** 확정 전에 옮겨 둔 카드(노란 테두리, 다시 끌거나 눌러 되돌린다) */
  staged?: boolean;
  onClick?: () => void;
  style?: MotionStyle;
  /** 보드의 같은 카드와 이동 애니메이션을 공유하지 않는다(선택 창 등 사본). */
  detached?: boolean;
  /** 처음 나타날 때 연출. flip은 뒷면에서 뒤집히며 공개되는 모습 */
  enter?: "flip";
  /** 선택했을 때 사용 버튼을 이 카드 위에 띄우기 위한 표식(owner:zone:index) */
  selectKey?: string;
  /** 끌어 놓기. start가 false를 돌려주면 끌지 않은 것으로 친다. */
  dragHandlers?: {
    start: () => void;
    move: (point: { x: number; y: number }) => void;
    end: (point: { x: number; y: number }) => void;
  };
}

/**
 * 끌기 좌표: 포인터 이벤트의 화면(client) 좌표를 그대로 쓴다. motion의 info.point는 프레임 단위로
 * 처리된 마지막 위치라 화면 갱신이 늦을 때 실제로 놓은 곳과 어긋날 수 있다.
 */
function client(event: MouseEvent | TouchEvent | PointerEvent, point: { x: number; y: number }) {
  if ("clientX" in event && Number.isFinite(event.clientX)) return { x: event.clientX, y: event.clientY };
  const touch = "changedTouches" in event ? event.changedTouches[0] : undefined;
  if (touch) return { x: touch.clientX, y: touch.clientY };
  return { x: point.x - window.scrollX, y: point.y - window.scrollY };
}

/** 우클릭 정보에 쓰는 위치: 보드 카드는 selectKey(owner:zone:index), 사본(선택 창·더미 목록)은 카드의 owner·zone */
function infoRef(card: BoardCard, selectKey?: string): CardRef {
  const visible = card as VisibleCard;
  if (selectKey) {
    const [owner, zone, index] = selectKey.split(":");
    return { owner: owner as Side, zone: zone as ZoneName, index: Number(index), instance_id: visible.instance_id };
  }
  return { owner: visible.owner as Side, zone: visible.zone as ZoneName, index: 0, instance_id: visible.instance_id };
}

const IMAGE_SIZE: Record<CardSize, ImageSize> = { mini: "sm", board: "md", hand: "md", large: "lg" };
const POSITION_MARK: Record<string, string> = { 상단: "上", 중단: "中", 하단: "下" };

/** 이미지가 없을 때 쓰는 그린 카드 면 */
function DrawnFace({ view }: { view: CardView }) {
  const isDefense = cardTypeClass(view.type) === "type-defense";
  const pos = String(view.pos ?? "");
  return (
    <>
      <div className="card-art" aria-hidden>
        <span>{String(view.name ?? "").slice(0, 1)}</span>
      </div>
      {view.frame != null && <span className="card-stat card-speed">{view.frame}</span>}
      {view.damage != null && <span className="card-stat card-damage">{view.damage}</span>}
      {pos && <span className="card-pos">{POSITION_MARK[pos] ?? pos}</span>}
      {isDefense && (
        <span className="card-guard">
          {(
            [
              ["상", view.g_top],
              ["중", view.g_mid],
              ["하", view.g_bot],
            ] as const
          ).map(([label, value]) => (
            <i key={label} className={value ? "is-on" : ""}>
              {label}
            </i>
          ))}
        </span>
      )}
      <span className="card-name">{view.name}</span>
      <span className="card-type">{view.type}</span>
    </>
  );
}

export function Card({
  card,
  size = "board",
  playable,
  selected,
  staged,
  onClick,
  style,
  detached,
  enter,
  selectKey,
  dragHandlers,
}: CardProps) {
  // 끌었다 놓은 직후에 click이 한 번 더 오는 것을 막는다.
  const dragged = useRef(false);
  // 끈 거리. 놓은 뒤에는 항상 0으로 되돌린다: 놓아도 상태가 바뀌지 않으면(거절, 픽스처 모드)
  // dragSnapToOrigin만으로는 놓은 자리에 남는 경우가 있었다. 상태가 바뀌면 layout 애니메이션이 새 자리로 옮긴다.
  const dragX = useMotionValue(0);
  const dragY = useMotionValue(0);
  const view = useCardView(card);
  const image = cardImage(view, IMAGE_SIZE[size]);
  const [failed, setFailed] = useState<string | null>(null);
  const showImage = !!image && failed !== image;
  // 손패는 원래 비공개이므로 표시하지 않는다. 필드에 뒷면으로 놓인 내 카드만 표시한다.
  const secretToOthers = !!view && !card.face_up && card.zone !== "hand" && size !== "large";
  const classes = [
    "card",
    `card-${size}`,
    view ? cardTypeClass(view.type) : "card-back",
    showImage ? "has-image" : "",
    playable ? "is-playable" : "",
    selected ? "is-selected" : "",
    staged ? "is-staged" : "",
    dragHandlers ? "is-draggable" : "",
    onClick ? "is-clickable" : "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <motion.button
      type="button"
      layout
      layoutId={view && size !== "large" && !detached ? `card-${(card as VisibleCard).instance_id}` : undefined}
      className={classes}
      style={dragHandlers ? { ...style, x: dragX, y: dragY } : style}
      data-select-key={selectKey}
      onClick={() => {
        if (dragged.current) {
          dragged.current = false;
          return;
        }
        onClick?.();
      }}
      drag={!!dragHandlers}
      dragSnapToOrigin
      dragElastic={0.9}
      dragMomentum={false}
      whileDrag={{ scale: 1.08, zIndex: 60, boxShadow: "0 1.2em 2.4em rgba(0,0,0,0.6)" }}
      onDragStart={() => {
        dragged.current = true;
        dragHandlers?.start();
      }}
      onDrag={(event, info) => dragHandlers?.move(client(event, info.point))}
      onDragEnd={(event, info) => {
        dragHandlers?.end(client(event, info.point));
        const spring = { type: "spring", stiffness: 420, damping: 34 } as const;
        void animate(dragX, 0, spring);
        void animate(dragY, 0, spring);
        // 놓은 자리에서 click이 오지 않는 브라우저도 있으므로 잠시 뒤 풀어 준다.
        setTimeout(() => {
          dragged.current = false;
        }, 250);
      }}
      onContextMenu={(event) => {
        // 우클릭: 카드 정보(PC는 왼쪽 패널, 모바일은 모달). 비공개 카드와 정보 패널 속 큰 카드는 제외.
        if (!view || size === "large") return;
        event.preventDefault();
        showCardInfo({ card, ref: infoRef(card, selectKey) });
      }}
      disabled={!onClick}
      aria-label={view ? String(view.name ?? "카드") : "비공개 카드"}
      initial={enter === "flip" && view ? { opacity: 1, rotateY: 90, scale: 1.08 } : { opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1, rotateY: 0 }}
      exit={{ opacity: 0, scale: 0.85, transition: { duration: 0.15 } }}
      whileHover={onClick ? { y: size === "hand" ? -14 : -4 } : undefined}
      transition={{ type: "spring", stiffness: 420, damping: 34 }}
    >
      {!view && <span className="card-back-mark">L</span>}
      {view && showImage && (
        <img className="card-image" src={image!} alt="" draggable={false} onError={() => setFailed(image)} />
      )}
      {view && !showImage && <DrawnFace view={view} />}
      {view && (card as VisibleCard).attached_to && (
        <span className="card-set" title="다른 기술에 세트된 카드">
          세트
        </span>
      )}
      {secretToOthers && (
        <span className="card-secret" title="상대에게는 뒷면으로 보입니다">
          비공개
        </span>
      )}
    </motion.button>
  );
}
