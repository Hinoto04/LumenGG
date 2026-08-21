# 울프 자동 효과 검토 세션 인수인계

> 완료 기록(2026-08-20): `review/wolf`의 `e2b73e2`, `67089b2`, `e6a3eff`,
> `2c3ef5d` 카드별 커밋을 메인 작업 트리에 수동 통합했다. 통합 후 자동 엔진
> 711개와 전체 820개 SQLite 테스트가 통과했다. 이 문서의 아래 계약은 과거
> 기록이며 새 작업에는 `PARALLEL_SESSION_LIN_CB01_HANDOFF.md`를 사용한다.

최종 확인: 2026-08-20 (Asia/Seoul)

이 세션은 완료된 RFS/AWL 브랜치를 보존한 채, 비어 있는 보조 worktree를
울프 잔여 카드 검토에 재사용한다. 공통 운영 규칙은
`PARALLEL_WORKFLOW.md`, 전체 완료 현황은
`AUTOMATIC_EFFECT_REVIEW_HANDOFF.md`를 따른다.

## 작업 계약

- 작업 경로: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/wolf`
- 시작 HEAD: `a20e907` (`Implement automatic effects for AWL-SP-002`)
- 예약 카드: `CB01-AT-016`, `CB01-AT-017`, `CRS-AT-033`, `PMP-AT-026`
- 운영 DB: 카드/Q&A 조회만 허용
- 결과물: 카드마다 정의·결정적 검토 시나리오·회귀 테스트를 한 커밋으로 작성

완료된 `review/awl`과 `review/rfs` 브랜치는 그대로 남아 있다. 이 worktree만
`review/wolf`로 전환했으므로 이전 브랜치를 삭제하거나 다시 합치지 않는다.

## 카드별 검토 초점

- `CB01-AT-016` 사냥 개시: 루멘 페이즈의 임의 개수 하울링 제거와 제거 수만큼
  상대 FP 감소, 체력 2500 이하에서의 자기 브레이크를 실제 상태 변화로 검증한다.
- `CB01-AT-017` 스트롱 블리츠: 상대 방어·상쇄 금지, 그랩 무효 때 효과 데미지 후
  자기 FP 4 감소, 히트 시 별도 100 효과 데미지를 구분한다.
- `CRS-AT-033` 데드네우스: 카운터 데미지 +400, 콤보 보정 무시, 위압 상태에서
  앞서 사용한 울프 기술 수를 최대 3장까지 세어 효과 데미지를 주고 콤보를 끝낸다.
- `PMP-AT-026` 새비지 블레이드: 사용한 턴의 하울링 획득 금지, 히트/카운터 때
  전부 제거한 실제 개수, 3개 이상일 때의 위압 부여, 속도 12 이상 사용 금지와
  울프 손 기술 데미지 +100의 지속 범위를 검증한다.

카드 원문, `detail_text`, 연결 Q&A를 구현 전에 다시 조회한다. 위 요약과 최신
재정이 다르면 최신 에라타·보충 설명 > 카드별 Q&A > 카드 문구 > 룰북 > 일반
Q&A 순으로 판정하고 차이를 완료 보고에 남긴다.

## 수정 범위

예약 카드 전용의 작은 블록만 다음 세 파일에 추가한다.

- `LumenGG/battlelog/game/drafts.py`
- `LumenGG/battlelog/game/review.py`
- `LumenGG/battlelog/test_automatic_engine.py`

`engine.py`, `schema.py`, `effects.py`, `spec.py`, 모델, 마이그레이션, UI,
`TESTING.md`와 인수인계 문서는 메인 세션만 수정한다. 공통 지원이 부족하면
우회 구현하거나 공통 파일을 고치지 말고, 최소 실패 시나리오와 필요한 DSL
인터페이스를 보고한다.

## 검토 기준

- 능력 그룹마다 최소 3개 결정적 시나리오를 작성하고 같은 시나리오의 반복 실행
  결과가 동일한지 확인한다.
- p1/p2 양쪽, 올바른 타이밍, 조건 불충족, 경계값, 번호 효과 무효를 포함한다.
- 카드를 강제로 획득·버리기·브레이크·이동하면서 대상을 특정하지 않은 효과는
  실제 `pending_decision`을 만들고 합법 후보를 다시 검증한다.
- 카운터를 임의 개수 소모하는 선택은 고정된 최대값으로 대신하지 않는다. 현재
  DSL에서 선택 개수를 표현할 수 없다면 검토 완료로 표시하지 않는다.
- 모호한 재정이나 실행되지 않는 설명용 노드는 테스트 수와 무관하게
  `review_required`로 남긴다.

## 시작 및 검증

```powershell
cd C:\Hinoto\LumenGG-review-rfs
git status --short --branch
git branch --show-current
git log -1 --oneline
git diff --name-only
```

예상 결과는 clean `review/wolf`, HEAD `a20e907`이다. 다르면 수정하지 않고 메인
세션에 보고한다.

카드마다 아래 순서로 진행한다. 구현 난도가 낮은 순서로
`CB01-AT-017`, `CRS-AT-033`, `CB01-AT-016`, `PMP-AT-026`을 권장한다.

```powershell
cd C:\Hinoto\LumenGG-review-rfs\LumenGG

python manage.py review_automatic_effect_drafts `
  --card-code CB01-AT-017 --verbose

$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput

cd ..
git diff --check
git status --short
```

운영 DB에 쓰는 `--apply`, seed, publish, 마이그레이션은 실행하지 않는다.
`test.local.ps1`, `SECRET_KEYS.py`, `.temp`의 비밀 자료는 열거나 복사하거나
커밋하지 않는다. `git add -A`, merge, rebase, stash, pull도 사용하지 않는다.

커밋할 때는 허용된 세 파일 중 실제 변경한 파일만 명시적으로 스테이징하고 카드
하나당 커밋 하나를 만든다.

## 완료 보고

```text
카드/작업: 울프 잔여 4장
기준 커밋과 작업 브랜치:
카드별 해석 요약:
변경 파일:
능력 그룹/결정적 시나리오 수:
카드별 읽기 전용 드라이런:
SQLite 자동 엔진 테스트:
git diff --check:
카드별 커밋 해시:
남은 재정 의문:
필요한 공통 엔진 변경:
```

예약 카드 네 장을 마치거나 공통 엔진 문제로 중단하면 다음 그룹을 임의로 시작하지
않고 메인 세션의 통합 결정을 기다린다.

## 새 세션에 붙여 넣을 프롬프트

```text
C:\Hinoto\LumenGG-review-rfs를 유일한 작업 루트로 사용해줘.
먼저 C:\Hinoto\LumenGG\PARALLEL_SESSION_START_HERE.md,
C:\Hinoto\LumenGG\PARALLEL_SESSION_WOLF_HANDOFF.md,
C:\Hinoto\LumenGG\PARALLEL_WORKFLOW.md,
C:\Hinoto\LumenGG\AUTOMATIC_EFFECT_REVIEW_HANDOFF.md를 처음부터 끝까지 읽어줘.
clean review/wolf, HEAD a20e907인지 확인한 뒤 CB01-AT-016, CB01-AT-017,
CRS-AT-033, PMP-AT-026만 카드별 한 커밋으로 구현·검토해줘. 공통 엔진 파일과
메인 worktree는 수정하지 말고 운영 DB에는 쓰지 마. 능력별 최소 3개 결정적
시나리오와 SQLite 회귀를 통과시키고, 공통 엔진 지원이 부족하면 우회하지 말고
실패 재현과 필요한 인터페이스를 보고해줘.
```
