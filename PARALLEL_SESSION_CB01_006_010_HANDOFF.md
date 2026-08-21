# CB01 006/008/010 병렬 자동 효과 검토 인수인계

최종 갱신: 2026-08-21 (Asia/Seoul)

> 완료된 과거 배치다. `CB01-AT-008/010`은 메인에 통합됐고 `CB01-AT-006`은
> 결과 커밋이 없어 새 `PARALLEL_SESSION_CB01_006_012_HANDOFF.md` 배치로 이관했다.
> 새 세션은 이 문서로 작업을 시작하지 않는다.

## 고정 작업 범위

- 작업 루트: `C:\Hinoto\LumenGG-review-rfs`
- 브랜치: `review/cb01-006-008-010`
- 시작 HEAD: `1219400` (`Implement automatic effects for CB01-AT-033`)
- 카드: `CB01-AT-006`, `CB01-AT-008`, `CB01-AT-010`
- 허용 파일:
  - `LumenGG/battlelog/game/drafts.py`
  - `LumenGG/battlelog/game/review.py`
  - `LumenGG/battlelog/test_automatic_engine.py`

작업 전 브랜치와 HEAD가 위와 같고 worktree가 clean인지 확인한다. 다르면 파일을
되돌리거나 삭제하지 말고 통합 세션에 보고한다. 앞선 `CB01-AT-035/036`은 결과
커밋이 확인되지 않아 여전히 미통합이지만, 이 세션의 수정 범위에는 포함하지 않는다.

## 구현·검토 계약

운영 DB의 카드 원문, `detail_text`, 연결 Q&A를 읽기 전용으로 확인한다. 카드별
정의·전용 검토기·테스트만 최소 블록으로 추가하고 공통 엔진, 스키마, 문서와 메인
worktree는 수정하지 않는다. `CB01-AT-006/008`의 복합 효과와
`CB01-AT-010`의 `combo_rules`를 설명용 노드가 아니라 실제 엔진 상태 변화로
검증한다. 공통 지원이 부족하면 우회하지 말고 실패 재현과 필요한 인터페이스를
보고한다.

능력 그룹마다 최소 3개 결정적 시나리오를 작성한다. 양쪽 소유자, 조건 경계,
번호 효과 무효를 포함하고, 대상이 특정되지 않은 강제 획득·브레이크·버리기·이동은
실제 `pending_decision`으로 플레이어가 합법 후보를 선택하게 한다. 카드마다 별도
커밋을 만들고 카드별 읽기 전용 드라이런, 전체 자동 엔진 SQLite 테스트와
`git diff --check` 결과를 전달한다. 운영 DB 쓰기, `--apply`, seed, publish,
마이그레이션, merge/rebase/stash/pull은 금지한다.
