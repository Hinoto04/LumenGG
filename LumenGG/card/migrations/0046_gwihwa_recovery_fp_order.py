from django.db import migrations
from django.utils import timezone


# 귀화 ②의 리커버리 FP는 리커버리 페이즈 시작 때 다른 효과보다 먼저 처리되어,
# 밤까치 ③으로 귀섬을 루멘 존에 놓기 전에 장수를 세었다(대부분 0FP).
# 같은 시점의 효과이므로 다른 유발 효과와 함께 해결 순서를 고르게 한다(종합 규칙 6.4.1).
CODE = 'CB03-AT-027'
ABILITY_ID = 'cb03-at-027-n2'
LABEL = '귀화 ②: 루멘 존의 [[card:RFS-AT-002]] 1장당 1FP를 얻는다. (최대 3)'


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
            for effect in ability.get('effects') or []:
                if effect.get('op') != 'schedule':
                    continue
                if forwards and not effect.get('order_with_triggers'):
                    effect['order_with_triggers'] = True
                    effect['label'] = LABEL
                    changed = True
                elif not forwards and 'order_with_triggers' in effect:
                    effect.pop('order_with_triggers', None)
                    effect.pop('label', None)
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
    dependencies = [('card', '0045_x05_zero_suit_fires_on_change_only')]
    operations = [migrations.RunPython(forwards, backwards)]
