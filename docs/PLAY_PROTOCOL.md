# 게임 클라이언트 프로토콜 (v1)

새 게임 클라이언트(`play/`)가 자동 판정 세션과 주고받는 데이터 계약이다.
서버가 판정하고 클라이언트는 고르기만 한다. 클라이언트는 룰을 몰라도 된다.

| 위치 | 역할 |
|---|---|
| `play/src/protocol.ts` | TypeScript 타입 |
| `LumenGG/battlelog/play_protocol.py` | 버전 상수, `validate_play_envelope()` 구조 검사 |
| `LumenGG/battlelog/test_play_protocol.py` | 계약 테스트, 픽스처 추출 |
| `scripts/export-play-fixtures.ps1` | 픽스처를 `play/fixtures/`로 추출 |
| `scripts/serve-play-dev.ps1` | 실제 룰셋·AI로 대전하는 격리된 로컬 서버 |

필드를 바꿀 때는 위 세 파일과 이 문서를 함께 고친다. 이미 배포된 클라이언트와 호환되도록
**필드 추가만** 하고, 의미가 바뀌면 `PLAY_PROTOCOL_VERSION`을 올린다.

## 전송

기존 시뮬레이터 WebSocket을 그대로 쓴다.

```
ws/battlelog/simulator/<view_token>/?seat=p1&seat_token=...&language=ko
```

1. 접속하면 서버가 `{type: "state", state: <envelope>}`를 보낸다(이벤트 제외).
2. `{type: "log_subscribe", since_seq: N}`을 보내면 N 이후 이벤트가 `log_events`로 오고,
   이후 변경 때마다 새 이벤트가 이어서 온다.
3. 세션이 바뀌면 모든 접속자에게 `state_dirty {version}`가 온다. 내 버전보다 크면 `state`를 다시 요청한다.
4. 행동은 `{type: "command", request_id, payload: {command_id, action_id, expected_version, selections}}`로 보낸다.
   성공하면 `command_ack`, 실패하면 `error`와 `code`가 온다.
   - `stale_state`: 버전이 지났다. 함께 온 `state`로 갱신한다.
   - `illegal_action`: 이미 무효가 된 행동이다. 상태를 다시 받는다.
   - `automatic_fallback`: 엔진 오류로 세션이 수동 모드로 바뀌었다. 게임 클라이언트는 종료 화면을 보여 준다.

HTTP로는 `GET simulator/<view_token>/state/`, `POST simulator/<view_token>/command/`가 같은 본문을 쓴다.

## Envelope

`serialize_simulator_session()`의 자동 모드 응답이다. 주요 필드:

| 필드 | 설명 |
|---|---|
| `protocol_version` | 현재 `1`. 자동 모드에서만 들어 있다 |
| `version` | 낙관적 동시성 버전. 명령의 `expected_version`으로 보낸다 |
| `role` | `p1` / `p2` / `viewer` |
| `can_submit_commands` | 이 접속이 명령을 보낼 수 있는지 |
| `state` | 역할별로 가린 보드 상태 |
| `legal_actions` | 지금 이 역할이 할 수 있는 행동. 관전자와 AI 좌석은 항상 빈 목록 |
| `pending_decision` | 효과 선택 요청. 상대의 선택이면 `owner`와 `prompt`만 온다 |
| `clocks` | 진행 중인 타이머 `{kind, owner, deadline, paused}` |
| `engine_status` | `{status, step, winner, reason}` |
| `events` | HTTP 응답에만 포함. WebSocket은 `log_events`로 받는다 |

### 카드

`state.players[side].zones[zone]`의 각 카드는 `hidden`으로 갈린다.

- `hidden: false`: `instance_id`와 `card_id`가 있다. 이름·수치·효과문은 공개 룰셋 값으로 채워져 있지만 **이미지는 없다**.
- `hidden: true`: `instance_id`, `card_id`, `code` 같은 식별 정보가 **없다**. 위치로만 가리킨다.

### 카드 카탈로그

이미지와 효과문 렌더 결과는 `card_id`로 따로 받는다(기존 시뮬레이터와 같은 엔드포인트).

```
GET simulator/<view_token>/card-metadata/?ids=109,110   (최대 200개)
→ {"cards": {"109": {card_id, code, name, type, frame, damage, pos, text, text_label,
                     detail_text, detail_text_label, img, img_sm, img_lg, ...}}}
```

| 필드 | 용도 |
|---|---|
| `img_sm` | 작은 썸네일(리스트·더미) |
| `img` | 보드·손패 |
| `img_lg` | 원본 크기, 확대 보기 |
| `text_label`, `detail_text_label` | `[[state:charge]]` 같은 마크업을 표시 문자열(「차지」)로 렌더한 효과문 |

화면에서는 상태 카드의 값(게임 중 바뀐 수치)을 우선하고, 비어 있는 값만 카탈로그로 채운다(`play/src/catalog.ts`).
캐릭터 이미지(`img` 전신, `icon_img` 아이콘)와 `color`는 `state.players[side].character`에 이미 들어 있다.

## 행동의 `ui` 힌트

`legal_actions`의 각 행동에는 `ui`가 붙는다. `action_id` 계산에는 포함되지 않는다.

```json
{
  "action_id": "030cc54b...",
  "type": "ready_card",
  "label": "p1-strike",
  "payload": {"card_instance_id": "p1-strike"},
  "ui": {
    "kind": "card",
    "cards": [{"owner": "p1", "zone": "hand", "index": 0, "instance_id": "p1-strike"}]
  }
}
```

| `ui.kind` | 화면에서의 의미 | 행동 종류 |
|---|---|---|
| `card` | 해당 카드를 빛나게 하고 누르면 실행 | `ready_card`, `select_get_card`, `select_ultimate`, `play_catch_card`, `play_combo_*`, `select_combo_first`, `select_combo_followup` |
| `primary` | 오른쪽 아래 진행 버튼 하나 | `pass_phase`, `end_combo`, `decline_catch`, `declare_no_response` |
| `secondary` | 진행 버튼 옆의 작은 버튼 | `cancel_combo_first` (모르는 새 행동도 여기로 온다) |
| `decision` | 선택 창 열기 | `submit_decision` |
| `system` | 메뉴·시스템 대화상자 | `pause_clock`, `resume_clock`, `request_rewind`, `answer_rewind`, `concede` |

분류표는 `battlelog/game/engine.py`의 `ACTION_UI_KINDS`다. 엔진에 새 행동을 추가하면
`test_every_dispatched_action_type_has_an_ui_kind`가 분류표 누락을 잡는다.

한 카드에 행동이 여러 개 묶일 수 있다. 예를 들어 같은 카드의 속도 선택지가 다른 캐치는
행동마다 `label`과 `choice_speed`가 다르다. 이때 클라이언트는 카드를 누르면 작은 선택 메뉴를 띄운다.

### `CardRef`

`{owner, zone, index}`는 **같은 응답**의 `state.players[owner].zones[zone][index]`를 가리킨다.
`instance_id`는 그 카드가 이 역할에게 보일 때만 들어 있다.

### 선택지

`submit_decision` 행동의 `options`와 `pending_decision.options`의 각 선택지에는
`ui: {card?: CardRef}`가 붙는다. `card`가 있으면 보드 위 그 카드를 눌러 고르게 하고,
없으면(효과 분기, 숫자 선택 등) 선택 창에 버튼으로 보여 준다.
제출은 `selections: {selected: [option.id, ...]}`이며 개수는 `minimum`~`maximum` 사이여야 한다.

## 이벤트

이벤트는 `seq` 순으로 재생한다. 애니메이션에 주로 쓰는 이벤트:

| type | payload |
|---|---|
| `phase_started` | `phase`, `turn` |
| `card_moved` | `card_instance_id`, `from_player`, `from_zone`, `to_player`, `to_zone`, `reason`, `card_label` |
| `battle_revealed`, `battle_judged` | 양쪽 배틀 카드, 판정 결과 |
| `hp_changed`, `fp_changed` | `before`, `after`, `amount`, `source` |
| `damage_dealt` | `target`, `amount`, `source` |
| `card_broken` | `card_instance_id`, `reason` |
| `game_finished` | 승자, 사유 |

### 비공개 이벤트

다른 플레이어의 비공개 이벤트는 `type: "private_event"`로 바뀌고 payload가 가려진다.
존별 장수는 이미 공개 정보이므로, 아래 이벤트는 애니메이션용으로 존 정보만 남긴다.
카드 정체(`card_instance_id`, `card_id`, `card_code`, `card_label`)와 `reason`은 절대 남지 않는다.

```json
{"type": "private_event", "actor": "p1",
 "payload": {"redacted": true, "event_type": "card_moved",
             "from_player": "p1", "from_zone": "hand", "to_player": "p1", "to_zone": "battle"}}
```

| 원래 type | 남는 필드 |
|---|---|
| `card_moved` | `from_player`, `from_zone`, `to_player`, `to_zone` |
| `card_readied` | 없음(`event_type`만) |
| 그 외 | `{redacted: true}`만. 종류 자체가 비밀일 수 있다(예: 수동 모드 선언) |

허용 목록은 `simulator_services.PRIVATE_EVENT_PUBLIC_FIELDS`다.

## 사이트와 앱에서의 제공

자동 판정 대전과 수동 대전 모두 이 클라이언트로 한다. 구 시뮬레이터 화면은 아래 "예전 화면이 계속 열리는 경우"에만 쓴다.

| 경로 | 설명 |
|---|---|
| `GET /battlelog/play/` | 클라이언트 페이지(`templates/battlelog/play.html`). `csrftoken` 쿠키를 심는다 |
| `GET /battlelog/play/api/decks/?q=` | 덱 검색(시작 화면 검색과 같은 규칙). `?mine=1`은 로그인한 사용자의 덱 |
| `POST /battlelog/play/api/new/` | `{p1_deck, p2_deck, opponent: ai\|human, mode: automatic\|manual, ready_timeout_seconds, effect_timeout_seconds}` → `{view_token, mode, seats, urls, legacy?}` |
| `POST /battlelog/simulator/<view>/preparation/check/` | 덱 준비 후보를 저장하지 않고 검사(`validate(stage='setup')`) |
| `POST /api/mobile/v1/simulator/sessions` | 앱용(JWT). 본문은 위와 같고 `urls`가 절대 주소다 |

- 대전 생성은 `battlelog/play_start.py`의 `start_session()` 하나로 모았다. 구 시작 화면, 새 로비, 앱이 같은 권한·특성 검사를 거친다.
- 대전을 만들거나 구 좌석·관전 주소(`/battlelog/simulator/<view>/...`)를 열면 `/battlelog/play/?game=…`으로 넘어간다(수동 대전의 예외는 아래).
- 엔진 오류로 수동 모드가 된 세션은 구 화면이 열린다. 오류 안내와 제보는 `static/v2/lumen-simulator-failure.js`가 맡는다.
  새 클라이언트의 중단 화면에는 "수동 모드로 이어하기" 링크가 나온다.
- 판정 문제 제보는 대전 메뉴에서 보낸다(`simulatorReportIssue`, `kind=user`). 브라우저 오류는 `kind=client_error`로 자동 보고된다.

### 수동 대전(샌드박스)

규칙 판정 없이 두 사람이 직접 조작하는 모드다. 로비·앱에서 "사람과 대전 → 수동(샌드박스)"으로 만든다(`mode: "manual"`, AI 상대는 불가).
새 형식 덱이면 자동 판정과 같은 덱 준비 화면을 먼저 거친다.

- 행동은 WebSocket `{type: "action", payload: {action, payload}}`로 보내고 서버(`perform_simulator_action`)가 그대로 적용한다.
  응답은 `action_ack`이며, 결과는 `state_dirty` → `state`로 돌아온다. 낙관적 동시성 버전은 없다.
- envelope에는 엔진 필드가 없으므로 `normalizeEnvelope`가 빈 값으로 채운다. 수동 이벤트(`move_card`, `hp`, `set_phase` …)는
  재생기에서 자동 엔진 이벤트 모양으로 바꿔(`adaptManual`) 같은 연출을 쓴다.

| 화면 | 서버 행동 |
|---|---|
| 내 카드 확대 보기 → 존 버튼, 상대 배틀·루멘 | `move_card {card_instance_id, to_zone, to_player}` |
| 확대 보기 → 공개하기 / 비공개로(공개 존 제외) | `set_visibility {card_instance_id, face_up}` |
| 초상 누르기 → HP ±, 직접 입력 / FP ±1, 초기화 | `hp`, `fp {target, amount}`, `fp_reset {target}` |
| 초상 누르기 → 패시브(토글·카운터·선택, 상태류는 표시만) | `passive {target, key, value, label}` |
| 완료 / 완료 취소 | `set_done {target, done}` |
| 10초 | `timer` (누를 때마다 시작·정지) |
| 도구 → 페이즈, 다음 페이즈, 다음 턴 | `set_phase {phase}`, `phase_advance`, `next_turn` |
| 도구 → 차례 넘기기 | `request_action {target}` |
| 도구 → 배틀존 일괄 이동, 손패 섞기·공개 | `bulk_move`, `shuffle_hand`, `set_hand_visibility` |
| 도구 → 신호, 빠른 기록·직접 기록, 카드 생성 | `signal`, `log_note`, `import_card {card_name}` |
| 도구 → 마지막 행동 되돌리기 | `undo` |

되돌리기는 서버 이벤트 수를 줄인다. 클라이언트는 상태의 `event_count`가 받은 마지막 `seq`보다 작아지면 기록을 잘라 내고
`log_subscribe`를 다시 보내 서버의 구독 위치를 맞춘다(그대로 두면 이후 이벤트가 전달되지 않는다).

**캐릭터 전용 패시브** (`play/src/components/CharacterPassive.tsx`, 예전 `static/battlelog/passive_ui/*_simulator.js`를 옮김)

| 캐릭터 | 패시브 | 전용 행동(자기 캐릭터만) |
|---|---|---|
| 니아 | - | 루멘 정리: 공격/수비 → 리스트 (`nia_lumen_cards_to_list`) |
| CMYK | `new_single_created` | 뉴 싱글 10장 생성 (`cmyk_new_single`) |
| 요한 | 예지 카운터 0~10(기본 2), 디제스터 원 | 예지 공개 (`yohan_foresight_reveal`), 홀·짝·공·수 선언 (`yohan_declare_reveal {declaration}`) |
| 타오 | 양·음 0~4, 조화, 조화 효과(+100DMG·+1FP) | - (양·음 4/4면 조화 켜짐, 한쪽이 3 미만이면 조화와 효과를 끔) |

패널 종류는 서버가 주는 `passive_ui.html`의 표식(`data-nia-panel` 등)으로 고른다.
카드 전용 조작도 확대 보기에 있다. 공개된 블랙아웃은 "암전"(`blackout_random_get`)으로 상대 리스트에서 무작위로 1장 가져온다.
CMYK는 레디 페이즈에 배틀존의 다른 기술에 세트한다(`attach_card`). 세트된 카드에는 "세트" 표시가 붙는다.

**예전 화면이 계속 열리는 경우** (`battlelog/play_start.py`의 `opens_in_game_client`)

- 새 클라이언트가 모르는 전용 패시브 화면을 쓰는 캐릭터가 있는 대전. 지원하는 표식은 `GAME_CLIENT_PASSIVE_MARKERS`이다.
  새 로비는 이때 예전 화면 주소를 돌려준다(`legacy: true`). 새 전용 패시브를 추가하면 이 목록과 `CharacterPassive.tsx`를 함께 고친다.
- 카드 편집 권한이 있는 운영진: 수동 보드에서 자동 테스트 시나리오를 만드는 도구가 예전 화면에만 있다.
- 주소에 `?legacy=1`을 붙인 경우. 새 화면의 메뉴에 "예전 화면으로 보기" 링크가 있다.

구 시뮬레이터 JS는 위 경우와 자동 엔진 오류로 수동 모드가 된 대전을 위해 남아 있다.

### 빌드와 배포

```powershell
cd play; npm run build:django   # → LumenGG/static/play/play.js, play.css
```

계산기 에셋처럼 빌드 결과물을 커밋한다. 파일 이름에 해시가 없으므로 캐시 무효화는 `collectstatic`의 정적 파일 저장소가 맡는다.
`play/` 소스를 바꾸면 커밋 전에 다시 빌드한다.

### 덱 준비

새 형식(특성 지정) 덱으로 만든 대전은 시작 전에 `preparation.status = editing` 상태다. 이때 envelope에는
`legal_actions`, `engine_status`, `clocks`가 없으므로 클라이언트가 빈 값으로 채우고(`normalizeEnvelope`) 준비 화면을 보여 준다.

- 등록 덱과 교체 덱 범위에서 기술·특성·얼티밋을 바꾸고, 카드별 시작 위치(리스트·손패·사이드)를 정한다.
- 고칠 때마다 `preparation/check/`로 검사만 받아 오류를 보여 주고, 교체 횟수는 클라이언트도 같은 규칙으로 센다(`play/src/prep/model.ts`).
- "준비 완료"는 기존 `preparation/` 엔드포인트(`preparation_action: ready`)로 보낸다. AI 좌석은 처음부터 준비 완료다.
- 대전이 끝나면 종료 화면의 "다음 게임"(`next_game`)으로 같은 상대와 다시 준비한다.

### 앱

홈의 "대전"에서 서버에 저장된(동기화된) 내 덱과 상대 덱(같은 덱·내 덱·공개 덱 검색)을 고른다.
`/simulator/sessions`로 만든 뒤 `app/play.tsx`의 WebView로 좌석 주소를 연다. WebView에는 로그인 정보를 넘기지 않는다.

- WebView 안에서는 대전(`/battlelog/play/?game=`)과 수동 모드 시뮬레이터만 연다. 로비 주소('나가기', '새 대전')는 앱 화면으로 돌아가고,
  그 밖의 주소는 바깥 브라우저로 연다(`mobile/src/battle-nav.ts`).
- 친구와 대전하면 상대 좌석 주소를 공유 시트로 보낸다. 마지막 좌석은 하루 동안 "이어하기"로 다시 열 수 있다.

## 로컬 대전 서버

실제 효과 정의와 AI로 대전하면서 클라이언트를 개발하는 환경이다. 설정된 DB(운영 DB일 수 있다)에는 쓰지 않는다.

```powershell
.\scripts\serve-play-dev.ps1          # 게임 서버 127.0.0.1:8874
cd play; npm run dev                  # 클라이언트 127.0.0.1:5175 (/battlelog, /ws, /play-dev 프록시)
```

1. `manage.py export_play_bundle`이 설정된 DB에서 활성 자동 룰셋 릴리스, 활성 AI 정책, 전체 카드·캐릭터(번역 포함),
   두 캐릭터의 자동 모드용 공개 덱 몇 개를 **읽기만** 해서 `.temp/play-dev/bundle.json`으로 내보낸다.
   이미 있으면 건너뛰고, `-Refresh`를 주면 다시 내보낸다. `-P1`, `-P2`로 캐릭터를 바꾼다.
2. `scripts/serve_play_dev.py`가 테스트 설정으로 `.temp/play-dev/play.sqlite`에 마이그레이션하고 묶음을 넣은 뒤
   Daphne를 띄운다. 연결된 DB가 그 SQLite 파일이 아니면 시작하지 않는다. `-Reset`은 SQLite를 새로 만든다.
3. Vite(5175)를 거친 POST가 CSRF 출처 검사를 통과하도록 `CSRF_TRUSTED_ORIGINS`에 Vite 주소를 넣는다(개발 서버에서만).

로비는 실제 사이트와 같은 API(`/battlelog/play/api/`)를 쓴다. 개발 서버에만 있는 `GET /play-dev/login/`은
개발 덱의 주인으로 로그인시켜 "내 덱"에 덱이 보이게 한다. 덱은 실제 공개 덱을 새 형식(특성 지정)으로 복사하므로
대전 전에 덱 준비 단계를 거친다. 캐릭터마다 교체 덱과 교체 한도(기술 2·특성 1·얼티밋 1)가 있는 "(교체 시험)" 덱도 하나씩 만든다.

클라이언트 주소:

| 주소 | 화면 |
|---|---|
| `/` | 새 대전 만들기(로비) |
| `/?game=<view_token>&seat=p1&token=<seat_token>` | 대전. 좌석을 빼면 관전 |
| `/?fixtures#step=3&role=p1` | 픽스처 보기 |
| 위 주소 + `&device=phone` | 기기 크기 미리보기(`phone`, `phone-land`, `tablet`, `laptop`) |

### 클라이언트 연결 동작 (`play/src/net/live.ts`)

- 접속하면 `log_subscribe`로 이벤트를 받기 시작한다. 끊기면 0.5초부터 최대 10초 간격으로 다시 붙고,
  다시 붙으면 서버가 보내는 `state`로 그대로 이어 간다.
- 명령을 보내면 그 `expected_version`보다 새 상태가 올 때까지 조작을 막는다(같은 행동을 두 번 보내지 않도록).
  15초 안에 오지 않으면 상태를 다시 요청한다.
- `stale_state`·`illegal_action`은 안내만 띄우고 최신 상태로 갱신한다. `automatic_fallback`이나
  `mode`가 `automatic`이 아닌 상태는 대전 중단 화면을 띄운다.
- 보이는 카드의 `card_id` 중 카탈로그에 없는 것만 `card-metadata`로 받는다.

### 사람 대 사람, 타이머, 재접속

- **초대**: 로비에서 "사람과 대전"을 고르면 상대 좌석 주소와 관전 주소를 보여 준다. 대전 중에는 P1의 메뉴에서
  상대 좌석 주소(envelope의 `player2_url`을 새 클라이언트 주소로 바꾼 것)와 관전 주소를 복사할 수 있다.
  관전은 `?game=<view_token>`만으로 열린다.
- **타이머**: 사람과 대전할 때 기본은 레디 30초, 효과 선택 60초다(로비에서 15~120초 또는 제한 없음).
  `clocks`로 누구의 어떤 타이머인지와 남은 초를 보여 주고, 10초 이하면 붉게 깜빡인다.
  서버는 시간 초과를 읽기·명령 때 정산하므로, 클라이언트가 마감 0.4초 뒤 `state`를 요청해 정산을 일으킨다.
  시계 차이로 아직이면 2초 뒤 다시 묻는다.
- **정산 알림**: 좌석의 `state` 요청에서 타이머 정산이나 AI 진행으로 버전이 오르면 consumer가 그룹 전체에
  `state_dirty`를 보낸다. 그래서 상대와 관전자도 바로 따라온다(`PlayClockBroadcastTests`).
- **시스템 행동**(`ui.kind = system`)은 메뉴에 모은다.
  - `pause_clock`: 상대 타이머만 멈출 수 있고 `selections.reason`이 필요하다. 사유는 버튼으로 고른다.
  - `resume_clock`: 일시정지 중에는 보드 가운데 안내에 "재개" 버튼이 나온다. 양쪽 모두 누를 수 있다.
  - `request_rewind` / `answer_rewind`: 상대가 요청하면 수락·거절 창을 띄운다. 현재 서버 설정(`AUTOMATIC_REWIND_ENABLED`)은 꺼져 있다.
  - `concede`: 한 번 더 확인한 뒤 보낸다.
- **접속 표시**: 서버의 `presence {p1, p2, viewer}`로 사람 상대의 접속 여부("상대 접속 중", "상대 연결 끊김")와 관전 인원을 보여 준다.
- **재접속**: 끊기면 백오프로 다시 붙는 것에 더해, 탭으로 돌아올 때(`visibilitychange`)와 네트워크가
  돌아올 때(`online`)는 기다리지 않고 바로 붙거나 상태를 다시 받는다.
- **이어하기**: 진행 중인 좌석을 브라우저에 저장해 두고, 로비에서 "이어하기"로 다시 연다. 대전이 끝나면 지운다.

### 화면 조작

- **카드 누르기**: PC는 카드를 선택해 카드 위에 사용 버튼(`SelectionPopover`)을, 화면 왼쪽에 카드 정보(`CardSidePanel`)를 띄운다.
  좁은 화면(세로 또는 760px 이하)은 정보와 버튼이 든 모달(`CardInspector`)을 연다. 빈 곳이나 Esc로 선택을 푼다.
- **콤보 끌어 놓기**: 1콤보 카드를 배틀 존에 놓으면(`select_combo_first`) 서버는 2콤보 카드를 받을 때까지 그 카드를 손패에 둔다.
  화면은 그동안 그 카드를 배틀 존에 노란 테두리로 놓아 두고(`stageCombo`), 손패로 끌거나 누르면 `cancel_combo_first`로 다시 고른다.
  2콤보 카드를 배틀 존에 놓으면 `select_combo_followup`으로 두 장을 함께 제시한다. 엔진은 제시된 1·2콤보 카드를 모두 배틀 존에 놓은 뒤
  각각의 효과를 처리하고(`_present_combo_cards`), 쓰지 못한 채 콤보가 끝난 카드는 원래 존으로 되돌린다.
  보드의 카드 행동은 instance id로 찾는다(`cardActions`): 화면에서만 옮겨 둔 카드 때문에 같은 존의 위치가 서버와 달라질 수 있다.
- 놓은 카드는 항상 원래 자리로 되돌아가는 애니메이션을 한다(상태가 바뀌면 새 자리로 옮겨 간다). 놓아도 상태가 그대로면(거절 등) 놓은 자리에 남던 문제를 막는다.
- **카드 우클릭**: 카드 정보만 보여 준다. PC는 사용 버튼 없이 왼쪽 정보 패널(`CardSidePanel`, 상태 `peek`)을, 좁은 화면은 카드 정보 모달을 연다.
  보드·더미 패널·선택 창·더미 목록의 공개 카드 어디서나 되며, Esc·닫기·다른 카드 선택으로 닫힌다.
- **끌어 놓기** (`play/src/dragMoves.ts`, `components/DragMask.tsx`): 카드를 출발 영역(A) 밖으로 끌면 A들과 도착 영역(B)만 남기고
  어둡게 덮고 B에 영역 이름을 적는다. B에 놓으면 항상 그 영역으로 옮기는 행동을 실행한다(같은 B로 가는 행동이 여럿이면 카드를 선택해 고른다).
  - 자동 판정의 B: 레디·캐치·콤보 → 내 배틀 존, 겟(리스트·얼티밋) → 내 손패, 효과 선택 → 서버가 준 `option.ui.to_zone`.
    엔진은 선택 요청의 이어지는 처리에서 도착 존을 찾아 힌트로 붙인다(`_decision_destination`: 버리기 → 리스트, 브레이크 → 브레이크 존,
    `move_card`의 `to_zone`, 사이드 보충 `break_replenish` → 리스트, 레디 강제 `force_ready` → 배틀 존,
    비용 선택 `play_cost`·`defense_cost`·`combo_speed_cost`·`battle_reveal_play_cost`의 비용 동작). 버리기는 카드마다 정한다(특수 기술 → 브레이크 존, 그 밖 → 리스트). 힌트가 없는 선택은 누르기로만 고른다.
  - B가 하나면 같은 B로 갈 수 있는 카드가 있는 다른 영역도 A로 함께 열어 둔다(예: 겟의 리스트와 얼티밋 존).
  - B가 여럿이면(수동 모드: 내 모든 존과 상대 배틀·루멘) 각 B를 14px씩 키워 놓기 쉽게 하고, 놓는 범위도 같이 넓힌다.
    작은 영역(더미)에는 짧은 이름을 작게 쓴다.
  - 놓을 자리는 `data-drop-owner`·`data-drop-zone` 표식이 있는 요소(배틀 존, 리스트, 손패, 더미)다.
  - **카드 옮기기 선택**: 모든 선택지가 카드이고 도착 존을 아는 효과 선택(예: 손패 제한 버리기 → 리스트, 효과로 카드 이동)은
    선택 창 없이 보드에서 끌어 옮긴다(`movesOnBoard`). 출발 영역에 빨간 테두리와 "N From"(N: 옮겨야 할 장 수, 범위면 `최소~최대`),
    도착 영역에 파란 테두리와 "M To"(M: 지금까지 옮긴 장 수)를 오른쪽 위에 붙인다(`components/DecisionFrames.tsx`).
    옮긴 카드는 서버에 보내지 않고 화면에서만 도착 존으로 옮겨(`stageDecision`) 노란 테두리로 표시한다. 다시 원래 영역으로 끌거나
    눌러서 되돌릴 수 있고, 위쪽 안내의 "모두 되돌리기"로 한꺼번에 되돌린다. 고를 수를 채우면 안내나 오른쪽 아래의 "확정"으로 보낸다.
    카드가 아닌 선택지(예: 사이드 보충의 "보충하지 않음")는 위쪽 안내의 버튼으로 바로 보낸다.
    "목록으로 보기"로 예전 선택 창을 열 수도 있다.
  - **더미 펼치기** (`components/ZoneDock.tsx`): 장 수만 보이는 더미(루멘·브레이크·얼티밋·사이드)가 출발이나 도착이면
    그 더미의 카드를 펼친 패널을 띄운다. 더미가 여럿이면 더미마다 같은 크기의 패널을 따로 놓고, From/To 테두리와 이름표가 겹치지 않게 띄운다.
    PC는 왼쪽 빈 곳에 위아래로, 모바일은 상대 필드 아래쪽(가운데 줄 바로 위)에 좌우로 나눈다.
    패널도 그 영역의 놓을 자리이고 더미 버튼에 놓아도 된다(같은 영역 요소가 여럿이면 놓기 판정은 모두 쓰고 테두리는 가장 큰 요소에 그린다:
    `zoneRects`/`zoneRect`). 패널 안의 후보 카드는 바로 끌어 꺼낼 수 있다. 카드 옮기기 선택 중에는 계속, 그 밖에는 카드를 끄는 동안
    도착 더미가 2개 이하일 때만 펼친다(수동 모드처럼 도착이 많으면 펼치지 않는다). "가리기"로 접으면 왼쪽 가장자리의 "펼치기" 탭만 남고,
    새 선택이 오면 다시 펼친다.
- **고를 수 없는 선택지**: 효과 분기(`choose_effect`)에서 대상이 없거나 다른 효과에 막혀(`selector_available` 미충족) 고를 수 없는
  선택지는 `pending_decision.unavailable_options`(`id`, `label`, `reason`)로 따로 온다. 선택 창 아래 "고를 수 없음"에 흐리게
  이유와 함께 보여 준다(예: "「프로토콜: 익시드」 효과로 브레이크할 수 없습니다."). 제출 검증과 AI는 `options`만 보므로 고를 수는 없다.
- **효과 선택**: 후보를 출처 존별로 묶어 보여 준다(예: "내 손패", "상대 리스트"). "보드에서 고르기"로 창을 접으면
  보드의 후보 카드(더미 안의 후보는 더미)가 빛나고, 보드나 더미 목록에서 눌러 고른 뒤 오른쪽 아래 버튼으로 확정한다.
- **리스트**: 6장까지 1줄, 12장까지 2줄, 그 이상 3줄 격자로 놓고 줄이 늘면 카드를 줄인다.
- **패시브**: 초상에 모든 카운터(상한이 있으면 n/상한)와 상태(꺼짐은 흐리게)를 보여 준다(`play/src/passives.ts`).
  수동 모드는 캐릭터 설정·전용 패널의 기본값으로 아직 바뀌지 않은 값도 채우고, 자동 판정은 엔진의 `passive_state`만 쓴다.
- **겟 페이즈**: 종합 규칙 4.5.3에 따라 손패가 패 매수 상한 미만이면 "획득하지 않음"이 없다(엔진 `legal_actions`).
  가져올 카드가 없으면(4.5.5) 넘길 수 있다.

### 내 행동 즉시 반영 (`play/src/net/optimistic.ts`)

행동을 보내는 순간 결과를 예측해 화면에 먼저 반영한다. 끌어 놓은 카드는 원래 자리로 돌아가지 않고 바로 도착 영역에 놓인다.

- 예측하는 것: 카드 이동(레디 → 배틀 존 뒷면, 캐치·콤보 → 배틀 존, 겟 → 손패, 효과 선택 → `ui.to_zone`),
  선택 창 닫기, 수동 모드의 `move_card`·`set_visibility`·`hp`·`fp`·`fp_reset`·`passive`·`set_phase`.
  규칙 판정이 필요한 결과(데미지, 효과)는 예측하지 않고 서버 결과를 기다린다.
- 예측은 서버가 그 요청을 받았다고 알릴 때(`command_ack`·`action_ack`)까지 유지한다. 그 뒤에 오는 서버 상태가
  진짜 결과로 대신한다. 서버 상태를 화면에 올릴 때마다 아직 확인되지 않은 예측을 다시 얹는다(`withPending`).
  그래서 수동 모드에서 행동을 빠르게 여러 번 해도 앞의 응답이 뒤의 예측을 지우지 않는다.
- 거절(`error`)되거나 15초 안에 응답이 없으면 그 예측을 버리고 마지막 서버 상태로 되돌린다.
- 예측 상태에서는 행동 목록을 비워 같은 행동을 두 번 보내지 않게 한다.
- 놓은 위치는 포인터 이벤트의 화면 좌표로 읽는다. motion의 `info.point`는 화면 갱신이 늦을 때 실제로 놓은 곳과 어긋날 수 있다.

### 이벤트 재생 (`play/src/anim/playback.ts`)

서버는 행동 하나와 이어지는 AI 행동까지 끝난 **최종 상태**만 보낸다. 클라이언트는 화면에 보이는 상태에
새 이벤트를 하나씩 적용한 중간 상태를 차례로 그리고, 마지막에 서버 상태로 맞춘다.
중간 상태는 화면용이라 조금 틀려도 마지막 맞춤에서 바로잡힌다. 재생 중에는 행동을 비워 조작을 막는다.

- 기준은 보이는 envelope의 `event_count`(반영된 마지막 이벤트 `seq`)다. 그보다 큰 `seq`만 재생한다.
- 상태가 이벤트보다 먼저 오면 이벤트를 최대 1.5초 기다린다.
- 밀린 이벤트가 40개를 넘으면 4배속, 160개를 넘으면(오래 끊겼다 재접속한 경우 등) 바로 최종 상태로 간다.
- 첫 접속, 시점 전환, 수동 모드 전환은 연출 없이 바로 보여 준다.

| 이벤트 | 화면 |
|---|---|
| `phase_started` | 페이즈 배너(턴이 바뀌면 턴 번호 포함) |
| `card_moved`, 비공개 `card_moved` | 카드를 출발 존에서 도착 존으로 옮긴다. 비공개면 뒷면 카드를 옮긴다 |
| `battle_revealed` | 상대 배틀 카드를 뒤집어 공개한다 |
| `battle_judged` | 내 판정 결과 배너(히트·가드·카운터 등)와 양쪽 속도 |
| `hp_changed`, `fp_changed` | 초상 위 숫자, HP 바 변화, 피격 시 흔들림 |
| `effect_resolved` | 발동한 카드와 효과문 띠(내 효과는 손패 위, 상대 효과는 화면 위) |
| `combo_started`, `catch_started` | "콤보!", "캐치!" 배너 |

연출 속도(×1, ×2)는 대전 화면 위 칩으로 바꾸고 브라우저에 저장된다. 카드 이동이 보이지 않으면 게임을 따라갈 수 없어서 연출은 끌 수 없다(예전에 저장한 "끔"은 ×1로 읽는다). 같은 이유로 재생 중 건너뛰기도 두지 않는다.
픽스처 보기에서도 바로 다음 단계로 넘어갈 때 그 사이 이벤트를 같은 방식으로 재생한다.

## 픽스처

서버 없이 화면을 만들 수 있도록, 계약 테스트가 진행한 대전의 각 단계를 역할별 envelope로 저장한다.

```powershell
.\scripts\export-play-fixtures.ps1
```

1. `manage.py export_play_sample`이 설정된 DB에서 캐릭터 두 명과 그 카드 일부를 **읽기만** 해서
   `play/fixtures/source/sample.json`으로 내보낸다. 기본은 루트(3) 대 니아(2)이고 `-P1`, `-P2`로 바꾼다.
2. 계약 테스트가 그 카드로 인메모리 SQLite에서 대전을 진행하며 각 단계를 저장한다.

결과물:

- `play/fixtures/step-NN-<phase>-<step>.json`: 파일마다 `{p1, p2, viewer}` envelope
- `play/fixtures/cards.json`: `card-metadata` 응답과 같은 형태의 카드 카탈로그(실제 이미지 URL 포함)

DB 없이 만들려면 `-Synthetic`을 붙인다(이미지 없는 합성 카드). 생성물이라 커밋하지 않는다.

시나리오의 카드 효과는 비워 두어 진행이 결정적이다. 이름·수치·효과문·이미지만 실제 카드에서 온다.
루멘 → 레디 → (배틀 자동 판정) → 획득 → 회복을 반복하며, 콤보·캐치·효과 선택 장면은
효과 정의를 켠 시나리오를 따로 만들어야 나온다.
