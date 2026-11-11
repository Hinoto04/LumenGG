import { create } from "zustand";

/**
 * 효과음.
 *
 * 기본 소리는 Web Audio로 그 자리에서 합성한다(파일·라이선스가 필요 없다).
 * 구입하거나 내려받은 음원이 있으면 play/public/sfx/에 넣고 manifest.json에
 * {"이름": "파일명"}을 적으면 그 소리가 합성음 대신 재생된다. 목록은 SOUND_NAMES와 docs/PLAY_SOUND.md.
 * 빌드하면 public/ 아래 파일이 LumenGG/static/play/sfx/로 함께 복사된다.
 */

export const SOUND_NAMES = [
  "card_move", // 카드가 존을 옮김(드로우·버림 등)
  "card_ready", // 배틀존에 카드를 뒷면으로 냄(레디)
  "card_reveal", // 배틀 공개
  "hit", // 판정: 히트
  "counter", // 판정: 카운터
  "guard", // 판정: 가드
  "dodge", // 판정: 회피
  "clash", // 판정: 상쇄
  "grab", // 판정: 잡기
  "damage", // HP 감소
  "heal", // HP 회복
  "fp_up", // FP 증가
  "fp_down", // FP 감소
  "effect", // 카드 효과 발동
  "passive", // 패시브(카운터·상태) 변화
  "shield", // 실드가 피해를 막음
  "combo", // 콤보 시작
  "catch", // 캐치 시작
  "break", // 카드 브레이크
  "shuffle", // 덱 섞기
  "phase", // 페이즈 시작
  "turn", // 새 턴
  "prompt", // 내 선택이 필요함
  "tick", // 제한 시간 5초 이하
  "win", // 승리
  "lose", // 패배
  "ui", // 버튼·드래그 놓기
] as const;

export type SoundName = (typeof SOUND_NAMES)[number];

const SETTINGS_KEY = "lumen-play-sound";

interface SoundSettings {
  volume: number;
  muted: boolean;
}

function loadSettings(): SoundSettings {
  try {
    const raw = JSON.parse(localStorage.getItem(SETTINGS_KEY) ?? "null") as Partial<SoundSettings> | null;
    if (raw && typeof raw === "object") {
      const volume = Number(raw.volume);
      return { volume: Number.isFinite(volume) ? Math.min(1, Math.max(0, volume)) : 0.6, muted: !!raw.muted };
    }
  } catch {
    /* 저장소를 못 쓰면 기본값 */
  }
  return { volume: 0.6, muted: false };
}

interface SoundStore extends SoundSettings {
  setVolume: (volume: number) => void;
  setMuted: (muted: boolean) => void;
}

export const useSound = create<SoundStore>((set, get) => {
  const save = () => {
    try {
      const { volume, muted } = get();
      localStorage.setItem(SETTINGS_KEY, JSON.stringify({ volume, muted }));
    } catch {
      /* 무시 */
    }
  };
  return {
    ...loadSettings(),
    setVolume: (volume) => {
      set({ volume: Math.min(1, Math.max(0, volume)), muted: false });
      save();
      if (master) master.gain.value = volume;
    },
    setMuted: (muted) => {
      set({ muted });
      save();
    },
  };
});

// ---------------------------------------------------------------------------
// 오디오 컨텍스트: 브라우저는 사용자 입력이 있기 전에는 소리를 막는다.

let context: AudioContext | null = null;
let master: GainNode | null = null;
let reverb: ConvolverNode | null = null;
let noise: AudioBuffer | null = null;
const files = new Map<SoundName, AudioBuffer>();
let manifestLoaded = false;

function audio(): AudioContext | null {
  if (context) return context;
  const Ctor = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    context = new Ctor();
  } catch {
    return null;
  }
  // 음량 → 압축기(작은 소리는 끌어올리고 큰 소리는 눌러 단단하게) → 출력.
  master = context.createGain();
  master.gain.value = useSound.getState().volume;
  const compressor = context.createDynamicsCompressor();
  compressor.threshold.value = -20;
  compressor.knee.value = 8;
  compressor.ratio.value = 5;
  compressor.attack.value = 0.002;
  compressor.release.value = 0.12;
  const makeup = context.createGain();
  makeup.gain.value = 1.6;
  // 끝단 리미터: 여러 소리가 겹쳐도 찢어지지 않게 0dB 아래로 묶는다.
  const limiter = context.createDynamicsCompressor();
  limiter.threshold.value = -3;
  limiter.knee.value = 0;
  limiter.ratio.value = 20;
  limiter.attack.value = 0.001;
  limiter.release.value = 0.08;
  master.connect(compressor);
  compressor.connect(makeup);
  makeup.connect(limiter);
  limiter.connect(context.destination);
  // 공간감용 짧은 잔향. 반짝임·금속음에만 조금 섞는다.
  reverb = context.createConvolver();
  reverb.buffer = impulse(context, 1.1, 2.8);
  const wet = context.createGain();
  wet.gain.value = 0.5;
  reverb.connect(wet);
  wet.connect(master);
  const length = Math.floor(context.sampleRate * 1.5);
  noise = context.createBuffer(1, length, context.sampleRate);
  const data = noise.getChannelData(0);
  for (let i = 0; i < length; i++) data[i] = Math.random() * 2 - 1;
  void loadManifest(context);
  return context;
}

async function loadManifest(ctx: AudioContext) {
  if (manifestLoaded) return;
  manifestLoaded = true;
  const base = `${import.meta.env.BASE_URL}sfx/`;
  let manifest: Record<string, string> = {};
  try {
    const response = await fetch(`${base}manifest.json`, { cache: "no-cache" });
    if (!response.ok) return;
    manifest = (await response.json()) as Record<string, string>;
  } catch {
    return;
  }
  await Promise.all(
    Object.entries(manifest).map(async ([name, file]) => {
      if (!(SOUND_NAMES as readonly string[]).includes(name) || typeof file !== "string" || !file) return;
      try {
        const response = await fetch(base + file);
        if (!response.ok) return;
        files.set(name as SoundName, await ctx.decodeAudioData(await response.arrayBuffer()));
      } catch {
        /* 못 읽은 파일은 합성음으로 대신한다 */
      }
    }),
  );
}

/** 첫 클릭·터치에서 오디오를 깨운다. main.tsx에서 한 번 부른다. */
export function installSoundUnlock() {
  const unlock = () => {
    const ctx = audio();
    if (ctx && ctx.state === "suspended") void ctx.resume();
  };
  window.addEventListener("pointerdown", unlock, { capture: true });
  window.addEventListener("keydown", unlock, { capture: true });
}

// ---------------------------------------------------------------------------
// 재생

const lastPlayed = new Map<SoundName, number>();
/** 같은 소리가 너무 촘촘하게 겹치지 않게 한다(빠른 재생·동시 이벤트). */
const MIN_GAP_MS = 70;

export function playSound(name: SoundName, { gain = 1 }: { gain?: number } = {}) {
  const { muted, volume } = useSound.getState();
  if (muted || volume <= 0) return;
  if (typeof document !== "undefined" && document.hidden) return;
  const ctx = audio();
  if (!ctx || !master || ctx.state !== "running") return;
  const nowMs = performance.now();
  if (nowMs - (lastPlayed.get(name) ?? -Infinity) < MIN_GAP_MS) return;
  lastPlayed.set(name, nowMs);
  const out = ctx.createGain();
  out.gain.value = gain;
  out.connect(master);
  const file = files.get(name);
  if (file) {
    const source = ctx.createBufferSource();
    source.buffer = file;
    source.connect(out);
    source.start();
    return;
  }
  RECIPES[name](new Synth(ctx, out, reverb!, noise!));
}


// ---------------------------------------------------------------------------
// 합성음
//
// 시원하게 들리도록 소리마다 세 겹을 쌓는다.
//   1) 아주 짧은 고음 잡음(어택): 귀에 걸리는 첫소리
//   2) 음정이 뚝 떨어지는 사인파(킥): 묵직한 몸통
//   3) 필터를 훑는 잡음이나 화음(꼬리): 쉭·쨍 하는 잔상
// 반짝임·금속음은 잔향(wet)을 섞어 공간감을 준다.

/** 지수 감쇠 잡음으로 만든 잔향 임펄스 */
function impulse(ctx: AudioContext, seconds: number, decay: number): AudioBuffer {
  const length = Math.floor(ctx.sampleRate * seconds);
  const buffer = ctx.createBuffer(2, length, ctx.sampleRate);
  for (let channel = 0; channel < 2; channel++) {
    const data = buffer.getChannelData(channel);
    for (let i = 0; i < length; i++) data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, decay);
  }
  return buffer;
}

type Wave = OscillatorType;

interface Shape {
  at?: number;
  attack?: number;
  decay?: number;
  level?: number;
  /** 잔향으로 보내는 양(0~1) */
  wet?: number;
  /** 좌우 위치(-1~1) */
  pan?: number;
}

class Synth {
  readonly t: number;
  constructor(
    readonly ctx: AudioContext,
    readonly out: AudioNode,
    readonly reverb: AudioNode,
    readonly noiseBuffer: AudioBuffer,
  ) {
    this.t = ctx.currentTime + 0.005;
  }

  /** 음 하나: 주파수가 from→to로 미끄러지고 attack 뒤 decay로 사라진다. */
  tone(wave: Wave, from: number, to: number, shape: Shape = {}) {
    const { at = 0, attack = 0.004, decay = 0.2 } = shape;
    const start = this.t + at;
    const osc = this.ctx.createOscillator();
    osc.type = wave;
    osc.frequency.setValueAtTime(from, start);
    if (to !== from) osc.frequency.exponentialRampToValueAtTime(Math.max(1, to), start + attack + decay * 0.7);
    osc.connect(this.envelope(start, { level: 0.3, ...shape, attack, decay }));
    osc.start(start);
    osc.stop(start + attack + decay + 0.05);
  }

  /** 잡음: 필터로 깎아 쉭, 탁, 쾅 같은 질감을 만든다. */
  noise(filter: BiquadFilterType, from: number, to: number, shape: Shape & { q?: number } = {}) {
    const { at = 0, attack = 0.002, decay = 0.15, q = 1 } = shape;
    const start = this.t + at;
    const source = this.ctx.createBufferSource();
    source.buffer = this.noiseBuffer;
    const biquad = this.ctx.createBiquadFilter();
    biquad.type = filter;
    biquad.Q.value = q;
    biquad.frequency.setValueAtTime(from, start);
    if (to !== from) biquad.frequency.exponentialRampToValueAtTime(Math.max(1, to), start + attack + decay);
    source.connect(biquad);
    biquad.connect(this.envelope(start, { level: 0.3, ...shape, attack, decay }));
    source.start(start, Math.random() * 0.5);
    source.stop(start + attack + decay + 0.05);
  }

  /** 묵직한 몸통: 높은 음에서 낮은 음으로 빠르게 떨어지는 사인파 */
  kick(from: number, to: number, shape: Shape = {}) {
    this.tone("sine", from, to, { decay: 0.22, level: 0.8, ...shape });
  }

  /** 첫소리 딱 */
  snap(shape: Shape = {}) {
    this.noise("highpass", 3500, 3500, { decay: 0.025, level: 0.5, ...shape });
  }

  /** 쉭: 필터가 from→to로 훑는다 */
  swoosh(from: number, to: number, shape: Shape & { q?: number } = {}) {
    this.noise("bandpass", from, to, { attack: 0.03, decay: 0.16, level: 0.45, q: 1.6, ...shape });
  }

  /** 맑은 종소리: 기음과 배음 */
  bell(freq: number, shape: Shape = {}) {
    this.tone("sine", freq, freq, { decay: 0.5, level: 0.16, wet: 0.5, ...shape });
    this.tone("sine", freq * 2.01, freq * 2.01, { decay: 0.25, level: 0.06, wet: 0.5, ...shape });
  }

  /** 쨍: 어긋난 배음을 겹친 금속음 */
  metal(freq: number, shape: Shape = {}) {
    [1, 1.47, 2.09, 2.76, 3.52].forEach((ratio, i) =>
      this.tone("triangle", freq * ratio, freq * ratio * 0.995, {
        decay: 0.55 - i * 0.07,
        level: 0.11 - i * 0.015,
        wet: 0.6,
        ...shape,
      }),
    );
  }

  private envelope(start: number, { attack = 0.004, decay = 0.2, level = 0.3, wet = 0, pan = 0 }: Shape): GainNode {
    const gain = this.ctx.createGain();
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(level, start + attack);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + attack + decay);
    let node: AudioNode = gain;
    if (pan && this.ctx.createStereoPanner) {
      const panner = this.ctx.createStereoPanner();
      panner.pan.value = pan;
      gain.connect(panner);
      node = panner;
    }
    node.connect(this.out);
    if (wet > 0) {
      const send = this.ctx.createGain();
      send.gain.value = wet;
      node.connect(send);
      send.connect(this.reverb);
    }
    return gain;
  }
}

const RECIPES: Record<SoundName, (s: Synth) => void> = {
  card_move: (s) => {
    s.swoosh(6000, 1800, { attack: 0.01, decay: 0.09, level: 0.4, q: 0.9 });
    s.snap({ at: 0.07, decay: 0.015, level: 0.25 });
  },
  card_ready: (s) => {
    s.swoosh(2500, 7000, { attack: 0.04, decay: 0.04, level: 0.3 });
    s.snap({ at: 0.07, level: 0.6 });
    s.noise("lowpass", 3000, 500, { at: 0.07, decay: 0.07, level: 0.6 });
    s.kick(220, 70, { at: 0.07, decay: 0.12, level: 0.6 });
  },
  card_reveal: (s) => {
    s.swoosh(1200, 8000, { attack: 0.08, decay: 0.08, level: 0.45 });
    s.snap({ at: 0.11, level: 0.4 });
    s.bell(1047, { at: 0.11, level: 0.14 });
    s.bell(1568, { at: 0.11, level: 0.1 });
  },
  hit: (s) => {
    s.snap({ level: 0.8 });
    s.kick(200, 42, { decay: 0.3, level: 1 });
    s.noise("lowpass", 7000, 400, { decay: 0.2, level: 0.75 });
    s.noise("bandpass", 1600, 900, { decay: 0.08, level: 0.5, q: 2 });
  },
  counter: (s) => {
    s.swoosh(900, 5000, { attack: 0.05, decay: 0.03, level: 0.4 });
    s.snap({ at: 0.06, level: 0.9 });
    s.kick(260, 35, { at: 0.06, decay: 0.45, level: 1 });
    s.noise("lowpass", 9000, 250, { at: 0.06, decay: 0.35, level: 0.85, wet: 0.3 });
    s.tone("sawtooth", 160, 45, { at: 0.06, decay: 0.3, level: 0.2 });
    s.kick(150, 40, { at: 0.2, decay: 0.25, level: 0.7 });
    s.noise("lowpass", 4000, 300, { at: 0.2, decay: 0.15, level: 0.45 });
  },
  guard: (s) => {
    s.snap({ level: 0.7 });
    s.kick(180, 90, { decay: 0.1, level: 0.5 });
    s.metal(820, { level: 0.12 });
    s.noise("bandpass", 4200, 3000, { decay: 0.12, level: 0.35, q: 3 });
  },
  dodge: (s) => {
    s.swoosh(500, 7000, { attack: 0.05, decay: 0.12, level: 0.6, pan: -0.5 });
    s.swoosh(1200, 9000, { at: 0.07, attack: 0.03, decay: 0.12, level: 0.35, pan: 0.6 });
  },
  clash: (s) => {
    s.snap({ level: 0.9 });
    s.kick(160, 60, { decay: 0.15, level: 0.6 });
    s.metal(1150, { level: 0.13 });
    s.metal(1630, { at: 0.02, level: 0.09 });
    s.noise("highpass", 6000, 3500, { decay: 0.3, level: 0.35, wet: 0.4 });
  },
  grab: (s) => {
    s.swoosh(3000, 700, { attack: 0.02, decay: 0.1, level: 0.4 });
    s.snap({ at: 0.1, level: 0.5 });
    s.kick(170, 60, { at: 0.1, decay: 0.2, level: 0.8 });
    s.noise("lowpass", 1500, 300, { at: 0.1, decay: 0.15, level: 0.5 });
  },
  damage: (s) => {
    s.snap({ level: 0.5 });
    s.kick(150, 45, { decay: 0.25, level: 0.85 });
    s.noise("lowpass", 2500, 250, { decay: 0.15, level: 0.45 });
  },
  heal: (s) => {
    s.swoosh(800, 4000, { attack: 0.1, decay: 0.2, level: 0.2 });
    [784, 988, 1175, 1568].forEach((f, i) => s.bell(f, { at: i * 0.06, level: 0.14 }));
  },
  fp_up: (s) => {
    s.tone("square", 988, 988, { decay: 0.06, level: 0.09 });
    s.tone("square", 1319, 1319, { at: 0.06, decay: 0.16, level: 0.09, wet: 0.25 });
  },
  fp_down: (s) => {
    s.tone("square", 1175, 1175, { decay: 0.06, level: 0.08 });
    s.tone("square", 784, 740, { at: 0.06, decay: 0.16, level: 0.08 });
  },
  effect: (s) => {
    s.swoosh(600, 9000, { attack: 0.12, decay: 0.15, level: 0.35, wet: 0.3 });
    [1047, 1319, 1568, 2093].forEach((f, i) => s.bell(f, { at: 0.05 + i * 0.045, level: 0.12 }));
    s.noise("highpass", 8000, 12000, { at: 0.05, attack: 0.05, decay: 0.35, level: 0.12, wet: 0.5 });
  },
  passive: (s) => {
    s.bell(1568, { level: 0.14 });
    s.bell(2349, { at: 0.07, level: 0.12 });
  },
  shield: (s) => {
    s.snap({ level: 0.4 });
    s.tone("sine", 330, 300, { decay: 0.45, level: 0.3, wet: 0.3 });
    s.tone("triangle", 660, 640, { decay: 0.4, level: 0.12, wet: 0.4 });
    s.noise("highpass", 5000, 9000, { attack: 0.03, decay: 0.3, level: 0.12, wet: 0.5 });
  },
  combo: (s) => {
    s.swoosh(300, 6000, { attack: 0.14, decay: 0.05, level: 0.5 });
    s.snap({ at: 0.15, level: 0.7 });
    s.kick(200, 50, { at: 0.15, decay: 0.25, level: 0.9 });
    [523, 659, 784, 1047].forEach((f) => s.tone("sawtooth", f, f, { at: 0.15, decay: 0.3, level: 0.05, wet: 0.3 }));
  },
  catch: (s) => {
    s.noise("highpass", 6000, 6000, { decay: 0.03, level: 0.8 });
    s.swoosh(7000, 900, { at: 0.02, attack: 0.01, decay: 0.12, level: 0.5 });
    s.tone("square", 1568, 523, { at: 0.02, decay: 0.15, level: 0.08 });
    s.kick(180, 60, { at: 0.03, decay: 0.15, level: 0.6 });
  },
  break: (s) => {
    s.snap({ level: 0.9 });
    s.kick(140, 50, { decay: 0.18, level: 0.6 });
    s.noise("highpass", 3000, 1200, { decay: 0.3, level: 0.55, wet: 0.3 });
    for (let i = 0; i < 6; i++) {
      const f = 2500 + Math.random() * 3500;
      s.tone("triangle", f, f, { at: 0.02 + i * 0.025, decay: 0.12, level: 0.06, wet: 0.5, pan: Math.random() * 1.4 - 0.7 });
    }
  },
  shuffle: (s) => {
    for (let i = 0; i < 8; i++) {
      s.noise("bandpass", 4500, 2000, { at: i * 0.035, decay: 0.03, level: 0.25, q: 1, pan: i % 2 ? 0.4 : -0.4 });
    }
    s.snap({ at: 0.3, level: 0.4 });
  },
  phase: (s) => {
    s.swoosh(400, 3000, { attack: 0.08, decay: 0.15, level: 0.2 });
    s.bell(784, { at: 0.06, level: 0.16 });
  },
  turn: (s) => {
    s.kick(120, 50, { decay: 0.35, level: 0.7 });
    s.swoosh(300, 5000, { attack: 0.12, decay: 0.2, level: 0.3 });
    [392, 587, 784].forEach((f, i) => s.bell(f, { at: 0.04 + i * 0.07, level: 0.15, decay: 0.8 }));
  },
  prompt: (s) => {
    s.bell(1175, { level: 0.16, decay: 0.2 });
    s.bell(1760, { at: 0.08, level: 0.15, decay: 0.3 });
  },
  tick: (s) => {
    s.tone("square", 1400, 1400, { decay: 0.035, level: 0.08 });
    s.snap({ decay: 0.01, level: 0.15 });
  },
  win: (s) => {
    s.kick(160, 50, { decay: 0.3, level: 0.7 });
    [523, 659, 784, 1047].forEach((f, i) =>
      s.tone("square", f, f, { at: i * 0.1, decay: i === 3 ? 0.9 : 0.2, level: 0.08, wet: 0.35 }),
    );
    [1047, 1319, 1568].forEach((f) => s.bell(f, { at: 0.3, decay: 1.1, level: 0.12 }));
  },
  lose: (s) => {
    [392, 349, 311, 262].forEach((f, i) =>
      s.tone("triangle", f, f * 0.97, { at: i * 0.2, decay: i === 3 ? 1 : 0.35, level: 0.2, wet: 0.35 }),
    );
    s.kick(90, 40, { at: 0.6, decay: 0.5, level: 0.5 });
  },
  ui: (s) => {
    s.snap({ decay: 0.012, level: 0.25 });
    s.tone("sine", 900, 600, { decay: 0.05, level: 0.12 });
  },
};
