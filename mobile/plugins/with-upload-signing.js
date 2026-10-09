const {
  withAppBuildGradle,
  createRunOncePlugin,
} = require("expo/config-plugins");

const marker = "// LumenDB local upload signing";
const signing = `
${marker}
def lumenUploadValues = [
    System.getenv('LUMEN_UPLOAD_STORE_FILE'),
    System.getenv('LUMEN_UPLOAD_STORE_PASSWORD'),
    System.getenv('LUMEN_UPLOAD_KEY_ALIAS'),
    System.getenv('LUMEN_UPLOAD_KEY_PASSWORD')
]
def lumenHasUploadSigning = lumenUploadValues.every { it != null && !it.isEmpty() }
if (lumenUploadValues.any { it != null } && !lumenHasUploadSigning) {
    throw new GradleException('Incomplete LumenDB upload signing configuration')
}
if (System.getenv('LUMEN_REQUIRE_UPLOAD_SIGNING') == '1' && !lumenHasUploadSigning) {
    throw new GradleException('A Play Store build requires the LumenDB upload key')
}
if (lumenHasUploadSigning) {
    android.signingConfigs.create('lumenUpload') {
        storeFile file(lumenUploadValues[0])
        storePassword lumenUploadValues[1]
        keyAlias lumenUploadValues[2]
        keyPassword lumenUploadValues[3]
        storeType 'JKS'
    }
    android.buildTypes.release.signingConfig = android.signingConfigs.lumenUpload
}
if (System.getenv('LUMEN_VERSION_CODE') != null) {
    def lumenVersionCode = System.getenv('LUMEN_VERSION_CODE').toInteger()
    if (lumenVersionCode < 1) throw new GradleException('versionCode must be positive')
    android.defaultConfig.versionCode = lumenVersionCode
}
`;

function withUploadSigning(config) {
  return withAppBuildGradle(config, (config) => {
    if (config.modResults.language !== "groovy") {
      throw new Error("LumenDB signing expects a Groovy app/build.gradle");
    }
    if (!config.modResults.contents.includes(marker)) {
      config.modResults.contents += signing;
    }
    return config;
  });
}

module.exports = createRunOncePlugin(
  withUploadSigning,
  "lumen-upload-signing",
  "1.0.0",
);
