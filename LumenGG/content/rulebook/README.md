# 룰북 편집 안내

공개 중인 규칙 본문은 DB에서 불러오며, 권한이 있는 사용자는 `/rules/manage/`의 위지윅 편집기에서 수정합니다. 이 폴더의 Markdown은 최초 이관용 원본과 백업으로 유지합니다.

## 가장 자주 수정하는 파일

| 수정 대상 | 파일 |
| --- | --- |
| 공개 규칙 본문과 계층 | `/rules/manage/` |
| 최초 이관용 한국어 원본 | 이 폴더의 `*.md` |
| 최초 이관용 영어 원본 | `en/*.md` |
| 최초 이관용 일본어 원본 | `ja/*.md` |
| 룰북 목록 순서와 요약 | `catalog.json` |
| 공개 비주얼 가이드 | `/rules/manage/`의 룰북별 관리 화면 |
| 최초 이관용 비주얼 원본 | `visuals/*.json` |
| 비주얼 영문 번역 | `visuals/translations.en.json` |
| 비주얼 일본어 번역 | `visuals/translations.ja.json` |

규칙 본문과 비주얼 가이드는 편집기에서 저장하는 즉시 반영됩니다. 비주얼 JSON은 최초 DB 이관용 원본과 백업으로만 유지합니다.

## 최초 DB 이관

마이그레이션 후 다음 명령으로 처음 플레이 가이드, 종합 규칙서, 플로어룰의 세 언어 Markdown과 비주얼 가이드를 DB에 넣습니다.

```shell
python manage.py import_rulebooks
```

특정 DB 룰북만 가져오려면 `--slug comprehensive`처럼 지정합니다. DB에 이미 규칙이 있는 룰북은 편집 내용 보호를 위해 가져오기를 중단하며, Markdown으로 완전히 덮어쓸 때만 `--replace`를 사용합니다.

```shell
python manage.py import_rulebooks --slug comprehensive --replace
```

## 규칙 편집

- 규칙 번호는 직접 입력하지 않습니다. 같은 상위 규칙 아래에서 `우선순위`가 낮은 규칙부터 자동으로 `1`, `2`, `3` 번호가 부여됩니다.
- 하위 규칙은 상위 규칙 바로 아래에 배치되며, 형제 규칙끼리 우선순위를 비교해 `1.1`, `1.2`, `1.3`처럼 번호가 정해집니다.
- 우선순위가 같으면 먼저 생성된 규칙이 앞에 표시됩니다. 부모 또는 우선순위를 바꾸면 표시 번호도 자동으로 다시 계산됩니다.
- `참조명`은 전체 규칙에서 고유해야 합니다.
- 본문에 `[[참조명]]`을 입력하면 해당 규칙으로 이동하는 링크가 만들어집니다.
- `[[참조명|표시할 문구]]` 형태로 링크 문구를 따로 지정할 수 있습니다.
- 개별 조항처럼 목차에 보이지 않아야 하는 규칙은 `목차에 표시`를 끕니다.

기존 번호형 참조명을 의미형 참조명으로 바꾸고, 본문의 규칙 번호와 비주얼 가이드 링크까지 함께 갱신하려면 다음 명령을 사용합니다. 이전 참조명은 별칭으로 보존되므로 기존 딥링크도 계속 작동합니다.

```shell
python manage.py semanticize_rule_references
```

`import_rulebooks`로 새로 가져오는 규칙은 이 의미형 참조명 변환을 자동으로 수행합니다.

## Markdown 원본 수정

Markdown 원본은 일반 Markdown으로 작성합니다. 이 파일의 수정은 이미 DB로 이관된 공개 본문에 자동 반영되지 않으며, `import_rulebooks --replace`를 실행해야 반영됩니다. 문서 맨 위의 `---` 사이에는 제목과 갱신일 같은 정보가 들어갑니다.

```md
---
title: "루멘콘덴서 처음 플레이 가이드"
short_title: "처음 플레이 가이드"
version: "2026.06-web-revision-1"
updated: "2026-08-24"
---

# 첫 번째 제목

본문을 작성합니다.
```

- `title`: 룰북 상세 페이지 제목
- `short_title`: 룰북 목록 버튼에 표시할 짧은 제목
- `version`: 내부 버전 정보
- `updated`: 페이지에 표시할 갱신일

## 비주얼 가이드 수정

공개 비주얼 가이드는 룰북 관리 화면의 `룰북 상단 비주얼 가이드`에서 WYSIWYG로 수정합니다. 여러 가이드가 공유하는 스타일과 동작은 `비주얼 CSS/JS`에서 수정하고, 개별 가이드에만 필요한 코드는 해당 가이드의 추가 CSS/JavaScript에 작성합니다. 아래 JSON과 `visuals/common.js`는 최초 이관 원본으로만 사용합니다.

기존 DB의 비주얼 가이드만 JSON 원본으로 다시 이관하려면 다음 명령을 사용합니다.

```shell
python manage.py import_rulebook_visuals --replace
```

각 비주얼 파일의 `visuals` 배열 안에서 탭과 버튼을 수정합니다.

```json
{
  "kind": "rules",
  "title": "판정 지도",
  "summary": "탭 전체에 대한 설명",
  "href": "#chapter-2",
  "items": [
    {
      "key": "zone-rules",
      "label": "존",
      "title": "존과 공개 정보",
      "text": "버튼을 눌렀을 때 표시할 설명",
      "hint": "공개 · 순서 · 이동",
      "href": "#chapter-2"
    }
  ]
}
```

- `kind`: `field`, `cards`, `phases`, `rules` 중 하나
- `key`: CSS와 JavaScript가 항목을 구분하는 고유 이름
- `label`: 버튼이나 카드 연결선에 표시하는 짧은 이름
- `title`: 선택했을 때 오른쪽 설명 패널에 표시하는 제목
- `text`: 상세 설명
- `hint`: 버튼에 작게 표시하는 보조 문구
- `href`: 이동할 본문 위치
- `example_image`: 카드 읽기 가이드에서 사용할 카드 이미지 URL

본문 제목을 기준으로 링크하려면 문자열 대신 다음 형태를 사용합니다. 제목 앞 번호가 같은 번역 문서의 항목도 자동으로 찾습니다.

```json
"href": {
  "heading": "3. 카드의 종류와 읽는 법",
  "fallback": "#section-12"
}
```

카드 위 표시 영역은 `%` 문자열로 위치와 크기를 지정합니다.

```json
{
  "key": "card-effect",
  "label": "효과",
  "title": "효과 텍스트",
  "text": "카드 효과가 적힌 영역입니다.",
  "shape": "rect",
  "label_side": "right",
  "top": "70%",
  "left": "15%",
  "width": "70%",
  "height": "12%",
  "href": "#section-12"
}
```

- `shape`: `rect`, `circle`, `pill`
- `label_side`: `left`, `right`, `top`, `bottom`
- `top`, `left`, `right`, `bottom`: 카드 가장자리에서 떨어진 위치
- `width`, `height`: 강조 영역의 크기
- `label_gap`: 강조 영역과 바깥 라벨 사이의 거리

## 비주얼 번역 추가

한국어 비주얼 문구를 새로 추가했다면 `translations.en.json`과 `translations.ja.json`의 `translations`에 같은 한국어 문장을 키로 추가합니다.

```json
"새 한국어 문구": "New English text"
```

번역이 없으면 한국어가 그대로 표시될 수 있으므로 세 언어 화면을 함께 확인하는 것이 좋습니다.
