"""Presentation data for the card-effect DSL help pages.

This module intentionally imports the engine's public constants.  The reference
page can therefore report a newly-added identifier that has not yet received a
human explanation instead of silently presenting an incomplete manual.
"""

from battlelog.game.spec import (
    ABILITY_KINDS,
    ABILITY_MODES,
    ALL_ZONES,
    CONDITION_OPS,
    EFFECT_OPS,
    EFFECT_SCHEMA_VERSION,
    PHASES,
    PREVENT_KINDS,
    TIMING_ORDER,
    TRIGGERS,
    VALUE_OPS,
    VISIBILITIES,
)


def _item(name, summary, fields, note=''):
    return {
        'name': name,
        'summary': summary,
        'fields': fields,
        'note': note,
    }


TRIGGER_DETAILS = {
    'game_start': '게임 준비가 끝난 직후. 첫 턴의 turn_start/phase_start와 별개다.',
    'turn_start': '새 턴을 만들 때 발생한다.',
    'turn_end': '턴 종료가 확정될 때 발생한다.',
    'phase_start': 'context.phase에 표시된 페이즈가 시작될 때 발생한다.',
    'phase_end': 'context.phase에 표시된 페이즈가 끝날 때 발생한다.',
    'battle_end': '판정·데미지·사용 후·콤보·캐치가 끝나 배틀을 정리할 때 발생한다.',
    'ready': '해당 기술이 레디되었을 때 발생한다.',
    'battle_reveal': '양쪽 레디 기술이 공개되어 배틀 카드가 확정될 때 발생한다.',
    'use': '해당 기술을 사용하는 순간. 레디·콤보·캐치 문맥을 context.use_context로 구별한다.',
    'before_judgment': '배틀 판정 전에 발생한다. 캐치와 콤보에는 일반적으로 발생하지 않는다.',
    'dodge': '해당 기술의 사용자가 회피 판정을 만들었을 때 발생한다.',
    'opponent_dodge': '해당 기술이 상대에게 회피당했을 때 발생한다.',
    'guard': '해당 수비 기술의 사용자가 방어 판정을 만들었을 때 발생한다.',
    'opponent_guard': '해당 기술이 상대에게 방어되었을 때 발생한다.',
    'hit': '해당 기술이 히트 판정을 만들었을 때 발생한다.',
    'opponent_hit': '상대 기술의 히트 판정으로 해당 기술 사용자가 맞았을 때 발생한다.',
    'counter': '해당 기술이 상대 공격 기술을 카운터냈을 때 발생한다.',
    'opponent_counter': '해당 기술이 상대에게 카운터당했을 때 발생한다.',
    'clash': '해당 기술 쪽에서 상쇄 판정이 성립했을 때 발생한다.',
    'opponent_clash': '상대 쪽 상쇄 결과에 반응할 때 발생한다.',
    'combo': '해당 카드가 콤보 기술로 실제 사용될 때 발생한다.',
    'combo_window': '다음 콤보 기술을 고르는 창을 열거나 다시 열 때 발생한다.',
    'catch': '해당 카드가 캐치 기술로 실제 사용될 때 발생한다.',
    'combo_end': '자신의 콤보 타임이 끝날 때 발생한다.',
    'opponent_combo_end': '상대의 콤보 타임이 끝날 때 발생한다.',
    'catch_opportunity_resolved': '한 플레이어의 캐치 기회가 사용 또는 거절로 정산된 뒤 발생한다.',
    'after_judgment': '판정 FP와 데미지 처리 뒤, 판정 후 순서에 발생한다.',
    'after_use': '해당 기술의 사용 후 처리 시점에 발생한다.',
    'damage_before': '데미지가 HP에 적용되기 직전. 예방·대체가 개입할 수 있다.',
    'damage_after': '데미지가 HP에 적용된 직후 발생한다.',
    'hp_changed': '효과나 데미지로 HP 값이 바뀐 직후 발생한다.',
    'fp_changed': 'FP 값이 바뀐 직후 발생한다.',
    'card_moved': '카드가 존 사이를 이동한 직후 발생한다.',
    'card_broken': '카드가 브레이크 존으로 이동한 직후 발생한다.',
    'card_attached': '카드가 다른 카드 아래에 세트된 직후 발생한다.',
    'card_discarded': '패의 카드가 버려진 직후 발생한다.',
    'state_gained': '상태가 부여된 직후 발생한다.',
    'state_lost': '상태가 제거된 직후 발생한다.',
    'counter_changed': '카운터 수가 실제로 바뀐 직후 발생한다.',
    'ability_completed': '능력 하나의 비용·대상·명령 해결이 끝난 뒤 발생한다.',
    'speed_fixed': '기술 속도가 고정된 직후 발생한다.',
    'no_response': '레디 제한 시간 만료로 대응하지 않음이 정산될 때 발생한다.',
    'sudden_death_start': '서든 데스에 진입할 때 발생한다.',
    'defense_over': '디펜스 오버가 성립할 때 발생한다.',
    'card_guess_resolved': '상대 패의 종류/홀짝 추측과 공개가 정산된 뒤 발생한다.',
    'grab_negated': '그랩 무효가 성공한 뒤 발생한다.',
}


TIMING_DETAILS = {
    'replacement': '0 · 금지·대체를 가장 먼저 설치한다.',
    'function': '10 · 번호 없는 기능 및 공개 직후 상시 규칙.',
    'use': '20 · 사용 시.',
    'before_judgment': '30 · 판정 전.',
    'dodge': '40 · 회피 시.',
    'opponent_dodge': '41 · 상대 회피 시.',
    'guard': '42 · 방어 시.',
    'opponent_guard': '43 · 상대 방어 시.',
    'hit_counter': '44 · 히트/카운터 시.',
    'opponent_hit_counter': '45 · 상대 히트/상대 카운터 시.',
    'clash': '46 · 상쇄 시.',
    'opponent_clash': '47 · 상대 상쇄 시.',
    'combo': '48 · 콤보 시.',
    'combo_end': '49 · 자신의 콤보 타임 종료 시.',
    'opponent_combo_end': '49 · 상대 콤보 타임 종료 시.',
    'result': '50 · 그 밖의 판정 결과 처리.',
    'after_judgment': '60 · 판정 후.',
    'after_use': '70 · 사용 후.',
    'catch': '80 · 캐치 시.',
    'catch_opportunity_resolved': '81 · 캐치 기회 정산 직후.',
    'cleanup': '90 · 배틀·콤보 종료 정리.',
}


CONDITION_DETAILS = {
    'all': 'conditions의 모든 조건이 참일 때 참.',
    'any': 'conditions 중 하나 이상이 참일 때 참.',
    'not': 'condition의 결과를 반전한다.',
    'equals': 'left와 right가 같은지 비교한다.',
    'not_equals': 'left와 right가 다른지 비교한다.',
    'gt': 'left > right.',
    'gte': 'left >= right.',
    'lt': 'left < right.',
    'lte': 'left <= right.',
    'in': 'left가 right 배열에 포함되는지 확인한다.',
    'contains': 'left 배열/문자열이 right를 포함하는지 확인한다.',
    'exists': 'left 경로의 값이 None이 아닌지 확인한다.',
    'card_matches': 'card(기본값 context.source_card)가 where 카드 필터에 맞는지 확인한다.',
    'zone_count': 'player의 zone에서 where와 맞는 카드 수가 min~max인지 확인한다. exclude_source와 exclude_combo_proposed를 지원한다.',
    'has_state': 'player에게 state 상태 또는 같은 키의 지속 상태가 존재하는지 확인한다.',
    'counter_at_least': 'player의 counter 수가 value 이상인지 확인한다.',
    'once_available': 'scope(game/turn/phase/battle)의 controller별 usage key가 아직 사용되지 않았는지 확인한다.',
    'phase_is': '현재 페이즈가 phase인지 확인한다.',
    'result_is': 'context.result가 result 또는 results 중 하나인지 확인한다.',
    'used_card': '현재 턴 카드 사용 이력에서 player/where/use_context/현재 카드 조건을 만족하는 항목이 min개 이상인지 확인한다.',
    'ability_resolved': '현재 턴 능력 해결 이력에서 ability_id가 해결되었는지 확인한다. same_source로 같은 카드 인스턴스를 요구할 수 있다.',
    'battle_result': '현재 턴 배틀 결과 이력에서 player의 result(s)와 상대 카드 opponent_where를 함께 확인한다.',
}


VALUE_DETAILS = {
    'add': 'values를 모두 더한다.',
    'subtract': 'left에서 right를 뺀다.',
    'multiply': 'values를 모두 곱한다.',
    'floor_divide': 'left를 right로 내림 나눗셈한다. 0으로 나누면 default(기본 0).',
    'modulo': 'left를 right로 나눈 나머지. 0으로 나누면 default(기본 0).',
    'min': 'values 중 최솟값. 빈 배열은 검증에서 거부된다.',
    'max': 'values 중 최댓값. 빈 배열은 검증에서 거부된다.',
    'clamp': 'value를 min 이상 max 이하로 제한한다.',
    'negate': 'value의 부호를 반전한다.',
    'abs': 'value의 절댓값.',
    'zone_count': 'player의 zone에서 where에 맞는 카드 수.',
    'counter_count': 'player가 가진 counter의 현재 수.',
    'selection_count': 'selection_key에 저장된 카드 수. where를 지정하면 맞는 카드만 센다.',
    'selected_value': 'selection_key의 첫 수치 선택값. 없으면 default.',
    'selected_card_field': 'selection_key의 첫 카드에서 frame/damage/code/name/type/instance_id를 읽는다.',
    'selected_cards_field_sum': '선택된 모든 카드의 frame 또는 damage 합.',
    'zone_distinct_count': 'zone의 서로 다른 frame/code/name/type/character_id/printed_character_id 수. exclude_values와 where 지원.',
    'attached_count': 'host(기본 source_card_instance_id)에 세트된 player 카드 중 where에 맞는 카드 수.',
    'state_rule_value': 'modify_state_rule로 설치된 state/field 값을 합성한다. minimum/maximum/replace 순서를 따른다.',
    'memory_value': 'engine.effect_memory의 player/key 값을 읽고 없으면 default를 반환한다.',
    'if': 'condition이 참이면 then, 아니면 else 값 표현식을 계산한다.',
}


EFFECT_GROUPS = [
    ('흐름과 선택', [
        _item('sequence', 'effects를 배열 순서대로 실행한다.', 'effects(필수 명령 배열)'),
        _item('conditional', '조건에 따라 명령 묶음을 분기한다.', 'condition, then(필수 명령 배열), else(선택 명령 배열)'),
        _item('request_choice', '카드/플레이어 선택을 요청하고 결과를 selection_key에 저장한다.', 'player, prompt, selector, selection_key, optional=false, default(필수 선택 시 필수), then, else, skip_if_unavailable', '필수 후보가 부족하면 else 또는 중단, 선택형이면 0장 확정이 가능하다.'),
        _item('request_amount', '정수 하나를 선택하게 한다.', 'player, prompt, min, max, values, selection_key, default, then'),
        _item('choose_effect', '여러 명령 묶음 중 하나를 선택하게 한다.', 'player, prompt, optional, default, options[{id,label,condition,selector_available,effects}]', 'optional이면 선택지 1개부터 가능하고 미선택 확정이 가능하다. 필수면 선택지 2개 이상과 유효한 default가 필요하다.'),
        _item('random_select', '결정적 RNG로 후보를 뽑아 selection_key에 기록한다.', 'selector, count=1, selection_key', '뽑힌 인스턴스 ID는 이벤트 로그에 확정값으로 남는다.'),
        _item('capture_selection', 'selector로 계산한 현재 후보를 사용자 질문 없이 selection_key에 저장한다.', 'selector, selection_key'),
        _item('set_memory', '플레이어별 효과 기억 값을 기록한다.', 'player, key, value'),
        _item('emit_event', '새 DSL 이벤트를 큐에 발행한다.', 'event, payload={}, source_only=false'),
        _item('schedule', '미래 이벤트에 단일 명령을 예약한다.', 'when{event,controller,where_event_card,condition}, effect, duration, effect_controller=scheduled|event, preserve_source, repeat'),
        _item('log', '사람이 읽을 효과 로그를 추가한다.', 'text'),
    ]),
    ('HP·FP·데미지', [
        _item('deal_damage', '대상에게 효과 데미지를 준다.', 'player, amount, repeat, suppress_counter_gain'),
        _item('change_hp', 'HP를 amount만큼 직접 증감한다.', 'player, amount'),
        _item('change_fp', 'FP를 amount만큼 증감한다.', 'player, amount'),
        _item('reset_fp', '대상의 FP를 0으로 만든다.', 'player'),
        _item('gain_shield', '데미지를 흡수할 보호막을 부여한다.', 'player, amount, duration=battle|phase|turn|game'),
    ]),
    ('카드와 존', [
        _item('move_card', '선택/지정 카드를 to_zone으로 옮긴다.', 'player, selector|selection_key|card_instance_id, to_zone, face_up, preserve_attachment, allow_special_destination, as_get, set_flags, max_zone_count, result_key, continue_resolution, block_hand_until', '특수 기술의 패/리스트 이동과 리스트 상한 등 코어 이동 규칙을 함께 적용한다.'),
        _item('exchange_cards', '두 selection_key의 카드 위치를 원자적으로 맞바꾼다.', 'first_selection_key, second_selection_key, result_key'),
        _item('draw', 'side에서 hand로 count장 뽑는다.', 'player, count=1'),
        _item('discard', '패 카드를 버린다.', 'player, selector|selection_key|card_instance_id, result_key, block_hand_until'),
        _item('reveal', '카드를 공개 상태로 만든다.', 'player, selector|selection_key|card_instance_id'),
        _item('hide', '카드를 비공개 상태로 만든다.', 'player, selector|selection_key|card_instance_id'),
        _item('break_card', '카드 한 장을 브레이크한다.', 'player, selector|selection_key|card_instance_id, result_key, continue_resolution'),
        _item('break_cards', '여러 카드를 함께 브레이크한다.', 'selector|selection_key|card_instance_ids(값 표현식 2개 이상), require_all, result_key'),
        _item('shuffle_zone', '존을 결정적으로 섞는다.', 'player, zone, face_up'),
        _item('attach_card', '카드를 다른 카드 아래에 세트한다.', 'player, selector|selection_key|card_instance_id, to_card_instance_id, attachment_expires=battle, return_to_hand_on_expiry, face_up'),
        _item('create_token', '런타임 토큰 카드를 만든다.', 'player, zone=passive, token/name/code/type/card, face_up=true, repeat, max_zone_count'),
        _item('delete_token', '토큰 카드를 게임 상태에서 제거한다.', 'player, selector|selection_key|card_instance_id'),
    ]),
    ('상태·카운터', [
        _item('gain_state', '상태를 부여한다.', 'player, state, value=true, label, rules, expires{event=phase_end,phase,occurrences}'),
        _item('lose_state', '상태와 같은 키의 카운터 표시를 제거한다.', 'player, state'),
        _item('change_counter', '카운터를 amount만큼 증감한다.', 'player, counter, amount, min, max, label'),
        _item('set_counter', '카운터를 value로 설정한다.', 'player, counter, value, min, max, label'),
        _item('limit_counter_gain', '카운터 획득량 상한을 설치한다.', 'player, counter, max, duration=phase|battle|turn|game'),
        _item('modify_state_rule', '상태가 참조하는 규칙 필드 값을 바꾼다.', 'player, state, field, value, mode=replace|minimum|maximum, duration=continuous'),
        _item('set_usage_limit', 'usage 저장소의 현재 사용량을 직접 기록한다.', 'player, key, scope=game|turn|phase|battle, value=1'),
    ]),
    ('수치·판정 변경', [
        _item('modify_stat', '카드의 frame 또는 damage를 증감/고정한다.', 'player, stat=frame|damage, amount 또는 fixed=true+value, where, target_zones, duration, source_only'),
        _item('fix_speed', '속도를 value로 고정해 FP와 후속 변경을 무시하게 한다.', 'player, stat=frame, value, where, target_zones, duration, preserve_prior_speed_changes'),
        _item('modify_damage', '이후 배틀/효과 데미지 보정자를 설치한다.', 'player, amount, where, duration, max_uses'),
        _item('modify_judgment', '판정 필드 문자열을 교체·추가·삭제한다.', 'player, field=hit|counter|guard|pos|special|g_top|g_mid|g_bot, value, mode=replace|append|clear, scope=battle|all_zones, where, target_zones, duration'),
        _item('modify_defense_judgments', '현재 수비 기술의 상/중/하 판정을 한 값으로 바꾼다.', 'player, value'),
        _item('copy_defense_judgments', '선택한 수비 카드의 방어 판정을 현재 카드에 복사한다.', 'selection_key, player'),
        _item('copy_clash_judgments', '선택한 카드의 상쇄 관련 판정을 복사한다.', 'selection_key, player'),
        _item('invalidate_battle_card', '선택/지정한 배틀 기술을 판정에서 무효화한다.', 'selection_key|card_instance_id, player'),
    ]),
    ('금지·무효·대체', [
        _item('prevent', 'kind의 행동/결과를 금지하는 수정자를 설치한다.', 'kind, player, condition, where, against_where, target_zones, duration, max_uses, controller_only, selection_key, unless_event_attached'),
        _item('negate', 'kind의 이미 발생하려는 처리에 무효 수정자를 설치한다.', 'prevent와 같은 공통 필드'),
        _item('replace', 'damage를 amount로 대체한다.', 'kind=damage, amount, player, condition, where, against_where, duration, max_uses, selection_key'),
        _item('grant_effect_immunity', '특정 출처/명령/방향의 카드 효과 면역을 부여한다.', 'player, scope=opponent|other_cards|source_codes, source_codes, operations, stats, directions, where, duration=event|battle|phase|turn|next_turn|game|continuous'),
    ]),
    ('페이즈·강제 진행', [
        _item('skip_phase', '지정 phase를 건너뛴다.', 'phase'),
        _item('repeat_phase', '지정 phase를 한 번 더 예약한다.', 'phase, after_current'),
        _item('force_ready', '선택/지정 기술을 강제로 레디한다.', 'player, selection_key|card_instance_id, face_up'),
        _item('force_ready_first', '대상이 다음 레디를 먼저 하도록 한다.', 'player, duration=turn'),
        _item('force_designated_get', '상대가 지정한 카드만 Get하게 한다.', 'player, duration=turn'),
        _item('skip_get', '해당 플레이어의 이번 Get을 건너뛴다.', 'player'),
        _item('replace_get', '기본 Get을 효과 전용 Get 흐름으로 대체한다.', 'player, selector, prompt'),
        _item('end_battle', '현재 배틀을 즉시 종료 흐름으로 보낸다.', 'reason'),
        _item('end_turn', '현재 턴을 종료 흐름으로 보낸다.', 'reason'),
        _item('win_game', 'player를 즉시 승자로 확정한다.', 'player, reason'),
    ]),
    ('콤보·캐치', [
        _item('start_combo', '현재 배틀 기술을 시동기로 콤보 타임을 시작한다.', 'player'),
        _item('end_combo', '현재 콤보 타임을 종료한다.', 'player, source_event_card'),
        _item('grant_catch', '추가 캐치 후보 규칙을 부여한다.', 'player, allow_zones, where, min_speed, max_speed, source_only, source_attached, damage_bonus, return_source_to_hand, break_after_use, break_source_after_use, counter_exemption_on_source_break{counter}, effect_replacement{abilities}'),
        _item('grant_flexible_use', 'list 등 추가 존의 카드를 콤보/캐치에 사용할 수 있게 한다.', 'player, allow_zones, where, max_uses=1, usage_scope=turn|battle|game, contexts=[combo,catch]'),
        _item('end_catch', '현재 연속 캐치 흐름을 종료한다.', 'player'),
        _item('modify_combo', '콤보 합법성·속도·데미지·사용 존·종료 규칙을 수정한다.', 'player, allow_zones, source_zones, where, after_where, min_combo, max_combo, max_combo_cap, extend_combo_to, extend_combo_by, max_speed_delta, speed_options, ignore_speed, optional_ignore_speed, any_speed, optional_any_speed, ignore_damage_penalty, optional_ignore_damage_penalty, damage_bonus, damage_bonus_speed, break_after_use, break_after_use_speeds, end_after_use, return_to_hand_after_use, skip_get_on_use, requires_followup, requires_followup_at_combo, counter_cost, optional_speed_cost, counter_on_speed_delta, usage_key/max_uses/usage_scope, allow_reuse, borrow_from, return_to_owner_zone_on_combo_end, duration, condition', '플래그가 많으므로 반드시 합법/불법 경계와 선택 분기를 격리 테스트한다.'),
    ]),
    ('특수 판정과 규칙 연결', [
        _item('guess_hand_parity', '상대 패를 고르고 종류/홀짝을 추측·공개한 뒤 분기한다.', 'player, selector, categories, prompt, repeat_on_correct, repeat_always, on_correct, on_wrong'),
        _item('modify_hand_guess_categories', '현재 추측 이벤트 카드에 허용되는 추측 종류를 바꾼다.', 'categories, target_card=event_card, duration=battle, max_attempts'),
        _item('static_rule', '엔진에 등록된 이름 기반 정적 규칙을 연결한다.', 'rules(중복 없는 문자열 배열)', '새 효과 구현의 우회로가 아니라 명시적으로 구현된 코어 규칙 연결에만 사용한다.'),
    ]),
]


ROOT_FIELDS = [
    _item('schema_version', 'DSL 스키마 버전. 현재 값은 1이다.', '정수, 필수'),
    _item('reviewed / draft / no_effect', '검수·초안·효과 없음 상태.', 'boolean', 'no_effect=true이면 abilities는 비어 있어야 한다.'),
    _item('source_refs / source_digest', '룰북·Q&A·카드 원문 출처와 승인 시점 SHA-256.', 'source_refs{rulebook_pages,qna_ids,general_qna_ids,card_text,detail_text}; digest는 서버 관리'),
    _item('review_evidence', '게시용 능력별 결정적 검토 증거.', 'passed, method, scenario_count, abilities[{ability_id,passed,scenarios[{passed,deterministic,...}]}]', '검토 완료 능력마다 최소 3개 상황이 필요하다.'),
    _item('deck_limit', '같은 카드 이름의 덱 투입 상한.', '1 이상의 정수'),
    _item('deck_rules / deck_rules_when_included', '캐릭터별 덱 크기·최소 캐릭터 기술·보충 카드·타 캐릭터 카드 규칙.', 'main_size, character_card_minimum, special_allowed_character_ids, supplements, other_character_cards'),
    _item('token_key / token_usage', '토큰·카운터의 의미 키와 사용 분류.', 'token_key 문자열; token_usage는 token/counter 배열'),
    _item('card_form', '특정 존에서 토큰 등을 기술 카드 형태로 취급.', 'active_zones, type, frame, token_key, character_key'),
    _item('trait_negation', '특성의 번호 효과 무효 규칙.', 'players=both, active_zones'),
    _item('trait_state_keys / trait_state_preserve_on_negation', '특성 무효 시 함께 제거하거나 보존할 상태 키.', '문자열 배열'),
    _item('state_grants', '카드가 존에 있는 동안 파생 상태를 제공.', 'states, active_zones, player=controller|opponent|both, condition, numbered_effect'),
    _item('effect_damage_limit', '이 카드가 주는 효과 데미지의 상대별 횟수 상한.', 'count, scope=game|turn'),
    _item('play_costs', '레디/콤보/캐치에 카드를 내기 전에 지불하는 비용.', 'operation=discard|delete_token|move_card, selector, to_zone, use_contexts, source_zones, payment_timing, numbered_effect'),
    _item('attached_effect_multiplier', '세트된 카드의 특정 이벤트 효과 실행 횟수 배율.', 'event, value, where, numbered_effect'),
    _item('hand_limit_bonus', '손패 제한 보정.', '정수'),
    _item('discard_state_alias', '특정 버리기 상태 키의 별칭.', '객체'),
    _item('play_condition / play_limit', '카드 자체의 사용 조건과 사용 횟수 제한.', 'condition; limit{scope,max,key}'),
    _item('combo_rules', '카드에 인쇄된 상시 콤보 합법성 규칙.', 'modify_combo와 같은 규칙 객체 배열'),
    _item('zone_limits', '특정 필터 카드의 존 내 상한.', 'zone, max, where'),
    _item('defense_rules', '상/중/하 회피·상쇄 판정의 속도/데미지/히트 및 비용 규칙.', 'position, judgment=dodge|clash, grant, min/max speed, min/max damage, min_hit, hit_values, where, cost, numbered_effect, condition'),
    _item('catch_rules', '카드 자체의 캐치 고정 속도·허용 존·비용·사용 후 브레이크.', 'fixed_speed, optional_fixed_speed, allow_zones, break_after_use, counter_cost, numbered_effect, condition'),
    _item('break_rules', '존/원인별 브레이크 금지.', 'forbidden_zones, preventions[{scope=all|owner_direct|opponent_effect,condition,numbered_effect}]'),
    _item('effect_immunity', '인쇄된 상시 효과 면역.', 'scope, source_codes, active_zones, operations=[modify_stat,move_card], to_zones, stats, directions, numbered_effect'),
    _item('abilities', '유발·지속·대체 능력 목록.', 'ability 객체 배열, 필수'),
]


ABILITY_FIELDS = [
    _item('id', '릴리스와 로그에서 유지되는 고유 ID.', '영문 소문자·숫자·점·콜론·밑줄·하이픈 권장, 필수'),
    _item('label / draft_text', '사용자 표시 이름과 카드 원문 단위.', '문자열'),
    _item('kind', '번호 없는 기능(function) 또는 번호 있는 효과(effect).', 'function | effect'),
    _item('mode', '강제/선택/지속/대체 처리 방식.', 'mandatory | optional | continuous | replacement'),
    _item('trigger', '발생 이벤트. events를 쓰면 하나의 능력이 여러 이벤트에 반응한다.', '{event, events?}; continuous는 생략 가능'),
    _item('timing', '같은 이벤트 해결 큐의 정렬 위치.', 'TIMING_ORDER 키'),
    _item('visibility', '유발 및 선택 정보 공개 범위.', 'public(기본) | private'),
    _item('source_refs', '능력 자체의 재정 출처.', '{rulebook_pages,qna_ids,general_qna_ids,card_text,detail_text}'),
    _item('active_zones', '능력이 탐색되는 소스 카드 존.', '존 배열; 세트 카드는 active_when_attached도 필요할 수 있음'),
    _item('condition / availability_selector', '유발 조건과 실제 후보 존재 조건.', 'condition 객체; selector 객체'),
    _item('recheck_condition', '큐 대기 뒤 실제 해결 직전에 condition을 다시 검사.', 'boolean'),
    _item('active_when_attached', '다른 카드 아래에 세트된 상태에서도 활성.', 'boolean'),
    _item('allow_non_source_trigger', '기술 자체가 만들지 않은 use/hit/counter 등의 이벤트에도 반응.', 'boolean', '기술 유발 오발동을 막기 위해 명시적 전역 반응에만 사용한다.'),
    _item('requires_combo_use', '이 카드가 시동기 또는 후속 기술로 포함된 콤보에서만 콤보 종료 유발.', 'boolean'),
    _item('dedupe_trigger_key', '한 이벤트 묶음에서 중복 유발을 제거하는 안정 키.', '[a-z0-9_.:-]+'),
    _item('limit', '능력의 실제 해결 횟수 제한.', '{scope,max,key,per_event_card,per_effect_resolution}'),
    _item('cost', '능력 해결 전에 실행되는 명령 배열.', 'effect 명령 배열'),
    _item('targets', '명령 전 순서대로 묻는 대상 선택기.', 'selector 배열; 선택 결과는 target_0, target_1...'),
    _item('handler / effects', '등록 Python 핸들러 또는 DSL 명령 배열 중 하나.', 'handler 문자열 또는 비어 있지 않은 effects 배열'),
]


SELECTOR_FIELDS = [
    _item('kind', '선택 대상 종류.', 'card | player, 필수'),
    _item('player', '후보 소유자/대상.', 'p1 | p2 | {controller:true} | {opponent:true}'),
    _item('zone / zones', '카드 후보 존 하나 또는 여러 개.', 'ALL_ZONES 값'),
    _item('min / max', '최소·최대 선택 수.', '0 이상 정수 또는 값 표현식; 기본은 1/최솟값'),
    _item('where', '카드 속성 필터.', 'card filter 객체'),
    _item('default', '시간 만료 시 선택할 인스턴스 ID.', 'ID 배열'),
    _item('history', '현재 존 대신 콤보 이력을 후보로 사용.', 'combo_used | combo_predecessors | combo_previous'),
    _item('as_operation', '후보 단계에서 실제로 가능한 작업만 남긴다.', 'discard | break_card | delete_token | move_card'),
    _item('to_zone / allow_special_destination', 'move_card 후보의 목적지와 특수 기술 이동 예외.', '존 / boolean'),
    _item('include_operation_blocked', '작업이 금지된 카드도 설명용 후보로 포함.', 'boolean'),
    _item('distinct_by', '선택 카드끼리 달라야 하는 속성.', 'frame | code | name | type'),
    _item('selection_key', '앞선 선택에 포함된 카드만 후보로 제한.', '문자열'),
    _item('exclude_source / exclude_combo_proposed', '효과 소스나 동시에 제시 중인 콤보 카드를 제외.', 'boolean'),
    _item('attached_to_source / attached_to_event', '소스 카드 또는 이벤트 카드 아래 세트된 카드만 선택.', 'boolean'),
]


CARD_FILTER_FIELDS = [
    ('any / all', '하위 카드 필터 배열 중 하나/모두 일치'),
    ('일반 필드', 'code, name, type, frame, damage, pos, character_id, token_key, instance_id 등 카드 필드의 정확 일치; 배열 값이면 그중 하나'),
    ('type_contains / type_not_contains / type_in', '카드 종류 문자열 포함·제외·목록 일치'),
    ('name_contains / name_not_contains', '대소문자 무시 이름 부분 일치·제외'),
    ('judgment_contains / judgment_contains_any', 'hit 또는 counter 판정값 일치'),
    ('battle_judgment_contains', 'special/g_top/g_mid/g_bot 전체에서 판정 문자열 검색'),
    ('keyword_any', '/로 구분된 키워드 중 하나 포함'),
    ('text_contains / text_contains_any / text_not_contains', '카드 텍스트 문자열 검색; hidden_bond 구 표기 호환 포함'),
    ('text_effect_prefix', '줄 시작의 번호 효과 접두사(예: 사용 시:) 검색'),
    ('frame_gte / frame_lte / frame_parity', '인쇄 속도 범위 및 odd/even'),
    ('code_in', '카드 코드 배열 중 하나'),
    ('instance_id_not', '특정 런타임 카드 제외'),
    ('owner', '런타임 소유자 일치'),
    ('face_up', '공개 상태 일치'),
    ('is_technique', '공격/수비/특수 기술 여부. 뒷면 비기술 플래그를 반영'),
    ('special_truthy / special_contains', '특수 판정 존재 여부/문자열 포함'),
]


def reference_context():
    described_effects = {
        item['name'] for _, items in EFFECT_GROUPS for item in items
    }
    return {
        'schema_version': EFFECT_SCHEMA_VERSION,
        'phases': PHASES,
        'zones': ALL_ZONES,
        'ability_kinds': sorted(ABILITY_KINDS),
        'ability_modes': sorted(ABILITY_MODES),
        'visibilities': sorted(VISIBILITIES),
        'prevent_kinds': sorted(PREVENT_KINDS),
        'trigger_details': [
            (name, TRIGGER_DETAILS.get(name, '설명이 아직 작성되지 않았습니다.'))
            for name in sorted(TRIGGERS)
        ],
        'timing_details': [
            (name, TIMING_DETAILS.get(name, f'{order}'))
            for name, order in sorted(TIMING_ORDER.items(), key=lambda pair: pair[1])
        ],
        'condition_details': [
            (name, CONDITION_DETAILS.get(name, '설명이 아직 작성되지 않았습니다.'))
            for name in sorted(CONDITION_OPS)
        ],
        'value_details': [
            (name, VALUE_DETAILS.get(name, '설명이 아직 작성되지 않았습니다.'))
            for name in sorted(VALUE_OPS)
        ],
        'effect_groups': EFFECT_GROUPS,
        'root_fields': ROOT_FIELDS,
        'ability_fields': ABILITY_FIELDS,
        'selector_fields': SELECTOR_FIELDS,
        'card_filter_fields': CARD_FILTER_FIELDS,
        'undocumented_effect_ops': sorted(EFFECT_OPS - described_effects),
        'unknown_documented_effect_ops': sorted(described_effects - EFFECT_OPS),
        'undocumented_triggers': sorted(TRIGGERS - set(TRIGGER_DETAILS)),
        'undocumented_conditions': sorted(CONDITION_OPS - set(CONDITION_DETAILS)),
        'undocumented_values': sorted(VALUE_OPS - set(VALUE_DETAILS)),
    }
