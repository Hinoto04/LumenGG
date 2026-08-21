# LIN/CB01 자동 효과 검토 세션 인수인계

> 완료/보존 문서: `CB01-AT-031/032/033`의 카드별 커밋 `a79b43f`,
> `96aa538`, `1219400`은 2026-08-20 메인에 통합됐다. 같은 worktree의 현재
> 작업은 `PARALLEL_SESSION_CB01_035_036_HANDOFF.md`를 따른다.

최종 확인: 2026-08-20 (Asia/Seoul)

이 문서는 완료된 울프 커밋을 메인에 통합한 뒤 같은 보조 worktree를 다음
연속 카드 묶음에 재사용하기 위한 실행 계약이다. 공통 운영 규칙은
`PARALLEL_WORKFLOW.md`, 전체 완료 현황과 재정 기준은
`AUTOMATIC_EFFECT_REVIEW_HANDOFF.md`를 따른다.

## 작업 계약

- 작업 경로: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/lin-cb01`
- 시작 HEAD: `2c3ef5d` (`Implement automatic effects for PMP-AT-026`)
- 예약 카드: `CB01-AT-031`, `CB01-AT-032`, `CB01-AT-033`
- 허용 파일: 아래 카드 전용 블록을 넣는 세 파일만
  - `LumenGG/battlelog/game/drafts.py`
  - `LumenGG/battlelog/game/review.py`
  - `LumenGG/battlelog/test_automatic_engine.py`
- 운영 DB: 카드 원문, `detail_text`, 연결 Q&A 조회만 허용
- 결과물: 카드마다 정의·결정적 검토 시나리오·회귀 테스트를 한 커밋으로 작성

완료된 `review/rfs`, `review/awl`, `review/wolf` 브랜치는 그대로 보존한다.
`review/wolf`의 마지막 네 커밋은 이미 메인에 수동 통합했으므로 다시 병합하거나
수정하지 않는다.

## 검토 초점

- `CB01-AT-031`: 체력 사용 제한, 사용 시 불씨 전부 제거, 실제 제거한 2개당
  데미지 +100, 사용 후 자기 브레이크와 콤보 타임 종료를 각각 검증한다.
- `CB01-AT-032`: 콤보 중 앞서 사용한 기술 전부 브레이크의 수락·거절,
  실제 브레이크 성공 여부, 그 경우에만 현재 카드의 콤보 데미지 보정 무시를
  검증한다.
- `CB01-AT-033`: 구현 전에 운영 카드 원문·보충 설명·연결 Q&A를 다시 조회해
  능력 경계와 대상 영역을 확정한다. 근거가 부족한 해석은 자동 승인하지 않고
  `review_required`로 남긴다.

각 능력 그룹마다 최소 3개 결정적 시나리오를 둔다. 기본 성공, 반대 플레이어 또는
경계값, 잘못된 타이밍/조건 불충족을 포함하고, 선택·브레이크·콤보·번호 효과 무효가
있으면 해당 분기를 추가한다. 강제 이동 대상이 특정되지 않았다면 실제
`pending_decision`과 합법 후보 재검증을 사용한다.

## 시작 전 확인과 중단 기준

```powershell
cd C:\Hinoto\LumenGG-review-rfs
git status --short --branch
git branch --show-current
git log -1 --oneline
git diff --name-only
```

예상 결과:

```text
## review/lin-cb01
review/lin-cb01
2c3ef5d Implement automatic effects for PMP-AT-026
```

브랜치·HEAD·경로가 다르거나 시작 전 변경 파일이 있으면 어떤 파일도 되돌리지 말고
메인 세션에 보고한다. 공통 엔진 지원이 부족한 경우에도 우회 구현하지 말고 실패
재현, 필요한 DSL/엔진 인터페이스와 예상 결과를 보고한다.

## 금지 작업

- `C:\Hinoto\LumenGG` 메인 worktree 수정, 스테이징, stash 또는 커밋
- `engine.py`, `schema.py`, `effects.py`, `spec.py`, 모델, 마이그레이션, 문서 수정
- `git pull`, `git merge`, `git rebase`, `git stash`, 전체 파일 정렬
- `review_automatic_effect_drafts --apply`, seed, publish, 운영 마이그레이션
- `.temp`, `test.local.ps1`, `SECRET_KEYS.py` 내용 열람·복사·커밋·공유
- 예약 밖 카드 작업 또는 완료 후 임의로 다음 카드 시작

## 검증과 커밋

명령 작업 디렉터리는 `C:\Hinoto\LumenGG-review-rfs\LumenGG`다. 운영 DB
검증을 생략하는 경우에도 SQLite 전용 테스트와 문법 검사는 반드시 실행한다.

```powershell
cd C:\Hinoto\LumenGG-review-rfs\LumenGG
python -m py_compile battlelog/game/drafts.py battlelog/game/review.py

$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput

cd ..
git diff --check
git status --short
git add LumenGG/battlelog/game/drafts.py `
  LumenGG/battlelog/game/review.py `
  LumenGG/battlelog/test_automatic_engine.py
git diff --cached --name-only
git commit -m "Implement automatic effects for CB01-AT-031"
```

카드 코드는 각 커밋에 맞게 바꾸고 한 카드당 한 커밋으로 유지한다. `git add -A`는
사용하지 않는다.

## 완료 보고 형식

```text
카드/작업:
기준 커밋과 작업 브랜치:
해석 요약:
변경 파일:
능력 그룹/결정적 시나리오 수:
카드별 읽기 전용 드라이런: PASS / SKIPPED / 정확한 실패 이유
SQLite 자동 엔진 테스트:
git diff --check:
커밋 해시:
남은 재정 의문:
필요한 공통 엔진 변경:
```

세 장을 마친 뒤 커밋 해시와 보고만 전달하고 통합은 메인 세션에 맡긴다.

## 다른 세션에 붙여 넣을 프롬프트

```text
C:\Hinoto\LumenGG-review-rfs를 유일한 작업 루트로 사용해줘.
먼저 C:\Hinoto\LumenGG\PARALLEL_SESSION_START_HERE.md,
C:\Hinoto\LumenGG\PARALLEL_SESSION_LIN_CB01_HANDOFF.md,
C:\Hinoto\LumenGG\PARALLEL_WORKFLOW.md,
C:\Hinoto\LumenGG\AUTOMATIC_EFFECT_REVIEW_HANDOFF.md를 처음부터 끝까지 읽어줘.
clean review/lin-cb01, HEAD 2c3ef5d인지 확인한 뒤 CB01-AT-031,
CB01-AT-032, CB01-AT-033만 카드별 한 커밋으로 구현·검토해줘. 공통 엔진 파일과
메인 worktree는 수정하지 말고 운영 DB에는 쓰지 마. 능력별 최소 3개 결정적
시나리오와 SQLite 회귀를 통과시키고, 공통 엔진 지원이 부족하면 우회하지 말고
실패 재현과 필요한 인터페이스를 보고해줘.
```
