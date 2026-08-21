# CRS 006~008 병렬 자동 효과 검토 인수인계

최종 갱신: 2026-08-20 (Asia/Seoul)

## 고정 작업 범위

- 작업 루트: `C:\Hinoto\LumenGG-review-unc-kiss`
- 브랜치: `review/crs-006-008`
- 시작 HEAD: `3ddf89f` (`Implement automatic effects for UNC-AT-028`)
- 카드: `CRS-AT-006`, `CRS-AT-007`, `CRS-AT-008`
- 허용 파일:
  - `LumenGG/battlelog/game/drafts.py`
  - `LumenGG/battlelog/game/review.py`
  - `LumenGG/battlelog/test_automatic_engine.py`

작업 시작 전 `git status --short --branch`, `git branch --show-current`,
`git log -1 --oneline`을 실행한다. 위 브랜치·HEAD와 다르거나 작업 트리가 dirty이면
되돌리거나 삭제하지 말고 메인 세션에 보고한다.

## 구현·검토 계약

각 카드의 운영 DB 원문, 보충 설명, 연결 Q&A를 읽기 전용으로 확인한다. 카드별
정의, 전용 검토기, 테스트만 최소 블록으로 추가하며 공통 엔진·스키마·문서와 메인
worktree는 수정하지 않는다. 공통 기능이 부족하면 카드 전용 우회 코드를 만들지
말고 실패 재현과 필요한 인터페이스를 보고한다.

능력 그룹마다 최소 3개의 결정적 시나리오를 작성한다. 양쪽 소유자, 발동/비발동
경계, 번호 효과 무효를 우선 포함하고, 카드가 이동 대상을 특정하지 않았다면 실제
`pending_decision`에서 합법 후보를 플레이어가 선택하게 한다. 정의 스키마와 카드
스냅샷·Q&A 출처가 정확히 일치해야만 검토 완료로 판정한다.

## 검증과 전달

```powershell
cd C:\Hinoto\LumenGG-review-unc-kiss\LumenGG

python manage.py review_automatic_effect_drafts --card-code CRS-AT-006 --verbose
python manage.py review_automatic_effect_drafts --card-code CRS-AT-007 --verbose
python manage.py review_automatic_effect_drafts --card-code CRS-AT-008 --verbose

$env:LUMENGG_TEST_DATABASE='sqlite'
python manage.py test battlelog.test_automatic_engine `
  --settings=LumenGG.test_settings --noinput
```

운영 DB에는 쓰지 않으며 `--apply`, seed, publish, migration을 실행하지 않는다.
카드 한 장당 커밋 하나를 만들고 실제 수정한 세 파일만 명시적으로 스테이징한다.
완료 보고에는 카드별 커밋 해시, 능력/시나리오 수, 읽기 전용 드라이런, SQLite
테스트, `git diff --check`, 남은 재정 의문과 필요한 공통 엔진 변경을 포함한다.
