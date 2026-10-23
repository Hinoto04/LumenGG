"""Shared technique-deck validation; retained adapter for legacy automatic games."""
import re
from dataclasses import dataclass, field
from django.db.models import Q
from card.models import Card
from deck.models import CardInDeck
from battlelog.game.card_identity import is_passive_card
from battlelog.game.deck_rules import allocate_supplement_counts, deck_rules_from_card_snapshots, main_size_range, merge_deck_rules
from battlelog.game.effects import card_matches

NEUTRAL_CHARACTER_ID = 1
CHARACTER_MAIN_DECK_EXCEPTIONS = {5: 24, 15: 33, 16: 26, 17: 25}

@dataclass
class DeckValidationReport:
    side: str
    errors: list = field(default_factory=list)

    @property
    def is_valid(self):
        return not self.errors

    def as_dict(self):
        return {'side': self.side, 'is_valid': self.is_valid, 'errors': self.errors}


def _is_special(card):
    return not is_passive_card(card) and '특수' in str(card.type or '')


def _is_attack(card):
    return not is_passive_card(card) and '공격' in str(card.type or '')


def _is_defense(card):
    return not is_passive_card(card) and '수비' in str(card.type or '')


def _card_definition(card, ruleset=None):
    if ruleset:
        released = ((ruleset.get('cards') or {}).get(str(card.code or '')) or {})
        return released.get('effect_definition') or {}
    return card.effect_definition or {}


def _card_rule_payload(card, ruleset=None):
    definition = _card_definition(card, ruleset)
    code = getattr(card, 'code', '') or ''
    character_id = getattr(card, 'character_id', None)
    released = ((ruleset or {}).get('cards') or {}).get(str(code)) or {}
    character = ((ruleset or {}).get('characters') or {}).get(str(character_id)) or {}
    return {
        'code': code,
        'name': getattr(card, 'name', ''),
        'type': getattr(card, 'type', ''),
        'ultimate': bool(getattr(card, 'ultimate', False)),
        'character_id': character_id,
        'character_key': character.get('key'),
        'token_key': definition.get('token_key'),
        **{key: value for key, value in released.items() if key in {
            'code', 'name', 'type', 'ultimate', 'character_id', 'character_key',
        }},
    }


def _card_same_name_limit(card, default, *, ruleset=None, supplements=None):
    definition = _card_definition(card, ruleset)
    configured = definition.get('deck_limit')
    if isinstance(configured, int) and not isinstance(configured, bool) and configured >= 1:
        default = configured
    payload = _card_rule_payload(card, ruleset)
    for supplement in supplements or []:
        if card_matches(payload, supplement.get('where')):
            configured = supplement.get('same_name_limit')
            if isinstance(configured, int) and not isinstance(configured, bool) and configured >= 1:
                default = max(default, configured)
    text = re.sub(r'\s+', ' ', str(card.text or ''))
    match = re.search(
        r'이 (?:기술|카드)은\s*(?:(\d+)장까지\s*덱에|덱에\s*(\d+)장까지)\s*넣을 수 있다',
        text,
    )
    if match:
        return max(default, int(next(value for value in match.groups() if value)))
    return default


def _character_deck_rules(deck, ruleset=None):
    trait = getattr(deck, 'trait_card', None)
    if getattr(deck, 'schema_version', 1) >= 2:
        released = ((ruleset or {}).get('characters') or {}).get(str(deck.character_id)) or {}
        configured = released.get('base_deck_rules', (released.get('datas') or {}).get('base_deck_rules', {}))
        if not ruleset:
            configured = (deck.character.datas or {}).get('base_deck_rules') or {}
        return merge_deck_rules(configured, (getattr(trait, 'trait_config', None) or {}).get('deck_rules'), _card_definition(trait, ruleset).get('deck_rules') if trait else {})
    if ruleset:
        released = ((ruleset.get('characters') or {}).get(str(deck.character_id)) or {})
        return merge_deck_rules(released.get('deck_rules') or {})
    characteristic_cards = Card.objects.filter(Q(character_id=deck.character_id), Q(type='특성') | Q(code__icontains='PS')).values('character_id', 'code', 'type', 'effect_definition')
    return merge_deck_rules((deck.character.datas or {}).get('automatic_deck_rules') or {}, deck_rules_from_card_snapshots(characteristic_cards, deck.character_id))


def validate_automatic_deck(deck, *, side='', ruleset=None, entries=None, check_setup=True):
    """Validate the rulebook setup constraints before automatic play."""
    if entries is None:
        entries = list(CardInDeck.objects.filter(deck=deck).select_related('card', 'card__character'))
    report = DeckValidationReport(side=side)
    rules = merge_deck_rules(
        _character_deck_rules(deck, ruleset),
        *(
            (_card_definition(entry.card, ruleset) or {}).get(
                'deck_rules_when_included',
            ) or {}
            for entry in entries
            if int(entry.count or 0) > 0
        ),
    )
    has_structured_size = isinstance(rules.get('main_size'), (dict, int))
    if has_structured_size:
        minimum_main_size, maximum_main_size = main_size_range(rules)
    else:
        legacy_size = int(CHARACTER_MAIN_DECK_EXCEPTIONS.get(deck.character_id, 20)) if getattr(deck, 'schema_version', 1) < 2 else 20
        minimum_main_size = maximum_main_size = legacy_size
    same_name_limit = int(rules.get('same_name_limit', 1))
    character_minimum = int(rules.get('character_card_minimum', 10))
    hand_size = int(rules.get('opening_hand_size', 5))
    list_size = int(rules.get('opening_list_size', 9))

    technique_count = 0
    character_count = 0
    ultimate_count = 0
    hand_count = 0
    list_count = 0
    names = {}
    name_limits = {}
    invalid_marks = []
    supplements = rules.get('supplements') or []
    supplement_counts = [0 for _item in supplements]
    supplement_character_counts = [0 for _item in supplements]
    imported_counts = {}
    imported_rule = rules.get('other_character_cards') or {}
    for entry in entries:
        card = entry.card
        count = max(0, int(entry.count or 0))
        card_payload = _card_rule_payload(card, ruleset)
        matching_supplements = [
            index for index, supplement in enumerate(supplements)
            if card_matches(card_payload, supplement.get('where'))
        ]
        supplement = supplements[matching_supplements[0]] if matching_supplements else {}
        for index in matching_supplements:
            supplement_counts[index] += count
            if card.character_id == deck.character_id:
                supplement_character_counts[index] += count
        allowed_character_ids = set(rules.get('allowed_character_ids') or [deck.character_id, NEUTRAL_CHARACTER_ID])
        imported = (
            card.character_id not in allowed_character_ids
            and card.character_id not in set(imported_rule.get('exclude_character_ids') or [])
            and card.type in set(imported_rule.get('allowed_types') or [])
            and (not imported_rule.get('exclude_ultimate') or not card.ultimate)
        )
        supplement_allows_mark = bool(supplement.get('allow_foreign_mark'))
        if card.character_id not in allowed_character_ids and not imported and not supplement_allows_mark:
            invalid_marks.append(card.name)
        if imported:
            imported_counts[card.character_id] = imported_counts.get(card.character_id, 0) + count
        if card.ultimate:
            ultimate_count += count
            if check_setup and (int(entry.hand or 0) or int(entry.side or 0)):
                report.errors.append(f'{card.name}: 얼티밋은 패·사이드 대신 얼티밋 영역에 배치해주세요.')
            continue
        is_technique = _is_attack(card) or _is_defense(card) or _is_special(card)
        if not is_technique and not supplement.get('allow_non_technique'):
            report.errors.append(f'{card.name}: 기술 덱에는 공격·수비·특수 기술만 넣을 수 있습니다.')
        technique_count += count
        names[card.name] = names.get(card.name, 0) + count
        name_limits[card.name] = max(
            name_limits.get(card.name, same_name_limit),
            _card_same_name_limit(
                card, same_name_limit, ruleset=ruleset, supplements=supplements,
            ),
        )
        if card.character_id == deck.character_id:
            character_count += count
        if _is_special(card):
            special_character_ids = rules.get('special_allowed_character_ids')
            if (
                isinstance(special_character_ids, list)
                and card.character_id not in set(special_character_ids)
            ):
                report.errors.append(
                    f'{card.name}: 이 덱에는 허용된 캐릭터의 특수 기술만 넣을 수 있습니다.'
                )
            # Special techniques count toward the 20-card technique deck, but
            # setup always places them in the side deck (rulebook p20/p37).
            if check_setup and (int(entry.hand or 0) or int(entry.side or 0) != count):
                report.errors.append(f'{card.name}: 특수 기술은 전부 사이드 덱에 있어야 합니다.')
            continue
        raw_hand = max(0, int(entry.hand or 0))
        raw_side = max(0, int(entry.side or 0))
        if raw_hand + raw_side > count:
            report.errors.append(f'{card.name}: 패와 사이드 배치 수가 보유 수량을 초과합니다.')
        allocated_hand = min(count, raw_hand)
        allocated_side = min(count - allocated_hand, raw_side)
        hand_count += allocated_hand
        list_count += count - allocated_hand - allocated_side

    if technique_count < minimum_main_size or technique_count > maximum_main_size:
        expected = (
            f'정확히 {minimum_main_size}장'
            if minimum_main_size == maximum_main_size
            else f'{minimum_main_size}~{maximum_main_size}장'
        )
        report.errors.append(f'기술 카드는 {expected}이어야 합니다. (현재 {technique_count}장)')
    main_size_rule = rules.get('main_size') or {}
    supplement_allocations = [0 for _item in supplements]
    if isinstance(main_size_rule, dict) and main_size_rule.get('base_excludes_supplements'):
        base_size = int(main_size_rule.get('min', 20))
        supplement_allocations = allocate_supplement_counts(
            technique_count, base_size, supplements, supplement_counts,
        )
        supplemental_total = sum(supplement_allocations)
        if technique_count - supplemental_total != int(main_size_rule.get('min', 20)):
            report.errors.append(
                '기본 기술 덱은 보충 카드를 제외하고 '
                f'{int(main_size_rule.get("min", 20))}장이어야 합니다. '
                f'(현재 {technique_count - supplemental_total}장)'
            )
    for index, count in enumerate(supplement_counts):
        maximum = int((supplements[index] or {}).get('max_count') or 0)
        if not (supplements[index] or {}).get('allow_base_copies') and count > maximum:
            report.errors.append(f'보충 카드 제한을 초과했습니다: {count}/{maximum}장')
    imported_maximum = imported_rule.get('max_per_character')
    if isinstance(imported_maximum, int) and not isinstance(imported_maximum, bool):
        exceeded = sorted(
            character_id for character_id, count in imported_counts.items()
            if count > imported_maximum
        )
        if exceeded:
            report.errors.append(
                '타 캐릭터 마크별 카드 제한을 초과했습니다: '
                + ', '.join(
                    f'{character_id}({imported_counts[character_id]}/{imported_maximum}장)'
                    for character_id in exceeded
                )
            )
    duplicates = sorted(name for name, count in names.items() if count > name_limits.get(name, same_name_limit))
    if duplicates:
        details = ', '.join(f'{name}({name_limits.get(name, same_name_limit)}장)' for name in duplicates)
        report.errors.append(f'동일 이름 카드 제한을 초과했습니다: {details}')
    base_character_count = character_count - sum(
        min(supplement_allocations[index], supplement_character_counts[index])
        for index in range(len(supplements))
    )
    if base_character_count < character_minimum:
        report.errors.append(f'캐릭터 마크 기술은 최소 {character_minimum}장이어야 합니다. (현재 {base_character_count}장)')
    if invalid_marks:
        report.errors.append(f'사용할 수 없는 캐릭터 마크가 포함되어 있습니다: {", ".join(sorted(set(invalid_marks)))}')
    if ultimate_count > int(rules.get('ultimate_maximum', 1)):
        report.errors.append('얼티밋 카드는 1장까지만 허용됩니다.')
    if check_setup and hand_count != hand_size:
        report.errors.append(f'공개할 시작 패는 정확히 {hand_size}장이어야 합니다. (현재 {hand_count}장)')
    if check_setup and list_count != list_size:
        report.errors.append(f'시작 리스트는 정확히 {list_size}장이어야 합니다. (현재 {list_count}장)')
    return report


