# LumenGG

카드게임 루멘콘덴서의 데이터베이스·플레이 도구 사이트(`lumen.hinoto.kr`)와 모바일 앱(LumenDB).
사용자와의 대화, 문서, 커밋 메시지는 한국어로 작성한다.

## 구조

- `LumenGG/` — Django 5.1 백엔드 (DRF + SimpleJWT, Channels/Daphne WebSocket, Redis, MySQL/MariaDB)
  - `card` 카드·캐릭터, 자동 효과 DSL 정의와 관리자 검수 에디터
  - `deck` 덱 빌더·레귤레이션 검증 / `collection` 수집 / `qna` 공식 재정
  - `statistic`, `tournament` 대회 통계·운영
  - `common` 다국어(ko/en/ja), 룰북(`/rules/`), 사이트 설정
  - `battlelog` HP/FP 대전 계산기(실시간 공유), 자동 판정 시뮬레이터·AI(`battlelog/game/`), 루멘 파티(`party_*`, 문서 `content/PARTY.md`)
  - `mobile_api` 앱용 API `/api/mobile/v1/`, 오프라인 카탈로그 배포
- `mobile/` — Expo SDK 57 / React Native / TypeScript / expo-router 앱. 자세한 내용은 `mobile/README.md`
- `scripts/` — 계산기 에셋 빌드 및 웹·Android 시각 검증 스크립트
- `docs/`, `MOBILE_IMPLEMENTATION.md`, `TESTING.md` — 기능별 설계·배포·테스트 문서

## 명령

Python은 루트 `.venv`를 쓰고, 의존성은 `LumenGG/requirements.txt`를 기준으로 한다(루트 `requirements.txt`는 예전 버전).

```powershell
.\test.ps1                                   # 인메모리 SQLite 회귀 테스트
.\test.ps1 -TestLabel battlelog.test_party   # 범위를 좁혀 실행
cd LumenGG; ..\.venv\Scripts\python.exe manage.py test <label> --settings=LumenGG.test_settings
cd mobile; npm run typecheck; npm test
```

MariaDB 호환성 확인: `docker compose -f compose.test.yml up -d --wait`, `.\test.ps1 -Database mariadb`

## 자동 효과 엔진 (`battlelog/game/`)

- 흐름: 카드 텍스트 → `drafts.py`가 DSL 초안 생성 → `review.py`가 결정적 시나리오로 자동 검수 → 운영진이 관리자 화면에서 수동 검수 → `publish_automatic_ruleset`으로 변경 불가 릴리스. 모든 카드가 통과해야 자동 모드가 공개된다.
- `review.py`(약 15만 줄), `drafts.py`(약 3만 줄), `engine.py`(약 1만 줄)는 매우 크다. 통째로 읽지 말고 Grep으로 필요한 부분만 찾는다.
- 수동 검수된 정의는 덮어쓰지 않는다. 시드 명령은 먼저 `--dry-run`으로 확인한다.
- 룰 해석이 불확실한 항목은 코드로 단정하지 않는다. `AUTOMATIC_EFFECT_RULE_QUESTIONS_KO.txt`에 질문으로 기록하고, 검증 근거는 `AUTOMATIC_EFFECT_BROWSER_REVIEW_KO.md`에 누적한다.
- 카드 동작은 공식 Q&A 번호를 근거로 삼고 테스트에 반영한다.

## 주의

- DB 접속 정보는 `LumenGG/SECRET_KEYS.py`(커밋 금지)에 있다. 로컬 개발 DB가 운영 DB일 수 있으므로 `migrate`, `--apply`, `publish_*`, 데이터 수정 명령은 실행 전에 반드시 사용자에게 확인한다.
- 스키마를 바꾸면 마이그레이션을 추가한다. 앱 API를 바꿀 때는 이미 배포된 앱 버전과의 호환성(필드 추가 위주)을 고려한다.
- 루트의 엑셀 파일(`카드DB.xlsx`, QNA 등)은 원본 자료이므로 수정하지 않는다.

## 커밋

한국어 conventional 형식을 쓴다. 예: `feat(party): ...`, `fix(calculator): ...`, `test(...)`, `chore: ...`. 릴리스 커밋은 버전 번호만 적는다(예: `2.1.2`).
