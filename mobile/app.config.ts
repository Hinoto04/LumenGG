import type { ExpoConfig } from "expo/config";

const config: ExpoConfig = {
  name: "LumenDB",
  icon: "./assets/icon.png",
  slug: "lumendb",
  version: "1.0.4",
  scheme: "lumendb",
  orientation: "default",
  userInterfaceStyle: "dark",
  ios: {
    supportsTablet: true,
    requireFullScreen: true,
    bundleIdentifier: "kr.hinoto.lumen",
  },
  android: {
    package: "kr.hinoto.lumen",
    versionCode: 5,
    // Android 13–15 must deliver Back to React Native's navigation handlers.
    // React Native registers the Android 16 dispatcher callback itself.
    predictiveBackGestureEnabled: false,
    blockedPermissions: [
      "android.permission.READ_EXTERNAL_STORAGE",
      "android.permission.WRITE_EXTERNAL_STORAGE",
      "android.permission.SYSTEM_ALERT_WINDOW",
      "android.permission.RECORD_AUDIO",
    ],
  },
  plugins: [
    "expo-router",
    "expo-sqlite",
    "expo-secure-store",
    "expo-image",
    "expo-status-bar",
    "./plugins/with-screen-orientations",
    "./plugins/with-upload-signing",
  ],
  experiments: { typedRoutes: true },
};
export default config;
