const {
  withAndroidManifest,
  createRunOncePlugin,
} = require("expo/config-plugins");

// Android 16 tablets otherwise ignore per-screen orientation requests.
// Revisit this compatibility setting when raising targetSdk to 37.
function withScreenOrientations(config) {
  return withAndroidManifest(config, (config) => {
    const application = config.modResults.manifest.application?.[0];
    const activity = application?.activity?.find((entry) =>
      entry.$["android:name"].endsWith("MainActivity"),
    );
    if (!activity) throw new Error("LumenDB MainActivity is missing");
    const name = "android.window.PROPERTY_COMPAT_ALLOW_RESTRICTED_RESIZABILITY";
    activity.property = (activity.property || []).filter(
      (entry) => entry.$["android:name"] !== name,
    );
    activity.property.push({
      $: { "android:name": name, "android:value": "true" },
    });
    return config;
  });
}

module.exports = createRunOncePlugin(
  withScreenOrientations,
  "lumen-screen-orientations",
  "1.0.0",
);
