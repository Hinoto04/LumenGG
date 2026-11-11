import type { GameEvent, PlayEnvelope, Side } from "../protocol";
import { usePlay } from "../store";
import { playSound, type SoundName } from "./sfx";

/** 판정 결과 → 소리. 양쪽 결과 중 더 강한 것 하나만 낸다. */
const JUDGE_SOUNDS: [SoundName, string[]][] = [
  ["counter", ["counter", "countered"]],
  ["grab", ["grabbed"]],
  ["hit", ["hit", "failed_defense"]],
  ["guard", ["guard", "guarded"]],
  ["clash", ["clash"]],
  ["dodge", ["dodge", "opponent_dodge"]],
];

/**
 * 재생기(anim/playback.ts)가 이벤트 하나를 화면에 올릴 때 부른다.
 * event는 수동 모드 이벤트를 자동 엔진 모양으로 바꾼 뒤의 것이다.
 */
export function soundForEvent(event: GameEvent, base: PlayEnvelope, me: Side) {
  const payload = event.payload as Record<string, unknown>;
  switch (event.type) {
    case "phase_started": {
      const turnChanged = payload.turn != null && Number(payload.turn) !== Number(base.state.turn);
      playSound(turnChanged ? "turn" : "phase");
      return;
    }
    case "card_moved": {
      const toBattle = payload.to_zone === "battle";
      playSound(toBattle ? "card_ready" : "card_move");
      return;
    }
    case "private_event":
      if (payload.event_type === "card_moved") playSound(payload.to_zone === "battle" ? "card_ready" : "card_move");
      return;
    case "battle_revealed":
      playSound("card_reveal");
      return;
    case "battle_judged": {
      const results = Object.values((payload.result ?? {}) as Record<string, string>);
      const found = JUDGE_SOUNDS.find(([, keys]) => results.some((result) => keys.includes(result)));
      if (found) playSound(found[0]);
      return;
    }
    case "hp_changed": {
      const amount = Number(payload.amount ?? 0);
      if (amount) playSound(amount < 0 ? "damage" : "heal");
      return;
    }
    case "fp_changed": {
      const amount = Number(payload.amount ?? 0);
      if (amount) playSound(amount > 0 ? "fp_up" : "fp_down");
      return;
    }
    case "effect_resolved":
    case "signal":
      playSound("effect");
      return;
    case "counter_changed":
      if (Number(payload.amount ?? 0)) playSound("passive");
      return;
    case "state_gained":
      playSound("passive");
      return;
    case "shield_absorbed":
      playSound("shield");
      return;
    case "combo_started":
      playSound("combo");
      return;
    case "catch_started":
      playSound("catch");
      return;
    case "card_broken":
      playSound("break");
      return;
    case "zone_shuffled":
      playSound("shuffle");
      return;
    case "card_guess_resolved":
      playSound(payload.correct ?? payload.guess_correct ? "hit" : "guard");
      return;
    case "game_finished": {
      const winner = payload.winner as Side | null;
      if (!winner) playSound("phase");
      else playSound(base.role === "viewer" || winner === me ? "win" : "lose");
      return;
    }
    default:
      return;
  }
}

/** 내 선택 창이 새로 열리면 알림음을 낸다. main.tsx에서 한 번 부른다. */
export function installDecisionSound() {
  let last: string | null = null;
  return usePlay.subscribe(({ envelope }) => {
    const decision = envelope?.pending_decision;
    if (!envelope || !decision || envelope.role === "viewer" || decision.owner !== envelope.role) {
      last = null;
      return;
    }
    const key = `${envelope.id}:${decision.id ?? decision.prompt}`;
    if (key === last) return;
    last = key;
    playSound("prompt");
  });
}
