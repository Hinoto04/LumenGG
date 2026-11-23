from django.db import migrations
from django.utils import timezone


# 디베르티스망 ②의 "속도를 무시하고 이 기술 뒤에 이을 수 있다"는 뒤에 잇는 기술의 규칙이다
# (②의 modify_combo가 처리). 카드 자신의 combo_rules에 조건 없는 ignore_speed가 있어
# 디베르티스망(13속도)을 9속 기술 뒤에도 이을 수 있었다.
CODE = 'CRS-AT-037'
OWN_IGNORE_SPEED = {'ignore_speed': True, 'numbered_effect': True}


def fixed_rules(rules):
    return [rule for rule in rules or [] if rule != OWN_IGNORE_SPEED]


def _save(card, definition):
    card.effect_definition = definition
    card.effect_revision = int(card.effect_revision or 0) + 1
    card.effect_updated_at = timezone.now()
    card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        rules = definition.get('combo_rules') or []
        fixed = fixed_rules(rules)
        if fixed != rules:
            definition['combo_rules'] = fixed
            _save(card, definition)


def backwards(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        rules = definition.get('combo_rules') or []
        if OWN_IGNORE_SPEED not in rules:
            definition['combo_rules'] = [*rules, dict(OWN_IGNORE_SPEED)]
            _save(card, definition)


class Migration(migrations.Migration):
    dependencies = [('card', '0038_arm_lumen_own_combo_only')]
    operations = [migrations.RunPython(forwards, backwards)]
