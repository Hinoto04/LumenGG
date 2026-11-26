from django.db import migrations
from django.utils import timezone


# 제트팩 ① "턴당 1번 <핀프> 기술로 캐치 시"는 자신의 캐치만 대상으로 한다. 루멘 존 유발은
# 양쪽 캐치를 모두 보므로, 미러 매치에서 상대의 핀프 캐치에도 발동해 FP를 얻고 턴 1회를
# 소모하던 조건을 자신의 캐치로 좁힌다.
CODE = 'RFS-AT-017'
ABILITY_ID = 'rfs-at-017-n1'
PINP = {
    'op': 'card_matches',
    'card': {'path': 'context.event_card'},
    'where': {'character_key': 'pinp'},
}
OWN_CATCH = {
    'op': 'equals', 'left': 'context.event_controller',
    'right': {'controller': True},
}


def _update(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for ability in definition.get('abilities') or []:
            if ability.get('id') != ABILITY_ID:
                continue
            condition = ability.get('condition')
            if forwards and condition == PINP:
                ability['condition'] = {
                    'op': 'all', 'conditions': [dict(OWN_CATCH), dict(PINP)],
                }
                changed = True
            elif not forwards and condition == {
                'op': 'all', 'conditions': [OWN_CATCH, PINP],
            }:
                ability['condition'] = dict(PINP)
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
    dependencies = [('card', '0043_rasetsu_breaks_own_battle_zone')]
    operations = [migrations.RunPython(forwards, backwards)]
