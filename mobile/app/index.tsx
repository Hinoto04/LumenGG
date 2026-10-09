import React, { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router, type Href } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "../src/provider";
import { colors } from "../src/ui";

const gap = 12;
const menus = [
  { label: "카드", icon: "▣", href: "/cards" },
  { label: "덱", icon: "▤", href: "/decks" },
  { label: "컬렉션", icon: "▦", href: "/collection" },
  { label: "QNA", icon: "?", href: "/qna" },
] as const;

export default function Home() {
  const { t } = useApp();
  const [height, setHeight] = useState(0);
  const cellHeight = Math.max(0, (height - gap * 3) / 4);
  return (
    <SafeAreaView edges={["bottom"]} style={homeStyles.screen}>
      <View
        style={homeStyles.grid}
        onLayout={(event) => setHeight(event.nativeEvent.layout.height)}
      >
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("계산기")}
          onPress={() => router.push("/calculator")}
          style={({ pressed }) => [
            homeStyles.tile,
            homeStyles.hero,
            { height: cellHeight * 2 + gap, opacity: pressed ? 0.75 : 1 },
          ]}
        >
          <Text style={[homeStyles.icon, { fontSize: 88 }]}>±</Text>
          <Text style={homeStyles.heroTitle}>{t("계산기")}</Text>
        </Pressable>
        {[0, 2].map((start) => (
          <View key={start} style={[homeStyles.row, { height: cellHeight }]}>
            {menus.slice(start, start + 2).map((menu) => (
              <Pressable
                key={menu.href}
                accessibilityRole="button"
                accessibilityLabel={t(menu.label)}
                onPress={() => router.push(menu.href as Href)}
                style={({ pressed }) => [
                  homeStyles.tile,
                  homeStyles.smallTile,
                  { opacity: pressed ? 0.75 : 1 },
                ]}
              >
                <Text style={homeStyles.icon}>{menu.icon}</Text>
                <Text style={homeStyles.title}>{t(menu.label)}</Text>
              </Pressable>
            ))}
          </View>
        ))}
      </View>
    </SafeAreaView>
  );
}

const homeStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  grid: { flex: 1, gap },
  row: { flexDirection: "row", gap },
  tile: {
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: 12,
  },
  hero: { backgroundColor: "#2a2215", borderColor: colors.accent },
  smallTile: { flex: 1 },
  icon: { fontSize: 38, color: colors.accent },
  heroTitle: { fontSize: 36, fontWeight: "800", color: colors.text },
  title: { fontSize: 22, fontWeight: "700", color: colors.text },
});
