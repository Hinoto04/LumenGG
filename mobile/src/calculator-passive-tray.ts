/**
 * 패시브 트레이: 웹(esbuild 번들 CalculatorPassiveTray)과 앱이 함께 쓰는 화면 모델.
 * 선언형 패시브 정의를 "이름 · 현재 상태 · 조작 가능 여부 · 조건 안내"가 붙은 항목으로 바꾼다.
 */
import { conditionMet, passiveActions, passiveGet } from "./core";
import { passiveActive, nextTaoEffect } from "./calculator-display";
import presentations from "./calculator-passive-visuals.json";
import type {
  Action,
  Condition,
  PassiveControl,
  PassiveDefinition,
  Player,
} from "./types";

type Control = Omit<PassiveControl, "choices"> & {
  labels?: Record<string, string>;
  unit?: string;
  choices?: {
    value?: any;
    key?: any;
    label: string;
    labels?: Record<string, string>;
  }[];
};

export type TrayChoice = { value: string; label: string; selected: boolean };
export type TrayItem = {
  key: string;
  kind: "toggle" | "counter" | "trigger" | "status" | "choice" | "text";
  label: string;
  /** 켜짐(토글·발동·상태) 또는 0보다 큰 카운터 */
  active: boolean;
  /** 지금 누를 수 있는가(조작 권한과 별개) */
  enabled: boolean;
  /** 발동 조건 충족(trigger 전용) */
  ready?: boolean;
  /** 지금 눌러야 진행되는 항목(발동 가능, 타오 조화 효과 선택 대기) */
  attention?: boolean;
  value?: number | string;
  max?: number;
  unit?: string;
  choices?: TrayChoice[];
  /** 조건·자동 발동 안내. 빈 문자열이면 표시하지 않는다. */
  hint: string;
  /** 일러스트 심볼 이름(calculator-clean-icons). 없으면 undefined. */
  symbol?: string;
};

const TEXT: Record<string, Record<string, string>> = {
  ko: {
    atLeast: "{a} {v} 이상",
    atMost: "{a} {v} 이하",
    hpAtMost: "HP {v} 이하",
    allEquals: "{a} 모두 {v}",
    allAtLeast: "{a} 모두 {v} 이상",
    active: "{a} 활성",
    auto: "자동",
    needs: "{c} 필요",
    when: "{c}일 때 선택",
    keep: "유지 {c}",
    taoLocked: "조화 효과를 먼저 선택",
    resets: "사용 시 {a} 초기화",
  },
  en: {
    atLeast: "{a} ≥ {v}",
    atMost: "{a} ≤ {v}",
    hpAtMost: "HP ≤ {v}",
    allEquals: "{a} all {v}",
    allAtLeast: "{a} all ≥ {v}",
    active: "{a} on",
    auto: "Auto",
    needs: "Needs {c}",
    when: "When {c}",
    keep: "Keeps while {c}",
    taoLocked: "Choose a Harmony effect first",
    resets: "Resets {a}",
  },
  ja: {
    atLeast: "{a} {v}以上",
    atMost: "{a} {v}以下",
    hpAtMost: "HP {v}以下",
    allEquals: "{a} すべて{v}",
    allAtLeast: "{a} すべて{v}以上",
    active: "{a} 有効",
    auto: "自動",
    needs: "{c}で使用可",
    when: "{c}で選択可",
    keep: "{c}で維持",
    taoLocked: "先に調和効果を選択",
    resets: "使用時に{a}をリセット",
  },
};
function text(language: string, key: string, values: Record<string, string>) {
  const template = (TEXT[language] || TEXT.ko)![key] || TEXT.ko![key] || "";
  return template.replace(/\{(\w)\}/g, (_, name) => values[name] ?? "");
}

export function controlLabel(control: Control, language: string): string {
  return control.labels?.[language] || control.label || control.key;
}

function controls(definition: PassiveDefinition): Control[] {
  return [
    ...(definition.controls || []),
    ...(definition.badges || []).map((b) => ({ ...b, type: b.type || "status" })),
  ] as Control[];
}

function labelOf(definition: PassiveDefinition, key: string | undefined, language: string) {
  const found = controls(definition).find((c) => c.key === key);
  return found ? controlLabel(found, language) : key || "";
}

/** 조건을 사람이 읽는 짧은 문장으로 바꾼다. 모르는 조건은 빈 문자열. */
export function conditionText(
  condition: Condition | undefined,
  definition: PassiveDefinition,
  language = "ko",
): string {
  if (!condition) return "";
  const nested = condition.all || condition.any || condition.conditions;
  if (nested && (condition.all || condition.any || ["all", "any"].includes(condition.type || "")))
    return nested
      .map((c) => conditionText(c, definition, language))
      .filter(Boolean)
      .join(condition.any || condition.type === "any" ? " / " : " · ");
  const names = (condition.keys || []).map((k) => labelOf(definition, k, language)).join("·");
  const a = labelOf(definition, condition.key, language);
  const v = String(condition.value ?? "");
  switch (condition.type) {
    case "hpAtMost":
      return text(language, "hpAtMost", { v });
    case "counterAtLeast":
      return text(language, "atLeast", { a, v });
    case "counterAtMost":
      return text(language, "atMost", { a, v });
    case "active":
    case "truthy":
    case "keyActive":
      return text(language, "active", { a });
    case "allEquals":
      return text(language, "allEquals", { a: names, v });
    case "allAtLeast":
      return text(language, "allAtLeast", { a: names, v });
    default:
      return "";
  }
}

function theme(player: Player): string {
  return player.character?.calculator_ui?.theme_key || "";
}
function symbolFor(player: Player, key: string): string | undefined {
  const entry = (presentations as Record<string, any>)[theme(player)];
  return entry?.controls?.[key]?.symbol;
}

function isTao(definition: PassiveDefinition): boolean {
  return (
    definition.adapter === "tao" ||
    controls(definition).some((c) => c.key === "harmony_effect")
  );
}
export function taoHarmony(player: Player): boolean {
  const yang = Number(passiveGet(player, "yang_counter"));
  const yin = Number(passiveGet(player, "yin_counter"));
  return (
    (yang === 4 && yin === 4) ||
    (passiveActive(passiveGet(player, "harmony", false)) && yang >= 3 && yin >= 3)
  );
}
function taoLocked(player: Player): boolean {
  return (
    taoHarmony(player) &&
    !["damage_100", "fp_1"].includes(String(passiveGet(player, "harmony_effect", "")))
  );
}

function value(player: Player, control: Control) {
  const initial = player.character?.initial_passive_state?.[control.key];
  return passiveGet(
    player,
    control.key,
    control.default ?? control.initial ?? initial?.value ?? initial?.count ?? 0,
  );
}

export function passiveTray(
  player: Player,
  definition: PassiveDefinition,
  language = "ko",
): TrayItem[] {
  const tao = isTao(definition);
  const items: TrayItem[] = [];
  for (const control of controls(definition)) {
    if (control.visibleWhen && !conditionMet(control.visibleWhen, player)) continue;
    const label = controlLabel(control, language);
    const current = value(player, control);
    const gate = !control.enableWhen || conditionMet(control.enableWhen, player);
    const base = { key: control.key, label, symbol: symbolFor(player, control.key) };
    switch (control.type) {
      case "counter": {
        const locked = tao && ["yang_counter", "yin_counter"].includes(control.key) && taoLocked(player);
        const number = Math.max(0, Number(current) || 0);
        items.push({
          ...base,
          kind: "counter",
          value: number,
          max: control.max,
          unit: control.unit,
          active: number > 0,
          enabled: gate && !locked,
          hint: locked
            ? text(language, "taoLocked", {})
            : gate
              ? ""
              : text(language, "when", { c: conditionText(control.enableWhen, definition, language) }),
        });
        break;
      }
      case "thresholdAction": {
        const active = passiveActive(current);
        const ready = conditionMet(control.requires || control.activateWhen || control.condition, player);
        const requirement = conditionText(control.requires || control.activateWhen || control.condition, definition, language);
        const resets = (control.resetKeys || []).map((k) => labelOf(definition, k, language)).join("·");
        items.push({
          ...base,
          kind: "trigger",
          active,
          ready,
          attention: gate && ready && !active,
          enabled: gate && (active || ready),
          hint: active
            ? ""
            : ready
              ? resets ? text(language, "resets", { a: resets }) : ""
              : requirement ? text(language, "needs", { c: requirement }) : "",
        });
        break;
      }
      case "status":
      case "latchedStatus": {
        const active =
          control.type === "status"
            ? conditionMet(control.condition, player)
            : tao && control.key === "harmony"
              ? taoHarmony(player)
              : (!!control.activateWhen && conditionMet(control.activateWhen, player)) ||
                (passiveActive(current) && (!control.keepWhile || conditionMet(control.keepWhile, player)));
        const activate = conditionText(control.condition || control.activateWhen, definition, language);
        const keep = conditionText(control.keepWhile, definition, language);
        const auto = text(language, "auto", {});
        items.push({
          ...base,
          kind: "status",
          active,
          enabled: false,
          hint: active && keep ? `${auto} · ${text(language, "keep", { c: keep })}` : activate ? `${auto} · ${activate}` : auto,
        });
        break;
      }
      case "choice": {
        const harmonyChoice = tao && control.key === "harmony_effect";
        const enabled = harmonyChoice ? taoHarmony(player) : gate;
        items.push({
          ...base,
          kind: "choice",
          attention: harmonyChoice && taoLocked(player),
          value: String(current ?? ""),
          active: !!current,
          enabled,
          choices: (control.choices || []).map((choice) => {
            const v = String(choice.value ?? choice.key ?? "");
            return { value: v, label: choice.labels?.[language] || choice.label, selected: String(current ?? "") === v };
          }),
          hint: enabled
            ? ""
            : text(language, "when", {
                c: tao ? labelOf(definition, "harmony", language) : conditionText(control.enableWhen, definition, language),
              }),
        });
        break;
      }
      case "toggle":
        items.push({
          ...base,
          kind: "toggle",
          active: passiveActive(current),
          enabled: gate,
          hint: gate ? "" : text(language, "when", { c: conditionText(control.enableWhen, definition, language) }),
        });
        break;
      default:
        items.push({ ...base, kind: "text", value: String(current ?? ""), active: !!current, enabled: gate, hint: "" });
    }
  }
  return items;
}

/** 카운터 칸 i(0부터)를 눌렀을 때의 값: 채워진 마지막 칸이면 하나 줄이고, 아니면 그 칸까지 채운다. */
export function pipValue(current: number, index: number): number {
  return current === index + 1 ? index : index + 1;
}

/**
 * 트레이 항목을 눌렀을 때 보낼 액션. 선택된 값을 다시 고르면 해제한다.
 * 막힌 조작이면 null.
 */
export function trayAction(
  player: Player,
  definition: PassiveDefinition,
  target: "p1" | "p2",
  key: string,
  next: unknown,
  language = "ko",
): Action | null {
  const control = controls(definition).find((c) => c.key === key);
  if (!control) return null;
  const item = passiveTray(player, definition, language).find((i) => i.key === key);
  if (!item || !item.enabled) return null;
  const label = controlLabel(control, language);
  const set = (k: string, v: unknown, l = k): Action => ({
    action: "passive",
    target,
    key: k,
    value: v,
    label: l,
    passive_action: "set",
  });
  if (item.kind === "counter") {
    const number = Number(next);
    if (!Number.isFinite(number)) return null;
    next = Math.max(0, Math.min(control.max ?? 32767, Math.trunc(number)));
  }
  if (item.kind === "choice") {
    next = nextTaoEffect(item.value, String(next ?? ""));
    if (isTao(definition) && key === "harmony_effect") {
      const effect = set(key, next, label);
      return passiveActive(passiveGet(player, "harmony", false))
        ? effect
        : { action: "batch", actions: [set("harmony", true, labelOf(definition, "harmony", language)), effect] };
    }
  }
  if (item.kind === "trigger") {
    const actions = [set(key, next, label)];
    if (next)
      for (const reset of control.resetKeys || [])
        actions.push(set(reset, 0, labelOf(definition, reset, language)));
    return actions.length === 1 ? actions[0]! : { action: "batch", actions };
  }
  return passiveActions(player, definition, target, key, next, label);
}
