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

export type ActiveCardFilter =
  | { kind: "value"; key: "character" | "type" | "pos"; value: string }
  | { kind: "range"; key: "frame" | "damage"; min: string; max: string };

/** 적용된 필터를 칩으로 보여 주기 위한 목록. 빈 조건은 넣지 않는다. */
export function activeCardFilters(filters: CardFilters): ActiveCardFilter[] {
  const active: ActiveCardFilter[] = [];
  for (const key of ["character", "type", "pos"] as const)
    if (filters[key]) active.push({ kind: "value", key, value: filters[key] });
  if (filters.frameMin || filters.frameMax)
    active.push({
      kind: "range",
      key: "frame",
      min: filters.frameMin,
      max: filters.frameMax,
    });
  if (filters.damageMin || filters.damageMax)
    active.push({
      kind: "range",
      key: "damage",
      min: filters.damageMin,
      max: filters.damageMax,
    });
  return active;
}

/** 칩 하나를 지웠을 때의 필터. 범위 필터는 최소·최대를 함께 지운다. */
export function withoutCardFilter(
  filters: CardFilters,
  key: ActiveCardFilter["key"],
): CardFilters {
  if (key === "frame") return { ...filters, frameMin: "", frameMax: "" };
  if (key === "damage") return { ...filters, damageMin: "", damageMax: "" };
  return { ...filters, [key]: "" };
}

/** 범위 필터를 "3–5", "3 이상", "5 이하" 꼴로 줄인다. */
export function rangeLabel(
  min: string,
  max: string,
  t: (key: string) => string,
): string {
  if (min && max) return min === max ? min : `${min}–${max}`;
  return min ? `${min} ${t("이상")}` : `${max} ${t("이하")}`;
}
