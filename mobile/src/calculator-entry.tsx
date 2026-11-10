import { useCallback } from "react";
import type { CalculatorUi } from "./calculator-ui";

/**
 * 계산기 화면은 하나로 합쳐져 고를 UI가 없다. 기존 호출부(홈·파티·대회)가 그대로 쓰도록
 * 같은 모양을 유지하고 바로 통합 계산기를 고른다. 배경(일러스트/단색)은 계산기 설정에서 바꾼다.
 */
export function useCalculatorEntry() {
  const chooseUi = useCallback(
    (): Promise<CalculatorUi | null> => Promise.resolve("character"),
    [],
  );
  return { chooseUi, entrySheet: null };
}
