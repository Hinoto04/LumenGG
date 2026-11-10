import { create } from "zustand";
import type { Side } from "../protocol";

/** 화면 가운데 큰 알림 */
export type Banner =
  | { id: number; kind: "phase"; title: string; sub?: string }
  | { id: number; kind: "judge"; mine: string; theirs: string; tone: Tone; speeds?: [number, number] | null }
  | { id: number; kind: "text"; title: string; tone?: Tone };

export type Tone = "good" | "bad" | "neutral";

/** 초상 위로 떠오르는 숫자 */
export interface Float {
  id: number;
  side: Side;
  text: string;
  tone: "damage" | "heal" | "fp" | "info";
}

/** 발동한 효과 한 줄(위쪽 띠) */
export interface Ribbon {
  id: number;
  side: Side | "system";
  card: string;
  text: string;
}

/** 연출은 끌 수 없다(카드 이동이 안 보이면 게임을 따라갈 수 없다). */
export type PlaybackSpeed = 1 | 2;

interface FxStore {
  banner: Banner | null;
  floats: Float[];
  ribbon: Ribbon | null;
  /** side → 마지막으로 맞은 시각 id. 값이 바뀌면 초상이 흔들린다. */
  shake: Partial<Record<Side, number>>;
  /** 재생 중인지(조작을 막고 '진행 중' 표시) */
  playing: boolean;
  /** 재생 속도 */
  speed: PlaybackSpeed;
  setSpeed: (speed: PlaybackSpeed) => void;
}

function storedSpeed(): PlaybackSpeed {
  try {
    const raw = localStorage.getItem("lumen-play-speed");
    // 예전에 저장한 "연출 끔"(0)은 ×1로 되돌린다.
    return raw === "2" ? 2 : 1;
  } catch {
    return 1;
  }
}

export const useFx = create<FxStore>((set) => ({
  banner: null,
  floats: [],
  ribbon: null,
  shake: {},
  playing: false,
  speed: storedSpeed(),
  setSpeed: (speed) => {
    try {
      localStorage.setItem("lumen-play-speed", String(speed));
    } catch {
      /* 저장 못 해도 이번 접속에는 적용된다 */
    }
    set({ speed });
  },
}));

let nextId = 1;
export const fxId = () => nextId++;

const timers = new Set<ReturnType<typeof setTimeout>>();

function later(ms: number, run: () => void) {
  const timer = setTimeout(() => {
    timers.delete(timer);
    run();
  }, ms);
  timers.add(timer);
}

type WithoutId<T> = T extends unknown ? Omit<T, "id"> : never;

export function showBanner(banner: WithoutId<Banner>, ms: number) {
  const id = fxId();
  useFx.setState({ banner: { ...banner, id } as Banner });
  later(ms, () => {
    if (useFx.getState().banner?.id === id) useFx.setState({ banner: null });
  });
}

export function showRibbon(ribbon: Omit<Ribbon, "id">, ms: number) {
  const id = fxId();
  useFx.setState({ ribbon: { ...ribbon, id } });
  later(ms, () => {
    if (useFx.getState().ribbon?.id === id) useFx.setState({ ribbon: null });
  });
}

export function addFloat(float: Omit<Float, "id">, ms = 1400) {
  const id = fxId();
  useFx.setState((state) => ({ floats: [...state.floats, { ...float, id }] }));
  later(ms, () => useFx.setState((state) => ({ floats: state.floats.filter((item) => item.id !== id) })));
}

export function shake(side: Side) {
  useFx.setState((state) => ({ shake: { ...state.shake, [side]: fxId() } }));
}

/** 초기화(첫 접속, 시점 전환 등) 때 남은 연출을 모두 지운다. */
export function clearFx() {
  timers.forEach(clearTimeout);
  timers.clear();
  useFx.setState({ banner: null, floats: [], ribbon: null });
}
