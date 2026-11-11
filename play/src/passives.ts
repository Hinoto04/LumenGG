import type { PlayerState } from "./protocol";

/**
 * 초상에 보여 줄 패시브 목록. 아직 한 번도 바뀌지 않아 passive_state에 없는 값도
 * 캐릭터 설정(컨트롤 기본값)과 전용 패널의 키로 채워서, 카운터와 상태가 모두 보이게 한다.
 */

export interface PassiveItem {
  key: string;
  label: string;
  kind: "counter" | "state" | "value";
  value: number | boolean | string;
  max?: number | null;
  /** 카운터이면서 상태로 켜질 수 있는 항목(타오 음/양): 켜진 쪽은 분홍색으로 강조한다. */
  active?: boolean;
}

interface Control {
  type: string;
  key: string;
  label?: string;
  default?: unknown;
  initial?: unknown;
  max?: number | null;
  choices?: { value: unknown; label?: string }[];
}

/** 전용 패널(CharacterPassive.tsx)이 다루는 키와 기본값 */
const PANEL_KEYS: Record<string, Control[]> = {
  "data-yohan-panel": [
    { type: "counter", key: "foresight_counter", label: "예지", default: 2, max: 10 },
    { type: "toggle", key: "disaster_one", label: "디제스터 원" },
  ],
  "data-tao-panel": [
    { type: "counter", key: "yang_counter", label: "양", max: 4 },
    { type: "counter", key: "yin_counter", label: "음", max: 4 },
    { type: "toggle", key: "harmony", label: "조화" },
    {
      type: "choice",
      key: "harmony_effect",
      label: "조화 효과",
      choices: [
        { value: "damage_100", label: "DMG+100" },
        { value: "fp_1", label: "FP+1" },
      ],
    },
  ],
  "data-cmyk-panel": [{ type: "toggle", key: "new_single_created", label: "뉴 싱글" }],
};

const ON = new Set<unknown>([true, "true", "on", "ON"]);
const OFF = new Set<unknown>([false, "false", "off", "OFF"]);

function stored(player: PlayerState, key: string): unknown {
  const entry = player.passive_state?.[key] as Record<string, unknown> | undefined;
  if (!entry) return undefined;
  if (entry.value !== undefined && entry.value !== "") return entry.value;
  return entry.count;
}

/** 엔진 상태 키가 그대로 노출되는 항목의 한글 이름 */
const STATE_LABELS: Record<string, string> = {
  yin: "음",
  yang: "양",
  harmony: "조화",
  harmony_damage: "조화: DMG+100",
  harmony_fp: "조화: FP+1",
};

export function labelFor(player: PlayerState, key: string, fallback?: string): string {
  if (STATE_LABELS[key]) return STATE_LABELS[key];
  const entry = player.passive_state?.[key];
  return String(entry?.display_label ?? fallback ?? entry?.label ?? key);
}

/**
 * manual=true(수동 모드)일 때만 설정·전용 패널의 기본값으로 빈 칸을 채운다.
 * 자동 판정은 엔진이 쓰는 키(예: 타오 yin/yang)가 설정의 키와 달라서, 엔진 값만 보여 준다.
 */
export function passiveItems(player: PlayerState, manual: boolean): PassiveItem[] {
  const ui = (player.character?.passive_ui ?? {}) as { html?: string; options?: { controls?: Control[] } };
  const html = String(ui.html ?? "");
  const controls = !manual ? [] : [
    ...(ui.options?.controls ?? []),
    ...Object.entries(PANEL_KEYS).flatMap(([marker, keys]) => (html.includes(marker) ? keys : [])),
  ];
  const items: PassiveItem[] = [];
  const seen = new Set<string>();

  for (const control of controls) {
    if (!control?.key || seen.has(control.key)) continue;
    const raw = stored(player, control.key) ?? control.default ?? control.initial;
    const label = labelFor(player, control.key, control.label);
    if (control.type === "counter") {
      items.push({ key: control.key, label, kind: "counter", value: Number(raw) || 0, max: control.max ?? null });
    } else if (control.type === "choice") {
      const choice = control.choices?.find((item) => String(item.value) === String(raw));
      if (raw === undefined || raw === "") continue;
      items.push({ key: control.key, label, kind: "value", value: String(choice?.label ?? raw) });
    } else if (control.type === "thresholdAction") {
      continue;
    } else {
      items.push({ key: control.key, label, kind: "state", value: ON.has(raw) });
    }
    seen.add(control.key);
  }

  // 설정에 없는 값(자동 엔진의 상태·토큰, 예전 대전의 값 등)도 빠짐없이 보여 준다.
  for (const [key, entry] of Object.entries(player.passive_state ?? {})) {
    if (seen.has(key) || !entry || typeof entry !== "object") continue;
    const raw = stored(player, key);
    const label = labelFor(player, key);
    // 타오의 음/양처럼 카운터와 같은 이름의 상태가 걸리면 엔진이 value=true를 덧씌운다.
    // 개수가 가려지지 않도록 카운터와 상태를 따로 보여 준다.
    // 개수는 항상 보이게 카운터로 두고, 상태가 켜졌는지는 강조(active)로 표시한다.
    const count = (entry as Record<string, unknown>).count;
    const flag = (entry as Record<string, unknown>).value;
    if (typeof count === "number" && (typeof flag === "boolean" || (entry as Record<string, unknown>).derived)) {
      items.push({ key, label, kind: "counter", value: count, active: ON.has(flag) });
      seen.add(key);
      continue;
    }
    if (typeof raw === "number") items.push({ key, label, kind: "counter", value: raw });
    else if (ON.has(raw) || OFF.has(raw)) items.push({ key, label, kind: "state", value: ON.has(raw) });
    else if (typeof raw === "string" && raw) items.push({ key, label, kind: "value", value: raw });
    else continue;
    seen.add(key);
  }
  return items;
}
