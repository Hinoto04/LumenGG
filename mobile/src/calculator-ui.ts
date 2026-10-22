import themes from "./calculator-themes.json";
import type { CalculatorTheme } from "./types";
export type CalculatorUi = "classic" | "character";
export function calculatorUi(value: unknown): CalculatorUi {
  return value === "character" ? "character" : "classic";
}
export function calculatorLink(value: string, ui: CalculatorUi): string {
  const absolute = /^https?:\/\//i.test(value);
  const url = new URL(value, "https://calculator.invalid");
  url.searchParams.delete("ui");
  if (ui === "character") url.searchParams.set("ui", "character");
  return absolute ? url.toString() : url.pathname + url.search + url.hash;
}
export function linkedCalculatorUi(value: string): CalculatorUi | undefined {
  try {
    const url = new URL(value, "https://calculator.invalid");
    return url.searchParams.has("ui")
      ? calculatorUi(url.searchParams.get("ui"))
      : undefined;
  } catch {
    return undefined;
  }
}
export function calculatorTheme(
  character:
    { id?: number; calculator_ui?: CalculatorTheme | null } | null | undefined,
): CalculatorTheme {
  const supplied = character?.calculator_ui;
  const known = themes.find((item) =>
    supplied?.theme_key
      ? item.theme_key === supplied.theme_key
      : item.id === character?.id,
  );
  if (!known)
    return {
      theme_key: "default",
      accent: "#a6b8d4",
      secondary: "#e8eff9",
      motif: "crest",
    };
  return {
    theme_key: known.theme_key,
    accent: known.accent,
    secondary: known.secondary,
    motif: known.motif,
  };
}
