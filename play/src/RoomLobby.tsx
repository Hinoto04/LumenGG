import { useCallback, useEffect, useRef, useState } from "react";
import { DeckPicker, TimerSelect, type DeckRow } from "./Lobby";
import { postJson } from "./net/http";
import { seconds as formatSeconds, t } from "./i18n";
import { playSound } from "./sound/sfx";
import { MATCH_FORMATS, matchFormatLabel, type MatchFormat } from "./matchFormat";

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
  options: { mode?: string; ready_timeout_seconds?: number; effect_timeout_seconds?: number; format?: MatchFormat };
  seat: "host" | "guest" | null;
  seats: { host: SeatView; guest: SeatView };
  error: string;
  play_url?: string;
  /** 퀵 매치 대기 중: 지금 같은 진행 방식으로 매칭을 기다리는 플레이어 수(나 포함) */
  quick_waiting?: number;
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

/** 퀵 매치가 잡히면 다른 탭·창을 보고 있어도 알 수 있게 알리고, 잠깐 보여 준 뒤 대전으로 옮긴다. */
const MATCHED_DELAY_MS = 1600;

/** 매칭을 시작하는 버튼을 누를 때(사용자 동작) 브라우저 알림 권한을 묻는다. */
function askNotificationPermission() {
  try {
    if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
  } catch {
    /* 알림을 못 쓰는 브라우저(일부 WebView)는 소리·제목으로만 알린다 */
  }
}

function notifyMatched(opponent: string) {
  const body = opponent ? t("상대: {character}", { character: opponent }) : t("대전을 시작합니다…");
  playSound("prompt");
  document.title = `● ${t("매칭 완료!")}`;
  try {
    navigator.vibrate?.([120, 60, 120]);
  } catch {
    /* 진동이 없는 기기 */
  }
  try {
    if ("Notification" in window && Notification.permission === "granted" && document.visibilityState !== "visible") {
      new Notification(t("매칭 완료!"), { body, tag: "lumen-quick-match" });
    }
  } catch {
    /* 알림 생성이 막힌 환경(모바일 Chrome 등은 서비스 워커가 필요하다) */
  }
}

/** 참가 중인 방(퀵 매치 포함)을 주기적으로 갱신하고, 대전이 시작되면 내 좌석으로 옮긴다. */
function useRoom(initial: StoredRoom | null) {
  const [joined, setJoined] = useState<StoredRoom | null>(initial);
  const [room, setRoom] = useState<RoomView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const leaving = useRef(false);
  const moving = useRef(false);

  const apply = useCallback((data: RoomResponse, kind: "room" | "quick") => {
    const next = { code: data.room.code, token: data.token, kind };
    setJoined(next);
    setRoom(data.room);
    if (data.room.status === "closed") {
      storeRoom(null);
      return;
    }
    storeRoom(next);
    if (data.room.status === "started" && data.room.play_url && !moving.current) {
      moving.current = true;
      storeRoom(null);
      const url = data.room.play_url;
      if (kind === "quick") {
        const rival = data.room.seat === "guest" ? data.room.seats.host : data.room.seats.guest;
        notifyMatched(rival.deck?.character ?? "");
        setTimeout(() => location.assign(url), MATCHED_DELAY_MS);
      } else {
        location.assign(url);
      }
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
          <b>{seat.name || t("플레이어")}</b>
          <span className="muted">
            {seat.deck ? (seat.me ? `${seat.deck.character} · ${seat.deck.name ?? ""}` : t("{character} 덱", { character: seat.deck.character })) : t("덱을 고르는 중")}
          </span>
          <span className={`room-ready ${seat.ready ? "is-on" : ""}`}>{seat.ready ? t("준비 완료") : t("준비 전")}</span>
        </>
      ) : (
        <span className="muted">{t("상대를 기다리는 중…")}</span>
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
          <span className="muted">{t("방 코드")}</span>
          <strong className="room-code">{room.code}</strong>
          <button type="button" className="btn-secondary" onClick={copy}>
            {copied ? t("복사됨") : t("초대 링크 복사")}
          </button>
        </div>
        <p className="muted">
          {room.options.mode === "manual" ? t("수동(샌드박스)") : t("자동 판정")}
          {room.options.mode !== "manual" &&
            ` · ${t("레디 {ready} · 효과 선택 {effect}", {
              ready: room.options.ready_timeout_seconds ? formatSeconds(room.options.ready_timeout_seconds) : t("제한 없음"),
              effect: room.options.effect_timeout_seconds ? formatSeconds(room.options.effect_timeout_seconds) : t("제한 없음"),
            })}`}
        </p>
        <div className="room-seats">
          <SeatCard seat={room.seats.host} label={t("방장 (P1)")} />
          <SeatCard seat={room.seats.guest} label={t("참가자 (P2)")} />
        </div>
        {room.status === "started" ? (
          <p>{t("대전을 시작합니다…")}</p>
        ) : (
          <>
            <DeckPicker
              label={t("내 덱")}
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
                {room.seat === "host" ? t("방 닫기") : t("나가기")}
              </button>
              <button
                type="button"
                className={me.ready ? "btn-secondary" : "btn-primary"}
                disabled={!me.deck}
                onClick={() => call("ready", { ready: !me.ready })}
              >
                {me.ready ? t("준비 취소") : t("준비 완료")}
              </button>
            </div>
            <p className="muted">{t("두 플레이어가 모두 덱을 고르고 준비하면 대전이 시작됩니다.")}</p>
          </>
        )}
        {(room.error || error) && <p className="lobby-error">{room.error || error}</p>}
      </section>
    );
  }

  return (
    <section className="lobby-card">
      {joined && room?.status === "closed" && <p className="lobby-error">{t("방이 닫혔습니다.")}</p>}
      <DeckPicker label={t("내 덱")} value={deck} onChange={setDeck} mine={mine} loginRequired={loginRequired} />
      <div className="room-split">
        <div className="room-box">
          <h2>{t("방 만들기")}</h2>
          <div className="lobby-row segmented" role="radiogroup" aria-label={t("대전 방식")}>
            {(
              [
                ["automatic", t("자동 판정")],
                ["manual", t("수동(샌드박스)")],
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
              <TimerSelect label={t("레디 제한")} value={readyTimer} onChange={setReadyTimer} />
              <TimerSelect label={t("효과 선택 제한")} value={effectTimer} onChange={setEffectTimer} />
            </div>
          )}
          <button type="button" className="btn-primary" disabled={busy} onClick={create}>
            {t("방 만들기")}
          </button>
        </div>
        <div className="room-box">
          <h2>{t("코드로 참가")}</h2>
          <div className="room-join">
            <input
              className="room-code-input"
              value={code}
              maxLength={8}
              placeholder={t("방 코드")}
              onChange={(event) => setCode(event.target.value.toUpperCase())}
              aria-label={t("방 코드")}
            />
            <button type="button" className="btn-primary" disabled={busy || code.trim().length < 4} onClick={join}>
              {t("참가")}
            </button>
          </div>
        </div>
      </div>
      <p className="muted">{t("덱은 방에 들어간 뒤에 골라도 됩니다. 상대에게는 내 덱의 캐릭터만 보입니다.")}</p>
      {error && <p className="lobby-error">{error}</p>}
    </section>
  );
}

const QUICK_COUNT_MS = 5000;

interface QuickCounts {
  waiting: number;
  /** 진행 방식별 대기 인원(예전 서버는 보내지 않는다) */
  formats?: Partial<Record<MatchFormat, number>>;
}

/** 퀵 매치 메뉴: 지금 매칭을 기다리는 플레이어 수(대기 중이 아닐 때만 따로 묻는다). */
function useQuickWaitingCount(active: boolean): QuickCounts | null {
  const [count, setCount] = useState<QuickCounts | null>(null);
  useEffect(() => {
    if (!active) return;
    let alive = true;
    const load = async () => {
      try {
        const response = await fetch("/battlelog/play/api/quick/status/", { credentials: "same-origin" });
        const data = (await response.json()) as { ok?: boolean } & Partial<QuickCounts>;
        if (alive && data.ok) setCount({ waiting: Number(data.waiting ?? 0), formats: data.formats });
      } catch {
        /* 숫자를 못 받으면 표시하지 않는다 */
      }
    };
    void load();
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") void load();
    }, QUICK_COUNT_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [active]);
  return count;
}

const FORMAT_KEY = "lumen-play-quick-format";

function savedFormat(): MatchFormat {
  try {
    const value = localStorage.getItem(FORMAT_KEY);
    if (MATCH_FORMATS.some(([format]) => format === value)) return value as MatchFormat;
  } catch {
    /* 기본값을 쓴다 */
  }
  return "single";
}

function saveFormat(format: MatchFormat) {
  try {
    localStorage.setItem(FORMAT_KEY, format);
  } catch {
    /* 다음에 기본값으로 돌아갈 뿐이다 */
  }
}

/** 퀵 매치: 덱만 정하면 같은 때 기다리는 다른 플레이어와 짝을 짓는다. */
export function QuickPanel({ mine, loginRequired }: { mine: DeckRow[]; loginRequired: boolean }) {
  const { joined, room, error, setError, apply, leave } = useRoom(rememberedRoom("quick"));
  const [deck, setDeck] = useState<DeckRow | null>(null);
  const [format, setFormat] = useState<MatchFormat>(savedFormat);
  const [busy, setBusy] = useState(false);
  const [since, setSince] = useState<number>(Date.now());
  const [, tick] = useState(0);

  const waiting = !!joined && room?.status === "waiting";
  const matched = !!joined && room?.status === "started";
  const idleCount = useQuickWaitingCount(!joined || room?.status === "closed");
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => tick((value) => value + 1), 1000);
    return () => clearInterval(timer);
  }, [waiting]);

  const start = async () => {
    if (!deck) return;
    askNotificationPermission();
    setBusy(true);
    setError(null);
    setSince(Date.now());
    try {
      apply(await postJson<RoomResponse>("/battlelog/play/api/quick/", { deck_id: deck.id, format }), "quick");
    } catch (exception) {
      setError((exception as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (matched && room) {
    const rival = room.seat === "guest" ? room.seats.host : room.seats.guest;
    return (
      <section className="lobby-card quick-card quick-matched" role="status">
        <strong className="quick-matched-title">{t("매칭 완료!")}</strong>
        <p>
          {rival.deck?.character
            ? t("상대: {name} · {character}", { name: rival.name || t("플레이어"), character: rival.deck.character })
            : rival.name}
        </p>
        <p className="muted">{t("대전을 시작합니다…")}</p>
      </section>
    );
  }

  if (waiting) {
    const seconds = Math.max(0, Math.floor((Date.now() - since) / 1000));
    return (
      <section className="lobby-card quick-card">
        <div className="quick-spinner" aria-hidden />
        <p>
          {t("상대를 찾는 중…")} <span className="muted">{formatSeconds(seconds)}</span>
        </p>
        {room?.quick_waiting != null && (
          <p className="quick-count">{t("지금 매칭 중인 플레이어 {n}명", { n: room.quick_waiting })}</p>
        )}
        <p className="muted">
          {t("{character} 덱", { character: room?.seats.host.deck?.character ?? "" })}
          {room?.options.format && <> · {matchFormatLabel(room.options.format)}</>} · {t("자동 판정 · 레디 10초 · 효과 선택 30초")}
        </p>
        <button type="button" className="btn-ghost" onClick={leave}>
          {t("매칭 취소")}
        </button>
        {error && <p className="lobby-error">{error}</p>}
      </section>
    );
  }

  return (
    <section className="lobby-card">
      <DeckPicker label={t("내 덱")} value={deck} onChange={setDeck} mine={mine} loginRequired={loginRequired} />
      <p className="muted">{t("덱과 진행 방식을 정하면 같은 방식으로 기다리는 다른 플레이어와 자동 판정으로 대전합니다(레디 10초 · 효과 선택 30초).")}</p>
      <div className="lobby-row segmented quick-formats" role="radiogroup" aria-label={t("진행 방식")}>
        {MATCH_FORMATS.map(([value, label, hint]) => {
          const waitingHere = idleCount?.formats?.[value];
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={format === value}
              className={format === value ? "is-active" : ""}
              onClick={() => {
                setFormat(value);
                saveFormat(value);
              }}
            >
              <span>{label}</span>
              <small>{hint}</small>
              {waitingHere ? <em className="quick-format-count">{t("{n}명 대기", { n: waitingHere })}</em> : null}
            </button>
          );
        })}
      </div>
      {idleCount != null && (
        <p className="quick-count">
          {idleCount.waiting > 0 ? t("지금 매칭 중인 플레이어 {n}명", { n: idleCount.waiting }) : t("지금 매칭 중인 플레이어가 없습니다")}
        </p>
      )}
      <button type="button" className="btn-primary lobby-start" disabled={busy || !deck} onClick={start}>
        {busy ? t("찾는 중…") : t("퀵 매치 시작")}
      </button>
      {room?.status === "started" && <p>{t("대전을 시작합니다…")}</p>}
      {error && <p className="lobby-error">{error}</p>}
    </section>
  );
}
