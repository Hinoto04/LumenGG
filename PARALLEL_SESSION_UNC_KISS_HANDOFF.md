# UNC Kiss 자동 효과 검토 세션 인수인계

> 완료/보존 문서: `UNC-AT-026/027/028`의 카드별 커밋 `eb1b5a5`,
> `aa6a626`, `3ddf89f`는 2026-08-20 메인에 통합됐다. 같은 worktree의 현재
> 작업은 `PARALLEL_SESSION_CRS_006_008_HANDOFF.md`를 따른다.

최종 확인: 2026-08-20 (Asia/Seoul)

## 작업 계약

- 유일한 작업 루트: `C:\Hinoto\LumenGG-review-unc-kiss`
- 브랜치: `review/unc-kiss`
- 시작 HEAD: `a20e907` (`Implement automatic effects for AWL-SP-002`)
- 시작 상태: clean
- 예약 카드: `UNC-AT-026`, `UNC-AT-027`, `UNC-AT-028`
- 공통 엔진·스키마·문서 수정자: 메인 세션만
- 운영 DB: 카드 원문·보충 설명·Q&A 읽기만 허용

이 worktree는 완료된 RFS와 AWL 보조 커밋을 포함하지만, 메인 dirty worktree의
후속 UNC·공통 엔진 변경은 포함하지 않는다. 메인 파일을 복사하거나 전체 파일을
한쪽 버전으로 교체하지 않는다. 카드 전용 정의·검토기·테스트만 커밋하고, 필요한
공통 기능이 기준 브랜치에 없으면 우회하지 말고 최소 실패 시나리오와 요청
인터페이스를 보고한다.

## 시작 점검

```powershell
cd C:\Hinoto\LumenGG-review-unc-kiss
git status --short --branch
git branch --show-current
git log -1 --oneline
git diff --name-only
```

예상 결과는 clean `review/unc-kiss`, HEAD `a20e907`이다. 다르면 파일을
되돌리거나 삭제하지 말고 메인 세션에 보고한다.

## 허용 범위

다음 세 파일에서 예약 카드 전용 블록만 수정한다.

- `LumenGG/battlelog/game/drafts.py`
- `LumenGG/battlelog/game/review.py`
- `LumenGG/battlelog/test_automatic_engine.py`

다음은 수정하지 않는다.

- `engine.py`, `effects.py`, `schema.py`, `spec.py`
- 모델, 마이그레이션, API, WebSocket, JavaScript, 템플릿
- `TESTING.md`와 모든 인수인계 문서
- 메인 worktree `C:\Hinoto\LumenGG`의 모든 파일
- `test.local.ps1`, `SECRET_KEYS.py`, `.temp` 자료와 자격 증명

`git pull`, `merge`, `rebase`, `stash`, `git add -A`를 사용하지 않는다.
`review_automatic_effect_drafts --apply`, seed, publish와 운영 DB 쓰기는 금지한다.

## 카드별 완료 기준

1. 카드 원문, `detail_text`, 연결 Q&A를 확인한다.
2. 재정 우선순위는 최신 에라타·보충 설명 > 카드별 Q&A > 카드 문구 > 룰북 >
   일반 Q&A다.
3. 기능과 번호 효과 그룹마다 최소 3개 결정적 시나리오를 작성한다.
4. 양쪽 소유자, 경계값, 조건 불충족, 잘못된 타이밍·영역, 번호 효과 무효를
   포함하고 필요하면 후보 없음·복수 후보·보호 전후를 추가한다.
5. 강제 획득·브레이크·버리기·이동의 대상이 특정되지 않았다면 실제
   `pending_decision`으로 합법 후보를 선택하게 한다.
6. 선택 시점의 합법성뿐 아니라 실제 도메인 명령의 성공 결과를 `result_key`로
   확인하고 “그 후” 효과는 성공한 경우에만 적용한다.
7. 판단 근거가 부족하면 자동 승인하지 않고 정확한 재정 의문을 남긴다.
8. 카드 한 장당 한 커밋으로 만들고 커밋 후 다음 카드로 진행한다.

## 실행 순서

명령 작업 디렉터리는 `C:\Hinoto\LumenGG-review-unc-kiss\LumenGG`다.

```powershell
cd C:\Hinoto\LumenGG-review-unc-kiss\LumenGG

# 원문/Q&A 및 구현 전후 결과 확인: 읽기 전용, --apply 금지
python manage.py review_automatic_effect_drafts `
  --card-code UNC-AT-026 --verbose

python -m py_compile battlelog/game/drafts.py `
  battlelog/game/review.py battlelog/test_automatic_engine.py

$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput

cd ..
git diff --check
git status --short
git add LumenGG/battlelog/game/drafts.py `
  LumenGG/battlelog/game/review.py `
  LumenGG/battlelog/test_automatic_engine.py
git diff --cached --stat
git commit -m "Implement automatic effects for UNC-AT-026"
```

각 카드에서 실제 수정된 허용 파일만 스테이징한다. 세 장을 하나의 커밋으로
합치지 않는다.

## 완료 보고 형식

```text
예약 그룹: UNC Kiss 3장
완료 카드와 카드별 커밋 해시:
보류 카드와 정확한 재정/공통 엔진 사유:
카드별 능력 그룹/결정적 시나리오 수:
카드별 읽기 전용 드라이런 결과:
자동 엔진 SQLite 테스트 결과:
git diff --check:
최종 브랜치/HEAD/clean 여부:
```

## 새 세션에 붙여 넣을 프롬프트

```text
C:\Hinoto\LumenGG-review-unc-kiss를 유일한 작업 루트로 사용해줘. 먼저
C:\Hinoto\LumenGG\PARALLEL_SESSION_UNC_KISS_HANDOFF.md와
C:\Hinoto\LumenGG\PARALLEL_WORKFLOW.md를 처음부터 끝까지 읽어줘.
review/unc-kiss 브랜치가 clean이고 HEAD가 a20e907인지 확인한 뒤
UNC-AT-026, UNC-AT-027, UNC-AT-028만 순서대로 검토해. 카드 한 장마다 별도
커밋을 만들고 카드 전용 drafts.py/review.py/test_automatic_engine.py 블록만
수정해. 메인 worktree와 공통 엔진·스키마·문서에는 손대지 마. 운영 DB는
원문/Q&A와 드라이런 읽기만 하고 --apply/seed/publish는 실행하지 마.
공통 기능이 부족하면 우회하지 말고 최소 실패 시나리오와 필요한 인터페이스를
보고해. 각 능력에 최소 3개 결정적 시나리오를 만들고, 지정되지 않은 강제 카드
이동은 실제 플레이어 선택으로 구현해. 마지막에 커밋 해시, 시나리오 수,
드라이런, SQLite 테스트와 보류 사유를 보고해.
```
