import themes from "./calculator-themes.json";
import type { CalculatorTheme } from "./types";
/** 계산기 화면은 하나다. "classic"은 예전 링크와 저장값을 읽기 위해서만 남긴다. */
export type CalculatorUi = "classic" | "character";
export function calculatorUi(_value?: unknown): CalculatorUi {
  return "character";
}
/** 예전 ?ui= 선택값을 걷어낸 링크. 역할 토큰·다른 쿼리·조각은 그대로 둔다. */
export function calculatorLink(value: string, _ui?: CalculatorUi): string {
  const absolute = /^https?:\/\//i.test(value);
  const url = new URL(value, "https://calculator.invalid");
  url.searchParams.delete("ui");
  url.searchParams.delete("choose_ui");
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
