import type { Player } from "./types";
import { calculatorTheme } from "./calculator-ui";

export const SHIELD_KEY = "finf_shield";
export const MAX_SHIELD_DELTA = 50000;
export function supportsShield(player: Pick<Player, "character">): boolean {
  return (
    calculatorTheme(player.character).theme_key === "finf" ||
    player.character?.name === "핀프"
  );
}
export function shieldAmount(player: Player): number {
  if (!supportsShield(player)) return 0;
  const entry = player.passive_state?.[SHIELD_KEY];
  const raw = Number(entry?.value ?? entry?.count ?? 0);
  return Number.isFinite(raw)
    ? Math.max(0, Math.trunc(raw))
    : 0;
}
export function setShield(player: Player, value: number): void {
  player.passive_state ||= {};
  player.passive_state[SHIELD_KEY] = {
    value: Math.max(0, value),
    label: "보호막",
  };
}
/** Used by both native local calculations and web optimistic state. */
export function applyHealthDelta(player: Player, amount: number) {
  const before = shieldAmount(player);
  const absorbed = amount < 0 ? Math.min(before, -amount) : 0;
  player.hp += amount + absorbed;
  if (absorbed) setShield(player, before - absorbed);
  return {
    shield_before: before,
    shield_after: before - absorbed,
    shield_absorbed: absorbed,
  };
}
