/**
 * 다국어용 의미 마크업([[card:CODE]], [[state:charge]], [[token-card:...]] 등)의 마지막 안전망.
 *
 * 서버가 보내기 전에 모두 표시 문자열로 렌더한다(simulator_services._render_payload_markup).
 * 그래도 남은 것(예전 데이터, 렌더 전에 캐시된 상태)은 서버의 UNRESOLVED_MARKUP_RE와 같은 규칙으로
 * 종류를 떼고 이름만 남겨, 대괄호 표기가 화면에 그대로 나오지 않게 한다.
 */
const MARKUP = /\[\[(?:[^:[\]]+:)?([^[\]]+)\]\]/g;

export function plainMarkup(text: unknown): string {
  const value = String(text ?? "");
  if (!value.includes("[[")) return value;
  return value.replace(MARKUP, (_match, slug: string) => slug.trim().replace(/_/g, " "));
}
