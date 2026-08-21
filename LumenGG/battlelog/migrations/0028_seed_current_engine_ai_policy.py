from django.db import migrations
from django.utils import timezone


POLICY_VERSION = 'linear-selfplay-v1.4.0'
WEIGHTS = {
    'answer_rewind': 0.0,
    'bias': 0.0,
    'card_attack': 1.09275,
    'card_damage': 0.212984,
    'card_defense': 0.210831,
    'card_speed': 1.106311,
    'zero_damage_attack': -12.0,
    'concede': -1000.0,
    'declare_no_response': 0.2,
    'decline_catch': -0.135896,
    'end_combo': -0.385528,
    'hp_advantage_attack': 0.318104,
    'low_hp_defense': 1.005251,
    'pass_phase': 0.025854,
    'pause_clock': -50.0,
    'play_catch_card': 1.765078,
    'play_combo_card': 1.599315,
    'play_combo_pair': 1.619503,
    'ready_card': 1.253191,
    'request_rewind': -50.0,
    'resume_clock': 5.0,
    'select_get_card': 1.574042,
    'select_ultimate': 2.140599,
    'submit_decision': 0.790517,
}
METRICS = {
    'training_kind': 'deterministic_synthetic_self_play',
    'engine_verification': 'current-engine-20260818-v2',
    'seed': 'current-engine-selfplay-20260818-v2',
    'generations': 4,
    'candidates_per_generation': 4,
    'games_per_candidate': 8,
    'evaluation_games': 40,
    'evaluation_method': 'paired_seats_same_seed',
    'selected': 'bootstrap',
    'evaluation': {
        'wins': 10,
        'losses': 10,
        'draws': 20,
        'incomplete': 0,
        'average_commands': 120.0,
        'score': 0.5,
    },
    'history': [
        {'generation': 1, 'wins': 1, 'losses': 1, 'draws': 6, 'incomplete': 0, 'average_commands': 120.0, 'score': 0.5},
        {'generation': 2, 'wins': 2, 'losses': 2, 'draws': 4, 'incomplete': 0, 'average_commands': 120.0, 'score': 0.5},
        {'generation': 3, 'wins': 1, 'losses': 1, 'draws': 6, 'incomplete': 0, 'average_commands': 120.0, 'score': 0.5},
        {'generation': 4, 'wins': 3, 'losses': 3, 'draws': 2, 'incomplete': 0, 'average_commands': 120.0, 'score': 0.5},
    ],
    'baseline_benchmark': {
        'opponent_policy': 'linear-selfplay-v1.2.0',
        'games': 20,
        'wins': 7,
        'losses': 5,
        'draws': 8,
        'incomplete': 0,
        'average_commands': 120.0,
        'score': 0.55,
        'seed': 'sudden-fixed-selfplay-20260818:evaluation',
    },
    'note': (
        '0데미지 공격 반복 방지 특징을 포함해 현재 엔진에서 200경기를 다시 평가했다. '
        '새 변이 후보가 기준을 넘지 못해 검증된 가중치를 유지했으며, 별도 양 좌석 '
        '벤치마크에서는 v1.2를 상회했다.'
    ),
}


def seed_current_engine_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(is_active=True).update(is_active=False)
    Policy.objects.update_or_create(
        version=POLICY_VERSION,
        defaults={
            'name': 'Lumen AI',
            'algorithm': 'linear_v1',
            'weights': WEIGHTS,
            'metrics': METRICS,
            'training_games': 200,
            'is_active': True,
            'activated_at': timezone.now(),
        },
    )


def remove_current_engine_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(version=POLICY_VERSION).delete()
    Policy.objects.filter(version='linear-selfplay-v1.3.0').update(
        is_active=True,
        activated_at=timezone.now(),
    )


class Migration(migrations.Migration):

    dependencies = [('battlelog', '0027_seed_sudden_death_trained_ai_policy')]

    operations = [migrations.RunPython(seed_current_engine_policy, remove_current_engine_policy)]
