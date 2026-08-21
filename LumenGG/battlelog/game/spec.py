"""Stable rule identifiers backed by the June 2026 master rulebook."""

RULEBOOK_FILENAME = '루멘콘덴서 룰북 26년6월 개정본.pdf'
RULEBOOK_SHA256 = '2A30590E2857C03FCE2FB5995029D4CEF3B5017493C8760FCFF8B92D39EC7D59'
RULEBOOK_PAGE_COUNT = 54
EFFECT_SCHEMA_VERSION = 1
ENGINE_SCHEMA_VERSION = 1

PLAYER_SIDES = ('p1', 'p2')
PHASES = ('lumen', 'ready', 'battle', 'get', 'recovery')
PUBLIC_ZONES = ('character', 'passive', 'list', 'break', 'ultimate')
PRIVATE_ZONES = ('hand', 'side')
ALL_ZONES = (*PUBLIC_ZONES, *PRIVATE_ZONES, 'battle', 'lumen')

# Page references make changes auditable without shipping the source PDF.
CORE_RULE_SOURCES = {
    'setup': {'rulebook_pages': [20, 37]},
    'phases': {'rulebook_pages': [21, 22]},
    'judgment': {'rulebook_pages': [23, 24, 25, 31, 32, 36, 43, 44]},
    'priority': {'rulebook_pages': [26, 42]},
    'break': {'rulebook_pages': [27, 48, 50]},
    'no_response': {'rulebook_pages': [27], 'qna_ids': [417, 514, 588, 589, 621, 661]},
    'combo': {'rulebook_pages': [25, 33, 34, 45, 46], 'qna_ids': [23, 25, 301, 433]},
    'catch': {'rulebook_pages': [35, 47]},
    'special_cases': {'rulebook_pages': [31, 41, 47]},
    'text_precedence': {'rulebook_pages': [48, 49]},
}

TRIGGERS = {
    'game_start', 'turn_start', 'turn_end', 'phase_start', 'phase_end', 'battle_end',
    'ready', 'battle_reveal', 'use', 'before_judgment', 'dodge', 'opponent_dodge',
    'guard', 'opponent_guard', 'hit', 'opponent_hit', 'counter',
    'opponent_counter', 'clash', 'opponent_clash', 'combo', 'combo_window', 'catch',
    'combo_end', 'opponent_combo_end', 'catch_opportunity_resolved',
    'after_judgment', 'after_use', 'damage_before', 'damage_after',
    'hp_changed', 'fp_changed', 'card_moved', 'card_broken', 'card_attached',
    'card_discarded', 'state_gained', 'state_lost', 'counter_changed',
    'ability_completed', 'speed_fixed', 'no_response', 'sudden_death_start', 'defense_over',
    'card_guess_resolved', 'grab_negated',
}

TIMING_ORDER = {
    'replacement': 0,
    'function': 10,
    'use': 20,
    'before_judgment': 30,
    'dodge': 40,
    'opponent_dodge': 41,
    'guard': 42,
    'opponent_guard': 43,
    'hit_counter': 44,
    'opponent_hit_counter': 45,
    'clash': 46,
    'opponent_clash': 47,
    'combo': 48,
    'combo_end': 49,
    'opponent_combo_end': 49,
    'result': 50,
    'after_judgment': 60,
    'after_use': 70,
    'catch': 80,
    'catch_opportunity_resolved': 81,
    'cleanup': 90,
}

ABILITY_KINDS = {'function', 'effect'}
ABILITY_MODES = {'mandatory', 'optional', 'continuous', 'replacement'}
VISIBILITIES = {'public', 'private'}

CONDITION_OPS = {
    'all', 'any', 'not', 'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte',
    'in', 'contains', 'exists', 'card_matches', 'zone_count', 'has_state',
    'counter_at_least', 'once_available', 'phase_is', 'result_is',
    'used_card', 'ability_resolved', 'battle_result',
}

VALUE_OPS = {
    'add', 'subtract', 'multiply', 'floor_divide', 'modulo', 'min', 'max',
    'clamp', 'negate', 'abs', 'zone_count', 'counter_count', 'selection_count',
    'selected_value', 'selected_card_field', 'selected_cards_field_sum',
    'zone_distinct_count', 'attached_count',
    'state_rule_value', 'memory_value', 'if',
}

PREVENT_KINDS = {
    'damage', 'ready', 'use_card', 'dodge', 'guard', 'clash',
    'combo', 'catch', 'break', 'counter_gain', 'get_card',
    'defense_rule', 'grab_negation', 'state_gain', 'state_loss',
}

EFFECT_OPS = {
    'sequence', 'conditional', 'deal_damage', 'change_hp', 'change_fp', 'reset_fp',
    'move_card', 'exchange_cards', 'draw', 'discard', 'reveal', 'hide',
    'break_card', 'break_cards', 'shuffle_zone',
    'attach_card',
    'create_token', 'delete_token', 'gain_state', 'lose_state',
    'change_counter', 'set_counter', 'limit_counter_gain', 'gain_shield',
    'grant_effect_immunity',
    'modify_stat', 'fix_speed', 'modify_damage',
    'modify_judgment', 'modify_defense_judgments',
    'prevent', 'negate', 'replace', 'skip_phase', 'repeat_phase',
    'copy_defense_judgments', 'copy_clash_judgments',
    'invalidate_battle_card',
    'guess_hand_parity', 'modify_hand_guess_categories',
    'force_ready', 'force_ready_first', 'force_designated_get',
    'skip_get', 'replace_get',
    'schedule', 'random_select', 'capture_selection', 'request_choice', 'start_combo',
    'request_amount', 'choose_effect',
    'end_combo', 'grant_catch', 'grant_flexible_use', 'end_catch', 'modify_combo',
    'modify_state_rule',
    'set_usage_limit', 'set_memory', 'emit_event',
    'end_battle', 'end_turn', 'win_game',
    'static_rule', 'log',
}

ACTION_TYPES = {
    'pass_phase', 'ready_card', 'declare_no_response', 'select_get_card', 'select_ultimate',
    'submit_decision', 'end_combo', 'play_combo_pair', 'play_combo_card',
    'decline_catch', 'play_catch_card', 'pause_clock', 'resume_clock',
    'request_rewind', 'answer_rewind', 'concede',
}

DEFAULT_EFFECT_CHOICE_SECONDS = 30
DEFAULT_READY_SECONDS = 10
MAX_RESOLUTION_STEPS = 500
MAX_EVENT_DEPTH = 64
