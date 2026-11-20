import copy

from django.db import migrations
from django.utils import timezone


# 세이프티 디스턴스 ①: 루멘 존에 놓인 이 카드가 '자신의 기술 사용 시' 유발한다.
# 기존 정의는 배틀 존에서만 활성이라 실제 대전에서 한 번도 유발되지 않았다.
SAFETY_DISTANCE = 'CB03-AT-034'
ABILITY_ID = 'cb03-at-034-n1'

GUARD_CONDITION = {
    'op': 'gte', 'left': 'context.opponent_card.guard', 'right': -7,
}

NEW_FIELDS = {
    'active_zones': ['lumen'],
    'allow_non_source_trigger': True,
    'condition': {
        'op': 'all', 'conditions': [
            {
                'op': 'equals', 'left': 'context.event_controller',
                'right': {'path': 'context.controller'},
            },
            copy.deepcopy(GUARD_CONDITION),
        ],
    },
}

OLD_FIELDS = {
    'active_zones': ['battle'],
    'condition': copy.deepcopy(GUARD_CONDITION),
}


def _apply(apps, fields, remove=()):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=SAFETY_DISTANCE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for ability in definition.get('abilities') or []:
            if not isinstance(ability, dict) or ability.get('id') != ABILITY_ID:
                continue
            for key in remove:
                if key in ability:
                    ability.pop(key)
                    changed = True
            for key, value in fields.items():
                if ability.get(key) != value:
                    ability[key] = copy.deepcopy(value)
                    changed = True
        if changed:
            card.effect_definition = definition
            card.effect_revision = int(card.effect_revision or 0) + 1
            card.effect_updated_at = timezone.now()
            card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _apply(apps, NEW_FIELDS)


def backwards(apps, schema_editor):
    _apply(apps, OLD_FIELDS, remove=('allow_non_source_trigger',))


class Migration(migrations.Migration):
    dependencies = [('card', '0036_drift_conversion_combo_entry')]
    operations = [migrations.RunPython(forwards, backwards)]
