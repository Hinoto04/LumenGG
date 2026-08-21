from django.db import migrations
from django.utils import timezone


POLICY_VERSION = 'linear-selfplay-v1.2.0'
WEIGHTS = {
    'answer_rewind': 0.0,
    'bias': 0.0,
    'card_attack': 0.842678,
    'card_damage': 0.141739,
    'card_defense': 0.134003,
    'card_speed': 0.296731,
    'concede': -1000.0,
    'declare_no_response': 0.2,
    'decline_catch': -0.027092,
    'end_combo': -0.192863,
    'hp_advantage_attack': 0.350087,
    'low_hp_defense': 0.800068,
    'pass_phase': 0.177016,
    'pause_clock': -50.0,
    'play_catch_card': 1.697907,
    'play_combo_card': 1.547716,
    'play_combo_pair': 1.874437,
    'ready_card': 1.332807,
    'request_rewind': -50.0,
    'resume_clock': 5.0,
    'select_get_card': 1.418428,
    'select_ultimate': 2.242129,
    'submit_decision': 0.619423,
}
METRICS = {
    'training_kind': 'deterministic_synthetic_self_play',
    'seed': 'corrected-selfplay-20260818',
    'generations': 4,
    'candidates_per_generation': 4,
    'games_per_candidate': 6,
    'evaluation_games': 40,
    'evaluation_method': 'paired_seats_same_seed',
    'selected': 'evolved',
    'evaluation': {
        'wins': 19,
        'losses': 17,
        'draws': 4,
        'incomplete': 0,
        'average_commands': 115.2,
        'score': 0.525,
    },
    'history': [
        {'generation': 1, 'wins': 3, 'losses': 3, 'draws': 0, 'incomplete': 0, 'average_commands': 108.0, 'score': 0.5},
        {'generation': 2, 'wins': 4, 'losses': 2, 'draws': 0, 'incomplete': 0, 'average_commands': 108.0, 'score': 2 / 3},
        {'generation': 3, 'wins': 3, 'losses': 3, 'draws': 0, 'incomplete': 0, 'average_commands': 108.0, 'score': 0.5},
        {'generation': 4, 'wins': 3, 'losses': 3, 'draws': 0, 'incomplete': 0, 'average_commands': 108.0, 'score': 0.5},
    ],
    'note': '정리 규칙 수정 후 같은 시드에서 좌석을 교대한 40경기 최종 평가로 기준 정책을 상회함.',
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
    Policy.objects.filter(version='linear-selfplay-v1.0.0').update(
        is_active=True,
        activated_at=timezone.now(),
    )


class Migration(migrations.Migration):

    dependencies = [('battlelog', '0025_seed_bootstrap_ai_policy')]

    operations = [migrations.RunPython(seed_trained_policy, remove_trained_policy)]
