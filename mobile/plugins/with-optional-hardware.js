const {
  withAndroidManifest,
  createRunOncePlugin,
} = require("expo/config-plugins");

// @react-native-community/netinfo adds ACCESS_WIFI_STATE, which makes Google Play
// treat android.hardware.wifi as required and hide the app from devices without Wi-Fi.
// The app only reads connectivity, so declare the hardware as optional.
const OPTIONAL_FEATURES = ["android.hardware.wifi"];

function withOptionalHardware(config) {
  return withAndroidManifest(config, (config) => {
    const manifest = config.modResults.manifest;
    manifest["uses-feature"] = (manifest["uses-feature"] || []).filter(
      (entry) => !OPTIONAL_FEATURES.includes(entry.$["android:name"]),
    );
    for (const name of OPTIONAL_FEATURES)
      manifest["uses-feature"].push({
        $: { "android:name": name, "android:required": "false" },
      });
    return config;
  });
}

module.exports = createRunOncePlugin(
  withOptionalHardware,
  "lumen-optional-hardware",
  "1.0.0",
);
