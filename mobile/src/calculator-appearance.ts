/** Device presentation only: never included in a battle action or session. */
export type HpButtonMode = "4" | "8";
export type CalculatorAppearance = {
  style: "illustrated" | "clean";
  brightness: number;
  /** HP 버튼 방식. null이면 아직 고르지 않아 처음 접속 때 묻는다. */
  hpButtons: HpButtonMode | null;
};
export const appearanceKey = "lumengg-calculator-appearance-v1";
export const defaultAppearance: CalculatorAppearance = {
  style: "illustrated",
  brightness: 35,
  hpButtons: null,
};
export function calculatorAppearance(value: unknown): CalculatorAppearance {
  const raw =
    value && typeof value === "object"
      ? (value as Record<string, unknown>)
      : {};
  const brightness =
    typeof raw.brightness === "number" && Number.isFinite(raw.brightness)
      ? Math.round(Math.max(0, Math.min(100, raw.brightness)))
      : defaultAppearance.brightness;
  const hpButtons = raw.hpButtons === "4" || raw.hpButtons === "8" ? raw.hpButtons : null;
  return { style: raw.style === "clean" ? "clean" : "illustrated", brightness, hpButtons };
}
