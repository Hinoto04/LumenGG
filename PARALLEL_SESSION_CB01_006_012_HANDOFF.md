# CB01 006/011/012 병렬 자동 효과 검토 인수인계

최종 갱신: 2026-08-21 (Asia/Seoul)

## 고정 작업 범위

- 작업 루트: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/cb01-006-011-012`
- 시작 HEAD: `5a05a96` (`Review automatic effects for PMP-AT-022`)
- 카드: `CB01-AT-006`, `CB01-AT-011`, `CB01-AT-012`
- 허용 파일:
  - `LumenGG/battlelog/game/drafts.py`
  - `LumenGG/battlelog/game/review.py`
  - `LumenGG/battlelog/test_automatic_engine.py`

`CB01-AT-006`은 직전 배치에서 완료 커밋이 없었던 복합 효과 카드다.
`CB01-AT-011/012`는 최상위 `play_condition` 때문에 카드별 검토가 필요하다.
같은 worktree의 이전 `CB01-AT-008/010`과 `PMP-AT-013/019/022` 커밋은 이미
메인에 수동 통합했으므로 다시 수정하지 않는다.

## 구현·검토 계약

운영 DB의 카드 원문, `detail_text`, 연결 Q&A는 읽기 전용으로 확인한다. 카드별
정의·전용 검토기·테스트만 작은 블록으로 추가한다. 공통 엔진, 스키마, 문서와 메인
worktree는 수정하지 않는다. 카드마다 별도 커밋을 만들며 한 카드가 공통 엔진
부족으로 막혀도 다른 예약 카드는 계속 검토한다.

능력 그룹마다 최소 3개 결정적 시나리오를 작성한다. 양쪽 소유자, 조건 경계,
번호 효과 무효를 포함한다. 대상이 특정되지 않은 강제 획득·브레이크·버리기·이동은
실제 `pending_decision`과 합법 후보로 검증한다. `play_condition`은 표시용 메타데이터
존재만 확인하지 말고 실제 합법 행동 차단과 경계값을 확인한다. 공통 지원이 부족하면
우회용 설명 노드로 통과시키지 말고 최소 실패 재현과 필요한 인터페이스를 보고한다.

카드별 읽기 전용 드라이런, 전체 자동 엔진 SQLite 테스트와 `git diff --check`를
실행한다. 운영 DB 쓰기, `--apply`, seed, publish, 마이그레이션,
merge/rebase/stash/pull은 금지한다.
