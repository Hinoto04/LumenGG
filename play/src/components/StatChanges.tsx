import { AnimatePresence, motion } from "motion/react";
import { t } from "../i18n";

/** 서버가 붙이는 효과로 바뀐 값: 인쇄값(base)과 지금 값(current). docs/PLAY_PROTOCOL.md "stat_changes" */
import type { StatChangeValue as StatChange } from "../protocol";
export type { StatChange };
export type StatChanges = Record<string, StatChange>;

const POSITION_MARK: Record<string, string> = { 상단: "上", 중단: "中", 하단: "下" };
const JUDGMENT_LABELS: Record<string, string> = {
  special: "특수",
  hit: "히트 시",
  guard: "가드 시",
  counter: "카운터 시",
};
const GUARD_FIELDS = [
  ["g_top", "상단"],
  ["g_mid", "중단"],
  ["g_bot", "하단"],
] as const;

/**
 * 카드 이미지(784×1064)에 판정이 인쇄된 자리. 카드 너비·높이에 대한 % 좌표(가운데).
 * 공격 기술: 왼쪽 원 안의 히트·가드·카운터 수치.
 * 수비 기술: 상·중·하단 원 옆의 방어 판정 문구.
 * 특수 판정과 공격 기술의 방어 판정("상단 회피" 등)은 효과문 위 가운데 줄에 인쇄된다.
 */
const ATTACK_SPOTS: Record<string, [number, number]> = {
  hit: [18, 55.6],
  guard: [30.6, 60.9],
  counter: [17.6, 66.4],
};
const DEFENSE_SPOTS: Record<string, [number, number]> = {
  g_top: [21, 55.7],
  g_mid: [34, 61.1],
  g_bot: [21, 66.7],
};
const LINE_SPOT: [number, number] = [50, 66.8];

function isNumeric(value: StatChange["current"]): boolean {
  return value != null && String(value).trim() !== "" && Number.isFinite(Number(value));
}

/** 히트·가드·카운터 수치는 카드처럼 +3, -5로 적는다. 콤보 등 낱말은 화면 언어로 옮긴다. */
function judgmentText(value: StatChange["current"]): string {
  if (value == null || value === "") return t("없음");
  if (isNumeric(value)) {
    const number = Number(value);
    return number > 0 ? `+${number}` : String(number);
  }
  return t(String(value));
}

function positionText(value: StatChange["current"]): string {
  if (value == null || value === "") return "—";
  const parts = String(value)
    .split(/[·•,/\s]+/)
    .filter(Boolean);
  return parts.map((part) => POSITION_MARK[part] ?? part).join("");
}

/** 빛의계승자체에는 上·中·下 한자 글리프가 비어 있어 판정 글꼴로 쓰는 곳은 한글 낱말로 적는다. */
function positionWords(value: StatChange["current"]): string {
  const parts = String(value ?? "")
    .split(/[·•,/\s]+/)
    .filter(Boolean);
  return parts.length ? parts.map((part) => t(part)).join("·") : "—";
}

function plainText(value: StatChange["current"]): string {
  return value == null || value === "" ? t("없음") : String(value);
}

/** 값이 바뀔 때마다 다시 튀어나오도록 부르는 쪽이 key에 값을 넣는다. */
const POP = {
  initial: { scale: 2.4, opacity: 0 },
  animate: { scale: 1, opacity: 1 },
  exit: { scale: 0.6, opacity: 0, transition: { duration: 0.15 } },
  transition: { type: "spring", stiffness: 380, damping: 18 },
} as const;

const POSITION_IMAGE: Record<string, string> = { 상단: "attack_top", 중단: "attack_mid", 하단: "attack_bot" };

function positionParts(value: unknown): string[] {
  return String(value ?? "")
    .split(/[·•,/\s]+/)
    .filter((part) => POSITION_IMAGE[part]);
}

/** 꼬리표의 "이전 값". 판정 때 FP로 줄인 속도는 FP 전 속도와 비교한다. */
function compareFrom(change: StatChange): string | number | null {
  return change.fp_reference ?? change.base;
}

/** 속도는 낮을수록 빠르다(유리), 대미지는 높을수록 세다. */
function tone(kind: "frame" | "damage", change: StatChange | undefined): string {
  if (!change) return "";
  const raised = Number(change.current) > Number(compareFrom(change));
  if (kind === "frame") return raised ? "is-worse" : "is-better";
  return raised ? "is-stronger" : "is-weaker";
}

/**
 * 왼쪽 위 위치 판정 마름모와 그 안의 속도. 카드 이미지의 마름모 위에 지금 위치의 마름모 그림을 덮고
 * 지금 속도를 다시 쓴다. 바뀐 값은 아래 꼬리표에 "인쇄값→지금 값"으로 남긴다.
 */
function SpeedDiamond({ changes, frame, pos }: { changes: StatChanges; frame: unknown; pos: unknown }) {
  const speed = changes.frame ? changes.frame.current : frame;
  const positions = positionParts(changes.pos ? changes.pos.current : pos);
  const speedTone = tone("frame", changes.frame);
  const title = [
    changes.frame &&
      t("{label} {before} → {after} (효과로 변경됨)", { label: t("속도"), before: String(compareFrom(changes.frame)), after: String(changes.frame.current) }),
    changes.pos &&
      t("{label} {before} → {after} (효과로 변경됨)", { label: t("위치"), before: positionText(changes.pos.base), after: positionText(changes.pos.current) }),
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <motion.span className="stat-diamond" title={title} {...POP}>
      {positions.length > 0 ? (
        positions.map((part) => (
          <img
            key={part}
            className={`stat-diamond-frame pos-${POSITION_IMAGE[part]}`}
            src={`${import.meta.env.BASE_URL}judgment/${POSITION_IMAGE[part]}.png`}
            alt=""
            draggable={false}
          />
        ))
      ) : (
        <span className="stat-diamond-plain" aria-hidden />
      )}
      {speed != null && speed !== "" && <b className={`stat-diamond-speed ${speedTone}`}>{String(speed)}</b>}
      <span className="stat-diamond-tag">
        {changes.frame && (
          <span className={speedTone}>
            <s>{String(compareFrom(changes.frame))}</s>
            {Number(changes.frame.current) > Number(compareFrom(changes.frame)) ? "▲" : "▼"}
            {changes.frame.note && <em className="stat-note">{changes.frame.note}</em>}
          </span>
        )}
        {changes.pos && (
          <span className="is-judgment">
            <s>{positionWords(changes.pos.base)}</s>→{positionWords(changes.pos.current)}
          </span>
        )}
      </span>
    </motion.span>
  );
}

/** 아래 가운데 인쇄된 대미지 자리를 가리고 지금 대미지를 쓴다. */
function DamagePlate({ change }: { change: StatChange }) {
  const damageTone = tone("damage", change);
  return (
    <motion.span
      className={`stat-damage ${damageTone}`}
      title={t("{label} {before} → {after} (효과로 변경됨)", { label: t("대미지"), before: String(change.base), after: String(change.current) })}
      {...POP}
    >
      <s className="stat-damage-base">{String(change.base)}</s>
      <b className="stat-damage-value">{String(change.current)}</b>
      <i aria-hidden>{Number(change.current) > Number(change.base) ? "▲" : "▼"}</i>
      {change.note && <em className="stat-note">{change.note}</em>}
    </motion.span>
  );
}

/** 인쇄된 판정 자리를 가리고 지금 값을 쓴다. 바뀌기 전 값은 위에 작게 그어 남긴다. */
function JudgmentPlate({
  spot,
  label,
  before,
  after,
  numeric,
  line,
}: {
  spot: [number, number];
  label: string;
  before: string;
  after: string;
  numeric: boolean;
  line?: boolean;
}) {
  return (
    <motion.span
      className={`stat-judgment${numeric ? " is-number" : " is-word"}${line ? " is-line" : ""}`}
      style={{ left: `${spot[0]}%`, top: `${spot[1]}%` }}
      title={t("{label} {before} → {after} (효과로 변경됨)", { label, before, after })}
      {...POP}
    >
      <s className="stat-judgment-base">{before}</s>
      <b className="stat-judgment-value">{after}</b>
    </motion.span>
  );
}

/** 카드 이미지 위에 덧씌우는 변경 표시. 위치·속도·대미지는 인쇄된 자리에, 나머지 판정은 가운데에 쌓는다. */
export function StatChangeOverlay({
  changes,
  frame,
  pos,
  defense,
  special,
}: {
  changes: StatChanges;
  frame?: unknown;
  pos?: unknown;
  /** 수비 기술이면 방어 판정을 상·중·하단 원 옆에, 아니면 가운데 줄에 쓴다. */
  defense?: boolean;
  /** 인쇄된 특수 판정(그랩 등). 가운데 줄을 덮을 때 함께 적어 가려지지 않게 한다. */
  special?: unknown;
}) {
  const plates: { id: string; spot: [number, number]; label: string; before: string; after: string; numeric: boolean; line?: boolean }[] = [];
  for (const [field, spot] of Object.entries(ATTACK_SPOTS)) {
    const change = changes[field];
    if (!change) continue;
    plates.push({
      id: field,
      spot,
      label: t(JUDGMENT_LABELS[field]),
      before: judgmentText(change.base),
      after: judgmentText(change.current),
      numeric: isNumeric(change.current),
    });
  }
  // 가운데 줄(특수 판정·공격 기술의 방어 판정)은 여러 개면 위아래로 나눠 쌓는다.
  const lineItems: { id: string; label: string; before: string; after: string }[] = [];
  for (const [field, position] of GUARD_FIELDS) {
    const change = changes[field];
    if (!change) continue;
    if (defense) {
      plates.push({
        id: field,
        spot: DEFENSE_SPOTS[field],
        label: `${t("방어")} ${t(position)}`,
        before: plainText(change.base),
        after: plainText(change.current),
        numeric: false,
      });
    } else {
      // 같은 줄에 인쇄된 특수 판정(그랩 등)은 덮어도 보이도록 앞에 붙인다.
      // "상단 회피"처럼 방어 판정 자체가 특수 판정 칸에 적힌 카드는 겹치므로 붙이지 않는다.
      const printedSpecial = String(special ?? "");
      const printed =
        !changes.special && printedSpecial && !/상단|중단|하단/.test(printedSpecial) ? `${t(printedSpecial)} · ` : "";
      lineItems.push({
        id: field,
        label: `${t("방어")} ${t(position)}`,
        before: change.base ? `${printed}${t(position)} ${plainText(change.base)}` : `${printed}${t("없음")}`,
        after: change.current ? `${printed}${t(position)} ${plainText(change.current)}` : `${printed}${t("없음")}`,
      });
    }
  }
  if (changes.special) {
    lineItems.unshift({
      id: "special",
      label: t("특수"),
      before: plainText(changes.special.base),
      after: plainText(changes.special.current),
    });
  }
  lineItems.forEach((item, index) => {
    const offset = (index - (lineItems.length - 1) / 2) * 6.5;
    plates.push({ ...item, spot: [LINE_SPOT[0], LINE_SPOT[1] + offset], numeric: false, line: true });
  });
  return (
    <span className="stat-changes" aria-label={t("효과로 바뀐 값")}>
      <AnimatePresence>
        {(changes.frame || changes.pos) && (
          <SpeedDiamond
            key={`diamond:${changes.frame?.current ?? ""}:${changes.pos?.current ?? ""}`}
            changes={changes}
            frame={frame}
            pos={pos}
          />
        )}
        {changes.damage && <DamagePlate key={`damage:${changes.damage.current}`} change={changes.damage} />}
        {plates.map((plate) => (
          <JudgmentPlate key={`${plate.id}:${plate.after}`} {...plate} />
        ))}
      </AnimatePresence>
    </span>
  );
}
