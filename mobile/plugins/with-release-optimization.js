const {
  withAppBuildGradle,
  withGradleProperties,
  createRunOncePlugin,
} = require("expo/config-plugins");

function withReleaseOptimization(config) {
  config = withGradleProperties(config, (config) => {
    for (const key of [
      "android.enableMinifyInReleaseBuilds",
      "android.enableShrinkResourcesInReleaseBuilds",
      "android.r8.optimizedResourceShrinking",
    ]) {
      config.modResults = config.modResults.filter(
        (item) => item.type !== "property" || item.key !== key,
      );
      config.modResults.push({ type: "property", key, value: "true" });
    }
    return config;
  });
  return withAppBuildGradle(config, (config) => {
    if (config.modResults.language !== "groovy")
      throw new Error("LumenDB release optimization expects Groovy Gradle.");
    config.modResults.contents = config.modResults.contents.replaceAll(
      "proguard-android.txt",
      "proguard-android-optimize.txt",
    );
    if (!config.modResults.contents.includes("proguard-android-optimize.txt"))
      throw new Error("Cannot locate the Android release optimization rules.");
    return config;
  });
}

module.exports = createRunOncePlugin(
  withReleaseOptimization,
  "lumen-release-optimization",
  "1.0.0",
);
