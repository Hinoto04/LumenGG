from django.db import migrations


CONFIGURABLE_PASSIVE_UI = {
    'template': 'battlelog/passive_ui/configurable.html',
    'css': 'battlelog/passive_ui/configurable.css',
    'js': 'battlelog/passive_ui/configurable.js',
}


PASSIVE_OPTIONS_BY_CHARACTER = {
    '니아': {
        'title': '오버 리밋',
        'controls': [
            {'type': 'toggle', 'key': 'over_limit', 'label': '오버 리밋'},
        ],
    },
    '델피': {
        'title': '다운 스탠스',
        'controls': [
            {'type': 'toggle', 'key': 'down_stance', 'label': '다운 스탠스'},
        ],
    },
    '키스': {
        'title': '예고',
        'controls': [
            {'type': 'toggle', 'key': 'notice', 'label': '예고'},
        ],
    },
    '핀프': {
        'title': '제로 슈트',
        'controls': [
            {'type': 'toggle', 'key': 'zero_suit', 'label': '제로 슈트'},
        ],
    },
    '무영': {
        'title': '청염',
        'description': '자신의 체력이 2500 이하라면 자동으로 활성화됩니다.',
        'controls': [
            {
                'type': 'status',
                'key': 'blue_flame',
                'label': '청염',
                'condition': {'type': 'hpAtMost', 'value': 2500},
                'activeText': '청염',
                'inactiveText': '대기',
            },
        ],
    },
    '비올라': {
        'title': '은연',
        'controls': [
            {'type': 'counter', 'key': 'silver_counter', 'label': '은연 카운터', 'max': 3},
        ],
    },
    '타오': {
        'title': '양과 음',
        'controls': [
            {'type': 'counter', 'key': 'yang_counter', 'label': '양 카운터', 'max': 4},
            {'type': 'counter', 'key': 'yin_counter', 'label': '음 카운터', 'max': 4},
            {
                'type': 'status',
                'key': 'harmony',
                'label': '조화',
                'condition': {'type': 'allEquals', 'keys': ['yang_counter', 'yin_counter'], 'value': 4},
                'activeText': '조화',
                'inactiveText': '대기',
            },
        ],
    },
    '요한': {
        'title': '예지',
        'controls': [
            {'type': 'counter', 'key': 'foresight_counter', 'label': '예지 카운터', 'max': 10},
        ],
    },
    '레브': {
        'title': '단검과 암야',
        'controls': [
            {'type': 'counter', 'key': 'dagger_token', 'label': '단검 토큰', 'max': 6},
            {'type': 'toggle', 'key': 'dark_night', 'label': '암야'},
        ],
    },
    '린': {
        'title': '불씨',
        'controls': [
            {'type': 'counter', 'key': 'ember_token', 'label': '불씨 토큰'},
        ],
    },
    '이제벨': {
        'title': '거미',
        'controls': [
            {'type': 'counter', 'key': 'spider_token', 'label': '거미 토큰'},
        ],
    },
    '울프': {
        'title': '하울링',
        'controls': [
            {'type': 'counter', 'key': 'howling_counter', 'label': '하울링 카운터', 'max': 5},
            {
                'type': 'thresholdAction',
                'key': 'pressure',
                'label': '위압',
                'description': '하울링 카운터가 5개일 때 발동할 수 있고, 발동 시 하울링 카운터가 초기화됩니다.',
                'requires': {'type': 'counterAtLeast', 'key': 'howling_counter', 'value': 5},
                'resetKeys': ['howling_counter'],
                'resetLabel': '하울링 카운터',
            },
        ],
    },
    '리타': {
        'title': '빛의 루멘과 역할',
        'controls': [
            {'type': 'toggle', 'key': 'light_lumen', 'label': '빛의 루멘'},
            {
                'type': 'choice',
                'key': 'rita_role',
                'label': '역할',
                'choices': [
                    {'value': 'guardian', 'label': '가디언'},
                    {'value': 'assassin', 'label': '어쌔신'},
                    {'value': 'paladin', 'label': '팔라딘'},
                ],
            },
        ],
    },
    '키메라': {
        'title': '브레이크',
        'controls': [
            {'type': 'counter', 'key': 'broken_card_count', 'label': '브레이크된 카드 수', 'unit': '장'},
        ],
    },
}


def apply_configurable_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    for name, options in PASSIVE_OPTIONS_BY_CHARACTER.items():
        for character in Character.objects.filter(name=name):
            datas = dict(character.datas or {})
            datas['battle_passive_ui'] = {
                **CONFIGURABLE_PASSIVE_UI,
                'options': options,
            }
            character.datas = datas
            character.save(update_fields=['datas'])


def remove_configurable_passive_ui(apps, schema_editor):
    Character = apps.get_model('card', 'Character')
    target_names = PASSIVE_OPTIONS_BY_CHARACTER.keys()
    for character in Character.objects.filter(name__in=target_names):
        datas = dict(character.datas or {})
        passive_ui = datas.get('battle_passive_ui')
        if (
            isinstance(passive_ui, dict)
            and passive_ui.get('template') == CONFIGURABLE_PASSIVE_UI['template']
            and passive_ui.get('css') == CONFIGURABLE_PASSIVE_UI['css']
            and passive_ui.get('js') == CONFIGURABLE_PASSIVE_UI['js']
        ):
            datas.pop('battle_passive_ui')
            character.datas = datas
            character.save(update_fields=['datas'])


class Migration(migrations.Migration):

    dependencies = [
        ('battlelog', '0002_root_passive_ui'),
    ]

    operations = [
        migrations.RunPython(apply_configurable_passive_ui, remove_configurable_passive_ui),
    ]
