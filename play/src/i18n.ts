import { EN } from "./i18n/en";
import { JA } from "./i18n/ja";

/**
 * 대전 클라이언트 화면 문구의 다국어 처리.
 *
 * 언어는 페이지를 열 때 한 번 정한다(사이트에서 언어를 바꾸면 페이지를 다시 연다).
 *   1. 주소의 ?lang=  (앱 WebView가 앱 언어를 넘긴다)
 *   2. <html lang>     (서버가 사이트 언어 설정으로 채운다)
 *   3. 한국어
 *
 * 문구는 한국어 원문을 키로 쓰고, 영어·일본어 사전(i18n/en.ts, i18n/ja.ts)에서 찾는다.
 * 사전에 없으면 원문(한국어)을 그대로 보여 준다. {name} 꼴의 자리표시자를 값으로 바꾼다.
 * 카드 이름·효과문·선택지처럼 서버가 보내는 문구는 서버가 같은 언어로 옮겨 보낸다.
 */
export type Language = "ko" | "en" | "ja";

const SUPPORTED: Language[] = ["ko", "en", "ja"];

function normalize(value: string | null | undefined): Language | null {
  const code = String(value ?? "").trim().toLowerCase().slice(0, 2);
  return (SUPPORTED as string[]).includes(code) ? (code as Language) : null;
}

function detect(): Language {
  if (typeof window === "undefined") return "ko";
  return (
    normalize(new URLSearchParams(window.location.search).get("lang")) ??
    normalize(document.documentElement.getAttribute("lang")) ??
    "ko"
  );
}

export const LANGUAGE: Language = detect();

const DICTIONARIES: Record<Language, Record<string, string>> = { ko: {}, en: EN, ja: JA };

type Vars = Record<string, string | number | null | undefined>;

function fill(text: string, vars?: Vars): string {
  if (!vars) return text;
  return text.replace(/\{(\w+)\}/g, (match, key: string) => (key in vars ? String(vars[key] ?? "") : match));
}

/** 화면 문구. t("손패 {n}장", { n: 3 }) */
export function t(source: string, vars?: Vars): string {
  const translated = LANGUAGE === "ko" ? source : DICTIONARIES[LANGUAGE][source] ?? source;
  return fill(translated, vars);
}

/** 숫자 + 단위(장, 턴 …)처럼 언어마다 복수형이 다른 짧은 문구. */
export function plural(n: number, ko: string, en: [string, string], ja: string): string {
  if (LANGUAGE === "en") return fill(n === 1 ? en[0] : en[1], { n });
  if (LANGUAGE === "ja") return fill(ja, { n });
  return fill(ko, { n });
}

/** "3장" · "3 cards" · "3枚" */
export function cardCount(n: number): string {
  return plural(n, "{n}장", ["{n} card", "{n} cards"], "{n}枚");
}

/** "5초" · "5s" · "5秒" */
export function seconds(n: number): string {
  return plural(n, "{n}초", ["{n}s", "{n}s"], "{n}秒");
}
