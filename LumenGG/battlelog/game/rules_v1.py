"""Machine-readable core rules with stable IDs and auditable sources.

These records describe engine policy, not card effects.  They are copied into
every immutable RulesetRelease so a historical session can explain which rule
and source governed a transition.
"""

CORE_RULES_V1 = {
    'setup.deck': {
        'source': {'rulebook_pages': [37]},
        'technique_count': 20,
        'same_name_max': 1,
        'character_mark_min': 10,
        'ultimate_min': 0,
        'ultimate_max': 1,
        'exceptions': 'character.automatic_deck_rules',
    },
    'setup.zones': {
        'source': {'rulebook_pages': [20]},
        'hand_non_special': 5,
        'list_non_special': 9,
        'remaining_zone': 'side',
        'public_order': ['character', 'passive', 'ultimate', 'hand_exchange', 'list'],
    },
    'turn.phases': {
        'source': {'rulebook_pages': [21, 22]},
        'order': ['lumen', 'ready', 'battle', 'get', 'recovery'],
    },
    'priority.get': {
        'source': {'rulebook_pages': [26, 42]},
        'compare': ['fp_desc', 'hp_desc', 'hand_count_desc'],
        'tie': 'keep_previous',
        'same_timing': 'alternate_from_priority',
        'visibility_order': ['public', 'private'],
    },
    'ready.no_response': {
        'source': {'rulebook_pages': [27], 'qna_ids': [417, 514, 588, 589, 621, 661]},
        'seconds': 10,
        'skip_get': True,
        'opponent_selects_hand_card': True,
        'virtual_results': ['hit', 'counter'],
        'disqualify_at': 3,
    },
    'battle.speed': {
        'source': {'rulebook_pages': [36, 43, 44]},
        'formula': 'max(1, effect_modified_speed - fp)',
        'condition_speed_excludes_fp': True,
        'fixed_speed_ignores': ['fp', 'later_speed_changes'],
    },
    'battle.pipeline': {
        'source': {'rulebook_pages': [36]},
        'order': [
            'use', 'before_judgment', 'capture_reference_speed', 'apply_and_reset_fp',
            'dodge', 'guard', 'win_loss', 'clash', 'result_effects', 'judgment_fp',
            'damage', 'after_judgment', 'after_use', 'combo', 'catch', 'cleanup',
        ],
    },
    'battle.clash': {
        'source': {'rulebook_pages': [25, 32, 36]},
        'both_receive_hit_result': True,
        'damage': 'positive_attack_damage_difference',
        'defense_damage': 0,
        'defense_has_hit_result': False,
    },
    'battle.grab_negation': {
        'source': {'rulebook_pages': [31, 47]},
        'cost': 'break_grab_from_hand',
        'result': 'return_battle_cards_and_repeat_ready',
    },
    'combo.core': {
        'source': {'rulebook_pages': [25, 33, 34, 45, 46], 'qna_ids': [23, 25, 301, 433]},
        'damage_penalty': '(combo_number - 1) * 100',
        'minimum_damage': 1,
        'proposal_sizes': [1, 2],
        'recheck_after_each_card': True,
        'interruptible': True,
        'mutual_result': 'each_ready_card_only_then_end_without_catch',
    },
    'catch.core': {
        'source': {'rulebook_pages': [35, 47]},
        'effect_before_fp': True,
        'order': ['use', 'catch', 'hit', 'damage', 'after_use'],
        'omits': ['before_judgment'],
    },
    'move.special': {
        'source': {'rulebook_pages': [48]},
        'allowed_zones': ['side', 'lumen', 'ultimate', 'break'],
        'invalid_destination': 'break',
    },
    'move.list_limit': {
        'source': {'qna_ids': [232, 340, 623]},
        'maximum': 14,
        'overflow': 'break',
        'replenish': False,
    },
    'defense_over': {
        'source': {'rulebook_pages': [41]},
        'consecutive_battles': 3,
        'requires': ['no_attack', 'no_damage', 'no_fp_change', 'no_effect_resolution'],
        'result': 'break_battle_cards',
    },
    'sudden_death': {
        'source': {'rulebook_pages': [41]},
        'start_hp': 1000,
        'start_fp': 0,
        'turns': 3,
        'winner': 'higher_hp',
        'simultaneous_zero_during_sudden_death': 'draw',
        'hp_floor': 0,
    },
    'effect.precedence': {
        'source': {'rulebook_pages': [48, 49]},
        'negative_before_positive': True,
        'equal_mandatory_conflict': 'first_applied_only',
        'function_text': 'unnumbered',
        'mandatory_suffix': '한다',
        'optional_suffix': '할 수 있다',
    },
}
