export type WebNavigation = "allow" | "close" | "external";

/**
 * 게임 화면(WebView) 안의 링크 처리.
 * - 같은 사이트의 대전(/battlelog/play/?game=...)과 수동 모드 시뮬레이터는 WebView 안에서 연다.
 * - 대전 클라이언트의 로비('나가기', '새 대전')는 앱의 대전 화면으로 돌아간다.
 * - 그 밖의 주소는 바깥 브라우저로 연다.
 */
export function classifyNavigation(url: string, origin: string): WebNavigation {
  if (url === "about:blank") return "allow";
  if (!url.startsWith(origin + "/")) return "external";
  const path = url.slice(origin.length);
  if (path.startsWith("/battlelog/play/")) return /[?&]game=/.test(path) ? "allow" : "close";
  if (path.startsWith("/battlelog/simulator/")) return "allow";
  return "external";
}
