# 자동 효과 검토 병렬 작업 규칙

최종 갱신: 2026-08-21 (Asia/Seoul)

현재 카드·브랜치 예약은 `PARALLEL_SESSION_START_HERE.md`를 단일 기준으로 삼는다.
이 문서는 세션 간 충돌을 막는 공통 계약만 설명한다.

## 현재 상태

PMP와 CB01 병렬 결과 및 마지막 `CB01-AT-006/009/022/025` 구현까지 메인
소스에 통합했다. 자동 엔진 803개와 전체 프로젝트 912개 SQLite 테스트가
통과했다.

운영 DB를 수정하지 않은 일반 전체 카탈로그 드라이런은 451/453장이다.
제외된 `ST1-011/012`는 정의가 아니라 저장된 과거 증거만 낡았고, 읽기 전용
`--rebuild-reviewed` 검토에서는 전체 453/453장이 통과한다. 현재 새 카드 예약은
없으며, 구체적인 최신 상태는 항상 `PARALLEL_SESSION_START_HERE.md`를 우선한다.

완료된 산출물은 다시 배정하지 않는다. 동일 카드의 늦은 산출물이 발견되면 두
구현을 함께 합치지 않고 정의와 시나리오를 비교해 하나만 채택한다.

## 소유권

통합 세션만 다음 범위를 수정한다.

- `C:\Hinoto\LumenGG`의 dirty `main`
- 공통 `engine.py`, `schema.py`, `effects.py`, `spec.py`
- 모델, 마이그레이션, API, WebSocket, JavaScript, 템플릿
- `TESTING.md`와 모든 집계·인수인계 문서
- 보조 결과 통합과 최종 전체 회귀

각 보조 세션은 자기 worktree에서 예약 카드 전용 블록만 다음 세 파일에 추가한다.

- `LumenGG/battlelog/game/drafts.py`
- `LumenGG/battlelog/game/review.py`
- `LumenGG/battlelog/test_automatic_engine.py`

공통 엔진 지원이 필요하면 직접 변경하지 않는다. 최소 실패 시나리오, 현재 상태,
필요한 DSL/인터페이스를 완료 보고에 남겨 통합 세션이 먼저 공통 변경을 검증한다.

## 카드 완료 조건

1. 운영 DB에서 카드 원문, `detail_text`, 연결 Q&A를 읽기 전용으로 확인한다.
2. 최신 에라타·보충 설명 > 카드별 Q&A > 카드 문구 > 룰북 > 일반 Q&A 순으로
   해석한다.
3. 카드의 각 능력 그룹에 최소 3개의 결정적 시나리오를 둔다.
4. 양쪽 소유자, 성공, 경계/실패, 번호 효과 무효를 검증한다.
5. 대상을 특정하지 않은 강제 획득·브레이크·버리기·이동은 실제
   `pending_decision`을 만들고 합법 후보에서 플레이어가 선택하게 한다.
6. 선택 후보 없음, 복수 후보, 선택 후 보호/무효화와 후속 효과의 성공 의존성을
   필요한 카드에서 검증한다.
7. 표시용 메타데이터만 존재하는 것으로 검토 완료하지 않고 실제 엔진 상태와 합법
   행동 변화를 확인한다.
8. 카드별 읽기 전용 드라이런, 전체 자동 엔진 SQLite 테스트와
   `git diff --check`를 통과한다.
9. 판단하기 어려운 재정은 추측하지 않고 검토 필요 상태로 남긴다.

## Git과 환경 규칙

1. 같은 worktree를 두 세션이 동시에 사용하지 않는다.
2. 예약 카드마다 커밋 하나를 만들며 예약 밖 카드를 선점하지 않는다.
3. 보조 세션은 다른 worktree나 메인 브랜치를 수정·스테이징·커밋하지 않는다.
4. `git add -A`, `git pull`, `merge`, `rebase`, `stash`, 전체 파일 교체와 대량
   포맷팅을 하지 않는다.
5. 운영 DB에서 `--apply`, seed, publish, 마이그레이션을 실행하지 않는다.
6. SQLite 테스트는 병렬로 실행할 수 있다. MariaDB 테스트는 세션별로 고유한 테스트
   DB 이름을 쓰지 않는 한 동시에 실행하지 않는다.
7. 개발 서버는 메인 8000, 보조 8001/8002처럼 포트를 분리한다.
8. `.temp`, `test.local.ps1`, `SECRET_KEYS.py`, DB 자격 증명은 복사·커밋·채팅
   공유하지 않는다.
9. 문서와 집계 수치는 통합 세션만 갱신한다.

## 보조 세션 검증 예시

카드 코드는 자기 예약 카드로 바꾼다. `--apply`를 붙이지 않는다.

```powershell
cd <자기-worktree>\LumenGG

python manage.py review_automatic_effect_drafts `
  --card-code CRS-AT-006 --verbose

python -m py_compile battlelog/game/drafts.py `
  battlelog/game/review.py battlelog/test_automatic_engine.py

$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput

cd ..
git diff --check
git status --short
```

완료 시 허용된 실제 변경 파일만 스테이징하고 카드별 커밋을 만든다.

## 통합 규칙

메인 worktree가 대규모 dirty 상태이므로 그 자리에서 보조 브랜치를 무조건
`cherry-pick`하지 않는다. 통합자는 커밋별 diff를 확인하고 다음 세 파일의 카드
전용 블록과 디스패처 등록만 수동 병합할 수 있다. 한쪽 파일 전체를 선택하지 않는다.

통합 후에는 다음을 확인한다.

1. 카드별 읽기 전용 드라이런
2. 추가된 집중 테스트
3. 자동 엔진 SQLite 전체 테스트
4. 전체 프로젝트 SQLite 회귀
5. `review_automatic_effect_drafts --verbose` 전체 카탈로그 드라이런
6. `git diff --check`와 중복 테스트 클래스/함수 검사

운영 DB 적용과 ruleset 게시는 별도 사용자 승인 및 전체 카탈로그 완료 조건을 따른다.

## 완료 보고 형식

```text
카드/작업:
기준 HEAD와 작업 브랜치:
해석 요약:
변경 파일:
능력 그룹/결정적 시나리오 수:
카드별 읽기 전용 드라이런:
SQLite 자동 엔진 테스트:
git diff --check:
커밋 해시:
남은 재정 의문:
필요한 공통 엔진 변경:
```
