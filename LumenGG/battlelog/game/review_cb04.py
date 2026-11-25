"""CB04 카드 17장의 카드별 결정적 자동 검토 시나리오.

`drafts_cb04.py`가 만든 정의가 그대로인지 확인한 뒤, 능력마다 소유자 p1/p2와
발동하지 않아야 하는 상황을 최소 3개씩 실제 엔진으로 실행한다. 같은 입력을 두 번
실행해 결과가 같아야 결정적 증거로 인정한다.
"""

import copy

from .drafts_cb04 import BUILDERS, build_cb04_definition
from .engine import AutomaticGameEngine
from .review import (
    AUTOMATIC_SCENARIO_VERSION, AbilityReview, DefinitionReview, _canonical,
)


BUKUKI = '부쿠키'
CHARACTER_BY_CODE = {
    'CB04-AT-035': 'cmyk', 'CB04-AT-036': 'cmyk', 'CB04-AT-037': 'cmyk',
    'CB04-TK-001': 'delphi', 'CB04-AT-021': 'tao', 'CB04-AT-022': 'tao',
    'CB04-AT-030': 'muyoung', 'CB04-AT-032': None,
    'CB04-AT-031': 'muyoung', 'CB04-AT-033': 'pinp', 'CB04-AT-034': 'pinp',
    'CB04-AT-024': 'rin', 'CB04-AT-027': 'ezebel',
}
META_ROOT_KEYS = {'reviewed', 'draft', 'review_evidence', 'source_digest', 'source_refs'}
META_ABILITY_KEYS = {'draft', 'source_refs'}
NO_EFFECT = {
    'schema_version': 1, 'reviewed': True, 'no_effect': True,
    'source_refs': {'rulebook_pages': [], 'qna_ids': []}, 'abilities': [],
}


def _set_effect_definition(key, condition_character='cmyk', effects=None):
    """【드럼】처럼 [CMYK] 기술에 세트됐을 때 사용 시 발동하는 검토용 세트 효과."""
    return {
        'schema_version': 1, 'reviewed': True, 'no_effect': False,
        'abilities': [{
            'id': f'review-cb04-{key}-n1', 'kind': 'effect', 'mode': 'mandatory',
            'timing': 'use', 'visibility': 'public', 'draft_compiled': True,
            'trigger': {'event': 'use'}, 'active_when_attached': True,
            'dedupe_trigger_key': f'cmyk:set:{key}',
            'condition': {'op': 'all', 'conditions': [
                {'op': 'equals', 'left': 'context.source_card.attached_to',
                 'right': {'path': 'context.event_card.instance_id'}},
                {'op': 'card_matches', 'card': {'path': 'context.event_card'},
                 'where': {'character_key': condition_character}},
            ]},
            'effects': effects or [
                {'op': 'change_fp', 'player': {'controller': True}, 'amount': 1},
            ],
        }],
    }


DRUM_DEFINITION = _set_effect_definition('drum')
DRUM_TEXT = '①[[token:drum]](<[[character:cmyk]]> 기술에 세트된 경우, 사용 시 1FP를 얻는다.)'


def _opp(owner):
    return 'p2' if owner == 'p1' else 'p1'


def _card(instance_id, owner, *, code=None, type_='공격', frame=5, damage=400,
          hit='0', counter='0', guard='0', character=None, text='',
          top=None, mid=None, bottom=None, special=None):
    card = {
        'instance_id': instance_id, 'kind': 'card', 'owner': owner,
        'code': code or f'REVIEW-CB04-{instance_id.upper()}', 'name': instance_id,
        'type': type_, 'frame': frame if type_ == '공격' else None,
        'damage': damage if type_ == '공격' else None,
        'pos': '상단' if type_ == '공격' else None, 'special': special,
        'hit': hit, 'guard': guard, 'counter': counter,
        'g_top': top, 'g_mid': mid, 'g_bot': bottom,
        'face_up': True, 'text': text,
    }
    if character:
        card['character_key'] = character
    return card


def _source(snapshot, code, owner, *, negated=False):
    snapshot = snapshot or {}
    type_ = str(snapshot.get('type') or '공격')
    card = _card(
        f'{owner}-source', owner, code=code,
        type_='수비' if '수비' in type_ else ('특성' if '특성' in type_ else (
            '토큰' if '토큰' in type_ else '공격')),
        frame=snapshot.get('frame') or 6,
        damage=snapshot.get('damage') if snapshot.get('damage') is not None else 400,
        hit=str(snapshot.get('hit') or '0'), counter=str(snapshot.get('counter') or '0'),
        guard=str(snapshot.get('guard') or '0'), character=CHARACTER_BY_CODE.get(code, BUKUKI),
        top=snapshot.get('g_top'), mid=snapshot.get('g_mid'), bottom=snapshot.get('g_bot'),
        special=snapshot.get('special'),
    )
    card['name'] = snapshot.get('name') or code
    if negated:
        card['numbered_effects_negated'] = True
    return card


def _engine(definition, source, zones, *, seed, fp=None, hp=None, definitions=None, phase='battle'):
    players = {}
    for side in ('p1', 'p2'):
        side_zones = {
            'character': [], 'passive': [], 'battle': [], 'list': [], 'hand': [],
            'side': [], 'break': [], 'lumen': [], 'ultimate': [],
        }
        for zone, cards in (zones.get(side) or {}).items():
            side_zones[zone] = [copy.deepcopy(card) for card in cards]
        players[side] = {
            'name': side, 'hp': (hp or {}).get(side, 5000), 'fp': (fp or {}).get(side, 0),
            'passive_state': {}, 'zones': side_zones,
        }
    state = {'turn': 1, 'phase': 'lumen', 'priority_player': 'p1', 'players': players}
    cards = {}
    for side_zones in zones.values():
        for zone_cards in side_zones.values():
            for card in zone_cards:
                cards[card['code']] = card
    release = {'version': AUTOMATIC_SCENARIO_VERSION, 'cards': {}}
    for code, card in cards.items():
        release['cards'][code] = {
            **{key: card.get(key) for key in (
                'code', 'name', 'type', 'frame', 'damage', 'pos', 'special', 'hit',
                'guard', 'counter', 'g_top', 'g_mid', 'g_bot', 'text',
            )},
            'effect_definition': copy.deepcopy(
                definition if code == source['code']
                else (definitions or {}).get(code, NO_EFFECT)
            ),
        }
    engine = AutomaticGameEngine.initialize(state, release, seed=seed)
    engine.state['phase'] = phase
    return engine


def _resolve(engine, *, accept=True):
    for _ in range(12):
        decision = engine.engine_state.get('pending_decision') or {}
        if not decision:
            return True
        options = [item.get('id') for item in decision.get('options') or []]
        kind = decision.get('kind')
        if kind == 'break_replenish' and 'decline' in options:
            selected = ['decline']
        elif kind == 'optional_effect':
            selected = ['accept' if accept and 'accept' in options else options[-1]]
        elif kind == 'effect_choice':
            maximum = int(decision.get('maximum') or 0)
            minimum = int(decision.get('minimum') or 0)
            selected = options[:max(minimum, maximum, 1)]
        else:
            selected = options[:1]
        engine._submit_decision(decision['owner'], decision['id'], selected)
        engine._continue()
    return False


def _fire(engine, event, source, **extra):
    engine._fire(event, {
        'controller': source['owner'], 'source_card': engine._find_card(source['instance_id']) or source,
        'source_card_instance_id': source['instance_id'], **extra,
    })
    return _resolve(engine)


def _frost(engine, side):
    return bool((engine.state['players'][side]['passive_state'].get('frost') or {}).get('value'))


def _zone_of(engine, instance_id):
    return engine._find_location(instance_id)[1]


def _zone_ids(engine, side, zone):
    return sorted(card['instance_id'] for card in engine.state['players'][side]['zones'][zone])


def _damage_delta(engine, source, side):
    live = engine._find_card(source['instance_id']) or source
    return engine.card_stat(live, 'damage', side) - (source.get('damage') or 0)


def _blocked(engine, kind, side, *, with_where=None):
    for item in engine.engine_state.get('replacements') or []:
        if item.get('op') != 'prevent' or item.get('kind') != kind or item.get('player') != side:
            continue
        if with_where is None or bool(item.get('where')) == with_where:
            return True
    return False


# --- 공통 시나리오 ---------------------------------------------------------------

def _run_defense_rule(definition, snapshot, owner, *, code, judgment, frame=5, guard='0', hit='0'):
    source = _source(snapshot, code, owner)
    attacker = _card(f'{_opp(owner)}-attacker', _opp(owner), frame=frame, guard=guard, hit=hit)
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [attacker]}},
                     seed=f'cb04-defense:{code}:{owner}:{judgment}:{frame}:{guard}:{hit}')
    return {'allowed': bool(engine._defense_judgment_allowed(
        engine._find_card(source['instance_id']), attacker, judgment, _opp(owner),
    ))}


def _run_frost_damage(definition, snapshot, owner, *, code, frost=True, negated=False):
    source = _source(snapshot, code, owner, negated=negated)
    engine = _engine(definition, source, {owner: {'battle': [source]}},
                     seed=f'cb04-frost-damage:{code}:{owner}:{frost}:{negated}')
    if frost:
        engine.set_passive(_opp(owner), 'frost', value=True)
    engine._refresh_continuous_rules()
    return {'damage_delta': _damage_delta(engine, source, owner)}


def _frost_damage_cases(code):
    return (
        ('owner-p1-opponent-frost-adds-200', 'p1', {'code': code}, {'damage_delta': 200}),
        ('owner-p2-opponent-frost-adds-200', 'p2', {'code': code}, {'damage_delta': 200}),
        ('no-frost-keeps-printed-damage', 'p1', {'code': code, 'frost': False}, {'damage_delta': 0}),
    )


def _run_blocked(definition, snapshot, owner, *, code, kind, zone='battle', with_where=None,
                 harmony=False):
    source = _source(snapshot, code, owner)
    engine = _engine(definition, source, {owner: {zone: [source]}},
                     seed=f'cb04-blocked:{code}:{owner}:{kind}:{zone}:{harmony}')
    if harmony:
        engine.set_passive(owner, 'harmony', value=True)
    engine._refresh_continuous_rules()
    return {'opponent_blocked': _blocked(engine, kind, _opp(owner), with_where=with_where)}


def _blocked_cases(code, kind, *, with_where=None):
    common = {'code': code, 'kind': kind, 'with_where': with_where}
    return (
        ('owner-p1-in-battle-blocks-opponent', 'p1', dict(common), {'opponent_blocked': True}),
        ('owner-p2-in-battle-blocks-opponent', 'p2', dict(common), {'opponent_blocked': True}),
        ('outside-battle-zone-has-no-effect', 'p1', {**common, 'zone': 'hand'}, {'opponent_blocked': False}),
    )


# --- 카드별 시나리오 ---------------------------------------------------------------

def _run_ps001_guard(definition, snapshot, owner, *, event='guard', by_opponent=False,
                     stock_character=BUKUKI):
    source = _source(snapshot, 'CB04-PS-001', owner)
    stock = _card(f'{owner}-stock', owner, code='REVIEW-CB04-STOCK', character=stock_character)
    engine = _engine(definition, source, {owner: {'passive': [source], 'hand': [stock]}},
                     seed=f'cb04-ps001:{owner}:{event}:{by_opponent}:{stock_character}')
    engine._fire(event, {'controller': _opp(owner) if by_opponent else owner})
    _resolve(engine)
    return {
        'opponent_frost': _frost(engine, _opp(owner)), 'owner_frost': _frost(engine, owner),
        'lumen': _zone_ids(engine, owner, 'lumen'),
    }


def _run_ps001_recovery(definition, snapshot, owner, *, owner_fp, opponent_fp):
    source = _source(snapshot, 'CB04-PS-001', owner)
    stored = _card(f'{owner}-stored', owner, code='REVIEW-CB04-STORED', character=BUKUKI)
    engine = _engine(definition, source, {owner: {'passive': [source], 'lumen': [stored]}},
                     fp={owner: owner_fp, _opp(owner): opponent_fp}, phase='recovery',
                     seed=f'cb04-ps001-recovery:{owner}:{owner_fp}:{opponent_fp}')
    engine._fire('phase_start', {'phase': 'recovery'})
    _resolve(engine)
    return {'stored_zone': _zone_of(engine, stored['instance_id'])}


def _run_at012_combo(definition, snapshot, owner, *, combo=True, starter=False, character=BUKUKI):
    source = _source(snapshot, 'CB04-AT-012', owner)
    used = _card(f'{owner}-used', owner, code='REVIEW-CB04-USED', damage=400,
                 hit='콤보' if starter else '0', character=character)
    engine = _engine(definition, source, {owner: {'lumen': [source], 'battle': [used]}},
                     seed=f'cb04-at012:{owner}:{combo}:{starter}:{character}')
    for _ in range(2 if starter else 1):
        if starter:
            _fire(engine, 'combo', used, combo_judgment=True, combo_number=1)
        else:
            _fire(engine, 'use', used, combo=combo)
    return {'damage_delta': _damage_delta(engine, used, owner)}


def _run_at001_play(definition, snapshot, owner, *, hp):
    source = _source(snapshot, 'CB04-AT-001', owner)
    engine = _engine(definition, source, {owner: {'hand': [source]}}, hp={owner: hp},
                     seed=f'cb04-at001-play:{owner}:{hp}')
    return {'use_allowed': bool(engine._card_use_allowed(
        engine._find_card(source['instance_id']), owner, 'ready',
    ))}


def _run_at001_battle(definition, snapshot, owner, *, event='use', negated=False):
    source = _source(snapshot, 'CB04-AT-001', owner, negated=negated)
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY')
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at001:{owner}:{event}:{negated}')
    engine.engine_state['battle'] = {
        owner: {'instance_id': source['instance_id'], 'card': engine._find_card(source['instance_id'])},
        _opp(owner): {'instance_id': enemy['instance_id'], 'card': engine._find_card(enemy['instance_id'])},
    }
    _fire(engine, event, source)
    live_enemy = engine._find_card(enemy['instance_id']) or {}
    return {
        'enemy_negated': bool(live_enemy.get('numbered_effects_negated')),
        'enemy_zone': _zone_of(engine, enemy['instance_id']),
        'opponent_frost': _frost(engine, _opp(owner)),
        'source_zone': _zone_of(engine, source['instance_id']),
    }


def _run_at002_dodge(definition, snapshot, owner, *, stored=True):
    source = _source(snapshot, 'CB04-AT-002', owner)
    lumen = [_card(f'{owner}-unrelated', owner, code='REVIEW-CB04-UNRELATED')]
    if stored:
        lumen.insert(0, _card(f'{owner}-stored', owner, code='REVIEW-CB04-STORED', character=BUKUKI))
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY')
    engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': lumen},
                                          _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at002-dodge:{owner}:{stored}')
    engine._fire('opponent_dodge', {
        'controller': owner, 'source_card': engine._find_card(source['instance_id']),
        'source_card_instance_id': source['instance_id'], 'opponent_card': enemy,
    })
    decision_owner = (engine.engine_state.get('pending_decision') or {}).get('owner')
    _resolve(engine)
    return {
        'opponent_fp': engine.state['players'][_opp(owner)]['fp'],
        'decision_owner': decision_owner,
        'list': _zone_ids(engine, owner, 'list'), 'lumen': _zone_ids(engine, owner, 'lumen'),
    }


def _run_list_to_lumen(definition, snapshot, owner, *, code, events, listed=2):
    source = _source(snapshot, code, owner)
    cards = [_card(f'{owner}-listed-{index}', owner, code=f'REVIEW-CB04-LISTED-{index}', character=BUKUKI)
             for index in range(listed)]
    engine = _engine(definition, source, {owner: {'battle': [source], 'list': cards}},
                     seed=f'cb04-list-lumen:{code}:{owner}:{",".join(events)}:{listed}')
    for event in events:
        _fire(engine, event, source)
    return {'lumen_count': len(engine.state['players'][owner]['zones']['lumen'])}


def _run_on_event(definition, snapshot, owner, *, code, event, negated=False, by_opponent=False,
                  opponent_fp=0, extra=None):
    source = _source(snapshot, code, owner, negated=negated)
    engine = _engine(definition, source, {owner: {'battle': [source]}}, fp={_opp(owner): opponent_fp},
                     seed=f'cb04-event:{code}:{owner}:{event}:{negated}:{by_opponent}:{opponent_fp}')
    context = {
        'controller': _opp(owner) if by_opponent else owner,
        'source_card': engine._find_card(source['instance_id']),
        'source_card_instance_id': source['instance_id'], **(extra or {}),
    }
    engine._fire(event, context)
    _resolve(engine)
    combo_modifiers = [
        item for item in engine.engine_state.get('modifiers') or []
        if item.get('op') == 'modify_combo'
    ]
    return {
        'opponent_frost': _frost(engine, _opp(owner)),
        'opponent_fp': engine.state['players'][_opp(owner)]['fp'],
        'owner_fp': engine.state['players'][owner]['fp'],
        'lumen_combo_rules': [
            (item.get('allow_zones'), (item.get('where') or {}).get('character_key'), item.get('duration'))
            for item in combo_modifiers
        ],
    }


def _run_cmyk_set(definition, snapshot, owner, *, code, role, set_definition=None, set_code=None,
                  set_text='', host_character='cmyk', negated=False):
    """role='host': 리뷰 카드에 세트 카드를 세트. role='set': 리뷰 카드를 다른 호스트에 세트."""
    if role == 'host':
        host = _source(snapshot, code, owner, negated=negated)
        attached = _card(f'{owner}-set', owner, code=set_code or 'REVIEW-CB04-SET', character='cmyk',
                         text=set_text)
        definitions = {attached['code']: set_definition} if set_definition else {}
    else:
        host = _card(f'{owner}-host', owner, code='REVIEW-CB04-HOST', damage=400, character=host_character)
        attached = _source(snapshot, code, owner)
        definitions = {}
    engine = _engine(definition, host if role == 'host' else attached,
                     {owner: {'battle': [host, attached]}}, definitions=definitions,
                     seed=f'cb04-set:{code}:{owner}:{role}:{set_code}:{host_character}:{negated}')
    if set_definition is not None or role == 'set':
        engine.attach_card(attached['instance_id'], host['instance_id'], controller=owner)
    _fire(engine, 'use', host)
    return {
        'owner_fp': engine.state['players'][owner]['fp'],
        'host_damage_delta': _damage_delta(engine, host, owner),
    }


def _run_at035_clash(definition, snapshot, owner, *, attached):
    source = _source(snapshot, 'CB04-AT-035', owner)
    setter = _card(f'{owner}-setter', owner, code='REVIEW-CB04-SETTER', character='cmyk')
    engine = _engine(definition, source, {owner: {'battle': [source, setter]}},
                     seed=f'cb04-at035-clash:{owner}:{attached}')
    if attached:
        engine.attach_card(setter['instance_id'], source['instance_id'], controller=owner)
    _fire(engine, 'before_judgment', source)
    return {'opponent_clash_blocked': _blocked(engine, 'clash', _opp(owner))}


def _run_at035_gain(definition, snapshot, owner, *, events):
    source = _source(snapshot, 'CB04-AT-035', owner)
    listed = [_card(f'{owner}-listed-{index}', owner, code=f'REVIEW-CB04-LISTED-{index}') for index in range(3)]
    engine = _engine(definition, source, {owner: {'battle': [source], 'list': listed}},
                     seed=f'cb04-at035-gain:{owner}:{",".join(events)}')
    for event in events:
        _fire(engine, event, source)
    return {
        'hand_count': len(engine.state['players'][owner]['zones']['hand']),
        'list_count': len(engine.state['players'][owner]['zones']['list']),
    }


def _run_at037_dodge(definition, snapshot, owner, *, attached):
    source = _source(snapshot, 'CB04-AT-037', owner)
    set_cards = [_card(f'{owner}-set-{index}', owner, code=f'REVIEW-CB04-SET-{index}', character='cmyk')
                 for index in range(attached)]
    listed = [_card(f'{owner}-listed-{index}', owner, code=f'REVIEW-CB04-LISTED-{index}') for index in range(3)]
    engine = _engine(definition, source, {owner: {'battle': [source, *set_cards], 'list': listed}},
                     seed=f'cb04-at037:{owner}:{attached}')
    for card in set_cards:
        engine.attach_card(card['instance_id'], source['instance_id'], controller=owner)
    _fire(engine, 'dodge', source)
    return {
        'owner_fp': engine.state['players'][owner]['fp'],
        'hand_count': len(engine.state['players'][owner]['zones']['hand']),
    }


def _run_token(definition, snapshot, owner, *, field):
    value = definition.get(field)
    return {field: copy.deepcopy(value)}


def _run_break_list(definition, snapshot, owner, *, code, event, listed=True, side_bukuki=True):
    source = _source(snapshot, code, owner)
    zones = {'battle': [source], 'list': [], 'side': [
        _card(f'{owner}-side-other', owner, code='REVIEW-CB04-SIDE-OTHER'),
    ]}
    if listed:
        zones['list'].append(_card(f'{owner}-listed', owner, code='REVIEW-CB04-LISTED'))
    if side_bukuki:
        zones['side'].insert(0, _card(f'{owner}-side-bukuki', owner, code='REVIEW-CB04-SIDE-BUKUKI',
                                      character=BUKUKI))
    engine = _engine(definition, source, {owner: zones},
                     seed=f'cb04-break-list:{code}:{owner}:{event}:{listed}:{side_bukuki}')
    _fire(engine, event, source)
    return {
        'break': _zone_ids(engine, owner, 'break'), 'lumen': _zone_ids(engine, owner, 'lumen'),
        'opponent_frost': _frost(engine, _opp(owner)),
    }


def _run_at006_clash(definition, snapshot, owner, *, negated=False):
    source = _source(snapshot, 'CB04-AT-006', owner, negated=negated)
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY', hit='3')
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at006-clash:{owner}:{negated}')
    engine.engine_state['battle'] = {
        owner: {'instance_id': source['instance_id'], 'card': engine._find_card(source['instance_id'])},
        _opp(owner): {'instance_id': enemy['instance_id'], 'card': engine._find_card(enemy['instance_id'])},
    }
    _fire(engine, 'clash', source)
    modified = [
        {key: (event.get('payload') or {}).get(key) for key in ('card_instance_id', 'field', 'after')}
        for event in engine.events
        if event.get('type') == 'judgment_modified'
    ]
    return {'judgment_modified': modified}


def _run_at006_bloom(definition, snapshot, owner, *, by_opponent=False):
    source = _source(snapshot, 'CB04-AT-006', owner)
    engine = _engine(definition, source, {owner: {'lumen': [source]}},
                     seed=f'cb04-at006-bloom:{owner}:{by_opponent}')
    engine._fire('opponent_hit', {'controller': _opp(owner) if by_opponent else owner})
    _resolve(engine)
    return {
        'source_zone': _zone_of(engine, source['instance_id']),
        'owner_fp': engine.state['players'][owner]['fp'],
        'shield': sum(item.get('amount', 0) for item in (engine.engine_state.get('shields') or {}).get(owner) or []),
    }


def _run_at021_spirit(definition, snapshot, owner, *, yin_at_trigger, yin_after_removal):
    source = _source(snapshot, 'CB04-AT-021', owner)
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), frame=7)
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at021:{owner}:{yin_at_trigger}:{yin_after_removal}')
    engine.change_counter(owner, 'yang', 1)
    engine.set_passive(owner, 'yin', value=yin_at_trigger)
    engine._fire('before_judgment', {
        'controller': owner, 'source_card': engine._find_card(source['instance_id']),
        'source_card_instance_id': source['instance_id'],
        'controller_speed': source.get('frame'), 'opponent_speed': 7,
    })
    decision = engine.engine_state.get('pending_decision') or {}
    engine.set_passive(owner, 'yin', value=yin_after_removal)
    if decision:
        engine._submit_decision(owner, decision['id'], ['1'])
        engine._continue()
    _resolve(engine)
    passive = engine.state['players'][owner]['passive_state']
    return {
        'yang_count': (passive.get('yang') or {}).get('count'),
        'yin_count': (passive.get('yin') or {}).get('count'),
        'speed_fixed': sum(item.get('op') == 'fix_speed' for item in engine.engine_state.get('modifiers') or []),
    }


def _run_harmony_hit(definition, snapshot, owner, *, code, harmony=True):
    source = _source(snapshot, code, owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}},
                     seed=f'cb04-harmony:{code}:{owner}:{harmony}')
    if harmony:
        engine.set_passive(owner, 'harmony', value=True)
    _fire(engine, 'hit', source)
    return {'damage_delta': _damage_delta(engine, source, owner)}


def _run_at022_fp(definition, snapshot, owner, *, yang_state, yang_after=None):
    source = _source(snapshot, 'CB04-AT-022', owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}},
                     seed=f'cb04-at022-fp:{owner}:{yang_state}:{yang_after}')
    engine.change_counter(owner, 'yang', 3)
    engine.state['players'][owner]['passive_state']['yang']['value'] = yang_state
    engine.resolver.collect('before_judgment', {
        'controller': owner, 'source_card': engine._find_card(source['instance_id']),
        'source_card_instance_id': source['instance_id'],
    })
    if yang_after is not None:
        engine.state['players'][owner]['passive_state']['yang']['value'] = yang_after
    engine.resolver.drain()
    _resolve(engine)
    return {'owner_fp': engine.state['players'][owner]['fp']}


def _run_at022_combo_end(definition, snapshot, owner, *, in_combo=True):
    source = _source(snapshot, 'CB04-AT-022', owner)
    partner = _card(f'{owner}-partner', owner, code='REVIEW-CB04-PARTNER')
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY')
    engine = _engine(definition, source, {owner: {'battle': [source, partner]},
                                          _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at022-combo-end:{owner}:{in_combo}')
    combo_ids = [partner['instance_id']] + ([source['instance_id']] if in_combo else [])
    engine._fire('combo_end', {
        'controller': owner, 'combo_owner': owner,
        'source_card_instance_id': partner['instance_id'],
        'source_card': engine._find_card(partner['instance_id']),
        'combo_card_instance_ids': combo_ids,
    })
    _resolve(engine)
    return {
        'hand': _zone_ids(engine, owner, 'hand'),
        'enemy_zone': _zone_of(engine, enemy['instance_id']),
    }


def _run_at010_fp(definition, snapshot, owner, *, effect_owner, card_type, target):
    source = _source(snapshot, 'CB04-AT-010', owner)
    effect_card = _card(f'{effect_owner}-effect-card', effect_owner, code='REVIEW-CB04-EFFECT-CARD',
                        type_=card_type)
    engine = _engine(definition, source, {owner: {'lumen': [source]},
                                          effect_owner if effect_owner != owner else _opp(owner): {}},
                     seed=f'cb04-at010-fp:{owner}:{effect_owner}:{card_type}:{target}')
    engine._refresh_continuous_rules()
    engine.resolver.execute_effect(
        {'op': 'change_fp', 'player': {target: True}, 'amount': 2},
        {'controller': effect_owner, 'opponent': _opp(effect_owner),
         'source_card': effect_card, 'source_card_instance_id': effect_card['instance_id']},
    )
    return {'opponent_fp': engine.state['players'][_opp(owner)]['fp']}


def _run_at010_clash(definition, snapshot, owner, *, by_opponent=False):
    source = _source(snapshot, 'CB04-AT-010', owner)
    engine = _engine(definition, source, {owner: {'list': [source]}},
                     seed=f'cb04-at010-clash:{owner}:{by_opponent}')
    engine._fire('clash', {'controller': _opp(owner) if by_opponent else owner})
    _resolve(engine)
    return {'source_zone': _zone_of(engine, source['instance_id'])}


def _run_at013(definition, snapshot, owner, *, damage_received):
    source = _source(snapshot, 'CB04-AT-013', owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}}, fp={_opp(owner): 10},
                     seed=f'cb04-at013:{owner}:{damage_received}')
    _fire(engine, 'after_judgment', source, controller_damage_received=damage_received)
    return {'opponent_fp': engine.state['players'][_opp(owner)]['fp'],
            'opponent_frost': _frost(engine, _opp(owner))}


def _run_at030_restriction(definition, snapshot, owner, *, body):
    source = _source(snapshot, 'CB04-AT-030', owner)
    attacker = _card(f'{_opp(owner)}-attacker', _opp(owner), code='REVIEW-CB04-ATTACKER')
    attacker['body'] = body
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [attacker]}},
                     seed=f'cb04-at030-restriction:{owner}:{body}')
    engine._refresh_continuous_rules()
    live = engine._find_card(source['instance_id'])
    return {
        'clash_blocked': bool(engine._rule_blocked('clash', owner, live, attacker)),
        'clash_rule_allowed': bool(engine._defense_judgment_allowed(live, attacker, 'clash', _opp(owner))),
    }


def _run_at030_clash(definition, snapshot, owner, *, oni_flash):
    source = _source(snapshot, 'CB04-AT-030', owner)
    flashes = [_card(f'{owner}-oni-flash-{index}', owner, code='RFS-AT-002', character='muyoung')
               for index in range(oni_flash)]
    other = _card(f'{owner}-other-lumen', owner, code='REVIEW-CB04-OTHER-LUMEN')
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY', hit='4')
    engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': [*flashes, other]},
                                          _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at030-clash:{owner}:{oni_flash}')
    engine.engine_state['battle'] = {
        owner: {'instance_id': source['instance_id'], 'card': engine._find_card(source['instance_id'])},
        _opp(owner): {'instance_id': enemy['instance_id'], 'card': engine._find_card(enemy['instance_id'])},
    }
    _fire(engine, 'clash', source)
    return {
        'owner_fp': engine.state['players'][owner]['fp'],
        'shield': sum(item.get('amount', 0) for item in (engine.engine_state.get('shields') or {}).get(owner) or []),
        'judgment_modified': [
            {key: (event.get('payload') or {}).get(key) for key in ('card_instance_id', 'field', 'after')}
            for event in engine.events if event.get('type') == 'judgment_modified'
        ],
    }


def _run_at032_combo(definition, snapshot, owner, *, combo_number):
    source = _source(snapshot, 'CB04-AT-032', owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}},
                     seed=f'cb04-at032:{owner}:{combo_number}')
    _fire(engine, 'combo', source, combo_number=combo_number)
    fp_before_recovery = engine.state['players'][owner]['fp']
    engine.state['phase'] = 'recovery'
    engine._fire('phase_start', {'phase': 'recovery'})
    _resolve(engine)
    return {'fp_before_recovery': fp_before_recovery, 'owner_fp': engine.state['players'][owner]['fp']}


def _oni_flashes(owner, count):
    return [_card(f'{owner}-oni-flash-{index}', owner, code='RFS-AT-002', character='muyoung')
            for index in range(count)]


def _run_at031_combo(definition, snapshot, owner, *, oni_flash):
    source = _source(snapshot, 'CB04-AT-031', owner)
    engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': _oni_flashes(owner, oni_flash)}},
                     seed=f'cb04-at031-combo:{owner}:{oni_flash}')
    _fire(engine, 'combo', source)
    return {'damage_delta': _damage_delta(engine, source, owner)}


def _run_at031_recovery(definition, snapshot, owner, *, oni_flash, blue_flame=True):
    source = _source(snapshot, 'CB04-AT-031', owner)
    listed = _card(f'{owner}-listed', owner, code='REVIEW-CB04-LISTED')
    engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': _oni_flashes(owner, oni_flash),
                                                  'list': [listed]}},
                     seed=f'cb04-at031-recovery:{owner}:{oni_flash}:{blue_flame}')
    if blue_flame:
        engine.set_passive(owner, 'blue_flame', value=True)
    _fire(engine, 'after_use', source)
    hand_before_recovery = _zone_ids(engine, owner, 'hand')
    engine.state['phase'] = 'recovery'
    engine._fire('phase_start', {'phase': 'recovery'})
    _resolve(engine)
    side = engine.state['players'][owner]['zones']['side']
    return {
        'hand_before_recovery': hand_before_recovery,
        'side_oni_flash': sum(card.get('code') == 'RFS-AT-002' for card in side),
        'hand': _zone_ids(engine, owner, 'hand'),
    }


def _arm_parts(owner, count):
    names = ['R ARM: 검토 파츠', 'L ARM: 검토 파츠', 'LEG: 검토 파츠']
    cards = []
    for index in range(count):
        card = _card(f'{owner}-part-{index}', owner, code=f'REVIEW-CB04-PART-{index}', type_='특수',
                     character='pinp')
        card['name'] = names[index]
        card['token_key'] = 'parts'
        cards.append(card)
    return cards


def _run_at033(definition, snapshot, owner, *, arm):
    parts = _arm_parts(owner, arm) + ([] if arm >= 2 else _arm_parts(owner, 3)[2:])
    source = _source(snapshot, 'CB04-AT-033', owner)
    battle_engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': parts}},
                            seed=f'cb04-at033-battle:{owner}:{arm}')
    battle_engine._refresh_continuous_rules()
    hand_engine = _engine(definition, source, {owner: {'hand': [source], 'lumen': parts}},
                          seed=f'cb04-at033-catch:{owner}:{arm}')
    catch = {'owner': owner, 'source': 'fp', 'allow_zones': ['hand'], 'max_speed': 12}
    return {
        'opponent_dodge_blocked': _blocked(battle_engine, 'dodge', _opp(owner)),
        'catch_speeds': [
            option.get('fixed_speed') for option in hand_engine._legal_catch_options(owner, catch)
            if (option.get('card') or {}).get('instance_id') == source['instance_id']
        ],
    }


def _run_at034_limit(definition, snapshot, owner, *, existing):
    source = _source(snapshot, 'CB04-AT-034', owner)
    source['token_key'] = 'parts'
    lumen = []
    if existing:
        other = _card(f'{owner}-existing', owner, code='REVIEW-CB04-EXISTING-PART', type_='특수')
        other['name'] = existing
        other['token_key'] = 'parts'
        lumen.append(other)
    engine = _engine(definition, source, {owner: {'hand': [source], 'lumen': lumen}},
                     seed=f'cb04-at034-limit:{owner}:{existing}')
    return {'lumen_allowed': bool(engine._zone_limit_allows(
        engine._find_card(source['instance_id']), owner, 'lumen',
    ))}


def _run_at034_combo(definition, snapshot, owner, *, combos=1, by_opponent=False):
    source = _source(snapshot, 'CB04-AT-034', owner)
    source['token_key'] = 'parts'
    actor = _opp(owner) if by_opponent else owner
    combo_card = _card(f'{actor}-combo', actor, code='REVIEW-CB04-COMBO', character='pinp')
    hand = [_card(f'{owner}-hand-{index}', owner, code=f'REVIEW-CB04-HAND-{index}') for index in range(2)]
    zones = {owner: {'lumen': [source], 'hand': hand}}
    zones.setdefault(actor, {}).setdefault('battle', []).append(combo_card)
    engine = _engine(definition, source, zones, seed=f'cb04-at034-combo:{owner}:{combos}:{by_opponent}')
    for _ in range(combos):
        _fire(engine, 'combo', combo_card)
    modifiers = [
        (bool(item.get('ignore_speed')), (item.get('where') or {}).get('character_key'))
        for item in engine.engine_state.get('modifiers') or []
        if item.get('op') == 'modify_combo' and item.get('player') == owner
    ]
    return {
        'hand_count': len(engine.state['players'][owner]['zones']['hand']),
        'combo_rules': modifiers,
        'recovery_skipped': bool(((engine.engine_state.get('skip_phases') or {}).get(owner) or {}).get('recovery')),
    }


def _run_at034_recovery(definition, snapshot, owner, *, use=True):
    # Q-AUTO-022: 자신의 리커버리 처리만 건너뛴다. 같은 턴 자신의 '리커버리 페이즈 시' 예약 효과
    # (지거 임팩트 4FP 등)는 불발되고, 상대의 리커버리와 예약 효과는 그대로 처리된다.
    source = _source(snapshot, 'CB04-AT-034', owner)
    source['token_key'] = 'parts'
    combo_card = _card(f'{owner}-combo', owner, code='REVIEW-CB04-COMBO', character='pinp')
    hand = [_card(f'{owner}-hand-0', owner, code='REVIEW-CB04-HAND-0')]
    engine = _engine(definition, source, {owner: {'lumen': [source], 'hand': hand, 'battle': [combo_card]}},
                     seed=f'cb04-at034-recovery:{owner}:{use}', fp={'p1': -3, 'p2': -3})
    if use:
        _fire(engine, 'combo', combo_card)
    for side in ('p1', 'p2'):
        engine.resolver.execute_effect({
            'op': 'schedule', 'when': {'event': 'phase_start', 'phase': 'recovery'}, 'duration': 'turn',
            'effect': {'op': 'change_fp', 'player': {'controller': True}, 'amount': 4},
        }, {'controller': side, 'source_card_instance_id': f'{side}-review-schedule'})
    engine.state['phase'] = 'get'
    engine.engine_state['step'] = 'phase_actions'
    engine._advance_phase('recovery')
    _resolve(engine)
    return {
        'phase': engine.state.get('phase'),
        'own_fp': engine.state['players'][owner]['fp'],
        'opponent_fp': engine.state['players'][_opp(owner)]['fp'],
        'own_passed': owner in (engine.engine_state.get('phase_passes') or []),
    }


def _ember(engine, side):
    return int((engine.state['players'][side]['passive_state'].get('ember') or {}).get('count') or 0)


def _combo_rule_summary(engine, owner, source):
    live = engine._find_card(source['instance_id'])
    combo = {'owner': owner, 'used': [], 'last_speed': 5}
    rules = engine._combo_rules(owner, live, combo)
    return live, rules, sorted({speed for rule in rules for speed in (rule.get('speed_options') or [])})


def _rin_trait(owner):
    from .drafts import build_effect_draft

    text = '자신의 <[[character:rin]]> 기술이 브레이크될 때마다 [[token:ember]]카운터 1개를 얻는다.'
    trait = _card(f'{owner}-rin-trait', owner, code='CRS-PS-001', type_='특성', character='rin', text=text)
    return trait, build_effect_draft('CRS-PS-001', text)


def _run_at024_combo(definition, snapshot, owner, *, speed, trait=False):
    source = _source(snapshot, 'CB04-AT-024', owner)
    zones = {owner: {'battle': [source]}}
    definitions = {}
    if trait:
        trait_card, trait_definition = _rin_trait(owner)
        zones[owner]['passive'] = [trait_card]
        definitions['CRS-PS-001'] = trait_definition
    engine = _engine(definition, source, zones, definitions=definitions,
                     seed=f'cb04-at024-combo:{owner}:{speed}:{trait}')
    _live, rules, speeds = _combo_rule_summary(engine, owner, source)
    _fire(engine, 'combo', source, combo_speed=speed)
    return {
        'combo_speeds': speeds,
        'zone_after_combo': _zone_of(engine, source['instance_id']),
        'breaks_after_use': any(engine._combo_rule_breaks_after_use(rule, speed) for rule in rules),
        'ember': _ember(engine, owner),
    }


def _run_at024_grab(definition, snapshot, owner, *, opponent_grab=False):
    source = _source(snapshot, 'CB04-AT-024', owner)
    rival = _card(f'{_opp(owner)}-grab', _opp(owner), code='REVIEW-CB04-RIVAL-GRAB', special='그랩')
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [rival]}},
                     seed=f'cb04-at024-grab:{owner}:{opponent_grab}')
    _fire(engine, 'grab_negated', rival if opponent_grab else source, source_zone='battle')
    return {'ember': _ember(engine, owner), 'opponent_ember': _ember(engine, _opp(owner))}


def _spider_tokens(owner, count):
    tokens = []
    for index in range(count):
        token = _card(f'{owner}-spider-{index}', owner, code='PMP-AT-053', type_='토큰', character='ezebel')
        token['token_key'] = 'spider'
        tokens.append(token)
    return tokens


def _run_at027_hit(definition, snapshot, owner, *, spiders, event='hit'):
    source = _source(snapshot, 'CB04-AT-027', owner)
    rival = _opp(owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}, rival: {'list': _spider_tokens(owner, spiders)}},
                     seed=f'cb04-at027-hit:{owner}:{spiders}:{event}')
    hp_before = engine.state['players'][rival]['hp']
    _fire(engine, event, source)
    zones = engine.state['players']
    return {
        'own_lumen_spiders': sum(card.get('token_key') == 'spider' for card in zones[owner]['zones']['lumen']),
        'rival_list_spiders': sum(card.get('token_key') == 'spider' for card in zones[rival]['zones']['list']),
        'rival_hp_delta': zones[rival]['hp'] - hp_before,
    }


def _run_at027_combo(definition, snapshot, owner):
    source = _source(snapshot, 'CB04-AT-027', owner)
    engine = _engine(definition, source, {owner: {'battle': [source]}}, seed=f'cb04-at027-combo:{owner}')
    _live, _rules, speeds = _combo_rule_summary(engine, owner, source)
    return {'combo_speeds': speeds}


def _run_at034_n1(definition, snapshot, owner, *, recovery=False, **kwargs):
    runner = _run_at034_recovery if recovery else _run_at034_combo
    return runner(definition, snapshot, owner, **kwargs)


# --- 능력별 시나리오 표 -----------------------------------------------------------

# --- CB04 추가 공개분(2026-11-21): 부쿠키 ------------------------------------------

def _battle_pair(engine, source, enemy):
    engine.engine_state['battle'] = {
        source['owner']: {'instance_id': source['instance_id'],
                          'card': engine._find_card(source['instance_id'])},
        enemy['owner']: {'instance_id': enemy['instance_id'], 'card': engine._find_card(enemy['instance_id'])},
    }


def _judgment_changes(engine):
    return [
        {key: (event.get('payload') or {}).get(key) for key in ('card_instance_id', 'field', 'after')}
        for event in engine.events if event.get('type') == 'judgment_modified'
    ]


def _run_at005_before(definition, snapshot, owner, *, bukuki, others=0):
    source = _source(snapshot, 'CB04-AT-005', owner)
    lumen = [_card(f'{owner}-bukuki-{index}', owner, code=f'REVIEW-CB04-BUKUKI-{index}', character=BUKUKI)
             for index in range(bukuki)]
    lumen += [_card(f'{owner}-other-{index}', owner, code=f'REVIEW-CB04-OTHER-{index}', character='rin')
              for index in range(others)]
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY')
    engine = _engine(definition, source, {owner: {'battle': [source], 'lumen': lumen},
                                          _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at005:{owner}:{bukuki}:{others}')
    _battle_pair(engine, source, enemy)
    _fire(engine, 'before_judgment', source, opponent_card=engine._find_card(enemy['instance_id']))
    live = engine._find_card(source['instance_id'])
    return {'hit': live.get('hit'), 'counter': live.get('counter'), 'judgment_modified': _judgment_changes(engine)}


def _run_at008_restriction(definition, snapshot, owner, *, body):
    source = _source(snapshot, 'CB04-AT-008', owner)
    attacker = _card(f'{_opp(owner)}-attacker', _opp(owner), code='REVIEW-CB04-ATTACKER')
    attacker['body'] = body
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [attacker]}},
                     seed=f'cb04-at008-restriction:{owner}:{body}')
    return {'clash_allowed': bool(engine._defense_judgment_allowed(
        engine._find_card(source['instance_id']), attacker, 'clash', _opp(owner),
    ))}


def _run_at008_before(definition, snapshot, owner, *, damage, enemy_type='공격'):
    source = _source(snapshot, 'CB04-AT-008', owner)
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY', type_=enemy_type, damage=damage)
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at008-before:{owner}:{damage}:{enemy_type}')
    _battle_pair(engine, source, enemy)
    live_enemy = engine._find_card(enemy['instance_id'])
    _fire(engine, 'before_judgment', source, opponent_card=live_enemy,
          opponent_damage=engine.card_stat(live_enemy, 'damage', _opp(owner), include_fp=False)
          if enemy_type == '공격' else None)
    printed = [item for item in str(source.get('special') or '').split(' · ') if item]
    special = [item for item in str(engine._find_card(source['instance_id']).get('special') or '').split(' · ')
               if item]
    return {'mid_clash_added': '중단 상쇄' in special and '중단 상쇄' not in printed,
            'printed_kept': special[:len(printed)] == printed}


def _run_at008_clash(definition, snapshot, owner, *, negated=False):
    source = _source(snapshot, 'CB04-AT-008', owner, negated=negated)
    enemy = _card(f'{_opp(owner)}-enemy', _opp(owner), code='REVIEW-CB04-ENEMY', hit='3')
    engine = _engine(definition, source, {owner: {'battle': [source]}, _opp(owner): {'battle': [enemy]}},
                     seed=f'cb04-at008-clash:{owner}:{negated}')
    _battle_pair(engine, source, enemy)
    _fire(engine, 'clash', source)
    return {'judgment_modified': _judgment_changes(engine), 'source_zone': _zone_of(engine, source['instance_id'])}


def _run_at009(definition, snapshot, owner, *, zone='lumen', frost=True):
    source = _source(snapshot, 'CB04-AT-009', owner)
    engine = _engine(definition, source, {owner: {zone: [source]}},
                     seed=f'cb04-at009:{owner}:{zone}:{frost}')
    if frost:
        engine.set_passive(_opp(owner), 'frost', value=True)
    engine._refresh_continuous_rules()
    return {
        'opponent_catch_blocked': bool(engine._rule_blocked('catch', _opp(owner))),
        'owner_catch_blocked': bool(engine._rule_blocked('catch', owner)),
    }


# --- CB04 추가 공개분(2026-11-25): 세츠메이 ----------------------------------------

def _run_at040_catch(definition, snapshot, owner, *, negated=False, by_opponent=False, fixed_speed=7):
    source = _source(snapshot, 'CB04-AT-040', owner, negated=negated)
    engine = _engine(definition, source, {owner: {'battle': [source]}},
                     seed=f'cb04-at040-catch:{owner}:{negated}:{by_opponent}:{fixed_speed}')
    speed = {'fixed_speed': fixed_speed} if fixed_speed is not None else {}
    if by_opponent:
        enemy = _card(f'{_opp(owner)}-catcher', _opp(owner), code='REVIEW-CB04-CATCHER')
        engine.state['players'][_opp(owner)]['zones']['battle'].append(copy.deepcopy(enemy))
        _fire(engine, 'catch', enemy, **speed)
    else:
        _fire(engine, 'catch', source, **speed)
    return {
        'owner_catch_blocked': bool(engine._rule_blocked('catch', owner)),
        'opponent_catch_blocked': bool(engine._rule_blocked('catch', _opp(owner))),
    }


def _run_at040_hit(definition, snapshot, owner, *, negated=False, turns=0, move_special=False):
    source = _source(snapshot, 'CB04-AT-040', owner, negated=negated)
    other = _opp(owner)
    special = _card(f'{other}-special', other, code='REVIEW-CB04-SPECIAL', type_='특수')
    attack = _card(f'{other}-attack', other, code='REVIEW-CB04-ATTACK')
    own_special = _card(f'{owner}-special', owner, code='REVIEW-CB04-OWN-SPECIAL', type_='특수')
    engine = _engine(definition, source, {
        owner: {'battle': [source], 'lumen': [own_special]},
        other: {'lumen': [special], 'hand': [attack]},
    }, seed=f'cb04-at040-hit:{owner}:{negated}:{turns}:{move_special}')
    _fire(engine, 'hit', source)
    if move_special:
        engine.move_card(special['instance_id'], 'list')
    for _ in range(turns):
        engine.state['turn'] = int(engine.state.get('turn') or 1) + 1
        engine._expire_modifiers('turn')

    def negated_flag(instance_id):
        return bool((engine._find_card(instance_id) or {}).get('numbered_effects_negated'))

    return {
        'opponent_special_negated': negated_flag(special['instance_id']),
        'opponent_attack_negated': negated_flag(attack['instance_id']),
        'owner_special_negated': negated_flag(own_special['instance_id']),
    }


# 자기 효과로 13속도로 사용할 수 있는 기술(인쇄 속도 9)과 다른 속도만 고를 수 있는 기술.
SPEED_13_OPTION = {
    'schema_version': 1, 'reviewed': True, 'no_effect': False,
    'source_refs': {'rulebook_pages': [], 'qna_ids': []},
    'combo_rules': [{'speed_options': [13], 'numbered_effect': True}],
    'abilities': [{
        'id': 'review-cb04-speed-13-n1', 'kind': 'effect', 'mode': 'continuous',
        'timing': 'combo', 'visibility': 'public', 'draft_compiled': True,
        'effects': [{'op': 'static_rule', 'rules': ['combo_rules']}],
    }],
}
SPEED_10_OPTION = copy.deepcopy(SPEED_13_OPTION)
SPEED_10_OPTION['combo_rules'][0]['speed_options'] = [10]


def _run_at041_combo(definition, snapshot, owner, *, negated=False, after_other=False):
    source = _source(snapshot, 'CB04-AT-041', owner, negated=negated)
    listed = {
        frame: _card(f'{owner}-list-{frame}', owner, code=f'REVIEW-CB04-LIST-{frame}', frame=frame)
        for frame in (12, 13, 14)
    }
    listed['9-to-13'] = _card(f'{owner}-list-9-to-13', owner, code='REVIEW-CB04-LIST-9-TO-13', frame=9)
    listed['9-to-10'] = _card(f'{owner}-list-9-to-10', owner, code='REVIEW-CB04-LIST-9-TO-10', frame=9)
    bridge = _card(f'{owner}-bridge', owner, code='REVIEW-CB04-BRIDGE', frame=12)
    engine = _engine(definition, source, {
        owner: {'battle': [source, bridge], 'list': list(listed.values())},
    }, seed=f'cb04-at041-combo:{owner}:{negated}:{after_other}', definitions={
        'REVIEW-CB04-LIST-9-TO-13': SPEED_13_OPTION, 'REVIEW-CB04-LIST-9-TO-10': SPEED_10_OPTION,
    })
    _fire(engine, 'combo', source, combo=True)
    live = engine._find_card(source['instance_id'])
    used = [source['instance_id'], bridge['instance_id']] if after_other else [source['instance_id']]
    combo = {'owner': owner, 'source': source['instance_id'], 'used': used, 'last_speed': 12}
    own_rules = engine._combo_rules(owner, live, {'owner': owner, 'used': [], 'last_speed': 11})
    return {
        'ignore_damage_penalty': any(rule.get('ignore_damage_penalty') for rule in own_rules),
        'damage_bonus': sum(int(rule.get('damage_bonus') or 0) for rule in own_rules),
        'list_frames_allowed': [
            frame for frame, card in listed.items()
            if engine._combo_zone_allowed(owner, engine._find_card(card['instance_id']), 'list', combo)
        ],
    }


def _cases():
    frost_ok = {'opponent_frost': True}
    return {
        'cb04-at-040-n1': (_run_at040_catch, (
            ('owner-p1-speed-7-catch-blocks-further-own-catches', 'p1', {},
             {'owner_catch_blocked': True, 'opponent_catch_blocked': False}),
            ('owner-p2-speed-7-catch-blocks-further-own-catches', 'p2', {},
             {'owner_catch_blocked': True, 'opponent_catch_blocked': False}),
            ('qa-auto-027-printed-speed-catch-blocks-nothing', 'p1', {'fixed_speed': None},
             {'owner_catch_blocked': False, 'opponent_catch_blocked': False}),
            ('opponent-catch-does-not-trigger', 'p1', {'by_opponent': True},
             {'owner_catch_blocked': False, 'opponent_catch_blocked': False}),
            ('negated-source-blocks-nothing', 'p2', {'negated': True},
             {'owner_catch_blocked': False, 'opponent_catch_blocked': False}),
        )),
        'cb04-at-040-n2': (_run_at040_hit, (
            ('owner-p1-hit-locks-opponent-special-effects', 'p1', {},
             {'opponent_special_negated': True, 'opponent_attack_negated': False,
              'owner_special_negated': False}),
            ('owner-p2-hit-locks-opponent-special-effects', 'p2', {},
             {'opponent_special_negated': True, 'opponent_attack_negated': False,
              'owner_special_negated': False}),
            ('lock-follows-moved-special-technique', 'p1', {'move_special': True},
             {'opponent_special_negated': True}),
            ('lock-lasts-through-next-turn', 'p2', {'turns': 1},
             {'opponent_special_negated': True}),
            ('lock-ends-after-next-turn', 'p1', {'turns': 2},
             {'opponent_special_negated': False, 'opponent_attack_negated': False}),
            ('negated-source-locks-nothing', 'p2', {'negated': True},
             {'opponent_special_negated': False}),
        )),
        'cb04-at-041-n1': (_run_at041_combo, (
            ('owner-p1-combo-ignores-scaling-and-links-list-13-speed', 'p1', {},
             {'ignore_damage_penalty': True, 'damage_bonus': -500, 'list_frames_allowed': [13, '9-to-13']}),
            ('owner-p2-combo-ignores-scaling-and-links-list-13-speed', 'p2', {},
             {'ignore_damage_penalty': True, 'damage_bonus': -500, 'list_frames_allowed': [13, '9-to-13']}),
            ('list-link-only-right-after-this-technique', 'p1', {'after_other': True},
             {'list_frames_allowed': []}),
            ('negated-source-changes-nothing', 'p2', {'negated': True},
             {'ignore_damage_penalty': False, 'damage_bonus': 0, 'list_frames_allowed': []}),
        )),
        'cb04-at-005-n1': (_run_at005_before, (
            ('owner-p1-three-bukuki-changes-hit-and-counter-to-combo', 'p1', {'bukuki': 3},
             {'hit': '콤보', 'counter': '콤보'}),
            ('owner-p2-four-bukuki-changes-hit-and-counter-to-combo', 'p2', {'bukuki': 4},
             {'hit': '콤보', 'counter': '콤보'}),
            ('two-bukuki-and-other-techniques-change-nothing', 'p1', {'bukuki': 2, 'others': 2},
             {'judgment_modified': []}),
        )),
        'cb04-at-005-n2': (_run_on_event, (
            ('owner-p1-combo-allows-lumen-bukuki', 'p1', {'code': 'CB04-AT-005', 'event': 'combo'},
             {'lumen_combo_rules': [(['lumen'], BUKUKI, 'turn')]}),
            ('owner-p2-combo-allows-lumen-bukuki', 'p2', {'code': 'CB04-AT-005', 'event': 'combo'},
             {'lumen_combo_rules': [(['lumen'], BUKUKI, 'turn')]}),
            ('negated-source-adds-no-combo-rule', 'p1',
             {'code': 'CB04-AT-005', 'event': 'combo', 'negated': True}, {'lumen_combo_rules': []}),
        )),
        'cb04-at-008-function': (_run_at008_restriction, (
            ('owner-p1-clashes-hand-technique', 'p1', {'body': '손'}, {'clash_allowed': True}),
            ('owner-p2-clashes-foot-technique', 'p2', {'body': '발'}, {'clash_allowed': True}),
            ('technique-without-hand-or-foot-cannot-be-clashed', 'p1', {'body': ''}, {'clash_allowed': False}),
            ('echo-technique-cannot-be-clashed', 'p2', {'body': '잔향'}, {'clash_allowed': False}),
        )),
        'cb04-at-008-n1': (_run_at008_before, (
            ('owner-p1-500-damage-attack-adds-mid-clash', 'p1', {'damage': 500},
             {'mid_clash_added': True, 'printed_kept': True}),
            ('owner-p2-700-damage-attack-adds-mid-clash', 'p2', {'damage': 700},
             {'mid_clash_added': True, 'printed_kept': True}),
            ('400-damage-attack-adds-nothing', 'p1', {'damage': 400},
             {'mid_clash_added': False, 'printed_kept': True}),
            ('defense-technique-adds-nothing', 'p2', {'damage': 600, 'enemy_type': '수비'},
             {'mid_clash_added': False, 'printed_kept': True}),
        )),
        'cb04-at-008-n2': (_run_at008_clash, (
            ('owner-p1-clash-sets-opponent-hit-plus-0-and-breaks', 'p1', {},
             {'judgment_modified': [{'card_instance_id': 'p2-enemy', 'field': 'hit', 'after': '+0'}],
              'source_zone': 'break'}),
            ('owner-p2-clash-sets-opponent-hit-plus-0-and-breaks', 'p2', {},
             {'judgment_modified': [{'card_instance_id': 'p1-enemy', 'field': 'hit', 'after': '+0'}],
              'source_zone': 'break'}),
            ('negated-source-changes-nothing', 'p1', {'negated': True},
             {'judgment_modified': [], 'source_zone': 'battle'}),
        )),
        'cb04-at-009-n1': (_run_at009, (
            ('owner-p1-lumen-and-opponent-frost-blocks-opponent-catch', 'p1', {},
             {'opponent_catch_blocked': True, 'owner_catch_blocked': False}),
            ('owner-p2-lumen-and-opponent-frost-blocks-opponent-catch', 'p2', {},
             {'opponent_catch_blocked': True, 'owner_catch_blocked': False}),
            ('no-frost-allows-catch', 'p1', {'frost': False}, {'opponent_catch_blocked': False}),
            ('outside-lumen-zone-allows-catch', 'p2', {'zone': 'battle'}, {'opponent_catch_blocked': False}),
        )),
        'cb04-at-024-n1': (_run_at024_combo, (
            ('owner-p1-speed-7-breaks-on-combo-and-gains-three-ember', 'p1', {'speed': 7},
             {'combo_speeds': [6, 7, 8], 'zone_after_combo': 'break', 'breaks_after_use': False, 'ember': 3}),
            ('owner-p2-speed-8-with-trait-gains-four-ember', 'p2', {'speed': 8, 'trait': True},
             {'zone_after_combo': 'break', 'ember': 4}),
            ('owner-p1-speed-6-with-trait-gains-four-ember', 'p1', {'speed': 6, 'trait': True},
             {'zone_after_combo': 'break', 'ember': 4}),
            ('printed-speed-12-keeps-card-and-gains-nothing', 'p1', {'speed': 12, 'trait': True},
             {'zone_after_combo': 'battle', 'breaks_after_use': False, 'ember': 0}),
        )),
        'cb04-at-024-n2': (_run_at024_grab, (
            ('owner-p1-grab-negated-gains-one-ember', 'p1', {}, {'ember': 1, 'opponent_ember': 0}),
            ('owner-p2-grab-negated-gains-one-ember', 'p2', {}, {'ember': 1, 'opponent_ember': 0}),
            ('opponent-grab-negated-does-not-trigger', 'p1', {'opponent_grab': True},
             {'ember': 0, 'opponent_ember': 0}),
        )),
        'cb04-at-027-n1': (_run_at027_hit, (
            ('owner-p1-hit-moves-three-spiders-and-deals-600', 'p1', {'spiders': 3},
             {'own_lumen_spiders': 3, 'rival_list_spiders': 0, 'rival_hp_delta': -600}),
            ('owner-p2-combo-moves-two-spiders-and-deals-400', 'p2', {'spiders': 2, 'event': 'combo'},
             {'own_lumen_spiders': 2, 'rival_list_spiders': 0, 'rival_hp_delta': -400}),
            ('owner-p1-counter-moves-four-spiders-and-deals-800', 'p1', {'spiders': 4, 'event': 'counter'},
             {'own_lumen_spiders': 4, 'rival_list_spiders': 0, 'rival_hp_delta': -800}),
            ('no-spider-in-rival-list-does-nothing', 'p2', {'spiders': 0},
             {'own_lumen_spiders': 0, 'rival_hp_delta': 0}),
        )),
        'cb04-at-027-n2': (_run_at027_combo, (
            ('owner-p1-can-combo-at-speed-9', 'p1', {}, {'combo_speeds': [9]}),
            ('owner-p2-can-combo-at-speed-9', 'p2', {}, {'combo_speeds': [9]}),
            ('combo-rule-has-only-speed-9', 'p1', {}, {'combo_speeds': [9]}),
        )),
        'cb04-at-031-n1': (_run_at031_combo, (
            ('owner-p1-three-oni-flash-adds-300', 'p1', {'oni_flash': 3}, {'damage_delta': 300}),
            ('owner-p2-two-oni-flash-adds-200', 'p2', {'oni_flash': 2}, {'damage_delta': 200}),
            ('no-oni-flash-keeps-damage', 'p1', {'oni_flash': 0}, {'damage_delta': 0}),
        )),
        'cb04-at-031-n2': (_run_at031_recovery, (
            ('owner-p1-blue-flame-returns-two-and-gains-list', 'p1', {'oni_flash': 2},
             {'hand_before_recovery': [], 'side_oni_flash': 2, 'hand': ['p1-listed']}),
            ('owner-p2-blue-flame-returns-only-two', 'p2', {'oni_flash': 3},
             {'side_oni_flash': 2, 'hand': ['p2-listed']}),
            ('without-blue-flame-does-nothing', 'p1', {'oni_flash': 2, 'blue_flame': False},
             {'side_oni_flash': 0, 'hand': []}),
            ('one-oni-flash-cannot-pay-and-gains-nothing', 'p2', {'oni_flash': 1},
             {'side_oni_flash': 0, 'hand': []}),
        )),
        'cb04-at-033-n1': (_run_at033, (
            ('owner-p1-two-arm-undodgeable-and-speed-9-catch', 'p1', {'arm': 2},
             {'opponent_dodge_blocked': True, 'catch_speeds': [9, None]}),
            ('owner-p2-two-arm-undodgeable-and-speed-9-catch', 'p2', {'arm': 2},
             {'opponent_dodge_blocked': True, 'catch_speeds': [9, None]}),
            ('one-arm-keeps-printed-rules', 'p1', {'arm': 1},
             {'opponent_dodge_blocked': False, 'catch_speeds': [None]}),
        )),
        'cb04-at-034-function': (_run_at034_limit, (
            ('owner-p1-second-option-cannot-enter-lumen', 'p1', {'existing': 'OPTION: 제트팩'},
             {'lumen_allowed': False}),
            ('owner-p2-second-option-cannot-enter-lumen', 'p2', {'existing': 'OPTION: 제트팩'},
             {'lumen_allowed': False}),
            ('arm-part-does-not-block-option', 'p1', {'existing': 'R ARM: 파워 건틀릿'},
             {'lumen_allowed': True}),
        )),
        'cb04-at-034-n1': (_run_at034_n1, (
            ('owner-p1-combo-discards-chains-pinp-and-skips-recovery', 'p1', {},
             {'hand_count': 1, 'combo_rules': [(True, 'pinp')], 'recovery_skipped': True}),
            ('owner-p2-only-once-per-turn', 'p2', {'combos': 2},
             {'hand_count': 1, 'combo_rules': [(True, 'pinp')], 'recovery_skipped': True}),
            ('opponent-combo-does-not-trigger', 'p1', {'by_opponent': True},
             {'hand_count': 2, 'combo_rules': [], 'recovery_skipped': False}),
            # Q-AUTO-023: 리커버리에서 음수 FP를 0으로 되돌리지 않는다(-3 + 리커버리 시 4FP = 1).
            ('owner-p1-skips-only-own-recovery', 'p1', {'recovery': True},
             {'phase': 'recovery', 'own_fp': -3, 'opponent_fp': 1, 'own_passed': True}),
            ('owner-p2-skips-only-own-recovery', 'p2', {'recovery': True},
             {'phase': 'recovery', 'own_fp': -3, 'opponent_fp': 1, 'own_passed': True}),
            ('without-use-both-recover', 'p1', {'recovery': True, 'use': False},
             {'phase': 'recovery', 'own_fp': 1, 'opponent_fp': 1, 'own_passed': False}),
        )),
        'cb04-at-030-function': (_run_at030_restriction, (
            ('owner-p1-cannot-clash-foot-technique', 'p1', {'body': '발'},
             {'clash_blocked': True, 'clash_rule_allowed': False}),
            ('owner-p2-cannot-clash-foot-technique', 'p2', {'body': '발'},
             {'clash_blocked': True, 'clash_rule_allowed': False}),
            ('hand-technique-can-be-clashed', 'p1', {'body': '손'},
             {'clash_blocked': False, 'clash_rule_allowed': True}),
        )),
        'cb04-at-030-n1': (_run_at030_clash, (
            ('owner-p1-three-oni-flash-fp-shield-and-hit-plus-2', 'p1', {'oni_flash': 3},
             {'owner_fp': 3, 'shield': 300,
              'judgment_modified': [{'card_instance_id': 'p2-enemy', 'field': 'hit', 'after': '+2'}]}),
            ('owner-p2-two-oni-flash-fp-and-shield-only', 'p2', {'oni_flash': 2},
             {'owner_fp': 2, 'shield': 200, 'judgment_modified': []}),
            ('no-oni-flash-gains-nothing', 'p1', {'oni_flash': 0},
             {'owner_fp': 0, 'shield': 0, 'judgment_modified': []}),
        )),
        'cb04-at-032-n1': (_run_at032_combo, (
            ('owner-p1-fourth-combo-gains-4-at-recovery', 'p1', {'combo_number': 4},
             {'fp_before_recovery': 0, 'owner_fp': 4}),
            ('owner-p2-fifth-combo-gains-4-at-recovery', 'p2', {'combo_number': 5},
             {'fp_before_recovery': 0, 'owner_fp': 4}),
            ('third-combo-gains-nothing', 'p1', {'combo_number': 3},
             {'fp_before_recovery': 0, 'owner_fp': 0}),
        )),
        'cb04-ps-001-n1': (_run_ps001_guard, (
            ('owner-p1-guard-gives-opponent-frost', 'p1', {}, {**frost_ok, 'owner_frost': False}),
            ('owner-p2-clash-gives-opponent-frost', 'p2', {'event': 'clash'}, frost_ok),
            ('opponent-guard-does-not-trigger', 'p1', {'by_opponent': True}, {'opponent_frost': False}),
        )),
        'cb04-ps-001-n2': (_run_ps001_guard, (
            ('owner-p1-frost-sends-hand-bukuki-to-lumen', 'p1', {}, {'lumen': ['p1-stock']}),
            ('owner-p2-frost-sends-hand-bukuki-to-lumen', 'p2', {}, {'lumen': ['p2-stock']}),
            ('non-bukuki-hand-card-stays', 'p1', {'stock_character': None}, {**frost_ok, 'lumen': []}),
        )),
        'cb04-ps-001-n3': (_run_ps001_recovery, (
            ('owner-p1-behind-returns-lumen-bukuki', 'p1', {'owner_fp': 1, 'opponent_fp': 3},
             {'stored_zone': 'list'}),
            ('owner-p2-behind-returns-lumen-bukuki', 'p2', {'owner_fp': 0, 'opponent_fp': 2},
             {'stored_zone': 'list'}),
            ('equal-fp-keeps-lumen-bukuki', 'p1', {'owner_fp': 3, 'opponent_fp': 3},
             {'stored_zone': 'lumen'}),
        )),
        'cb04-at-012-function': (_run_defense_rule, (
            ('owner-p1-dodges-x-guard-attack', 'p1', {'code': 'CB04-AT-012', 'judgment': 'dodge', 'guard': 'X'},
             {'allowed': True}),
            ('owner-p2-dodges-x-guard-attack', 'p2', {'code': 'CB04-AT-012', 'judgment': 'dodge', 'guard': 'X'},
             {'allowed': True}),
            ('numeric-guard-attack-cannot-be-dodged', 'p1',
             {'code': 'CB04-AT-012', 'judgment': 'dodge', 'guard': '-4'}, {'allowed': False}),
        )),
        'cb04-at-012-n1': (_run_at012_combo, (
            ('owner-p1-combo-bukuki-adds-100', 'p1', {}, {'damage_delta': 100}),
            ('owner-p2-combo-bukuki-adds-100', 'p2', {}, {'damage_delta': 100}),
            ('non-combo-use-keeps-damage', 'p1', {'combo': False}, {'damage_delta': 0}),
        )),
        'cb04-at-012-n1-starter': (_run_at012_combo, (
            ('owner-p1-bukuki-starter-adds-100-once', 'p1', {'starter': True}, {'damage_delta': 100}),
            ('owner-p2-bukuki-starter-adds-100-once', 'p2', {'starter': True}, {'damage_delta': 100}),
            ('non-bukuki-starter-keeps-damage', 'p1', {'starter': True, 'character': None},
             {'damage_delta': 0}),
        )),
        'cb04-at-001-function': (_run_at001_play, (
            ('owner-p1-hp-2500-can-use', 'p1', {'hp': 2500}, {'use_allowed': True}),
            ('owner-p2-hp-2000-can-use', 'p2', {'hp': 2000}, {'use_allowed': True}),
            ('hp-2600-cannot-use', 'p1', {'hp': 2600}, {'use_allowed': False}),
        )),
        'cb04-at-001-n1': (_run_at001_battle, (
            ('owner-p1-negates-opponent-battle-effects', 'p1', {}, {'enemy_negated': True, 'enemy_zone': 'battle'}),
            ('owner-p2-negates-opponent-battle-effects', 'p2', {}, {'enemy_negated': True, 'enemy_zone': 'battle'}),
            ('negated-source-does-not-negate', 'p1', {'negated': True}, {'enemy_negated': False}),
        )),
        'cb04-at-001-n2': (_run_at001_battle, (
            ('owner-p1-after-use-frost-and-break', 'p1', {'event': 'after_use'},
             {**frost_ok, 'source_zone': 'break'}),
            ('owner-p2-after-use-frost-and-break', 'p2', {'event': 'after_use'},
             {**frost_ok, 'source_zone': 'break'}),
            ('negated-source-stays-without-frost', 'p1', {'event': 'after_use', 'negated': True},
             {'opponent_frost': False, 'source_zone': 'battle'}),
        )),
        'cb04-at-002-n1': (_run_at002_dodge, (
            ('owner-p1-dodged-opponent-gains-2-user-picks', 'p1', {},
             {'opponent_fp': 2, 'decision_owner': 'p1', 'list': ['p1-stored'], 'lumen': ['p1-unrelated']}),
            ('owner-p2-dodged-opponent-gains-2-user-picks', 'p2', {},
             {'opponent_fp': 2, 'decision_owner': 'p2', 'list': ['p2-stored']}),
            ('no-lumen-bukuki-still-gives-fp', 'p1', {'stored': False},
             {'opponent_fp': 2, 'list': [], 'lumen': ['p1-unrelated']}),
        )),
        'cb04-at-002-n2': (_run_list_to_lumen, (
            ('owner-p1-hit-sends-list-bukuki', 'p1', {'code': 'CB04-AT-002', 'events': ['hit']}, {'lumen_count': 1}),
            ('owner-p2-counter-sends-list-bukuki', 'p2', {'code': 'CB04-AT-002', 'events': ['counter']},
             {'lumen_count': 1}),
            ('hit-and-combo-same-turn-only-once', 'p1', {'code': 'CB04-AT-002', 'events': ['hit', 'combo']},
             {'lumen_count': 1}),
        )),
        'cb04-at-007-function': (_run_defense_rule, (
            ('owner-p1-dodges-speed-8', 'p1', {'code': 'CB04-AT-007', 'judgment': 'dodge', 'frame': 8},
             {'allowed': True}),
            ('owner-p2-dodges-speed-8', 'p2', {'code': 'CB04-AT-007', 'judgment': 'dodge', 'frame': 8},
             {'allowed': True}),
            ('speed-9-cannot-be-dodged', 'p1', {'code': 'CB04-AT-007', 'judgment': 'dodge', 'frame': 9},
             {'allowed': False}),
        )),
        'cb04-at-007-n1': (_run_frost_damage, _frost_damage_cases('CB04-AT-007')),
        'cb04-at-007-n2': (_run_on_event, (
            ('owner-p1-hit-gives-frost', 'p1', {'code': 'CB04-AT-007', 'event': 'hit'}, frost_ok),
            ('owner-p2-counter-gives-frost', 'p2', {'code': 'CB04-AT-007', 'event': 'counter'}, frost_ok),
            ('negated-source-gives-no-frost', 'p1', {'code': 'CB04-AT-007', 'event': 'hit', 'negated': True},
             {'opponent_frost': False}),
        )),
        'cb04-at-007-n3': (_run_on_event, (
            ('owner-p1-combo-allows-lumen-bukuki', 'p1', {'code': 'CB04-AT-007', 'event': 'combo'},
             {'lumen_combo_rules': [(['lumen'], BUKUKI, 'turn')]}),
            ('owner-p2-combo-allows-lumen-bukuki', 'p2', {'code': 'CB04-AT-007', 'event': 'combo'},
             {'lumen_combo_rules': [(['lumen'], BUKUKI, 'turn')]}),
            ('negated-source-adds-no-combo-rule', 'p1',
             {'code': 'CB04-AT-007', 'event': 'combo', 'negated': True}, {'lumen_combo_rules': []}),
        )),
        'cb04-at-035-n1': (_run_cmyk_set, (
            ('owner-p1-set-drum-applies-twice', 'p1',
             {'code': 'CB04-AT-035', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT}, {'owner_fp': 2}),
            ('owner-p2-set-drum-applies-twice', 'p2',
             {'code': 'CB04-AT-035', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT}, {'owner_fp': 2}),
            ('negated-host-applies-set-effect-once', 'p1',
             {'code': 'CB04-AT-035', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT, 'negated': True}, {'owner_fp': 1}),
        )),
        'cb04-at-035-n2': (_run_at035_clash, (
            ('owner-p1-with-set-card-blocks-clash', 'p1', {'attached': True}, {'opponent_clash_blocked': True}),
            ('owner-p2-with-set-card-blocks-clash', 'p2', {'attached': True}, {'opponent_clash_blocked': True}),
            ('without-set-card-allows-clash', 'p1', {'attached': False}, {'opponent_clash_blocked': False}),
        )),
        'cb04-at-035-n3': (_run_at035_gain, (
            ('owner-p1-hit-gains-two-from-list', 'p1', {'events': ['hit']}, {'hand_count': 2, 'list_count': 1}),
            ('owner-p2-counter-gains-two-from-list', 'p2', {'events': ['counter']},
             {'hand_count': 2, 'list_count': 1}),
            ('hit-and-combo-same-turn-only-once', 'p1', {'events': ['hit', 'combo']},
             {'hand_count': 2, 'list_count': 1}),
        )),
        'cb04-at-036-n1': (_run_cmyk_set, (
            ('owner-p1-set-on-cmyk-host-adds-100', 'p1', {'code': 'CB04-AT-036', 'role': 'set'},
             {'host_damage_delta': 100}),
            ('owner-p2-set-on-cmyk-host-adds-100', 'p2', {'code': 'CB04-AT-036', 'role': 'set'},
             {'host_damage_delta': 100}),
            ('non-cmyk-host-gets-nothing', 'p1', {'code': 'CB04-AT-036', 'role': 'set', 'host_character': 'tao'},
             {'host_damage_delta': 0}),
        )),
        'cb04-at-036-n2': (_run_cmyk_set, (
            ('owner-p1-set-drum-fp-becomes-damage', 'p1',
             {'code': 'CB04-AT-036', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT}, {'owner_fp': 0, 'host_damage_delta': 200}),
            ('owner-p2-set-drum-fp-becomes-damage', 'p2',
             {'code': 'CB04-AT-036', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT}, {'owner_fp': 0, 'host_damage_delta': 200}),
            ('negated-host-keeps-drum-fp', 'p1',
             {'code': 'CB04-AT-036', 'role': 'host', 'set_definition': DRUM_DEFINITION,
              'set_code': 'REVIEW-CB04-DRUM', 'set_text': DRUM_TEXT, 'negated': True},
             {'owner_fp': 1, 'host_damage_delta': 0}),
        )),
        'cb04-at-037-function': (_run_defense_rule, (
            ('owner-p1-dodges-non-combo-attack', 'p1', {'code': 'CB04-AT-037', 'judgment': 'dodge', 'hit': '3'},
             {'allowed': True}),
            ('owner-p2-dodges-non-combo-attack', 'p2', {'code': 'CB04-AT-037', 'judgment': 'dodge', 'hit': '3'},
             {'allowed': True}),
            ('combo-attack-cannot-be-dodged', 'p1', {'code': 'CB04-AT-037', 'judgment': 'dodge', 'hit': '콤보'},
             {'allowed': False}),
        )),
        'cb04-at-037-n1': (_run_at037_dodge, (
            ('owner-p1-two-set-cards-gain-two', 'p1', {'attached': 2}, {'owner_fp': 2, 'hand_count': 2}),
            ('owner-p2-one-set-card-gains-one', 'p2', {'attached': 1}, {'owner_fp': 2, 'hand_count': 1}),
            ('no-set-card-gains-only-fp', 'p1', {'attached': 0}, {'owner_fp': 2, 'hand_count': 0}),
        )),
        'cb04-tk-001-function': (_run_token, (
            ('token-key-is-garage', 'p1', {'field': 'token_key'}, {'token_key': 'garage'}),
            ('usable-as-token-or-counter', 'p2', {'field': 'token_usage'}, {'token_usage': ['token', 'counter']}),
            ('no-character-root-rules', 'p1', {'field': 'combo_rules'}, {'combo_rules': None}),
        )),
        'cb04-at-003-n1': (_run_frost_damage, _frost_damage_cases('CB04-AT-003')),
        'cb04-at-003-n2': (_run_on_event, (
            ('owner-p1-dodged-opponent-gains-3', 'p1', {'code': 'CB04-AT-003', 'event': 'opponent_dodge'},
             {'opponent_fp': 3}),
            ('owner-p2-dodged-opponent-gains-3', 'p2', {'code': 'CB04-AT-003', 'event': 'opponent_dodge'},
             {'opponent_fp': 3}),
            ('negated-source-gives-no-fp', 'p1',
             {'code': 'CB04-AT-003', 'event': 'opponent_dodge', 'negated': True}, {'opponent_fp': 0}),
        )),
        'cb04-at-003-n3': (_run_break_list, (
            ('owner-p1-counter-breaks-list-for-frost', 'p1', {'code': 'CB04-AT-003', 'event': 'counter'},
             {'break': ['p1-listed'], **frost_ok}),
            ('owner-p2-counter-breaks-list-for-frost', 'p2', {'code': 'CB04-AT-003', 'event': 'counter'},
             {'break': ['p2-listed'], **frost_ok}),
            ('empty-list-gives-no-frost', 'p1', {'code': 'CB04-AT-003', 'event': 'counter', 'listed': False},
             {'break': [], 'opponent_frost': False}),
        )),
        'cb04-at-004-function': (_run_defense_rule, (
            ('owner-p1-dodges-speed-8', 'p1', {'code': 'CB04-AT-004', 'judgment': 'dodge', 'frame': 8},
             {'allowed': True}),
            ('owner-p2-dodges-speed-8', 'p2', {'code': 'CB04-AT-004', 'judgment': 'dodge', 'frame': 8},
             {'allowed': True}),
            ('speed-9-cannot-be-dodged', 'p1', {'code': 'CB04-AT-004', 'judgment': 'dodge', 'frame': 9},
             {'allowed': False}),
        )),
        'cb04-at-004-n1': (_run_break_list, (
            ('owner-p1-hit-breaks-list-sends-side-bukuki', 'p1', {'code': 'CB04-AT-004', 'event': 'hit'},
             {'break': ['p1-listed'], 'lumen': ['p1-side-bukuki']}),
            ('owner-p2-counter-breaks-list-sends-side-bukuki', 'p2', {'code': 'CB04-AT-004', 'event': 'counter'},
             {'break': ['p2-listed'], 'lumen': ['p2-side-bukuki']}),
            ('no-side-bukuki-only-breaks', 'p1', {'code': 'CB04-AT-004', 'event': 'hit', 'side_bukuki': False},
             {'break': ['p1-listed'], 'lumen': []}),
        )),
        'cb04-at-006-function': (_run_defense_rule, (
            ('owner-p1-clashes-speed-8', 'p1', {'code': 'CB04-AT-006', 'judgment': 'clash', 'frame': 8},
             {'allowed': True}),
            ('owner-p2-clashes-speed-8', 'p2', {'code': 'CB04-AT-006', 'judgment': 'clash', 'frame': 8},
             {'allowed': True}),
            ('speed-9-cannot-be-clashed', 'p1', {'code': 'CB04-AT-006', 'judgment': 'clash', 'frame': 9},
             {'allowed': False}),
        )),
        'cb04-at-006-n1': (_run_at006_clash, (
            ('owner-p1-clash-lowers-opponent-hit', 'p1', {},
             {'judgment_modified': [{'card_instance_id': 'p2-enemy', 'field': 'hit', 'after': '-2'}]}),
            ('owner-p2-clash-lowers-opponent-hit', 'p2', {},
             {'judgment_modified': [{'card_instance_id': 'p1-enemy', 'field': 'hit', 'after': '-2'}]}),
            ('negated-source-changes-nothing', 'p1', {'negated': True}, {'judgment_modified': []}),
        )),
        'cb04-at-006-n2': (_run_at006_bloom, (
            ('owner-p1-hit-breaks-for-shield-and-fp', 'p1', {},
             {'source_zone': 'break', 'owner_fp': 3, 'shield': 400}),
            ('owner-p2-hit-breaks-for-shield-and-fp', 'p2', {},
             {'source_zone': 'break', 'owner_fp': 3, 'shield': 400}),
            ('opponent-event-does-not-trigger', 'p1', {'by_opponent': True},
             {'source_zone': 'lumen', 'owner_fp': 0, 'shield': 0}),
        )),
        'cb04-at-021-function': (_run_blocked, _blocked_cases('CB04-AT-021', 'guard')),
        'cb04-at-021-n1': (_run_at021_spirit, (
            ('owner-p1-yin-at-trigger-gains-yin', 'p1', {'yin_at_trigger': True, 'yin_after_removal': False},
             {'yang_count': 0, 'yin_count': 1, 'speed_fixed': 2}),
            ('owner-p2-yin-at-trigger-gains-yin', 'p2', {'yin_at_trigger': True, 'yin_after_removal': True},
             {'yang_count': 0, 'yin_count': 1, 'speed_fixed': 2}),
            ('yin-only-after-removal-gains-nothing', 'p1', {'yin_at_trigger': False, 'yin_after_removal': True},
             {'yang_count': 0, 'yin_count': None, 'speed_fixed': 2}),
        )),
        'cb04-at-021-n2': (_run_harmony_hit, (
            ('owner-p1-harmony-hit-adds-400', 'p1', {'code': 'CB04-AT-021'}, {'damage_delta': 400}),
            ('owner-p2-harmony-hit-adds-400', 'p2', {'code': 'CB04-AT-021'}, {'damage_delta': 400}),
            ('no-harmony-keeps-damage', 'p1', {'code': 'CB04-AT-021', 'harmony': False}, {'damage_delta': 0}),
        )),
        'cb04-at-022-function': (_run_blocked, _blocked_cases('CB04-AT-022', 'dodge', with_where=True)),
        'cb04-at-022-n1': (_run_at022_fp, (
            ('owner-p1-three-yang-counters-gain-one', 'p1', {'yang_state': False}, {'owner_fp': 1}),
            ('owner-p2-yang-state-gains-three', 'p2', {'yang_state': True}, {'owner_fp': 3}),
            ('yang-state-is-fixed-at-trigger', 'p1', {'yang_state': True, 'yang_after': False}, {'owner_fp': 3}),
        )),
        'cb04-at-022-n2': (_run_blocked, (
            ('owner-p1-harmony-blocks-all-dodge', 'p1',
             {'code': 'CB04-AT-022', 'kind': 'dodge', 'with_where': False, 'harmony': True},
             {'opponent_blocked': True}),
            ('owner-p2-harmony-blocks-all-dodge', 'p2',
             {'code': 'CB04-AT-022', 'kind': 'dodge', 'with_where': False, 'harmony': True},
             {'opponent_blocked': True}),
            ('no-harmony-blocks-only-special-dodge', 'p1',
             {'code': 'CB04-AT-022', 'kind': 'dodge', 'with_where': False}, {'opponent_blocked': False}),
        )),
        'cb04-at-022-n3': (_run_at022_combo_end, (
            ('owner-p1-combo-end-gains-own-battle', 'p1', {},
             {'hand': ['p1-partner', 'p1-source'], 'enemy_zone': 'battle'}),
            ('owner-p2-combo-end-gains-own-battle', 'p2', {},
             {'hand': ['p2-partner', 'p2-source'], 'enemy_zone': 'battle'}),
            ('not-used-in-combo-does-not-trigger', 'p1', {'in_combo': False}, {'hand': []}),
        )),
        'cb04-at-010-n1': (_run_at010_fp, (
            ('owner-p1-opponent-attack-effect-fp-blocked', 'p1',
             {'effect_owner': 'p2', 'card_type': '공격', 'target': 'controller'}, {'opponent_fp': 0}),
            ('owner-p2-opponent-defense-effect-fp-allowed', 'p2',
             {'effect_owner': 'p1', 'card_type': '수비', 'target': 'controller'}, {'opponent_fp': 2}),
            ('own-attack-effect-giving-opponent-fp-allowed', 'p1',
             {'effect_owner': 'p1', 'card_type': '공격', 'target': 'opponent'}, {'opponent_fp': 2}),
        )),
        'cb04-at-010-n2': (_run_at010_clash, (
            ('owner-p1-clash-moves-list-to-lumen', 'p1', {}, {'source_zone': 'lumen'}),
            ('owner-p2-clash-moves-list-to-lumen', 'p2', {}, {'source_zone': 'lumen'}),
            ('opponent-clash-keeps-list', 'p1', {'by_opponent': True}, {'source_zone': 'list'}),
        )),
        'cb04-at-011-function': (_run_blocked, _blocked_cases('CB04-AT-011', 'clash')),
        'cb04-at-011-n1': (_run_frost_damage, _frost_damage_cases('CB04-AT-011')),
        'cb04-at-013-n1': (_run_at013, (
            ('owner-p1-no-damage-drains-8-and-frost', 'p1', {'damage_received': 0},
             {'opponent_fp': 2, **frost_ok}),
            ('owner-p2-no-damage-drains-8-and-frost', 'p2', {'damage_received': 0},
             {'opponent_fp': 2, **frost_ok}),
            ('damage-received-does-nothing', 'p1', {'damage_received': 300},
             {'opponent_fp': 10, 'opponent_frost': False}),
        )),
    }


CASES = _cases()


def _strip(definition):
    stripped = {key: copy.deepcopy(value) for key, value in (definition or {}).items()
                if key not in META_ROOT_KEYS}
    stripped['abilities'] = [
        {key: value for key, value in ability.items() if key not in META_ABILITY_KEYS}
        for ability in stripped.get('abilities') or []
    ]
    return stripped


def _scenarios(runner, definition, snapshot, cases):
    results = []
    for name, owner, kwargs, expected in cases:
        try:
            first = runner(definition, snapshot, owner, **kwargs)
            second = runner(definition, snapshot, owner, **kwargs)
        except Exception as error:  # 엔진 오류도 실패한 검토 상황으로 남긴다.
            results.append({
                'name': name, 'passed': False, 'deterministic': False,
                'expected': expected, 'error': f'{type(error).__name__}: {error}',
            })
            continue
        deterministic = _canonical(first) == _canonical(second)
        results.append({
            'name': name, 'owner': owner,
            'passed': bool(deterministic and all(first.get(key) == value for key, value in expected.items())),
            'deterministic': deterministic, 'expected': expected, **first,
        })
    return results


def review_cb04_definition(definition, card_snapshot, extra_root):
    code = str((card_snapshot or {}).get('code') or '')
    if code not in BUILDERS:
        return None
    expected = build_cb04_definition(code)
    if _strip(definition) != _strip(expected):
        return DefinitionReview(
            False, False, [AbilityReview(
                code.lower(), False,
                reason='CB04 카드 정의가 drafts_cb04 기준 정의와 다릅니다. 수정 내용에 맞는 검토 시나리오가 필요합니다.',
            )], f'{code} 전용 정의 검증에 실패했습니다.', method=AUTOMATIC_SCENARIO_VERSION,
        )
    reviews = []
    for ability in definition.get('abilities') or []:
        ability_id = ability.get('id')
        runner, cases = CASES.get(ability_id, (None, ()))
        if runner is None:
            reviews.append(AbilityReview(ability_id, False, reason='검토 시나리오가 없습니다.'))
            continue
        scenarios = _scenarios(runner, definition, card_snapshot, cases)
        reviews.append(AbilityReview(
            ability_id, len(scenarios) >= 3 and all(item['passed'] for item in scenarios), scenarios,
        ))
    passed = bool(reviews) and all(item.passed for item in reviews)
    return DefinitionReview(
        passed, False, reviews,
        '' if passed else f'{code} 카드별 시나리오 검증에 실패했습니다.',
        method=AUTOMATIC_SCENARIO_VERSION,
    )
