import React, { useEffect } from "react";
import { Stack, router, usePathname } from "expo-router";
import { BackHandler, Pressable, Text } from "react-native";
import { StatusBar } from "expo-status-bar";
import { AppProvider, useApp } from "../src/provider";
import { Icon, colors } from "../src/ui";
export default function RootLayout() {
  return (
    <AppProvider>
      <StatusBar style="light" />
      <Navigation />
    </AppProvider>
  );
}

function Navigation() {
  const { t } = useApp();
  const pathname = usePathname();
  useEffect(() => {
    if (pathname === "/") return;
    const subscription = BackHandler.addEventListener(
      "hardwareBackPress",
      () => {
        if (
          [
            "/cards",
            "/decks",
            "/collection",
            "/qna",
            "/calculator",
            "/tournaments",
            "/utilities",
          ].includes(pathname)
        )
          router.dismissTo("/");
        else if (pathname === "/party") router.dismissTo("/utilities");
        else if (router.canGoBack()) router.back();
        else router.replace("/");
        return true;
      },
    );
    return () => subscription.remove();
  }, [pathname]);
  return (
    <Stack
      initialRouteName="index"
      screenOptions={{
        orientation: "portrait",
        headerStyle: { backgroundColor: colors.panel },
        headerTintColor: colors.text,
        contentStyle: { backgroundColor: colors.bg },
        headerRight: () => (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("설정")}
            onPress={() => router.push("/settings")}
            style={{ padding: 12 }}
          >
            <Icon name="settings-outline" size={22} color={colors.accent} />
          </Pressable>
        ),
      }}
    >
      <Stack.Screen name="index" options={{ title: "LumenDB" }} />
      <Stack.Screen name="cards" options={{ title: t("카드 검색") }} />
      <Stack.Screen name="decks" options={{ title: t("덱") }} />
      <Stack.Screen name="collection" options={{ title: t("컬렉션") }} />
      <Stack.Screen name="qna" options={{ title: "QNA" }} />
      <Stack.Screen name="utilities" options={{ title: t("유틸리티") }} />
      <Stack.Screen name="party" options={{ title: t("루멘 파티") }} />
      <Stack.Screen name="tournaments" options={{ title: t("내 대회") }} />
      <Stack.Screen name="tournament/[id]" options={{ title: t("내 경기") }} />
      <Stack.Screen
        name="calculator"
        options={{
          title: t("계산기"),
          // 기기 방향을 따른다. 세로에서는 보드가 위아래로 쌓인다.
          orientation: "default",
          headerShown: false,
        }}
      />
      <Stack.Screen name="battle" options={{ title: t("시뮬") }} />
      <Stack.Screen
        name="play"
        options={{
          title: t("대전"),
          orientation: "default",
          headerShown: false,
        }}
      />
      <Stack.Screen name="card/[id]" options={{ title: "LumenDB" }} />
      <Stack.Screen name="qna/[id]" options={{ title: "Q&A" }} />
      <Stack.Screen name="regulations" options={{ title: "대회 규정" }} />
      <Stack.Screen name="deck-editor" options={{ title: "덱 작성" }} />
      <Stack.Screen name="deck/[id]" options={{ title: t("덱") }} />
      <Stack.Screen
        name="settings"
        options={{ title: t("설정"), headerRight: () => null }}
      />
    </Stack>
  );
}
