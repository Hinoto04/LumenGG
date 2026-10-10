# Verified implementation

The implementation was checked with isolated databases, never migrated or
deployed to the production database/server.

- Earlier full Django regression suite: 1,089 tests passed, including 18 mobile API,
  migration and realtime scenarios.
- TypeScript strict type checking, Expo dependency compatibility, and 42
  application/SQL storage tests passed.
- Both Android and iOS Hermes bundles exported successfully.
- An installable ARM64/x86_64 Android APK was built with JDK 21/SDK 36.
- An upload-signed Android App Bundle was built for `kr.hinoto.lumen`, version
  1.0.5, versionCode 6, minSdk 24 and targetSdk 36.
- bundletool 1.18.3 validated the final AAB. All 1,268 payload entries had valid
  signatures matching the saved upload certificate. All 50 native libraries
  passed the 16 KB ELF segment alignment check; the AAB requests
  `PAGE_ALIGNMENT_16K`, and its generated universal APK passed zipalign's 16 KB
  check. These are binary alignment checks, not a 16 KB-device runtime test.

Android 15 emulator checks used an isolated SQLite/Daphne backend with a
test-only signing key:

1. With Wi-Fi/data disabled, all 455 bundled cards loaded, a code search returned
   one matching card, and an existing Q&A question/answer opened correctly.
2. A draft named `offline-smoke` remained after leaving/restarting the app.
   Three rapid collection increments persisted as quantity 3 across force-stop.
3. A local calculator changed HP from 5000 to 4900 and restored it after restart.
4. Without rebuilding/reinstalling the APK, changing a server card and publishing
   a new catalog changed its app title to `Native update verified` on the next
   launch. The saved collection quantity remained 3.
5. An intentionally incorrect catalog SHA-256 was rejected. The app retained
   the prior card title/database and displayed the update failure notice.
6. Login and explicit guest import stored quantity 3 on the isolated server.
7. The native shared calculator's -100 action stored HP 4900 on the server.
   Another client's -50 HTTP action then appeared live as HP 4850 in the app.

The final AAB was converted into a universal APK with bundletool and a test
certificate, then installed on the Android 15 emulator:

1. The start menu has two columns/four rows, with Calculator occupying the top
   2×2 area, Cards/Decks in the next row, and Collection/QNA in the last row.
   There is no application bottom navigation bar.
2. Card display switched between a two-column grid and detailed rows. Searching
   `AWL-AT-001` returned one card; switching display retained the query/result.
3. The sort button opened the options. Damage descending placed
   `RFS-AT-013` (1500 damage) first. The sort modal closed with Android Back.
4. Android Back returned all five feature screens to the start menu. Android
   13–15 use legacy Back dispatch; React Native handles Android 16's dispatcher.
5. Force-stop/relaunch retained the grid display and damage-descending sort.

The revised filter/calculator UI was also checked on the Android 15 emulator:

- Filter controls occupy a full-screen dialog with named groups, horizontal
  choices and a pinned Apply footer. Horizontal swipes changed the visible
  character choices without moving the footer.
- Selecting Attack previewed 332 cards; Cancel retained all 455 cards. Applying
  the selection displayed 332 cards in the list.
- With the numeric keyboard visible, the footer stayed above it. Minimum damage
  500 previewed and applied 158 cards, matching an independent seed SQLite query.
- Both tool buttons are icons on the right of the filter row.
- Calculator entry forced landscape even with the device in portrait; its
  player panels, FP strips and center timer remained simultaneously visible.
- HP changes and HP-only undo matched the web behavior; FP increment/reset and
  timer countdown were exercised. Local calculator values survived restart.
- History remained landscape; closing calculator returned the start menu to
  portrait and re-entering calculator restored landscape.

iOS Hermes export is checked; iOS device rotation and Android 16 tablet rotation
still require those devices. The latter's compatibility property is included in
the generated Android manifest.

Additional calculator checks on the Android 15 emulator:

- Three rapid HP taps (-500, -100, -100) displayed a -700 badge with HP still
  5000, then committed HP 4300 with a single -700 history event.
- At HP 800, the ratio-based bar showed an orange background/short fill, while
  the other player's full-health bar stayed green.
- Both FP + controls are above FP − controls. Root's Charge button showed its
  name instead of ON/OFF; its checked state toggled on and off.
- Tao's Yang/Yin counters share a row. At 4/4 harmony, both effect switches
  appeared dark on the next row. Repeated taps enabled/disabled the same effect;
  choosing the other effect preserved mutual exclusion. The Tao panel had no
  scroll container.
- Leaving for the menu before an HP +100 debounce expired flushed the local
  change; calculator re-entry restored HP 900 from the previous HP 800.

Queue tests cover 900 ms trailing debounce, opposite-delta cancellation,
disconnect cancellation, serial shared delivery and local flush/disposal.

Card printing and collection filter checks on the Android 15 emulator:

- Standing Guard (ST1-011) showed its separate starter-pack printings with pack
  names, printing numbers, rarity, release dates and thumbnails.
- Collection opened a full-screen filter sheet. The pack choices scrolled
  horizontally while the Apply footer remained fixed.
- Skin selection previewed 72 items. Cancel retained all 1,802 items; Apply
  displayed 72 items; Reset plus Apply restored all 1,802 items.
- Card search's filter screen still opened and previewed all 455 cards after
  extracting the shared filter-sheet components.

Collection data tests verify grouped rarities, separate same-code packs/skins,
missing references, combined filters, quantity-sensitive unowned filtering and
localized search/code normalization.

FP/history changes passed 981 isolated `mobile_api`/`battlelog` regression tests,
including new coverage for shared passive event before/after payloads. Client
tests cover FP debounce, selective reset cancellation, numeric/boolean passive
logs, shared payloads, missing legacy values, player attribution and timer
exclusion before history limits. Android UI checks verified FP 0 → 3 and numeric
passive history with opposite-side player cards. Final native checks also
verified Charge's inactive → active label, Yang 1 → 2, and no timer rows after
starting/stopping the timer. The pending FP screenshot showed +3 while the
committed FP value was still 0, then the history recorded a single 0 → 3 change.

The final distributable uses the production HTTPS origin, contains the public
seed, and excludes the temporary emulator API/cleartext settings. Both the AAB
and supplied review APK are signed with the upload key at
`C:\Hinoto\lumen-upload.keystore`, configured alias `HInoto_key`, RSA 3072,
certificate expiration December 31, 9999. The test-only universal APK is separate
from the supplied artifacts. Passwords are outside the repository in
Windows-encrypted credential storage.

Still requiring deployment/account/device access: production migration/hosting,
Docker image execution and MariaDB validation, Play Console registration and
submission, and iOS signing/native/physical-device tests. Existing Expo tooling npm
advisories are documented in the server rollout guide.


Mobile 1.0.5 deck browsing validation:

- 42 client tests passed, including physical-copy zone partitioning, 9/6/3-column
  sizes, missing catalog references, description HTML-to-text rendering, draft
  archival, suppression of old deck operations, and collection-only guest import.
- 24 isolated mobile API tests passed. New browsing coverage checks anonymous
  public search, author/name/character search, pagination, owner-only private
  decks, hidden unlisted/deleted search results, and 405 for write methods.
- TypeScript and both Android/iOS Hermes exports passed.
- Android 15 used an isolated local test backend with a 24-card public fixture.
  The app opened the deck from public search. Native accessibility bounds showed
  exactly 9, 6 and 3 cards on the first row for Small, Medium and Large.
  Zone headings were List (21), Hand (2), Side (1), then Description. No deck
  creation, edit, copy or delete buttons were present.
- Force-stop/relaunch restored Large (3 columns). After selecting Small, disabling
  Wi-Fi/data and force-stopping/relaunching still restored the cached deck with
  9 columns. Network connectivity was restored after the test.
- Screenshots: artifacts/LumenDB-decks-9.png, LumenDB-decks-6.png,
  LumenDB-decks-3.png. Small and Medium were visually inspected.
- The test APK/API are separate from the production-address upload-signed AAB.
  This task does not deploy the new GET deck endpoints to production.
