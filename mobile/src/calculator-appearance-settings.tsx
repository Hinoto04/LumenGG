import React, { useEffect, useSyncExternalStore } from "react";
import { StyleSheet, View } from "react-native";
import {
  calculatorAppearance,
  defaultAppearance,
  appearanceKey,
  type CalculatorAppearance,
} from "./calculator-appearance";
import { preference, setPreference } from "./storage";
import { useApp } from "./provider";
import { Button, IconButton, Segmented, colors, radius } from "./ui";
import { SettingColumn, SettingRow, SettingSection } from "./setting-rows";

let current = defaultAppearance,
  loaded = false,
  revision = 0;
let writes = Promise.resolve();
const listeners = new Set<() => void>();
const subscribe = (callback: () => void) => {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
};
export function setCalculatorAppearance(patch: Partial<CalculatorAppearance>) {
  current = calculatorAppearance({ ...current, ...patch });
  revision++;
  listeners.forEach((callback) => callback());
  const saved = current;
  writes = writes
    .catch(() => undefined)
    .then(async () => {
      await setPreference(appearanceKey, saved);
    });
  void writes.catch(() => undefined);
}
export function useCalculatorAppearance() {
  const value = useSyncExternalStore(subscribe, () => current);
  useEffect(() => {
    if (loaded) return;
    loaded = true;
    const before = revision;
    void preference(appearanceKey, defaultAppearance)
      .then((saved) => {
        if (revision !== before) return;
        current = calculatorAppearance(saved);
        listeners.forEach((callback) => callback());
      })
      .catch(() => undefined);
  }, []);
  return value;
}
export function CalculatorAppearanceSettings() {
  const { t } = useApp();
  const value = useCalculatorAppearance();
  const step = (delta: number) =>
    setCalculatorAppearance({ brightness: value.brightness + delta });
  return (
    <SettingColumn>
      <SettingSection
        title="화면"
        footer="화면 설정은 이 기기에만 저장됩니다."
        first
      >
        <SettingRow
          title="화면 스타일"
          description={
            value.style === "illustrated"
              ? "캐릭터 일러스트를 배경에 깔고 패시브를 그림으로 보여 줍니다."
              : "배경 그림 없이 단색 화면으로 숫자만 또렷하게 보여 줍니다."
          }
        >
          <View style={{ width: 260 }}>
            <Segmented
              value={value.style}
              onChange={(style) =>
                setCalculatorAppearance({
                  style: style === "clean" ? "clean" : "illustrated",
                })
              }
              values={[
                {
                  key: "illustrated",
                  label: "일러스트",
                  icon: "image-outline",
                },
                { key: "clean", label: "깔끔하게", icon: "contrast-outline" },
              ]}
            />
          </View>
        </SettingRow>
        {value.style === "illustrated" && (
          <SettingRow
            title={t("배경 밝기") + " · " + value.brightness + "%"}
            description="배경 그림이 숫자를 가리면 낮추세요. 권장 35%"
          >
            <View style={appearanceStyles.brightness}>
              <IconButton
                icon="remove"
                label={t("배경 밝기") + " −10"}
                filled
                disabled={value.brightness === 0}
                onPress={() => step(-10)}
              />
              <View style={appearanceStyles.meter}>
                <View
                  style={[
                    appearanceStyles.fill,
                    { width: `${value.brightness}%` },
                  ]}
                />
              </View>
              <IconButton
                icon="add"
                label={t("배경 밝기") + " +10"}
                filled
                disabled={value.brightness === 100}
                onPress={() => step(10)}
              />
              <Button
                label="권장 밝기"
                variant="ghost"
                size="sm"
                disabled={value.brightness === defaultAppearance.brightness}
                onPress={() =>
                  setCalculatorAppearance({
                    brightness: defaultAppearance.brightness,
                  })
                }
              />
            </View>
          </SettingRow>
        )}
      </SettingSection>
    </SettingColumn>
  );
}

const appearanceStyles = StyleSheet.create({
  brightness: { flexDirection: "row", alignItems: "center", gap: 6 },
  meter: {
    width: 90,
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surface2,
    overflow: "hidden",
  },
  fill: { height: "100%", backgroundColor: colors.accent },
});
