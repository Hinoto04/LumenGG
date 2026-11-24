import copy

from django.db import migrations
from django.utils import timezone


# 섭리의 궤 ①의 "이 효과는 콤보 타임 중에는 적용하지 않는다": 콤보 판정이 난 1콤보 기술의
# 남은 처리(키메라의 사용 후 브레이크 등)도 콤보 타임 중이다(룰 8.1.1). 엔진이 그 구간에
# engine.combo_time을 표시하므로 조건에 추가한다.
CODE = 'CB02-AT-002'
ABILITY_ID = 'cb02-at-002-n1'
NOT_COMBO_TIME = {
    'op': 'not_equals', 'left': {'path': 'engine.combo_time'}, 'right': True,
}


def _update(apps, add):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        for ability in definition.get('abilities') or []:
            if ability.get('id') != ABILITY_ID:
                continue
            conditions = ((ability.get('condition') or {}).get('conditions'))
            if not isinstance(conditions, list):
                continue
            present = NOT_COMBO_TIME in conditions
            if add and not present:
                conditions.append(copy.deepcopy(NOT_COMBO_TIME))
                changed = True
            elif not add and present:
                conditions.remove(NOT_COMBO_TIME)
                changed = True
        if changed:
            card.effect_definition = definition
            card.effect_revision = int(card.effect_revision or 0) + 1
            card.effect_updated_at = timezone.now()
            card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _update(apps, True)


def backwards(apps, schema_editor):
    _update(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0039_divertissement_own_speed')]
    operations = [migrations.RunPython(forwards, backwards)]
