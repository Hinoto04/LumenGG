import copy

from django.db import migrations
from django.utils import timezone


# 혹한 ①은 "이 기술이 루멘 존에 존재하는 한" 적용되는 지속 효과다. 콤보 사용·1콤보 시동마다
# 유발되어 효과 순서 선택과 발동 연출이 반복되던 두 능력을, 콤보에 쓰인 [부쿠키] 기술
# 데미지를 한 번씩 올리는 지속 효과 하나로 바꾼다.
CODE = 'CB04-AT-012'
ABILITY_ID = 'cb04-at-012-n1'
STARTER_ID = 'cb04-at-012-n1-starter'
LABEL = '이 기술이 루멘 존에 존재하는 한, 콤보 시 [부쿠키] 기술 데미지+100'
CONTINUOUS_FIELDS = {
    'kind': 'effect', 'mode': 'continuous', 'timing': 'function',
    'active_zones': ['lumen'],
    'effects': [{
        'op': 'modify_stat', 'player': {'controller': True}, 'scope': 'player_cards',
        'where': {'character_key': '부쿠키', 'is_technique': True, 'combo_member': True},
        'stat': 'damage', 'amount': 100, 'duration': 'continuous',
    }],
}
TRIGGERED_FIELDS = {
    'kind': 'effect', 'mode': 'mandatory', 'timing': 'use',
    'active_zones': ['lumen'], 'trigger': {'event': 'use'},
    'condition': {'op': 'all', 'conditions': [
        {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
        {'op': 'equals', 'left': 'context.combo', 'right': True},
        {'op': 'card_matches', 'card': {'path': 'context.event_card'},
         'where': {'character_key': '부쿠키', 'is_technique': True}},
    ]},
    'effects': [{
        'op': 'modify_stat', 'player': {'controller': True}, 'target_card': 'event_card',
        'stat': 'damage', 'amount': 100, 'duration': 'battle',
    }],
}
STARTER = {
    'id': STARTER_ID, 'label': LABEL, 'kind': 'effect', 'mode': 'mandatory',
    'timing': 'combo', 'visibility': 'public', 'draft': False, 'draft_text': LABEL,
    'draft_compiled': True, 'active_zones': ['lumen'], 'trigger': {'event': 'combo'},
    'limit': {'scope': 'turn', 'max': 1, 'key': STARTER_ID, 'per_event_card': True},
    'condition': {'op': 'all', 'conditions': [
        {'op': 'equals', 'left': 'context.event_controller', 'right': {'controller': True}},
        {'op': 'equals', 'left': 'context.combo_number', 'right': 1},
        {'op': 'card_matches', 'card': {'path': 'context.event_card'},
         'where': {'character_key': '부쿠키', 'is_technique': True}},
    ]},
    'effects': copy.deepcopy(TRIGGERED_FIELDS['effects']),
}


def _apply(ability, fields, drop):
    for key in drop:
        ability.pop(key, None)
    ability.update(copy.deepcopy(fields))


def _update(apps, forwards):
    Card = apps.get_model('card', 'Card')
    for card in Card.objects.filter(code=CODE):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        abilities = definition.get('abilities') or []
        main = next((a for a in abilities if a.get('id') == ABILITY_ID), None)
        if main is None:
            continue
        starter = next((a for a in abilities if a.get('id') == STARTER_ID), None)
        if forwards:
            if main.get('mode') == 'continuous' and starter is None:
                continue
            _apply(main, CONTINUOUS_FIELDS, ('trigger', 'condition', 'limit'))
            if starter is not None:
                abilities.remove(starter)
                main.setdefault('source_refs', copy.deepcopy(starter.get('source_refs')))
        else:
            if main.get('mode') != 'continuous':
                continue
            _apply(main, TRIGGERED_FIELDS, ())
            if starter is None:
                restored = copy.deepcopy(STARTER)
                if main.get('source_refs'):
                    restored['source_refs'] = copy.deepcopy(main['source_refs'])
                abilities.insert(abilities.index(main) + 1, restored)
        card.effect_definition = definition
        card.effect_revision = int(card.effect_revision or 0) + 1
        card.effect_updated_at = timezone.now()
        card.save(update_fields=['effect_definition', 'effect_revision', 'effect_updated_at'])


def forwards(apps, schema_editor):
    _update(apps, True)


def backwards(apps, schema_editor):
    _update(apps, False)


class Migration(migrations.Migration):
    dependencies = [('card', '0040_providence_combo_time')]
    operations = [migrations.RunPython(forwards, backwards)]
