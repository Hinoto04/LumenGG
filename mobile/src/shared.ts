import { AppState } from "react-native";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import type { Action, CalcState } from "./types";
import { BASE_URL, request, ApiError } from "./api";

export interface SharedSession {
  view_token: string;
  control_token: string;
}
export async function saveShared(session: SharedSession | null) {
  if (session)
    await SecureStore.setItemAsync(
      "lumendb.calculator",
      JSON.stringify(session),
    );
  else await SecureStore.deleteItemAsync("lumendb.calculator");
}
export async function storedShared(): Promise<SharedSession | null> {
  const v = await SecureStore.getItemAsync("lumendb.calculator");
  return v ? JSON.parse(v) : null;
}
export function parseShareLink(value: string): SharedSession {
  const path = value.trim();
  const match = path.match(
    /\/session\/([\w-]+)(?:\/control\/([\w-]+))?\/?(?:[?#].*)?$/,
  );
  if (!match) throw new Error("계산기 공유 링크를 확인해주세요.");
  return { view_token: match[1]!, control_token: match[2] || "" };
}
export class SharedCalculator {
  private socket: WebSocket | null = null;
  private disposed = false;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private state: CalcState | null = null;
  private attempt = 0;
  private action: Action | null = null;
  private pendingResolve: ((s: CalcState) => void) | null = null;
  private pendingReject: ((e: Error) => void) | null = null;
  private timeout: ReturnType<typeof setTimeout> | undefined;
  private appSubscription: ReturnType<typeof AppState.addEventListener>;
  constructor(
    private session: SharedSession,
    private language: string,
    private changed: (s: CalcState) => void,
    private connection: (connected: boolean) => void,
  ) {
    this.appSubscription = AppState.addEventListener("change", (state) => {
      if (state === "active") {
        this.socket?.close();
        this.connect();
      } else {
        this.connection(false);
        this.socket?.close();
      }
    });
    this.connect();
  }
  private accept(state: CalcState) {
    if (!this.state || state.version >= this.state.version) {
      this.state = state;
      this.changed(state);
    }
  }
  private connect() {
    if (this.disposed || AppState.currentState !== "active") return;
    clearTimeout(this.retry);
    const socket = new WebSocket(
      BASE_URL.replace(/^http/, "ws") +
        "/ws/mobile/v1/calculators/" +
        this.session.view_token +
        "/",
    );
    this.socket = socket;
    socket.onopen = () =>
      socket.send(
        JSON.stringify({
          type: "authenticate",
          request_id: "auth",
          control_token: this.session.control_token,
          language: this.language,
        }),
      );
    socket.onmessage = (event) => {
      if (this.socket !== socket) return;
      try {
        const payload = JSON.parse(event.data);
        if (payload.state) this.accept(payload.state);
        if (payload.request_id === "auth") {
          this.attempt = 0;
          this.connection(true);
          if (this.action) this.recover();
        }
        if (this.action && payload.request_id === this.action.action_id) {
          if (payload.type === "error") {
            this.finish(undefined, new Error(payload.error || payload.code));
          } else if (payload.ok && payload.state) this.finish(payload.state);
        }
      } catch {
        this.connection(false);
        socket.close();
      }
    };
    socket.onclose = (event) => {
      if (this.socket !== socket) return;
      this.connection(false);
      if (!this.disposed && event.code !== 4404)
        this.retry = setTimeout(
          () => this.connect(),
          Math.min(15000, 1000 * 2 ** this.attempt++),
        );
      if (event.code === 4404)
        this.finish(undefined, new Error("Calculator unavailable."));
    };
    socket.onerror = () => {
      this.connection(false);
      socket.close();
    };
  }
  async send(action: Action): Promise<CalcState> {
    if (this.action) throw new Error("이전 동작을 처리 중입니다.");
    if (!this.state?.can_control || this.socket?.readyState !== WebSocket.OPEN)
      throw new Error("계산기 연결이 끊겼습니다.");
    this.action = {
      ...action,
      action_id: Crypto.randomUUID(),
      expected_version: this.state.version,
    };
    const result = new Promise<CalcState>((resolve, reject) => {
      this.pendingResolve = resolve;
      this.pendingReject = reject;
    });
    this.timeout = setTimeout(() => this.recover(), 8000);
    this.socket.send(
      JSON.stringify({
        type: "action",
        request_id: this.action.action_id,
        payload: this.action,
      }),
    );
    return result;
  }
  private async recover() {
    const action = this.action;
    if (!action) return;
    try {
      const response = await request(
        "/calculators/" +
          this.session.view_token +
          "/action?language=" +
          this.language,
        {
          method: "POST",
          headers: { "X-Calculator-Control": this.session.control_token },
          body: JSON.stringify(action),
        },
        false,
      );
      if (this.action !== action) return;
      this.accept(response.state);
      this.finish(response.state);
    } catch (error) {
      if (this.action !== action) return;
      if (error instanceof ApiError && error.detail?.state)
        this.accept(error.detail.state);
      // The same action UUID is retained when outcome is unknown, so a later
      // reconnect can reconcile safely instead of allowing a duplicate action.
      if (error instanceof ApiError) this.finish(undefined, error);
      else {
        this.connection(false);
        this.socket?.close();
      }
    }
  }
  private finish(state?: CalcState, error?: Error) {
    clearTimeout(this.timeout);
    if (state) this.pendingResolve?.(state);
    else if (error) this.pendingReject?.(error);
    this.action = null;
    this.pendingResolve = null;
    this.pendingReject = null;
  }
  dispose() {
    this.disposed = true;
    clearTimeout(this.retry);
    clearTimeout(this.timeout);
    this.appSubscription.remove();
    this.socket?.close();
    this.finish(undefined, new Error("Session closed."));
  }
}
