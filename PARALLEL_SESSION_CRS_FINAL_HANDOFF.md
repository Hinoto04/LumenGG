# CRS 잔여 4장 병렬 자동 효과 검토 인수인계

> 완료 기록(2026-08-21): 보조 브랜치에는 결과 커밋이 없었으나 메인에서
> `CRS-AT-006/007/008/026`을 11개 능력 그룹과 70개 결정적 시나리오로
> 구현·검토했다. 자동 엔진 795개와 전체 904개 SQLite 테스트가 통과했으며,
> 이 네 장은 새 병렬 예약에서 제외한다.

최종 갱신: 2026-08-21 (Asia/Seoul)

## 고정 작업 범위

- 작업 루트: `C:\Hinoto\LumenGG-review-unc-kiss`
- 브랜치: `review/crs-final-006-008-026`
- 시작 HEAD: `f91dfd1` (`Review automatic effects for CRS-AT-024`)
- 카드: `CRS-AT-006`, `CRS-AT-007`, `CRS-AT-008`, `CRS-AT-026`
- 허용 파일:
  - `LumenGG/battlelog/game/drafts.py`
  - `LumenGG/battlelog/game/review.py`
  - `LumenGG/battlelog/test_automatic_engine.py`

이 네 장은 현재 카탈로그에 남은 CRS 전부다. `006/007`은 복합 효과,
`008`은 수비 제한을 포함한 효과, `026`은 `deck_limit` 때문에 카드별 검토가
필요하다. 과거 `006/007/008` 요청과 직전 `026` 요청에서는 완료 커밋이 없었으므로
이번 배치에서 처음부터 실제 결과를 확인한다.

## 구현·검토 계약

운영 DB의 카드 원문, `detail_text`, 연결 Q&A는 읽기 전용으로 확인한다. 카드별
정의·전용 검토기·테스트만 작은 블록으로 추가한다. 공통 엔진, 스키마, 문서와 메인
worktree는 수정하지 않는다. 카드마다 별도 커밋을 만들며 한 카드가 공통 엔진
부족으로 막혀도 다른 예약 카드는 계속 검토한다.

능력 그룹마다 최소 3개 결정적 시나리오를 작성한다. 양쪽 소유자, 조건 경계,
번호 효과 무효를 포함한다. 대상이 특정되지 않은 강제 획득·브레이크·버리기·이동은
실제 `pending_decision`과 합법 후보로 검증한다. 공통 지원이 부족하면 우회용
설명 노드로 통과시키지 말고 최소 실패 재현과 필요한 인터페이스를 보고한다.

카드별 읽기 전용 드라이런, 전체 자동 엔진 SQLite 테스트와 `git diff --check`를
실행한다. 운영 DB 쓰기, `--apply`, seed, publish, 마이그레이션,
merge/rebase/stash/pull은 금지한다.
