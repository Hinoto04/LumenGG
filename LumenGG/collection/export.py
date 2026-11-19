"""컬렉션 즐겨찾기(하트 분류) 목록 내보내기.

앱(`mobile/src/collection-export.ts`)과 같은 형식을 만든다. 둘 중 하나를 바꾸면 다른 쪽도 맞춘다.
"""
import re
from dataclasses import dataclass

from django.db.models import Case, IntegerField, When

from common.language import translated_card_field, ui_text

from .models import COLLECTION_CATEGORY_COUNT, Collected

EXPORT_FORMATS = ('txt', 'csv')
EXPORT_COLUMNS = ('name', 'code', 'rare', 'amount')
EXPORT_HEADERS = {'name': '카드명', 'code': '코드', 'rare': '레어도', 'amount': '갯수'}
CONTENT_TYPES = {'txt': 'text/plain; charset=utf-8', 'csv': 'text/csv; charset=utf-8'}
# 웹 컬렉션 목록의 custom_order와 같은 레어도 순서.
RARE_ORDER = ('N', 'SR', 'EXR', 'AN', 'AEX', 'SAR', 'SP')
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


def parse_export_options(params):
    """GET 파라미터에서 옵션을 읽는다. 열 체크박스는 체크했을 때만 '1'로 넘어온다."""
    fmt = params.get('format', 'txt')
    return ExportOptions(
        format=fmt if fmt in EXPORT_FORMATS else 'txt',
        code=params.get('code') == '1',
        rare=params.get('rare') == '1',
        amount=params.get('amount') == '1',
    )


def parse_heart(value):
    """'' 하트 전체, '1'~'5' 그 하트만. 그 밖의 값은 전체로 본다."""
    value = str(value or '').strip()
    return value if value.isdigit() and 1 <= int(value) <= COLLECTION_CATEGORY_COUNT else ''


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
        return '﻿' + '\r\n'.join(','.join(row) for row in rows) + '\r\n'
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


def favorite_export_entries(user, language, heart=''):
    """사용자가 하트를 붙인 인쇄본을 웹 컬렉션 기본 정렬(속도 순)로 모은다."""
    rows = Collected.objects.filter(user=user)
    rows = rows.filter(category=int(heart)) if heart else rows.filter(category__gte=1)
    rows = rows.select_related('card__card', 'card__pack').annotate(
        rare_order=Case(
            *[When(card__rare=rare, then=index) for index, rare in enumerate(RARE_ORDER)],
            default=len(RARE_ORDER),
            output_field=IntegerField(),
        )
    ).order_by('card__card__frame', 'card__name', 'card__pack__released', 'rare_order', 'card_id')
    entries = []
    for row in rows:
        item = row.card
        name = translated_card_field(item.card, language, 'name') if item.card else ''
        entries.append(ExportEntry(
            name=name or item.name,
            code=item.code,
            rare=item.rare,
            amount=max(0, row.amount),
        ))
    return entries
