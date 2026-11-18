from django.db import migrations


# 무영 특성 「밤까치」(RFS-PS-001)에서도 핀프와 같은 보호막 조작을 사용한다.
# 기존 값 false는 deck.0016 시드가 핀프 외 캐릭터에 일괄로 넣은 기본값이다.
MUYEONG_TRAIT_CODE = 'RFS-PS-001'


def _set_shield(apps, enabled):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=MUYEONG_TRAIT_CODE):
        config = dict(card.trait_config or {})
        if config.get('supports_shield') is enabled:
            continue
        config['supports_shield'] = enabled
        card.trait_config = config
        card.save(update_fields=['trait_config'])


def apply(apps, schema_editor):
    _set_shield(apps, True)


def revert(apps, schema_editor):
    _set_shield(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0033_bukuki_trait_passive_ui')]
    operations = [migrations.RunPython(apply, revert)]
