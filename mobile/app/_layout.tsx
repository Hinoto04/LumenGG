import React, { useEffect } from "react";
import { Stack, router, usePathname } from "expo-router";
import { BackHandler, Pressable, Text } from "react-native";
import { StatusBar } from "expo-status-bar";
import { useSafeAreaInsets } from "react-native-safe-area-context";
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
  // 안드로이드 3버튼 내비게이션·제스처 바, 가로 화면의 측면 버튼 영역에 내용이 가려지지 않도록
  // 모든 화면의 내용 영역을 그만큼 비운다. 자체로 안전 영역을 다루는 화면은 아래에서 따로 지정한다.
  const insets = useSafeAreaInsets();
  const safeContent = {
    backgroundColor: colors.bg,
    paddingBottom: insets.bottom,
    paddingLeft: insets.left,
    paddingRight: insets.right,
  };
  const fullContent = { backgroundColor: colors.bg };
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
        // 기기를 돌리면 화면도 돌아간다. 각 화면은 useWindowDimensions로 배치를 다시 계산한다.
        orientation: "default",
        headerStyle: { backgroundColor: colors.panel },
        headerTintColor: colors.text,
        contentStyle: safeContent,
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
      <Stack.Screen
        name="index"
        options={{ title: "LumenDB", contentStyle: fullContent }}
      />
      <Stack.Screen name="cards" options={{ title: t("카드 검색") }} />
      <Stack.Screen name="decks" options={{ title: t("덱") }} />
      <Stack.Screen name="collection" options={{ title: t("컬렉션") }} />
      <Stack.Screen name="qna" options={{ title: "QNA" }} />
      <Stack.Screen name="utilities" options={{ title: t("유틸리티") }} />
      <Stack.Screen
        name="party"
        options={{
          title: t("루멘 파티"),
          orientation: "portrait",
          contentStyle: fullContent,
        }}
      />
      <Stack.Screen name="tournaments" options={{ title: t("내 대회") }} />
      <Stack.Screen name="tournament/[id]" options={{ title: t("내 경기") }} />
      <Stack.Screen
        name="calculator"
        options={{
          title: t("계산기"),
          // 세로 배치는 자리가 모자라 항상 가로로 연다(웹 계산기도 세로 휴대폰에서 가로로 돌려 보여 준다).
          orientation: "landscape",
          headerShown: false,
          contentStyle: fullContent,
        }}
      />
      <Stack.Screen name="battle" options={{ title: t("시뮬") }} />
      <Stack.Screen
        name="play"
        options={{
          title: t("대전"),
          orientation: "default",
          headerShown: false,
          contentStyle: fullContent,
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
