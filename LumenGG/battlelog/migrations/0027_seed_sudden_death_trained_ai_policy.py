from django.db import migrations
from django.utils import timezone


POLICY_VERSION = 'linear-selfplay-v1.3.0'
WEIGHTS = {
    'answer_rewind': 0.0,
    'bias': 0.0,
    'card_attack': 1.09275,
    'card_damage': 0.212984,
    'card_defense': 0.210831,
    'card_speed': 1.106311,
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
    'seed': 'sudden-fixed-selfplay-20260818',
    'generations': 3,
    'candidates_per_generation': 4,
    'games_per_candidate': 8,
    'evaluation_games': 40,
    'evaluation_method': 'paired_seats_same_seed',
    'selected': 'evolved',
    'evaluation': {
        'wins': 17,
        'losses': 16,
        'draws': 7,
        'incomplete': 0,
        'average_commands': 103.7,
        'score': 0.5125,
    },
    'history': [
        {'generation': 1, 'wins': 2, 'losses': 2, 'draws': 4, 'incomplete': 0, 'average_commands': 103.0, 'score': 0.5},
        {'generation': 2, 'wins': 3, 'losses': 3, 'draws': 2, 'incomplete': 0, 'average_commands': 104.0, 'score': 0.5},
        {'generation': 3, 'wins': 3, 'losses': 3, 'draws': 2, 'incomplete': 0, 'average_commands': 102.0, 'score': 0.5},
    ],
    'note': '서든데스 규칙 보정 후 좌석을 교대한 40경기 최종 평가로 v1.2 정책을 상회함.',
}


def seed_trained_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(is_active=True).update(is_active=False)
    Policy.objects.update_or_create(
        version=POLICY_VERSION,
        defaults={
            'name': 'Lumen AI',
            'algorithm': 'linear_v1',
            'weights': WEIGHTS,
            'metrics': METRICS,
            'training_games': 160,
            'is_active': True,
            'activated_at': timezone.now(),
        },
    )


def remove_trained_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(version=POLICY_VERSION).delete()
    Policy.objects.filter(version='linear-selfplay-v1.2.0').update(
        is_active=True,
        activated_at=timezone.now(),
    )


class Migration(migrations.Migration):

    dependencies = [('battlelog', '0026_seed_trained_ai_policy')]

    operations = [migrations.RunPython(seed_trained_policy, remove_trained_policy)]
