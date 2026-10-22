export function supplyCombo(speedsText: string, damageText: string) {
  const tokens = speedsText
    .trim()
    .split(/[\s,，→>]+/)
    .filter(Boolean);
  const speeds = tokens.map(Number),
    damage = Number(damageText);
  if (
    !tokens.length ||
    tokens.some((token) => !/^-?\d+$/.test(token)) ||
    speeds.some(
      (speed, index) =>
        !Number.isSafeInteger(speed) ||
        (index > 0 && speed <= speeds[index - 1]!),
    )
  )
    throw new Error(
      "사용한 카드의 속도를 작은 수부터, 같은 수 없이 입력해주세요.",
    );
  if (!Number.isSafeInteger(damage) || damage <= 0)
    throw new Error("콤보 보정과 효과를 적용한 최종 피해를 입력해주세요.");
  return { speeds, damage };
}
