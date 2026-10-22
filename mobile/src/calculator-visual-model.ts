import specs from "./calculator-passives.json";
import art from "./calculator-passive-art.json";
import presentations from "./calculator-passive-visuals.json";
import symbolArt from "./calculator-symbol-art.json";
import cleanArt from "./calculator-clean-icons.json";
import { conditionMet, passiveActions, passiveGet } from "./core";
import { passiveActive, nextTaoEffect } from "./calculator-display";
import type {
  Action,
  PassiveControl,
  PassiveDefinition,
  Player,
} from "./types";

export type VisualControl = PassiveControl & {
  labels?: Record<string, string>;
};
export const passiveArt = art;
export const passiveSymbolArt = symbolArt;
export const passiveCleanArt = cleanArt;
export type AmbientEffect =
  "fire" | "light" | "arc" | "mist" | "orbit" | "wave" | "spark";
export type VisualPresentation = {
  symbol?: string;
  effect?: AmbientEffect;
  color?: string;
};
export function visualLayout(theme: string): string {
  return (presentations as Record<string, any>)[theme]?.layout || "focus";
}
export function visualPresentation(
  theme: string,
  key: string,
): VisualPresentation {
  return (presentations as Record<string, any>)[theme]?.controls[key] || {};
}
// Shared normalized positions keep touch regions and artwork identical on both platforms.
export function visualTokenPositions(
  theme: string,
): { x: number; y: number; rotation: number }[] | null {
  const sets: Record<string, number[][]> = {
    wolf: [
      [40, 76, -32],
      [64, 24, -15],
      [160, 24, 15],
      [184, 76, 32],
      [112, 148, 0],
    ],
    rev: [
      [24, 112, -50],
      [68, 68, -30],
      [96, 24, -10],
      [144, 24, 10],
      [172, 68, 30],
      [216, 112, 50],
    ],
    yohan: Array.from({ length: 10 }, (_, i) => [
      24 + 48 * (i % 5),
      i < 5 ? 24 : 152,
      0,
    ]),
  };
  return (
    sets[theme]?.map(([x, y, rotation]) => ({
      x: x! / (theme === "wolf" ? 224 : 240),
      y: y! / 176,
      rotation: rotation!,
    })) || null
  );
}
export function visualDefinition(
  theme: string,
): PassiveDefinition & { controls: VisualControl[] } {
  return (specs as Record<string, any>)[theme] || { controls: [] };
}
export function visualLabel(control: VisualControl, language: string) {
  return control.labels?.[language] || control.label;
}
export function visualValue(player: Player, control: VisualControl) {
  const initial = player.character?.initial_passive_state?.[control.key];
  return passiveGet(player, control.key, initial?.value ?? initial?.count ?? 0);
}

export function harmonyState(player: Player) {
  const yang = Number(passiveGet(player, "yang_counter"));
  const yin = Number(passiveGet(player, "yin_counter"));
  return (
    (yang === 4 && yin === 4) ||
    (passiveActive(passiveGet(player, "harmony", false)) &&
      yang >= 3 &&
      yin >= 3)
  );
}
export function taoInputLocked(player: Player) {
  return (
    harmonyState(player) &&
    !["damage_100", "fp_1"].includes(
      String(passiveGet(player, "harmony_effect", "")),
    )
  );
}
export function visualActive(player: Player, control: VisualControl) {
  return control.type === "status"
    ? conditionMet(control.condition, player)
    : passiveActive(visualValue(player, control));
}
export function visualEnabled(player: Player, control: VisualControl) {
  return (
    (!control.enableWhen || conditionMet(control.enableWhen, player)) &&
    (control.type !== "thresholdAction" ||
      visualActive(player, control) ||
      conditionMet(
        control.requires || control.activateWhen || control.condition,
        player,
      ))
  );
}
export function steppedCounter(
  player: Player,
  control: VisualControl,
  filled: boolean,
) {
  const current = Math.max(0, Number(visualValue(player, control)) || 0);
  return Math.max(
    0,
    Math.min(control.max ?? 32767, current + (filled ? -1 : 1)),
  );
}
export function visualAction(
  theme: string,
  player: Player,
  target: "p1" | "p2",
  key: string,
  value: unknown,
  language = "ko",
): Action | null {
  const definition = visualDefinition(theme);
  const control = definition.controls.find((c) => c.key === key);
  if (
    !control ||
    control.type === "status" ||
    (!visualEnabled(player, control) &&
      !(theme === "tao" && key === "harmony_effect" && harmonyState(player)))
  )
    return null;
  if (
    theme === "tao" &&
    ["yang_counter", "yin_counter"].includes(key) &&
    taoInputLocked(player)
  )
    return null;
  if (control.type === "counter") {
    if (!Number.isFinite(Number(value))) return null;
    value = Math.max(
      0,
      Math.min(control.max ?? 32767, Math.trunc(Number(value))),
    );
  }
  if (theme === "tao" && key === "harmony_effect") {
    if (
      !harmonyState(player) ||
      !["damage_100", "fp_1"].includes(String(value))
    )
      return null;
    const chosen = nextTaoEffect(visualValue(player, control), String(value));
    const effect: Action = {
      action: "passive",
      target,
      key,
      value: chosen,
      label: visualLabel(control, language),
      passive_action: "set",
    };
    return passiveActive(passiveGet(player, "harmony", false))
      ? effect
      : {
          action: "batch",
          actions: [
            {
              action: "passive",
              target,
              key: "harmony",
              value: true,
              label: "조화",
              passive_action: "set",
            },
            effect,
          ],
        };
  }
  if (control.type === "thresholdAction") {
    const actions: Action[] = [
      {
        action: "passive",
        target,
        key,
        value,
        label: visualLabel(control, language),
        passive_action: "set",
      },
    ];
    if (value)
      for (const reset of control.resetKeys || [])
        actions.push({
          action: "passive",
          target,
          key: reset,
          value: 0,
          label: reset,
          passive_action: "set",
        });
    return { action: "batch", actions };
  }
  return passiveActions(
    player,
    definition,
    target,
    key,
    value,
    visualLabel(control, language),
  );
}
export { passiveActive };
