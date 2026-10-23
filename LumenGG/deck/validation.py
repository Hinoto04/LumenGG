"""Snapshot-based draft, registration, replacement and setup validation."""
import copy
from collections import Counter
from types import SimpleNamespace
from card.models import Card
from battlelog.game.card_identity import is_passive_card
from .regulations import DEFAULT_RULES

CARD_FIELDS = ('id', 'name', 'code', 'character_id', 'type', 'ultimate', 'text', 'detail_text', 'effect_definition', 'trait_config', 'frame', 'damage', 'pos', 'body', 'special', 'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot', 'img', 'img_mid', 'img_sm')


def card_snapshot(card):
    return {key: copy.deepcopy(getattr(card, key, None)) for key in CARD_FIELDS}


def snapshot_deck(deck, regulation=None):
    from .traits import selected_trait
    trait = deck.trait_card or selected_trait(deck.character_id)
    entries = list(deck.cids.select_related('card'))
    reserve = list(deck.reserve_entries.select_related('card'))
    cards = {str(row.card_id): card_snapshot(row.card) for row in entries + reserve}
    if trait:
        cards[str(trait.id)] = card_snapshot(trait)
    version = regulation if regulation is not None else deck.regulation_version
    return {'schema_version': 2, 'deck_id': deck.pk, 'name': deck.name,
            'character_id': deck.character_id, 'character': {'id': deck.character_id, 'name': deck.character.name, 'datas': copy.deepcopy(deck.character.datas), **{k: getattr(deck.character, k, '') for k in ('img', 'sd_img', 'body_img', 'icon_img', 'color')}},
            'trait_card_id': trait.id if trait else None,
            'cards': [{'card_id': e.card_id, 'count': e.count, 'hand': e.hand, 'side': e.side} for e in entries],
            'reserve_cards': [{'card_id': e.card_id, 'count': e.count} for e in reserve],
            'catalog': cards, 'regulation_version_id': version.pk if version else None,
            'regulation_rules': copy.deepcopy(version.rules) if version else None}


def baseline(snapshot):
    return {key: copy.deepcopy(snapshot.get(key)) for key in ('character_id', 'trait_card_id', 'cards')}


def snapshot_candidate(data, user):
    from card.models import Character
    from .regulations import accessible_versions
    character = Character.objects.get(pk=data.get('character_id'))
    entries, reserve = data.get('cards', []), data.get('reserve_cards', [])
    if not isinstance(entries, list) or not isinstance(reserve, list) or len(entries) + len(reserve) > 1000:
        raise ValueError('Invalid card list.')
    ids = {row['card_id'] for row in entries + reserve}
    if data.get('trait_card_id'):
        ids.add(data['trait_card_id'])
    cards = Card.objects.in_bulk(ids)
    version = accessible_versions(user).filter(pk=data.get('regulation_version_id')).first()
    if not version and data.get('deck_id'):
        from .models import Deck
        from .views.views import can_view_deck
        context = Deck.objects.filter(pk=data['deck_id'], deleted=False, regulation_version_id=data.get('regulation_version_id')).first()
        if context and can_view_deck(user, context):
            version = context.regulation_version
    if data.get('regulation_version_id') and not version:
        raise ValueError('Unavailable regulation.')
    return {'schema_version': 2, 'character_id': character.pk, 'character': {'id': character.pk, 'name': character.name, 'datas': character.datas},
            'trait_card_id': data.get('trait_card_id'), 'cards': entries, 'reserve_cards': reserve,
            'catalog': {str(pk): card_snapshot(card) for pk, card in cards.items()},
            'regulation_version_id': version.pk if version else None, 'regulation_rules': version.rules if version else None}


def validate(snapshot, *, stage='registration', active=None, ruleset=None):
    if stage not in ('draft', 'registration', 'replacement', 'setup'):
        raise ValueError('Invalid validation stage.')
    issues = []
    def issue(code, message, ids=(), *, severity='error'):
        issues.append({'code': code, 'severity': severity, 'card_ids': list(ids), 'message': message})
    catalog = snapshot.get('catalog') or {}
    unrestricted = snapshot.get('regulation_rules') is None
    policy = {**DEFAULT_RULES, **(snapshot.get('regulation_rules') or {})}
    current = active if active is not None else baseline(snapshot)
    if not isinstance(current, dict) or current.get('character_id') != snapshot.get('character_id'):
        issue('character_fixed', '등록한 캐릭터는 교체할 수 없습니다.')
        current = baseline(snapshot)
    def counts(rows, *, placement=False):
        result = Counter()
        if not isinstance(rows, list) or len(rows) > 1000:
            issue('invalid_entries', '카드 목록이 올바르지 않습니다.')
            return result
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                issue('invalid_entry', '카드 항목이 올바르지 않습니다.')
                continue
            pk, n = row.get('card_id'), row.get('count')
            if isinstance(pk, bool) or not isinstance(pk, int) or str(pk) not in catalog:
                issue('unknown_card', '등록되지 않은 카드입니다.')
                continue
            if pk in seen:
                issue('duplicate_entry', '카드 항목이 중복되었습니다.', [pk])
            seen.add(pk)
            if isinstance(n, bool) or not isinstance(n, int) or not 1 <= n <= 1000:
                issue('invalid_count', '수량이 올바르지 않습니다.', [pk])
                continue
            if placement:
                h, s = row.get('hand', 0), row.get('side', 0)
                if any(isinstance(v, bool) or not isinstance(v, int) or v < 0 for v in (h, s)) or h + s > n:
                    issue('invalid_placement', '시작 배치 수량이 올바르지 않습니다.', [pk])
            result[pk] += n
        return result
    base = counts(snapshot.get('cards', []))
    reserve = counts(snapshot.get('reserve_cards', []))
    used = counts(current.get('cards', []), placement=True)
    base_trait = snapshot.get('trait_card_id')
    trait_id = current.get('trait_card_id')
    if isinstance(trait_id, bool) or (trait_id is not None and not isinstance(trait_id, int)):
        issue('trait_required', '특성 선택이 올바르지 않습니다.')
        trait_id = None
    for target in (base_trait, trait_id):
        trait = catalog.get(str(target)) or {}
        if not target or not is_passive_card(trait) or trait.get('character_id') != snapshot['character_id']:
            issue('trait_required', '선택한 캐릭터의 특성 1장을 지정해주세요.', [target] if target else [])
    registered = base + reserve
    if base_trait:
        registered[base_trait] += 1
    active_counts = used.copy()
    if trait_id:
        active_counts[trait_id] += 1
    if not unrestricted and sum(reserve.values()) > policy['reserve_limit']:
        issue('reserve_limit', f'교체 덱 등록 한도를 초과했습니다. ({sum(reserve.values())}/{policy["reserve_limit"]})', reserve)
    for pk, n in active_counts.items():
        if ruleset and str((catalog.get(str(pk)) or {}).get('code') or '') not in ruleset.get('cards', {}):
            issue('unreleased_card', '이 자동 규칙 릴리스에서 사용할 수 없는 카드입니다.', [pk])
        if n > registered[pk]:
            issue('unregistered_card', '등록한 카드 수량을 초과했습니다.', [pk])
    for pk in used:
        if is_passive_card(catalog[str(pk)]):
            issue('trait_in_techniques', '특성은 기술 카드 구성에 넣을 수 없습니다.', [pk])
    if not unrestricted:
        for pk in reserve:
            card = catalog[str(pk)]
            if is_passive_card(card) and card['character_id'] != snapshot['character_id']:
                issue('foreign_trait', '같은 캐릭터의 특성만 등록할 수 있습니다.', [pk])
            elif not is_passive_card(card) and not any(k in (card.get('type') or '') for k in ('공격', '수비', '특수')):
                issue('invalid_reserve_type', '교체 덱에 등록할 수 없는 카드입니다.', [pk])
    def techniques(counter):
        return Counter({pk: n for pk, n in counter.items() if not (catalog[str(pk)].get('ultimate') or is_passive_card(catalog[str(pk)]))})
    old_tech, new_tech = techniques(base), techniques(used)
    swap_counts = {'technique': max(sum((new_tech - old_tech).values()), sum((old_tech - new_tech).values())),
                   'trait': int(trait_id != base_trait),
                   'ultimate': int({pk: n for pk, n in base.items() if catalog[str(pk)].get('ultimate')} != {pk: n for pk, n in used.items() if catalog[str(pk)].get('ultimate')})}
    if not unrestricted and stage in ('replacement', 'setup'):
        for kind, count in swap_counts.items():
            if count > policy[f'{kind}_swap_limit']:
                issue(f'{kind}_swap_limit', f'{kind}: 교체 한도를 초과했습니다. ({count}/{policy[f"{kind}_swap_limit"]})')
    if not unrestricted:
        for key, code in (('bans', 'banned_card'), ('combinations', 'restricted_combination')):
            for rule in policy[key]:
                pool = registered if rule.get('scope', 'registered') == 'registered' else active_counts
                matched = [pk for pk in rule['card_ids'] if pool[pk] > 0]
                if matched and (key == 'bans' or len(matched) == len(rule['card_ids'])):
                    names = ' + '.join((catalog.get(str(pk)) or {}).get('name', str(pk)) for pk in matched)
                    issue(code, f'{"금지 카드" if key == "bans" else "제한 조합"}: {names}', matched)
    if not unrestricted and not any(i['code'] in ('invalid_count', 'unknown_card', 'invalid_entry', 'invalid_entries', 'invalid_placement') for i in issues):
        from .game_validation import validate_automatic_deck
        character = SimpleNamespace(**snapshot['character'])
        trait = SimpleNamespace(**catalog[str(trait_id)]) if str(trait_id) in catalog else None
        deck = SimpleNamespace(character_id=snapshot['character_id'], character=character, schema_version=2, trait_card=trait)
        rows = [SimpleNamespace(card=SimpleNamespace(**catalog[str(row['card_id'])]), count=row['count'], hand=row.get('hand', 0), side=row.get('side', 0)) for row in current.get('cards', [])]
        report = validate_automatic_deck(deck, entries=rows, ruleset=ruleset, check_setup=stage == 'setup')
        for message in report.errors:
            issue('deck_composition', message, [int(pk) for pk, c in catalog.items() if c.get('name') and c['name'] in message])
    if stage == 'draft':
        for item in issues:
            if item['code'] not in ('invalid_count', 'unknown_card', 'invalid_entry', 'invalid_entries', 'invalid_placement', 'duplicate_entry'):
                item['severity'] = 'warning'
    return {'stage': stage, 'regulation_version_id': snapshot.get('regulation_version_id'), 'issues': issues,
            'is_valid': not any(i['severity'] == 'error' for i in issues), 'swap_counts': swap_counts}
