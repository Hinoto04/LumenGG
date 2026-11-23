"""Per-deck AI profiles written in TOML (docs/AI_DECK_PROFILE.md).

A profile only adjusts the linear policy in ``ai.py``. It reads the same
role-filtered observation as the policy, so it never sees hidden cards.

Normalized shape (pinned into the session as ``document['ai_deck']``)::

    {
        'style': 'balanced',
        'weights': {'card_attack': 2.0},
        'prefer': {'UNC-AT-001': 2.5},
        'situations': [{'name': ..., 'when': {...}, 'prefer': {...}, 'weights': {...}}],
        'combos': [{'name': ..., 'cards': [...], 'bonus': 3.0, 'when': {...}}],
        'counter': {'enabled': True, 'bonus': 2.0, 'scope': 'hand', 'guard_bonus': 6.0, 'guard_fp': 3.0},
        'safety': {'avoid_certain_loss': True},
        'hand': {'enabled': True, 'bonus': 8.0, 'keep': 3, 'swap_margin': 0.1},
    }
"""

import tomllib
from pathlib import Path

TEMPLATE_PATH = Path(__file__).with_name('ai_profile_template.toml')


def default_ai_profile_text():
    """Blank, fully commented profile form for a new AI deck."""
    return TEMPLATE_PATH.read_text(encoding='utf-8')

STYLE_BALANCED = 'balanced'
STYLE_AGGRESSIVE = 'aggressive'
STYLE_DEFENSIVE = 'defensive'
STYLE_SPEED = 'speed'
STYLE_CHOICES = [
    (STYLE_BALANCED, '균형'),
    (STYLE_AGGRESSIVE, '공격적'),
    (STYLE_DEFENSIVE, '수비적'),
    (STYLE_SPEED, '속도 중시'),
]
STYLE_PRESETS = {
    STYLE_BALANCED: {},
    STYLE_AGGRESSIVE: {
        'card_attack': 2.5, 'card_defense': -0.5,
        'card_damage': 0.45, 'hp_advantage_attack': 0.8,
    },
    STYLE_DEFENSIVE: {
        'card_attack': 0.6, 'card_defense': 1.5, 'low_hp_defense': 2.5,
    },
    STYLE_SPEED: {'card_speed': 1.6, 'card_damage': 0.1},
}
# Human-readable meaning of every weight a profile may change. Safety/meta
# actions (concede, rewind, pause) are never adjustable by a deck.
WEIGHT_DESCRIPTIONS = {
    'card_damage': '카드 데미지 100당 점수',
    'card_speed': '속도 1 빠를수록(12 - 속도) 점수',
    'card_attack': '공격 카드면 더하는 점수',
    'card_defense': '수비 카드면 더하는 점수',
    'zero_damage_attack': '데미지 0 공격 카드면 더하는 점수(보통 음수)',
    'low_hp_defense': '내 체력 1500 이하에서 수비 카드면 더하는 점수',
    'hp_advantage_attack': '공격 카드일 때 (내 체력 - 상대 체력)/5000 에 곱하는 점수',
    'battle_preview': '레디할 카드가 상대가 낼 법한 카드(공개·기억한 손패)와 붙었을 때의 기대 결과(약 -2~+2)에 곱하는 점수. 기본 6',
    'preview_trust': '상대 손패를 알수록 속도·데미지·공수 점수를 줄이는 정도(0~1). 1이면 다 알 때 예측만 봄. 기본 0.7',
    'ready_card': '레디 행동 자체의 기본 점수',
    'select_get_card': '리스트 카드 획득 행동의 기본 점수',
    'select_ultimate': '얼티밋 획득 행동의 기본 점수',
    'play_combo_card': '콤보 카드 1장 사용의 기본 점수',
    'play_combo_pair': '콤보 첫 2장 사용의 기본 점수',
    'select_combo_first': '콤보 첫 장 고르기의 기본 점수',
    'select_combo_followup': '콤보 두 번째 장 고르기의 기본 점수',
    'end_combo': '콤보를 끝내는 행동의 점수(높을수록 일찍 끝냄)',
    'play_catch_card': '캐치 카드 사용의 기본 점수',
    'decline_catch': '캐치를 하지 않는 행동의 점수',
    'pass_phase': '페이즈를 넘기는 행동의 점수',
    'submit_decision': '효과 선택을 확정하는 행동의 점수',
}
STYLE_WEIGHT_KEYS = tuple(WEIGHT_DESCRIPTIONS)
WEIGHT_LIMIT = 20.0
PREFERENCE_LIMIT = 10.0
BONUS_LIMIT = 10.0
DEFAULT_ROUTE_BONUS = 3.0
DEFAULT_COUNTER_BONUS = 2.0
# 상대가 이득 프레임일 때를 대비한 가드 획득 가산. 공격 카드의 기본 점수(card_attack·card_speed)를
# 넘어야 획득되므로 일반 대처 가산보다 크다.
DEFAULT_GUARD_BONUS = 6.0
DEFAULT_GUARD_FP = 3.0
GUARD_FP_LIMIT = 20.0
# 겟 페이즈: 패 가치(ai_hand)가 1 오를 때의 가산, 상대 카드에 강한 카드를 몇 장 두텁게 쥘지,
# 패가 가득 찼을 때 교체할 최소 이득(이보다 작으면 패스).
DEFAULT_HAND_BONUS = 8.0
DEFAULT_HAND_KEEP = 3
DEFAULT_SWAP_MARGIN = 0.1
HAND_KEEP_LIMIT = 10
MAX_ITEMS = 30
MAX_ROUTE_LENGTH = 10
COUNTER_SCOPES = ('hand', 'hand_and_list')

ACTION_KINDS = {
    'ready': {'ready_card'},
    'get': {'select_get_card', 'select_ultimate'},
    'combo': {
        'play_combo_card', 'play_combo_pair', 'play_combo_sequence',
        'select_combo_first', 'select_combo_followup',
    },
    'catch': {'play_catch_card'},
}
COMBO_ACTION_TYPES = ACTION_KINDS['combo']
GET_ACTION_TYPES = ACTION_KINDS['get']
# A route starts with the card that wins the battle, so readying that card is
# worth part of the route bonus; getting any route card a smaller part.
READY_STARTER_FACTOR = 0.5
GET_MEMBER_FACTOR = 0.3
COMPLETION_FACTOR = 0.5

# ``when`` keys: name -> (kind, description)
CONDITION_KEYS = {
    'action': ('kinds', '행동 종류 목록: ready(레디) get(획득) combo(콤보) catch(캐치)'),
    'turn_min': ('number', '이 턴 이상'),
    'turn_max': ('number', '이 턴 이하'),
    'my_hp_min': ('number', '내 체력 이상'),
    'my_hp_max': ('number', '내 체력 이하'),
    'rival_hp_min': ('number', '상대 체력 이상'),
    'rival_hp_max': ('number', '상대 체력 이하'),
    'hp_lead_min': ('number', '(내 체력 - 상대 체력) 이상. 음수면 지고 있을 때'),
    'hp_lead_max': ('number', '(내 체력 - 상대 체력) 이하'),
    'my_fp_min': ('number', '내 FP 이상'),
    'my_fp_max': ('number', '내 FP 이하'),
    'fp_lead_min': ('number', '(내 FP - 상대 FP) 이상. 예: 4면 +4FP 이상 유리'),
    'fp_lead_max': ('number', '(내 FP - 상대 FP) 이하. 예: -1이면 1FP 이상 불리'),
    'combo_min': ('number', '이번 콤보에서 이미 쓴 콤보 카드 수 이상'),
    'combo_max': ('number', '이번 콤보에서 이미 쓴 콤보 카드 수 이하'),
    'rival_shows': ('codes', '상대의 공개된 카드(배틀·손패·리스트) 중 하나라도 이 코드면'),
    'i_hold': ('codes', '내 손패에 이 코드 중 하나라도 있으면'),
    'hand_min': ('number', '내 손패 장수 이상'),
    'hand_max': ('number', '내 손패 장수 이하'),
    'hand_attack_min': ('number', '내 손패의 공격 기술 장수 이상'),
    'hand_attack_max': ('number', '내 손패의 공격 기술 장수 이하'),
    'hand_defense_min': ('number', '내 손패의 수비 기술 장수 이상'),
    'hand_defense_max': ('number', '내 손패의 수비 기술 장수 이하'),
    'my_lumen_min': ('number', '내 루멘 존 카드 장수 이상'),
    'my_lumen_max': ('number', '내 루멘 존 카드 장수 이하'),
    'speed_lead_min': ('number', '속도 우위(상대의 가장 빠른 공개 공격 속도 - 내 손패의 가장 빠른 공격 속도, FP 반영) 이상. '
                       '예: 3이면 내가 3 이상 빠름. 상대 공격을 모르면 99'),
    'speed_lead_max': ('number', '속도 우위 이하. 예: 0이면 내가 빠르지 않음'),
    'my_counter_min': ('counters', '내 패시브 카운터 이상. 예: { foresight = 2 }'),
    'my_counter_max': ('counters', '내 패시브 카운터 이하. 예: { howling = 4 }'),
}

# [[effect]] rules: activation and choices of optional effects and passives.
EFFECT_RULE_KEYS = {
    'name': '규칙 이름',
    'ability': '능력 ID(또는 목록). 관리자 화면 "선택이 있는 패시브" 참고표',
    'card': '카드 코드(또는 목록). 그 카드의 모든 능력',
    'decision': '결정 종류(또는 목록): optional_effect effect_branch effect_choice effect_amount ability_target 등',
    'when': '상황 조건(조건표와 같음)',
    'use': 'true = 발동한다 / false = 발동하지 않는다(고르지 않아도 되는 선택은 비워 둔다)',
    'choose': '효과 분기 ID 우선순위 목록. 고를 수 있는 것 중 앞쪽부터',
    'pick': '가져오거나 고를 카드 코드 우선순위 목록',
    'avoid': '되도록 고르지 않을 카드 코드 목록',
    'count': '고를 장수: "max"(최대) "min"(최소) 또는 숫자',
    'amount': '수치 선택: "max" "min" 또는 숫자',
}
DECISION_KINDS = (
    'optional_effect', 'effect_branch', 'effect_choice', 'effect_amount', 'ability_target',
    'effect_order', 'play_cost', 'defense_cost', 'combo_speed_cost', 'hand_limit_discard',
    'break_replenish', 'forced_get_designation', 'no_response_card', 'no_response_result',
    'grab_negation', 'hand_guess_card', 'hand_guess_parity', 'hand_guess_repeat',
)


class ProfileError(ValueError):
    pass


def parse_profile_text(text, *, allowed_codes=None):
    """Parse TOML profile text and normalize it; raise ProfileError (Korean)."""
    try:
        raw = tomllib.loads(text or '')
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f'TOML 문법 오류: {exc}') from None
    return normalize_profile(raw, allowed_codes=allowed_codes)


# 수치표(ai_outcomes) 덮어쓰기: 판정 결과 이름과 자원별 허용 범위.
OUTCOME_RESULTS = (
    'hit', 'counter', 'clash', 'countered', 'dodge', 'opponent_dodge',
    'guard', 'guarded', 'failed_defense', 'none',
)
OUTCOME_LIMITS = {'damage': 20000, 'fp': 50, 'counter': 50, 'card': 20}
# [resources]: 자원 1단위를 HP 몇에 해당한다고 볼지. 데미지는 1 = HP 1로 고정.
RESOURCE_HP_DEFAULTS = {'fp': 400 / 6.0, 'counter': 200.0, 'card': 300.0}
RESOURCE_HP_LIMIT = 5000


def _bounded(value, limit, label, errors):
    if isinstance(value, bool):
        errors.append(f'{label}은(는) 숫자여야 합니다.')
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f'{label}은(는) 숫자여야 합니다.')
        return None
    if number != number or abs(number) > limit:
        errors.append(f'{label}은(는) -{limit:g}~{limit:g} 사이여야 합니다.')
        return None
    return number


def normalize_profile(raw, *, allowed_codes=None):
    """Validate a profile dict and return a clean copy; raise ProfileError.

    ``allowed_codes``: card codes in the deck. When given, card codes may only
    name those cards (``rival_shows`` may name any card).
    """
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ProfileError('AI 덱 설정은 표(table)여야 합니다.')
    errors = []
    known = {
        'style', 'weights', 'prefer', 'situation', 'combo', 'counter', 'safety', 'effect', 'effects',
        'outcome', 'resources', 'hand',
    }
    for key in raw:
        if key not in known:
            errors.append(f'알 수 없는 항목입니다: {key}')

    style = str(raw.get('style') or STYLE_BALANCED)
    if style not in STYLE_PRESETS:
        errors.append(f'알 수 없는 성향입니다: {style} (balanced, aggressive, defensive, speed)')
        style = STYLE_BALANCED

    def code(value, where, *, own=True):
        value = str(value or '').strip()
        if not value:
            errors.append(f'{where}: 빈 카드 코드가 있습니다.')
            return None
        if own and allowed_codes is not None and value not in allowed_codes:
            errors.append(f'{where}: 덱에 없는 카드 코드입니다: {value}')
            return None
        return value

    def weights(value, where):
        if value in (None, {}):
            return {}
        if not isinstance(value, dict):
            errors.append(f'{where}: weights는 키 = 숫자 형식이어야 합니다.')
            return {}
        result = {}
        for key, number in value.items():
            if key not in STYLE_WEIGHT_KEYS:
                errors.append(f'{where}: 조절할 수 없는 가중치입니다: {key}')
                continue
            number = _bounded(number, WEIGHT_LIMIT, f'{where} 가중치 {key}', errors)
            if number is not None:
                result[key] = number
        return result

    def prefer(value, where):
        if value in (None, {}):
            return {}
        if not isinstance(value, dict):
            errors.append(f'{where}: prefer는 "카드 코드" = 숫자 형식이어야 합니다.')
            return {}
        result = {}
        for key, number in value.items():
            key = code(key, where)
            number = _bounded(number, PREFERENCE_LIMIT, f'{where} 선호 {key}', errors)
            if key and number is not None:
                result[key] = number
        return result

    def when(value, where):
        if value in (None, {}):
            return {}
        if not isinstance(value, dict):
            errors.append(f'{where}: when은 표(table)여야 합니다.')
            return {}
        result = {}
        for key, item in value.items():
            spec = CONDITION_KEYS.get(key)
            if not spec:
                errors.append(f'{where}: 알 수 없는 조건입니다: {key}')
                continue
            kind = spec[0]
            if kind == 'number':
                number = _bounded(item, 100000, f'{where} 조건 {key}', errors)
                if number is not None:
                    result[key] = number
            elif kind == 'counters':
                if not isinstance(item, dict) or not item:
                    errors.append(f'{where}: {key}는 {{ 카운터 = 숫자 }} 형식이어야 합니다.')
                    continue
                counters = {}
                for name, number in item.items():
                    number = _bounded(number, 1000, f'{where} 조건 {key}.{name}', errors)
                    if number is not None:
                        counters[str(name)] = number
                result[key] = counters
            elif kind == 'kinds':
                items = item if isinstance(item, list) else [item]
                bad = [str(entry) for entry in items if entry not in ACTION_KINDS]
                if bad:
                    errors.append(f'{where}: 알 수 없는 행동 종류입니다: {", ".join(bad)}')
                else:
                    result[key] = list(items)
            else:
                items = item if isinstance(item, list) else [item]
                codes = [code(entry, where, own=key == 'i_hold') for entry in items]
                if None not in codes:
                    result[key] = codes
        return result

    def table_list(name):
        value = raw.get(name) or []
        if isinstance(value, dict):
            value = [value]
        if not isinstance(value, list):
            errors.append(f'{name}은(는) [[{name}]] 목록이어야 합니다.')
            return []
        if len(value) > MAX_ITEMS:
            errors.append(f'{name}은(는) 최대 {MAX_ITEMS}개입니다.')
        return value[:MAX_ITEMS]

    situations = []
    for index, item in enumerate(table_list('situation'), start=1):
        where = f'situation {index}'
        if not isinstance(item, dict):
            errors.append(f'{where}: 표(table)여야 합니다.')
            continue
        where = f'situation "{item.get("name") or index}"'
        for key in item:
            if key not in {'name', 'when', 'prefer', 'weights'}:
                errors.append(f'{where}: 알 수 없는 항목입니다: {key}')
        entry = {
            'name': str(item.get('name') or f'상황 {index}')[:60],
            'when': when(item.get('when'), where),
            'prefer': prefer(item.get('prefer'), where),
            'weights': weights(item.get('weights'), where),
        }
        if not entry['prefer'] and not entry['weights']:
            errors.append(f'{where}: prefer나 weights 중 하나는 있어야 합니다.')
        situations.append(entry)

    combos = []
    for index, item in enumerate(table_list('combo'), start=1):
        where = f'combo {index}'
        if not isinstance(item, dict):
            errors.append(f'{where}: 표(table)여야 합니다.')
            continue
        where = f'combo "{item.get("name") or index}"'
        for key in item:
            if key not in {'name', 'cards', 'bonus', 'when'}:
                errors.append(f'{where}: 알 수 없는 항목입니다: {key}')
        cards = item.get('cards')
        if not isinstance(cards, list) or not 2 <= len(cards) <= MAX_ROUTE_LENGTH:
            errors.append(f'{where}: cards는 2~{MAX_ROUTE_LENGTH}장이어야 합니다.')
            continue
        codes = [code(entry, where) for entry in cards]
        bonus = _bounded(item.get('bonus', DEFAULT_ROUTE_BONUS), BONUS_LIMIT, f'{where} bonus', errors)
        if None in codes or bonus is None:
            continue
        combos.append({
            'name': str(item.get('name') or f'콤보 {index}')[:60],
            'cards': codes,
            'bonus': bonus,
            'when': when(item.get('when'), where),
        })

    effects = []
    for index, item in enumerate(table_list('effect'), start=1):
        where = f'effect {index}'
        if not isinstance(item, dict):
            errors.append(f'{where}: 표(table)여야 합니다.')
            continue
        where = f'effect "{item.get("name") or index}"'
        for key in item:
            if key not in EFFECT_RULE_KEYS:
                errors.append(f'{where}: 알 수 없는 항목입니다: {key}')

        def names(key, item=item):
            value = item.get(key)
            if value is None:
                return []
            values = value if isinstance(value, list) else [value]
            return [str(entry).strip() for entry in values if str(entry).strip()]

        rule = {
            'name': str(item.get('name') or f'효과 {index}')[:60],
            'ability': names('ability'),
            'card': names('card'),
            'decision': names('decision'),
            'when': when(item.get('when'), where),
        }
        bad_kinds = [kind for kind in rule['decision'] if kind not in DECISION_KINDS]
        if bad_kinds:
            errors.append(f'{where}: 알 수 없는 결정 종류입니다: {", ".join(bad_kinds)}')
        if not (rule['ability'] or rule['card'] or rule['decision']):
            errors.append(f'{where}: ability, card, decision 중 하나는 있어야 합니다.')
        if 'use' in item:
            if isinstance(item['use'], bool):
                rule['use'] = item['use']
            else:
                errors.append(f'{where}: use는 true 또는 false여야 합니다.')
        for key in ('choose', 'pick', 'avoid'):
            if key in item:
                rule[key] = names(key)
        for key in ('count', 'amount'):
            if key in item:
                value = item[key]
                if value in ('max', 'min') or (
                    isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100
                ):
                    rule[key] = value
                else:
                    errors.append(f'{where}: {key}는 "max", "min" 또는 0~100 숫자여야 합니다.')
        if not any(key in rule for key in ('use', 'choose', 'pick', 'avoid', 'count', 'amount')):
            errors.append(f'{where}: use, choose, pick, avoid, count, amount 중 하나는 있어야 합니다.')
        effects.append(rule)

    effects_raw = raw.get('effects') or {}
    if not isinstance(effects_raw, dict):
        errors.append('effects는 표(table)여야 합니다.')
        effects_raw = {}
    default_use = effects_raw.get('default_use', True)
    if not isinstance(default_use, bool):
        errors.append('effects.default_use는 true 또는 false여야 합니다.')
        default_use = True

    counter_raw = raw.get('counter') or {}
    if not isinstance(counter_raw, dict):
        errors.append('counter는 표(table)여야 합니다.')
        counter_raw = {}
    scope = str(counter_raw.get('scope') or 'hand')
    if scope not in COUNTER_SCOPES:
        errors.append(f'counter.scope는 {", ".join(COUNTER_SCOPES)} 중 하나여야 합니다.')
        scope = 'hand'
    counter_bonus = _bounded(
        counter_raw.get('bonus', DEFAULT_COUNTER_BONUS), BONUS_LIMIT, 'counter.bonus', errors,
    )
    guard_bonus = _bounded(
        counter_raw.get('guard_bonus', DEFAULT_GUARD_BONUS), BONUS_LIMIT, 'counter.guard_bonus', errors,
    )
    guard_fp = _bounded(counter_raw.get('guard_fp', DEFAULT_GUARD_FP), GUARD_FP_LIMIT, 'counter.guard_fp', errors)
    if guard_fp is not None and guard_fp < 0:
        errors.append('counter.guard_fp는 0 이상이어야 합니다.')
        guard_fp = None
    hand_raw = raw.get('hand') or {}
    if not isinstance(hand_raw, dict):
        errors.append('hand는 표(table)여야 합니다.')
        hand_raw = {}
    hand_bonus = _bounded(hand_raw.get('bonus', DEFAULT_HAND_BONUS), WEIGHT_LIMIT, 'hand.bonus', errors)
    hand_keep = _bounded(hand_raw.get('keep', DEFAULT_HAND_KEEP), HAND_KEEP_LIMIT, 'hand.keep', errors)
    if hand_keep is not None and hand_keep < 1:
        errors.append('hand.keep은 1 이상이어야 합니다.')
        hand_keep = None
    swap_margin = _bounded(hand_raw.get('swap_margin', DEFAULT_SWAP_MARGIN), 4.0, 'hand.swap_margin', errors)
    if swap_margin is not None and swap_margin < 0:
        errors.append('hand.swap_margin은 0 이상이어야 합니다.')
        swap_margin = None
    safety_raw = raw.get('safety') or {}
    if not isinstance(safety_raw, dict):
        errors.append('safety는 표(table)여야 합니다.')
        safety_raw = {}

    outcome = {}
    outcome_raw = raw.get('outcome') or {}
    if not isinstance(outcome_raw, dict):
        errors.append('outcome은 표(table)여야 합니다. 예: [outcome."ST2-AT-001".hit]')
        outcome_raw = {}
    for card_code, rows in outcome_raw.items():
        # 상대 카드의 수치도 적을 수 있으므로 덱 밖 코드도 허용한다.
        card_code = code(card_code, 'outcome', own=False)
        if card_code is None:
            continue
        if not isinstance(rows, dict):
            errors.append(f'outcome."{card_code}"는 판정 결과별 표여야 합니다.')
            continue
        for result, values in rows.items():
            where = f'outcome."{card_code}".{result}'
            if result not in OUTCOME_RESULTS:
                errors.append(f'{where}: 알 수 없는 판정 결과입니다 ({", ".join(OUTCOME_RESULTS)})')
                continue
            if not isinstance(values, dict):
                errors.append(f'{where}: {{ damage = 2000, counter = 3 }} 같은 표여야 합니다.')
                continue
            row = {}
            for key, value in values.items():
                if key not in OUTCOME_LIMITS:
                    errors.append(f'{where}: 알 수 없는 자원입니다: {key} ({", ".join(OUTCOME_LIMITS)})')
                    continue
                number = _bounded(value, OUTCOME_LIMITS[key], f'{where}.{key}', errors)
                if number is not None:
                    row[key] = number
            if row:
                outcome.setdefault(card_code, {})[result] = row
    resources = {}
    resources_raw = raw.get('resources') or {}
    if not isinstance(resources_raw, dict):
        errors.append('resources는 표(table)여야 합니다. 예: [resources] counter = 200')
        resources_raw = {}
    for key, value in resources_raw.items():
        if key not in RESOURCE_HP_DEFAULTS:
            errors.append(f'resources: 알 수 없는 자원입니다: {key} ({", ".join(RESOURCE_HP_DEFAULTS)})')
            continue
        number = _bounded(value, RESOURCE_HP_LIMIT, f'resources.{key}', errors)
        if number is not None:
            # 사람이 쓰는 단위는 HP 환산값, 계산은 배틀 한 번(HP 400) 단위.
            resources[key] = number / 400.0

    profile = {
        'style': style,
        'weights': weights(raw.get('weights'), 'weights'),
        'prefer': prefer(raw.get('prefer'), 'prefer'),
        'situations': situations,
        'combos': combos,
        'counter': {
            'enabled': bool(counter_raw.get('enabled', True)),
            'bonus': counter_bonus if counter_bonus is not None else DEFAULT_COUNTER_BONUS,
            'scope': scope,
            'guard_bonus': guard_bonus if guard_bonus is not None else DEFAULT_GUARD_BONUS,
            'guard_fp': guard_fp if guard_fp is not None else DEFAULT_GUARD_FP,
        },
        'safety': {'avoid_certain_loss': bool(safety_raw.get('avoid_certain_loss', True))},
        'hand': {
            'enabled': bool(hand_raw.get('enabled', True)),
            'bonus': hand_bonus if hand_bonus is not None else DEFAULT_HAND_BONUS,
            'keep': int(hand_keep) if hand_keep is not None else DEFAULT_HAND_KEEP,
            'swap_margin': swap_margin if swap_margin is not None else DEFAULT_SWAP_MARGIN,
        },
        'effects': effects,
        'effect_settings': {'default_use': default_use},
        'outcome': outcome,
        'resources': resources,
    }
    if errors:
        raise ProfileError('\n'.join(errors))
    return profile


# Defaults for an AI seat without a registered deck profile.
DEFAULT_COUNTER = {
    'enabled': True, 'bonus': DEFAULT_COUNTER_BONUS, 'scope': 'hand',
    'guard_bonus': DEFAULT_GUARD_BONUS, 'guard_fp': DEFAULT_GUARD_FP,
}
DEFAULT_SAFETY = {'avoid_certain_loss': True}
DEFAULT_HAND = {
    'enabled': True, 'bonus': DEFAULT_HAND_BONUS, 'keep': DEFAULT_HAND_KEEP, 'swap_margin': DEFAULT_SWAP_MARGIN,
}


def counter_settings(profile):
    # 예전에 고정된 프로필(세션 문서)에는 나중에 생긴 키가 없으므로 기본값을 채운다.
    return {**DEFAULT_COUNTER, **((profile or {}).get('counter') or {})}


def hand_settings(profile):
    return {**DEFAULT_HAND, **((profile or {}).get('hand') or {})}


def safety_settings(profile):
    return (profile or {}).get('safety') or DEFAULT_SAFETY


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _action_codes(action):
    cards = []
    if isinstance(action.get('card'), dict):
        cards.append(action['card'])
    cards.extend(item for item in action.get('cards') or [] if isinstance(item, dict))
    return [str(card.get('code') or '') for card in cards if card.get('code')]


def _players(observation, role):
    players = ((observation.get('state') or {}).get('players') or {})
    rival_role = 'p2' if role == 'p1' else 'p1'
    return players.get(role) or {}, players.get(rival_role) or {}


def _combo(observation, role):
    combo = (((observation.get('state') or {}).get('engine') or {}).get('combo') or {})
    return combo if combo.get('owner') == role else {}


def _current_combo_codes(observation, role):
    combo = _combo(observation, role)
    codes = [combo.get('source_code')] if combo.get('source_code') else []
    codes.extend(code for code in combo.get('used_codes') or [] if code)
    if combo.get('selected_first_code'):
        codes.append(combo['selected_first_code'])
    return [str(code) for code in codes]


def _zone_cards(player, zone):
    return [card for card in ((player.get('zones') or {}).get(zone)) or [] if isinstance(card, dict)]


def _zone_codes(player, zones, *, visible_only):
    codes = set()
    for zone in zones:
        for card in ((player.get('zones') or {}).get(zone)) or []:
            if isinstance(card, dict) and card.get('code') and not (visible_only and card.get('hidden')):
                codes.add(str(card['code']))
    return codes


NO_ATTACK_LEAD = 99.0


def _fastest_attack(cards, fp):
    speeds = []
    for card in cards:
        frame = str((card or {}).get('frame') or '').strip()
        if '공격' in str((card or {}).get('type') or '') and frame.lstrip('-').isdigit():
            speeds.append(max(1.0, float(frame) - fp))
    return min(speeds) if speeds else None


def speed_lead(observation, role):
    """Frames by which my fastest hand attack beats the rival's fastest known one.

    Positive when I am faster. 99 when no rival attack is known, -99 when I
    hold no attack. Uses printed speed and current FP (no card effects).
    """
    from .ai_preview import rival_hand_view

    own, rival = _players(observation, role)
    mine = _fastest_attack(_zone_cards(own, 'hand'), _number(own.get('fp')))
    known, _unknown = rival_hand_view(observation, role)
    theirs = _fastest_attack(known, _number(rival.get('fp')))
    if mine is None:
        return -NO_ATTACK_LEAD
    if theirs is None:
        return NO_ATTACK_LEAD
    return theirs - mine


def condition_matches(when, observation, role, action=None):
    """True when every ``when`` condition holds for this observation/action."""
    if not when:
        return True
    state = observation.get('state') or {}
    own, rival = _players(observation, role)
    my_hp, rival_hp = _number(own.get('hp')), _number(rival.get('hp'))
    values = {
        'turn': _number(state.get('turn')),
        'my_hp': my_hp,
        'rival_hp': rival_hp,
        'hp_lead': my_hp - rival_hp,
        'my_fp': _number(own.get('fp')),
        'fp_lead': _number(own.get('fp')) - _number(rival.get('fp')),
        'combo': float(len(_combo(observation, role).get('used_codes') or [])),
        'hand': float(len(_zone_cards(own, 'hand'))),
        'hand_attack': float(sum(1 for card in _zone_cards(own, 'hand') if '공격' in str(card.get('type') or ''))),
        'hand_defense': float(sum(1 for card in _zone_cards(own, 'hand') if '수비' in str(card.get('type') or ''))),
        'my_lumen': float(len(_zone_cards(own, 'lumen'))),
    }
    if any(key.startswith('speed_lead') for key in when):
        values['speed_lead'] = speed_lead(observation, role)
    for key, expected in when.items():
        if key == 'action':
            action_type = (action or {}).get('type')
            if not any(action_type in ACTION_KINDS[kind] for kind in expected):
                return False
        elif key == 'rival_shows':
            if not set(expected) & _zone_codes(rival, ('battle', 'hand', 'list'), visible_only=True):
                return False
        elif key in ('my_counter_min', 'my_counter_max'):
            counters = own.get('passive_state') or {}
            for name, bound in expected.items():
                entry = counters.get(name) or {}
                count = _number(entry.get('count') if isinstance(entry, dict) else entry)
                if key == 'my_counter_min' and count < bound:
                    return False
                if key == 'my_counter_max' and count > bound:
                    return False
        elif key == 'i_hold':
            if not set(expected) & _zone_codes(own, ('hand',), visible_only=False):
                return False
        else:
            name, bound = key.rsplit('_', 1)
            if bound == 'min' and values[name] < expected:
                return False
            if bound == 'max' and values[name] > expected:
                return False
    return True


def profile_weights(weights, profile, observation=None, role=None, action=None):
    """Policy weights with style, deck weights and matching situations applied."""
    if not profile:
        return weights
    merged = dict(weights)
    merged.update(STYLE_PRESETS.get(profile.get('style'), {}))
    merged.update(profile.get('weights') or {})
    if observation is not None:
        for situation in profile.get('situations') or []:
            if situation.get('weights') and condition_matches(situation.get('when'), observation, role, action):
                merged.update(situation['weights'])
    return merged


def _route_extension_bonus(current, new_codes, route):
    """Bonus when ``new_codes`` continue ``route`` from the current combo.

    The proposed sequence must end with the first ``m`` route cards and the new
    cards must lie inside that matched part. Routes may begin with the battle
    card (the combo source) or with the first combo card.
    """
    cards = route['cards']
    sequence = [*current, *new_codes]
    for matched in range(min(len(cards), len(sequence)), len(new_codes) - 1, -1):
        if matched and sequence[-matched:] == cards[:matched]:
            bonus = route['bonus'] * len(new_codes)
            if matched == len(cards):
                bonus += route['bonus'] * COMPLETION_FACTOR
            return bonus
    return 0.0


def profile_bonus(observation, role, action, profile):
    """Extra score from preferred cards, situations and combo routes."""
    if not profile:
        return 0.0
    codes = _action_codes(action)
    if not codes:
        return 0.0
    bonus = sum(_number((profile.get('prefer') or {}).get(code)) for code in codes)
    for situation in profile.get('situations') or []:
        prefer = situation.get('prefer') or {}
        if prefer and condition_matches(situation.get('when'), observation, role, action):
            bonus += sum(_number(prefer.get(code)) for code in codes)
    routes = [
        route for route in profile.get('combos') or []
        if condition_matches(route.get('when'), observation, role, action)
    ]
    action_type = action.get('type')
    if action_type in COMBO_ACTION_TYPES:
        current = _current_combo_codes(observation, role)
        bonus += max(
            (_route_extension_bonus(current, codes, route) for route in routes),
            default=0.0,
        )
    elif action_type == 'ready_card':
        bonus += max(
            (route['bonus'] * READY_STARTER_FACTOR for route in routes if route['cards'][0] in codes),
            default=0.0,
        )
    elif action_type in GET_ACTION_TYPES:
        bonus += max(
            (route['bonus'] * GET_MEMBER_FACTOR for route in routes if set(codes) & set(route['cards'])),
            default=0.0,
        )
    return bonus
