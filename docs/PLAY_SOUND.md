# 대전 클라이언트 효과음

코드는 `play/src/sound/`에 있다.

- `sfx.ts`: 소리 이름 목록, 재생, 음량 설정, Web Audio 합성음
- `events.ts`: 게임 이벤트를 소리 이름으로 연결

기본 소리는 브라우저에서 바로 합성한다. 따라서 음원 파일이나 라이선스가 없어도 소리가 난다.

## 동작

- 재생기(`anim/playback.ts`)가 이벤트를 화면에 올릴 때마다 해당 소리를 낸다.
  - 밀린 이벤트를 4배속으로 따라잡을 때는 소리를 내지 않는다.
  - 같은 소리는 70ms 안에 겹쳐 나지 않는다.
- 내 선택 창이 새로 열리면 `prompt`가 울린다.
- 내 제한 시간이 5초 이하로 남으면 1초마다 `tick`이 울린다.
- 덱 준비 화면에서 카드를 다른 영역에 놓으면 `card_move`가 울린다.
- 브라우저는 사용자가 한 번 누르기 전에는 소리를 막는다. 첫 클릭이나 터치 때 오디오를 깨운다.
- 탭이 가려져 있으면 소리를 내지 않는다.

## 모바일

- 오디오는 터치 입력(`touchstart`·`touchend`·`click` 등)에서 깨운다. iOS WebKit은 `pointerdown`을 사용자 입력으로 치지 않기 때문이다.
  처음 깨울 때 무음 버퍼를 한 번 재생한다.
- 전화를 받거나 앱을 전환한 뒤에는 오디오가 멈춘다. 화면으로 돌아오거나 다음 입력이 있을 때 다시 깨운다.
  소리를 내려는 순간 멈춰 있으면 깨우고 그 소리 하나만 건너뛴다.
- 앱 WebView(`mobile/app/play.tsx`)는 `mediaPlaybackRequiresUserAction={false}`와 `allowsInlineMediaPlayback`을 켠다.
  안드로이드 WebView는 기본값에서 오디오 재생을 막는다.
- 안드로이드는 미디어 음량을 따른다.
- 아이폰은 기본값에서 무음 스위치를 켜면 효과음도 나지 않는다.
  메뉴의 '무음 모드에서도 재생'을 켜면 오디오 세션을 `playback`으로 바꿔 무음 스위치와 상관없이 낸다.
  이 경우 듣던 음악이 멈출 수 있다. 이 항목은 `navigator.audioSession`이 있는 Safari 17 이상(iOS 17)에서만 보인다.
- 대전 화면의 메뉴 버튼(☰) → 효과음에서 음소거와 음량을 조절한다. 설정은 기기에 저장된다(`localStorage`의 `lumen-play-sound`).
  '들어보기'를 누르면 주요 효과음을 차례로 들려준다.
- 합성음은 짧은 어택, 떨어지는 저음, 필터 스윕 꼬리를 겹쳐 만든다. 반짝임과 금속음에는 잔향을 섞는다.
  출력은 압축기와 리미터를 거친다. 여러 소리가 겹쳐도 깨지지 않고 전체 음압은 높게 유지된다.

## 음원 파일로 바꾸기

1. `play/public/sfx/`에 파일을 넣는다. `.ogg`나 `.mp3`를 권장하고 `.wav`도 된다.
2. `play/public/sfx/manifest.json`에 `"소리 이름": "파일명"`을 적는다. 예:
   ```json
   { "hit": "hit_heavy.ogg", "card_move": "card_slide_02.ogg" }
   ```
3. `cd play; npm run build:django`를 실행한다. 파일이 `LumenGG/static/play/sfx/`로 복사된다.

목록에 없는 이름은 계속 합성음을 쓴다. 파일을 못 읽어도 합성음으로 대신한다.
`LumenGG/static/play/`는 빌드할 때 비워지므로 파일은 반드시 `play/public/sfx/`에 둔다.

| 이름 | 언제 | 찾을 소리 |
| --- | --- | --- |
| `card_move` | 카드가 존을 옮김(드로우·버림·준비 화면 드롭) | 카드 미끄러짐 |
| `card_ready` | 배틀존에 카드를 냄(레디·콤보) | 카드 내려놓기 |
| `card_reveal` | 배틀 공개 | 카드 뒤집기 |
| `hit` | 판정 히트·방어 실패 | 타격 |
| `counter` | 판정 카운터 | 강한 타격 |
| `guard` | 판정 가드 | 금속 방패 |
| `dodge` | 판정 회피 | 휙(whoosh) |
| `clash` | 판정 상쇄 | 칼 부딪힘 |
| `grab` | 판정 잡기 | 붙잡기·천 |
| `damage` | HP 감소 | 둔탁한 피격 |
| `heal` | HP 회복 | 회복 차임 |
| `fp_up` / `fp_down` | FP 증감 | 짧은 상승·하강음 |
| `effect` | 카드 효과 발동 | 마법 반짝임 |
| `passive` | 패시브 카운터·상태 변화 | 작은 반짝임 |
| `shield` | 실드가 피해를 막음 | 보호막 |
| `combo` | 콤보 시작 | 상승 스윙 |
| `catch` | 캐치 시작 | 날카로운 가로채기 |
| `break` | 카드 브레이크 | 깨짐 |
| `shuffle` | 덱 섞기 | 카드 셔플 |
| `phase` / `turn` | 페이즈 시작 / 새 턴 | 부드러운 알림 / 징 |
| `prompt` | 내 선택 필요 | UI 알림 |
| `tick` | 제한 시간 5초 이하 | 시계 틱 |
| `win` / `lose` | 대전 종료 | 승리·패배 징글 |
| `ui` | (예비) 버튼 | 클릭 |

## 추천 음원

라이선스는 바뀔 수 있다. 구입하거나 내려받기 전에 각 페이지의 조건을 다시 확인한다.

**무료**

- [Kenney Casino Audio](https://kenney.nl/assets/casino-audio): CC0. 카드 다루는 소리가 들어 있어 `card_move`, `card_ready`, `card_reveal`, `shuffle`에 맞는다.
- [Freesound](https://freesound.org): 라이선스를 'Creative Commons 0'으로 걸러서 타격·마법 소리를 고른다. CC-BY 음원은 출처를 표기해야 한다.

**유료**

| 상품 | 가격 | 메모 |
| --- | --- | --- |
| [Card Games Sound Effects (itch.io, ad-sounds)](https://ad-sounds.itch.io/card-games-sound-effects) | 약 $10부터 | 카드 소리 위주. 상업 게임에 사용할 수 있다. |
| [Board and Card Game FX (itch.io, Verdillo)](https://verdillo.itch.io/board-and-card-game-fx) | 약 €4부터 | WAV 215개. 상업용으로 쓸 수 있고, 음원 팩으로 재배포하는 것만 금지한다. |
| [Card & Board Games SFX and Music Pack (GameDev Market)](https://gamedevmarket.net/asset/cardboard-games-sound-effects-and-music-pack) | $49 | 효과음 520개 이상과 음악. 프로젝트 수 제한이 없다. |

타격·마법 계열(`hit`, `counter`, `effect`, `combo`)은 카드 게임 팩보다 격투·RPG 효과음 팩에서 고르는 편이 어울린다.
