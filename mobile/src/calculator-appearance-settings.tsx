import React, { useEffect, useSyncExternalStore } from "react";
import { Pressable, Text, View } from "react-native";
import {
  calculatorAppearance,
  defaultAppearance,
  appearanceKey,
  type CalculatorAppearance,
} from "./calculator-appearance";
import { preference, setPreference } from "./storage";
import { useApp } from "./provider";
import { Choices, styles } from "./ui";

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
  return (
    <View style={{ gap: 8, marginBottom: 16 }}>
      <Text style={styles.title}>{t("화면 스타일")}</Text>
      <Choices
        value={value.style}
        onChange={(style) =>
          setCalculatorAppearance({
            style: style === "clean" ? "clean" : "illustrated",
          })
        }
        values={[
          { key: "illustrated", label: t("일러스트") },
          { key: "clean", label: t("깔끔하게") },
        ]}
      />
      {value.style === "illustrated" && (
        <>
          <Text style={styles.text}>
            {t("배경 밝기")} · {value.brightness}%
          </Text>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 8 }}>
            {[-10, 10].map((step) => (
              <Pressable
                key={step}
                accessibilityRole="button"
                accessibilityLabel={
                  t("배경 밝기") + (step < 0 ? " −10" : " +10")
                }
                disabled={
                  step < 0 ? value.brightness === 0 : value.brightness === 100
                }
                onPress={() =>
                  setCalculatorAppearance({
                    brightness: value.brightness + step,
                  })
                }
                style={{
                  minWidth: 64,
                  minHeight: 44,
                  borderRadius: 8,
                  backgroundColor: "#23324a",
                  justifyContent: "center",
                  alignItems: "center",
                }}
              >
                <Text style={styles.text}>{step < 0 ? "−" : "+"}</Text>
              </Pressable>
            ))}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("권장 밝기")}
              onPress={() =>
                setCalculatorAppearance({
                  brightness: defaultAppearance.brightness,
                })
              }
              style={{
                minHeight: 44,
                paddingHorizontal: 14,
                justifyContent: "center",
              }}
            >
              <Text style={styles.text}>{t("권장 밝기")} · 35%</Text>
            </Pressable>
          </View>
        </>
      )}
      <Text style={styles.muted}>
        {t("화면 설정은 이 기기에만 저장됩니다.")}
      </Text>
    </View>
  );
}
