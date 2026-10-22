# 선택형 캐릭터 계산기

기존 계산기와 캐릭터 계산기는 같은 세션·토큰·이벤트·HP/FP 입력 큐를 사용합니다. UI 선택은 표시 방식이며 서버 세션 모델에는 저장하지 않습니다.

## 진입과 호환

- 웹 시작 화면에서 기존/캐릭터 UI를 선택합니다. 앱 홈과 파티 진입에는 선택 시트가 표시됩니다.
- 기존 URL과 알 수 없는 UI 값은 기존 화면으로 열립니다. 신규 화면은 `?ui=character`를 사용합니다.
- 대회와 파티의 계산기 열기는 `?choose_ui=1` 선택 화면을 거칩니다. 기존 직접 링크는 계속 기존 화면으로 열립니다.
- 공유 및 최근 접속 링크는 선택한 UI를 유지합니다. 최근 목록은 같은 경로의 UI 차이를 중복 세션으로 저장하지 않습니다.
- 대전 도중 UI 전환 버튼은 없습니다. 같은 세션 링크를 다른 표시 방식으로 열어도 HP·FP·패시브·기록을 초기화하지 않습니다.

## 화면과 규칙

- 기존 웹 템플릿을 상속한 신규 템플릿에서만 신규 CSS·연출을 로드합니다. 기존 화면에는 신규 그래픽 요청이 없습니다.
- 신규 웹·앱 패시브는 전용 화면과 같은 순수 상태 어댑터를 사용합니다. DB의 패시브 HTML·CSS·JS를 실행해 화면을 만들지 않습니다. 기존 passiveActions, 조건 판정, 입력 큐와 세션 액션은 함께 사용합니다.
- 신규 앱 보드는 지연 로딩하며 배경·문양은 앱 번들에 포함합니다. 구형 카탈로그와 저장 데이터는 캐릭터 ID로 기본 테마를 찾고, 미지원 캐릭터는 중립 화면을 사용합니다.
- 테마 고유색과 HP 상태색을 분리합니다. 신규 그래픽은 텍스트·버튼 아래 보호 레이어와 함께 표시됩니다.
- 발동 연출은 사용자의 입력에 따른 상태 변화에서만 재생합니다. 초기 로딩·다른 기기의 변경·재접속·되돌리기에는 발동 연출을 재생하지 않습니다. 활성 상태에는 약한 지속 장식을 표시하며 시스템 움직임 줄이기에서는 정적인 강조로 대체합니다.
- 서버·카탈로그의 선택적 `calculator_ui` 필드에는 테마 키·고유색·보조색·문양·그래픽 참조가 들어갑니다. 기존 액션 API와 DB 스키마 변경은 없습니다.

## 테마·그래픽 원본

19명 테마의 기준 데이터는 `LumenGG/content/calculator-ui.json`입니다.

- 웹 그래픽: `LumenGG/static/v2/calculator-character/<theme>/background.webp`, `emblem.png`
- 앱 그래픽: `mobile/assets/calculator-character/<theme>/` — 웹 파일과 동일한 바이트
- 패키징 도구: `scripts/build_calculator_assets.py`
- 생성 프롬프트: `artifacts/calculator-character/prompts.json`
- 생성 원본 경로: `artifacts/calculator-character/generated-sources.json`

배경 19장은 imagegen 스킬의 **기본 내장 이미지 생성 도구**로 제작했습니다. 기존 캐릭터를 새로 그리지 않고, 테마별 어두운 2D 배경에 가장자리 문양과 중앙 여백을 요청했습니다. 투명 문양은 재사용 가능한 코드 도형으로 제작했습니다. 원본 배경은 색상·구도를 수정하지 않고 WebP 크기·형식만 변환했습니다.

`python scripts/build_calculator_assets.py`로 웹·앱 파일, 테마 JSON 및 정적 이미지 참조를 함께 갱신합니다. 새로 내려받은 카탈로그는 서버 메타데이터를 받고, 기존 오프라인 카탈로그도 번들 테마를 이용하므로 배포 시 DB 마이그레이션은 필요하지 않습니다.

## 검증 산출물

`artifacts/calculator-character/`에 화면 캡처와 JSON 결과를 저장합니다.

- `web-layout-report.json`: 740×360, 844×390, 1024×768, 1440×900, 390×844 배치와 기존 화면의 신규 그래픽 미로딩
- `web-interaction-report.json`: 두 UI의 동기화·누적 입력·되돌리기 및 대표 패시브 상호작용
- `web-character-*.png`, `web-pair-*.png`: 신규 화면과 대표 6명
- `web-classic-844x390.png`: 기존 화면
- `android-*.png`, `android-interaction-report.json`: 실제 Android 에뮬레이터에서 로컬 상태·대표 6명·기존 화면 복원 확인
- `web-language-*.png`, `android-language-*.png`: 한국어·영어·일본어 화면
- `review.html`: 웹과 Android의 대표 상태를 나란히 볼 수 있는 검토 페이지

브라우저 검증 스크립트는 격리된 로컬 테스트 서버와 `review-sessions.json`을 사용하며 운영 DB에는 연결하지 않습니다. 동시 브라우저 입력 검증용 SQLite 사본에는 WAL을 사용합니다. Windows의 Playwright 설치 경로는 `NODE_PATH`로 지정할 수 있습니다.


## 2026-10-17 검증 결과

- Django 계산기·수동 시뮬레이터·모바일 API 회귀 테스트 87개 통과.
- 모바일 단위 테스트 52개와 TypeScript 타입 검사 통과.
- Android/iOS Hermes 번들 생성 통과. Android 검증용 APK는 개발 키로 서명하며 운영 업로드 키를 사용하지 않았습니다.
- 웹 5개 크기에서 가로 넘침·스크립트 오류 없음. 기존 화면의 신규 그래픽 요청 없음.
- 두 UI를 동시에 연 HP 누적 입력·동기화·되돌리기, 루트 차지, 타오 조화, 무영 HP 경계, 울프 위압 초기화, 리타 역할 선택 검증 통과.
- Android 로컬 모드에서 HP 입력·되돌리기, 루트 차지, 타오 조화 진입·유지·해제, 무영 HP 2500, 울프 위압의 하울링 소모, 리타 루멘·레기온 선택을 확인했습니다. UI 인수가 없는 경로로 복원해도 같은 로컬 상태가 유지됩니다.
- 웹·앱 영어/일본어 화면을 확인하고 신규 화면의 버튼 줄바꿈·문구 및 로컬 캐릭터 이름 갱신을 보완했습니다.
- Android 네트워크를 끈 상태에서 로컬 저장 대전과 번들 장식 그래픽 복원을 확인했습니다. 웹 그래픽 요청 실패 시에도 HP·FP와 입력 화면이 유지됩니다.
- 19개 테마의 웹/앱 그래픽 바이트 일치 및 PNG 알파 채널 확인.
- iOS는 Windows 환경에서 번들 검증까지 수행하며 기기 화면 검증은 별도입니다.

Android 화면은 API 35 에뮬레이터의 2400×1080 물리 해상도에서 확인했습니다. 초기 에뮬레이터 실행 중 응답 지연이 있어 앱을 재시작한 뒤 상호작용 검증을 완료했습니다. Android 캡처는 임베디드 JS를 포함한 검증용 빌드이며, iOS 기기 화면이나 운영 배포를 뜻하지 않습니다.

## 2026-10-17 이미지 패시브 개편

- 상단 이름·아이콘을 제거하고 손패 수를 HP 상자에 합쳤습니다. 공통 자원 입력을 위로 올려 740×360에서 패시브 높이 약 188px을 확보했습니다.
- 패시브는 스크롤 뷰를 사용하지 않으며 내용을 잘라 숨기는 방식으로 맞추지 않습니다. 19명 전부에 대해 터치 버튼의 크기와 영역 안 배치를 검사합니다.
- 리타는 원본 레기온 카드 3장의 마름모 선택과 루멘 문양 점등, 타오는 양·음 세로 바와 조화 효과 선택, 비올라는 원본 토큰 문양 3개로 조작합니다.
- 1P 배경만 좌우 반전하고 캐릭터·배경의 가시성을 높였습니다.
- 전용 정의는 content/calculator-passives.json, 공통 상태 어댑터는 mobile/src/calculator-visual-model.ts입니다. node scripts/build_calculator_visuals.cjs로 웹 번들과 앱 참조를 함께 갱신합니다.
- 19명의 전용 표현 구현과 상태값 연결은 CALCULATOR_PASSIVE_DESIGN.md에 있습니다.
- 새 검증 파일은 visual-layout-report.json, visual-interaction-report.json, visual-*.png입니다. 이전 web-*.png와 android-*.png는 첫 구현 당시의 기록이며 새 비교 페이지에서는 새 캡처를 우선 보여줍니다.

- 개편 후 Django 87개·모바일 60개 테스트, 타입 검사, Android 검증 APK 및 Android/iOS Hermes 번들이 통과했습니다.
- 이미지 패시브 전용 검증은 node scripts/check_calculator_visuals.cjs, node scripts/check_calculator_visual_interactions.cjs로 실행합니다. 예전 대표 6명 회귀 스크립트 check_calculator_interactions.cjs도 새 조작에 맞게 갱신했습니다.
- Android에서는 한국어 로컬 모드의 scripts/check_android_visuals.py로 비올라·타오·리타 조작, 스크롤 없음과 기존 화면 복원을 확인했습니다.

- 기존 오프라인 카탈로그의 모든 패시브 키·카운터 상한을 보존하는 계약 검증을 추가했습니다. CMYK의 기존 모바일 잼 데이(464) 수동 카운터도 유지합니다.

- 앱의 번들 배경·문양·카드 그림은 네이티브 기본 이미지 렌더러로 표시합니다. 캐릭터 교체 시 이미지 식별자를 분리하고, 네트워크 일러스트도 새 식별자로 다시 열어 이전 그림의 잔류를 방지했습니다.

- 신규 웹 파티 화면의 공방 카운터·완료 버튼을 중앙 도구 영역으로 옮겼습니다. 740×360에서 패시브 공간 188px을 유지하는 배치를 확인했으며 기존 액션 선택자는 유지합니다.


## 대칭 자원 배치·전체 패시브 확장

- 신규 UI의 자원 행을 1P HP→FP, 2P FP→HP로 대칭 배치했습니다.
- 16명의 제안한 전용 표현을 구현했습니다. 초기 20종 도형은 2026-10-18에 생성 이미지·원작 카드 크롭으로 교체했으며 현재 웹·앱 PNG 바이트가 같습니다. 타오·리타·비올라의 기존 전용 화면도 유지합니다.
- 울프의 발톱과 중앙 문장, 레브의 단검 부채, 요한의 예지 동전과 디제스터 원은 같은 정규화 좌표로 웹·앱의 터치 영역을 배치합니다.
- 활성 요소에는 캐릭터별 불꽃·빛·전류·안개·원호·음파·반짝임을 약하게 계속 표시합니다. 장식만 변경하며 새로운 효과나 자동 계산은 없습니다.
- 앱의 지속 효과는 네이티브 Animated 드라이버로 재생하며 AppState와 움직임 줄이기 설정에 따라 멈춥니다. 웹은 숨긴 문서에서 CSS 애니메이션을 일시 중지합니다.
- scripts/check_calculator_bespoke.cjs가 19명 상태 입력·자원 대칭·터치 겹침·지속 장식의 무상태 변경·움직임 줄이기를 확인합니다.

- 최종 검증: Django 87개·모바일 60개 테스트, TypeScript 검사, Android 검증 APK와 Android/iOS Hermes 번들을 통과했습니다.
- 웹·Android 각각 19명(10개 조합)의 전용 배치와 입력을 확인했습니다. 웹은 740×360에서 활성 상태의 터치 겹침·패시브 스크롤이 없으며 추가 4개 크기도 통과했습니다.
- 웹 지속 효과가 재생되는 동안 서버 수치가 유지되고, Android에서도 두 프레임의 패시브 영역이 바뀌면서 수치는 유지됨을 확인했습니다. 양쪽 움직임 줄이기는 정적인 강조를 표시합니다.
- 40개 활성·비활성 PNG의 웹·앱 바이트가 일치합니다. 비교 갤러리는 artifacts/calculator-character/review.html, 실제 CSS 지속 효과 미리보기는 ambient-preview.html입니다.
- Android 전체 조합 검증은 scripts/check_android_bespoke.py입니다. UIAutomator가 갱신에 실패하면 이전 XML을 사용하지 않고 제한적으로 재시도 후 실패하도록 검증 도구를 보완했습니다.
- 상세 결과: bespoke-report.json, android-bespoke-report.json, android-ambient-report.json, bespoke-assets-report.json, visual-validation-summary.json. iOS는 번들 검증이며 실기기 화면 검증은 수행하지 않았습니다.


## 2026-10-18 아이콘 이미지 품질 개편

기존 코드 도형 20종은 현재 화면에서 사용하지 않습니다. 10종의 생성 이미지와 10종의 원작 카드 크롭으로 교체했습니다. 리타·비올라의 기존 원작 카드 그림과 타오의 조화 조작은 유지합니다.

- 내장 image_gen 도구로 생성: 중립 문장, 차지 코어, 발톱, 불씨, 카드 파편, 청염 검, 개러지 도구, 거미, 예지 문양, 단검. 원작 모티프 참고 이미지 5개를 프롬프트와 함께 기록했습니다.
- 원작 카드 직접 크롭: 오버 리밋(ST1-PS1), 다운 스탠스(ST3-PS1), 예고(ST4-PS1), 위압(ST5-PS1), 장막을 두른 칼날(AWL-PS-001), 서드아이(CRS-PS-002), 오목눈이 영물(CB01-PS-001), X-05 솔다트(RFS-PS-002), 잼 데이(DFR-PS-001), 하이텐션(CB03-PS-001).
- 최종 파일: LumenGG/static/v2/calculator-character/symbols/*-v2.png, mobile/assets/calculator-character/symbols/*-v2.png. 512×512 RGBA이며 양쪽 바이트가 같습니다.
- 단일 정의: LumenGG/content/calculator-symbol-art.json. 카드 출처·크롭 좌표와 생성 이미지 원본 경로를 기록합니다.
- 생성 원본·프롬프트: artifacts/calculator-character/raster-sources/generated/, raster-sources/imagegen-prompts.json. 기본 내장 도구를 사용했으며 CLI/API 대체 경로는 사용하지 않았습니다.
- 패키징: NODE_PATH에 워크스페이스 sharp 런타임을 지정하고 node scripts/build_calculator_symbols.cjs를 실행한 뒤 node scripts/build_calculator_visuals.cjs를 실행합니다. 기호를 코드로 그리는 이전 방식은 재실행하지 않습니다.
- 활성·비활성에 같은 원본을 사용하고 표시 밝기로 구분합니다. 버전이 들어간 파일명으로 웹 캐시와 앱 번들 그림의 혼동을 방지합니다.
- 비교: artifacts/calculator-character/raster-assets.html, 실제 장식 움직임: ambient-preview.html. 이전 그림은 비교용으로만 남고 현재 런타임 참조에는 포함하지 않습니다.


- 이미지 개편 검증: 모바일 60개 테스트와 타입 검사, 웹 19명·5개 크기, Android 19명의 입력·배치, Android/iOS 번들 내 새 PNG 20종 실제 포함을 확인했습니다.
- 새 파일은 모두 512×512 RGBA이며 웹·앱 바이트가 같습니다. 실제 카드의 직접 크롭과 생성 에셋을 출처별로 구분합니다. 최종 검증은 artifacts/calculator-character/raster-validation.json, 플랫폼별 실제 포함은 raster-bundle-report.json에 기록합니다.
- iOS는 번들 검증이며 실기기 화면 검증은 수행하지 않았습니다.

## 2026-10-19 후속 이미지·배치 수정

- 키스: ST4-PS1의 예고장만 분리하고, 원본에서 가려지거나 잘린 모서리를 내장 image_gen 편집으로 복원했습니다. 384×512 투명 PNG를 contain으로 표시해 네 모서리와 카드 전체를 보존합니다. 기존 notice 상태에 따라 점등·소등하며 발동·지속 효과를 유지합니다.
- 레브: 초승달과 밤의 장막을 별도로 생성했습니다. dark_night 상태와 연결하며 단검 토큰과 분리합니다.
- 요한: 새 은색 동전은 foresight_counter 10칸에 사용합니다. 이전 붉은 눈 PNG는 바이트 변경 없이 disaster_one 전용으로 옮겼습니다. 중앙 스위치 76px와 위·아래 동전 44px가 겹치지 않도록 배치했습니다.
- 이오몽: 신규 UI에서 조작 정의를 비우고 빈 영역을 반환합니다. 구형 저장 데이터 364는 삭제·초기화하지 않습니다. 기존 계산기의 서버 정의는 변경하지 않습니다.
- 잼 데이: DFR-PS-001 원작 크롭을 [94,158,597,529]로 확장하고 contain으로 패키징해 네 캐릭터의 얼굴을 모두 유지합니다.
- 현재 런타임 기호는 생성·편집 13종과 원작 카드 크롭 6종입니다. 이전 에셋은 비교·출처 기록으로 남기되 번들 레지스트리에서 제외합니다.
- 생성 방식: 기본 내장 image_gen. 원본·프롬프트: artifacts/calculator-character/raster-sources/generated/{notice-v3,veil-v3,foresight-coin-v3}.png 및 raster-sources/oct19-prompts.json. 포맷·투명 여백·크롭만 Sharp로 패키징합니다.
- 최신 검증은 artifacts/calculator-character/oct19-validation.json, 화면 비교는 review.html, 개별 이미지는 raster-assets.html에 기록합니다. 이전 날짜의 검증 수치는 당시 결과입니다.

검증 완료: 모바일 타입 검사·61개 테스트, 웹 19명과 5개 크기, 이번 변경 5명의 Android 실제 입력·스크린샷, Android/iOS Hermes 번들에 현행 PNG 19종 포함 및 웹·앱 바이트 일치를 확인했습니다. iOS 기기 화면은 Windows에서 확인하지 못했습니다.

## 배경 밝기·깔끔한 스타일 후속 개선

신규 캐릭터 UI는 일러스트와 깔끔하게 표시 설정을 지원합니다. 기본 배경 밝기는 35%이며 아이콘과 수치는 어두워지지 않습니다. Android 배경 크기·패딩·캐릭터 맞춤을 웹과 통일했습니다. 자세한 동작·출처·검증은 [CALCULATOR_APPEARANCE.md](CALCULATOR_APPEARANCE.md)를 참고하세요. 이전 날짜의 화면·검증 결과는 당시 기록입니다.
