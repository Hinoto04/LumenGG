/**
 * 사람끼리 대전(방 · 퀵 매치)의 응답 모양과 화면 표시 규칙. 네이티브 모듈 없이 테스트한다.
 * 서버: battlelog/play_rooms.py, 앱 API: /api/mobile/v1/simulator/rooms·quick
 */

export type RoomKind = "room" | "quick";

export interface RoomSeat {
  present: boolean;
  name: string;
  /** 내 덱이면 id·name이 있고, 상대 덱은 캐릭터만 보인다 */
  deck: { character: string; id?: number; name?: string } | null;
  ready: boolean;
  me: boolean;
}

export interface RoomOptions {
  mode?: string;
  ready_timeout_seconds?: number;
  effect_timeout_seconds?: number;
}

export interface RoomView {
  code: string;
  kind: RoomKind;
  status: "waiting" | "started" | "closed";
  options: RoomOptions;
  seat: "host" | "guest" | null;
  seats: { host: RoomSeat; guest: RoomSeat };
  error: string;
  /** 대전이 시작되면 내 좌석 주소(절대 주소) */
  play_url?: string;
  /** 방 초대 링크(사이트 로비) */
  invite_url?: string;
}

export interface RoomResponse {
  ok: boolean;
  token: string;
  room: RoomView;
}

/** 이 기기가 참가 중인 방. 화면을 떠났다 와도 이어진다. */
export interface JoinedRoom {
  code: string;
  token: string;
  kind: RoomKind;
}

/** 방 코드 입력 정리: 대문자, 영문·숫자만, 최대 8자 */
export function normalizeRoomCode(text: string): string {
  return text.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);
}

export function mySeat(room: RoomView): RoomSeat {
  return room.seat === "guest" ? room.seats.guest : room.seats.host;
}

function seconds(value: number | undefined): string {
  return value ? `${value}초` : "제한 없음";
}

/** 방 규칙 한 줄 요약 */
export function roomOptionsText(options: RoomOptions): string {
  if (options.mode === "manual") return "수동(샌드박스)";
  return `자동 판정 · 레디 ${seconds(options.ready_timeout_seconds)} · 효과 선택 ${seconds(options.effect_timeout_seconds)}`;
}

/** 자리 카드의 덱 표시. 상대에게는 캐릭터만 보인다. */
export function seatDeckText(seat: RoomSeat): string {
  if (!seat.present) return "상대를 기다리는 중…";
  if (!seat.deck) return "덱을 고르는 중";
  return seat.me && seat.deck.name ? `${seat.deck.character} · ${seat.deck.name}` : `${seat.deck.character} 덱`;
}

/** 응답을 받은 뒤 할 일: 계속 기다림 / 대전 열기 / 방이 닫힘 */
export function roomOutcome(room: RoomView): { kind: "wait" } | { kind: "play"; url: string } | { kind: "closed" } {
  if (room.status === "closed") return { kind: "closed" };
  if (room.status === "started" && room.play_url) return { kind: "play", url: room.play_url };
  return { kind: "wait" };
}
