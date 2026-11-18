# 클라이언트 AI 계산 시제품 (Pyodide)

AI 대전의 AI 계산을 서버 대신 플레이어 브라우저에서 하는 방안을 시험했다. 서버의 엔진·AI 파이썬 모듈을 **수정 없이** Pyodide 0.29.5(WebAssembly CPython 3.13.2)의 Web Worker에서 실행해 AI 대 AI 한 판을 끝까지 돌렸다. 사람끼리 대전은 이 방안의 대상이 아니다.

측정일 2026-11-18. 같은 Windows 데스크톱 한 대에서 CPython 3.13.1과 앱 내장 브라우저(Chromium 156)로 쟀다.

## 결론

- **동작한다.** 엔진·AI 모듈 11개와 TOML 2개를 고치지 않고 그대로 브라우저에서 import 했고, AI 대 AI 한 판이 끝까지 돌았다. 같은 시드에서 CPython과 결과(명령 수·턴·승자·HP)가 완전히 같았다.
- **속도는 CPython의 약 1.5~1.6배 느리다.** 기본 수치 행렬(엔진 평가 끔)은 한 판 3.8초, 결정 한 번 10~14ms라 문제가 없다.
- **엔진 평가(`EngineReadyEvaluator`)는 지금 그대로는 너무 느리다.** 레디 결정 한 번이 데스크톱에서 평균 6.8초(p90 9.0초)다. 휴대폰 CPU는 이보다 느리므로 그대로 붙이면 AI 차례마다 십수 초를 기다리게 된다. 엔진 쪽 최적화(아래 "엔진 병목")나 시간 예산이 먼저 필요하다. 이 병목은 서버에서도 같으므로 고치면 서버 부하도 함께 준다.
- 내려받기는 처음 한 번 약 5.9MB(전송 기준)이고, 캐시가 있어도 불러오기에 약 2.4초가 걸린다(대부분 WebAssembly 초기화).

## 측정값

### 내려받기 크기

| 항목 | 원본 | 전송(압축) | 비고 |
| --- | --- | --- | --- |
| Pyodide 런타임 (`pyodide.asm.wasm`) | 8.25MiB | 2.55MiB | jsDelivr 압축 전송 |
| Pyodide 표준 라이브러리 (`python_stdlib.zip`) | 2.31MiB | 2.28MiB | zip이라 더 줄지 않음 |
| Pyodide 로더 (`pyodide.asm.js`, `pyodide.mjs`, `pyodide-lock.json`) | 1.16MiB | 0.25MiB | |
| **Pyodide 소계** | 11.7MiB | **5.07MiB** | 버전 고정 시 장기 캐시 가능 |
| 엔진·AI 모듈 11개 + TOML 2개 | 729KiB | **141KiB** (gzip) | `engine.json`으로 묶음 |
| 규칙 스냅샷 (카드 472장) | 3.43MiB | **400KiB** (gzip) | 릴리스마다 한 번. 카드 정의가 거의 전부 |
| 시작 상태 | 122KiB | **16KiB** (gzip) | 대전마다 |
| **합계(처음)** | | **약 5.6MiB (5.9MB)** | |

### 불러오기 시간

| 단계 | 처음(캐시 없음) | 다시(브라우저 캐시) |
| --- | --- | --- |
| Pyodide 런타임 로드 (`loadPyodide`) | 1.95초 | 1.70초 |
| 엔진 모듈 받기 + import(바이트코드 컴파일 포함) | 0.08초 + 0.31초 | 0.06초 + 0.28초 |
| 규칙 스냅샷 받기 + JSON 파싱 | 0.07초 + 0.21초 | 0.07초 + 0.21초 |
| **합계** | **2.68초** | **2.37~2.41초** |

- 개발 PC의 빠른 회선 기준이다. 5.9MB는 10Mbps 회선에서 약 5초가 더 든다.
- 캐시가 있어도 2.4초가 드는 것은 WebAssembly 컴파일·인스턴스화와 표준 라이브러리 준비 때문이다. 로비에 들어오면 미리 불러오는 식으로 가릴 수 있다.
- 실행 중 화면은 막히지 않는다(계산은 모두 Web Worker).

### 대전 (루트 vs 니아, 릴리스 2026.11.16-CB04, 시드 `client-ai`)

AI 대 AI라 레디 결정은 양쪽이 모두 한다. 사람 대 AI라면 AI 쪽만 하므로 판당 레디 결정 수는 절반이다.

| 실행 환경 | 엔진 평가 | 결과 | 판당 | 레디 결정 1회 평균 / p90 / 최대 | 그 밖 결정 평균 | 명령 적용 평균 | 시뮬/레디 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CPython 3.13 | 끔 | 95명령·10턴, P2 승 | 2.35초 | 8ms / 9ms / 10ms | 6.5ms | 10.9ms | - |
| Pyodide 데스크톱 창 | 끔 | 95명령·10턴, P2 승 | 3.76초 | 14ms / 16ms / 17ms | 10.3ms | 17.1ms | - |
| Pyodide 휴대폰 창(375×812) | 끔 | 95명령·10턴, P2 승 | 3.78초 | 14ms / 16ms / 19ms | 10.5ms | 17.0ms | - |
| CPython 3.13 | 켬 | 141명령·15턴, P2 승 | 205.7초 | 4.50초 / 5.69초 / 6.80초 | 6.8ms | 9.6ms | 34 |
| Pyodide 데스크톱 창 | 켬 | 141명령·15턴, P2 승 | 309.5초 | **6.78초 / 9.01초 / 9.89초** | 10.0ms | 13.8ms | 34 |
| Pyodide 휴대폰 창(375×812) | 켬 | 40명령까지(5턴) | 65.9초 | 5.39초 / 7.81초 / 7.84초 | 9.0ms | 13.7ms | 29.4 |

- 휴대폰 창은 화면 크기·UA(Android Pixel 8)만 흉내 낸 것이고 CPU는 같은 데스크톱이다. **실제 휴대폰 CPU 측정은 하지 못했다.** 중급 안드로이드에서 WebAssembly는 보통 데스크톱보다 2~4배 느리므로, 엔진 평가 레디 결정은 그대로라면 15~30초로 예상한다. 실제 기기 측정이 다음 할 일이다(Android 에뮬레이터 `Medium_Phone_API_37.0`은 호스트 CPU를 쓰므로 대신할 수 없다).
- 시뮬레이션 한 번은 CPython 약 130ms, Pyodide 약 200ms다.
- 원래 세션에서 본 "서버에서 레디 1~4초"보다 길게 나온 것은 AI 대 AI라 상대가 아는 카드가 많아 행렬 칸(시뮬레이션 34번)이 많았기 때문으로 보인다.

### 엔진 병목 (CPython cProfile, 엔진 평가 켬 앞부분 12명령)

| 함수 | 누적 비중 | 내용 |
| --- | --- | --- |
| `copy.deepcopy` | 약 46% | 시뮬레이션마다 상태 복제와 엔진 내부 복제 |
| `engine._supplied_token_cards` 안의 `walk` | 약 30% | 토큰 공급 캐시가 **엔진 인스턴스**에 붙어 있어, 시뮬레이션마다 새 엔진이 카드 472장의 효과 정의를 전부 다시 훑는다 |
| `effects.continuous_effects` / `_refresh_continuous_rules` | 약 38% (일부 겹침) | 지속 효과 재계산 |

- 시제품 드라이버는 서버의 `automatic_services.ImmutableRulesetSnapshot`과 같은 표지 클래스로 규칙을 감싼다. 이것이 없으면 엔진이 시뮬레이션마다 규칙 전체를 deepcopy 해 레디 결정이 11초(CPython)까지 늘었다. 클라이언트에 붙일 때 반드시 같은 표지를 써야 한다.
- 서버 코드 수정 제안(이 작업에서는 고치지 않음):
  1. `engine.py` `_supplied_token_cards`의 결과를 규칙 스냅샷 단위로 캐시한다(예: 불변 규칙 객체에 붙이거나 `id(ruleset)`·릴리스 버전 키 모듈 캐시). 약 30% 감소 예상. 서버·클라이언트 모두 이득.
  2. `ai_engine_eval._simulate`의 `copy.deepcopy(self.state)`와 엔진 생성자의 상태 deepcopy가 겹친다(생성자가 다시 복제). 한 번만 복제하도록 하면 복제 비용 일부가 준다.
  3. 시간 예산: 평가기가 정해진 시간(예: 1.5초)을 넘으면 남은 칸을 기본 수치로 채우는 방식. 느린 기기에서도 기다림 상한이 생긴다.

## 시제품 구성과 실행 방법

| 파일 | 역할 |
| --- | --- |
| `scripts/export_client_ai_sample.py` | 격리 개발 데이터(`.temp/play-dev/play.sqlite`)의 **임시 사본**에서 시작 상태·규칙 스냅샷·정책 가중치·AI 덱 프로필을 `.temp/client-ai/sample.json`으로 내보낸다. 설정된 DB나 개발 서버 파일에는 쓰지 않는다. |
| `play/src/pyodideLab/driver.py` | AI 대 AI 루프. `automatic_services.advance_ai_session`과 같은 방식(양쪽 결정 중 점수가 높은 쪽, 동점이면 우선권, 시간 초과 진행)으로 돌리고 결정·적용 시간을 잰다. CPython에서도 돈다. |
| `play/src/pyodideLab/worker.ts` | Web Worker. Pyodide를 불러와 엔진 모듈을 가상 파일 시스템의 `lumen_game` 패키지로 쓰고 드라이버를 실행한다. |
| `play/src/pyodideLab/main.ts`, `play/pyodide-lab.html` | 측정 화면. 결과를 표·콘솔·`window.__clientAiLab`에 남긴다. |
| `play/vite.pyodide.config.ts` | 시제품 전용 Vite 설정(포트 5176). 기존 `vite.config.ts`와 `LumenGG/static/play/` 빌드에는 영향이 없다. `/__client-ai/engine.json`(엔진 원본 묶음), `/__client-ai/sample.json`을 gzip으로 제공한다. |
| `.claude/launch.json` | 미리보기용 `pyodide-lab` 항목을 추가했다. |

```powershell
.\.venv\Scripts\python.exe scripts\export_client_ai_sample.py --p1 1 --p2 5
node play\node_modules\vite\bin\vite.js --config play\vite.pyodide.config.ts
# http://127.0.0.1:5176/pyodide-lab.html?auto=off,on  (max=40 으로 명령 수 제한)
```

CPython 기준값은 엔진 모듈 11개를 `lumen_game/` 폴더로 복사한 뒤 `PYTHONPATH=<그 상위 폴더> python play/src/pyodideLab/driver.py .temp/client-ai/sample.json`으로 잰다.

### 브라우저에 올리는 모듈

Django가 필요 없는 대전·AI 모듈만 올린다. 패키지 `__init__.py`는 빈 파일로 새로 만들었다(서버 패키지 `__init__.py`는 손대지 않음).

- 올림: `engine.py`, `effects.py`, `spec.py`, `handlers.py`, `card_identity.py`, `ai.py`, `ai_profile.py`, `ai_preview.py`, `ai_decisions.py`, `ai_matrix.py`, `ai_engine_eval.py`, `ai_effect_defaults.toml`, `ai_profile_template.toml`
- 필요 없음: `schema.py`, `rules_v1.py`, `deck_rules.py`(대전 실행 경로에서 import 하지 않음), `simulation.py`(드라이버가 대신함)
- 뺌(Django 사용 또는 검수 전용): `catalog.py`, `training.py`, `sandbox.py`, `review*.py`, `drafts*.py`
- import 되는 표준 라이브러리는 `copy`, `json`, `random`, `re`, `datetime`, `dataclasses`, `tomllib`, `pathlib`, `hashlib`, `itertools`, `functools` 정도로 모두 Pyodide 기본 표준 라이브러리에 들어 있다. 추가 패키지는 없다.

## 실제 대전 클라이언트에 붙이는 구조안

### 원칙

- **사람끼리 대전은 지금처럼 서버 판정만 쓴다.** 클라이언트 계산 경로는 AI 좌석이 있는 세션에서만 열린다.
- **서버 계산은 설정으로 유지한다.** 운영 설정(예: `SiteSettings` 또는 `LUMEN_AI_EXECUTION = 'server' | 'client' | 'auto'`)으로 고르고, 세션을 만들 때 `document['ai_execution']`에 고정한다. 진행 중인 세션은 설정이 바뀌어도 처음 방식대로 간다.
- 판정 권한은 어느 경우든 엔진이 정하는 합법 행동 안에서만 움직인다.

### 1단계(권장): 서버 판정 유지 + AI 결정만 클라이언트

서버는 지금처럼 세션 상태를 갖고 명령을 적용·방송한다(명령 적용은 10ms 안팎이라 가볍다). 무거운 부분인 AI 결정(엔진 평가 포함)만 플레이어 브라우저가 한다.

1. 세션이 `ai_execution='client'`이면 서버의 `ai_runner`는 AI 좌석을 돌리지 않는다.
2. AI 차례가 되면 서버가 플레이어 클라이언트에 AI 좌석용 데이터를 보낸다: AI 좌석 관찰(`observe(include_memory=True)`), 엔진 평가에 필요한 엔진 상태(`state`, `version`, `now`), 정책 가중치, AI 덱 프로필, 규칙 릴리스 버전. 규칙 스냅샷은 릴리스 버전으로 따로 받아 오래 캐시한다.
3. 클라이언트의 Web Worker(Pyodide)가 `choose_action`(+`EngineReadyEvaluator`)으로 결정하고, AI 좌석 명령으로 보낸다. 서버는 세션 생성 때 만든 AI 좌석 전용 토큰과 `expected_version`을 확인하고, 평소처럼 `submit_action`으로 합법성을 검사해 적용한다.
4. 일정 시간(예: 20초) 안에 명령이 오지 않거나 클라이언트가 Pyodide를 못 불러오면(구형 기기, WebView 오류) 서버가 그 결정만 대신 계산한다. 이때 엔진 평가를 끄고 기본 행렬로 계산하면 서버 부담이 작다.

장점: 기존 프로토콜·관전·리플레이·되감기·기록이 그대로다. 서버 부하에서 시뮬레이션 20~30번이 빠진다. 클라이언트가 조작해도 AI가 엔진이 허락한 합법 행동 중 하나를 고르게 될 뿐이다.

단점: 엔진 평가에 상태 전체가 필요해 **AI의 손패·덱 순서가 플레이어 브라우저로 간다.** 개발자 도구로 볼 수 있다. AI 대전은 순위·대회와 무관하므로 받아들일 만하다고 보지만, AI 대전 결과를 통계에 쓴다면 그 통계에서는 빼야 한다.

### 2단계(선택): 완전 클라이언트 판정

엔진까지 클라이언트에서 돌리고 서버는 시작 상태와 시드만 준다. 앱의 오프라인 AI 대전도 가능해진다. 다만 세션·명령·방송 계층(`automatic_services`의 명령 검증, 되감기, 준비 단계, 시계)을 클라이언트에 옮겨야 해 작업이 크다. 결과를 서버에 남겨야 하면 명령 기록을 올리고 서버가 재생해 확인한다(재생은 AI 계산 없이 명령 적용만이라 CPython 기준 한 판 1~2초).

### 배포

- Pyodide는 CDN 대신 `/static/pyodide/0.29.5/`로 직접 제공해 버전을 고정하고 외부 의존을 없앤다(CSP를 쓰면 `script-src`에 `'wasm-unsafe-eval'`이 필요하다).
- 엔진 모듈은 `build:django` 때 `ENGINE_FILES` 목록으로 묶고(zip 또는 JSON) 내용 해시를 이름에 넣는다. 서버가 세션에 엔진 묶음 해시를 알려 주고, 다르면 새로 받는다. 서버와 클라이언트 엔진 코드가 어긋나면 1단계에서는 서버가 불법 명령을 거부하고 서버 계산으로 넘긴다.
- 규칙 스냅샷은 릴리스 버전 주소로 제공하고 `immutable` 캐시를 준다. 브라우저에서 반드시 `ImmutableRulesetSnapshot`과 같은 표지로 감싼다.
- 앱(WebView)은 같은 `/battlelog/play/`를 쓰므로 그대로 따라온다. 오프라인 카탈로그에 규칙 스냅샷과 Pyodide를 넣는 것은 2단계에서 검토한다.
- CPython 테스트 하나를 추가해, `ENGINE_FILES`만 복사한 패키지로 드라이버가 한 판을 끝내는지 확인한다(엔진에 새 모듈 import가 생기면 바로 드러나도록).

## 남은 위험

1. **엔진 평가 속도.** 데스크톱 Pyodide에서 레디 결정 6.8초, 휴대폰은 더 느릴 것으로 예상한다. 엔진 최적화(토큰 공급 캐시, 이중 deepcopy)와 시간 예산 없이는 체감이 나쁘다. 실제 기기 측정을 아직 못 했다.
2. **첫 불러오기.** 처음 5.9MB, 매번 약 2.4초 초기화. 저사양·느린 회선에서는 더 길다. 로비에서 미리 불러오기가 필요하다.
3. **메모리.** Pyodide 힙 + 규칙 스냅샷(파이썬 객체로 수십 MB 예상)을 재지 않았다. iOS Safari·WebView의 WebAssembly 메모리 한도에 걸리는지 확인해야 한다.
4. **iOS·앱 WebView 호환.** 이번에는 Chromium에서만 확인했다. iOS WKWebView와 Expo 앱 WebView에서 모듈 Worker·WebAssembly 동작을 확인해야 한다.
5. **정보 노출.** 1단계는 AI 손패 등 숨은 정보를 플레이어 브라우저에 보낸다.
6. **엔진 버전 어긋남.** 서버 배포 직후 오래된 엔진 묶음을 쓴 클라이언트가 다른 판단을 한다. 해시 확인과 서버 대체 계산으로 막는다.
7. **모듈 목록 관리.** 엔진에 Django import나 새 모듈이 들어가면 브라우저에서 깨진다. 위의 CPython 테스트로 막는다.
8. **결정성.** 이번 측정에서는 CPython과 Pyodide 결과가 같았지만, 해시 순서(`set` 순회)나 부동소수 차이에 기대는 코드가 생기면 달라질 수 있다. 1단계는 서버가 판정하므로 영향이 작다.
