import type { Phase, ZoneName } from "./protocol";
import { t } from "./i18n";

export const PHASE_ORDER: Phase[] = ["lumen", "ready", "battle", "get", "recovery"];

export const PHASE_LABELS: Record<string, string> = {
  lumen: t("루멘"),
  ready: t("레디"),
  battle: t("배틀"),
  get: t("겟"),
  recovery: t("리커버리"),
};

export const ZONE_LABELS: Record<ZoneName, string> = {
  character: t("캐릭터"),
  passive: t("패시브"),
  battle: t("배틀"),
  list: t("리스트"),
  hand: t("손패"),
  side: t("사이드"),
  break: t("브레이크"),
  lumen: t("루멘"),
  ultimate: t("얼티밋"),
};

/** 보드 옆에 더미로 접어 두는 존. 순서대로 그린다. */
/** 장 수로 보이는 더미(필드 바깥쪽). */
export const PILE_ZONES: ZoneName[] = ["lumen", "break", "side"];
/** 한 장뿐이라 카드 앞면으로 보이는 존. 가로 화면은 캐릭터 패널과 배틀존 사이, 세로 화면은 더미 줄 앞에 놓는다. */
export const SINGLE_ZONES: ZoneName[] = ["passive", "ultimate"];

export function cardTypeClass(type: unknown): string {
  const value = String(type ?? "");
  if (value.includes("공격")) return "type-attack";
  if (value.includes("수비") || value.includes("방어")) return "type-defense";
  if (value.includes("기술")) return "type-technique";
  if (value.includes("특수") || value.includes("얼티")) return "type-special";
  return "type-other";
}

/** engine_status.reason → 종료 사유 문구 */
export const FINISH_REASONS: Record<string, string> = {
  hp_zero: t("HP가 0이 되었습니다"),
  concede: t("기권"),
  no_response_disqualification: t("사용 가능한 카드 없음을 3번 선언해 실격되었습니다"),
  sudden_death: t("서든 데스로 승부가 났습니다"),
  sudden_death_hp_tie_draw: t("서든 데스에서 HP가 같아 무승부입니다"),
  sudden_death_simultaneous_zero_draw: t("양쪽 HP가 동시에 0이 되어 무승부입니다"),
  card_effect: t("카드 효과로 승부가 났습니다"),
};
