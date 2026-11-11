import React from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { router, type Href } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { useApp } from "../src/provider";
import { Icon, colors, radius, tapFeedback, type IconName } from "../src/ui";

import { useCalculatorEntry } from "../src/calculator-entry";

const gap = 12;
// 루멘 파티는 미공개 기능이라 메인화면이 아닌 유틸리티 아래에 둔다.
const menus: { label: string; icon: IconName; href: string }[] = [
  { label: "계산기", icon: "calculator-outline", href: "/calculator" },
  { label: "시뮬", icon: "flash-outline", href: "/battle" },
  { label: "카드", icon: "albums-outline", href: "/cards" },
  { label: "덱", icon: "layers-outline", href: "/decks" },
  { label: "컬렉션", icon: "grid-outline", href: "/collection" },
  { label: "QNA", icon: "help-circle-outline", href: "/qna" },
  { label: "대회", icon: "trophy-outline", href: "/tournaments" },
  { label: "유틸리티", icon: "apps-outline", href: "/utilities" },
];

export default function Home() {
  const { t } = useApp();
  const { chooseUi, entrySheet } = useCalculatorEntry();
  return (
    <SafeAreaView edges={["bottom"]} style={homeStyles.screen}>
      {entrySheet}
      <View style={homeStyles.grid}>
        {[0, 2, 4, 6].map((start) => (
          <View key={start} style={homeStyles.row}>
            {menus.slice(start, start + 2).map((menu) => (
              <Pressable
                key={menu.href}
                accessibilityRole="button"
                accessibilityLabel={t(menu.label)}
                onPress={async () => {
                  tapFeedback();
                  if (menu.href === "/calculator") {
                    const ui = await chooseUi();
                    if (ui)
                      router.push({ pathname: "/calculator", params: { ui } });
                  } else {
                    router.push(menu.href as Href);
                  }
                }}
                style={({ pressed }) => [
                  homeStyles.tile,
                  homeStyles.smallTile,
                  menu.href === "/calculator" && homeStyles.calculator,
                  pressed && homeStyles.pressed,
                ]}
              >
                <View
                  style={[
                    homeStyles.iconWrap,
                    menu.href === "/calculator" && homeStyles.calculatorIcon,
                  ]}
                >
                  <Icon
                    name={menu.icon}
                    size={30}
                    color={
                      menu.href === "/calculator"
                        ? colors.onAccent
                        : colors.accent
                    }
                  />
                </View>
                <Text style={homeStyles.title}>{t(menu.label)}</Text>
              </Pressable>
            ))}
            {start + 1 >= menus.length && <View style={homeStyles.smallTile} />}
          </View>
        ))}
      </View>
    </SafeAreaView>
  );
}

const homeStyles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg, padding: 16 },
  grid: { flex: 1, gap },
  row: { flex: 1, flexDirection: "row", gap },
  tile: {
    borderRadius: radius.lg + 2,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: colors.line,
    backgroundColor: colors.panel,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    padding: 12,
  },
  calculator: { backgroundColor: "#2a2215", borderColor: colors.accent },
  smallTile: { flex: 1 },
  iconWrap: {
    width: 60,
    height: 60,
    borderRadius: radius.pill,
    backgroundColor: colors.accentSoft,
    alignItems: "center",
    justifyContent: "center",
  },
  calculatorIcon: { backgroundColor: colors.accent },
  pressed: { opacity: 0.85, transform: [{ scale: 0.97 }] },
  title: {
    fontSize: 19,
    fontWeight: "700",
    letterSpacing: -0.2,
    color: colors.text,
    textAlign: "center",
  },
});
