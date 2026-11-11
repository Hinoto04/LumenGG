import type { CalcState } from "./types";

export interface CalculatorLogRow {
  id: string;
  target: "p1" | "p2" | null;
  player: string;
  title: string;
  detail: string;
  time: string;
  undone: boolean;
  /** 숫자 변화(HP·FP·카운터). 시뮬레이터 기록처럼 오른쪽에 +초록/−빨강으로 보여준다. */
  delta: { label: string; amount: number } | null;
}
const own = (value: any, key: string) =>
  value && Object.prototype.hasOwnProperty.call(value, key);
function stateValue(state: any): unknown {
  if (own(state, "value")) return state.value;
  if (own(state, "count")) return state.count;
  return undefined;
}
export function calculatorLogRows(
  state: CalcState,
  t: (key: string) => string,
): CalculatorLogRow[] {
  return state.events
    .filter(
      (event) =>
        !["timer", "timer_start", "timer_stop", "round_timer"].includes(
          event.type,
        ),
    )
    .map((event, index) => ({ event, index }))
    .sort(
      (a, b) =>
        (Date.parse(b.event.created_at) || 0) -
          (Date.parse(a.event.created_at) || 0) ||
        eventSequence(b.event.id) - eventSequence(a.event.id) ||
        a.index - b.index,
    )
    .slice(0, 100)
    .map(({ event, index }) => {
      const target: "p1" | "p2" | null =
        event.target === "p1" || event.target === "p2" ? event.target : null;
      const player = target ? state.players[target] : undefined;
      const payload = event.payload || {};
      const controls = player?.character?.passive?.controls || [];
      const key = payload.key || event.key;
      const control = controls.find((c: any) => c.key === key);
      const format = (value: unknown): string => {
        if (value === undefined) return t("기록 없음");
        if (value === null || value === "") return t("선택 없음");
        if (
          ["toggle", "thresholdAction", "status", "latchedStatus"].includes(
            control?.type,
          )
        ) {
          if ([false, 0, "0", "false", "off", "OFF"].includes(value as any))
            return t("비활성");
          if ([true, 1, "1", "true", "on", "ON"].includes(value as any))
            return t("활성");
        }
        if (typeof value === "boolean") return t(value ? "활성" : "비활성");
        const choice = control?.choices?.find(
          (c: any) => (c.value ?? c.key) === value,
        );
        if (choice) return choice.label;
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
      };
      let title = t(
        (
          {
            hp: "HP",
            fp: "FP",
            fp_reset: "FP 초기화",
            passive: "패시브",
            undo: "HP 되돌리기",
            reset: "전체 초기화",
            reset_session: "전체 초기화",
            sudden_death: "서든 데스",
            sudden_turn: "남은 턴",
            character: "캐릭터 변경",
            set_start: "세트 시작",
            set_report: "세트 결과",
            extra_time: "추가 시간",
          } as Record<string, string>
        )[event.type] || event.type,
      );
      let before: unknown, after: unknown;
      let detail = "";
      if (event.type === "hp" || event.type === "undo") {
        before = event.hp_before;
        after = event.hp_after;
        detail = `${format(before)} → ${format(after)}`;
        if (payload.shield_absorbed) detail += ` · ${t("보호막 흡수")} ${payload.shield_absorbed}`;
        if (payload.shield_restored) detail += ` · ${t("보호막 복원")} ${payload.shield_restored}`;
      } else if (event.type === "fp" || event.type === "fp_reset") {
        before = own(event, "fp_before") ? event.fp_before : payload.before;
        after = own(event, "fp_after") ? event.fp_after : payload.after;
        detail = `${format(before)} → ${format(after)}`;
      } else if (event.type === "passive") {
        title =
          payload.label ||
          control?.label ||
          payload.after_state?.label ||
          payload.state?.label ||
          event.label ||
          key ||
          t("패시브");
        if (key === "finf_shield") title = t("보호막");
        before = stateValue(payload.before_state);
        after = stateValue(payload.after_state || payload.state);
        if (after === undefined && own(payload, "value")) after = payload.value;
        // 처음 바뀐 값은 이전 기록이 없으니 바뀐 값만 보여 준다.
        detail = before === undefined ? format(after) : `${format(before)} → ${format(after)}`;
      } else if (event.type === "sudden_death") {
        detail = payload.turn_advanced
          ? `${t("남은 턴")} ${payload.turns_remaining ?? ""}`
          : t(payload.enabled ? "진입" : "해제");
      } else if (event.type === "set_start" || event.type === "set_report") {
        const set = payload.set_number ? `${payload.set_number}S` : "";
        const winner = event.type === "set_report" && target ? `${player?.name || ""} ${t("승")}` : "";
        detail = [set, winner].filter(Boolean).join(" · ");
      } else if (event.type === "extra_time") {
        detail = `+${Math.round(Number(event.amount || 0) / 60)}${t("분")}`;
      } else if (payload.note) detail = String(payload.note);
      const date = new Date(event.created_at);
      const numeric = (value: unknown) =>
        typeof value === "number" || (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value)));
      const change =
        numeric(before) && numeric(after) ? Number(after) - Number(before) : 0;
      const deltaLabel =
        event.type === "hp" || event.type === "undo"
          ? "HP"
          : event.type === "fp" || event.type === "fp_reset"
            ? "FP"
            : "";
      return {
        id: String(event.id ?? `log-${index}`),
        target,
        player: target
          ? `${t(target === "p1" ? "플레이어1" : "플레이어2")} · ${event.player_name || player?.name || ""}`
          : t("전체 플레이어"),
        title,
        detail,
        time: Number.isFinite(date.getTime())
          ? date.toLocaleTimeString(undefined, {
              hour12: false,
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })
          : "",
        undone: !!event.undone,
        delta: change ? { label: deltaLabel, amount: change } : null,
      };
    });
}
function eventSequence(id: unknown): number {
  if (typeof id === "number") return id;
  const match = String(id).match(/^\d+-(\d+)$/);
  return match ? Number(match[1]) : 0;
}
