from django.db import migrations
from django.utils import timezone


# 나찰파쇄열권 ② "콤보 타임 종료 시, 배틀 존의 모든 기술을 브레이크한다"는 자신의 배틀 존
# 기술만 대상으로 한다. 상대 배틀 존 기술까지 브레이크하던 선택 범위를 자신으로 좁힌다.
CODE = 'CB02-AT-038'
ABILITY_ID = 'cb02-at-038-n2'
OWN = {'controller': True}


def _selectors(definition):
    for ability in definition.get('abilities') or []:
        if ability.get('id') != ABILITY_ID:
            continue
        for effect in ability.get('effects') or []:
            inner = effect.get('effect') or {}
            if effect.get('op') == 'schedule' and inner.get('op') == 'break_card':
                selector = inner.get('selector')
                if isinstance(selector, dict) and 'battle' in (selector.get('zones') or []):
                    yield selector


def _update(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for selector in _selectors(definition):
            if forwards and selector.get('player') == 'any':
                selector['player'] = dict(OWN)
                changed = True
            elif not forwards and selector.get('player') == OWN:
                selector['player'] = 'any'
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
    dependencies = [('card', '0042_bukuki_lumen_combo_unlimited')]
    operations = [migrations.RunPython(forwards, backwards)]
