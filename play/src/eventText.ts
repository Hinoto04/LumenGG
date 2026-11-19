import { PHASE_LABELS, ZONE_LABELS } from "./labels";
import type { GameEvent, Side, ZoneName } from "./protocol";

/** 기록 창에 보여 줄 한 줄. 화면에 쓸 만한 이벤트만 문장으로 만들고 나머지는 null. */
export function eventText(event: GameEvent, me: Side): string | null {
  const p = event.payload as Record<string, unknown>;
  const who = (side: unknown) => (side === me ? "나" : side === "p1" || side === "p2" ? "상대" : "");
  const zone = (name: unknown) => ZONE_LABELS[name as ZoneName] ?? String(name ?? "");
  switch (event.type) {
    case "automatic_game_started":
      return "대전 시작";
    case "opening_review_started":
      return "서로 상대의 시작 패를 확인합니다";
    case "opening_review_confirmed":
      return `${who(event.actor)}: 시작 패 확인 완료`;
    case "phase_started":
      return `턴 ${String(p.turn ?? "")} · ${PHASE_LABELS[String(p.phase)] ?? String(p.phase)} 페이즈`;
    case "card_moved":
      // 토큰은 사이드 덱에서 꺼내는 것이 아니라 생성한다(Q-AUTO-012).
      if (p.token_created) return `${who(p.to_player)}: ${String(p.card_label ?? "토큰")} 생성 → ${zone(p.to_zone)}`;
      return `${who(p.to_player)}: ${String(p.card_label ?? "카드")} ${zone(p.from_zone)} → ${zone(p.to_zone)}`;
    case "private_event":
      if (p.event_type === "card_moved") return `${who(event.actor)}: 비공개 카드 ${zone(p.from_zone)} → ${zone(p.to_zone)}`;
      return null;
    case "hp_changed": {
      const amount = Number(p.amount ?? 0);
      return `${who(event.actor)} HP ${String(p.before)} → ${String(p.after)} (${amount > 0 ? "+" : ""}${amount})`;
    }
    case "fp_changed": {
      const amount = Number(p.amount ?? 0);
      return `${who(event.actor)} FP ${amount > 0 ? "+" : ""}${amount}`;
    }
    case "damage_dealt":
      return `${who(p.target)}에게 ${String(p.amount)} 데미지`;
    case "battle_judged":
      return `배틀 판정: ${String(p.result ?? "")}`;
    case "card_broken":
      return `${who(event.actor)}: 카드 브레이크`;
    case "combo_started":
      return `${who(event.actor)}: 콤보 시작`;
    case "combo_skipped": {
      // 콤보 판정이 났지만 이어 낼 수 없어 콤보 타임을 건너뛴 경우. 사유를 보여 주지 않으면
      // 콤보가 "안 된다"고 오해하기 쉽다(8.3.1: 임의의 공격 + 그보다 속도가 정확히 1 큰 공격).
      const reasons: Record<string, string> = {
        normal_combo_requires_two_cards: "이어 낼 2·3콤보 조합(속도 차 1)이 없어 콤보 생략",
        special_combo_requires_pair: "이어 낼 1·2콤보 조합이 없어 콤보 생략",
        card_effect_ended_combo_time: "카드 효과로 콤보 불가",
      };
      return `${who(event.actor)}: ${reasons[String(p.reason)] ?? "콤보 생략"}`;
    }
    case "catch_started":
      return `${who(event.actor)}: 캐치`;
    case "catch_skipped": {
      const reasons: Record<string, string> = {
        no_legal_card: p.max_speed != null
          ? `캐치할 수 있는 ${String(p.max_speed)}속도 이하 공격이 없어 캐치 생략`
          : "캐치할 수 있는 공격이 없어 캐치 생략",
        usage_limit: "사용 횟수 제한으로 캐치 생략",
        combo_time_started: "콤보 타임에 들어가 캐치 생략",
        timing_missed: "캐치 타이밍을 놓침",
        battle_ended_by_effect: "효과로 배틀이 끝나 캐치 생략",
      };
      return `${who(event.actor)}: ${reasons[String(p.reason)] ?? "캐치 생략"}`;
    }
    // 수동 모드
    case "move_card":
      return `${who(event.actor)}: ${String(p.card_label ?? "카드")} ${zone(p.from_zone)} → ${who(p.to_player) === who(event.actor) ? "" : `${who(p.to_player)} `}${zone(p.to_zone)}`;
    case "bulk_move":
      return `${who(p.player)}: 배틀존 카드 ${String(p.count ?? "")}장 → ${zone(p.to_zone)}`;
    case "hp":
    case "fp": {
      const amount = Number(p.amount ?? 0);
      return `${who(p.target)} ${event.type.toUpperCase()} ${String(p.before)} → ${String(p.after)} (${amount > 0 ? "+" : ""}${amount})`;
    }
    case "fp_reset":
      return `${who(p.target)} FP 초기화`;
    case "set_phase":
      return `${who(event.actor)}: ${PHASE_LABELS[String(p.to_phase)] ?? String(p.to_phase ?? "")} 페이즈로`;
    case "next_turn":
      return `${who(event.actor)}: 다음 턴`;
    case "phase_advance":
      return p.to_phase ? `${PHASE_LABELS[String(p.to_phase)] ?? String(p.to_phase)} 페이즈` : "페이즈 진행";
    case "set_done":
      return `${who(p.target ?? event.actor)} ${p.done === false ? "완료 취소" : "완료"}`;
    case "request_action":
      return `${who(event.actor)} → ${who(p.target)}: 행동 요청`;
    case "shuffle_hand":
      return `${who(p.player)}: 손패 섞기`;
    case "set_hand_visibility":
      return `${who(p.target)}: 손패 ${p.face_up ? "공개" : "비공개"}`;
    case "set_visibility":
      return `${who(event.actor)}: ${String(p.card_label ?? "카드")} ${p.face_up ? "공개" : "비공개"}`;
    case "passive":
      return `${who(p.target)} 패시브 · ${String((p.state as Record<string, unknown> | undefined)?.label ?? p.label ?? p.key ?? "")}`;
    case "timer":
      return `${who(event.actor)}: 10초 타이머 ${p.running ? "시작" : "정지"}`;
    case "signal":
      return `${who(event.actor)}: ${String(p.label ?? p.signal ?? "")}`;
    case "log_note":
      return `${who(event.actor)}: ${String(p.text ?? "")}`;
    case "import_card":
      return `${who(event.actor)}: ${String(p.card_label ?? p.card_name ?? "카드")} 생성 → 루멘`;
    // 캐릭터 전용(수동 모드)
    case "yohan_declare_reveal":
      return `${who(event.actor)}: 선언 「${String(p.declaration_label ?? p.declaration ?? "")}」 · 상대 ${String(p.card_label ?? "카드")} 공개`;
    case "yohan_foresight_reveal":
      return `${who(event.actor)}: 예지 · 상대 ${String(p.card_label ?? "카드")} 공개`;
    case "nia_lumen_cards_to_list":
      return `${who(event.actor)}: 루멘 정리 · ${String(p.count ?? 0)}장 → 리스트`;
    case "cmyk_new_single":
      return `${who(event.actor)}: 뉴 싱글 생성`;
    case "blackout_random_get":
      return `${who(event.actor)}: ${String(p.source_card_label ?? "블랙아웃")} · 상대 리스트 → ${String(p.card_label ?? "카드")}`;
    case "attach_card":
      return `${who(event.actor)}: CMYK 세트`;
    case "game_finished":
    case "automatic_game_finished":
      return p.winner ? `${who(p.winner)} 승리` : "대전 종료";
    default:
      return null;
  }
}
