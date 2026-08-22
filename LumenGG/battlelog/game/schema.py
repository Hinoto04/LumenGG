"""Validation for the language-neutral card-effect DSL."""

from dataclasses import dataclass
import re

from .handlers import registered_handler_names
from .spec import (
    ABILITY_KINDS,
    ABILITY_MODES,
    CONDITION_OPS,
    EFFECT_OPS,
    EFFECT_SCHEMA_VERSION,
    ALL_ZONES,
    PHASES,
    PREVENT_KINDS,
    TIMING_ORDER,
    TRIGGERS,
    VALUE_OPS,
    VISIBILITIES,
)


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    code: str = 'invalid'

    def as_dict(self):
        return {'path': self.path, 'message': self.message, 'code': self.code}


def empty_effect_definition():
    return {'schema_version': EFFECT_SCHEMA_VERSION, 'reviewed': False, 'abilities': []}


def _issue(issues, path, message, code='invalid'):
    issues.append(ValidationIssue(path, message, code))


def _validate_sources(value, path, issues):
    if value is None:
        return
    if not isinstance(value, dict):
        _issue(issues, path, '출처는 객체여야 합니다.')
        return
    pages = value.get('rulebook_pages', [])
    qna_ids = value.get('qna_ids', [])
    general_qna_ids = value.get('general_qna_ids', [])
    if not isinstance(pages, list) or any(not isinstance(item, int) or not 1 <= item <= 54 for item in pages):
        _issue(issues, f'{path}.rulebook_pages', '룰북 페이지는 1~54 정수 배열이어야 합니다.')
    if not isinstance(qna_ids, list) or any(not isinstance(item, int) or item <= 0 for item in qna_ids):
        _issue(issues, f'{path}.qna_ids', 'Q&A 참조는 양의 정수 배열이어야 합니다.')
    if not isinstance(general_qna_ids, list) or any(
        not isinstance(item, int) or item <= 0 for item in general_qna_ids
    ):
        _issue(
            issues, f'{path}.general_qna_ids',
            '일반 Q&A 참조는 양의 정수 배열이어야 합니다.',
        )
    if 'card_text' in value and not isinstance(value.get('card_text'), bool):
        _issue(issues, f'{path}.card_text', '카드 원문 참조 여부는 불리언이어야 합니다.')
    if 'detail_text' in value and not isinstance(value.get('detail_text'), bool):
        _issue(issues, f'{path}.detail_text', '보충 설명 참조 여부는 불리언이어야 합니다.')


def _has_sources(value):
    return isinstance(value, dict) and bool(
        value.get('rulebook_pages') or value.get('qna_ids')
        or value.get('general_qna_ids') or value.get('card_text')
    )


def _validate_review_evidence(definition, abilities, issues):
    """Require reproducible scenario evidence for every published ability."""
    if not abilities or definition.get('reviewed') is not True:
        return
    evidence = definition.get('review_evidence')
    if not isinstance(evidence, dict):
        _issue(
            issues, '$.review_evidence',
            '게시되는 효과 카드에는 능력별 자동 검토 증거가 필요합니다.',
            'missing_review_evidence',
        )
        return
    if evidence.get('passed') is not True:
        _issue(
            issues, '$.review_evidence.passed',
            '전체 자동 검토가 통과한 정의만 게시할 수 있습니다.',
            'review_evidence_failed',
        )
    method = evidence.get('method')
    if not isinstance(method, str) or not method.strip():
        _issue(
            issues, '$.review_evidence.method',
            '자동 검토 방법 버전이 필요합니다.',
            'missing_review_method',
        )
    evidence_abilities = evidence.get('abilities')
    if not isinstance(evidence_abilities, list):
        _issue(
            issues, '$.review_evidence.abilities',
            '능력별 검토 증거 목록이 필요합니다.',
            'missing_ability_review',
        )
        return
    by_id = {}
    total_scenarios = 0
    for index, item in enumerate(evidence_abilities):
        path = f'$.review_evidence.abilities[{index}]'
        if not isinstance(item, dict):
            _issue(
                issues, path, '능력 검토 증거는 객체여야 합니다.',
                'invalid_ability_review',
            )
            continue
        ability_id = str(item.get('ability_id') or '').strip()
        if not ability_id:
            _issue(
                issues, f'{path}.ability_id', '검토한 능력 ID가 필요합니다.',
                'missing_ability_review_id',
            )
        elif ability_id in by_id:
            _issue(
                issues, f'{path}.ability_id',
                f'능력 검토 증거 ID가 중복되었습니다: {ability_id}',
                'duplicate_ability_review',
            )
        else:
            by_id[ability_id] = (item, path)
        scenarios = item.get('scenarios')
        if not isinstance(scenarios, list):
            _issue(
                issues, f'{path}.scenarios', '결정적 검토 상황 목록이 필요합니다.',
                'missing_review_scenarios',
            )
            continue
        total_scenarios += len(scenarios)
        if item.get('passed') is not True:
            _issue(
                issues, f'{path}.passed', '능력 검토가 통과하지 않았습니다.',
                'ability_review_failed',
            )
        for scenario_index, scenario in enumerate(scenarios):
            scenario_path = f'{path}.scenarios[{scenario_index}]'
            if not isinstance(scenario, dict):
                _issue(
                    issues, scenario_path, '검토 상황은 객체여야 합니다.',
                    'invalid_review_scenario',
                )
                continue
            if scenario.get('passed') is not True:
                _issue(
                    issues, f'{scenario_path}.passed',
                    '통과하지 않은 검토 상황이 있습니다.',
                    'review_scenario_failed',
                )
            if scenario.get('deterministic') is not True:
                _issue(
                    issues, f'{scenario_path}.deterministic',
                    '게시 검토 상황은 동일 입력에서 같은 결과를 내야 합니다.',
                    'nondeterministic_review_scenario',
                )
    for ability_index, ability in enumerate(abilities):
        if not isinstance(ability, dict):
            continue
        ability_id = str(ability.get('id') or '').strip()
        if not ability_id:
            continue
        reviewed = by_id.get(ability_id)
        if not reviewed:
            _issue(
                issues,
                f'$.abilities[{ability_index}].id',
                f'능력 {ability_id}의 자동 검토 증거가 없습니다.',
                'missing_ability_review',
            )
            continue
        item, path = reviewed
        scenarios = item.get('scenarios') or []
        if len(scenarios) < 3:
            _issue(
                issues, f'{path}.scenarios',
                f'능력 {ability_id}은 최소 3개의 결정적 상황 검토가 필요합니다.',
                'insufficient_review_scenarios',
            )
    scenario_count = evidence.get('scenario_count')
    if (
        not isinstance(scenario_count, int)
        or isinstance(scenario_count, bool)
        or scenario_count != total_scenarios
    ):
        _issue(
            issues, '$.review_evidence.scenario_count',
            '전체 검토 상황 수가 능력별 증거의 합계와 일치해야 합니다.',
            'inconsistent_review_scenario_count',
        )


def _validate_condition(value, path, issues):
    if value in (None, True, False):
        return
    if not isinstance(value, dict):
        _issue(issues, path, '조건은 객체 또는 불리언이어야 합니다.')
        return
    op = value.get('op')
    if op not in CONDITION_OPS:
        _issue(issues, f'{path}.op', f'지원하지 않는 조건 연산입니다: {op!r}')
        return
    if op in {'all', 'any'}:
        items = value.get('conditions')
        if not isinstance(items, list) or not items:
            _issue(issues, f'{path}.conditions', '조건 목록이 필요합니다.')
        else:
            for index, item in enumerate(items):
                _validate_condition(item, f'{path}.conditions[{index}]', issues)
    elif op == 'not':
        _validate_condition(value.get('condition'), f'{path}.condition', issues)
    elif op in {'equals', 'not_equals', 'gt', 'gte', 'lt', 'lte', 'in', 'contains', 'exists'}:
        if not value.get('left'):
            _issue(issues, f'{path}.left', '비교할 상태 경로가 필요합니다.')
        elif isinstance(value.get('left'), dict):
            _validate_value(value.get('left'), f'{path}.left', issues)
    elif op == 'phase_is' and value.get('phase') not in PHASES:
        _issue(issues, f'{path}.phase', '유효한 페이즈가 필요합니다.')
    elif op == 'result_is' and not (value.get('result') or value.get('results')):
        _issue(issues, f'{path}.result', '판정 결과가 필요합니다.')
    elif op == 'zone_count':
        if value.get('zone') not in ALL_ZONES:
            _issue(issues, f'{path}.zone', '카드 수를 셀 유효한 존이 필요합니다.')
        if value.get('where') is not None and not isinstance(
            value.get('where'), dict,
        ):
            _issue(issues, f'{path}.where', '카드 수 필터는 객체여야 합니다.')
        if 'exclude_source' in value and not isinstance(
            value.get('exclude_source'), bool,
        ):
            _issue(
                issues, f'{path}.exclude_source',
                '소스 카드 제외 여부는 불리언이어야 합니다.',
            )
        if 'exclude_combo_proposed' in value and not isinstance(
            value.get('exclude_combo_proposed'), bool,
        ):
            _issue(
                issues, f'{path}.exclude_combo_proposed',
                '동시에 제시한 콤보 카드 제외 여부는 불리언이어야 합니다.',
            )
    elif op == 'has_state' and not value.get('state'):
        _issue(issues, f'{path}.state', '상태 키가 필요합니다.')
    elif op == 'counter_at_least' and not value.get('counter'):
        _issue(issues, f'{path}.counter', '카운터 키가 필요합니다.')
    elif op == 'used_card':
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '사용 카드 필터는 객체여야 합니다.')
        minimum = value.get('min', 1)
        if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
            _issue(issues, f'{path}.min', '사용 횟수는 1 이상의 정수여야 합니다.')
        if value.get('use_context') not in {None, 'ready', 'combo', 'catch'}:
            _issue(issues, f'{path}.use_context', '카드 사용 맥락이 올바르지 않습니다.')
        if 'current_card' in value and not isinstance(value.get('current_card'), bool):
            _issue(issues, f'{path}.current_card', '현재 카드 제한 여부는 불리언이어야 합니다.')
    elif op == 'ability_resolved':
        if not str(value.get('ability_id') or '').strip():
            _issue(issues, f'{path}.ability_id', '발동 여부를 확인할 효과 ID가 필요합니다.')
        if 'same_source' in value and not isinstance(value.get('same_source'), bool):
            _issue(
                issues, f'{path}.same_source',
                '동일 소스 카드 제한 여부는 불리언이어야 합니다.',
            )
    elif op == 'battle_result':
        if not (value.get('result') or value.get('results')):
            _issue(issues, f'{path}.result', '확인할 배틀 판정 결과가 필요합니다.')
        if value.get('opponent_where') is not None and not isinstance(value.get('opponent_where'), dict):
            _issue(issues, f'{path}.opponent_where', '상대 카드 필터는 객체여야 합니다.')


def _validate_selector(value, path, issues):
    if not isinstance(value, dict):
        _issue(issues, path, '대상 선택기는 객체여야 합니다.')
        return
    if value.get('kind') not in {'card', 'player'}:
        _issue(issues, f'{path}.kind', '대상 종류는 card 또는 player여야 합니다.')
    minimum = value.get('min', 1)
    maximum = value.get('max', minimum)
    if isinstance(minimum, dict):
        _validate_value(minimum, f'{path}.min', issues)
    elif not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0:
        _issue(issues, f'{path}.min', '최소 선택 수는 0 이상의 정수여야 합니다.')
    if isinstance(maximum, dict):
        _validate_value(maximum, f'{path}.max', issues)
    elif not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
        _issue(issues, f'{path}.max', '최대 선택 수는 최소 선택 수 이상이어야 합니다.')
    elif isinstance(minimum, int) and maximum < minimum:
        _issue(issues, f'{path}.max', '최대 선택 수는 최소 선택 수 이상이어야 합니다.')
    where = value.get('where')
    if where is not None and not isinstance(where, dict):
        _issue(issues, f'{path}.where', '카드 필터는 객체여야 합니다.')
    zones = value.get('zones')
    if zones is not None and (not isinstance(zones, list) or any(zone not in ALL_ZONES for zone in zones)):
        _issue(issues, f'{path}.zones', '대상 존 목록이 올바르지 않습니다.')
    if value.get('zone') is not None and value.get('zone') not in ALL_ZONES:
        _issue(issues, f'{path}.zone', '대상 존이 올바르지 않습니다.')
    if 'default' in value and not isinstance(value.get('default'), list):
        _issue(issues, f'{path}.default', '기본 선택은 ID 배열이어야 합니다.')
    if value.get('history') not in {None, 'combo_used', 'combo_predecessors', 'combo_previous'}:
        _issue(issues, f'{path}.history', '지원하지 않는 카드 이력 선택기입니다.')
    if value.get('as_operation') not in {
        None, 'discard', 'break_card', 'delete_token', 'move_card',
    }:
        _issue(issues, f'{path}.as_operation', '대상 선택 시 적용할 작업이 올바르지 않습니다.')
    if value.get('as_operation') == 'move_card':
        if value.get('to_zone') not in ALL_ZONES:
            _issue(
                issues, f'{path}.to_zone',
                '이동 대상으로 선택할 때는 유효한 목적 존이 필요합니다.',
            )
        if 'allow_special_destination' in value and not isinstance(
            value.get('allow_special_destination'), bool,
        ):
            _issue(
                issues, f'{path}.allow_special_destination',
                '특수 기술 목적지 예외 여부는 불리언이어야 합니다.',
            )
    elif value.get('to_zone') is not None:
        _issue(
            issues, f'{path}.to_zone',
            '목적 존은 move_card 선택기에만 지정할 수 있습니다.',
        )
    if 'include_operation_blocked' in value and not isinstance(
        value.get('include_operation_blocked'), bool,
    ):
        _issue(
            issues, f'{path}.include_operation_blocked',
            '작업 방지 카드 포함 여부는 불리언이어야 합니다.',
        )
    if value.get('distinct_by') not in {None, 'frame', 'code', 'name', 'type'}:
        _issue(issues, f'{path}.distinct_by', '서로 달라야 할 카드 필드가 올바르지 않습니다.')
    if value.get('selection_key') is not None and not str(value.get('selection_key') or '').strip():
        _issue(issues, f'{path}.selection_key', '후보를 제한할 선택 키가 올바르지 않습니다.')
    if 'exclude_source' in value and not isinstance(value.get('exclude_source'), bool):
        _issue(issues, f'{path}.exclude_source', '소스 카드 제외 여부는 불리언이어야 합니다.')
    if 'exclude_combo_proposed' in value and not isinstance(
        value.get('exclude_combo_proposed'), bool,
    ):
        _issue(
            issues, f'{path}.exclude_combo_proposed',
            '동시에 제시한 콤보 카드 제외 여부는 불리언이어야 합니다.',
        )
    for field_name in ('attached_to_source', 'attached_to_event'):
        if field_name in value and not isinstance(value.get(field_name), bool):
            _issue(issues, f'{path}.{field_name}', '세트 대상 선택기 플래그는 불리언이어야 합니다.')


def _validate_deck_rules(value, path, issues):
    if value is None:
        return
    if not isinstance(value, dict):
        _issue(issues, path, '덱 편성 규칙은 객체여야 합니다.')
        return
    main_size = value.get('main_size')
    if main_size is not None:
        if not isinstance(main_size, dict):
            _issue(issues, f'{path}.main_size', '덱 크기는 min/max 객체여야 합니다.')
        else:
            minimum = main_size.get('min')
            maximum = main_size.get('max')
            if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
                _issue(issues, f'{path}.main_size.min', '최소 덱 크기는 1 이상의 정수여야 합니다.')
            if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                _issue(issues, f'{path}.main_size.max', '최대 덱 크기는 1 이상의 정수여야 합니다.')
            if isinstance(minimum, int) and isinstance(maximum, int) and maximum < minimum:
                _issue(issues, f'{path}.main_size', '최대 덱 크기는 최소 덱 크기 이상이어야 합니다.')
            if 'base_excludes_supplements' in main_size and not isinstance(main_size.get('base_excludes_supplements'), bool):
                _issue(issues, f'{path}.main_size.base_excludes_supplements', '보충 카드 제외 여부는 불리언이어야 합니다.')
    minimum = value.get('character_card_minimum')
    if minimum is not None and (
        not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 0
    ):
        _issue(issues, f'{path}.character_card_minimum', '캐릭터 기술 최소 수는 0 이상의 정수여야 합니다.')
    special_character_ids = value.get('special_allowed_character_ids')
    if special_character_ids is not None and (
        not isinstance(special_character_ids, list)
        or not special_character_ids
        or any(
            not isinstance(item, int) or isinstance(item, bool) or item < 1
            for item in special_character_ids
        )
    ):
        _issue(
            issues, f'{path}.special_allowed_character_ids',
            '특수 기술에 허용할 캐릭터 ID는 비어 있지 않은 양의 정수 배열이어야 합니다.',
        )
    supplements = value.get('supplements', [])
    if not isinstance(supplements, list):
        _issue(issues, f'{path}.supplements', '보충 카드 규칙은 배열이어야 합니다.')
    else:
        for index, supplement in enumerate(supplements):
            supplement_path = f'{path}.supplements[{index}]'
            if not isinstance(supplement, dict):
                _issue(issues, supplement_path, '보충 카드 규칙은 객체여야 합니다.')
                continue
            if not isinstance(supplement.get('where'), dict) or not supplement.get('where'):
                _issue(issues, f'{supplement_path}.where', '보충 카드 필터가 필요합니다.')
            for field_name in ('max_count', 'same_name_limit'):
                amount = supplement.get(field_name)
                if amount is not None and (
                    not isinstance(amount, int) or isinstance(amount, bool) or amount < 1
                ):
                    _issue(issues, f'{supplement_path}.{field_name}', '보충 카드 제한은 1 이상의 정수여야 합니다.')
            if not isinstance(supplement.get('max_count'), int) or isinstance(supplement.get('max_count'), bool):
                _issue(issues, f'{supplement_path}.max_count', '보충 카드 최대 수가 필요합니다.')
            for field_name in (
                'allow_foreign_mark', 'allow_non_technique',
                'allow_base_copies',
            ):
                if field_name in supplement and not isinstance(supplement.get(field_name), bool):
                    _issue(issues, f'{supplement_path}.{field_name}', '보충 카드 허용 플래그는 불리언이어야 합니다.')
    imported = value.get('other_character_cards')
    if imported is not None:
        imported_path = f'{path}.other_character_cards'
        if not isinstance(imported, dict):
            _issue(issues, imported_path, '타 캐릭터 카드 규칙은 객체여야 합니다.')
        else:
            allowed_types = imported.get('allowed_types')
            if not isinstance(allowed_types, list) or not allowed_types or any(
                item not in {'공격', '수비', '특수'} for item in allowed_types
            ):
                _issue(issues, f'{imported_path}.allowed_types', '허용 기술 종류 목록이 올바르지 않습니다.')
            maximum = imported.get('max_per_character')
            if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                _issue(issues, f'{imported_path}.max_per_character', '캐릭터별 한도는 1 이상의 정수여야 합니다.')
            excluded = imported.get('exclude_character_ids', [])
            if not isinstance(excluded, list) or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 1
                for item in excluded
            ):
                _issue(issues, f'{imported_path}.exclude_character_ids', '제외 캐릭터 ID는 양의 정수 배열이어야 합니다.')
            for field_name in ('exclude_ultimate', 'treat_as_own_character', 'negate_effects', 'break_after_use'):
                if field_name in imported and not isinstance(imported.get(field_name), bool):
                    _issue(issues, f'{imported_path}.{field_name}', '타 캐릭터 카드 규칙 플래그는 불리언이어야 합니다.')


def _validate_value(value, path, issues):
    if value is None or isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    if not isinstance(value, dict):
        _issue(issues, path, '수치는 숫자 또는 값 표현식이어야 합니다.')
        return
    if set(value) == {'value'}:
        _validate_value(value.get('value'), f'{path}.value', issues)
        return
    if 'path' in value:
        if not str(value.get('path') or '').strip():
            _issue(issues, f'{path}.path', '상태 값 경로가 필요합니다.')
        return
    op = value.get('op')
    if op not in VALUE_OPS:
        _issue(issues, f'{path}.op', f'지원하지 않는 값 연산입니다: {op!r}')
        return
    if op in {'add', 'multiply', 'min', 'max'}:
        values = value.get('values')
        if not isinstance(values, list) or not values:
            _issue(issues, f'{path}.values', '계산할 값 목록이 필요합니다.')
        else:
            for index, item in enumerate(values):
                _validate_value(item, f'{path}.values[{index}]', issues)
    elif op in {'subtract', 'floor_divide', 'modulo'}:
        _validate_value(value.get('left'), f'{path}.left', issues)
        _validate_value(value.get('right'), f'{path}.right', issues)
    elif op in {'negate', 'abs'}:
        _validate_value(value.get('value'), f'{path}.value', issues)
    elif op == 'clamp':
        _validate_value(value.get('value'), f'{path}.value', issues)
        _validate_value(value.get('min'), f'{path}.min', issues)
        _validate_value(value.get('max'), f'{path}.max', issues)
    elif op == 'if':
        _validate_condition(value.get('condition'), f'{path}.condition', issues)
        _validate_value(value.get('then'), f'{path}.then', issues)
        _validate_value(value.get('else'), f'{path}.else', issues)
    elif op == 'zone_count':
        if value.get('zone') not in ALL_ZONES:
            _issue(issues, f'{path}.zone', '카드 수를 셀 유효한 존이 필요합니다.')
        where = value.get('where')
        if where is not None and not isinstance(where, dict):
            _issue(issues, f'{path}.where', '카드 수 필터는 객체여야 합니다.')
    elif op == 'zone_distinct_count':
        if value.get('zone') not in ALL_ZONES:
            _issue(issues, f'{path}.zone', '서로 다른 값을 셀 유효한 존이 필요합니다.')
        if value.get('field') not in {
            'frame', 'code', 'name', 'type', 'character_id',
            'printed_character_id',
        }:
            _issue(issues, f'{path}.field', '서로 다른 값을 셀 카드 필드가 올바르지 않습니다.')
        excluded = value.get('exclude_values', [])
        if not isinstance(excluded, list) or any(
            not isinstance(item, (str, int)) or isinstance(item, bool)
            for item in excluded
        ):
            _issue(
                issues, f'{path}.exclude_values',
                '서로 다른 값 집계에서 제외할 값은 문자열/정수 배열이어야 합니다.',
            )
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '카드 필터는 객체여야 합니다.')
    elif op == 'counter_count':
        if not str(value.get('counter') or '').strip():
            _issue(issues, f'{path}.counter', '수를 확인할 카운터 키가 필요합니다.')
    elif op == 'state_rule_value':
        if not str(value.get('state') or '').strip():
            _issue(issues, f'{path}.state', '상태 규칙의 상태 키가 필요합니다.')
        if not str(value.get('field') or '').strip():
            _issue(issues, f'{path}.field', '상태 규칙의 필드 키가 필요합니다.')
        _validate_value(value.get('default', 0), f'{path}.default', issues)
    elif op == 'memory_value':
        if not str(value.get('key') or '').strip():
            _issue(issues, f'{path}.key', '기억 값을 확인할 키가 필요합니다.')
    elif op == 'selection_count':
        if not str(value.get('selection_key') or '').strip():
            _issue(issues, f'{path}.selection_key', '수를 확인할 선택 키가 필요합니다.')
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '선택 카드 필터는 객체여야 합니다.')
    elif op == 'selected_value':
        if not str(value.get('selection_key') or '').strip():
            _issue(issues, f'{path}.selection_key', '수치를 확인할 선택 키가 필요합니다.')
    elif op == 'selected_card_field':
        if not str(value.get('selection_key') or '').strip():
            _issue(issues, f'{path}.selection_key', '카드를 확인할 선택 키가 필요합니다.')
        if value.get('field') not in {
            'frame', 'damage', 'code', 'name', 'type', 'instance_id',
        }:
            _issue(issues, f'{path}.field', '확인할 카드 필드가 올바르지 않습니다.')
    elif op == 'selected_cards_field_sum':
        if not str(value.get('selection_key') or '').strip():
            _issue(issues, f'{path}.selection_key', '합산할 선택 키가 필요합니다.')
        if value.get('field') not in {'frame', 'damage'}:
            _issue(issues, f'{path}.field', '합산할 카드 수치가 올바르지 않습니다.')
    elif op == 'attached_count':
        if value.get('host') is not None:
            _validate_value(value.get('host'), f'{path}.host', issues)
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '세트 카드 필터는 객체여야 합니다.')


def _validate_effect(value, path, issues):
    if not isinstance(value, dict):
        _issue(issues, path, '실행 명령은 객체여야 합니다.')
        return
    op = value.get('op')
    if op not in EFFECT_OPS:
        _issue(issues, f'{path}.op', f'지원하지 않는 실행 명령입니다: {op!r}')
        return
    if op == 'sequence':
        items = value.get('effects')
        if not isinstance(items, list) or not items:
            _issue(issues, f'{path}.effects', '순차 실행할 명령 목록이 필요합니다.')
        else:
            for index, item in enumerate(items):
                _validate_effect(item, f'{path}.effects[{index}]', issues)
    if op == 'conditional':
        _validate_condition(value.get('condition'), f'{path}.condition', issues)
        for branch_name in ('then', 'else'):
            items = value.get(branch_name, [])
            if not isinstance(items, list):
                _issue(issues, f'{path}.{branch_name}', '조건 분기 명령은 배열이어야 합니다.')
                continue
            if branch_name == 'then' and not items:
                _issue(issues, f'{path}.then', '조건 충족 시 실행할 명령이 필요합니다.')
            for index, item in enumerate(items):
                _validate_effect(item, f'{path}.{branch_name}[{index}]', issues)
    if op == 'emit_event':
        if value.get('event') not in TRIGGERS:
            _issue(issues, f'{path}.event', '발행할 효과 이벤트가 올바르지 않습니다.')
        if not isinstance(value.get('payload', {}), dict):
            _issue(issues, f'{path}.payload', '효과 이벤트 데이터는 객체여야 합니다.')
        if 'source_only' in value and not isinstance(value.get('source_only'), bool):
            _issue(issues, f'{path}.source_only', '소스 카드 전용 이벤트 여부는 불리언이어야 합니다.')
    if op == 'set_memory':
        if not str(value.get('key') or '').strip():
            _issue(issues, f'{path}.key', '저장할 기억 값 키가 필요합니다.')
        if 'value' not in value:
            _issue(issues, f'{path}.value', '저장할 기억 값이 필요합니다.')
        else:
            _validate_value(value.get('value'), f'{path}.value', issues)
    if op in {'prevent', 'negate', 'replace'} and (
        value.get('selection_key') is not None
        and not str(value.get('selection_key') or '').strip()
    ):
        _issue(
            issues, f'{path}.selection_key',
            '선택 결과를 따르는 규칙 키가 올바르지 않습니다.',
        )
    if op == 'request_choice':
        _validate_selector(value.get('selector'), f'{path}.selector', issues)
        optional = bool(value.get('optional'))
        if not optional and 'default' not in value:
            _issue(issues, f'{path}.default', '필수 선택에는 만료 기본값이 필요합니다.', 'missing_default')
        if 'default' in value and not isinstance(value.get('default'), list):
            _issue(issues, f'{path}.default', '기본 선택은 ID 배열이어야 합니다.')
        if not isinstance(value.get('then', []), list):
            _issue(issues, f'{path}.then', '선택 후 명령은 배열이어야 합니다.')
        else:
            for index, item in enumerate(value.get('then') or []):
                _validate_effect(item, f'{path}.then[{index}]', issues)
        if 'else' in value and not isinstance(value.get('else'), list):
            _issue(
                issues, f'{path}.else',
                '후보 부족 시 대체 명령은 배열이어야 합니다.',
            )
        else:
            for index, item in enumerate(value.get('else') or []):
                _validate_effect(item, f'{path}.else[{index}]', issues)
        if 'skip_if_unavailable' in value and not isinstance(value.get('skip_if_unavailable'), bool):
            _issue(issues, f'{path}.skip_if_unavailable', '후보 부족 시 건너뛰기 여부는 불리언이어야 합니다.')
    if op == 'request_amount':
        _validate_value(value.get('min', 0), f'{path}.min', issues)
        _validate_value(value.get('max'), f'{path}.max', issues)
        if not str(value.get('selection_key') or '').strip():
            _issue(issues, f'{path}.selection_key', '수치 선택을 저장할 키가 필요합니다.')
        if 'default' in value and not isinstance(value.get('default'), int):
            _issue(issues, f'{path}.default', '수치 선택의 기본값은 정수여야 합니다.')
        if value.get('values') is not None and (
            not isinstance(value.get('values'), list)
            or not value.get('values')
            or any(
                not isinstance(item, int) or isinstance(item, bool)
                for item in value.get('values')
            )
            or len(value.get('values')) != len(set(value.get('values')))
        ):
            _issue(issues, f'{path}.values', '선택 가능 수치는 중복 없는 정수 배열이어야 합니다.')
        if not isinstance(value.get('then', []), list):
            _issue(issues, f'{path}.then', '수치 선택 후 명령은 배열이어야 합니다.')
        else:
            for index, item in enumerate(value.get('then') or []):
                _validate_effect(item, f'{path}.then[{index}]', issues)
    if op == 'choose_effect':
        options = value.get('options')
        minimum_options = 1 if value.get('optional') else 2
        if not isinstance(options, list) or len(options) < minimum_options:
            _issue(
                issues, f'{path}.options',
                '선택 효과는 실행 선택지 1개 이상, 필수 분기는 2개 이상이어야 합니다.',
            )
        else:
            option_ids = []
            for option_index, option in enumerate(options):
                option_path = f'{path}.options[{option_index}]'
                if not isinstance(option, dict) or not str(option.get('id') or '').strip():
                    _issue(issues, option_path, '효과 선택지 ID가 필요합니다.')
                    continue
                option_ids.append(str(option['id']))
                if option.get('condition') is not None:
                    _validate_condition(option.get('condition'), f'{option_path}.condition', issues)
                if option.get('selector_available') is not None:
                    _validate_selector(
                        option.get('selector_available'),
                        f'{option_path}.selector_available', issues,
                    )
                effects = option.get('effects')
                if not isinstance(effects, list) or not effects:
                    _issue(issues, f'{option_path}.effects', '선택 후 실행할 명령이 필요합니다.')
                    continue
                for effect_index, item in enumerate(effects):
                    _validate_effect(item, f'{option_path}.effects[{effect_index}]', issues)
            if len(option_ids) != len(set(option_ids)):
                _issue(issues, f'{path}.options', '효과 선택지 ID는 중복될 수 없습니다.')
            if not value.get('optional') and str(value.get('default') or '') not in option_ids:
                _issue(issues, f'{path}.default', '필수 효과 선택에는 유효한 기본값이 필요합니다.', 'missing_default')
    if op == 'end_combo' and 'source_event_card' in value and not isinstance(
        value.get('source_event_card'), bool,
    ):
        _issue(
            issues, f'{path}.source_event_card',
            '콤보 종료의 이벤트 카드 지정 여부는 불리언이어야 합니다.',
        )
    if op in {'move_card', 'draw', 'discard', 'reveal', 'hide', 'break_card', 'delete_token', 'random_select', 'capture_selection'}:
        selector = value.get('selector')
        if selector is not None:
            _validate_selector(selector, f'{path}.selector', issues)
    if op == 'exchange_cards':
        for field_name in ('first_selection_key', 'second_selection_key'):
            if not str(value.get(field_name) or '').strip():
                _issue(
                    issues, f'{path}.{field_name}',
                    '교체할 카드 선택 키가 필요합니다.',
                )
        first_key = str(value.get('first_selection_key') or '')
        second_key = str(value.get('second_selection_key') or '')
        if first_key and first_key == second_key:
            _issue(
                issues, path, '교체할 두 카드는 다른 선택 키가 필요합니다.',
            )
        if value.get('result_key') is not None and not str(
            value.get('result_key') or ''
        ).strip():
            _issue(
                issues, f'{path}.result_key',
                '교체 성공 결과 키가 올바르지 않습니다.',
            )
    if op == 'break_cards':
        card_instance_ids = value.get('card_instance_ids')
        selector = value.get('selector')
        selection_key = str(value.get('selection_key') or '').strip()
        if isinstance(selector, dict):
            _validate_selector(selector, f'{path}.selector', issues)
        elif selection_key:
            pass
        elif not isinstance(card_instance_ids, list) or len(card_instance_ids) < 2:
            _issue(
                issues, f'{path}.card_instance_ids',
                '일괄 브레이크할 카드 값 표현식 2개 이상, 선택기 또는 선택 키가 필요합니다.',
            )
        else:
            for index, item in enumerate(card_instance_ids):
                _validate_value(item, f'{path}.card_instance_ids[{index}]', issues)
        if 'require_all' in value and not isinstance(value.get('require_all'), bool):
            _issue(issues, f'{path}.require_all', '전체 성공 조건은 불리언이어야 합니다.')
    if op in {'move_card', 'discard', 'break_card', 'break_cards'} and (
        value.get('result_key') is not None
        and not str(value.get('result_key') or '').strip()
    ):
        _issue(issues, f'{path}.result_key', '작업 성공 결과를 저장할 키가 올바르지 않습니다.')
    if op in {'break_card', 'move_card'} and 'continue_resolution' in value and not isinstance(
        value.get('continue_resolution'), bool,
    ):
        _issue(
            issues, f'{path}.continue_resolution',
            '카드 이동 후 현재 기술 해결 계속 여부는 불리언이어야 합니다.',
        )
    if op in {'move_card', 'discard'} and value.get('block_hand_until') not in {
        None, 'battle', 'turn', 'next_turn',
    }:
        _issue(
            issues, f'{path}.block_hand_until',
            '패 이동 금지 범위가 올바르지 않습니다.',
        )
    if op == 'move_card':
        for field_name in (
            'preserve_attachment', 'allow_special_destination', 'as_get',
            'face_up',
        ):
            if field_name in value and not isinstance(value.get(field_name), bool):
                _issue(issues, f'{path}.{field_name}', '카드 이동 플래그는 불리언이어야 합니다.')
        if value.get('set_flags') is not None and not isinstance(value.get('set_flags'), dict):
            _issue(issues, f'{path}.set_flags', '이동 후 카드 플래그는 객체여야 합니다.')
    if op == 'capture_selection' and not str(value.get('selection_key') or '').strip():
        _issue(issues, f'{path}.selection_key', '선택 결과를 저장할 키가 필요합니다.')
    if op == 'copy_defense_judgments' and not str(value.get('selection_key') or '').strip():
        _issue(issues, f'{path}.selection_key', '수비 판정을 복사할 선택 키가 필요합니다.')
    if op == 'copy_clash_judgments' and not str(value.get('selection_key') or '').strip():
        _issue(issues, f'{path}.selection_key', '상쇄 판정을 복사할 선택 키가 필요합니다.')
    if op == 'modify_defense_judgments' and (
        not isinstance(value.get('value'), str)
        or not value.get('value').strip()
    ):
        _issue(issues, f'{path}.value', '변경할 수비 판정값이 필요합니다.')
    if op == 'invalidate_battle_card' and not (
        str(value.get('selection_key') or '').strip()
        or value.get('card_instance_id') is not None
    ):
        _issue(issues, f'{path}.selection_key', '무효화할 배틀 기술 선택 키가 필요합니다.')
    if op == 'force_ready' and not (
        str(value.get('selection_key') or '').strip()
        or value.get('card_instance_id') is not None
    ):
        _issue(issues, f'{path}.selection_key', '강제 레디할 기술 선택 키가 필요합니다.')
    if op == 'force_designated_get' and value.get('duration', 'turn') != 'turn':
        _issue(
            issues, f'{path}.duration',
            '상대 지정 Get 효과의 만료 범위는 turn이어야 합니다.',
        )
    if op == 'guess_hand_parity':
        selector = value.get('selector')
        if not isinstance(selector, dict):
            _issue(issues, f'{path}.selector', '홀짝을 확인할 상대 패 선택기가 필요합니다.')
        else:
            _validate_selector(selector, f'{path}.selector', issues)
        for branch_name in ('on_correct', 'on_wrong'):
            branch = value.get(branch_name)
            if not isinstance(branch, list):
                _issue(issues, f'{path}.{branch_name}', '홀짝 결과 명령은 배열이어야 합니다.')
            else:
                for index, branch_effect in enumerate(branch):
                    _validate_effect(branch_effect, f'{path}.{branch_name}[{index}]', issues)
        if value.get('repeat_on_correct') is not None and not isinstance(
            value.get('repeat_on_correct'), bool,
        ):
            _issue(issues, f'{path}.repeat_on_correct', '홀짝 반복 여부는 불리언이어야 합니다.')
        if value.get('repeat_always') is not None and not isinstance(
            value.get('repeat_always'), bool,
        ):
            _issue(issues, f'{path}.repeat_always', '추측 반복 여부는 불리언이어야 합니다.')
        categories = value.get('categories')
        valid_categories = {
            'odd', 'even', 'attack', 'odd_attack', 'even_attack', 'defense',
        }
        if categories is not None and (
            not isinstance(categories, list) or not categories
            or any(item not in valid_categories for item in categories)
            or len(categories) != len(set(categories))
        ):
            _issue(issues, f'{path}.categories', '추측 종류 목록이 올바르지 않습니다.')
    if op == 'modify_hand_guess_categories':
        categories = value.get('categories')
        valid_categories = {
            'odd', 'even', 'attack', 'odd_attack', 'even_attack', 'defense',
        }
        if (
            not isinstance(categories, list) or not categories
            or any(item not in valid_categories for item in categories)
            or len(categories) != len(set(categories))
        ):
            _issue(
                issues, f'{path}.categories',
                '변경할 추측 종류 목록이 올바르지 않습니다.',
            )
        if value.get('target_card') != 'event_card':
            _issue(
                issues, f'{path}.target_card',
                '추측 종류를 변경할 이벤트 기술 대상이 필요합니다.',
            )
        if value.get('duration') not in {None, 'battle'}:
            _issue(
                issues, f'{path}.duration',
                '추측 종류 변경의 만료 범위는 battle이어야 합니다.',
            )
        if value.get('max_attempts') is not None and (
            not isinstance(value.get('max_attempts'), int)
            or isinstance(value.get('max_attempts'), bool)
            or not 1 <= value.get('max_attempts') <= 50
        ):
            _issue(issues, f'{path}.max_attempts', '홀짝 최대 시도 횟수는 1~50 정수여야 합니다.')
    if op in {'discard', 'reveal', 'hide', 'delete_token'} and not (
        isinstance(value.get('selector'), dict) or str(value.get('selection_key') or '').strip()
        or value.get('card_instance_id') is not None
    ):
        _issue(issues, f'{path}.selector', '대상 선택기 또는 앞선 선택 키가 필요합니다.')
    if op == 'schedule' and isinstance(value.get('effect'), dict):
        _validate_effect(value['effect'], f'{path}.effect', issues)
    if op in {'deal_damage', 'change_hp', 'change_fp'} and 'amount' not in value:
        _issue(issues, f'{path}.amount', '변경량이 필요합니다.')
    elif op in {'deal_damage', 'change_hp', 'change_fp'}:
        _validate_value(value.get('amount'), f'{path}.amount', issues)
    if op == 'deal_damage' and 'repeat' in value:
        repeat = value.get('repeat')
        _validate_value(repeat, f'{path}.repeat', issues)
        if isinstance(repeat, int) and not isinstance(repeat, bool) and not 1 <= repeat <= 50:
            _issue(issues, f'{path}.repeat', '데미지 반복 횟수는 1~50이어야 합니다.')
    if op == 'deal_damage' and 'suppress_counter_gain' in value and not isinstance(
        value.get('suppress_counter_gain'), bool,
    ):
        _issue(
            issues, f'{path}.suppress_counter_gain',
            '카운터 획득 억제 여부는 불리언이어야 합니다.',
        )
    if op == 'draw':
        count = value.get('count', 1)
        _validate_value(count, f'{path}.count', issues)
    if op == 'move_card' and value.get('to_zone') not in ALL_ZONES:
        _issue(issues, f'{path}.to_zone', '유효한 이동 대상 존이 필요합니다.')
    if op == 'move_card' and value.get('max_zone_count') is not None and (
        not isinstance(value.get('max_zone_count'), int)
        or isinstance(value.get('max_zone_count'), bool)
        or value.get('max_zone_count') < 1
    ):
        _issue(issues, f'{path}.max_zone_count', '목적지 카드 상한은 1 이상의 정수여야 합니다.')
    if op in {'gain_state', 'lose_state'} and not str(value.get('state') or '').strip():
        _issue(issues, f'{path}.state', '상태 키가 필요합니다.')
    if op == 'gain_state' and value.get('expires') is not None:
        expires = value.get('expires')
        if not isinstance(expires, dict):
            _issue(issues, f'{path}.expires', '상태 만료 규칙은 객체여야 합니다.')
        else:
            if expires.get('event', 'phase_end') != 'phase_end':
                _issue(
                    issues, f'{path}.expires.event',
                    '상태 만료 이벤트는 phase_end여야 합니다.',
                )
            if expires.get('phase') not in PHASES:
                _issue(
                    issues, f'{path}.expires.phase',
                    '상태 만료 페이즈가 올바르지 않습니다.',
                )
            occurrences = expires.get('occurrences', 1)
            if (
                not isinstance(occurrences, int)
                or isinstance(occurrences, bool)
                or not 1 <= occurrences <= 20
            ):
                _issue(
                    issues, f'{path}.expires.occurrences',
                    '상태 만료 횟수는 1~20 정수여야 합니다.',
                )
    if op in {'change_counter', 'set_counter'}:
        if not str(value.get('counter') or '').strip():
            _issue(issues, f'{path}.counter', '카운터 키가 필요합니다.')
        if op == 'change_counter' and 'amount' not in value:
            _issue(issues, f'{path}.amount', '카운터 변경량이 필요합니다.')
        elif op == 'change_counter':
            _validate_value(value.get('amount'), f'{path}.amount', issues)
        if op == 'set_counter' and 'value' not in value:
            _issue(issues, f'{path}.value', '카운터 설정값이 필요합니다.')
        elif op == 'set_counter':
            _validate_value(value.get('value'), f'{path}.value', issues)
        for field_name in ('min', 'max'):
            boundary = value.get(field_name)
            if boundary is not None and (
                not isinstance(boundary, int) or isinstance(boundary, bool)
            ):
                _issue(issues, f'{path}.{field_name}', '카운터 범위는 정수여야 합니다.')
        if value.get('min') is not None and value.get('max') is not None and value['max'] < value['min']:
            _issue(issues, path, '카운터 최대값은 최소값 이상이어야 합니다.')
    if op == 'limit_counter_gain':
        if not str(value.get('counter') or '').strip():
            _issue(issues, f'{path}.counter', '획득을 제한할 카운터 키가 필요합니다.')
        maximum = value.get('max')
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
            _issue(issues, f'{path}.max', '카운터 획득 상한은 0 이상의 정수여야 합니다.')
        if value.get('duration', 'turn') not in {'phase', 'battle', 'turn', 'game'}:
            _issue(issues, f'{path}.duration', '카운터 획득 제한 기간이 올바르지 않습니다.')
    if op == 'gain_shield':
        if 'amount' not in value:
            _issue(issues, f'{path}.amount', '보호막 수치가 필요합니다.')
        else:
            _validate_value(value.get('amount'), f'{path}.amount', issues)
        if value.get('duration') not in {None, 'battle', 'phase', 'turn', 'game'}:
            _issue(issues, f'{path}.duration', '보호막 지속 시간은 battle/phase/turn/game 중 하나여야 합니다.')
    if op == 'grant_effect_immunity':
        if value.get('scope') not in {'opponent', 'other_cards', 'source_codes'}:
            _issue(
                issues, f'{path}.scope',
                '효과 면역 범위는 opponent/other_cards/source_codes 중 하나여야 합니다.',
            )
        if value.get('scope') == 'source_codes' and (
            not isinstance(value.get('source_codes'), list)
            or not value.get('source_codes')
            or any(not str(item or '').strip() for item in value.get('source_codes') or [])
        ):
            _issue(issues, f'{path}.source_codes', '면역할 효과 원본 카드 코드가 필요합니다.')
        operations = value.get('operations', [])
        if not isinstance(operations, list) or any(
            operation not in {
                'modify_stat', 'modify_judgment', 'move_card', 'break_card',
                'discard', 'invalidate_battle_card',
            }
            for operation in operations
        ):
            _issue(issues, f'{path}.operations', '효과 면역 명령 범위가 올바르지 않습니다.')
        stats = value.get('stats', [])
        if not isinstance(stats, list) or any(stat not in {'frame', 'damage'} for stat in stats):
            _issue(issues, f'{path}.stats', '효과 면역 수치는 frame/damage만 지원합니다.')
        directions = value.get('directions', [])
        if not isinstance(directions, list) or any(
            direction not in {'increase', 'decrease'} for direction in directions
        ):
            _issue(issues, f'{path}.directions', '효과 면역 방향이 올바르지 않습니다.')
        if directions and not stats:
            _issue(issues, f'{path}.stats', '증감 방향 면역에는 대상 수치가 필요합니다.')
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '효과 면역 카드 필터는 객체여야 합니다.')
        if value.get('duration') not in {
            'event', 'battle', 'phase', 'turn', 'next_turn', 'game',
            'continuous',
        }:
            _issue(issues, f'{path}.duration', '효과 면역 지속 시간이 올바르지 않습니다.')
    if op == 'replace_get' and value.get('player') is not None and not isinstance(
        value.get('player'), (dict, str),
    ):
        _issue(issues, f'{path}.player', '대체 Get 대상 플레이어가 올바르지 않습니다.')
    if op in {'modify_stat', 'fix_speed'}:
        if value.get('stat') not in {'frame', 'damage'}:
            _issue(issues, f'{path}.stat', '변경 수치는 frame 또는 damage여야 합니다.')
        if op == 'fix_speed' and value.get('stat') != 'frame':
            _issue(issues, f'{path}.stat', '속도 고정은 frame 수치에만 사용할 수 있습니다.')
        if value.get('duration') not in {
            None, 'event', 'combo', 'battle', 'phase', 'turn', 'game',
            'continuous',
        }:
            _issue(issues, f'{path}.duration', '지원하지 않는 지속 시간입니다.')
        numeric_key = 'value' if op == 'fix_speed' or value.get('fixed') else 'amount'
        if numeric_key not in value:
            _issue(issues, f'{path}.{numeric_key}', '수치 변경값이 필요합니다.')
        else:
            _validate_value(value.get(numeric_key), f'{path}.{numeric_key}', issues)
        if (
            value.get('preserve_prior_speed_changes') is not None
            and not isinstance(value.get('preserve_prior_speed_changes'), bool)
        ):
            _issue(
                issues, f'{path}.preserve_prior_speed_changes',
                '선행 속도 변경 보존 여부는 boolean이어야 합니다.',
            )
        if (
            value.get('preserve_prior_speed_changes') is not None
            and op != 'fix_speed'
        ):
            _issue(
                issues, f'{path}.preserve_prior_speed_changes',
                '선행 속도 변경 보존은 속도 고정에만 사용할 수 있습니다.',
            )
    if op == 'modify_damage':
        if 'amount' not in value:
            _issue(issues, f'{path}.amount', '데미지 보정값이 필요합니다.')
        else:
            _validate_value(value.get('amount'), f'{path}.amount', issues)
        if value.get('duration') not in {
            None, 'event', 'battle', 'phase', 'turn', 'game', 'continuous',
        }:
            _issue(issues, f'{path}.duration', '데미지 보정 지속 시간이 올바르지 않습니다.')
        if value.get('max_uses') is not None and (
            not isinstance(value.get('max_uses'), int)
            or isinstance(value.get('max_uses'), bool)
            or value.get('max_uses') < 1
        ):
            _issue(issues, f'{path}.max_uses', '데미지 보정 적용 횟수는 1 이상의 정수여야 합니다.')
    if op == 'modify_judgment':
        if value.get('field') not in {
            'hit', 'counter', 'guard', 'pos', 'special',
            'g_top', 'g_mid', 'g_bot',
        }:
            _issue(
                issues, f'{path}.field',
                '변경할 판정은 hit/counter/guard/pos/special 또는 '
                'g_top/g_mid/g_bot 중 하나여야 합니다.',
            )
        if (
            not isinstance(value.get('value'), str)
            or (value.get('mode', 'replace') != 'clear' and not value.get('value').strip())
        ):
            _issue(issues, f'{path}.value', '변경할 판정값이 필요합니다.')
        if value.get('mode', 'replace') not in {'replace', 'append', 'clear'}:
            _issue(issues, f'{path}.mode', '판정 변경 방식은 replace/append/clear 중 하나여야 합니다.')
        if value.get('scope', 'battle') not in {'battle', 'all_zones'}:
            _issue(
                issues, f'{path}.scope',
                '판정 변경 범위는 battle 또는 all_zones여야 합니다.',
            )
        if value.get('duration') not in {
            None, 'battle', 'phase', 'turn', 'game', 'continuous',
        }:
            _issue(
                issues, f'{path}.duration',
                '판정 변경 지속 시간이 올바르지 않습니다.',
            )
        target_zones = value.get('target_zones')
        if target_zones is not None and (
            not isinstance(target_zones, list)
            or any(zone not in ALL_ZONES for zone in target_zones)
        ):
            _issue(
                issues, f'{path}.target_zones',
                '판정 변경 대상 존 목록이 올바르지 않습니다.',
            )
    if op in {'skip_phase', 'repeat_phase'} and value.get('phase') not in PHASES:
        _issue(issues, f'{path}.phase', '유효한 페이즈가 필요합니다.')
    if op == 'repeat_phase' and 'after_current' in value and not isinstance(
        value.get('after_current'), bool,
    ):
        _issue(
            issues, f'{path}.after_current',
            '현재 페이즈 종료 후 반복 여부는 불리언이어야 합니다.',
        )
    if op == 'schedule':
        when = value.get('when')
        if not isinstance(when, dict) or when.get('event') not in TRIGGERS:
            _issue(issues, f'{path}.when.event', '예약 효과의 유효한 이벤트가 필요합니다.')
        elif when.get('controller') not in {None, 'self', 'opponent', 'p1', 'p2'}:
            _issue(issues, f'{path}.when.controller', '예약 효과의 발생 플레이어가 올바르지 않습니다.')
        if isinstance(when, dict) and when.get('where_event_card') is not None and not isinstance(
            when.get('where_event_card'), dict
        ):
            _issue(issues, f'{path}.when.where_event_card', '예약 이벤트 카드 필터는 객체여야 합니다.')
        if isinstance(when, dict) and when.get('condition') is not None:
            _validate_condition(
                when.get('condition'), f'{path}.when.condition', issues,
            )
        if not isinstance(value.get('effect'), dict):
            _issue(issues, f'{path}.effect', '예약할 명령이 필요합니다.')
        if value.get('duration') not in {
            None, 'battle', 'phase', 'turn', 'next_turn', 'game',
        }:
            _issue(issues, f'{path}.duration', '예약 효과의 지속 시간이 올바르지 않습니다.')
        if value.get('effect_controller') not in {None, 'scheduled', 'event'}:
            _issue(
                issues, f'{path}.effect_controller',
                '예약 효과의 실행 주체는 scheduled 또는 event여야 합니다.',
            )
        if 'preserve_source' in value and not isinstance(
            value.get('preserve_source'), bool,
        ):
            _issue(
                issues, f'{path}.preserve_source',
                '예약 효과의 원래 출처 보존 여부는 불리언이어야 합니다.',
            )
        if 'repeat' in value and not isinstance(value.get('repeat'), bool):
            _issue(
                issues, f'{path}.repeat',
                '예약 효과의 반복 여부는 불리언이어야 합니다.',
            )
    if op == 'win_game' and value.get('reason') is not None and not str(
        value.get('reason') or ''
    ).strip():
        _issue(issues, f'{path}.reason', '특수 승리 사유는 빈 문자열일 수 없습니다.')
    if op == 'random_select':
        _validate_value(value.get('count', 1), f'{path}.count', issues)
        if not isinstance(value.get('selector'), dict):
            _issue(issues, f'{path}.selector', '무작위 후보 선택기가 필요합니다.')
        count = value.get('count', 1)
        if (
            not isinstance(count, dict)
            and (not isinstance(count, int) or isinstance(count, bool) or count < 0)
        ):
            _issue(issues, f'{path}.count', '무작위 선택 수는 0 이상의 정수여야 합니다.')
    if op == 'grant_catch':
        allow_zones = value.get('allow_zones', ['hand'])
        if not isinstance(allow_zones, list) or not allow_zones or any(zone not in ALL_ZONES for zone in allow_zones):
            _issue(issues, f'{path}.allow_zones', '캐치에 사용할 존 목록이 올바르지 않습니다.')
        for field_name in ('min_speed', 'max_speed'):
            speed = value.get(field_name)
            if speed is not None and (
                not isinstance(speed, int) or isinstance(speed, bool) or speed < 1
            ):
                _issue(issues, f'{path}.{field_name}', '캐치 속도 제한은 1 이상의 정수여야 합니다.')
        if value.get('min_speed') and value.get('max_speed') and value['max_speed'] < value['min_speed']:
            _issue(issues, path, '캐치 최대 속도는 최소 속도 이상이어야 합니다.')
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '캐치 카드 필터는 객체여야 합니다.')
        if 'source_only' in value and not isinstance(value.get('source_only'), bool):
            _issue(issues, f'{path}.source_only', '소스 카드 전용 캐치 여부는 불리언이어야 합니다.')
        if 'source_attached' in value and not isinstance(value.get('source_attached'), bool):
            _issue(issues, f'{path}.source_attached', '소스에 세트된 카드 전용 여부는 불리언이어야 합니다.')
        if 'damage_bonus' in value:
            _validate_value(value.get('damage_bonus'), f'{path}.damage_bonus', issues)
        if 'return_source_to_hand' in value and not isinstance(value.get('return_source_to_hand'), bool):
            _issue(issues, f'{path}.return_source_to_hand', '캐치 후 소스 회수 여부는 불리언이어야 합니다.')
        if 'break_after_use' in value and not isinstance(value.get('break_after_use'), bool):
            _issue(issues, f'{path}.break_after_use', '캐치 기술의 사용 후 브레이크 여부는 불리언이어야 합니다.')
        if 'break_source_after_use' in value and not isinstance(value.get('break_source_after_use'), bool):
            _issue(issues, f'{path}.break_source_after_use', '캐치 후 소스 브레이크 여부는 불리언이어야 합니다.')
        counter_exemption = value.get('counter_exemption_on_source_break')
        if counter_exemption is not None:
            if not isinstance(counter_exemption, dict):
                _issue(
                    issues, f'{path}.counter_exemption_on_source_break',
                    '소스 브레이크 시 카운터 소비 면제는 객체여야 합니다.',
                )
            elif not str(counter_exemption.get('counter') or '').strip():
                _issue(
                    issues,
                    f'{path}.counter_exemption_on_source_break.counter',
                    '소비를 면제할 카운터 키가 필요합니다.',
                )
        replacement = value.get('effect_replacement')
        if replacement is not None:
            replacement_path = f'{path}.effect_replacement'
            if not isinstance(replacement, dict):
                _issue(
                    issues, replacement_path,
                    '캐치 기술 효과 교체 정의는 객체여야 합니다.',
                )
            else:
                replacement_abilities = replacement.get('abilities')
                if not isinstance(replacement_abilities, list) or not replacement_abilities:
                    _issue(
                        issues, f'{replacement_path}.abilities',
                        '캐치 기술 효과 교체에는 하나 이상의 능력이 필요합니다.',
                    )
                else:
                    seen_replacement_ids = set()
                    for replacement_index, replacement_ability in enumerate(
                        replacement_abilities
                    ):
                        ability_path = (
                            f'{replacement_path}.abilities[{replacement_index}]'
                        )
                        if not isinstance(replacement_ability, dict):
                            _issue(
                                issues, ability_path,
                                '캐치 기술 교체 능력은 객체여야 합니다.',
                            )
                            continue
                        replacement_id = str(
                            replacement_ability.get('id') or ''
                        ).strip()
                        if not replacement_id or not re.fullmatch(
                            r'[a-z0-9_.:-]+', replacement_id,
                        ):
                            _issue(
                                issues, f'{ability_path}.id',
                                '캐치 기술 교체 능력에는 안정적인 영문 소문자 ID가 필요합니다.',
                            )
                        elif replacement_id in seen_replacement_ids:
                            _issue(
                                issues, f'{ability_path}.id',
                                f'캐치 기술 교체 능력 ID가 중복되었습니다: {replacement_id}',
                            )
                        seen_replacement_ids.add(replacement_id)
                        event = replacement_ability.get('event')
                        if event not in {'use', 'catch', 'hit', 'after_use'}:
                            _issue(
                                issues, f'{ability_path}.event',
                                '캐치 기술 교체 능력 이벤트는 use/catch/hit/after_use 중 하나여야 합니다.',
                            )
                        timing = replacement_ability.get('timing')
                        if timing not in TIMING_ORDER:
                            _issue(
                                issues, f'{ability_path}.timing',
                                '캐치 기술 교체 능력의 처리 타이밍이 올바르지 않습니다.',
                            )
                        replacement_effects = replacement_ability.get('effects')
                        if not isinstance(replacement_effects, list) or not replacement_effects:
                            _issue(
                                issues, f'{ability_path}.effects',
                                '캐치 기술 교체 능력에는 하나 이상의 명령이 필요합니다.',
                            )
                        else:
                            for effect_index, replacement_effect in enumerate(
                                replacement_effects
                            ):
                                _validate_effect(
                                    replacement_effect,
                                    f'{ability_path}.effects[{effect_index}]',
                                    issues,
                                )
    if op == 'grant_flexible_use':
        allow_zones = value.get('allow_zones', ['list'])
        if not isinstance(allow_zones, list) or not allow_zones or any(
            zone not in ALL_ZONES for zone in allow_zones
        ):
            _issue(issues, f'{path}.allow_zones', '추가 사용 허용 존이 올바르지 않습니다.')
        if value.get('where') is not None and not isinstance(value.get('where'), dict):
            _issue(issues, f'{path}.where', '추가 사용 카드 필터는 객체여야 합니다.')
        maximum = value.get('max_uses', 1)
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
            _issue(issues, f'{path}.max_uses', '추가 사용 횟수는 1 이상의 정수여야 합니다.')
        if value.get('usage_scope', 'turn') not in {'turn', 'battle', 'game'}:
            _issue(issues, f'{path}.usage_scope', '추가 사용 제한 범위가 올바르지 않습니다.')
        contexts = value.get('contexts', ['combo', 'catch'])
        if (
            not isinstance(contexts, list) or not contexts
            or any(item not in {'combo', 'catch'} for item in contexts)
            or len(contexts) != len(set(contexts))
        ):
            _issue(
                issues, f'{path}.contexts',
                '추가 사용 문맥은 중복 없는 콤보/캐치 목록이어야 합니다.',
            )
    if op == 'shuffle_zone':
        if value.get('zone') not in ALL_ZONES:
            _issue(issues, f'{path}.zone', '섞을 유효한 존이 필요합니다.')
        if 'face_up' in value and not isinstance(value.get('face_up'), bool):
            _issue(issues, f'{path}.face_up', '섞은 카드의 공개 여부는 불리언이어야 합니다.')
    if op == 'attach_card':
        if not (
            str(value.get('selection_key') or '').strip()
            or value.get('card_instance_id') is not None
            or isinstance(value.get('selector'), dict)
        ):
            _issue(issues, f'{path}.selection_key', '세트할 카드 대상이 필요합니다.')
        if value.get('to_card_instance_id') is None:
            _issue(issues, f'{path}.to_card_instance_id', '세트 대상 기술이 필요합니다.')
        if value.get('attachment_expires') not in {None, 'battle'}:
            _issue(issues, f'{path}.attachment_expires', '세트 만료 범위가 올바르지 않습니다.')
        if 'return_to_hand_on_expiry' in value and not isinstance(value.get('return_to_hand_on_expiry'), bool):
            _issue(issues, f'{path}.return_to_hand_on_expiry', '세트 만료 시 회수 여부는 불리언이어야 합니다.')
        if 'face_up' in value and not isinstance(value.get('face_up'), bool):
            _issue(issues, f'{path}.face_up', '세트 직후 공개 여부는 불리언이어야 합니다.')
    if op == 'modify_combo':
        allow_zones = value.get('allow_zones', [])
        if not isinstance(allow_zones, list) or any(zone not in ALL_ZONES for zone in allow_zones):
            _issue(issues, f'{path}.allow_zones', '콤보 사용 허용 존 목록이 올바르지 않습니다.')
        source_zones = value.get('source_zones')
        if source_zones is not None and (
            not isinstance(source_zones, list)
            or any(zone not in ALL_ZONES for zone in source_zones)
        ):
            _issue(
                issues, f'{path}.source_zones',
                '콤보 규칙을 적용할 원본 존 목록이 올바르지 않습니다.',
            )
        for field_name in ('where', 'after_where'):
            if value.get(field_name) is not None and not isinstance(value.get(field_name), dict):
                _issue(issues, f'{path}.{field_name}', '콤보 카드 필터는 객체여야 합니다.')
        for field_name in (
            'min_combo', 'max_combo', 'max_combo_cap', 'extend_combo_to',
        ):
            field_value = value.get(field_name)
            if field_value is not None and (
                not isinstance(field_value, int) or isinstance(field_value, bool) or field_value < 2
            ):
                _issue(issues, f'{path}.{field_name}', '콤보 번호는 2 이상의 정수여야 합니다.')
        extend_combo_by = value.get('extend_combo_by')
        if extend_combo_by is not None and (
            not isinstance(extend_combo_by, int)
            or isinstance(extend_combo_by, bool)
            or extend_combo_by < 1
        ):
            _issue(
                issues, f'{path}.extend_combo_by',
                '콤보 추가 횟수는 1 이상의 정수여야 합니다.',
            )
        max_speed_delta = value.get('max_speed_delta')
        if max_speed_delta is not None and (
            not isinstance(max_speed_delta, int)
            or isinstance(max_speed_delta, bool)
            or max_speed_delta < 1
        ):
            _issue(
                issues, f'{path}.max_speed_delta',
                '다음 콤보 속도 차이 상한은 1 이상의 정수여야 합니다.',
            )
        if value.get('min_combo') and value.get('max_combo') and value['max_combo'] < value['min_combo']:
            _issue(issues, path, '최대 콤보 번호는 최소 콤보 번호 이상이어야 합니다.')
        usage_key = str(value.get('usage_key') or '').strip()
        if value.get('max_uses') is not None and not usage_key:
            _issue(
                issues, f'{path}.usage_key',
                '콤보 추가 사용 횟수 제한에는 사용 키가 필요합니다.',
            )
        if value.get('max_uses') is not None and (
            not isinstance(value.get('max_uses'), int)
            or isinstance(value.get('max_uses'), bool)
            or value.get('max_uses') < 1
        ):
            _issue(
                issues, f'{path}.max_uses',
                '콤보 추가 사용 횟수는 1 이상의 정수여야 합니다.',
            )
        if value.get('usage_scope') not in {None, 'turn', 'battle', 'game'}:
            _issue(
                issues, f'{path}.usage_scope',
                '콤보 추가 사용 제한 범위가 올바르지 않습니다.',
            )
        for field_name in (
            'ignore_speed', 'ignore_damage_penalty',
            'optional_ignore_damage_penalty', 'optional_ignore_speed',
            'any_speed', 'optional_any_speed',
            'after_source', 'break_after_use', 'source_only',
            'after_source_sequence', 'skip_get_on_use',
            'usage_key_source_scoped',
            'where_source_attached',
            'where_event_attached',
            'negate_effects',
            'end_after_use', 'return_to_hand_after_use', 'exclude_source',
            'numbered_effect', 'requires_followup',
            'reopen_combo', 'allow_reuse', 'respect_speed_window',
            'break_on_optional_ignore_damage_penalty',
        ):
            if field_name in value and not isinstance(value.get(field_name), bool):
                _issue(issues, f'{path}.{field_name}', '콤보 예외 플래그는 불리언이어야 합니다.')
        if value.get('allow_reuse') and (
            not usage_key or value.get('max_uses') is None
        ):
            _issue(
                issues, f'{path}.allow_reuse',
                '같은 카드 재사용 허용에는 사용 키와 최대 사용 횟수가 필요합니다.',
            )
        followup_combo = value.get('requires_followup_at_combo')
        if followup_combo is not None and (
            not isinstance(followup_combo, int)
            or isinstance(followup_combo, bool) or followup_combo < 2
        ):
            _issue(
                issues, f'{path}.requires_followup_at_combo',
                '후속 기술을 요구할 콤보 번호는 2 이상이어야 합니다.',
            )
        counter_cost = value.get('counter_cost')
        if counter_cost is not None:
            if not isinstance(counter_cost, dict):
                _issue(
                    issues, f'{path}.counter_cost',
                    '콤보 카운터 비용은 객체여야 합니다.',
                )
            else:
                if not str(counter_cost.get('counter') or '').strip():
                    _issue(
                        issues, f'{path}.counter_cost.counter',
                        '소모할 카운터 키가 필요합니다.',
                    )
                amount = counter_cost.get('amount')
                if (
                    not isinstance(amount, int) or isinstance(amount, bool)
                    or amount < 1
                ):
                    _issue(
                        issues, f'{path}.counter_cost.amount',
                        '카운터 비용은 1 이상의 정수여야 합니다.',
                    )
        optional_speed_cost = value.get('optional_speed_cost')
        if optional_speed_cost is not None:
            if not isinstance(optional_speed_cost, dict):
                _issue(
                    issues, f'{path}.optional_speed_cost',
                    '선택형 콤보 속도 비용은 객체여야 합니다.',
                )
            else:
                if optional_speed_cost.get('operation') != 'discard':
                    _issue(
                        issues, f'{path}.optional_speed_cost.operation',
                        '지원하지 않는 선택형 콤보 속도 비용입니다.',
                    )
                _validate_selector(
                    optional_speed_cost.get('selector'),
                    f'{path}.optional_speed_cost.selector', issues,
                )
            if not (
                value.get('optional_any_speed')
                or value.get('optional_ignore_speed')
            ):
                _issue(
                    issues, f'{path}.optional_speed_cost',
                    '선택형 속도 예외가 있어야 속도 비용을 지정할 수 있습니다.',
                )
        counter_gain = value.get('counter_on_speed_delta')
        if counter_gain is not None:
            if not isinstance(counter_gain, dict):
                _issue(
                    issues, f'{path}.counter_on_speed_delta',
                    '속도 차이 카운터 예측은 객체여야 합니다.',
                )
            else:
                if not str(counter_gain.get('counter') or '').strip():
                    _issue(
                        issues, f'{path}.counter_on_speed_delta.counter',
                        '획득할 카운터 키가 필요합니다.',
                    )
                for field_name, minimum in (('delta', 1), ('amount', 1), ('max', 1)):
                    field_value = counter_gain.get(field_name)
                    if field_name == 'max' and field_value is None:
                        continue
                    if (
                        not isinstance(field_value, int)
                        or isinstance(field_value, bool)
                        or field_value < minimum
                    ):
                        _issue(
                            issues,
                            f'{path}.counter_on_speed_delta.{field_name}',
                            '속도 차이 카운터 수치는 1 이상의 정수여야 합니다.',
                        )
        speed_options = value.get('speed_options')
        if speed_options is not None and (
            not isinstance(speed_options, list)
            or not speed_options
            or any(not isinstance(item, int) or isinstance(item, bool) or item < 1 for item in speed_options)
            or len(set(speed_options)) != len(speed_options)
        ):
            _issue(issues, f'{path}.speed_options', '콤보 선택 속도는 중복 없는 양의 정수 배열이어야 합니다.')
        break_after_use_speeds = value.get('break_after_use_speeds')
        if break_after_use_speeds is not None and (
            not isinstance(break_after_use_speeds, list)
            or not break_after_use_speeds
            or any(
                not isinstance(item, int) or isinstance(item, bool) or item < 1
                for item in break_after_use_speeds
            )
            or len(set(break_after_use_speeds)) != len(break_after_use_speeds)
        ):
            _issue(
                issues, f'{path}.break_after_use_speeds',
                '사용 후 브레이크 속도는 중복 없는 양의 정수 배열이어야 합니다.',
            )
        damage_bonus = value.get('damage_bonus')
        if damage_bonus is not None:
            _validate_value(damage_bonus, f'{path}.damage_bonus', issues)
        damage_bonus_speed = value.get('damage_bonus_speed')
        if damage_bonus_speed is not None and (
            not isinstance(damage_bonus_speed, int)
            or isinstance(damage_bonus_speed, bool)
            or damage_bonus_speed < 1
        ):
            _issue(
                issues, f'{path}.damage_bonus_speed',
                '조건부 콤보 데미지 보너스 속도는 양의 정수여야 합니다.',
            )
        if value.get('duration') not in {
            None, 'combo', 'battle', 'phase', 'turn', 'game', 'continuous',
        }:
            _issue(issues, f'{path}.duration', '콤보 규칙의 지속 시간이 올바르지 않습니다.')
        if value.get('borrow_from') not in {None, 'opponent'}:
            _issue(issues, f'{path}.borrow_from', '빌려올 카드의 소유자 범위가 올바르지 않습니다.')
        if value.get('return_to_owner_zone_on_combo_end') not in {None, 'list'}:
            _issue(issues, f'{path}.return_to_owner_zone_on_combo_end', '빌린 카드의 반환 영역이 올바르지 않습니다.')
        _validate_condition(value.get('condition'), f'{path}.condition', issues)
    if op == 'modify_state_rule':
        if not str(value.get('state') or '').strip():
            _issue(issues, f'{path}.state', '변경할 상태 규칙의 상태 키가 필요합니다.')
        if not str(value.get('field') or '').strip():
            _issue(issues, f'{path}.field', '변경할 상태 규칙의 필드 키가 필요합니다.')
        _validate_value(value.get('value'), f'{path}.value', issues)
        if value.get('mode', 'replace') not in {'replace', 'minimum', 'maximum'}:
            _issue(issues, f'{path}.mode', '상태 규칙 변경 방식이 올바르지 않습니다.')
        if value.get('duration') not in {None, 'continuous'}:
            _issue(issues, f'{path}.duration', '상태 규칙 변경은 continuous 지속 시간이어야 합니다.')
    if op == 'create_token' and value.get('zone', 'passive') not in ALL_ZONES:
        _issue(issues, f'{path}.zone', '토큰을 만들 존이 올바르지 않습니다.')
    if op == 'create_token' and 'repeat' in value:
        repeat = value.get('repeat')
        _validate_value(repeat, f'{path}.repeat', issues)
        if isinstance(repeat, int) and not isinstance(repeat, bool) and not 1 <= repeat <= 50:
            _issue(issues, f'{path}.repeat', '토큰 생성 횟수는 1~50이어야 합니다.')
    if op == 'create_token' and value.get('max_zone_count') is not None and (
        not isinstance(value.get('max_zone_count'), int)
        or isinstance(value.get('max_zone_count'), bool)
        or value.get('max_zone_count') < 1
    ):
        _issue(
            issues, f'{path}.max_zone_count',
            '토큰 영역 상한은 1 이상의 정수여야 합니다.',
        )
    if op in {'prevent', 'negate', 'replace'}:
        kind = value.get('kind', value.get('target'))
        if kind not in PREVENT_KINDS:
            _issue(issues, f'{path}.kind', f'지원하지 않는 금지·대체 대상입니다: {kind!r}')
        if op == 'replace' and (kind != 'damage' or 'amount' not in value):
            _issue(issues, path, 'replace는 damage 대상과 대체 amount가 필요합니다.')
        if kind in {'ready', 'use_card'} and value.get('duration') not in {
            'battle', 'phase', 'turn', 'game', 'continuous',
        }:
            _issue(
                issues, f'{path}.duration',
                '카드 사용 금지는 battle/phase/turn/game/continuous 지속 시간이 필요합니다.',
            )
        if value.get('duration') not in {None, 'event', 'battle', 'phase', 'turn', 'game', 'continuous'}:
            _issue(issues, f'{path}.duration', '지원하지 않는 지속 시간입니다.')
        if 'controller_only' in value and not isinstance(
            value.get('controller_only'), bool,
        ):
            _issue(
                issues, f'{path}.controller_only',
                '제어자 원인 제한은 불리언이어야 합니다.',
            )
        if value.get('max_uses') is not None and (
            not isinstance(value.get('max_uses'), int)
            or isinstance(value.get('max_uses'), bool)
            or value.get('max_uses') < 1
        ):
            _issue(issues, f'{path}.max_uses', '금지·대체 적용 횟수는 1 이상의 정수여야 합니다.')
        _validate_condition(value.get('condition'), f'{path}.condition', issues)
        for filter_name in ('where', 'against_where'):
            if value.get(filter_name) is not None and not isinstance(value.get(filter_name), dict):
                _issue(issues, f'{path}.{filter_name}', '카드 필터는 객체여야 합니다.')
        if 'unless_event_attached' in value and not isinstance(
            value.get('unless_event_attached'), bool,
        ):
            _issue(
                issues, f'{path}.unless_event_attached',
                '이벤트 카드에 세트된 기술 예외 여부는 불리언이어야 합니다.',
            )
        target_zones = value.get('target_zones')
        if target_zones is not None and (
            not isinstance(target_zones, list)
            or any(zone not in ALL_ZONES for zone in target_zones)
        ):
            _issue(issues, f'{path}.target_zones', '금지 대상 존 목록이 올바르지 않습니다.')
    if op == 'static_rule':
        rules = value.get('rules')
        if (
            not isinstance(rules, list) or not rules
            or any(not str(rule or '').strip() for rule in rules)
            or len({str(rule) for rule in rules}) != len(rules)
        ):
            _issue(issues, f'{path}.rules', '연결된 정적 규칙 이름은 중복 없는 문자열 배열이어야 합니다.')
    if op == 'log' and not isinstance(value.get('text', ''), str):
        _issue(issues, f'{path}.text', '로그 문구는 문자열이어야 합니다.')
    if op == 'set_usage_limit':
        if not str(value.get('key') or '').strip():
            _issue(issues, f'{path}.key', '사용 제한 키가 필요합니다.')
        if value.get('scope', 'game') not in {'game', 'turn', 'phase', 'battle'}:
            _issue(issues, f'{path}.scope', '사용 제한 범위가 올바르지 않습니다.')
        if not isinstance(value.get('value', 1), int) or isinstance(value.get('value', 1), bool):
            _issue(issues, f'{path}.value', '사용 제한 값은 정수여야 합니다.')


def validate_effect_definition(definition, *, require_coverage=False, card_has_text=False, handler_names=None):
    issues = []
    if not isinstance(definition, dict):
        return [ValidationIssue('$', '효과 정의는 객체여야 합니다.')]
    if definition.get('schema_version') != EFFECT_SCHEMA_VERSION:
        _issue(issues, '$.schema_version', f'스키마 버전은 {EFFECT_SCHEMA_VERSION}이어야 합니다.')
    source_digest = definition.get('source_digest')
    if source_digest is not None and not re.fullmatch(r'[0-9a-f]{64}', str(source_digest)):
        _issue(issues, '$.source_digest', '출처 해시는 SHA-256 소문자 64자리여야 합니다.')
    deck_limit = definition.get('deck_limit')
    if deck_limit is not None and (
        not isinstance(deck_limit, int) or isinstance(deck_limit, bool) or deck_limit < 1
    ):
        _issue(issues, '$.deck_limit', '동명 카드 덱 제한은 1 이상의 정수여야 합니다.')
    _validate_deck_rules(definition.get('deck_rules'), '$.deck_rules', issues)
    _validate_deck_rules(
        definition.get('deck_rules_when_included'),
        '$.deck_rules_when_included', issues,
    )
    token_key = definition.get('token_key')
    if token_key is not None and not re.fullmatch(r'[a-z0-9_]+', str(token_key)):
        _issue(issues, '$.token_key', '토큰 키는 영문 소문자·숫자·밑줄만 사용할 수 있습니다.')
    token_usage = definition.get('token_usage')
    if token_usage is not None and (
        not isinstance(token_usage, list)
        or any(item not in {'token', 'counter'} for item in token_usage)
        or len(set(token_usage)) != len(token_usage)
    ):
        _issue(issues, '$.token_usage', '토큰 사용 방식은 token/counter 중복 없는 배열이어야 합니다.')
    card_form = definition.get('card_form')
    if card_form is not None:
        if not isinstance(card_form, dict):
            _issue(issues, '$.card_form', '카드 취급 정보는 객체여야 합니다.')
        else:
            active_zones = card_form.get('active_zones')
            if (
                not isinstance(active_zones, list) or not active_zones
                or any(zone not in ALL_ZONES for zone in active_zones)
            ):
                _issue(issues, '$.card_form.active_zones', '카드 취급이 적용되는 유효한 존 배열이 필요합니다.')
            if not str(card_form.get('type') or '').strip():
                _issue(issues, '$.card_form.type', '취급할 카드 종류가 필요합니다.')
            frame = card_form.get('frame')
            if frame is not None and (
                not isinstance(frame, int) or isinstance(frame, bool) or frame < 1
            ):
                _issue(issues, '$.card_form.frame', '취급 속도는 1 이상의 정수여야 합니다.')
            form_token_key = card_form.get('token_key')
            if form_token_key is not None and not re.fullmatch(r'[a-z0-9_]+', str(form_token_key)):
                _issue(issues, '$.card_form.token_key', '취급 토큰 키 형식이 올바르지 않습니다.')
            character_key = card_form.get('character_key')
            if character_key is not None and not re.fullmatch(r'[a-z0-9_]+', str(character_key)):
                _issue(issues, '$.card_form.character_key', '취급 캐릭터 키 형식이 올바르지 않습니다.')
    trait_negation = definition.get('trait_negation')
    if trait_negation is not None:
        if not isinstance(trait_negation, dict):
            _issue(issues, '$.trait_negation', '특성 무효 규칙은 객체여야 합니다.')
        else:
            if trait_negation.get('players') != 'both':
                _issue(issues, '$.trait_negation.players', '현재 특성 무효 대상은 both만 지원합니다.')
            active_zones = trait_negation.get('active_zones')
            if (
                not isinstance(active_zones, list) or not active_zones
                or any(zone not in ALL_ZONES for zone in active_zones)
            ):
                _issue(issues, '$.trait_negation.active_zones', '특성 무효 활성 존 배열이 필요합니다.')
    trait_state_keys = definition.get('trait_state_keys')
    if trait_state_keys is not None and (
        not isinstance(trait_state_keys, list) or not trait_state_keys
        or any(not re.fullmatch(r'[a-z0-9_]+', str(key or '')) for key in trait_state_keys)
        or len({str(key) for key in trait_state_keys}) != len(trait_state_keys)
    ):
        _issue(issues, '$.trait_state_keys', '특성 상태 키는 중복 없는 영문 소문자 키 배열이어야 합니다.')
    preserved_trait_states = definition.get('trait_state_preserve_on_negation')
    if preserved_trait_states is not None and (
        not isinstance(preserved_trait_states, list)
        or any(not re.fullmatch(r'[a-z0-9_]+', str(key or '')) for key in preserved_trait_states)
        or len({str(key) for key in preserved_trait_states}) != len(preserved_trait_states)
        or any(key not in (trait_state_keys or []) for key in preserved_trait_states)
    ):
        _issue(
            issues, '$.trait_state_preserve_on_negation',
            '특성 무효 중 유지할 상태는 특성 상태 키의 중복 없는 부분 배열이어야 합니다.',
        )
    state_grants = definition.get('state_grants', [])
    if not isinstance(state_grants, list):
        _issue(issues, '$.state_grants', '지속 상태 부여 규칙은 배열이어야 합니다.')
    else:
        for index, grant in enumerate(state_grants):
            path = f'$.state_grants[{index}]'
            if not isinstance(grant, dict):
                _issue(issues, path, '지속 상태 부여 규칙은 객체여야 합니다.')
                continue
            states = grant.get('states')
            if not isinstance(states, list) or not states or any(
                not re.fullmatch(r'[a-z0-9_]+', str(state or '')) for state in states
            ):
                _issue(issues, f'{path}.states', '상태 키가 하나 이상 필요합니다.')
            zones = grant.get('active_zones')
            if not isinstance(zones, list) or not zones or any(
                zone not in ALL_ZONES for zone in zones
            ):
                _issue(issues, f'{path}.active_zones', '활성 존 배열이 올바르지 않습니다.')
            if grant.get('player', 'controller') not in {'controller', 'opponent', 'both'}:
                _issue(issues, f'{path}.player', '상태 부여 대상이 올바르지 않습니다.')
            if grant.get('condition') is not None:
                _validate_condition(
                    grant.get('condition'), f'{path}.condition', issues,
                )
            if 'numbered_effect' in grant and not isinstance(
                grant.get('numbered_effect'), bool,
            ):
                _issue(
                    issues, f'{path}.numbered_effect',
                    '지속 상태 부여의 번호 효과 여부는 불리언이어야 합니다.',
                )
    effect_damage_limit = definition.get('effect_damage_limit')
    if effect_damage_limit is not None:
        if not isinstance(effect_damage_limit, dict):
            _issue(issues, '$.effect_damage_limit', '효과 데미지 상한은 객체여야 합니다.')
        else:
            maximum = effect_damage_limit.get('opponent')
            if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                _issue(issues, '$.effect_damage_limit.opponent', '상대 데미지 횟수는 1 이상의 정수여야 합니다.')
            if effect_damage_limit.get('scope', 'game') not in {'game', 'turn'}:
                _issue(issues, '$.effect_damage_limit.scope', '효과 데미지 상한 범위가 올바르지 않습니다.')
    play_costs = definition.get('play_costs', [])
    if not isinstance(play_costs, list):
        _issue(issues, '$.play_costs', '카드 사용 비용은 배열이어야 합니다.')
    else:
        for index, cost in enumerate(play_costs):
            path = f'$.play_costs[{index}]'
            if not isinstance(cost, dict):
                _issue(issues, path, '카드 사용 비용은 객체여야 합니다.')
                continue
            operation = cost.get('operation')
            if operation not in {'discard', 'delete_token', 'move_card'}:
                _issue(issues, f'{path}.operation', '지원하지 않는 카드 사용 비용입니다.')
            if operation == 'move_card':
                if cost.get('to_zone') not in ALL_ZONES:
                    _issue(
                        issues, f'{path}.to_zone',
                        '카드 이동 사용 비용에는 유효한 목적 존이 필요합니다.',
                    )
            elif cost.get('to_zone') is not None:
                _issue(
                    issues, f'{path}.to_zone',
                    '목적 존은 카드 이동 사용 비용에만 지정할 수 있습니다.',
                )
            if 'numbered_effect' in cost and not isinstance(
                cost.get('numbered_effect'), bool,
            ):
                _issue(
                    issues, f'{path}.numbered_effect',
                    '카드 사용 비용의 번호 효과 여부는 불리언이어야 합니다.',
                )
            _validate_selector(cost.get('selector'), f'{path}.selector', issues)
            use_contexts = cost.get('use_contexts')
            if use_contexts is not None and (
                not isinstance(use_contexts, list)
                or not use_contexts
                or any(value not in {'ready', 'combo', 'catch'} for value in use_contexts)
            ):
                _issue(issues, f'{path}.use_contexts', '사용 비용의 적용 시점이 올바르지 않습니다.')
            source_zones = cost.get('source_zones')
            if source_zones is not None and (
                not isinstance(source_zones, list)
                or not source_zones
                or any(value not in ALL_ZONES for value in source_zones)
            ):
                _issue(issues, f'{path}.source_zones', '사용 비용의 원본 영역이 올바르지 않습니다.')
            if cost.get('payment_timing', 'before_play') not in {
                'before_play', 'battle_reveal',
            }:
                _issue(
                    issues, f'{path}.payment_timing',
                    '사용 비용 지불 시점은 before_play 또는 battle_reveal이어야 합니다.',
                )
    attached_multiplier = definition.get('attached_effect_multiplier')
    if attached_multiplier is not None:
        if not isinstance(attached_multiplier, dict):
            _issue(issues, '$.attached_effect_multiplier', '세트 효과 수치 배율은 객체여야 합니다.')
        else:
            if attached_multiplier.get('event') not in TRIGGERS:
                _issue(issues, '$.attached_effect_multiplier.event', '세트 효과 배율 이벤트가 올바르지 않습니다.')
            value = attached_multiplier.get('value')
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                _issue(issues, '$.attached_effect_multiplier.value', '세트 효과 배율은 1 이상의 정수여야 합니다.')
            if 'numbered_effect' in attached_multiplier and not isinstance(
                attached_multiplier.get('numbered_effect'), bool,
            ):
                _issue(
                    issues, '$.attached_effect_multiplier.numbered_effect',
                    '세트 효과 배율의 번호 효과 여부는 불리언이어야 합니다.',
                )
            if attached_multiplier.get('where') is not None and not isinstance(
                attached_multiplier.get('where'), dict,
            ):
                _issue(
                    issues, '$.attached_effect_multiplier.where',
                    '세트 효과 배율의 카드 조건은 객체여야 합니다.',
                )
    hand_limit_bonus = definition.get('hand_limit_bonus')
    if hand_limit_bonus is not None and (
        not isinstance(hand_limit_bonus, int) or isinstance(hand_limit_bonus, bool)
        or hand_limit_bonus < 1
    ):
        _issue(issues, '$.hand_limit_bonus', '패 매수 상한 보너스는 1 이상의 정수여야 합니다.')
    discard_state_alias = definition.get('discard_state_alias')
    if discard_state_alias is not None:
        if not isinstance(discard_state_alias, dict):
            _issue(issues, '$.discard_state_alias', '버리기 상태 대체 정의는 객체여야 합니다.')
        else:
            if not str(discard_state_alias.get('source_character') or '').strip():
                _issue(issues, '$.discard_state_alias.source_character', '효과 출처 캐릭터가 필요합니다.')
            states = discard_state_alias.get('states')
            if (
                not isinstance(states, list) or not states
                or any(not str(state or '').strip() for state in states)
            ):
                _issue(issues, '$.discard_state_alias.states', '대체할 상태 키 배열이 필요합니다.')
    play_limit = definition.get('play_limit')
    if play_limit is not None:
        if not isinstance(play_limit, dict):
            _issue(issues, '$.play_limit', '카드 사용 제한은 객체여야 합니다.')
        else:
            if play_limit.get('scope', 'game') not in {'game', 'turn', 'phase', 'battle'}:
                _issue(issues, '$.play_limit.scope', '카드 사용 제한 범위가 올바르지 않습니다.')
            maximum = play_limit.get('max', 1)
            if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                _issue(issues, '$.play_limit.max', '카드 사용 횟수는 1 이상의 정수여야 합니다.')
            if not str(play_limit.get('key') or '').strip():
                _issue(issues, '$.play_limit.key', '카드 사용 제한 키가 필요합니다.')
    _validate_sources(definition.get('source_refs'), '$.source_refs', issues)
    _validate_condition(definition.get('play_condition'), '$.play_condition', issues)
    combo_rules = definition.get('combo_rules', [])
    if not isinstance(combo_rules, list):
        _issue(issues, '$.combo_rules', '카드 고유 콤보 규칙은 배열이어야 합니다.')
    else:
        for index, rule in enumerate(combo_rules):
            if not isinstance(rule, dict):
                _issue(issues, f'$.combo_rules[{index}]', '콤보 규칙은 객체여야 합니다.')
            else:
                _validate_effect({**rule, 'op': 'modify_combo'}, f'$.combo_rules[{index}]', issues)
    zone_limits = definition.get('zone_limits', [])
    if not isinstance(zone_limits, list):
        _issue(issues, '$.zone_limits', '존 배치 제한은 배열이어야 합니다.')
    else:
        for index, limit in enumerate(zone_limits):
            path = f'$.zone_limits[{index}]'
            if not isinstance(limit, dict):
                _issue(issues, path, '존 배치 제한은 객체여야 합니다.')
                continue
            if limit.get('zone') not in ALL_ZONES:
                _issue(issues, f'{path}.zone', '유효한 존이 필요합니다.')
            maximum = limit.get('max')
            if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                _issue(issues, f'{path}.max', '배치 한도는 1 이상의 정수여야 합니다.')
            if not isinstance(limit.get('where'), dict) or not limit.get('where'):
                _issue(issues, f'{path}.where', '제한할 카드 필터가 필요합니다.')
    defense_rules = definition.get('defense_rules', [])
    if not isinstance(defense_rules, list):
        _issue(issues, '$.defense_rules', '수비 판정 제한은 배열이어야 합니다.')
    else:
        for index, rule in enumerate(defense_rules):
            path = f'$.defense_rules[{index}]'
            if not isinstance(rule, dict):
                _issue(issues, path, '수비 판정 제한은 객체여야 합니다.')
                continue
            if rule.get('position') not in {None, '상단', '중단', '하단'}:
                _issue(issues, f'{path}.position', '위치 판정은 상단/중단/하단이어야 합니다.')
            if rule.get('judgment', 'dodge') not in {'dodge', 'clash'}:
                _issue(issues, f'{path}.judgment', '수비 판정은 dodge 또는 clash여야 합니다.')
            if 'grant' in rule and not isinstance(rule.get('grant'), bool):
                _issue(issues, f'{path}.grant', '수비 판정 부여 여부는 불리언이어야 합니다.')
            for field_name in ('min_speed', 'max_speed'):
                amount = rule.get(field_name)
                if amount is not None and (
                    not isinstance(amount, int) or isinstance(amount, bool) or amount < 1
                ):
                    _issue(issues, f'{path}.{field_name}', '속도 제한은 1 이상의 정수여야 합니다.')
            for field_name in ('min_damage', 'max_damage', 'min_hit'):
                amount = rule.get(field_name)
                if amount is not None and (
                    not isinstance(amount, int) or isinstance(amount, bool) or amount < 0
                ):
                    _issue(issues, f'{path}.{field_name}', '판정 제한 수치는 0 이상의 정수여야 합니다.')
            if rule.get('min_speed') and rule.get('max_speed') and rule['max_speed'] < rule['min_speed']:
                _issue(issues, path, '최대 속도는 최소 속도 이상이어야 합니다.')
            if rule.get('min_damage') is not None and rule.get('max_damage') is not None and rule['max_damage'] < rule['min_damage']:
                _issue(issues, path, '최대 데미지는 최소 데미지 이상이어야 합니다.')
            hit_values = rule.get('hit_values')
            if hit_values is not None and (
                not isinstance(hit_values, list)
                or not hit_values
                or any(not isinstance(value, str) or not value for value in hit_values)
            ):
                _issue(issues, f'{path}.hit_values', '허용 히트 판정은 비어 있지 않은 문자열 배열이어야 합니다.')
            if rule.get('where') is not None and not isinstance(rule.get('where'), dict):
                _issue(issues, f'{path}.where', '상대 카드 필터는 객체여야 합니다.')
            cost = rule.get('cost')
            if cost is not None:
                if not isinstance(cost, dict):
                    _issue(issues, f'{path}.cost', '수비 판정 비용은 객체여야 합니다.')
                else:
                    if cost.get('operation') != 'discard':
                        _issue(
                            issues, f'{path}.cost.operation',
                            '현재 수비 판정 비용은 버리기만 지원합니다.',
                        )
                    _validate_selector(
                        cost.get('selector'), f'{path}.cost.selector', issues,
                    )
                    if cost.get('prompt') is not None and not str(
                        cost.get('prompt') or ''
                    ).strip():
                        _issue(
                            issues, f'{path}.cost.prompt',
                            '수비 판정 비용 안내 문구가 올바르지 않습니다.',
                        )
                    if 'optional' in cost and not isinstance(
                        cost.get('optional'), bool,
                    ):
                        _issue(
                            issues, f'{path}.cost.optional',
                            '수비 판정 비용의 선택 여부는 불리언이어야 합니다.',
                        )
            if 'numbered_effect' in rule and not isinstance(
                rule.get('numbered_effect'), bool,
            ):
                _issue(
                    issues, f'{path}.numbered_effect',
                    '수비 판정 규칙의 번호 효과 여부는 불리언이어야 합니다.',
                )
            _validate_condition(rule.get('condition'), f'{path}.condition', issues)
    catch_rules = definition.get('catch_rules', [])
    if not isinstance(catch_rules, list):
        _issue(issues, '$.catch_rules', '카드 고유 캐치 규칙은 배열이어야 합니다.')
    else:
        for index, rule in enumerate(catch_rules):
            path = f'$.catch_rules[{index}]'
            if not isinstance(rule, dict):
                _issue(issues, path, '캐치 규칙은 객체여야 합니다.')
                continue
            fixed_speed = rule.get('fixed_speed')
            optional_fixed_speed = rule.get('optional_fixed_speed')
            allow_zones = rule.get('allow_zones', [])
            break_after_use = rule.get('break_after_use', False)
            if (
                fixed_speed is None and optional_fixed_speed is None
                and not allow_zones and not break_after_use
            ):
                _issue(
                    issues, path,
                    '캐치 규칙에는 고정 속도, 추가 허용 존 또는 사용 후 브레이크가 필요합니다.',
                )
            elif fixed_speed is not None and (
                not isinstance(fixed_speed, int) or isinstance(fixed_speed, bool) or fixed_speed < 1
            ):
                _issue(issues, f'{path}.fixed_speed', '캐치 고정 속도는 1 이상의 정수여야 합니다.')
            if optional_fixed_speed is not None and (
                not isinstance(optional_fixed_speed, int)
                or isinstance(optional_fixed_speed, bool)
                or optional_fixed_speed < 1
            ):
                _issue(
                    issues, f'{path}.optional_fixed_speed',
                    '선택 캐치 고정 속도는 1 이상의 정수여야 합니다.',
                )
            counter_cost = rule.get('counter_cost')
            if counter_cost is not None:
                if not isinstance(counter_cost, dict):
                    _issue(issues, f'{path}.counter_cost', '카운터 비용은 객체여야 합니다.')
                else:
                    if not str(counter_cost.get('counter') or '').strip():
                        _issue(issues, f'{path}.counter_cost.counter', '카운터 키가 필요합니다.')
                    amount = counter_cost.get('amount')
                    if (
                        not isinstance(amount, int) or isinstance(amount, bool)
                        or amount < 1
                    ):
                        _issue(issues, f'{path}.counter_cost.amount', '카운터 비용은 1 이상이어야 합니다.')
            if 'numbered_effect' in rule and not isinstance(
                rule.get('numbered_effect'), bool,
            ):
                _issue(issues, f'{path}.numbered_effect', '번호 효과 여부는 불리언이어야 합니다.')
            if not isinstance(allow_zones, list) or any(zone not in ALL_ZONES for zone in allow_zones):
                _issue(issues, f'{path}.allow_zones', '캐치 추가 허용 존 목록이 올바르지 않습니다.')
            if not isinstance(break_after_use, bool):
                _issue(issues, f'{path}.break_after_use', '사용 후 브레이크 여부는 불리언이어야 합니다.')
            _validate_condition(rule.get('condition'), f'{path}.condition', issues)
    break_rules = definition.get('break_rules')
    if break_rules is not None:
        if not isinstance(break_rules, dict):
            _issue(issues, '$.break_rules', '브레이크 제한은 객체여야 합니다.')
        else:
            forbidden_zones = break_rules.get('forbidden_zones', [])
            if not isinstance(forbidden_zones, list) or any(zone not in ALL_ZONES for zone in forbidden_zones):
                _issue(issues, '$.break_rules.forbidden_zones', '브레이크 금지 존 목록이 올바르지 않습니다.')
            preventions = break_rules.get('preventions', [])
            if not isinstance(preventions, list):
                _issue(issues, '$.break_rules.preventions', '브레이크 금지 규칙은 배열이어야 합니다.')
            else:
                for index, prevention in enumerate(preventions):
                    path = f'$.break_rules.preventions[{index}]'
                    if not isinstance(prevention, dict):
                        _issue(issues, path, '브레이크 금지 규칙은 객체여야 합니다.')
                        continue
                    if prevention.get('scope') not in {'all', 'owner_direct', 'opponent_effect'}:
                        _issue(issues, f'{path}.scope', '지원하지 않는 브레이크 금지 범위입니다.')
                    if 'numbered_effect' in prevention and not isinstance(
                        prevention.get('numbered_effect'), bool,
                    ):
                        _issue(
                            issues, f'{path}.numbered_effect',
                            '번호 효과 여부는 불리언이어야 합니다.',
                        )
                    _validate_condition(prevention.get('condition'), f'{path}.condition', issues)
    effect_immunity = definition.get('effect_immunity')
    if effect_immunity is not None:
        if not isinstance(effect_immunity, dict):
            _issue(issues, '$.effect_immunity', '효과 면역 규칙은 객체여야 합니다.')
        else:
            if effect_immunity.get('scope') not in {'opponent', 'other_cards', 'source_codes'}:
                _issue(
                    issues, '$.effect_immunity.scope',
                    '효과 면역 범위가 올바르지 않습니다.',
                )
            if 'numbered_effect' in effect_immunity and not isinstance(
                effect_immunity.get('numbered_effect'), bool,
            ):
                _issue(
                    issues, '$.effect_immunity.numbered_effect',
                    '번호 효과 면역 여부는 불리언이어야 합니다.',
                )
            active_zones = effect_immunity.get('active_zones', [])
            if not isinstance(active_zones, list) or any(zone not in ALL_ZONES for zone in active_zones):
                _issue(
                    issues, '$.effect_immunity.active_zones',
                    '효과 면역 활성 존 목록이 올바르지 않습니다.',
                )
            operations = effect_immunity.get('operations', [])
            if not isinstance(operations, list) or any(
                item not in {'modify_stat', 'move_card'} for item in operations
            ):
                _issue(
                    issues, '$.effect_immunity.operations',
                    '면역 효과 연산 목록이 올바르지 않습니다.',
                )
            to_zones = effect_immunity.get('to_zones', [])
            if not isinstance(to_zones, list) or any(
                zone not in ALL_ZONES for zone in to_zones
            ):
                _issue(
                    issues, '$.effect_immunity.to_zones',
                    '효과 면역 이동 목적지 목록이 올바르지 않습니다.',
                )
            if to_zones and 'move_card' not in operations:
                _issue(
                    issues, '$.effect_immunity.to_zones',
                    '이동 목적지 면역에는 move_card 연산이 필요합니다.',
                )
            stats = effect_immunity.get('stats', [])
            if not isinstance(stats, list) or any(
                item not in {'frame', 'damage'} for item in stats
            ):
                _issue(
                    issues, '$.effect_immunity.stats',
                    '면역 수치 목록이 올바르지 않습니다.',
                )
            directions = effect_immunity.get('directions', [])
            if not isinstance(directions, list) or any(
                item not in {'increase', 'decrease'} for item in directions
            ):
                _issue(
                    issues, '$.effect_immunity.directions',
                    '면역 수치 방향 목록이 올바르지 않습니다.',
                )
            if (stats or directions) and 'modify_stat' not in operations:
                _issue(
                    issues, '$.effect_immunity.stats',
                    '수치 방향 면역에는 modify_stat 연산이 필요합니다.',
                )
            if effect_immunity.get('scope') == 'source_codes':
                source_codes = effect_immunity.get('source_codes')
                if not isinstance(source_codes, list) or not source_codes or any(
                    not isinstance(code, str) or not code.strip() for code in source_codes
                ):
                    _issue(issues, '$.effect_immunity.source_codes', '면역할 효과 원본 카드 코드가 필요합니다.')
    abilities = definition.get('abilities')
    if not isinstance(abilities, list):
        _issue(issues, '$.abilities', '능력 목록이 필요합니다.')
        return issues
    if require_coverage and definition.get('reviewed') is not True:
        _issue(issues, '$.reviewed', '게시 전에 카드 효과 정의 검토를 완료해야 합니다.', 'unreviewed')
    if require_coverage and definition.get('draft') is True:
        _issue(issues, '$.draft', '자동 생성 초안을 실제 효과 명령으로 교체해야 합니다.', 'draft_definition')
    if definition.get('no_effect') and abilities:
        _issue(issues, '$.no_effect', '효과 없음 정의에는 능력 노드를 함께 둘 수 없습니다.')
    if require_coverage and card_has_text and definition.get('no_effect') and not _has_sources(definition.get('source_refs')):
        _issue(issues, '$.source_refs', '텍스트를 효과 없음으로 재정한 출처가 필요합니다.', 'missing_source')
    if require_coverage and card_has_text and not abilities and not definition.get('no_effect'):
        _issue(issues, '$.abilities', '효과 텍스트가 있는 카드는 최소 한 개의 능력 정의가 필요합니다.', 'missing_coverage')
    if require_coverage:
        _validate_review_evidence(definition, abilities, issues)

    known_handlers = set(registered_handler_names() if handler_names is None else handler_names)
    seen_ids = set()
    for index, ability in enumerate(abilities):
        path = f'$.abilities[{index}]'
        if not isinstance(ability, dict):
            _issue(issues, path, '능력은 객체여야 합니다.')
            continue
        if require_coverage and ability.get('draft') is True:
            _issue(issues, f'{path}.draft', '초안 능력은 게시할 수 없습니다.', 'draft_ability')
        ability_id = str(ability.get('id') or '').strip()
        if not ability_id:
            _issue(issues, f'{path}.id', '안정적인 능력 ID가 필요합니다.')
        elif ability_id in seen_ids:
            _issue(issues, f'{path}.id', f'능력 ID가 중복되었습니다: {ability_id}')
        seen_ids.add(ability_id)
        if ability.get('kind') not in ABILITY_KINDS:
            _issue(issues, f'{path}.kind', f'능력 종류는 {sorted(ABILITY_KINDS)} 중 하나여야 합니다.')
        if ability.get('mode') not in ABILITY_MODES:
            _issue(issues, f'{path}.mode', f'처리 방식은 {sorted(ABILITY_MODES)} 중 하나여야 합니다.')
        visibility = ability.get('visibility', 'public')
        if visibility not in VISIBILITIES:
            _issue(issues, f'{path}.visibility', f'공개 범위는 {sorted(VISIBILITIES)} 중 하나여야 합니다.')
        trigger = ability.get('trigger')
        if ability.get('mode') != 'continuous':
            if not isinstance(trigger, dict) or trigger.get('event') not in TRIGGERS:
                _issue(issues, f'{path}.trigger.event', '지원되는 트리거 이벤트가 필요합니다.')
            elif trigger.get('events') is not None:
                events = trigger.get('events')
                if (
                    not isinstance(events, list) or not events
                    or any(event not in TRIGGERS for event in events)
                    or len(set(events)) != len(events)
                ):
                    _issue(issues, f'{path}.trigger.events', '중복 없는 유효한 트리거 이벤트 배열이 필요합니다.')
                elif trigger.get('event') not in events:
                    _issue(issues, f'{path}.trigger.events', '기본 트리거 event가 events 배열에 포함되어야 합니다.')
        timing = ability.get('timing')
        if timing is not None and timing not in TIMING_ORDER:
            _issue(issues, f'{path}.timing', f'지원하지 않는 타이밍입니다: {timing!r}')
        _validate_sources(ability.get('source_refs'), f'{path}.source_refs', issues)
        if require_coverage and not _has_sources(ability.get('source_refs')) and not _has_sources(definition.get('source_refs')):
            _issue(issues, f'{path}.source_refs', '게시되는 능력에는 룰북 페이지 또는 Q&A 출처가 필요합니다.', 'missing_source')
        _validate_condition(ability.get('condition'), f'{path}.condition', issues)
        if ability.get('availability_selector') is not None:
            _validate_selector(
                ability.get('availability_selector'),
                f'{path}.availability_selector', issues,
            )
        if 'recheck_condition' in ability and not isinstance(ability.get('recheck_condition'), bool):
            _issue(issues, f'{path}.recheck_condition', '해결 시 조건 재검사 여부는 불리언이어야 합니다.')
        if 'active_when_attached' in ability and not isinstance(
            ability.get('active_when_attached'), bool,
        ):
            _issue(
                issues, f'{path}.active_when_attached',
                '세트 상태 활성 여부는 불리언이어야 합니다.',
            )
        if 'allow_non_source_trigger' in ability and not isinstance(
            ability.get('allow_non_source_trigger'), bool,
        ):
            _issue(
                issues, f'{path}.allow_non_source_trigger',
                '다른 기술이 만든 타이밍에 반응하는지 여부는 불리언이어야 합니다.',
            )
        if 'requires_combo_use' in ability and not isinstance(
            ability.get('requires_combo_use'), bool,
        ):
            _issue(
                issues, f'{path}.requires_combo_use',
                '콤보에서 직접 사용된 카드만 유발하는지 여부는 불리언이어야 합니다.',
            )
        dedupe_trigger_key = ability.get('dedupe_trigger_key')
        if dedupe_trigger_key is not None and not re.fullmatch(
            r'[a-z0-9_.:-]+', str(dedupe_trigger_key or ''),
        ):
            _issue(issues, f'{path}.dedupe_trigger_key', '중복 유발 키 형식이 올바르지 않습니다.')
        active_zones = ability.get('active_zones')
        if active_zones is not None and (
            not isinstance(active_zones, list) or any(zone not in ALL_ZONES for zone in active_zones)
        ):
            _issue(issues, f'{path}.active_zones', '능력 활성 존 목록이 올바르지 않습니다.')
        limit = ability.get('limit')
        if limit is not None:
            if not isinstance(limit, dict):
                _issue(issues, f'{path}.limit', '사용 제한은 객체여야 합니다.')
            else:
                if limit.get('scope', 'game') not in {'game', 'turn', 'phase', 'battle'}:
                    _issue(issues, f'{path}.limit.scope', '사용 제한 범위가 올바르지 않습니다.')
                maximum = limit.get('max', 1)
                if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
                    _issue(issues, f'{path}.limit.max', '사용 횟수는 1 이상의 정수여야 합니다.')
                if 'per_event_card' in limit and not isinstance(limit.get('per_event_card'), bool):
                    _issue(issues, f'{path}.limit.per_event_card', '이벤트 카드별 제한 여부는 불리언이어야 합니다.')
                if (
                    'per_effect_resolution' in limit
                    and not isinstance(limit.get('per_effect_resolution'), bool)
                ):
                    _issue(
                        issues, f'{path}.limit.per_effect_resolution',
                        '효과 해결 단위 제한 여부는 불리언이어야 합니다.',
                    )
        costs = ability.get('cost') or []
        if not isinstance(costs, list):
            _issue(issues, f'{path}.cost', '비용은 명령 배열이어야 합니다.')
        else:
            for cost_index, cost in enumerate(costs):
                _validate_effect(cost, f'{path}.cost[{cost_index}]', issues)
        targets = ability.get('targets') or []
        if not isinstance(targets, list):
            _issue(issues, f'{path}.targets', '능력 대상은 선택기 배열이어야 합니다.')
        else:
            for selector_index, selector in enumerate(targets):
                _validate_selector(selector, f'{path}.targets[{selector_index}]', issues)
        handler = str(ability.get('handler') or '').strip()
        effects = ability.get('effects')
        if handler:
            if handler not in known_handlers:
                _issue(issues, f'{path}.handler', f'등록되지 않은 핸들러입니다: {handler}', 'unknown_handler')
        elif not isinstance(effects, list) or not effects:
            _issue(issues, f'{path}.effects', '실행 명령 또는 등록된 핸들러가 필요합니다.')
        else:
            for effect_index, effect in enumerate(effects):
                _validate_effect(effect, f'{path}.effects[{effect_index}]', issues)
    return issues
