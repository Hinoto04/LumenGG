# 계산기 타이머 확대 · 패시브 입력 누적

2026-10-22 적용. 기존·일러스트·깔끔한 계산기에 공통 적용합니다.

## 동작

- 모바일의 10초 타이머 상자와 숫자를 키웠습니다. 안전 영역과 중앙 도구가 차지하는 높이를 빼고 남은 공간을 사용합니다. 파티·서든 데스에서는 추가 버튼 높이도 반영합니다. 양쪽 HP·FP·패시브 패널 폭은 유지합니다.
- 웹·앱의 패시브 카운터, 켜기/끄기, 효과 선택은 화면에 즉시 반영하고 **마지막 입력 후 0.9초**에 확정합니다. 같은 항목을 여러 번 바꾸면 최종값만 저장·전송합니다. 앱에서는 플레이어별 입력 대기 시간을 따로 관리합니다.
- 예: 비올라 토큰을 빠르게 세 번 누르면 바로 세 칸이 켜지고, `0 → 3` 기록 하나를 남깁니다. 리타의 레기온을 연달아 선택하면 마지막 선택을 확정합니다.
- 타오의 조화 진입·효과 선택·유지·해제, 울프 위압의 토큰 소비 등 기존 조건을 그대로 적용합니다. 함께 변해야 하는 수치는 같은 배치로 전달합니다. 기존 웹 타오의 카운터와 조화 처리도 원자적으로 묶었습니다.
- HP·FP·보호막과 다른 조작을 섞으면 먼저 입력한 패시브를 확정하고 다음 조작을 진행합니다. 되돌리기도 패시브 대기 입력을 먼저 확정합니다. 전체 초기화·서든 데스 전환·새 계산기는 미확정 입력을 비웁니다.
- 앱 로컬 계산기는 백그라운드 이동·화면 종료 때 대기 입력을 확정합니다. 공유 계산기는 연결·조작 권한을 잃으면 미전송 입력을 비우며, 재접속 때 늦게 재전송하지 않습니다. 확정된 상태와 화면 미리보기를 분리해 공유 상태 수신 중에도 대기 값이 깜박이지 않도록 했습니다.

이오몽 등 조작할 패시브가 없는 캐릭터에는 새 조작을 추가하지 않습니다. 핀프 보호막의 ±100 입력 누적과 수동 초기화 규칙도 유지합니다. 서버 대전 모델과 패시브 규칙 변경은 없습니다.

## 구현 위치

- `mobile/src/calculator-passive-queue.ts`: 900ms 대기, 같은 키 최종값 병합, 미리보기, 전송 순서와 생명 주기 처리.
- `mobile/app/calculator.tsx`: 확정 상태와 미리보기 분리, HP·FP·보호막 큐와 연결.
- `mobile/src/calculator-board.tsx`: 사용 가능한 높이에 따른 타이머 상자·숫자 크기.
- `LumenGG/static/v2/battle-calculator.js`: 웹 전송 대기와 최종값 병합, 수신 상태 위 미리보기.
- `LumenGG/static/battlelog/passive_ui/{configurable,tao}.js`: 연관 상태를 한 배치로 처리.
- `scripts/build_calculator_visuals.cjs`: 같은 패시브 입력 모델을 웹용 JS로 생성. 모델 수정 후 다시 실행합니다.

## 검증

- 모바일 타입 검사와 테스트 **80개** 통과. 새 테스트 10개는 900ms 경계, 플레이어별 대기, 타오·울프·리타, 전송 중 추가 입력, 실패·권한 해제·초기화, HP·보호막 사이의 순서를 검증합니다.
- Django/API 회귀 테스트 **47개** 통과: 보호막, 계산기 UI, 모바일 API, 파티 교전.
- 웹 **19명**의 조작 가능한 모든 패시브, 실제 WebSocket의 900ms 전송 대기, 항목당 최종값 한 번 전송, 서버 값 일치, 기존 타오와 신규 화면의 패시브 스크롤 없음 검증.
- Android 검토 에뮬레이터에서 타이머 전후 크기, 연속 입력과 기록, 타오 조화, 울프 위압, 리타 선택, 서든 데스, 기존 화면 복원 검증 통과. 이 기기에서 타이머 상자는 폭 399px을 유지하며 높이 236px → 613px(2.60배)로 확대됐습니다. 실제 크기는 화면 높이와 추가 도구에 따라 달라집니다.
- Android·iOS Expo 번들 및 Android 검토 APK 빌드 통과. iOS 실제 기기 화면은 미검증입니다.

재현 명령:

```powershell
# mobile/에서
npm run typecheck
npm test
npx expo export --platform android --platform ios --output-dir ../.temp/calculator-passive-input-export

# 저장소 루트에서: 실행 중인 검토 서버/에뮬레이터와 검토용 세션 필요
node scripts/check_calculator_passive_input.cjs
.venv/Scripts/python.exe scripts/check_android_passive_input.py
.venv/Scripts/python.exe scripts/build_calculator_passive_input_review.py
```

화면: `artifacts/calculator-character/passive-input-review.html`.
결과: `passive-input-validation.json`, `passive-input-web-report.json`, `passive-input-android-report.json`.
