import type { Side } from "./protocol";

/** 접속할 자동 판정 세션. 좌석 없이 view 토큰만 있으면 관전이다. */
export interface LiveTarget {
  view: string;
  seat: Side | "";
  token: string;
}

export type AppMode = { kind: "fixtures" } | { kind: "live"; target: LiveTarget } | { kind: "lobby" };

/**
 * URL로 화면을 고른다.
 *   ?game=<view_token>&seat=p1&token=<seat_token>  실제 대전(좌석 생략 시 관전)
 *   ?fixtures#step=3&role=p1                         픽스처 보기(개발)
 *   (없음)                                           새 대전 만들기
 */
export function readMode(search = location.search): AppMode {
  const query = new URLSearchParams(search);
  if (query.has("fixtures")) return { kind: "fixtures" };
  const view = query.get("game");
  if (view) {
    const seat = query.get("seat");
    const token = query.get("token") ?? "";
    return {
      kind: "live",
      target: { view, seat: (seat === "p1" || seat === "p2") && token ? seat : "", token },
    };
  }
  return { kind: "lobby" };
}

export function liveUrl(target: LiveTarget): string {
  const query = new URLSearchParams({ game: target.view });
  if (target.seat && target.token) {
    query.set("seat", target.seat);
    query.set("token", target.token);
  }
  return `${location.pathname}?${query}`;
}
