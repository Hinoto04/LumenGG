import React from "react";
import {
  Keyboard,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "./provider";
import { colors } from "./ui";

export function FilterSheet({
  visible,
  title,
  count,
  unit = "장",
  error,
  onClose,
  onReset,
  onApply,
  children,
}: {
  visible: boolean;
  title: string;
  count: number;
  unit?: string;
  error?: string | null;
  onClose: () => void;
  onReset: () => void;
  onApply: () => void;
  children: React.ReactNode;
}) {
  const { t } = useApp();
  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="fullScreen"
      supportedOrientations={["portrait"]}
      onRequestClose={onClose}
    >
      <SafeAreaView style={filterStyles.screen}>
        <KeyboardAvoidingView
          style={{ flex: 1 }}
          behavior={Platform.OS === "ios" ? "padding" : "height"}
        >
          <View style={filterStyles.header}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("취소")}
              onPress={onClose}
              style={filterStyles.close}
            >
              <Text style={filterStyles.back}>‹</Text>
            </Pressable>
            <Text style={filterStyles.title}>{t(title)}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("필터 초기화")}
              onPress={onReset}
              style={filterStyles.reset}
            >
              <Text style={{ color: colors.accent }}>{t("초기화")}</Text>
            </Pressable>
          </View>
          <ScrollView
            style={{ flex: 1 }}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            contentContainerStyle={{ paddingVertical: 12 }}
          >
            {children}
          </ScrollView>
          <View style={filterStyles.footer}>
            {!!error && (
              <Text accessibilityRole="alert" style={filterStyles.error}>
                {t(error)}
              </Text>
            )}
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("필터 적용")}
              accessibilityState={{ disabled: !!error }}
              disabled={!!error}
              onPress={() => {
                Keyboard.dismiss();
                onApply();
              }}
              style={[filterStyles.apply, !!error && { opacity: 0.4 }]}
            >
              <Text style={filterStyles.applyText}>
                {t("적용")} · {count} {t(unit)}
              </Text>
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}
export function FilterChoices({
  title,
  value,
  values,
  onChange,
}: {
  title: string;
  value: string;
  values: { key: string; label: string }[];
  onChange: (value: string) => void;
}) {
  const { t } = useApp();
  return (
    <View style={filterStyles.section}>
      <Text style={filterStyles.heading}>{t(title)}</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={filterStyles.choices}
      >
        {values.map((option) => (
          <Pressable
            key={option.key}
            accessibilityRole="radio"
            accessibilityLabel={`${t(title)}: ${option.label}`}
            accessibilityState={{ checked: value === option.key }}
            onPress={() => onChange(option.key)}
            style={[
              filterStyles.chip,
              value === option.key && filterStyles.selected,
            ]}
          >
            <Text
              style={[
                filterStyles.chipText,
                value === option.key && { color: colors.accent },
              ]}
            >
              {option.label}
            </Text>
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}
export const filterStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  header: {
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderColor: colors.line,
    paddingHorizontal: 12,
    minHeight: 56,
  },
  close: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  back: { color: colors.text, fontSize: 38, lineHeight: 40 },
  title: { flex: 1, color: colors.text, fontSize: 21, fontWeight: "700" },
  reset: { minHeight: 44, justifyContent: "center", paddingHorizontal: 12 },
  section: { marginBottom: 16 },
  heading: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "700",
    marginHorizontal: 16,
    marginBottom: 9,
  },
  choices: {
    flexDirection: "row",
    gap: 8,
    paddingHorizontal: 16,
    paddingBottom: 4,
  },
  chip: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 16,
    backgroundColor: colors.panel,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: 10,
  },
  chipText: { color: colors.text, fontSize: 15 },
  selected: { borderColor: colors.accent, backgroundColor: "#392e1c" },
  range: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 16,
  },
  input: { flex: 1, marginBottom: 0 },
  footer: {
    padding: 16,
    borderTopWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  apply: {
    minHeight: 52,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: colors.accent,
  },
  applyText: { color: colors.bg, fontSize: 17, fontWeight: "800" },
  error: { color: colors.danger, marginBottom: 10 },
});
