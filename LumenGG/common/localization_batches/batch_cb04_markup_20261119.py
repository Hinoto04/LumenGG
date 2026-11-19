"""CB04 공개 카드 원문·번역의 용어를 변환 표기(``[[kind:slug]]``)로 바꾼다(2026-11-19).

CB04 배치(0023~0027)는 [부쿠키]·[불씨]·「서리」 같은 키워드를 언어별 괄호
문자열로 저장해, 다른 카드처럼 ``[[character:부쿠키]]``·``[[token:ember]]``·
``[[state:frost]]``로 렌더링되지 않았다. 같은 공개분의 「개러지」 토큰을 쓰는
DFR-AT-017도 함께 바꾼다. 새 용어 ``state.frost``와 ``token.garage``를 추가한다.

변환 결과는 ``convert_localized_references``의 결과를 검토해 고정한 값이다.
현재 텍스트가 변환 전 값과 정확히 같을 때만 바꾸므로, 그 사이 편집된 텍스트는
건드리지 않는다. 마이그레이션 0028 배포 후에는 이 모듈과 JSON을 수정하지 않는다.
"""

import json
from pathlib import Path


DATA = json.loads(Path(__file__).with_name('cb04_markup_20261119.json').read_text(encoding='utf-8'))
LANGUAGES = ('en', 'ja')


def _seed_terms(TranslationSource, TranslationValue, using):
    for term in DATA['terms']:
        kind = term['kind']
        source, _ = TranslationSource.objects.using(using).get_or_create(
            key=f"term.{kind}.{term['slug']}",
            defaults={
                'category': kind, 'source_text': term['ko'], 'field_name': kind,
                'note': f'Semantic {kind} reference; rendered with standard marks.',
                'is_active': True,
            },
        )
        for language in LANGUAGES:
            value, _ = TranslationValue.objects.using(using).get_or_create(
                source_id=source.pk, language=language,
                defaults={'text': term[language], 'data': {}, 'status': 'translated'},
            )
            if not (value.text or '').strip():
                value.text = term[language]
                value.data = {}
                value.status = 'translated'
                value.save(using=using, update_fields=['text', 'data', 'status', 'updated_at'])


def apply_markup(apps, *, using='default'):
    Card = apps.get_model('card', 'Card')
    CardTranslation = apps.get_model('card', 'CardTranslation')
    TranslationSource = apps.get_model('common', 'TranslationSource')
    TranslationValue = apps.get_model('common', 'TranslationValue')
    _seed_terms(TranslationSource, TranslationValue, using)

    cards = {
        card.code: card
        for card in Card.objects.using(using).filter(
            code__in={change['code'] for change in DATA['changes']},
        )
    }
    changed = 0
    for change in DATA['changes']:
        card = cards.get(change['code'])
        if card is None:
            continue
        field, old, new = change['field'], change['old'], change['new']
        language = change['language']
        source = TranslationSource.objects.using(using).filter(key=f'card.{card.code}.{field}').first()
        if language == 'ko':
            if (getattr(card, field) or '') == old:
                Card.objects.using(using).filter(pk=card.pk).update(**{field: new})
                setattr(card, field, new)
                changed += 1
            if source is not None and (source.source_text or '') == old:
                source.source_text = new
                source.save(using=using, update_fields=['source_text'])
            continue
        changed += CardTranslation.objects.using(using).filter(
            card_id=card.pk, language=language, **{field: old},
        ).update(**{field: new})
        if source is not None:
            for value in TranslationValue.objects.using(using).filter(
                source_id=source.pk, language=language, text=old,
            ):
                value.text = new
                value.save(using=using, update_fields=['text', 'updated_at'])
    return changed
