# AWL 자동 효과 검토 세션 인수인계

최종 확인: 2026-08-20 (Asia/Seoul)

## 완료 상태와 후속 계약

- 유일한 작업 루트: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/awl`
- 시작 HEAD: `c0741ea` (`Implement automatic effects for RFS-PS-002`)
- 현재 HEAD: `a20e907` (`Implement automatic effects for AWL-SP-002`)
- 현재 상태: clean
- 카드별 커밋 완료 후 메인 통합: `AWL-AT-026/027/030/031/032`,
  `AWL-SP-002`
- 보조 커밋은 없었으나 메인에서 완료: `AWL-AT-025`

```text
AWL-AT-025 AWL-AT-026 AWL-AT-027 AWL-AT-030
AWL-AT-031 AWL-AT-032 AWL-SP-002
```

RFS 20장 구현은 이미 메인 작업 트리에 통합되었다. AWL의 준비된 6개 커밋도
메인 작업 트리에 카드별 블록으로 합쳤고, `AWL-AT-025`는 메인에서 구현했다.
통합 기준 자동 엔진 690개와 프로젝트 전체 799개 테스트가 통과했다. 다음 네 RFS 카드는 재정을
추측하지 않고 검토 필요 상태로 남겨 두었으므로 이 세션에서 수정하지 않는다.

```text
RFS-AT-026 RFS-AT-027 RFS-AT-041 RFS-PS-001
```

메인 세션은 `C:\Hinoto\LumenGG`에서 `ST2-001`~`ST2-005`, `ST2-008`,
`ST2-010` 검토를 완료했고 공통 엔진을 소유한다. `ST4-SS1`~`ST4-SS3`도 완료됐다.
메인 worktree를 수정·스테이징·stash·커밋하거나 파일 전체를 복사하지 않는다.

## 시작 점검

```powershell
cd C:\Hinoto\LumenGG-review-rfs
git status --short --branch
git branch --show-current
git log -1 --oneline
git diff --name-only
```

예상 결과는 clean `review/awl`, HEAD `a20e907`이다. 값이 다르거나 변경이 있으면
아무것도 되돌리지 말고 메인 세션에 보고한다. 이 worktree는 완료 기록으로 보존하고
기존 6개 커밋 위에 새 작업을 추가하지 않는다.

## 허용 파일과 금지 범위

다음 세 파일의 AWL 카드 전용 작은 블록만 수정한다.

- `LumenGG/battlelog/game/drafts.py`
- `LumenGG/battlelog/game/review.py`
- `LumenGG/battlelog/test_automatic_engine.py`

`engine.py`, `schema.py`, `effects.py`, `spec.py`, 모델, 마이그레이션, API,
JavaScript, 템플릿, `TESTING.md`, 모든 인수인계 문서는 수정하지 않는다. 공통
기능이 부족하면 카드 코드, 최소 실패 시나리오, 필요한 DSL/엔진 인터페이스를
보고하고 해당 카드 구현은 보류한다. 다른 카드가 독립적이면 다음 예약 카드로
계속할 수 있다.

운영 DB는 카드 원문·보충 설명·Q&A와 드라이런 확인에만 읽기 전용으로 사용한다.
`--apply`, seed, publish, 마이그레이션과 운영 데이터 수정은 금지한다.
`test.local.ps1`이나 비밀 설정은 읽거나 공유하지 않는다.

## 카드별 완료 조건

1. 카드 원문, `detail_text`, 연결 Q&A를 확인하고 출처 우선순위를 적용한다.
2. 기능/번호 효과 그룹마다 최소 3개 결정적 시나리오를 작성한다.
3. 양쪽 소유자, 경계값, 조건 불충족, 잘못된 타이밍·영역, 번호 효과 무효를
   가능한 범위에서 포함한다.
4. 대상이 특정되지 않은 강제 획득·브레이크·버리기·이동은 실제
   `pending_decision`과 합법 후보 선택으로 구현한다.
5. 최초부터 이동 불가능한 후보를 제외하고, 선택 뒤 보호가 생긴 경우 실제 명령
   성공 여부를 재검사한다. “그 후” 효과는 앞선 동작 성공 시에만 적용한다.
6. 정의와 카드 기본 수치 mutation 검사를 포함하고, 판단 근거가 부족하면 자동
   승인하지 않는다.
7. 한 카드당 한 커밋으로 만들고 예약 순서대로 진행한다. 관련 없는 리팩터링이나
   파일 전체 포맷 변경을 섞지 않는다.

## 실행 순서

첫 카드는 `AWL-AT-025`다. 이후 예약 목록 순서대로 같은 절차를 반복한다.

```powershell
cd C:\Hinoto\LumenGG-review-rfs\LumenGG

# 작업 전/후 운영 DB 읽기 전용 드라이런
python manage.py review_automatic_effect_drafts `
  --card-code AWL-AT-025 --verbose

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
git commit -m "Implement automatic effects for AWL-AT-025"
```

`git add -A`, `pull`, `merge`, `rebase`, `stash`를 사용하지 않는다. 카드별 커밋
직전 `git diff --cached`에서 그 카드 전용 변경만 포함되었는지 확인한다.

## 완료 보고 형식

```text
예약 그룹: AWL 잔여 7장
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
C:\Hinoto\LumenGG-review-rfs를 유일한 작업 루트로 사용해줘. 먼저
C:\Hinoto\LumenGG\PARALLEL_SESSION_START_HERE.md,
C:\Hinoto\LumenGG\PARALLEL_SESSION_AWL_HANDOFF.md,
C:\Hinoto\LumenGG\PARALLEL_WORKFLOW.md를 처음부터 끝까지 읽어줘.
review/awl 브랜치가 clean이고 HEAD가 a20e907인지 확인해. AWL 7장은 이미 메인에
통합 완료됐으므로 기존 카드를 수정하거나 새 커밋을 만들지 말고 상태만 보고해.
운영 DB 쓰기, --apply/seed/publish, 공통 엔진 수정과 메인 worktree 변경은 하지 마.
```
