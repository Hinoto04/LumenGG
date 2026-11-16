from django.db import migrations


# 부쿠키 특성 「프로스트 베일」(CB04-PS-001)의 계산기 패시브 구성.
# - 패시브·카드로 상대에게 부여하는 「서리」 상태를 직접 켜고 끄는 토글.
# - 일부 카드가 보호막을 쓰므로 핀프(RFS-PS-002)와 같은 보호막 조작(supports_shield)을 켠다.
#   보호막 값과 동작은 battlelog/shields.py의 공용 키(finf_shield)를 그대로 사용한다.
BUKUKI_TRAIT_CODE = 'CB04-PS-001'
BUKUKI_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
    'options': {
        'title': '서리',
        'controls': [
            {
                'type': 'toggle',
                'key': 'frost',
                'label': '서리',
                'labels': {'ko': '서리', 'en': 'Frost', 'ja': '霜'},
            },
        ],
    },
}


def bukuki_trait_config(current):
    """수동으로 입력한 값은 덮어쓰지 않고 빠진 항목만 채운다."""
    config = dict(current or {})
    config.setdefault('battle_passive_ui', BUKUKI_PASSIVE_UI)
    config.setdefault('supports_shield', True)
    return config


def apply(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=BUKUKI_TRAIT_CODE):
        config = bukuki_trait_config(card.trait_config)
        if config != (card.trait_config or {}):
            card.trait_config = config
            card.save(update_fields=['trait_config'])


def revert(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=BUKUKI_TRAIT_CODE):
        config = dict(card.trait_config or {})
        if config.get('battle_passive_ui') == BUKUKI_PASSIVE_UI:
            config.pop('battle_passive_ui')
        if config.get('supports_shield') is True:
            config.pop('supports_shield')
        if config != (card.trait_config or {}):
            card.trait_config = config
            card.save(update_fields=['trait_config'])


class Migration(migrations.Migration):
    dependencies = [('card', '0032_best_effort_cost_and_required_catch_speed')]
    operations = [migrations.RunPython(apply, revert)]
