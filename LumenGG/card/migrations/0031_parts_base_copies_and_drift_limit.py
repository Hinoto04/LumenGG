from django.db import migrations
from django.utils import timezone


DRIFT_CONVERSION_CODE = 'CRS-AT-054'
DRIFT_CONVERSION_ABILITY = 'crs-at-054-n1'
TURN_LIMIT = {'scope': 'turn', 'max': 1}


def _allow_parts_in_base_deck(definition):
    """Parts는 핀프 기술이므로 기본 20장에도 들어갈 수 있다.

    특성이 만든 추가 4장 슬롯은 20장을 넘는 Parts에만 쓰이도록
    ``allow_base_copies``를 켠다.
    """
    changed = False
    for supplement in (definition.get('deck_rules') or {}).get('supplements') or []:
        if (
            isinstance(supplement, dict)
            and supplement.get('where') == {'token_key': 'parts'}
            and supplement.get('allow_base_copies') is not True
        ):
            supplement['allow_base_copies'] = True
            changed = True
    return changed


def _limit_drift_conversion(definition):
    """사이드의 드리프트 컨버전 여러 장이 한 턴에 함께 발동하지 않게 한다."""
    changed = False
    for ability in definition.get('abilities') or []:
        if (
            isinstance(ability, dict)
            and ability.get('id') == DRIFT_CONVERSION_ABILITY
            and ability.get('limit') != TURN_LIMIT
        ):
            ability['limit'] = dict(TURN_LIMIT)
            changed = True
    return changed


def forwards(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    updates = []
    rows = Card.objects.filter(code__icontains='PS') | Card.objects.filter(code=DRIFT_CONVERSION_CODE)
    for card in rows.only('id', 'code', 'effect_definition', 'effect_revision', 'effect_updated_at').iterator():
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = _allow_parts_in_base_deck(definition)
        if card.code == DRIFT_CONVERSION_CODE:
            changed = _limit_drift_conversion(definition) or changed
        if not changed:
            continue
        card.effect_definition = definition
        card.effect_revision = int(card.effect_revision or 0) + 1
        card.effect_updated_at = timezone.now()
        updates.append(card)
    if updates:
        Card.objects.bulk_update(
            updates, ['effect_definition', 'effect_revision', 'effect_updated_at'],
        )


class Migration(migrations.Migration):
    dependencies = [('card', '0030_card_trait_config')]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
