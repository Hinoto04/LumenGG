import { create } from "zustand";
import type { Side, VisibleCard } from "../protocol";
import { clearClash } from "./clash";

/** 화면 가운데 큰 알림 */
export type Banner =
  | { id: number; kind: "phase"; title: string; sub?: string }
  | { id: number; kind: "text"; title: string; tone?: Tone }
  /** 효과로 고른 패를 양쪽이 함께 확인하는 연출(요한 선언 등) */
  | { id: number; kind: "card"; title: string; sub?: string; card: VisibleCard; tone?: Tone };

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

/**
 * 효과가 발동한 카드를 잠깐 크게 띄우는 연출. 발동한 쪽 편에 카드와 효과문을 보여 준다.
 * from은 보드 위 그 카드의 가운데·너비(화면 좌표)로, 있으면 그 자리에서 날아오른다.
 */
export interface Activation {
  id: number;
  side: Side | "system";
  card: VisibleCard;
  label: string;
  text: string;
  from?: { x: number; y: number; width: number };
}

/** 연출은 끌 수 없다(카드 이동이 안 보이면 게임을 따라갈 수 없다). */
export type PlaybackSpeed = 1 | 2;

interface FxStore {
  banner: Banner | null;
  floats: Float[];
  ribbon: Ribbon | null;
  activation: Activation | null;
  /** side → 마지막으로 맞은 시각 id. 값이 바뀌면 초상이 흔들린다. */
  shake: Partial<Record<Side, number>>;
  /** 재생 중인지(조작을 막고 '진행 중' 표시) */
  playing: boolean;
  /** 화면에 올릴 더 새 서버 상태가 기다리는 중(이벤트 재생 전후). 이 동안 보이는 타이머는 지난 것이다. */
  behind: boolean;
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
  activation: null,
  shake: {},
  playing: false,
  behind: false,
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

export function showActivation(activation: Omit<Activation, "id">, ms: number) {
  const id = fxId();
  useFx.setState({ activation: { ...activation, id }, ribbon: null });
  later(ms, () => {
    if (useFx.getState().activation?.id === id) useFx.setState({ activation: null });
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
  clearClash();
  useFx.setState({ banner: null, floats: [], ribbon: null, activation: null });
}
