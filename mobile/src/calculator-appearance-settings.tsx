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
import { SettingRow } from "./setting-rows";

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
/** 계산기 설정 안의 화면 옵션 두 줄(화면 스타일·배경 밝기). 이 기기에만 저장된다. */
export function CalculatorAppearanceRows() {
  const { t } = useApp();
  const value = useCalculatorAppearance();
  const step = (delta: number) =>
    setCalculatorAppearance({ brightness: value.brightness + delta });
  return (
    <>
      <SettingRow title="화면 스타일">
        <View style={{ width: 260 }}>
          <Segmented
            value={value.style}
            onChange={(style) =>
              setCalculatorAppearance({
                style: style === "clean" ? "clean" : "illustrated",
              })
            }
            values={[
              { key: "illustrated", label: "일러스트", icon: "image-outline" },
              { key: "clean", label: "깔끔하게", icon: "contrast-outline" },
            ]}
          />
        </View>
      </SettingRow>
      {value.style === "illustrated" && (
        <SettingRow title={t("배경 밝기") + " · " + value.brightness + "%"}>
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
    </>
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
