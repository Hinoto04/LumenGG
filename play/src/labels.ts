import type { Phase, ZoneName } from "./protocol";

export const PHASE_ORDER: Phase[] = ["lumen", "ready", "battle", "get", "recovery"];

export const PHASE_LABELS: Record<string, string> = {
  lumen: "루멘",
  ready: "레디",
  battle: "배틀",
  get: "겟",
  recovery: "리커버리",
};

export const ZONE_LABELS: Record<ZoneName, string> = {
  character: "캐릭터",
  passive: "패시브",
  battle: "배틀",
  list: "리스트",
  hand: "손패",
  side: "사이드",
  break: "브레이크",
  lumen: "루멘",
  ultimate: "얼티밋",
};

/** 보드 옆에 더미로 접어 두는 존. 순서대로 그린다. */
export const PILE_ZONES: ZoneName[] = ["lumen", "break", "ultimate", "side", "passive"];

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
  hp_zero: "HP가 0이 되었습니다",
  concede: "기권",
  no_response_disqualification: "사용 가능한 카드 없음을 3번 선언해 실격되었습니다",
  sudden_death: "서든 데스로 승부가 났습니다",
  sudden_death_hp_tie_draw: "서든 데스에서 HP가 같아 무승부입니다",
  sudden_death_simultaneous_zero_draw: "양쪽 HP가 동시에 0이 되어 무승부입니다",
  card_effect: "카드 효과로 승부가 났습니다",
};
