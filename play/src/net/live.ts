import { create } from "zustand";
import { pushEnvelope, pushEvents, resetPlayback } from "../anim/playback";
import { syncCatalog } from "../catalog";
import { installErrorReporter } from "./report";
import { acknowledge, predict, predictCommand, predictManual, reject, resetPredictions } from "./optimistic";
import type { LiveTarget } from "../mode";
import type { ClientMessage, GameEvent, LegalAction, PlayEnvelope, Role, ServerMessage } from "../protocol";
import { usePlay } from "../store";

export type LiveStatus = "connecting" | "open" | "reconnecting" | "closed";

interface LiveStore {
  status: LiveStatus;
  /** 보낸 명령의 결과(새 상태)를 기다리는 중. 그동안 조작을 막는다. */
  busy: boolean;
  /** 최근 이벤트. seq 순. */
  events: GameEvent[];
  /** 더 진행할 수 없는 이유(세션 없음, 수동 모드 전환 등) */
  fatal: string | null;
  /** 역할별 접속 수. 서버가 접속·종료 때마다 보낸다. */
  presence: Partial<Record<Role, number>> | null;
}

export const useLive = create<LiveStore>(() => ({
  status: "connecting",
  busy: false,
  events: [],
  fatal: null,
  presence: null,
}));

export type Selections = { selected?: string[]; reason?: string };

// ---------------------------------------------------------------------------
// 이어하기: 마지막으로 앉은 좌석을 기억해 로비에서 다시 열 수 있게 한다.

const LAST_GAME_KEY = "lumen-play-last-game";

export interface SavedGame extends LiveTarget {
  savedAt: number;
}

export function lastGame(): SavedGame | null {
  try {
    const saved = JSON.parse(localStorage.getItem(LAST_GAME_KEY) ?? "null") as SavedGame | null;
    // 시뮬레이터 세션은 하루 안팎으로 만료되므로 오래된 것은 보여 주지 않는다.
    return saved?.view && saved.seat && Date.now() - saved.savedAt < 24 * 3600 * 1000 ? saved : null;
  } catch {
    return null;
  }
}

function rememberGame(target: LiveTarget | null) {
  try {
    if (target) localStorage.setItem(LAST_GAME_KEY, JSON.stringify({ ...target, savedAt: Date.now() }));
    else localStorage.removeItem(LAST_GAME_KEY);
  } catch {
    /* 저장하지 못해도 대전에는 지장이 없다 */
  }
}

const EVENT_KEEP = 300;
const COMMAND_TIMEOUT_MS = 15000;

function uid(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
}

function socketUrl(target: LiveTarget): string {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  const query = new URLSearchParams({ seat: target.seat, seat_token: target.token, language: "ko" });
  return `${scheme}://${location.host}/ws/battlelog/simulator/${encodeURIComponent(target.view)}/?${query}`;
}

interface Connection {
  target: LiveTarget;
  manual: (action: string, payload: Record<string, unknown>) => void;
  submit: (action: LegalAction, selections?: Selections) => void;
  apply: (envelope: PlayEnvelope) => void;
  close: () => void;
}

let current: Connection | null = null;

/** 지금 접속한 좌석. HTTP 요청(덱 준비)에 쓴다. */
export function currentTarget(): LiveTarget | null {
  return current?.target ?? null;
}

/** HTTP 응답으로 받은 상태를 WebSocket 소식보다 먼저 반영한다. */
export function applyEnvelope(envelope: PlayEnvelope): void {
  current?.apply(envelope);
}

/**
 * 덱 준비 중인 envelope에는 엔진 필드가 없다. 화면이 같은 모양을 기대할 수 있게 채운다.
 */
export function normalizeEnvelope(envelope: PlayEnvelope): PlayEnvelope {
  const preparing = envelope.preparation?.status === "editing";
  if (!preparing && envelope.mode === "automatic") return envelope;
  // 덱 준비 중이거나 수동 모드: 엔진이 없으므로 행동 목록·타이머·엔진 상태를 비워 둔다.
  return {
    ...envelope,
    legal_actions: envelope.legal_actions ?? [],
    pending_decision: null,
    clocks: null,
    engine_status: { status: preparing ? "preparing" : "running", step: null, winner: null, reason: "" },
  };
}

export function isManual(envelope: PlayEnvelope | null): boolean {
  return envelope?.mode === "manual" && !envelope.automation_failure;
}

/**
 * 수동 모드 행동(move_card, hp, set_phase ...)을 보낸다. 서버가 그대로 적용하고
 * 모두에게 state_dirty를 보내므로 결과는 새 상태로 돌아온다.
 */
export function sendManual(action: string, payload: Record<string, unknown> = {}): void {
  current?.manual(action, payload);
}

export function isPreparing(envelope: PlayEnvelope | null): boolean {
  return envelope?.preparation?.status === "editing";
}

/** 지금 연결로 행동을 보낸다. 연결이 없으면 무시한다. */
export function submitAction(action: LegalAction, selections?: Selections): void {
  current?.submit(action, selections);
}

/**
 * 시뮬레이터 WebSocket에 붙는다. 끊기면 지수 백오프로 다시 붙고,
 * 다시 붙으면 서버가 상태를 새로 보내 주므로 따로 복구할 것이 없다.
 */
export function connectLive(target: LiveTarget): () => void {
  let socket: WebSocket | null = null;
  let stopped = false;
  let retry = 0;
  let retryTimer: ReturnType<typeof setTimeout> | undefined;
  let heartbeat: ReturnType<typeof setInterval> | undefined;
  let commandTimer: ReturnType<typeof setTimeout> | undefined;
  let clockTimer: ReturnType<typeof setTimeout> | undefined;
  /** 이 버전보다 새 상태가 오면 busy를 푼다. */
  let awaitingAbove: number | null = null;
  let pendingRequest: string | null = null;
  let requestedVersion = 0;
  /** 받은 상태 중 가장 새 버전. 화면은 재생 중이라 이보다 뒤처질 수 있다. */
  let latestVersion = 0;
  let lastSeq = 0;

  const send = (message: ClientMessage) => {
    if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(message));
  };

  const clearBusy = () => {
    clearTimeout(commandTimer);
    awaitingAbove = null;
    pendingRequest = null;
    useLive.setState({ busy: false });
  };

  const applyEnvelope = (incoming: PlayEnvelope) => {
    if (incoming.version < latestVersion) return;
    const envelope = normalizeEnvelope(incoming);
    latestVersion = envelope.version;
    if (envelope.event_count < lastSeq) {
      // 수동 모드 되돌리기: 서버 이벤트가 줄었다. 기록을 잘라 내고 구독 위치를 다시 맞춘다.
      // 그대로 두면 서버가 이전 위치 이후의 새 이벤트를 보내지 않는다.
      lastSeq = envelope.event_count;
      useLive.setState({ events: useLive.getState().events.filter((event) => event.seq <= lastSeq) });
      send({ type: "log_subscribe", since_seq: lastSeq });
      resetPlayback(envelope);
    } else if (envelope.mode === "manual" && envelope.automation_failure) {
      useLive.setState({ fatal: "엔진 오류로 이 대전은 수동 모드로 바뀌었습니다. 새 대전을 시작해 주세요." });
      resetPlayback(envelope);
    } else {
      // 앞선 이벤트를 재생한 뒤에 화면에 반영된다.
      pushEnvelope(envelope);
    }
    syncCatalog(target.view, envelope);
    if (awaitingAbove !== null && envelope.version > awaitingAbove) clearBusy();
    scheduleClock(envelope);
    if (target.seat) rememberGame(["running", "preparing"].includes(envelope.engine_status.status) ? target : null);
  };

  /**
   * 서버는 시간 초과를 읽기·명령 때 정산한다. 마감이 지나면 상태를 요청해서 정산을 일으키고,
   * 시계 차이로 아직이면 2초마다 다시 묻는다.
   */
  const scheduleClock = (envelope: PlayEnvelope) => {
    clearTimeout(clockTimer);
    const clock = envelope.clocks;
    if (!clock?.deadline || clock.paused || envelope.engine_status.status !== "running") return;
    const due = Date.parse(clock.deadline) - Date.now() + 400;
    clockTimer = setTimeout(() => send({ type: "state" }), due > 0 ? due : 2000);
  };

  const requestState = (version: number) => {
    if (version <= requestedVersion) return;
    requestedVersion = version;
    send({ type: "state" });
  };

  const handle = (message: ServerMessage) => {
    switch (message.type) {
      case "state":
        applyEnvelope(message.state);
        return;
      case "state_dirty":
        if (message.version > latestVersion) requestState(message.version);
        return;
      case "log_events": {
        const events = message.reset ? message.events : [...useLive.getState().events, ...message.events];
        const fresh = events.filter((event, index, all) => index === 0 || event.seq > all[index - 1].seq);
        lastSeq = Math.max(lastSeq, message.event_count ?? 0, ...fresh.map((event) => event.seq));
        useLive.setState({ events: fresh.slice(-EVENT_KEEP) });
        pushEvents(message.events);
        return;
      }
      case "command_ack":
        // 새 상태는 곧 state_dirty로 온다. busy는 그 상태를 받을 때 푼다.
        acknowledge(message.request_id);
        if (message.request_id && message.request_id === pendingRequest) pendingRequest = null;
        return;
      case "action_ack":
        acknowledge(message.request_id);
        return;
      case "error": {
        // 거절된 행동의 예측은 버린다(수동 모드 행동도 여기로 온다).
        reject(message.request_id);
        if (message.request_id && pendingRequest && message.request_id !== pendingRequest) return;
        clearBusy();
        if (message.code === "automatic_fallback") {
          useLive.setState({ fatal: message.error || "엔진 오류로 대전이 중단되었습니다." });
        } else {
          usePlay.getState().flash(message.error || "요청이 거부되었습니다.");
        }
        if (message.state) applyEnvelope(message.state);
        else send({ type: "state" });
        return;
      }
      case "presence":
        useLive.setState({ presence: message.presence });
        return;
      default:
        return;
    }
  };

  const open = () => {
    useLive.setState({ status: retry ? "reconnecting" : "connecting" });
    socket = new WebSocket(socketUrl(target));
    socket.onopen = () => {
      retry = 0;
      requestedVersion = 0;
      useLive.setState({ status: "open" });
      send({ type: "log_subscribe", since_seq: lastSeq });
      heartbeat = setInterval(() => send({ type: "presence" }), 20000);
    };
    socket.onmessage = (event) => {
      try {
        handle(JSON.parse(String(event.data)) as ServerMessage);
      } catch (error) {
        console.error("[play] bad message", error);
      }
    };
    socket.onclose = (event) => {
      clearInterval(heartbeat);
      clearBusy();
      if (stopped) return;
      if (event.code === 4404) {
        useLive.setState({ status: "closed", fatal: "대전을 찾을 수 없습니다. 만료되었거나 주소가 잘못되었습니다." });
        return;
      }
      useLive.setState({ status: "reconnecting" });
      retryTimer = setTimeout(open, Math.min(10000, 500 * 2 ** retry++));
    };
  };

  /** 탭으로 돌아오거나 네트워크가 돌아오면 기다리지 않고 바로 다시 붙거나 따라잡는다. */
  const wake = () => {
    if (stopped) return;
    if (socket?.readyState === WebSocket.OPEN) {
      send({ type: "state" });
      return;
    }
    if (socket?.readyState === WebSocket.CONNECTING) return;
    clearTimeout(retryTimer);
    retry = Math.max(retry, 1);
    open();
  };
  const onVisibility = () => {
    if (document.visibilityState === "visible") wake();
  };
  const onOffline = () => {
    if (!stopped) useLive.setState({ status: "reconnecting" });
  };
  document.addEventListener("visibilitychange", onVisibility);
  window.addEventListener("online", wake);
  window.addEventListener("offline", onOffline);

  const connection: Connection = {
    target,
    manual(action, payload) {
      if (socket?.readyState !== WebSocket.OPEN) {
        usePlay.getState().flash("연결이 끊겨 있습니다. 다시 연결되면 시도해 주세요.");
        return;
      }
      const requestId = uid();
      predict(requestId, predictManual(action, payload));
      send({ type: "action", request_id: requestId, payload: { action, payload } });
    },
    apply: (envelope) => applyEnvelope(envelope),
    submit(action, selections) {
      const envelope = usePlay.getState().envelope;
      if (!envelope || envelope.version !== latestVersion || useLive.getState().busy || socket?.readyState !== WebSocket.OPEN) return;
      const requestId = uid();
      pendingRequest = requestId;
      awaitingAbove = envelope.version;
      useLive.setState({ busy: true });
      // 결과를 기다리지 않고 내 행동을 바로 화면에 반영한다.
      predict(requestId, predictCommand(envelope, action, selections));
      commandTimer = setTimeout(() => {
        reject(requestId);
        clearBusy();
        usePlay.getState().flash("응답이 늦습니다. 상태를 다시 불러옵니다.");
        send({ type: "state" });
      }, COMMAND_TIMEOUT_MS);
      send({
        type: "command",
        request_id: requestId,
        payload: {
          command_id: uid(),
          action_id: action.action_id,
          expected_version: envelope.version,
          selections: selections ?? {},
        },
      });
    },
    close() {
      stopped = true;
      clearTimeout(retryTimer);
      clearInterval(heartbeat);
      clearTimeout(commandTimer);
      clearTimeout(clockTimer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("online", wake);
      window.removeEventListener("offline", onOffline);
      socket?.close();
    },
  };

  current = connection;
  resetPredictions();
  installErrorReporter();
  resetPlayback(null);
  useLive.setState({ status: "connecting", busy: false, events: [], fatal: null, presence: null });
  open();
  return () => {
    connection.close();
    if (current === connection) current = null;
  };
}
