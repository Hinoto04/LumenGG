import { t } from "./i18n";
import type { MatchView, Side } from "./protocol";

/** 퀵 매치 진행 방식. 서버: battlelog/play_match.py */
export type MatchFormat = MatchView["format"];

export const MATCH_FORMATS: [MatchFormat, string, string][] = [
  ["single", t("단판"), t("한 판으로 끝납니다")],
  ["bo3", t("매치"), t("3판 2선승")],
  ["endless", t("무한"), t("원할 때까지 이어 합니다")],
];

export function matchFormatLabel(format: MatchFormat): string {
  if (format === "bo3") return t("매치(3판 2선승)");
  return format === "single" ? t("단판") : t("무한");
}

/** "매치(3판 2선승) · 1 : 0" — 내 승수를 앞에 둔다(관전자는 P1 : P2). */
export function matchScoreText(match: MatchView, me: Side): string {
  const opp: Side = me === "p1" ? "p2" : "p1";
  const label = matchFormatLabel(match.format);
  if (match.format === "single") return label;
  return `${label} · ${match.wins[me]} : ${match.wins[opp]}`;
}
