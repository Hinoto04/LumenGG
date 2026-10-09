import React, { useEffect, useState } from "react";
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
import { localized, normalizeSearch } from "./core";
import {
  emptyCardFilters,
  filterError,
  matchesCardFilters,
  type CardFilters,
} from "./card-filters";
import { colors, Input } from "./ui";

export function CardFilterScreen({
  visible,
  value,
  query,
  onApply,
  onClose,
}: {
  visible: boolean;
  value: CardFilters;
  query: string;
  onApply: (value: CardFilters) => void;
  onClose: () => void;
}) {
  const { catalog, language, t } = useApp();
  const [draft, setDraft] = useState<CardFilters>({ ...value });
  useEffect(() => {
    if (visible) setDraft({ ...value });
  }, [visible, value]);
  const error = filterError(draft);
  const needle = normalizeSearch(query);
  const count = (catalog?.cards || []).filter(
    (card) =>
      (!needle || card.search?.includes(needle)) &&
      matchesCardFilters(card, draft),
  ).length;
  function set(key: keyof CardFilters, value: string) {
    setDraft((current) => ({ ...current, [key]: value }));
  }
  function choices(
    title: string,
    key: "character" | "type" | "pos",
    values: { key: string; label: string }[],
  ) {
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
              accessibilityState={{ checked: draft[key] === option.key }}
              onPress={() => set(key, option.key)}
              style={[
                filterStyles.chip,
                draft[key] === option.key && filterStyles.selected,
              ]}
            >
              <Text
                style={[
                  filterStyles.chipText,
                  draft[key] === option.key && { color: colors.accent },
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
  function range(
    title: string,
    min: "frameMin" | "damageMin",
    max: "frameMax" | "damageMax",
  ) {
    return (
      <View style={filterStyles.section}>
        <Text style={filterStyles.heading}>{t(title)}</Text>
        <View style={filterStyles.range}>
          <Input
            accessibilityLabel={`${t(title)} ${t("최소값")}`}
            placeholder={t("최소값")}
            value={draft[min]}
            onChangeText={(v) => set(min, v.trim())}
            keyboardType="numeric"
            style={filterStyles.input}
          />
          <Text style={{ color: colors.muted }}>—</Text>
          <Input
            accessibilityLabel={`${t(title)} ${t("최대값")}`}
            placeholder={t("최대값")}
            value={draft[max]}
            onChangeText={(v) => set(max, v.trim())}
            keyboardType="numeric"
            style={filterStyles.input}
          />
        </View>
      </View>
    );
  }
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
            <Text style={filterStyles.title}>{t("카드 필터")}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("필터 초기화")}
              onPress={() => setDraft({ ...emptyCardFilters })}
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
            {choices("캐릭터", "character", [
              { key: "", label: t("전체") },
              ...(catalog?.characters || []).map((c) => ({
                key: String(c.id),
                label: localized(c, language),
              })),
            ])}
            {choices("카드 종류", "type", [
              { key: "", label: t("전체") },
              ...[...new Set(catalog?.cards.map((c) => c.type) || [])]
                .filter(Boolean)
                .map((type) => ({ key: type, label: t(type) })),
            ])}
            {choices("공격 판정", "pos", [
              { key: "", label: t("전체") },
              ...["상단", "중단", "하단"].map((pos) => ({
                key: pos,
                label: t(pos),
              })),
            ])}
            {range("속도", "frameMin", "frameMax")}
            {range("대미지", "damageMin", "damageMax")}
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
                onApply({ ...draft });
              }}
              style={[filterStyles.apply, !!error && { opacity: 0.4 }]}
            >
              <Text style={filterStyles.applyText}>
                {t("적용")} · {count} {t("장")}
              </Text>
            </Pressable>
          </View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </Modal>
  );
}
const filterStyles = StyleSheet.create({
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
