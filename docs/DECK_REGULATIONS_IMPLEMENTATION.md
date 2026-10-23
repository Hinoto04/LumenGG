# 특성 선택·대회 규정·교체 덱

웹, 모바일 앱, 계산기, 수동·자동 시뮬레이터와 대회 제출에 특성 선택과 교체 덱을 연결했다. 기존 CB02 카탈로그·현지화 작업은 보존했다.

## 사용자 동작

- 덱 작성에서 특성, 적용 규정, 별도의 교체 덱을 선택한다. 편성 위반이 있는 초안도 저장할 수 있다. 특성 변경 시 기술 카드를 삭제하지 않는다.
- 열람·공유 이미지·복사·JSON 가져오기/내보내기에 특성과 교체 덱을 포함한다. 목록에서 특성과 규정으로 검색한다.
- 규정 관리에서 공통 규정을 복사하거나 소유 규정의 새 버전을 게시한다. 금지·제한마다 전체 등록 구성(`registered`) 또는 게임 사용 구성(`active`)을 선택한다.
- 대회 제출은 원본 덱과 분리된 스냅샷이다. 접수 중 규정 변경 시 제출을 재검증하고, 시작 시 필수 제출·적합성을 확인한다. 시작 후 규정 변경을 거절한다. 제출이 필수가 아닌 대회는 미검사로 표시한다.
- 대회 계산기는 제출 번호로 덱을 선택하며 같은 캐릭터도 특성명으로 구분한다. 일반 계산기는 캐릭터 다음에 특성을 선택한다.
- 첫 게임과 다음 게임 준비에서 등록 기본 구성으로 복귀한다. 양쪽 준비 완료 시 게임을 한 번 초기화한다. 양쪽 완료 전에는 철회할 수 있다. AI는 기본 구성으로 준비한다.
- 교체 후보는 본인과 대회 운영자에게만 제공한다. 공개 규정에서도 확정 전 선택은 숨긴다. 확정 후 조합 공개에도 시작 패·사이드 배치를 포함하지 않는다.

## 데이터와 판정

`Card.trait_config`가 선택한 특성의 계산기 UI·초기 상태·준비 보정값을 가진다. 편성 예외는 기존 특성 카드의 `effect_definition.deck_rules`를 사용한다. 캐릭터 공통 예외는 `Character.datas.base_deck_rules`를 사용한다. 선택하지 않은 특성의 규칙·컨트롤은 합치지 않는다.

특성 설정 예시:

```json
{
  "initial_hp": 5000,
  "hand": {"5000": 5, "2500": 4},
  "initial_passive_state": {"charge": {"count": 2}},
  "battle_passive_ui": {
    "options": {
      "controls": [{"type": "counter", "key": "charge", "label": "차지", "initial": 2, "min": 0}]
    }
  },
  "supports_shield": false
}
```

이관한 기존 단일 특성에는 `legacy_character_actions: true`를 설정해 전용 UI를 유지한다. 새 특성은 선택한 설정의 일반 컨트롤을 사용하며 서버도 허용 키를 검사한다. 초기 상태와 캐릭터·특성 설정을 세션에 보존해 이후 카탈로그 변경이 진행 중 계산기에 적용되지 않는다.

덱 저장의 추가 필드:

```json
{
  "schema_version": 2,
  "trait_card_id": 101,
  "regulation_version_id": 1,
  "reserve_cards": [{"card_id": 102, "count": 1}]
}
```

기존 `cards[].count/hand/side`와 덱 `version`의 의미는 유지한다. 교체 덱은 `ReserveCardInDeck`에 별도 저장하고 게임 영역에 넣지 않는다. 재록은 기존 `CollectionCard.card`의 원본 연결을 사용한다. 동명 제한은 번역되지 않은 원문 카드명을 기준으로 한다.

규정 기본값은 아래와 같다. 교체를 허용하려면 유형별 한도를 모두 명시해야 한다. 특성·얼티밋 한도는 각각 0 또는 1이다.

```json
{
  "bans": [], "combinations": [],
  "reserve_limit": 0,
  "technique_swap_limit": 0, "trait_swap_limit": 0, "ultimate_swap_limit": 0,
  "reserve_public": false, "swaps_public": false
}
```

금지·조합 항목은 `{"card_ids": [123, 456], "scope": "registered"}` 형식이다. 금지는 목록 중 하나가 있으면, 제한 조합은 목록 카드가 함께 있으면 위반이다. 특성의 편성 예외가 대회 금지를 해제하지 않는다.

공통 서버 판정기는 `deck/validation.py`, 기술 편성 판정기는 `deck/game_validation.py`다.

| 단계 | 판정 |
| --- | --- |
| `draft` | 참조·수량·배치 데이터 오류는 거절하고 편성 위반은 경고로 반환 |
| `registration` | 기본 편성, 교체 등록 한도, 금지·조합 제한 |
| `replacement` | 등록 수량 보존, 고정 캐릭터, 유형별 한도, 변경 특성의 편성 |
| `setup` | 위 항목과 시작 패·리스트·특수 기술·얼티밋 배치 |

기술 교체 매수는 기본 대비 추가 매수와 제거 매수 중 큰 값이다. 특성 변경으로 기술 매수가 줄어도 제거 매수가 계산된다. 결과는 `stage`, `regulation_version_id`, `is_valid`, `swap_counts`, `issues[]`이며 문제는 `code`, `severity`, `card_ids`, `message`를 가진다.

웹의 빠른 검사는 서버 초안 검사, 앱 오프라인 검사는 `mobile/src/deck-rules.ts`를 사용한다. Python·TypeScript가 같은 `LumenGG/content/deck-validation-cases.json` 사례를 검사한다. 대회 제출·준비 확정의 최종 기준은 서버다.

## API와 화면

| 경로 | 용도 |
| --- | --- |
| `GET /deck/options?deck_id=…` | 특성·선택값·접근 가능한 규정·교체 후보 |
| `GET/POST /deck/regulations` | 규정 조회·소유 규정 생성·새 버전 게시 |
| `POST /deck/validate` | `deck_id`, `stage`, 선택적 `active` 또는 초안 `candidate` 검사 |
| `/deck/regulations/manage` | 웹 규정 작성·복사·게시 |
| `/deck/export/<id>`, `/deck/import/v2` | 권한을 검사하는 JSON 교환 |
| 대회 화면의 제출 기록 링크 | 당시 스냅샷 열람과 현재 규정 비교 |
| `POST /battlelog/simulator/<view_token>/preparation/` | 시뮬레이터 준비 명령 |
| 계산기 기존 action API | `action: "preparation"` 대회 준비 명령 |

모바일은 기존 `/api/mobile/v1/` URL을 유지한다. `regulations`, `deck-options`, `deck-validation`, `submitted-decks/<submission_id>`를 추가했다. 카탈로그와 덱의 데이터 스키마 2는 URL 버전과 별개다. 규정 API는 웹 세션과 앱 JWT 인증을 모두 지원한다.

준비 명령은 `save`, `ready`, `cancel`, `select_deck`(대회 계산기), `next_game`이다. `preparation_action`, UUID `request_id`, 최신 `expected_version`, `active`를 보낸다. 시뮬레이터는 `seat`/`seat_token`으로 좌석을 검사한다. 모바일 계산기는 전송용 세션 버전과 별도로 `preparation_version`을 보낸다. 참가자·운영자 권한, stale 버전, UUID 재사용을 검사하며 동일 요청 재전송은 중복 초기화하지 않는다.

## 이관과 배포

구현 과정에서는 운영 DB 이관, 서버 카탈로그 게시, 앱 스토어 배포를 실행하지 않았다. 아래는 배포 환경에서 수행할 순서다.

1. 백업 후 서버 배포와 `python manage.py migrate`를 실행한다. nullable 필드, 교체 항목, 규정·제출 스냅샷·준비 상태가 추가된다.
2. 이관은 단일 특성 캐릭터의 기존 덱만 자동 연결한다. 여러 특성의 선택을 확정할 근거가 없으면 미지정으로 남긴다. 새 제출·새 대전에서는 선택해야 한다. 단일 특성의 기존 UI·초기 상태도 특성 설정으로 복사한다.
3. 특성별 설정을 확인한 뒤 `python manage.py validate_automatic_ruleset`과 `python manage.py publish_automatic_ruleset <새 버전>`으로 효과 릴리스를 검증·게시한다. 기존 게시 릴리스와 진행 중 대전은 유지한다. 대회 규정 버전과 효과 릴리스는 독립적이다.
4. `python manage.py publish_mobile_catalog --schema-version 2`로 앱용 카탈로그를 게시한다. 기존 활성 스키마 1은 유지된다. 필요하면 별도로 `--schema-version 1`을 게시할 수 있다.
5. 앱 1.1.0(Android versionCode 10)을 배포한다. 번들 시드는 스키마 2다. 구형 요청으로 새 형식 덱을 수정하면 서버가 거절해 특성·교체 덱 삭제를 막는다.
6. 확인된 대회 규정의 금지 목록·한도를 입력한다. 초기 공통 규정에는 금지·제한이 없고 교체 한도는 0이다.

웹 모델 재생성은 루트에서 `node scripts/build_deck_models.cjs`를 실행한다. `mobile/scripts/upgrade-seed-catalog.py`는 로컬 번들 시드 보정 도구이며 서버 게시를 대신하지 않는다.

운영 오류는 검증 문제 코드, `preparation_invalid`/`preparation_forbidden`, stale 버전·구버전 동기화 거절로 구분한다. 비공개 후보·교체 내용은 공개 응답·이벤트·로그에 넣지 않는다.

## 검증 기록

- Django 전체 회귀 검사 1,297개 통과. 이후 제출이 필수가 아닌 대회의 미검사 처리를 포함한 추가 회귀 검사 8개 통과.
- 앱 타입 검사와 테스트 93개 통과. 공통 사례는 등록/사용 범위, 실제 금지 조합 교체, 특성 변경에 따른 기술 증감, 얼티밋 배치, 구형 특성 코드를 포함한다.
- Django 시스템 검사와 마이그레이션 누락 검사 통과.
- Android·iOS Metro/Hermes 번들 내보내기 통과. 실제 기기 설치·스토어 배포는 별도다.
- 격리 로컬 DB·브라우저에서 데스크톱·모바일 웹 작성, 특성 변경 저장, 교체 영역, 양쪽 준비 완료 후 시작, 같은 캐릭터의 다른 특성 UI를 확인했다. 해당 화면에 콘솔 오류·가로 넘침이 없었다.

서버 검사는 `.venv/Scripts/python.exe`와 `--settings=LumenGG.test_settings`를 사용했다. 로컬 리뷰 서버 `scripts/serve_deck_review.py`는 별도 `.temp` DB를 사용한다.
