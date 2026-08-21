from django.db import migrations


POLICY_VERSION = 'linear-selfplay-v1.0.0'
WEIGHTS = {
    'answer_rewind': 0.0,
    'bias': 0.0,
    'card_attack': 0.35,
    'card_damage': 0.32,
    'card_defense': 0.2,
    'card_speed': 0.18,
    'concede': -1000.0,
    'declare_no_response': 0.2,
    'decline_catch': 0.1,
    'end_combo': 0.15,
    'hp_advantage_attack': 0.15,
    'low_hp_defense': 0.75,
    'pass_phase': 0.1,
    'pause_clock': -50.0,
    'play_catch_card': 1.2,
    'play_combo_card': 1.5,
    'play_combo_pair': 2.1,
    'ready_card': 1.1,
    'request_rewind': -50.0,
    'resume_clock': 5.0,
    'select_get_card': 1.0,
    'select_ultimate': 2.2,
    'submit_decision': 1.0,
}
METRICS = {
    'training_kind': 'synthetic_self_play',
    'seed': 'bootstrap-selfplay-20260818-v2',
    'generations': 6,
    'candidates_per_generation': 3,
    'games_per_candidate': 6,
    'selected': 'bootstrap',
    'evaluation': {
        'wins': 4,
        'losses': 6,
        'draws': 2,
        'incomplete': 0,
        'average_commands': 136.0,
        'score': 0.4166666666666667,
    },
    'note': '변이 후보가 안전 승격 기준을 충족하지 않아 검증된 기준 정책을 유지함.',
}


def seed_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(is_active=True).update(is_active=False)
    Policy.objects.update_or_create(
        version=POLICY_VERSION,
        defaults={
            'name': 'Lumen AI',
            'algorithm': 'linear_v1',
            'weights': WEIGHTS,
            'metrics': METRICS,
            'training_games': 156,
            'is_active': True,
        },
    )


def remove_policy(apps, schema_editor):
    Policy = apps.get_model('battlelog', 'SimulatorAIPolicy')
    Policy.objects.filter(version=POLICY_VERSION).delete()


class Migration(migrations.Migration):

    dependencies = [('battlelog', '0024_ai_and_issue_reports')]

    operations = [migrations.RunPython(seed_policy, remove_policy)]
