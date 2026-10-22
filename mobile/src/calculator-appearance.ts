/** Device presentation only: never included in a battle action or session. */
export type CalculatorAppearance = {
  style: "illustrated" | "clean";
  brightness: number;
};
export const appearanceKey = "lumengg-calculator-appearance-v1";
export const defaultAppearance: CalculatorAppearance = {
  style: "illustrated",
  brightness: 35,
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
  return { style: raw.style === "clean" ? "clean" : "illustrated", brightness };
}
