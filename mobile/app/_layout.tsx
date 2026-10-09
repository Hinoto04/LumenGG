import React, { useEffect } from "react";
import { Stack, router, usePathname } from "expo-router";
import { BackHandler, Pressable, Text } from "react-native";
import { StatusBar } from "expo-status-bar";
import { AppProvider, useApp } from "../src/provider";
import { colors } from "../src/ui";
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
          ["/cards", "/decks", "/collection", "/qna", "/calculator"].includes(
            pathname,
          )
        )
          router.dismissTo("/");
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
            <Text style={{ color: colors.accent, fontSize: 22 }}>⚙</Text>
          </Pressable>
        ),
      }}
    >
      <Stack.Screen name="index" options={{ title: "LumenDB" }} />
      <Stack.Screen name="cards" options={{ title: t("카드 검색") }} />
      <Stack.Screen name="decks" options={{ title: t("덱") }} />
      <Stack.Screen name="collection" options={{ title: t("컬렉션") }} />
      <Stack.Screen name="qna" options={{ title: "QNA" }} />
      <Stack.Screen
        name="calculator"
        options={{
          title: t("계산기"),
          orientation: "landscape",
          headerShown: false,
        }}
      />
      <Stack.Screen name="card/[id]" options={{ title: "LumenDB" }} />
      <Stack.Screen name="qna/[id]" options={{ title: "Q&A" }} />
      <Stack.Screen name="deck/[id]" options={{ title: t("덱") }} />
      <Stack.Screen
        name="settings"
        options={{ title: t("설정"), headerRight: () => null }}
      />
    </Stack>
  );
}
