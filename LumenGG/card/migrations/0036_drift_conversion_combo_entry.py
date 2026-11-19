import copy

from django.db import migrations
from django.utils import timezone


# 드리프트 컨버전 ①: 콤보 타임 진입 시, 적용하면 2·3콤보를 이을 수 있을 때만 유발한다.
# 3콤보만 패에서 속도를 무시하고 잇고, 3콤보 후 콤보 타임을 종료한다.
DRIFT_CONVERSION = 'CRS-AT-054'
ABILITY_ID = 'crs-at-054-n1'
BROKEN_KEY = 'crs_at_054_source_broken'

NEW_MODIFIERS = [
    {
        'op': 'modify_combo', 'player': {'controller': True},
        'source_zones': ['hand'], 'ignore_speed': True,
        'condition': {'op': 'equals', 'left': 'context.combo_number', 'right': 3},
        'duration': 'combo',
    },
    {
        'op': 'modify_combo', 'player': {'controller': True},
        'max_combo_cap': 3, 'duration': 'combo',
    },
]


def _effects(then):
    return [
        {'op': 'break_card', 'result_key': BROKEN_KEY},
        {
            'op': 'conditional',
            'condition': {
                'op': 'gte',
                'left': {'op': 'selection_count', 'selection_key': BROKEN_KEY},
                'right': 1,
            },
            'then': copy.deepcopy(then),
            'else': [],
        },
    ]


NEW_FIELDS = {
    'trigger': {'event': 'combo_time_start'},
    'condition': {
        'op': 'equals', 'left': 'context.event_controller',
        'right': {'path': 'context.controller'},
    },
    'availability_combo_grant': {'modifiers': copy.deepcopy(NEW_MODIFIERS)},
    'effects': _effects(NEW_MODIFIERS),
}

OLD_FIELDS = {
    'trigger': {'event': 'combo_window'},
    'condition': {
        'op': 'all', 'conditions': [
            {
                'op': 'equals', 'left': 'context.event_controller',
                'right': {'path': 'context.controller'},
            },
            {'op': 'equals', 'left': 'context.combo_number', 'right': 2},
        ],
    },
    'effects': _effects([{
        'op': 'modify_combo', 'player': {'controller': True},
        'allow_zones': ['hand'], 'source_zones': ['hand'],
        'min_combo': 3, 'max_combo': 3,
        'ignore_speed': True, 'requires_followup': True,
        'end_after_use': True, 'usage_key': 'crs_at_054_followup',
        'usage_key_source_scoped': True, 'max_uses': 1,
        'usage_scope': 'battle', 'duration': 'combo',
    }]),
}


def _apply(apps, fields, remove=()):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=DRIFT_CONVERSION):
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
    _apply(apps, OLD_FIELDS, remove=('availability_combo_grant',))


class Migration(migrations.Migration):
    dependencies = [('card', '0035_child_of_starlight_excludes_special')]
    operations = [migrations.RunPython(forwards, backwards)]
