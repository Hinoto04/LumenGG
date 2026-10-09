import type { Card } from "./types";

export interface CardFilters {
  character: string;
  type: string;
  pos: string;
  frameMin: string;
  frameMax: string;
  damageMin: string;
  damageMax: string;
}
export const emptyCardFilters: CardFilters = {
  character: "",
  type: "",
  pos: "",
  frameMin: "",
  frameMax: "",
  damageMin: "",
  damageMax: "",
};
export function filterError(filters: CardFilters): string | null {
  for (const [min, max] of [
    [filters.frameMin, filters.frameMax],
    [filters.damageMin, filters.damageMax],
  ] as const) {
    if (
      [min, max].some(
        (v) =>
          v !== "" && (!/^-?\d+$/.test(v) || !Number.isSafeInteger(Number(v))),
      )
    )
      return "필터 수치는 정수로 입력해주세요.";
    if (min !== "" && max !== "" && Number(min) > Number(max))
      return "최소값은 최대값보다 클 수 없습니다.";
  }
  return null;
}
export function matchesCardFilters(card: Card, filters: CardFilters): boolean {
  const range = (value: number | null, min: string, max: string) =>
    (min === "" || (value !== null && value >= Number(min))) &&
    (max === "" || (value !== null && value <= Number(max)));
  return (
    (!filters.character || String(card.character_id) === filters.character) &&
    (!filters.type || card.type === filters.type) &&
    (!filters.pos || card.pos === filters.pos) &&
    range(card.frame, filters.frameMin, filters.frameMax) &&
    range(card.damage, filters.damageMin, filters.damageMax)
  );
}
export function activeFilterCount(filters: CardFilters): number {
  return (
    Number(!!filters.character) +
    Number(!!filters.type) +
    Number(!!filters.pos) +
    Number(!!(filters.frameMin || filters.frameMax)) +
    Number(!!(filters.damageMin || filters.damageMax))
  );
}
