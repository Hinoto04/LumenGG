import { useEffect, useRef, useState } from "react";
import { playSound, useSound, type SoundName } from "../sound/sfx";

/** 들어보기: 대전에서 자주 나는 소리를 차례로 들려준다. */
const DEMO: SoundName[] = ["card_ready", "card_reveal", "hit", "counter", "guard", "dodge", "clash", "effect", "combo", "catch", "break", "turn"];

function playDemo() {
  DEMO.forEach((name, i) => setTimeout(() => playSound(name), i * 650));
}

/** 대전 화면 위쪽 메뉴의 '소리' 칩: 누르면 음소거와 음량 조절이 열린다. */
export function SoundButton() {
  const { volume, muted, setVolume, setMuted } = useSound();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const close = (event: PointerEvent) => {
      if (!ref.current?.contains(event.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", close);
    return () => window.removeEventListener("pointerdown", close);
  }, [open]);
  const silent = muted || volume <= 0;
  return (
    <div className="sound-menu" ref={ref}>
      <button
        type="button"
        className={`btn-chip ${silent ? "" : "is-on"}`}
        aria-expanded={open}
        title="효과음"
        onClick={() => setOpen(!open)}
      >
        {silent ? "소리 끔" : "소리"}
      </button>
      {open && (
        <div className="sound-pop" role="dialog" aria-label="효과음 설정">
          <label className="sound-row">
            <input type="checkbox" checked={!muted} onChange={(event) => setMuted(!event.target.checked)} />
            <span>효과음</span>
          </label>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={Math.round(volume * 100)}
            aria-label="음량"
            disabled={muted}
            onChange={(event) => setVolume(Number(event.target.value) / 100)}
            onPointerUp={() => playSound("card_ready")}
          />
          <span className="sound-value">{muted ? "꺼짐" : `${Math.round(volume * 100)}%`}</span>
          <button type="button" className="btn-chip sound-demo" disabled={muted} onClick={playDemo}>
            들어보기
          </button>
        </div>
      )}
    </div>
  );
}
