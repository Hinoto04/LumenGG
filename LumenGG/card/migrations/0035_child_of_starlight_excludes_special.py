from django.db import migrations
from django.utils import timezone


# 리타 「별빛의 아이」 ①: 사이드 덱에서 성녀 효과를 가진 기술을 세트할 때
# 특수 기술(빛의 루멘 등)은 대상이 아니다.
CHILD_OF_STARLIGHT = 'DFR-AT-027'
ABILITY_ID = 'dfr-at-027-n1'
SAINTESS_TEXT = '[[state:saintess]]'


def _set_exclusion(apps, exclude):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CHILD_OF_STARLIGHT):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for ability in definition.get('abilities') or []:
            if not isinstance(ability, dict) or ability.get('id') != ABILITY_ID:
                continue
            selectors = [ability.get('availability_selector')]
            selectors += [
                effect.get('selector') for effect in ability.get('effects') or []
                if isinstance(effect, dict) and effect.get('op') == 'request_choice'
            ]
            for selector in selectors:
                where = (selector or {}).get('where')
                if not isinstance(where, dict) or where.get('text_contains') != SAINTESS_TEXT:
                    continue
                if exclude and where.get('type_not_contains') != '특수':
                    where['type_not_contains'] = '특수'
                    changed = True
                elif not exclude and 'type_not_contains' in where:
                    where.pop('type_not_contains')
                    changed = True
        if changed:
            card.effect_definition = definition
            card.effect_revision = int(card.effect_revision or 0) + 1
            card.effect_updated_at = timezone.now()
            card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _set_exclusion(apps, True)


def backwards(apps, schema_editor):
    _set_exclusion(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0034_muyeong_trait_shield')]
    operations = [migrations.RunPython(forwards, backwards)]
