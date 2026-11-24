import { t } from "./i18n";
import { PHASE_LABELS, ZONE_LABELS } from "./labels";
import type { GameEvent, Side, ZoneName } from "./protocol";

/** 기록 창 줄 앞의 "나: " / "상대: "를 떼어 낼 때 쓴다(logEntries.ts). */
export const ME_LABEL = t("나");
export const OPPONENT_LABEL = t("상대");

/** 기록 창에 보여 줄 한 줄. 화면에 쓸 만한 이벤트만 문장으로 만들고 나머지는 null. */
export function eventText(event: GameEvent, me: Side): string | null {
  const p = event.payload as Record<string, unknown>;
  const who = (side: unknown) => (side === me ? ME_LABEL : side === "p1" || side === "p2" ? OPPONENT_LABEL : "");
  const zone = (name: unknown) => ZONE_LABELS[name as ZoneName] ?? String(name ?? "");
  const phase = (name: unknown) => PHASE_LABELS[String(name)] ?? String(name ?? "");
  const card = (value: unknown, fallback = t("카드")) => String(value ?? fallback);
  const signed = (amount: number) => `${amount > 0 ? "+" : ""}${amount}`;
  const actor = who(event.actor);
  switch (event.type) {
    case "automatic_game_started":
      return t("대전 시작");
    case "opening_review_started":
      return t("서로 상대의 시작 패를 확인합니다");
    case "opening_review_confirmed":
      return t("{who}: 시작 패 확인 완료", { who: actor });
    case "phase_started":
      return t("턴 {turn} · {phase} 페이즈", { turn: String(p.turn ?? ""), phase: phase(p.phase) });
    case "card_moved":
      // 토큰은 사이드 덱에서 꺼내는 것이 아니라 생성한다(Q-AUTO-012).
      if (p.token_created) {
        return t("{who}: {card} 생성 → {to}", { who: who(p.to_player), card: card(p.card_label, t("토큰")), to: zone(p.to_zone) });
      }
      return `${who(p.to_player)}: ${card(p.card_label)} ${zone(p.from_zone)} → ${zone(p.to_zone)}`;
    case "private_event":
      if (p.event_type === "card_moved") {
        return t("{who}: 비공개 카드 {from} → {to}", { who: actor, from: zone(p.from_zone), to: zone(p.to_zone) });
      }
      return null;
    case "hp_changed": {
      const amount = Number(p.amount ?? 0);
      return `${actor} HP ${String(p.before)} → ${String(p.after)} (${signed(amount)})`;
    }
    case "fp_changed": {
      const amount = Number(p.amount ?? 0);
      return `${actor} FP ${signed(amount)}`;
    }
    case "damage_dealt":
      return t("{who}에게 {amount} 데미지", { who: who(p.target), amount: String(p.amount) });
    case "battle_judged":
      return t("배틀 판정: {result}", { result: String(p.result ?? "") });
    case "card_broken":
      return t("{who}: 카드 브레이크", { who: actor });
    case "combo_started":
      return t("{who}: 콤보 시작", { who: actor });
    case "combo_skipped": {
      // 콤보 판정이 났지만 이어 낼 수 없어 콤보 타임을 건너뛴 경우. 사유를 보여 주지 않으면
      // 콤보가 "안 된다"고 오해하기 쉽다(8.3.1: 임의의 공격 + 그보다 속도가 정확히 1 큰 공격).
      const reasons: Record<string, string> = {
        normal_combo_requires_two_cards: t("이어 낼 2·3콤보 조합(속도 차 1)이 없어 콤보 생략"),
        special_combo_requires_pair: t("이어 낼 1·2콤보 조합이 없어 콤보 생략"),
        card_effect_ended_combo_time: t("카드 효과로 콤보 불가"),
      };
      return `${actor}: ${reasons[String(p.reason)] ?? t("콤보 생략")}`;
    }
    case "catch_started":
      return t("{who}: 캐치", { who: actor });
    case "catch_skipped": {
      const reasons: Record<string, string> = {
        no_legal_card: p.max_speed != null
          ? t("캐치할 수 있는 {speed}속도 이하 공격이 없어 캐치 생략", { speed: String(p.max_speed) })
          : t("캐치할 수 있는 공격이 없어 캐치 생략"),
        usage_limit: t("사용 횟수 제한으로 캐치 생략"),
        combo_time_started: t("콤보 타임에 들어가 캐치 생략"),
        timing_missed: t("캐치 타이밍을 놓침"),
        battle_ended_by_effect: t("효과로 배틀이 끝나 캐치 생략"),
      };
      return `${actor}: ${reasons[String(p.reason)] ?? t("캐치 생략")}`;
    }
    // 수동 모드
    case "move_card": {
      const target = who(p.to_player) === actor ? zone(p.to_zone) : `${who(p.to_player)} ${zone(p.to_zone)}`;
      return `${actor}: ${card(p.card_label)} ${zone(p.from_zone)} → ${target}`;
    }
    case "bulk_move":
      return t("{who}: 배틀존 카드 {count}장 → {to}", { who: who(p.player), count: String(p.count ?? ""), to: zone(p.to_zone) });
    case "hp":
    case "fp": {
      const amount = Number(p.amount ?? 0);
      return `${who(p.target)} ${event.type.toUpperCase()} ${String(p.before)} → ${String(p.after)} (${signed(amount)})`;
    }
    case "fp_reset":
      return t("{who} FP 초기화", { who: who(p.target) });
    case "set_phase":
      return t("{who}: {phase} 페이즈로", { who: actor, phase: phase(p.to_phase) });
    case "next_turn":
      return t("{who}: 다음 턴", { who: actor });
    case "phase_advance":
      return p.to_phase ? t("{phase} 페이즈", { phase: phase(p.to_phase) }) : t("페이즈 진행");
    case "set_done":
      return `${who(p.target ?? event.actor)} ${p.done === false ? t("완료 취소") : t("완료")}`;
    case "request_action":
      return t("{who} → {target}: 행동 요청", { who: actor, target: who(p.target) });
    case "shuffle_hand":
      return t("{who}: 손패 섞기", { who: who(p.player) });
    case "set_hand_visibility":
      return p.face_up ? t("{who}: 손패 공개", { who: who(p.target) }) : t("{who}: 손패 비공개", { who: who(p.target) });
    case "set_visibility":
      return `${actor}: ${card(p.card_label)} ${p.face_up ? t("공개") : t("비공개")}`;
    case "passive":
      return t("{who} 패시브 · {label}", {
        who: who(p.target),
        label: String((p.state as Record<string, unknown> | undefined)?.label ?? p.label ?? p.key ?? ""),
      });
    case "timer":
      return p.running ? t("{who}: 10초 타이머 시작", { who: actor }) : t("{who}: 10초 타이머 정지", { who: actor });
    case "signal":
      return `${actor}: ${String(p.label ?? p.signal ?? "")}`;
    case "log_note":
      return `${actor}: ${String(p.text ?? "")}`;
    case "import_card":
      return t("{who}: {card} 생성 → 루멘", { who: actor, card: card(p.card_label ?? p.card_name) });
    // 캐릭터 전용(수동 모드)
    case "yohan_declare_reveal":
      return t("{who}: 선언 「{declaration}」 · 상대 {card} 공개", {
        who: actor,
        declaration: String(p.declaration_label ?? p.declaration ?? ""),
        card: card(p.card_label),
      });
    case "yohan_foresight_reveal":
      return t("{who}: 예지 · 상대 {card} 공개", { who: actor, card: card(p.card_label) });
    case "nia_lumen_cards_to_list":
      return t("{who}: 루멘 정리 · {count}장 → 리스트", { who: actor, count: String(p.count ?? 0) });
    case "cmyk_new_single":
      return t("{who}: 뉴 싱글 생성", { who: actor });
    case "blackout_random_get":
      return t("{who}: {source} · 상대 리스트 → {card}", {
        who: actor,
        source: String(p.source_card_label ?? t("블랙아웃")),
        card: card(p.card_label),
      });
    case "attach_card":
      return t("{who}: CMYK 세트", { who: actor });
    case "game_finished":
    case "automatic_game_finished":
      return p.winner ? t("{who} 승리", { who: who(p.winner) }) : t("대전 종료");
    default:
      return null;
  }
}
