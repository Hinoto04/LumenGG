import React from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { router, type Href } from "expo-router";
import { useApp } from "../src/provider";
import { Notice, colors } from "../src/ui";

// 메인화면에 두기 애매한 부가 기능 모음.
// 루멘 파티는 아직 미공개라 화면은 유지하되 목록에서 숨긴다. 공개할 때 true로 바꾼다.
const PARTY_PUBLIC = false;

const tools = [
  {
    label: "루멘 파티",
    description: "2–4인 보드게임 모드",
    icon: "⚄",
    href: "/party",
    visible: PARTY_PUBLIC,
  },
].filter((tool) => tool.visible);

export default function Utilities() {
  const { t } = useApp();
  return (
    <ScrollView
      style={utilityStyles.screen}
      contentContainerStyle={utilityStyles.content}
    >
      {tools.length === 0 && <Notice text="준비 중인 기능이 곧 추가됩니다." />}
      {tools.map((tool) => (
        <Pressable
          key={tool.href}
          accessibilityRole="button"
          accessibilityLabel={t(tool.label)}
          onPress={() => router.push(tool.href as Href)}
          style={({ pressed }) => [
            utilityStyles.row,
            { opacity: pressed ? 0.75 : 1 },
          ]}
        >
          <Text style={utilityStyles.icon}>{tool.icon}</Text>
          <View style={utilityStyles.body}>
            <Text style={utilityStyles.title}>{t(tool.label)}</Text>
            <Text style={utilityStyles.description}>
              {t(tool.description)}
            </Text>
          </View>
          <Text style={utilityStyles.chevron}>›</Text>
        </Pressable>
      ))}
    </ScrollView>
  );
}

const utilityStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  content: { padding: 16, gap: 12 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    padding: 16,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
  },
  icon: { fontSize: 30, color: colors.accent, width: 36, textAlign: "center" },
  body: { flex: 1, gap: 4 },
  title: { fontSize: 18, fontWeight: "700", color: colors.text },
  description: { fontSize: 13, color: colors.muted },
  chevron: { fontSize: 24, color: colors.muted },
});
