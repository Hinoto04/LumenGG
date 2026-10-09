/** Same HP ratio/hue scale as the web calculator, with a visible tinted bar. */
export function hpAppearance(hp: number, initialHp: number) {
  const ratio = initialHp > 0 ? Math.max(0, Math.min(1, hp / initialHp)) : 0.5;
  const hue = Math.round(4 + ratio * 136);
  return {
    ratio,
    hue,
    strong: `hsl(${hue}, 78%, 62%)`,
    border: `hsla(${hue}, 58%, 52%, 0.65)`,
    background: `hsl(${hue}, 48%, 14%)`,
    fill: `hsla(${hue}, 58%, 40%, 0.35)`,
  };
}
export function passiveActive(value: unknown): boolean {
  return (
    value === true ||
    value === 1 ||
    value === "true" ||
    value === "on" ||
    value === "ON"
  );
}
export function nextTaoEffect(current: unknown, chosen: string): string {
  return current === chosen ? "" : chosen;
}
