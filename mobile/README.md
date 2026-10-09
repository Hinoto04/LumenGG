# LumenDB mobile

Android/iOS app built with Expo SDK 57, React Native and TypeScript. It contains
the five database features, a bundled public catalog, account-scoped offline
storage, and local/shared calculators. The included seed contains 455 cards,
19 characters, 35 packs, 1,802 collection items and 487 Q&A entries.

The start screen uses a two-column/four-row menu: Calculator occupies the top
2×2 area; Cards/Decks and Collection/QNA occupy the remaining four cells. Feature
screens return to this menu through stack navigation; there is no bottom tab bar.
Card search has icon-only sort and display controls at the right end of the
filter row. Display cycles directly
between a card grid and detailed rows. The sort popover supports card number,
localized name, speed, damage, hit/counter/guard values, and first release date;
missing/non-numeric values stay at the end. Both preferences persist locally.

Filters open a full-screen editor. Character, card type and attack-height
categories each use one horizontally scrolling option row. Speed and damage
ranges have named minimum/maximum fields. Edits stay in a draft until the fixed
bottom Apply button is pressed; Cancel leaves the previous filters intact. Apply
stays above the keyboard, and invalid/reversed numeric ranges cannot be applied.

Calculator opens in landscape; other routes use portrait. Its three columns
follow the web calculator: player HP/FP panels on either side, timer and common
actions in the center, and independently scrolling passive controls below HP.
Tap an HP value for custom damage. Settings, sharing and history use landscape
dialogs. HP undo retains the existing web behavior; FP reset is separate.

Per-screen orientation uses [Expo Router's native stack orientation option](https://docs.expo.dev/versions/latest/sdk/screen-orientation/#per-screen-orientation-with-expo-router).
iOS allows both orientations and requires full screen on iPad. Android 16's
large-screen compatibility property preserves these orientation requests;
[revisit the property before targeting API 37](https://developer.android.com/about/versions/16/behavior-changes-16#adaptive-layouts).

## Run and build

Use Node 24 and an Android SDK/JDK 21 for local Android builds.

```powershell
cd mobile
npm ci
Copy-Item .env.example .env.local
npm run typecheck
npm test
npm run start
```

`EXPO_PUBLIC_API_URL` is the server origin, without `/api/mobile/v1`.
The default is `https://lumen.hinoto.kr`. For an Android emulator and a local
server, use `http://10.0.2.2:8000` in a development build. Deploy the new backend
before testing account sync or shared calculators against the production origin.

```powershell
npm run android
# Installable internal builds; requires an Expo account/project:
npx eas-cli login
npx eas-cli build --platform android --profile preview
npx eas-cli build --platform ios --profile preview
# Signed store builds also require Google/Apple developer credentials:
npx eas-cli build --platform all --profile production
```

`npm run export` verifies both native JS/Hermes bundles. This does not sign an
APK/IPA or replace device testing. EAS project registration/signing and store
submission are account-specific and are not embedded in the repository.

### Local Play Store bundle

The application ID is `kr.hinoto.lumen`, version `1.0.1`, versionCode 2.
The upload keystore is `C:\Hinoto\lumen-upload.keystore`; the configured alias is
`HInoto_key`. Its RSA-3072 certificate expires on December 31, 9999. The passwords
are stored outside the repository in Windows-encrypted SecureStrings at
`C:\Hinoto\lumen-upload.credentials.xml`. This XML can be decrypted only by the
Windows account/machine that created it. Keep a separate backup of the keystore
and the passwords supplied when creating it; the XML is a local convenience.
JKS aliases are case-insensitive and keytool displays this alias in lowercase.

From the repository root:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File mobile/scripts/build-play-bundle.ps1
# For a later upload, use a greater versionCode:
powershell -NoProfile -ExecutionPolicy Bypass -File mobile/scripts/build-play-bundle.ps1 -VersionCode 3
```

The default versionCode comes from app.config.ts. The script regenerates Android
configuration while retaining build caches, passes signing credentials only through
process environment variables, builds the AAB and a review APK, verifies the AAB
signature, and copies them to `artifacts/`. No private key/password is embedded
in source, Gradle configuration, or the deliverable. Do not generate a replacement
key for updates. EAS builds require importing the same upload key into the Expo
project's Android credentials before submission.

In Play Console, create the app, configure Play App Signing and upload the AAB to
an internal test track first. Google can manage the distribution signing key;
the local key is then the upload key for subsequent bundles. The public
certificate is `C:\Hinoto\lumen-upload-certificate.pem`.
See [Android's signing guide](https://developer.android.com/studio/publish/app-signing).
Production backend deployment and the Play Console listing/privacy/data-safety
information remain separate from producing an uploadable binary.

## Offline data and synchronization

`src/catalog.ts` validates catalog size, SHA-256, SQLite integrity, foreign keys,
schema and embedded revision before committing the active-file pointer. The
previous DB is retained for startup recovery. Startup always checks for updates;
foreground/network-resume checks use a five-minute interval. Thumbnails are
downloaded by three workers. Full images use a 300 MB LRU cache.

The catalog and `lumendb-user.sqlite` are separate files. User documents and
immutable operations are scoped to `guest` or `user:<id>`. Failed operations stay
local; editing creates a fresh operation. Acknowledging an older revision cannot
erase a newer edit. The server applies operations in arrival order and remembers
operation UUIDs, so an old retry cannot overwrite a newer server value.

Guest import creates new deck UUIDs. Imported drafts are validated before sync;
only selected collection quantities replace the account quantities. Login does
not silently combine or add quantities. Logout keeps account caches isolated;
refresh/control tokens are in SecureStore.

Shared calculators use server authority and lock controls while disconnected.
Only a previously submitted action with an unknown outcome is reconciled using
the same UUID. New offline shared actions are never queued. Local calculators
remain available and persist their state/history independently.

## Refresh the bundled seed

This command reads only the public catalog in the existing source database;
it does not migrate or write that database and exports no user decks/accounts.

```powershell
cd ../LumenGG
../.venv/Scripts/python.exe manage.py export_mobile_seed --output ../mobile/assets/catalog.sqlite
```

Run it before each store release. Ordinary card/Q&A/translation/image changes
are distributed by the backend publisher and do not require rebuilding the app.

## Validation

`tests/storage.test.ts` runs the actual SQL storage engine against Node SQLite:
in-flight edit preservation, failed receipts, account separation, guest import.
`tests/core.test.ts` covers search, deck rules, HP/FP/undo/reset, timer and passives.

The backend tests verify snapshot hashes/publication, source changes, image
changes, idempotent sync, account boundaries, token rotation, expiration and
WebSocket broadcasts to existing web viewers. See [server rollout](../MOBILE_IMPLEMENTATION.md).

Before store submission, also verify on Android and iOS devices: first launch in
airplane mode; search/Q&A; draft and quantities across force-stop; reconnect and
account switching; unchanged app binary receiving a new catalog; shared web/app
actions, viewer permissions and reconnect; cache eviction and storage exhaustion.
