"""Helpers shared by catalog snapshots, deck validation, and the engine."""

import copy

from .card_identity import is_passive_card


DEFAULT_MAIN_SIZE = 20


def merge_deck_rules(*values):
    """Merge independently printed setup rules in a deterministic order."""
    merged = {}
    supplements = []
    for value in values:
        if not isinstance(value, dict):
            continue
        for key, item in value.items():
            if key == 'supplements':
                supplements.extend(
                    copy.deepcopy(entry)
                    for entry in (item or [])
                    if isinstance(entry, dict)
                )
            elif key == 'other_character_cards' and isinstance(item, dict):
                merged[key] = {**merged.get(key, {}), **copy.deepcopy(item)}
            else:
                merged[key] = copy.deepcopy(item)
    if supplements:
        merged['supplements'] = supplements
    return merged


def deck_rules_from_card_snapshots(cards, character_id):
    """Collect root deck rules from a character's public characteristic cards."""
    definitions = []
    rows = cards.values() if isinstance(cards, dict) else cards
    for card in rows:
        if not isinstance(card, dict):
            continue
        if card.get('character_id') != character_id or not is_passive_card(card):
            continue
        definition = card.get('effect_definition') or {}
        if definition.get('deck_rules'):
            definitions.append(definition['deck_rules'])
    return merge_deck_rules(*definitions)


def main_size_range(rules):
    configured = (rules or {}).get('main_size')
    if isinstance(configured, int) and not isinstance(configured, bool):
        return configured, configured
    if isinstance(configured, dict):
        minimum = int(configured.get('min', DEFAULT_MAIN_SIZE))
        maximum = int(configured.get('max', minimum))
        return minimum, maximum
    return DEFAULT_MAIN_SIZE, DEFAULT_MAIN_SIZE


def allocate_supplement_counts(total_count, base_size, supplements, counts):
    """Choose which matching cards occupy printed additional deck slots.

    Most supplementary cards can only occupy those added slots, so every
    matching copy is fixed as a supplement.  ``allow_base_copies`` rules are
    different: matching cards may already be part of the ordinary base deck,
    and only the number needed above ``base_size`` consumes the added slots.
    """
    supplements = list(supplements or [])
    counts = [max(0, int(value or 0)) for value in (counts or [])]
    allocations = [0 for _item in supplements]
    fixed_total = 0
    for index, supplement in enumerate(supplements):
        count = counts[index] if index < len(counts) else 0
        if (supplement or {}).get('allow_base_copies'):
            continue
        allocations[index] = count
        fixed_total += count
    remaining_extra = max(
        0, int(total_count or 0) - int(base_size or 0) - fixed_total,
    )
    for index, supplement in enumerate(supplements):
        supplement = supplement or {}
        if not supplement.get('allow_base_copies'):
            continue
        count = counts[index] if index < len(counts) else 0
        allocated = min(
            count, max(0, int(supplement.get('max_count') or 0)),
            remaining_extra,
        )
        allocations[index] = allocated
        remaining_extra -= allocated
    return allocations
