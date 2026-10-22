import React, { useCallback, useEffect, useRef, useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "./provider";
import type { CalculatorUi } from "./calculator-ui";
import {
  setCalculatorAppearance,
  useCalculatorAppearance,
} from "./calculator-appearance-settings";

/** Entry-only choice. Does not create or modify a calculator session. */
export function useCalculatorEntry() {
  useCalculatorAppearance();
  const { t } = useApp();
  const [visible, setVisible] = useState(false);
  const pending = useRef<{
    promise: Promise<CalculatorUi | null>;
    resolve: (ui: CalculatorUi | null) => void;
  } | null>(null);
  const chooseUi = useCallback(() => {
    if (pending.current) return pending.current.promise;
    let resolve!: (ui: CalculatorUi | null) => void;
    const promise = new Promise<CalculatorUi | null>((done) => {
      resolve = done;
    });
    pending.current = { promise, resolve };
    setVisible(true);
    return promise;
  }, []);
  const close = (ui: CalculatorUi | null) => {
    pending.current?.resolve(ui);
    pending.current = null;
    setVisible(false);
  };
  useEffect(
    () => () => {
      pending.current?.resolve(null);
    },
    [],
  );
  const entrySheet = (
    <Modal
      visible={visible}
      transparent
      animationType="fade"
      onRequestClose={() => close(null)}
      supportedOrientations={[
        "portrait",
        "landscape",
        "landscape-left",
        "landscape-right",
      ]}
    >
      <View style={s.backdrop}>
        <Pressable
          style={StyleSheet.absoluteFill}
          accessibilityRole="button"
          accessibilityLabel={t("취소")}
          onPress={() => close(null)}
        />
        <SafeAreaView edges={["bottom"]} style={s.sheet}>
          <Text accessibilityRole="header" style={s.title}>
            {t("계산기 UI 선택")}
          </Text>
          <Text style={s.help}>
            {t("같은 대전을 원하는 화면으로 열 수 있습니다.")}
          </Text>
          <View style={s.choices}>
            <Pressable
              accessibilityRole="button"
              onPress={() => close("classic")}
              style={[s.card, s.classic]}
            >
              <Text style={s.kicker}>CLASSIC</Text>
              <Text style={s.name}>{t("기존 계산기")}</Text>
              <Text style={s.help}>{t("익숙한 기본 화면")}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setCalculatorAppearance({ style: "illustrated" });
                close("character");
              }}
              style={[s.card, s.character]}
            >
              <Text style={[s.kicker, { color: "#b8c8ff" }]}>
                CHARACTER ARENA
              </Text>
              <Text style={s.name}>{t("캐릭터 UI 계산기")}</Text>
              <Text style={s.help}>{t("캐릭터 전용 테마와 패시브")}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => {
                setCalculatorAppearance({ style: "clean" });
                close("character");
              }}
              style={[
                s.card,
                { backgroundColor: "#162032", borderColor: "#8da3bb" },
              ]}
            >
              <Text style={[s.kicker, { color: "#c5d5e8" }]}>CLEAN</Text>
              <Text style={s.name}>{t("깔끔한 UI 계산기")}</Text>
              <Text style={s.help}>{t("단색 배경과 간결한 아이콘")}</Text>
            </Pressable>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => close(null)}
            style={s.cancel}
          >
            <Text style={s.help}>{t("취소")}</Text>
          </Pressable>
        </SafeAreaView>
      </View>
    </Modal>
  );
  return { chooseUi, entrySheet };
}
const s = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: "#03060dcc",
    justifyContent: "flex-end",
  },
  sheet: {
    backgroundColor: "#111a29",
    padding: 20,
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    borderWidth: 1,
    borderColor: "#35445e",
  },
  title: { color: "#f5f3ef", fontSize: 21, fontWeight: "800", marginBottom: 6 },
  help: { color: "#b3bfd2", fontSize: 12, lineHeight: 18 },
  choices: { flexDirection: "row", gap: 10, marginTop: 16 },
  card: {
    flex: 1,
    minHeight: 118,
    padding: 14,
    borderWidth: 1,
    borderRadius: 12,
    justifyContent: "center",
    gap: 6,
  },
  classic: { backgroundColor: "#24211b", borderColor: "#b28d47" },
  character: { backgroundColor: "#202943", borderColor: "#788dc7" },
  kicker: {
    color: "#d5b775",
    fontSize: 9,
    fontWeight: "800",
    letterSpacing: 1,
  },
  name: { color: "#f6f3ef", fontSize: 16, fontWeight: "800" },
  cancel: {
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
    marginTop: 6,
  },
});
