import { hasAudioSession, playSound, useSound, type SoundName } from "../sound/sfx";

/** 들어보기: 대전에서 자주 나는 소리를 차례로 들려준다. */
const DEMO: SoundName[] = ["card_ready", "card_reveal", "hit", "counter", "guard", "dodge", "clash", "effect", "combo", "catch", "break", "turn"];

function playDemo() {
  DEMO.forEach((name, i) => setTimeout(() => playSound(name), i * 650));
}

/** 메뉴 안의 효과음 설정: 켜기·끄기, 음량, 들어보기 */
export function SoundSettings() {
  const { volume, muted, ignoreSilentSwitch, setVolume, setMuted, setIgnoreSilentSwitch } = useSound();
  return (
    <div className="menu-sound">
      <label className="menu-row menu-toggle">
        <span>효과음</span>
        <input type="checkbox" checked={!muted} onChange={(event) => setMuted(!event.target.checked)} />
      </label>
      <div className="sound-row">
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
        <button type="button" className="btn-secondary" disabled={muted} onClick={playDemo}>
          들어보기
        </button>
      </div>
      {hasAudioSession() && (
        <label className="menu-row menu-toggle">
          <span>
            무음 모드에서도 재생
            <small className="muted">아이폰 무음 스위치를 켜도 효과음을 냅니다. 듣던 음악이 멈출 수 있습니다.</small>
          </span>
          <input
            type="checkbox"
            checked={ignoreSilentSwitch}
            disabled={muted}
            onChange={(event) => setIgnoreSilentSwitch(event.target.checked)}
          />
        </label>
      )}
    </div>
  );
}
