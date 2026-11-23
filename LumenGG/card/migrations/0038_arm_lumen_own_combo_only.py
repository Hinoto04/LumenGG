import copy

from django.db import migrations
from django.utils import timezone


# L ARM: 어질리티 핸즈 ①, R ARM: 멧서 슈나이더 ①은 루멘 존에서 '콤보 시' 유발한다.
# 루멘 존 카드는 양쪽 플레이어의 콤보를 모두 보므로 조건이 없으면 상대의 콤보에도
# 유발됐다. 다른 루멘 존 콤보 유발 카드처럼 자신의 콤보로 한정한다.
OWN_COMBO = {
    'op': 'equals', 'left': 'context.event_controller',
    'right': {'controller': True},
}
PINP_EVENT_CARD = {
    'op': 'card_matches',
    'card': {'path': 'context.event_card'},
    'where': {'character_key': 'pinp'},
}

CHANGES = {
    ('RFS-AT-015', 'rfs-at-015-n1'): (
        copy.deepcopy(OWN_COMBO),
        None,
    ),
    ('RFS-AT-018', 'rfs-at-018-n1'): (
        {'op': 'all', 'conditions': [
            copy.deepcopy(OWN_COMBO), copy.deepcopy(PINP_EVENT_CARD),
        ]},
        copy.deepcopy(PINP_EVENT_CARD),
    ),
}


def _apply(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for (code, ability_id), (new_condition, old_condition) in CHANGES.items():
        condition = new_condition if forwards else old_condition
        for card in Card.objects.filter(code=code):
            definition = card.effect_definition
            if not isinstance(definition, dict):
                continue
            changed = False
            for ability in definition.get('abilities') or []:
                if not isinstance(ability, dict) or ability.get('id') != ability_id:
                    continue
                if condition is None:
                    if 'condition' in ability:
                        ability.pop('condition')
                        changed = True
                elif ability.get('condition') != condition:
                    ability['condition'] = copy.deepcopy(condition)
                    changed = True
            if changed:
                card.effect_definition = definition
                card.effect_revision = int(card.effect_revision or 0) + 1
                card.effect_updated_at = timezone.now()
                card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _apply(apps, True)


def backwards(apps, schema_editor):
    _apply(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0037_safety_distance_lumen_trigger')]
    operations = [migrations.RunPython(forwards, backwards)]
