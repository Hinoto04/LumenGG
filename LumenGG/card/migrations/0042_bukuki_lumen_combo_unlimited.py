from django.db import migrations
from django.utils import timezone


# 블리자드 ③·아이스 블로 ②: "이번 턴 루멘 존의 [부쿠키] 기술을 콤보에 사용할 수 있다"는
# 장수 제한이 없다. usage_key가 붙어 있으면 콤보 허가가 턴당 1장으로 제한되어, 루멘 존의
# 두 번째 부쿠키 기술부터 콤보에 쓸 수 없었다.
TARGETS = {
    'CB04-AT-007': ('cb04-at-007-n3', 'cb04-at-007-lumen-combo'),
    'CB04-AT-005': ('cb04-at-005-n2', 'cb04-at-005-lumen-combo'),
}


def _grants(definition, ability_id):
    for ability in definition.get('abilities') or []:
        if ability.get('id') != ability_id:
            continue
        for effect in ability.get('effects') or []:
            if effect.get('op') == 'modify_combo' and 'lumen' in (effect.get('allow_zones') or []):
                yield effect


def _update(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for code, (ability_id, usage_key) in TARGETS.items():
        for card in Card.objects.filter(code=code):
            definition = card.effect_definition
            if not isinstance(definition, dict):
                continue
            changed = False
            for effect in _grants(definition, ability_id):
                if forwards and effect.get('usage_key') == usage_key:
                    effect.pop('usage_key')
                    changed = True
                elif not forwards and 'usage_key' not in effect:
                    effect['usage_key'] = usage_key
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
    dependencies = [('card', '0041_bitter_cold_continuous')]
    operations = [migrations.RunPython(forwards, backwards)]
