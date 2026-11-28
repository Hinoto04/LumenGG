from django.db import migrations
from django.utils import timezone


# X-05 솔다트 ②(제로 수트 부여)와 제로 수트 해제는 카드가 움직일 때마다 조건을 확인한다.
# 상태가 이미 그렇게 되어 있어도 발동해, 로그에 X-05 솔다트 효과가 카드 이동마다 남았다.
# 상태가 실제로 바뀔 때만 발동하도록 조건에 현재 상태를 더한다.
CODE = 'RFS-PS-002'
HAS_ZERO_SUIT = {
    'op': 'has_state', 'player': {'controller': True}, 'state': 'zero_suit',
}
ZERO_PARTS = {
    'op': 'zone_count', 'player': {'controller': True},
    'zone': 'lumen', 'max': 0, 'where': {'token_key': 'parts'},
}
CLEAR_WHEN = {
    'op': 'any',
    'conditions': [
        {
            'op': 'zone_count', 'player': {'controller': True},
            'zone': 'lumen', 'min': 1, 'where': {'token_key': 'parts'},
        },
        {
            'op': 'card_matches', 'card': {'path': 'context.source_card'},
            'where': {'numbered_effects_negated': True},
        },
    ],
}
GAIN_NEW = {
    'op': 'all',
    'conditions': [{'op': 'not', 'condition': HAS_ZERO_SUIT}, ZERO_PARTS],
}
CLEAR_NEW = {'op': 'all', 'conditions': [HAS_ZERO_SUIT, CLEAR_WHEN]}
CHANGES = {
    'rfs-ps-002-n2': (ZERO_PARTS, GAIN_NEW),
    'rfs-ps-002-zero-suit-clear': (CLEAR_WHEN, CLEAR_NEW),
}


def _update(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for ability in definition.get('abilities') or []:
            pair = CHANGES.get(ability.get('id'))
            if not pair:
                continue
            old, new = pair if forwards else pair[::-1]
            if ability.get('condition') == old:
                ability['condition'] = {**new}
                changed = True
        if not changed:
            continue
        card.effect_definition = definition
        card.effect_revision = int(card.effect_revision or 0) + 1
        card.effect_updated_at = timezone.now()
        card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _update(apps, True)


def backwards(apps, schema_editor):
    _update(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0044_jetpack_own_catch_only')]
    operations = [migrations.RunPython(forwards, backwards)]
