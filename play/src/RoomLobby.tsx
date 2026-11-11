import { useCallback, useEffect, useRef, useState } from "react";
import { DeckPicker, TimerSelect, type DeckRow } from "./Lobby";
import { postJson } from "./net/http";

/**
 * 사람끼리 대전: 방(코드로 참가)과 퀵 매치. 각 플레이어는 자기 덱만 고른다.
 * 서버: battlelog/play_rooms.py. 자리 토큰은 이 브라우저에만 보관하고 POST 본문으로만 보낸다.
 */

interface SeatView {
  present: boolean;
  name: string;
  deck: { character: string; id?: number; name?: string } | null;
  ready: boolean;
  me: boolean;
}

export interface RoomView {
  code: string;
  kind: "room" | "quick";
  status: "waiting" | "started" | "closed";
  options: { mode?: string; ready_timeout_seconds?: number; effect_timeout_seconds?: number };
  seat: "host" | "guest" | null;
  seats: { host: SeatView; guest: SeatView };
  error: string;
  play_url?: string;
}

interface RoomResponse {
  ok: boolean;
  token: string;
  room: RoomView;
}

const ROOM_KEY = "lumen-play-room";
const POLL_MS = 1500;

interface StoredRoom {
  code: string;
  token: string;
  kind: "room" | "quick";
}

function storedRoom(): StoredRoom | null {
  try {
    const value = JSON.parse(localStorage.getItem(ROOM_KEY) ?? "null") as StoredRoom | null;
    return value?.code && value?.token ? value : null;
  } catch {
    return null;
  }
}

function storeRoom(value: StoredRoom | null) {
  try {
    if (value) localStorage.setItem(ROOM_KEY, JSON.stringify(value));
    else localStorage.removeItem(ROOM_KEY);
  } catch {
    /* 저장하지 못하면 새로고침 때 방을 다시 찾지 못할 뿐이다 */
  }
}

/** 이 브라우저가 참가 중인 방(새로고침해도 이어진다) */
export function rememberedRoom(kind: "room" | "quick"): StoredRoom | null {
  const room = storedRoom();
  return room?.kind === kind ? room : null;
}

const api = (code: string, action: string) => `/battlelog/play/api/rooms/${encodeURIComponent(code)}/${action}/`;

/** 참가 중인 방(퀵 매치 포함)을 주기적으로 갱신하고, 대전이 시작되면 내 좌석으로 옮긴다. */
function useRoom(initial: StoredRoom | null) {
  const [joined, setJoined] = useState<StoredRoom | null>(initial);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const leaving = useRef(false);

  const apply = useCallback((data: RoomResponse, kind: "room" | "quick") => {
    const next = { code: data.room.code, token: data.token, kind };
    setJoined(next);
    setRoom(data.room);
    if (data.room.status === "closed") {
      storeRoom(null);
      return;
    }
    storeRoom(next);
    if (data.room.status === "started" && data.room.play_url) {
      storeRoom(null);
      location.assign(data.room.play_url);
    }
  }, []);

  useEffect(() => {
    if (!joined) return;
    let alive = true;
    const tick = async () => {
      try {
        const data = await postJson<RoomResponse>(api(joined.code, "state"), { token: joined.token });
        if (alive && !leaving.current) apply(data, joined.kind);
      } catch (exception) {
        if (alive) setError((exception as Error).message);
      }
    };
    void tick();
    const timer = setInterval(tick, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [joined?.code, joined?.token]); // eslint-disable-line react-hooks/exhaustive-deps

  const call = async (action: string, body: Record<string, unknown> = {}) => {
    if (!joined) return;
    setError(null);
    try {
      apply(await postJson<RoomResponse>(api(joined.code, action), { token: joined.token, ...body }), joined.kind);
    } catch (exception) {
      setError((exception as Error).message);
    }
  };

  const leave = async () => {
    if (!joined) return;
    leaving.current = true;
    try {
      await postJson(api(joined.code, "leave"), { token: joined.token });
    } catch {
      /* 이미 닫힌 방이어도 화면에서는 나간다 */
    }
    storeRoom(null);
    setJoined(null);
    setRoom(null);
    leaving.current = false;
  };

  return { joined, room, error, setError, apply, call, leave };
}

function SeatCard({ seat, label }: { seat: SeatView; label: string }) {
  return (
    <div className={`room-seat ${seat.me ? "is-me" : ""} ${seat.ready ? "is-ready" : ""}`}>
      <span className="room-seat-label">{label}</span>
      {seat.present ? (
        <>
          <b>{seat.name || "플레이어"}</b>
          <span className="muted">
            {seat.deck ? (seat.me ? `${seat.deck.character} · ${seat.deck.name ?? ""}` : `${seat.deck.character} 덱`) : "덱을 고르는 중"}
          </span>
          <span className={`room-ready ${seat.ready ? "is-on" : ""}`}>{seat.ready ? "준비 완료" : "준비 전"}</span>
        </>
      ) : (
        <span className="muted">상대를 기다리는 중…</span>
      )}
    </div>
  );
}

/** 방 만들기 · 코드로 참가 · 대기실 */
export function RoomPanel({ mine, loginRequired }: { mine: DeckRow[]; loginRequired: boolean }) {
  const invited = new URLSearchParams(location.search).get("room")?.toUpperCase() ?? "";
  const remembered = rememberedRoom("room");
  const { joined, room, error, setError, apply, call, leave } = useRoom(
    remembered && (!invited || remembered.code === invited) ? remembered : null,
  );
  const [deck, setDeck] = useState<DeckRow | null>(null);
  const [mode, setMode] = useState<"automatic" | "manual">("automatic");
  const [readyTimer, setReadyTimer] = useState(10);
  const [effectTimer, setEffectTimer] = useState(30);
  const [code, setCode] = useState(invited);
  const [busy, setBusy] = useState(false);
  const [copied, setCopied] = useState(false);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      apply(
        await postJson<RoomResponse>("/battlelog/play/api/rooms/", {
          deck_id: deck?.id,
          mode,
          ready_timeout_seconds: readyTimer,
          effect_timeout_seconds: effectTimer,
        }),
        "room",
      );
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const join = async () => {
    const target = code.trim().toUpperCase();
    if (!target) return;
    setBusy(true);
    setError(null);
    try {
      apply(await postJson<RoomResponse>(api(target, "join"), { deck_id: deck?.id }), "room");
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (joined && room && room.status !== "closed") {
    const me = room.seat === "guest" ? room.seats.guest : room.seats.host;
    const link = `${location.origin}/battlelog/simulator/?room=${room.code}`;
    const copy = async () => {
      try {
        await navigator.clipboard.writeText(link);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        setCopied(false);
      }
    };
    return (
      <section className="lobby-card room-card">
        <div className="room-head">
          <span className="muted">방 코드</span>
          <strong className="room-code">{room.code}</strong>
          <button type="button" className="btn-secondary" onClick={copy}>
            {copied ? "복사됨" : "초대 링크 복사"}
          </button>
        </div>
        <p className="muted">
          {room.options.mode === "manual" ? "수동(샌드박스)" : "자동 판정"}
          {room.options.mode !== "manual" &&
            ` · 레디 ${room.options.ready_timeout_seconds ? `${room.options.ready_timeout_seconds}초` : "제한 없음"} · 효과 선택 ${
              room.options.effect_timeout_seconds ? `${room.options.effect_timeout_seconds}초` : "제한 없음"
            }`}
        </p>
        <div className="room-seats">
          <SeatCard seat={room.seats.host} label="방장 (P1)" />
          <SeatCard seat={room.seats.guest} label="참가자 (P2)" />
        </div>
        {room.status === "started" ? (
          <p>대전을 시작합니다…</p>
        ) : (
          <>
            <DeckPicker
              label="내 덱"
              value={deck ?? (me.deck?.id ? ({ id: me.deck.id, name: me.deck.name ?? "", character: me.deck.character } as DeckRow) : null)}
              onChange={(chosen) => {
                setDeck(chosen);
                void call("deck", { deck_id: chosen.id });
              }}
              mine={mine}
              loginRequired={loginRequired}
            />
            <div className="lobby-row">
              <button type="button" className="btn-ghost" onClick={leave}>
                {room.seat === "host" ? "방 닫기" : "나가기"}
              </button>
              <button
                type="button"
                className={me.ready ? "btn-secondary" : "btn-primary"}
                disabled={!me.deck}
                onClick={() => call("ready", { ready: !me.ready })}
              >
                {me.ready ? "준비 취소" : "준비 완료"}
              </button>
            </div>
            <p className="muted">두 플레이어가 모두 덱을 고르고 준비하면 대전이 시작됩니다.</p>
          </>
        )}
        {(room.error || error) && <p className="lobby-error">{room.error || error}</p>}
      </section>
    );
  }

  return (
    <section className="lobby-card">
      {joined && room?.status === "closed" && <p className="lobby-error">방이 닫혔습니다.</p>}
      <DeckPicker label="내 덱" value={deck} onChange={setDeck} mine={mine} loginRequired={loginRequired} />
      <div className="room-split">
        <div className="room-box">
          <h2>방 만들기</h2>
          <div className="lobby-row segmented" role="radiogroup" aria-label="대전 방식">
            {(
              [
                ["automatic", "자동 판정"],
                ["manual", "수동(샌드박스)"],
              ] as const
            ).map(([value, label]) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={mode === value}
                className={mode === value ? "is-active" : ""}
                onClick={() => setMode(value)}
              >
                {label}
              </button>
            ))}
          </div>
          {mode === "automatic" && (
            <div className="lobby-row lobby-timers">
              <TimerSelect label="레디 제한" value={readyTimer} onChange={setReadyTimer} />
              <TimerSelect label="효과 선택 제한" value={effectTimer} onChange={setEffectTimer} />
            </div>
          )}
          <button type="button" className="btn-primary" disabled={busy} onClick={create}>
            방 만들기
          </button>
        </div>
        <div className="room-box">
          <h2>코드로 참가</h2>
          <div className="room-join">
            <input
              className="room-code-input"
              value={code}
              maxLength={8}
              placeholder="방 코드"
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              aria-label="방 코드"
            />
            <button type="button" className="btn-primary" disabled={busy || code.trim().length < 4} onClick={join}>
              참가
            </button>
          </div>
        </div>
      </div>
      <p className="muted">덱은 방에 들어간 뒤에 골라도 됩니다. 상대에게는 내 덱의 캐릭터만 보입니다.</p>
      {error && <p className="lobby-error">{error}</p>}
    </section>
  );
}

/** 퀵 매치: 덱만 정하면 같은 때 기다리는 다른 플레이어와 짝을 짓는다. */
export function QuickPanel({ mine, loginRequired }: { mine: DeckRow[]; loginRequired: boolean }) {
  const { joined, room, error, setError, apply, leave } = useRoom(rememberedRoom("quick"));
  const [deck, setDeck] = useState<DeckRow | null>(null);
  const [busy, setBusy] = useState(false);
  const [since, setSince] = useState<number>(Date.now());
  const [, tick] = useState(0);

  const waiting = !!joined && room?.status === "waiting";
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => tick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  const start = async () => {
    if (!deck) return;
    setBusy(true);
    setError(null);
    setSince(Date.now());
    try {
      apply(await postJson<RoomResponse>("/battlelog/play/api/quick/", { deck_id: deck.id }), "quick");
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (waiting) {
    const seconds = Math.max(0, Math.floor((Date.now() - since) / 1000));
    return (
      <section className="lobby-card quick-card">
        <div className="quick-spinner" aria-hidden />
        <p>
          상대를 찾는 중… <span className="muted">{seconds}초</span>
        </p>
        <p className="muted">
          {room?.seats.host.deck?.character} 덱 · 자동 판정 · 레디 10초 · 효과 선택 30초
        </p>
        <button type="button" className="btn-ghost" onClick={leave}>
          매칭 취소
        </button>
        {error && <p className="lobby-error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="lobby-card">
      <DeckPicker label="내 덱" value={deck} onChange={setDeck} mine={mine} loginRequired={loginRequired} />
      <p className="muted">덱만 정하면 지금 퀵 매치를 기다리는 다른 플레이어와 자동 판정으로 대전합니다(레디 10초 · 효과 선택 30초).</p>
      <button type="button" className="btn-primary lobby-start" disabled={busy || !deck} onClick={start}>
        {busy ? "찾는 중…" : "퀵 매치 시작"}
      </button>
      {room?.status === "started" && <p>대전을 시작합니다…</p>}
      {error && <p className="lobby-error">{error}</p>}
    </section>
  );
}
