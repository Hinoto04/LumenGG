import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, BackHandler, Linking, Pressable, Text, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { WebView } from "react-native-webview";
import { SITE_ORIGIN } from "../src/battle";
import { classifyNavigation } from "../src/battle-nav";
import { colors, styles } from "../src/ui";

/**
 * 대전 화면: 사이트의 게임 클라이언트(/battlelog/play/)를 WebView로 연다.
 * 좌석 토큰이 주소에 들어 있으므로 WebView에 로그인 정보를 넘기지 않는다.
 */
export default function Play() {
  const { url } = useLocalSearchParams<{ url?: string }>();
  const web = useRef<WebView>(null);
  const canGoBack = useRef(false);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const target = typeof url === "string" && classifyNavigation(url, SITE_ORIGIN) === "allow" ? url : null;

  // 안드로이드 뒤로 가기: WebView 안에서 먼저 돌아가고, 더 갈 곳이 없으면 화면을 닫는다.
  useEffect(() => {
    const subscription = BackHandler.addEventListener("hardwareBackPress", () => {
      if (canGoBack.current) {
        web.current?.goBack();
        return true;
      }
      return false;
    });
    return () => subscription.remove();
  }, []);

  if (!target) {
    return (
      <SafeAreaView style={styles.screen}>
        <Text style={styles.text}>대전 주소가 올바르지 않습니다.</Text>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView edges={["top", "bottom"]} style={{ flex: 1, backgroundColor: "#070b14" }}>
      {failed ? (
        <View style={[styles.screen, { justifyContent: "center", alignItems: "center", gap: 12 }]}>
          <Text style={styles.text}>대전 화면을 불러오지 못했습니다.</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setFailed(false);
              setLoading(true);
              web.current?.reload();
            }}
            style={styles.button}
          >
            <Text style={styles.buttonText}>다시 시도</Text>
          </Pressable>
          <Pressable accessibilityRole="button" onPress={() => router.back()} style={styles.button}>
            <Text style={styles.buttonText}>돌아가기</Text>
          </Pressable>
        </View>
      ) : (
        <WebView
          ref={web}
          source={{ uri: target }}
          originWhitelist={[SITE_ORIGIN]}
          javaScriptEnabled
          domStorageEnabled
          sharedCookiesEnabled
          allowsBackForwardNavigationGestures={false}
          setSupportMultipleWindows={false}
          overScrollMode="never"
          bounces={false}
          onLoadEnd={() => setLoading(false)}
          onError={() => setFailed(true)}
          onHttpError={(event) => {
            if (event.nativeEvent.statusCode >= 500) setFailed(true);
          }}
          onRenderProcessGone={() => setFailed(true)}
          onNavigationStateChange={(state) => {
            canGoBack.current = state.canGoBack;
          }}
          onShouldStartLoadWithRequest={(request) => {
            const kind = classifyNavigation(request.url, SITE_ORIGIN);
            if (kind === "allow") return true;
            if (kind === "close") router.back();
            else void Linking.openURL(request.url);
            return false;
          }}
          style={{ flex: 1, backgroundColor: "#070b14" }}
        />
      )}
      {loading && !failed && (
        <View
          pointerEvents="none"
          style={{ position: "absolute", inset: 0, alignItems: "center", justifyContent: "center" }}
        >
          <ActivityIndicator color={colors.accent} />
        </View>
      )}
    </SafeAreaView>
  );
}
