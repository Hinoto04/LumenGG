# RFS 자동 효과 검토 세션 인수인계

> 완료 기록(2026-08-20): `review/rfs`의 `c0741ea`까지 구현된 RFS 20장은 메인
> 작업 트리에 통합했고, 잔여 `RFS-AT-026`, `RFS-AT-027`, `RFS-AT-041`,
> `RFS-PS-001`도 메인에서 완료했다. 현재 RFS 24장 전체가 검토 완료이며 최신
> 통합 기준으로 자동 엔진 743개, 전체 852개 테스트를 통과했다. 이 문서의 아래 실행 계약은 과거
> 기록이므로 새 작업에 사용하지 않는다. 현재 이 worktree는 `review/wolf`이며
> 새 병렬 작업은 `PARALLEL_SESSION_WOLF_HANDOFF.md`를 사용한다.

최종 갱신: 2026-08-20 (Asia/Seoul)

이 문서는 두 번째 Codex/IDE 세션에 그대로 전달하는 짧은 실행 지침이다. 전체
병렬 운영 원칙은 `PARALLEL_WORKFLOW.md`, 배경, 완료 카드와 판정 기준은
`AUTOMATIC_EFFECT_REVIEW_HANDOFF.md`에 있다. 세 문서를 함께 전달한다.

## 이번 세션의 작업 계약

- 작업 경로: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/rfs`
- 시작 시 기대 HEAD: `c0741ea`
- 이번 예약 카드: **`RFS-AT-026` 한 장만**
- 메인 세션 예약 카드: `ST3-*`, `ST4-*`, `ST6-002`, `LMI-AT-011`,
  `LMI-AT-012`, `LMI-AT-019`, `LMI-AT-020`, `LMI-AT-023`,
  `LMI-AT-004`/`LMI-AT-005`/`LMI-AT-006`/`LMI-AT-007`/`LMI-AT-008`/
  `LMI-AT-009`/`LMI-AT-024` 완료, `LMI-AT-010` 예약
- 공통 엔진·스키마 수정자: 메인 세션 한 곳만
- 운영 DB: 읽기만 허용
- 결과물: 카드별 정의, 전용 검토 시나리오, 단위 테스트를 묶은 커밋 1개

`ST3-011`이라는 카드는 운영 카탈로그에 없다. 실제 `ST3` 코드는
`ST3-001`~`ST3-010`, `ST3-017`, `ST3-018`, `ST3-PS1`이며 이 블록은 메인
세션에서 검증을 마쳤다. 따라서 이 세션은 `ST3-*`나 `ST4-*`를 선점하지 않는다.

현재 확인 기준으로 이 worktree에는 gitignored `LumenGG/SECRET_KEYS.py`와
`test.local.ps1`이 없다. 따라서 Django 명령 전에 사용자가 이 worktree 전용 로컬
설정을 제공해야 할 수 있다. 가장 안전한 구성은 카드/Q&A 조회만 가능한 **SELECT
전용 DB 계정**과 테스트용 비밀 키를 사용하는 것이다. 운영 쓰기 권한 계정이나
설정 파일 내용을 채팅으로 전달하지 않는다. 설정 후 아래 명령으로 파일이 Git 추적
대상에서 제외되는지만 확인한다.

```powershell
git -C C:\Hinoto\LumenGG-review-rfs check-ignore `
  LumenGG/SECRET_KEYS.py test.local.ps1
```

`check-ignore`는 파일 내용을 출력하지 않는다. SQLite 테스트와 운영 카탈로그
읽기 명령을 구분하고, MariaDB 테스트는 다른 세션과 동시에 실행하지 않는다.

메인 worktree에는 현재 완료된 `ST3-008`~`ST3-010`, `ST4-PS1`, `ST4-001`~`ST4-010`,
`ST6-002`, `LMI-AT-011`, `LMI-AT-012`, `LMI-AT-019`, `LMI-AT-020`, PS 특성
카드의 패시브 존 처리, 완료된 `LMI-AT-004`/`LMI-AT-005`/`LMI-AT-023`/`LMI-AT-024`
및 `LMI-AT-006`/`LMI-AT-007`/`LMI-AT-008`/`LMI-AT-009` 검토와 다음
`LMI-AT-010`을 위한
`drafts.py`, `review.py`, `engine.py`,
`schema.py` 미커밋 변경이 있다. 이 변경을 병렬 worktree로 복사하거나, 반대로
병렬 브랜치의 공유 파일을 메인 worktree에 덮어쓰지 않는다. 병렬 세션은 오직
자기 카드 커밋 해시만 전달하고 통합은 메인 세션이 맡는다.

다음 조건 중 하나라도 다르면 파일을 수정하지 말고 사용자에게 상태를 보고한다.

```powershell
cd C:\Hinoto\LumenGG-review-rfs
git status --short --branch
git branch --show-current
git log -1 --oneline
```

예상 상태는 변경 파일이 없는 `review/rfs`, HEAD
`c0741ea Implement automatic effects for RFS-PS-002`다.

2026-08-20 인수인계 작성 시점에는 위 상태가 실제로 확인됐다. 새 세션을 열 때는
항상 다시 확인하고, 예상과 다르면 그 상태를 덮어쓰지 않는다.

검증된 시작 상태:

```text
## review/rfs
review/rfs
c0741ea Implement automatic effects for RFS-PS-002
```

## 허용 범위

필요한 최소 블록만 아래 파일에 추가한다.

- `LumenGG/battlelog/game/drafts.py`: `RFS-AT-026` 전용 정의
- `LumenGG/battlelog/game/review.py`: `RFS-AT-026` 전용 결정적 검토기와 디스패치
- `LumenGG/battlelog/test_automatic_engine.py`: 이 카드의 회귀 및 mutation 테스트

카드 원문, `detail_text`, 연결 Q&A와 기존 엔진 코드는 읽어도 된다. 아래 공유
기반 파일의 범용 동작은 이 세션에서 수정하지 않는다.

- `LumenGG/battlelog/game/engine.py`
- `LumenGG/battlelog/game/schema.py`
- `LumenGG/battlelog/game/effects.py`
- `LumenGG/battlelog/game/spec.py`
- `TESTING.md`
- `AUTOMATIC_EFFECT_REVIEW_HANDOFF.md`

공통 엔진 지원이 필요하면 추측 구현하지 않는다. 재현 가능한 실패 시나리오,
필요한 DSL/엔진 인터페이스와 예상 결과를 완료 보고에 남긴다.

## 구현·검토 기준

- 최신 에라타/보충 설명 > 카드별 Q&A > 카드 문구 > 룰북 > 일반 Q&A 순으로
  해석한다.
- 불명확한 문구는 검토 완료로 만들지 않는다.
- 강제로 카드를 획득·브레이크·버리기·이동하지만 대상이 특정되지 않았다면 실제
  `pending_decision`으로 플레이어가 합법 후보를 선택하게 한다.
- 후보는 현재 실행할 수 없는 카드를 제외하며, 선택 후 상태 변화도 실제 명령에서
  다시 검증한다.
- 능력 그룹마다 최소 3개 결정적 시나리오를 만든다. 기본 구성은 p1 성공, p2
  성공/경계, 잘못된 타이밍 또는 조건 불충족이다. 필요하면 후보 없음, 복수 후보,
  보호, 번호 효과 무효와 실제 영역 이동을 더한다.
- 자동 승인 여부를 테스트 개수로 대신하지 않는다. 재정 근거가 부족하면
  `review_required`로 남긴다.

## 금지 작업

- `C:\Hinoto\LumenGG` 메인 worktree의 파일 수정, 스테이징, stash 또는 커밋
- `git pull`, `git merge`, `git rebase`, `git stash`
- 전체 파일 정렬, 대규모 포맷 변경, 주변 카드 리팩터링
- 새 마이그레이션 작성
- `review_automatic_effect_drafts --apply`
- `seed_automatic_effect_drafts`
- `publish_automatic_ruleset`
- 운영 DB를 수정하는 모든 명령
- `test.local.ps1` 내용 열람, 복사 또는 채팅 공유

로컬 설정 파일이 없어서 Django가 시작되지 않으면 자격 증명을 추측하거나
추적 파일에 쓰지 말고 사용자에게 로컬 설정 제공을 요청한다. 설정 파일은 반드시
gitignored 상태로 유지한다.

## 실행 순서

명령 작업 디렉터리는 `C:\Hinoto\LumenGG-review-rfs\LumenGG`다.

```powershell
cd C:\Hinoto\LumenGG-review-rfs\LumenGG

# 운영 DB 읽기 전용: 구현 전 원문/Q&A/현재 결과 확인
python manage.py review_automatic_effect_drafts `
  --card-code RFS-AT-026 --verbose

# 구현 후 문법 확인
python -m py_compile battlelog/game/drafts.py `
  battlelog/game/review.py battlelog/game/schema.py

# SQLite 단위/전체 자동 엔진 테스트
$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test `
  battlelog.test_automatic_engine.AutomaticEngineTests `
  --settings=LumenGG.test_settings --noinput
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput

# 운영 DB 쓰기 없는 카드별 최종 드라이런
python manage.py review_automatic_effect_drafts `
  --card-code RFS-AT-026 --verbose

cd ..
git diff --check
git status --short
git add LumenGG/battlelog/game/drafts.py `
  LumenGG/battlelog/game/review.py `
  LumenGG/battlelog/test_automatic_engine.py
git diff --cached --stat
git commit -m "Implement automatic effects for RFS-AT-026"
```

실제 변경 파일이 위 세 개보다 적으면 존재하는 변경만 스테이징한다. `git add -A`는
사용하지 않는다.

## 완료 보고 형식

```text
카드: RFS-AT-026
해석 요약:
- ...

변경 파일:
- ...

검증:
- 능력 그룹 N개 / 결정적 시나리오 N개
- 카드별 드라이런: PASS 또는 정확한 실패 이유
- 자동 엔진 테스트: N tests, OK 또는 정확한 실패 이유
- git diff --check: PASS

커밋: <hash>
남은 재정 의문: 없음 또는 ...
공통 엔진 요청: 없음 또는 실패 재현/제안 인터페이스 ...
```

커밋 후 다음 카드로 넘어가지 않는다. 커밋 해시와 보고를 사용자에게 전달하고 통합
세션의 결정을 기다린다.

## 통합 시 주의사항

현재 메인 worktree는 대규모 미커밋 변경이 있는 dirty 상태다. 따라서 병렬 세션은
메인 경로에서 `cherry-pick`을 실행하지 않는다. 메인 세션이 먼저 현재 변경을
체크포인트 커밋으로 보존하거나 그 커밋을 기준으로 clean 통합 worktree를 만든 뒤,
`RFS-AT-026` 커밋 하나만 가져온다.

공유 파일에서 충돌이 나면 한쪽 파일 전체를 선택하지 않는다. 아래 세 종류를 양쪽
모두 보존해 수동으로 합친다.

- `drafts.py`의 카드 코드 전용 정의 블록
- `review.py`의 카드 전용 검토 함수와 디스패치 등록
- `test_automatic_engine.py`의 카드 전용 테스트 메서드

통합 뒤에는 두 카드별 드라이런, 자동 엔진 SQLite 테스트, 전체 SQLite 회귀를
다시 실행하고 그 결과가 통과한 뒤에만 집계 문서를 갱신한다.

## 다른 세션에 붙여 넣을 프롬프트

```text
C:\Hinoto\LumenGG-review-rfs를 작업 루트로 열고
C:\Hinoto\LumenGG\PARALLEL_WORKFLOW.md,
C:\Hinoto\LumenGG\PARALLEL_SESSION_RFS_HANDOFF.md와
C:\Hinoto\LumenGG\AUTOMATIC_EFFECT_REVIEW_HANDOFF.md를 읽어 그 작업 계약을
따라줘. 우선 clean review/rfs, HEAD c0741ea인지 확인하고 RFS-AT-026 한 장만
구현·검토해. 공통 엔진 파일과 메인 worktree는 수정하지 말고, 운영 DB에는 어떤
쓰기 명령도 실행하지 마. 능력별 최소 3개 결정적 시나리오와 SQLite 자동 엔진
회귀를 통과한 뒤 카드 하나만 커밋하여 해시와 완료 보고를 전달해.
```
