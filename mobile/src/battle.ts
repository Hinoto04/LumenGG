import { BASE_URL, request } from "./api";
import type { JoinedRoom, RoomResponse } from "./battle-room";
import { preference, setPreference } from "./storage";

/**
 * 자동 판정 대전(시뮬레이터). 덱은 앱에서 고르고, 대전 화면은 사이트의 게임 클라이언트
 * (/battlelog/play/)를 WebView로 연다. 좌석 토큰이 주소에 들어 있어 WebView에 로그인이 필요 없다.
 */

export type Opponent = "ai" | "human";

export type BattleMode = "automatic" | "manual";

export interface BattleRequest {
  p1_deck: number;
  p2_deck: number;
  opponent: Opponent;
  /** manual은 사람끼리만. 규칙 판정 없이 직접 조작하는 샌드박스 */
  mode: BattleMode;
  ready_timeout_seconds: number;
  effect_timeout_seconds: number;
}

export interface BattleSession {
  view_token: string;
  seats: { p1: string; p2?: string };
  urls: { p1: string; p2?: string; viewer: string };
}

export async function createBattle(body: BattleRequest): Promise<BattleSession> {
  return request("/simulator/sessions", { method: "POST", body: JSON.stringify(body) });
}

// ---------------------------------------------------------------------------
// 사람끼리 대전: 방(코드로 참가)과 퀵 매치. 각자 자기 덱만 고른다. 자리 토큰은 본문 `token`으로만 보낸다.

const roomPath = (code: string, action: string) => `/simulator/rooms/${encodeURIComponent(code)}/${action}`;

function post(path: string, body: Record<string, unknown>): Promise<RoomResponse> {
  return request(path, { method: "POST", body: JSON.stringify(body) });
}

export interface RoomCreateRequest {
  deck_id?: number;
  mode: BattleMode;
  ready_timeout_seconds: number;
  effect_timeout_seconds: number;
}

export const createRoom = (body: RoomCreateRequest) => post("/simulator/rooms", { ...body });
export const joinRoom = (code: string, deckId?: number) => post(roomPath(code, "join"), { deck_id: deckId });
export const roomState = (room: JoinedRoom) => post(roomPath(room.code, "state"), { token: room.token });
export const chooseRoomDeck = (room: JoinedRoom, deckId: number) =>
  post(roomPath(room.code, "deck"), { token: room.token, deck_id: deckId });
export const setRoomReady = (room: JoinedRoom, ready: boolean) =>
  post(roomPath(room.code, "ready"), { token: room.token, ready });
export const leaveRoom = (room: JoinedRoom) => post(roomPath(room.code, "leave"), { token: room.token });
export const quickMatch = (deckId: number) => post("/simulator/quick", { deck_id: deckId });

const ROOM_KEY = "battle.room";

export async function joinedRoom(): Promise<JoinedRoom | null> {
  const saved = await preference<JoinedRoom | null>(ROOM_KEY, null);
  return saved?.code && saved?.token ? saved : null;
}

export function rememberRoom(room: JoinedRoom | null) {
  return setPreference(ROOM_KEY, room);
}

/** 공개 덱 검색(상대 덱 고르기용) */
export interface PublicDeck {
  id: number;
  name: string;
  character_id: number;
  author?: { username: string };
}

export async function searchPublicDecks(query: string): Promise<PublicDeck[]> {
  const params = new URLSearchParams({ scope: "public", q: query.trim() });
  const data = await request(`/decks?${params}`, {}, false);
  return (data?.decks ?? []) as PublicDeck[];
}

/** 게임 화면 WebView 안에서의 이동 처리(battle-nav.ts) */
export const SITE_ORIGIN = BASE_URL.replace(/^(https?:\/\/[^/]+).*$/, "$1");

// ---------------------------------------------------------------------------
// 이어하기: 마지막 좌석 주소를 기억한다(사이트 세션은 하루 안팎으로 만료).

const LAST_KEY = "battle.last";
const KEEP_MS = 24 * 3600 * 1000;

export interface LastBattle {
  url: string;
  savedAt: number;
  label: string;
}

export async function lastBattle(): Promise<LastBattle | null> {
  const saved = await preference<LastBattle | null>(LAST_KEY, null);
  return saved && Date.now() - saved.savedAt < KEEP_MS ? saved : null;
}

export function rememberBattle(url: string, label: string) {
  return setPreference(LAST_KEY, { url, label, savedAt: Date.now() } satisfies LastBattle);
}
