/**
 * 계산기 패널 배치 규칙. 웹(esbuild 번들 CalculatorLayout)과 앱이 함께 쓴다.
 * - HP 버튼: 4버튼 또는 4×2(8버튼). 4버튼이면 두 번째 줄은 보호막(모든 캐릭터), 보호막 특성은 항상 4버튼 + 보호막 줄.
 * - HP 바: 체력 뒤에 보호막을 파랗게 붙인다.
 * - 패시브: 개수에 따라 크게 1개 / 둘로 나누기 / 목록. 카드 그림 일부를 잘라 아이콘으로 쓴다.
 */
import type { HpButtonMode } from "./calculator-appearance";
import type { TrayItem } from "./calculator-passive-tray";

export const HP_STEPS_4 = [-500, -100, 100, 500];
export const HP_STEPS_8 = [-600, -500, -400, -300, -200, -100, 100, 200];

/** 화면에 보일 HP 버튼 줄. P2는 바깥쪽부터 −가 오도록 거울 배치한다. */
export function hpButtonRows(mode: HpButtonMode | null, hasShield: boolean, mirrored = false): number[][] {
  const rows = mode === "8" && !hasShield ? [HP_STEPS_8.slice(0, 4), HP_STEPS_8.slice(4)] : [HP_STEPS_4];
  return mirrored ? rows.map((row) => [...row].reverse()) : rows;
}

/** 체력 바 비율. 전체 길이는 최대 체력과 (체력 + 보호막) 중 큰 값이다. */
export function hpBar(hp: number, initialHp: number, shield: number) {
  const health = Math.max(0, Number(hp) || 0);
  const guard = Math.max(0, Number(shield) || 0);
  const total = Math.max(Number(initialHp) || 0, health + guard, 1);
  return { hp: health / total, shield: guard / total, ratio: initialHp > 0 ? Math.min(1, health / initialHp) : 1 };
}

export type PassiveLayout = "hero" | "split" | "list";
/** 패시브 개수로 배치를 고른다: 1개 크게, 2개 둘로 나누기, 그 외는 목록. */
export function passiveLayout(items: TrayItem[]): PassiveLayout {
  const groups = passiveGroups(items);
  // 줄로 묶인 항목(양·음 짝, 상태+선택)이 있으면 카드 한두 장으로는 담기지 않으므로 목록으로 쌓는다.
  if (groups.some((group) => group.kind !== "single")) return "list";
  return groups.length <= 1 ? "hero" : groups.length === 2 ? "split" : "list";
}

export type PassiveGroup =
  | { kind: "single"; item: TrayItem }
  | { kind: "pair"; items: [TrayItem, TrayItem] }
  | { kind: "status-choice"; status: TrayItem; choice: TrayItem };
/**
 * 목록 배치의 줄 묶음.
 * - 칸 6개 이하 카운터가 둘 이어지면 한 줄에 반씩 나란히 둔다(타오 양·음).
 * - 자동 상태 바로 뒤의 선택지는 한 줄로 합친다(타오 조화 + 조화 효과).
 */
export function passiveGroups(items: TrayItem[]): PassiveGroup[] {
  const groups: PassiveGroup[] = [];
  for (let i = 0; i < items.length; i += 1) {
    const item = items[i]!;
    const next = items[i + 1];
    const smallCounter = (x?: TrayItem) => x?.kind === "counter" && !!x.max && x.max <= 6;
    if (smallCounter(item) && smallCounter(next) && items.length > 2) {
      groups.push({ kind: "pair", items: [item, next!] });
      i += 1;
    } else if (item.kind === "status" && next?.kind === "choice") {
      groups.push({ kind: "status-choice", status: item, choice: next });
      i += 1;
    } else groups.push({ kind: "single", item });
  }
  return groups;
}

/** 카드 그림에서 잘라낼 영역(카드 폭·높이에 대한 비율). */
export type CardCrop = { x: number; y: number; w: number; h: number };
// 카드 일러스트가 있는 윗부분. 같은 캐릭터의 패시브끼리 서로 다른 부분이 보이도록 순서마다 조금씩 옮긴다.
const DEFAULT_CROPS: CardCrop[] = [
  { x: 0.18, y: 0.14, w: 0.64, h: 0.32 },
  { x: 0.1, y: 0.34, w: 0.64, h: 0.32 },
  { x: 0.26, y: 0.24, w: 0.64, h: 0.32 },
  { x: 0.04, y: 0.08, w: 0.64, h: 0.32 },
];
/** 캐릭터·패시브별로 손본 영역. 비어 있으면 DEFAULT_CROPS를 쓴다. */
export const CARD_CROPS: Record<string, Record<string, CardCrop>> = {};
export function cardCrop(theme: string, key: string, index: number): CardCrop {
  return CARD_CROPS[theme]?.[key] || DEFAULT_CROPS[index % DEFAULT_CROPS.length]!;
}
/** CSS background-size / background-position 값(%)으로 바꾼다. */
/** 토큰 카드의 그림 부분(카드 위쪽 60% 안). */
export const TOKEN_CROP: CardCrop = { x: 0.14, y: 0.1, w: 0.72, h: 0.48 };
export function cropBackground(crop: CardCrop) {
  const position = (offset: number, size: number) => (size >= 1 ? 0 : (offset / (1 - size)) * 100);
  return {
    // 폭만 맞추고 높이는 비율대로 둔다(칸 모양이 달라도 그림이 찌그러지지 않게).
    size: `${(100 / crop.w).toFixed(2)}% auto`,
    position: `${position(crop.x, crop.w).toFixed(2)}% ${position(crop.y, crop.h).toFixed(2)}%`,
  };
}
/** 패시브 그림으로 쓸 카드 그림 주소: 특성 카드(웹·공유) → 카탈로그 특성. */
export function passiveCardImage(character: any): string {
  return String(character?.passive_cards?.[0]?.img || character?.trait_img || "");
}

/** 계산기에서 다루기 쉬운 최대 개수(불빛 수). 서버 mobile_api/passives.py의 COUNTER_MAX_OVERRIDES와 같다. */
export const COUNTER_MAX_OVERRIDES: Record<string, number> = { foresight_counter: 5 };
const TOKEN_NAME_NOISE = /[「」『』【】[\]()\s]|토큰/g;
export function tokenName(text: unknown): string {
  return String(text ?? "").replace(TOKEN_NAME_NOISE, "");
}
type TokenCard = { id: number; code?: string | null; character_id?: number; type?: string; img?: string; original_name?: string; localized?: Record<string, any> };
/**
 * 앱 카탈로그만으로 서버와 같은 보정을 한다(서버가 아직 붙이지 않은 예전 카탈로그 대비).
 * 카운터 이름(한국어)에 그 캐릭터 토큰 카드 이름이 들어 있으면 카드 그림을 붙이고, 최대 개수를 보정한다.
 */
export function withCalculatorExtras<T extends { controls?: any[] }>(
  definition: T,
  characterId: number | undefined,
  cards: TokenCard[] | undefined,
  koreanLabels: Record<string, string> = {},
): T {
  const controls = definition?.controls;
  if (!Array.isArray(controls) || !controls.length) return definition;
  const tokens = (cards || [])
    .filter((card) => characterId && card.character_id === characterId && String(card.type || "").includes("토큰") && card.img)
    .map((card) => ({ name: tokenName(card.localized?.ko?.name ?? card.original_name), card }))
    .filter((entry) => entry.name)
    .sort((a, b) => b.name.length - a.name.length);
  let changed = false;
  const next = controls.map((control) => {
    if (!control || typeof control !== "object") return control;
    let result = control;
    const max = COUNTER_MAX_OVERRIDES[control.key];
    if (max != null && control.max !== max) result = { ...result, max };
    if (control.type === "counter" && !control.token && tokens.length) {
      const label = tokenName(koreanLabels[control.key] ?? control.label);
      const match = tokens.find((entry) => label.includes(entry.name));
      if (match) result = { ...result, token: { id: match.card.id, code: match.card.code || "", img: match.card.img } };
    }
    if (result !== control) changed = true;
    return result;
  });
  return changed ? { ...definition, controls: next } : definition;
}
