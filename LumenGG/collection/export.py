"""컬렉션 목록 내보내기. 목록 화면에 적용된 검색·정렬 조건 그대로 내보낸다.

앱(`mobile/src/collection-export.ts`)과 같은 형식을 만든다. 둘 중 하나를 바꾸면 다른 쪽도 맞춘다.
"""
import re
from dataclasses import dataclass

from common.language import translated_card_field, ui_text


EXPORT_FORMATS = ('txt', 'csv')
EXPORT_COLUMNS = ('name', 'code', 'rare', 'amount')
EXPORT_HEADERS = {'name': '카드명', 'code': '코드', 'rare': '레어도', 'amount': '갯수'}
CONTENT_TYPES = {'txt': 'text/plain; charset=utf-8', 'csv': 'text/csv; charset=utf-8'}
_CSV_SPECIAL = re.compile(r'[",\r\n]')


@dataclass(frozen=True)
class ExportEntry:
    name: str
    code: str
    rare: str
    amount: int


@dataclass(frozen=True)
class ExportOptions:
    format: str = 'txt'
    code: bool = True
    rare: bool = True
    amount: bool = True

    @property
    def columns(self):
        return [key for key in EXPORT_COLUMNS if key == 'name' or getattr(self, key)]


# 목록 화면의 검색 조건 파라미터. 내보내기 폼이 숨은 값으로 그대로 넘긴다.
EXPORT_FILTER_PARAMS = ('char', 'rare', 'code', 'sortValue', 'category', 'onlyZero')


def parse_export_options(params):
    """GET 파라미터에서 옵션을 읽는다. 열 체크박스는 체크했을 때만 '1'로 넘어온다.
    code·rare는 검색 조건(팩·레어도)이 이미 쓰는 이름이라 열 옵션은 col_ 접두사를 붙인다."""
    fmt = params.get('format', 'txt')
    return ExportOptions(
        format=fmt if fmt in EXPORT_FORMATS else 'txt',
        code=params.get('col_code') == '1',
        rare=params.get('col_rare') == '1',
        amount=params.get('col_amount') == '1',
    )


def csv_field(value):
    """쉼표·따옴표·줄바꿈이 있으면 따옴표로 감싸고 안의 따옴표는 두 번 쓴다(RFC 4180)."""
    value = str(value)
    if _CSV_SPECIAL.search(value):
        return '"' + value.replace('"', '""') + '"'
    return value


def format_collection_export(entries, options, headers=None):
    """내보낼 파일 내용을 만든다.

    - csv: 엑셀에서 한글이 깨지지 않게 UTF-8 BOM으로 시작하고, 머리글 행과 CRLF 줄바꿈을 쓴다.
    - txt: 한 줄에 한 항목. 예) ``번개 [ST1-001] (SR) x2``
    """
    headers = headers or EXPORT_HEADERS
    columns = options.columns
    if options.format == 'csv':
        rows = [[csv_field(headers[key]) for key in columns]]
        rows += [[csv_field(getattr(entry, key)) for key in columns] for entry in entries]
        return '\ufeff' + '\r\n'.join(','.join(row) for row in rows) + '\r\n'
    lines = []
    for entry in entries:
        line = entry.name
        if options.code and entry.code:
            line += f' [{entry.code}]'
        if options.rare and entry.rare:
            line += f' ({entry.rare})'
        if options.amount:
            line += f' x{entry.amount}'
        lines.append(line + '\n')
    return ''.join(lines)


def export_file_name(fmt, date):
    """예) lumen-favorites-20261119.csv"""
    return f'lumen-favorites-{date:%Y%m%d}.{fmt}'


def export_headers(language):
    return {key: ui_text(label, language) for key, label in EXPORT_HEADERS.items()}


def collection_export_entries(collection, language):
    """목록 화면과 같은 queryset(검색·정렬 적용)을 내보낼 항목으로 바꾼다. 비로그인이면 갯수는 0이다."""
    entries = []
    for item in collection:
        name = translated_card_field(item.card, language, 'name') if item.card else ''
        entries.append(ExportEntry(
            name=name or item.name,
            code=item.code,
            rare=item.rare,
            amount=max(0, getattr(item, 'amount', None) or 0),
        ))
    return entries
