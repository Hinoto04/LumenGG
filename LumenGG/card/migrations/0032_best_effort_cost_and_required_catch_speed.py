from django.db import migrations
from django.utils import timezone


BEST_EFFORT_COST_CODES = {'ST4-004'}  # 키스 슈타이너: 패가 부족하면 부족한 만큼만 버린다.
# "캐치 시 N속도로 사용한다", 그리고 비용과 속도가 묶인 오더: 스팀팔로스
REQUIRED_CATCH_SPEED_CODES = {'CRS-AT-002', 'ST2-005', 'CRS-AT-017'}
ENDLESS_BALLARE_CODE = 'DFR-AT-020'
# 엔드리스 발라레 ②: 본인이 패로 가져갈 카드를 고른 뒤, 남은 배틀 존 기술을 리스트로 정리하고 처리를 잇는다.
BATTLE_CLEANUP_STEP = {
    'op': 'move_card',
    'selector': {
        'kind': 'card', 'player': 'any', 'zones': ['battle'],
        'all': True, 'where': {'is_technique': True},
    },
    'to_zone': 'list',
}


def forwards(apps, schema_editor):
    Card = apps.get_model('card', 'Card')
    updates = []
    codes = BEST_EFFORT_COST_CODES | REQUIRED_CATCH_SPEED_CODES | {ENDLESS_BALLARE_CODE}
    for card in Card.objects.filter(code__in=codes).only(
        'id', 'code', 'effect_definition', 'effect_revision', 'effect_updated_at',
    ):
        definition = card.effect_definition
        if not isinstance(definition, dict):
            continue
        changed = False
        if card.code in BEST_EFFORT_COST_CODES:
            for cost in definition.get('play_costs') or []:
                if isinstance(cost, dict) and cost.get('best_effort') is not True:
                    cost['best_effort'] = True
                    changed = True
        if card.code in REQUIRED_CATCH_SPEED_CODES:
            for rule in definition.get('catch_rules') or []:
                if (
                    isinstance(rule, dict) and rule.get('fixed_speed') is not None
                    and rule.get('speed_required') is not True
                ):
                    rule['speed_required'] = True
                    changed = True
        if card.code == ENDLESS_BALLARE_CODE:
            for ability in definition.get('abilities') or []:
                effects = ability.get('effects') if isinstance(ability, dict) else None
                if ability.get('id') != 'dfr-at-020-n2' or not isinstance(effects, list):
                    continue
                if BATTLE_CLEANUP_STEP in effects:
                    continue
                index = next((
                    i for i, effect in enumerate(effects)
                    if effect.get('selection_key') == 'dfr_at_020_opponent_recovery'
                ), None)
                if index is not None:
                    effects.insert(index, dict(BATTLE_CLEANUP_STEP))
                    changed = True
        if changed:
            card.effect_definition = definition
            card.effect_revision = int(card.effect_revision or 0) + 1
            card.effect_updated_at = timezone.now()
            updates.append(card)
    if updates:
        Card.objects.bulk_update(updates, ['effect_definition', 'effect_revision', 'effect_updated_at'])


class Migration(migrations.Migration):
    dependencies = [('card', '0031_parts_base_copies_and_drift_limit')]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
