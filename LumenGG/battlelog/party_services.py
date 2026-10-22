import secrets
import copy
import random
from collections import deque
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404
from django.urls import reverse
from django.utils import timezone

from card.models import Character
from .models import BattleSession, PartyEncounter, PartyPlayer, PartyRoom
from .party_board import BOARD, SHOP, EVENTS, CRYSTAL_COSTS, board_for, home_for, range_exits
from .party_cards import card_catalog, display_board, display_event
from .party_supplies import spawn_supplies, supply_at, finish_supply_visit, validate_supply_combo
from .event_buffer import recent_battle_event_payloads
from .services import generate_token, initial_hp_for_character, initial_passive_state_for_character, hand_limit_for_hp, party_battle_complete


class PartyConflict(ValueError):
    pass


def _number(value, minimum=0, maximum=100000):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError('숫자 입력이 올바르지 않습니다.')
    return value


def _text(value, limit, default=''):
    if not isinstance(value, str):
        raise ValueError('문자 입력이 올바르지 않습니다.')
    return value.strip()[:limit] or default


def _live(room):
    if room.expires_at <= timezone.now():
        raise ValueError('만료된 파티입니다. 새 방을 만들어주세요.')


def _log(room, message):
    entries = room.document.setdefault('log', [])
    entries.append({'text': message, 'at': timezone.now().isoformat()})
    room.document['log'] = entries[-80:]


def _save_room(room):
    room.version += 1
    room.save(update_fields=['document', 'status', 'version', 'updated_at'])


def _ensure_board(room):
    if room.document.get('board_version', 1) >= getattr(settings, 'PARTY_BOARD_VERSION', 2):
        return
    with transaction.atomic():
        current = PartyRoom.objects.select_for_update().get(pk=room.pk)
        if current.document.get('board_version', 1) < 2:
            remap = lambda node: (round(node * 40 / 24) + 5) % 40 if node < 24 else 40 + (node - 24) * 3
            old_positions = {}
            for player in current.players.all():
                old_positions[str(player.seat)] = player.position
                player.position = remap(player.position)
                player.save(update_fields=['position'])
            for barrier in current.document.get('roadblocks', []):
                barrier['node'] = remap(barrier['node'])
            for crate in current.document.get('supplies', []):
                crate['node'] = remap(crate['node'])
            current.document['previous_positions'] = {}
            current.document.pop('move_path', None)
            current.document['board_version'] = 2
            current.document['board_upgrade'] = {'from': 1, 'positions': old_positions}
            if current.document.get('move_prompt'):
                actor = current.players.get(seat=current.document['turn'])
                current.document['move_prompt'] = _passing_prompt(current, actor)
            _log(current, '확장 순환 광장으로 이동했습니다. 체력·아이템·남은 이동은 유지됩니다.')
            _save_room(current)
    room.refresh_from_db()


def _add_player(room, data, host=False):
    character = Character.objects.filter(pk=_number(data.get('character_id'), 1)).first()
    if not character:
        raise ValueError('캐릭터를 선택해주세요.')
    seats = set(room.players.values_list('seat', flat=True))
    seat = next((seat for seat in range(4) if seat not in seats), None)
    if seat is None:
        raise ValueError('방이 가득 찼습니다. 최대 4명이 참여할 수 있습니다.')
    hp = initial_hp_for_character(character)
    player = PartyPlayer.objects.create(
        room=room, seat=seat, token=generate_token(), is_host=host,
        name=_text(data.get('name', ''), 30, f'플레이어 {seat + 1}'), character=character,
        hp=hp, max_hp=hp, position=home_for(room, seat), coins=0,
    )
    _log(room, f'{player.name}님이 참여했습니다.')
    return player


def create_room(data):
    for _ in range(8):
        try:
            with transaction.atomic():
                room = PartyRoom.objects.create(
                    code=''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(6)),
                    name=_text(data.get('room_name', ''), 60, '루멘 파티'),
                    expires_at=timezone.now() + timedelta(hours=24),
                    document={'board_version': getattr(settings, 'PARTY_BOARD_VERSION', 2), 'round': 1, 'turn': 0, 'turn_number': 1,
                              'move': None, 'move_prompt': None, 'arrival': None, 'landed': False,
                              'boost': 0, 'winners': [], 'log': []},
                )
                player = _add_player(room, data, host=True)
                room.save(update_fields=['document'])
                return room, player
        except IntegrityError:
            continue
    raise ValueError('방 생성에 실패했습니다. 다시 시도해주세요.')


def join_room(code, data):
    with transaction.atomic():
        room = PartyRoom.objects.select_for_update().get(code=code)
        _ensure_board(room)
        _live(room)
        if room.status != 'lobby':
            raise ValueError('이미 시작한 파티입니다. 관전으로 참여할 수 있습니다.')
        player = _add_player(room, data)
        _save_room(room)
        return room, player


def room_player(room, token):
    if not isinstance(token, str) or not token:
        return None
    player = room.players.select_related('character').filter(token=token).first()
    if player:
        player.items = [_item_key(item) for item in player.items]
    return player


def forward_exits(room, player):
    move = room.document.get('move')
    if move and player.seat == room.document['turn'] and move.get('free_direction'):
        return list(board_for(room)['nodes'][player.position]['exits'])
    previous = room.document.get('previous_positions', {}).get(str(player.seat))
    if previous not in board_for(room)['nodes'][player.position]['exits']:
        heading = room.document.get('headings', {}).get(str(player.seat), 1)
        previous = _ring_neighbor(room, player.position, -heading)
    return [node for node in board_for(room)['nodes'][player.position]['exits'] if node != previous]


def _ring_neighbor(room, position, direction):
    expanded = board_for(room)['version'] >= 2
    outer, inner = (40, 24) if expanded else (24, 8)
    base, count = (outer, inner) if position >= outer else (0, outer)
    return base + (position - base + direction) % count


def _movement_power(room):
    return (room.document['round'] - 1) // 3


def _attacker_bonus(room):
    return (room.document['round'] - 1) // 5


def _item_key(item):
    return 'hurry' if item == 'boost' else item


def _flag(room, name, player):
    return room.document.get(name, {}).get(str(player.seat))


def _set_flag(room, name, player, value=True):
    room.document.setdefault(name, {})[str(player.seat)] = value


def _targetable(room, player):
    return player.hp > 0 and not _flag(room, 'cloaks', player)


def _item_targets(room, player):
    distances = {player.position: 0}
    queue = deque([player.position])
    while queue:
        node = queue.popleft()
        if distances[node] >= 8:
            continue
        for following in range_exits(board_for(room)['nodes'][node]):
            if following not in distances:
                distances[following] = distances[node] + 1
                queue.append(following)
    others = list(room.players.exclude(pk=player.pk))
    targets = {}
    for key, item in SHOP.items():
        if item['target'] == 'player':
            targets[key] = [p.seat for p in others
                            if _targetable(room, p) and distances.get(p.position, 99) <= item['range']]
        elif item['target'] == 'tile':
            occupied = {b['node'] for b in room.document.get('roadblocks', [])}
            targets[key] = [node for node in range(len(board_for(room)['nodes'])) if node not in occupied and distances.get(node, 99) <= item['range']]
    return targets


def _hand_task(room, player, reason):
    count = hand_limit_for_hp(player.character, player.hp)
    task = {'reason': reason, 'count': count, 'version': room.version + 1}
    _set_flag(room, 'hand_tasks', player, task)
    amount = f'{count}장' if count is not None else '캐릭터의 최대 손패'
    _log(room, f'{player.name}: 손패를 모두 버린 후 {amount}까지 새로 획득하세요. ({reason})')


def _knock_out(room, player, source=None):
    if _flag(room, 'knockouts', player):
        return
    _set_flag(room, 'knockouts', player, {'rested': False, 'at_turn': room.document['turn_number']})
    room.document.get('hand_tasks', {}).pop(str(player.seat), None)
    if player.seat == room.document['turn']:
        room.document.update(move=None, move_prompt=None, arrival=None, landed=True)
    _log(room, f'{player.name}: 기절. 다음 자기 턴을 쉬고, 그다음 자기 턴에 현재 위치에서 부활합니다.')
    if source and source.pk != player.pk:
        source.crystals += 1
        source.coins += 5
        source.save(update_fields=['crystals', 'coins'])
        _log(room, f'{source.name}: {player.name} 기절 · 승점 +1 (현재 {source.crystals}점) · 5코인 획득.')


def _damage(room, player, amount, source=None, item=False):
    if player.hp <= 0:
        return
    if item and _flag(room, 'shields', player):
        room.document['shields'].pop(str(player.seat))
        _log(room, f'{player.name}: 효과 보호막이 아이템 피해를 막았습니다.')
        return
    player.hp = max(0, player.hp - amount)
    if player.hp == 0:
        _knock_out(room, player, source)
    player.save(update_fields=['hp'])


def _use_item(room, player, body):
    if _movement_started(room):
        raise ValueError('아이템은 자기 턴의 이동 전에만 사용할 수 있습니다.')
    key = _item_key(body.get('item'))
    if not isinstance(key, str) or key not in SHOP or key not in player.items:
        raise ValueError('지금 사용할 수 없는 아이템입니다.')
    if room.document.get('item_turn') == room.document['turn_number']:
        raise ValueError('아이템은 한 턴에 한 번 사용할 수 있습니다.')
    item = display_board(room)['shop'][key]
    if item['target'] == 'player':
        target = room.players.select_related('character').filter(seat=_number(body.get('target'), 0, 3)).first()
        if not target or target.seat not in _item_targets(room, player)[key]:
            raise ValueError('사거리 내의 대상이 될 수 있는 다른 캐릭터를 선택해주세요.')
        _damage(room, target, item['damage'], source=player, item=True)
    elif item['target'] == 'tile':
        node = _number(body.get('node'), 0, len(board_for(room)['nodes']) - 1)
        if node not in _item_targets(room, player)[key]:
            raise ValueError('8칸 내의 설치물이 없는 칸을 선택해주세요.')
        room.document.setdefault('roadblocks', []).append({'node': node, 'owner': player.seat})
    elif key == 'smart_dice':
        _set_flag(room, 'smart_dice', player, _number(body.get('value'), 1, 6))
    elif key in ('heal', 'heal_kit'):
        player.hp = min(player.max_hp, player.hp + (200 if key == 'heal' else 400))
    elif key == 'prepare':
        player.prepared_fp += 4
    elif key == 'training':
        _hand_task(room, player, '기술 수련')
    else:
        flag = {'hurry': 'double_dice', 'redirect': 'free_direction', 'shield': 'shields',
                'cloak': 'cloaks', 'revenge': 'revenge'}[key]
        _set_flag(room, flag, player)
    player.items.remove(key)
    room.document['item_turn'] = room.document['turn_number']
    _log(room, f'{player.name}: {item["label"]} 사용.')
    reward = room.document.get('item_rewards', {}).pop(str(player.seat), None)
    if reward:
        reward = _item_key(reward)
        player.items.append(reward)
        _log(room, f'{player.name}: 빈 슬롯에 거점 보상 {display_board(room)["shop"][reward]["label"]}을 받았습니다.')
    player.save()


def _battle_visit(room, player):
    return [room.document['turn_number'], player.seat, player.position, room.document.get('movement_visit', 0)]


def _meeting_targets(room, player):
    fought = room.document.get('fought_here') or {}
    completed = fought.get('targets', []) if fought.get('visit') == _battle_visit(room, player) else []
    return [p.seat for p in room.players.filter(position=player.position, hp__gt=0).exclude(pk=player.pk)
            if _targetable(room, p) and p.seat not in completed]


def challenge_targets(room, player):
    if player.hp <= 0 or room.document.get('counter_prompt'):
        return []
    if not room.document['landed'] and not room.document.get('move_prompt') and room.document.get('arrival') != 'dash':
        return []
    return _meeting_targets(room, player)


def movement_preview(room, player):
    """Bounded reachability over directed arrivals; no enumeration of branching walks."""
    move = room.document.get('move')
    if not move or room.status != 'running':
        return None
    budget = move['remaining']
    start = (None, player.position)
    distance, transitions, reverse = {start: 0}, {}, {}
    queue = deque([start])
    barriers = {b['node'] for b in room.document.get('roadblocks', [])}
    while queue:
        here = queue.popleft()
        depth = distance[here]
        transitions[here] = []
        if depth >= budget or (here != start and here[1] in barriers):
            continue
        exits = forward_exits(room, player) if here == start else [n for n in board_for(room)['nodes'][here[1]]['exits'] if n != here[0]]
        for node in exits:
            following = (here[1], node)
            transitions[here].append(following)
            reverse.setdefault(following, []).append(here)
            if following not in distance:
                distance[following] = depth + 1
                queue.append(following)
    edge_key = lambda a, b: f'{min(a, b)}-{max(a, b)}'
    nodes = sorted({state[1] for state in distance if state != start})
    edges = sorted({edge_key(here[1], following[1]) for here, exits in transitions.items() for following in exits})
    routes = {}
    for node in nodes:
        back = {state: 0 for state in distance if state != start and state[1] == node}
        queue = deque(back)
        while queue:
            here = queue.popleft()
            for previous in reverse.get(here, []):
                if previous not in back:
                    back[previous] = back[here] + 1
                    queue.append(previous)
        path_edges, path_nodes = set(), {node}
        for here, exits in transitions.items():
            for following in exits:
                if following in back and distance[here] + 1 + back[following] <= budget:
                    path_edges.add(edge_key(here[1], following[1]))
                    path_nodes.update([here[1], following[1]])
        routes[str(node)] = {'nodes': sorted(path_nodes), 'edges': sorted(path_edges)}
    return {'origin': player.position, 'remaining': budget, 'nodes': nodes, 'edges': edges, 'routes': routes}


def _start_move_path(room, player):
    room.document['move_path'] = {'seat': player.seat, 'nodes': [player.position], 'version': room.version + 1}


def _step(room, player, node):
    room.document['challenge_declined'] = False
    room.document['movement_visit'] = room.document.get('movement_visit', 0) + 1
    if board_for(room)['nodes'][node]['ring'] == board_for(room)['nodes'][player.position]['ring']:
        heading = 1 if node == _ring_neighbor(room, player.position, 1) else -1
        room.document.setdefault('headings', {})[str(player.seat)] = heading
    room.document.setdefault('previous_positions', {})[str(player.seat)] = player.position
    player.position = node
    room.document['move_path']['nodes'].append(node)
    room.document['move']['remaining'] -= 1
    room.document['move']['free_direction'] = False
    player.save()
    barrier = next((b for b in room.document.get('roadblocks', []) if b['node'] == node), None)
    if barrier:
        room.document['roadblocks'].remove(barrier)
        _log(room, f'{player.name}: 통행 금지에 도착하여 이동을 멈췄습니다. 설치물을 제거합니다.')
    if barrier or room.document['move']['remaining'] == 0:
        _land(room, player)
    else:
        room.document['move_prompt'] = _passing_prompt(room, player)


def _passing_prompt(room, player):
    targets = [] if room.document.get('challenge_declined') else _meeting_targets(room, player)
    own_camp = player.position == home_for(room, player.seat)
    shared_camp = bool(board_for(room)['nodes'][player.position].get('shared'))
    shop = (board_for(room)['nodes'][player.position]['kind'] == 'shop' and
            room.document.get('shop_bought_turn') != room.document['turn_number'] and
            room.document.get('shop_closed_turn') != room.document['turn_number'])
    crate = supply_at(room, player)
    if not (targets or own_camp or shared_camp or shop or crate):
        return None
    prompt = {'targets': targets, 'own_camp': own_camp}
    if shared_camp:
        prompt['shared_camp'] = True
    if shop:
        prompt['shop'] = True
        prompt['shop_open'] = True
    if crate:
        prompt['supply'] = crate['id']
    return prompt


def _advance_forced_path(room, player):
    while room.document['move'] and not room.document['move'].get('reveal_pending') and not room.document.get('move_prompt'):
        exits = forward_exits(room, player)
        if len(exits) != 1:
            break
        _step(room, player, exits[0])


def _camp_available(room, player):
    return (player.hp > 0 and not room.document.get('counter_prompt') and room.document['landed'] and player.seat == room.document['turn'] and
            board_for(room)['nodes'][player.position]['kind'] == 'camp' and
            room.document.get('camp_arrival_turn') == room.document['turn_number'] and
            room.document.get('bought_turn') != room.document['turn_number'])


def _camp_gift(room, player):
    gift = room.document.get('camp_gift') or {}
    return gift if gift.get('seat') == player.seat and gift.get('turn') == room.document['turn_number'] else None


def _buy_crystal(room, player):
    cost = CRYSTAL_COSTS[player.crystals]
    player.coins -= cost
    player.crystals += 1
    room.document['bought_turn'] = room.document['turn_number']
    room.document['camp_gift'] = {'seat': player.seat, 'turn': room.document['turn_number'],
                                  'items': secrets.SystemRandom().sample(list(SHOP), 3)}
    _log(room, f'{player.name}: 루멘 결정 획득 ({player.crystals}/3) · {cost}코인. 보상 아이템을 선택해주세요.')
    player.save()


def _shop_available(room, player):
    prompt = room.document.get('move_prompt') or {}
    return (room.status == 'running' and player.hp > 0 and player.seat == room.document['turn'] and
            not room.document.get('counter_prompt') and not _flag(room, 'hand_tasks', player) and
            board_for(room)['nodes'][player.position]['kind'] == 'shop' and
            (room.document['landed'] or (room.document['move'] and prompt.get('shop') and prompt.get('shop_open'))) and
            room.document.get('shop_bought_turn') != room.document['turn_number'] and
            room.document.get('shop_closed_turn') != room.document['turn_number'])


def _movement_started(room):
    return bool(room.document.get('movement_started') or room.document.get('move') or
                room.document['landed'] or room.document.get('arrival'))


def _shop_offers(room):
    # Stable fallback also covers rooms that were already open before this rule.
    offer = room.document.get('shop_offer') or {}
    if offer.get('turn') == room.document['turn_number']:
        return offer['items']
    return random.Random(f'{room.code}:{room.document["turn_number"]}:shop').sample(list(SHOP), 3)


def _supply_encounter(room, player):
    if (player.hp <= 0 or room.document.get('counter_prompt') or _flag(room, 'hand_tasks', player) or
            not (room.document['landed'] or room.document.get('move_prompt') or room.document.get('arrival') == 'dash')):
        return None
    return supply_at(room, player)


def _can_auto_end_turn(room, player):
    if (room.status != 'running' or not room.document['landed'] or room.document['move'] or
            player.seat != room.document['turn'] or room.document.get('counter_prompt') or
            (room.document.get('event') or {}).get('pending') or
            room.encounters.filter(status='active').exists()):
        return False
    if player.hp <= 0:
        return True
    if (_flag(room, 'hand_tasks', player) or _flag(room, 'item_rewards', player) or _camp_gift(room, player) or
            room.document.get('arrival') in ('charge', 'transfer') or _shop_available(room, player) or _supply_encounter(room, player)):
        return False
    if _camp_available(room, player) and player.crystals < 3 and player.coins >= CRYSTAL_COSTS[player.crystals]:
        return False
    return not challenge_targets(room, player) or bool(room.document.get('challenge_declined'))


def test_player_seat(room, data):
    """Seat impersonation is available only on explicitly enabled test servers."""
    if not getattr(settings, 'PARTY_TEST_CONTROLS', False):
        raise Http404
    seat = data.get('seat')
    if seat == 'spectator':
        return None
    seat = _number(seat, 0, 3)
    player = room.players.filter(seat=seat).first()
    if not player:
        raise ValueError('참여 중인 플레이어를 선택해주세요.')
    return player


def _turn_order(room, players):
    seats = [p.seat for p in players]
    order = []
    for seat in room.document.get('turn_order', seats):
        if seat in seats and seat not in order:
            order.append(seat)
    return order + [seat for seat in seats if seat not in order]


def serialize_room(room, token=''):
    _ensure_board(room)
    card_catalog(room, refresh=True)
    players = list(room.players.select_related('character'))
    actor = next((p for p in players if token and secrets.compare_digest(token, p.token)), None)
    encounter = room.encounters.filter(status='active').select_related('session').first()
    moving = next((p for p in players if p.seat == room.document['turn']), None)
    revealing = bool(room.document['move'] and room.document['move'].get('reveal_pending'))
    revealing = revealing or bool((room.document.get('event') or {}).get('pending'))
    state = {
        'code': room.code, 'name': room.name, 'status': room.status, 'version': room.version,
        'expired': room.expires_at <= timezone.now(), 'expires_at': room.expires_at.isoformat(),
        'url': reverse('battlelog:partyRoom', args=[room.code]), 'board': display_board(room),
        'round': room.document['round'], 'turn_number': room.document['turn_number'],
        'turn_order': _turn_order(room, players),
        'order_change': room.document.get('order_change'),
        'movement_power': _movement_power(room), 'attacker_bonus': _attacker_bonus(room),
        'turn': room.document['turn'], 'move': room.document['move'], 'landed': room.document['landed'],
        'server_time': int(timezone.now().timestamp() * 1000),
        'dice_roll': room.document.get('dice_roll'),
        'move_path': room.document.get('move_path'),
        'movement_preview': movement_preview(room, moving) if moving else None,
        'move_prompt': room.document.get('move_prompt'), 'arrival': room.document.get('arrival'),
        'can_charge': room.document.get('arrival') == 'charge' and room.document.get('charge_used_turn') != room.document['turn_number'],
        'can_transfer': room.document.get('arrival') == 'transfer',
        'transfer_to': board_for(room)['nodes'][moving.position].get('transfer_to') if moving and room.document.get('arrival') == 'transfer' else None,
        'last_action': room.document.get('last_action'), 'event': display_event(room, room.document.get('event')),
        'challenge_targets': challenge_targets(room, actor) if actor and actor.seat == room.document['turn'] and not encounter and not revealing else [],
        'can_buy_item': bool(actor and not encounter and _shop_available(room, actor)),
        'shop_offers': _shop_offers(room) if moving and _shop_available(room, moving) else [],
        'can_auto_end_turn': bool(actor and _can_auto_end_turn(room, actor)),
        'can_buy_crystal': bool(actor and _camp_available(room, actor)),
        'camp_gift': _camp_gift(room, actor) if actor else None,
        'camp_purchase_done': room.document.get('bought_turn') == room.document['turn_number'],
        'camp_stop_shortfall': (max(0, CRYSTAL_COSTS[moving.crystals] - moving.coins - (3 if moving.position == home_for(room, moving.seat) else 0)) if moving and moving.crystals < 3 else 0),
        'challenge_declined': bool(room.document.get('challenge_declined')),
        'winners': room.document['winners'], 'log': room.document['log'],
        'roadblocks': room.document.get('roadblocks', []),
        'supplies': room.document.get('supplies', []),
        'supply_encounter': _supply_encounter(room, actor) if actor and actor.seat == room.document['turn'] and not encounter and not revealing and room.status == 'running' else None,
        'counter_prompt': room.document.get('counter_prompt'),
        'can_act': bool(not revealing and room.status == 'running' and room.expires_at > timezone.now() and actor and actor.hp > 0 and actor.seat == room.document['turn'] and not encounter and not room.document.get('counter_prompt') and not _flag(room, 'hand_tasks', actor)),
        'can_use_items': bool(not revealing and not _movement_started(room) and room.status == 'running' and room.expires_at > timezone.now() and actor and actor.hp > 0 and actor.seat == room.document['turn'] and not encounter and not room.document.get('counter_prompt') and not _flag(room, 'hand_tasks', actor) and room.document.get('item_turn') != room.document['turn_number']),
        'me': None, 'players': [], 'battle': None,
        'test_controls': bool(getattr(settings, 'PARTY_TEST_CONTROLS', False)),
    }
    for player in players:
        current_hp, fp = player.hp, player.prepared_fp
        if encounter:
            if player.pk == encounter.player1_id:
                current_hp, fp = encounter.session.player1_hp, encounter.session.player1_fp
            elif player.pk == encounter.player2_id:
                current_hp, fp = encounter.session.player2_hp, encounter.session.player2_fp
        state['players'].append({
            'seat': player.seat, 'name': player.name, 'hp': current_hp, 'max_hp': player.max_hp,
            'fp': fp, 'prepared_fp': player.prepared_fp, 'coins': player.coins,
            'crystals': player.crystals, 'position': player.position, 'ready': player.ready,
            'forward_exits': forward_exits(room, player),
            'is_host': player.is_host, 'home': home_for(room, player.seat),
            'poison_turns': room.document.get('poison_turns', {}).get(str(player.seat), 0),
            'double_dice': bool(room.document.get('double_dice', {}).get(str(player.seat))),
            'cloaked': bool(_flag(room, 'cloaks', player)),
            'shielded': bool(_flag(room, 'shields', player)),
            'revenge_ready': bool(_flag(room, 'revenge', player)),
            'free_direction': bool(_flag(room, 'free_direction', player)),
            'smart_dice': bool(_flag(room, 'smart_dice', player)),
            'ko_status': ('resting' if (_flag(room, 'knockouts', player) or {}).get('rested') else 'knocked_out') if player.hp <= 0 else None,
            'hand_limit': hand_limit_for_hp(player.character, current_hp),
            'character': {
                'id': player.character_id, 'name': player.character.name, 'img': player.character.img,
                'body_img': player.character.body_img or '', 'sd_img': player.character.sd_img or '',
                'icon_img': player.character.icon_img or '',
            },
        })
    if actor:
        state['me'] = {'seat': actor.seat, 'is_host': actor.is_host, 'items': [_item_key(item) for item in actor.items]}
        reward = room.document.get('item_rewards', {}).get(str(actor.seat))
        state['item_reward'] = _item_key(reward) if reward else None
        state['item_targets'] = _item_targets(room, actor)
        state['hand_task'] = _flag(room, 'hand_tasks', actor)
    if encounter:
        session = encounter.session
        participates = bool(actor and actor.pk in (encounter.player1_id, encounter.player2_id))
        result = {key: value for key, value in encounter.result.items() if key != 'winner'} if encounter.result.get('version') == session.version else {}
        state['battle'] = {
            'id': encounter.pk, 'p1': encounter.player1.seat, 'p2': encounter.player2.seat,
            'version': session.version, 'exchanges': encounter.snapshot.get('exchanges', 0),
            'completed': party_battle_complete(encounter),
            'result': result, 'can_confirm': participates and party_battle_complete(encounter),
            'view_token': session.view_token,
            'calculator_url': reverse('battlelog:sessionDetail', args=[session.view_token]),
        }
        if participates:
            state['battle']['control_token'] = session.control_token
            state['battle']['calculator_url'] = reverse('battlelog:sessionControl', args=[session.view_token, session.control_token])
    return state


def _prepare(room, player):
    player.prepared_fp += 2 + _attacker_bonus(room)


def _random_item():
    return list(SHOP)[secrets.randbelow(len(SHOP))]


def _give_item(room, player):
    item = _random_item()
    if len(player.items) < 3:
        player.items.append(item)
    else:
        room.document.setdefault('item_rewards', {})[str(player.seat)] = item
    _log(room, f'{player.name}: {display_board(room)["shop"][item]["label"]} 획득' + (' · 가방이 가득 차 교체할 아이템을 선택해주세요.' if len(player.items) == 3 and room.document.get('item_rewards', {}).get(str(player.seat)) else '.'))


def _event(room, player):
    key = secrets.choice(list(EVENTS))
    label, description = EVENTS[key]
    started = int(timezone.now().timestamp() * 1000)
    duration = max(0, int(getattr(settings, 'PARTY_EVENT_REVEAL_MS', 2400)))
    path = room.document.get('move_path') or {}
    walking = 0 if path.get('teleport') or not duration else max(0, len(path.get('nodes', [])) - 1) * 500
    room.document['event'] = {'id': key, 'label': label, 'description': description,
                              'seat': player.seat, 'version': room.version + 1,
                              'image': next(e['image'] for e in BOARD['events'] if e['id'] == key),
                              'show_at': started + walking, 'reveal_until': started + walking + duration,
                              'pending': bool(duration)}
    room.document['event'] = display_event(room, room.document['event'])
    if not duration:
        _apply_event(room, player)


def _apply_event(room, player):
    room.document['event'] = display_event(room, room.document['event'])
    event = room.document['event']
    key, label, description = event['id'], event['label'], event['description']
    event.update(pending=False, applied_at=int(timezone.now().timestamp() * 1000))
    event['effect_until'] = event['applied_at'] + 1800
    _log(room, f'이벤트 · {label}: {description}')
    previous_position = player.position
    if key in ('rich', 'home'):
        player.save()
        for other in room.players.all():
            if key == 'rich':
                other.coins += 2
            else:
                other.position = home_for(room, other.seat)
            other.save()
        player.refresh_from_db()
        if key == 'home':
            if player.position != previous_position:
                room.document['movement_visit'] = room.document.get('movement_visit', 0) + 1
            room.document['previous_positions'] = {}
            room.document['headings'] = {}
            room.document['arrival'] = None
            # Returning home is not a camp arrival and cannot grant rewards or a purchase.
            room.document['camp_arrival_turn'] = None
    elif key == 'swamp':
        player.prepared_fp -= 2
    elif key == 'chance':
        player.prepared_fp += 9
    elif key == 'hurry':
        room.document['double_dice'] = {str(p.seat): True for p in room.players.all()}
    elif key == 'box':
        while len(player.items) < 3:
            player.items.append(_random_item())
    elif key == 'poison':
        room.document['poison_turns'] = {str(p.seat): 3 for p in room.players.all()}


def _land(room, player):
    room.document['challenge_declined'] = False
    room.document['move'] = None
    room.document['move_prompt'] = None
    room.document['arrival'] = None
    room.document['landed'] = True
    kind = board_for(room)['nodes'][player.position]['kind']
    _log(room, f'{player.name}: {board_for(room)["nodes"][player.position]["label"]} 도착.')
    if kind == 'camp':
        room.document['camp_arrival_turn'] = room.document['turn_number']
        if player.position == home_for(room, player.seat):
            player.coins += 3
            _give_item(room, player)
        if _camp_available(room, player) and player.crystals < 3 and player.coins >= CRYSTAL_COSTS[player.crystals]:
            _buy_crystal(room, player)
    elif kind == 'dash':
        room.document['landed'] = False
        room.document['arrival'] = 'dash'
        _log(room, f'{player.name}: 질주! 주사위를 한 번 더 자동으로 굴립니다.')
    elif kind == 'charge':
        if room.document.get('charge_used_turn') != room.document['turn_number']:
            room.document['arrival'] = 'charge'
    elif kind == 'transfer':
        room.document['arrival'] = 'transfer'
    elif kind == 'prepare':
        _prepare(room, player)
        _log(room, f'{player.name}: FP +{2 + _attacker_bonus(room)}.')
    elif kind == 'disaster':
        _damage(room, player, 300)
    elif kind == 'fortune':
        dice = secrets.randbelow(3) + 1
        player.coins += dice
        _log(room, f'{player.name}: 횡재 주사위 {dice}, 코인 +{dice}.')
    elif kind == 'event':
        _event(room, player)
    player.save()


def _begin_turn(room, player):
    room.document.pop('dice_roll', None)
    room.document.pop('camp_gift', None)
    room.document.pop('fought_here', None)
    room.document.pop('supply_visits', None)
    room.document['movement_visit'] = 0
    player.battle_immune = False
    room.document.get('cloaks', {}).pop(str(player.seat), None)
    if player.hp <= 0:
        knockout = room.document.setdefault('knockouts', {}).setdefault(str(player.seat), {'rested': False})
        if not knockout['rested']:
            knockout['rested'] = True
            _log(room, f'{player.name}: 기절로 이번 턴은 쉽니다.')
        else:
            player.hp = min(player.max_hp, ((player.max_hp + 199) // 200) * 100)
            room.document['knockouts'].pop(str(player.seat))
            _set_flag(room, 'passive_states', player, initial_passive_state_for_character(player.character))
            _log(room, f'{player.name}: 현재 위치에서 HP {player.hp}로 부활, 패시브를 초기화했습니다.')
            _hand_task(room, player, '부활')
    poison = room.document.get('poison_turns', {}).get(str(player.seat), 0)
    if poison:
        _damage(room, player, 500)
        room.document['poison_turns'][str(player.seat)] = poison - 1
        _log(room, f'{player.name}: 식중독 500 데미지 · 남은 {poison - 1}턴.')
    player.save()
    room.document.update({'move': None, 'move_prompt': None, 'arrival': None, 'landed': player.hp <= 0,
                          'boost': 0, 'camp_arrival_turn': None, 'movement_started': False,
                          'challenge_declined': False,
                          'shop_offer': {'turn': room.document['turn_number'], 'items': secrets.SystemRandom().sample(list(SHOP), 3)}})


def _start_battle(room, player, target, counter=False):
    if target.pk == player.pk or not _targetable(room, target) or player.hp <= 0:
        raise ValueError('현재 교전할 수 없는 상대입니다.')
    if player.position != target.position or (not counter and target.seat not in challenge_targets(room, player)):
        raise ValueError('도착하거나 지나치는 칸의 상대에게 도전할 수 있습니다.')
    room.document['challenge_declined'] = False
    session = BattleSession.objects.create(
        session_type=BattleSession.SESSION_PARTY, view_token=generate_token(), control_token=generate_token(),
        player1_name=player.name, player2_name=target.name,
        player1_character=player.character, player2_character=target.character,
        player1_initial_hp=player.max_hp, player2_initial_hp=target.max_hp,
        player1_hp=player.hp, player2_hp=target.hp,
        player1_fp=player.prepared_fp + _attacker_bonus(room), player2_fp=target.prepared_fp,
        player1_passive_state=copy.deepcopy(_flag(room, 'passive_states', player) if _flag(room, 'passive_states', player) is not None else initial_passive_state_for_character(player.character)),
        player2_passive_state=copy.deepcopy(_flag(room, 'passive_states', target) if _flag(room, 'passive_states', target) is not None else initial_passive_state_for_character(target.character)), expires_at=room.expires_at,
    )
    PartyEncounter.objects.create(room=room, session=session, player1=player, player2=target,
        snapshot={'hp': [player.hp, target.hp], 'fp': [player.prepared_fp, target.prepared_fp],
                  'visit': _battle_visit(room, player),
                  'attacker_bonus': _attacker_bonus(room), 'turn': room.document['turn_number'], 'exchanges': 0,
                  'counter': counter, 'counter_prompt': copy.deepcopy(room.document.get('counter_prompt')) if counter else None})
    for participant in (player, target):
        participant.prepared_fp = 0
        participant.save()
    _log(room, f'{player.name} ↔ {target.name}: 최대 두 번의 공방을 시작합니다.')


def _resume_after_battle(room, encounter=None):
    if room.document.get('counter_prompt'):
        return
    attacker = room.players.get(seat=room.document['turn'])
    if attacker.hp <= 0:
        room.document.update({'move': None, 'move_prompt': None, 'arrival': None, 'landed': True})
        return
    if not room.document['move']:
        return
    room.document['move_prompt'] = _passing_prompt(room, attacker)
    _start_move_path(room, attacker)
    _advance_forced_path(room, attacker)


def complete_exchange(session, body):
    """Called while the calculator row is locked; never acquire a room lock here."""
    encounter = PartyEncounter.objects.get(session=session, status='active')
    count = encounter.snapshot.get('exchanges', 0)
    if body.get('expected_exchange') != count or party_battle_complete(encounter):
        raise ValueError('공방 횟수가 바뀌었습니다. 화면을 갱신해주세요.')
    encounter.snapshot['exchanges'] = count + 1
    encounter.snapshot['completed'] = count + 1 >= 2 or session.player1_hp <= 0 or session.player2_hp <= 0
    encounter.result = {}
    encounter.save(update_fields=['snapshot', 'result'])
    return session


def _battle_damage(session, encounter):
    """Count effective, non-undone HP damage, including buffered calculator entries."""
    events = {}
    for event in recent_battle_event_payloads(session.pk, limit=None):
        key = str(event.get('event_uid') or event['id'])
        if key not in events or event.get('undone'):
            events[key] = event
    received = [0, 0]
    seen = [False, False]
    limits = [encounter.player1.max_hp, encounter.player2.max_hp]
    for event in events.values():
        if event.get('type') != 'hp' or event.get('target') not in ('p1', 'p2'):
            continue
        index = 0 if event['target'] == 'p1' else 1
        seen[index] = True
        if event.get('undone'):
            continue
        before, after = event.get('hp_before'), event.get('hp_after')
        if before is not None and after is not None:
            clamp = lambda hp: max(0, min(limits[index], hp))
            received[index] += max(0, clamp(before) - clamp(after))
    for index, hp in enumerate([session.player1_hp, session.player2_hp]):
        if not seen[index]:
            received[index] = max(0, encounter.snapshot['hp'][index] - max(0, min(limits[index], hp)))
    return list(reversed(received))


def _confirm_battle(room, player, encounter, body):
    if player.pk not in (encounter.player1_id, encounter.player2_id):
        raise PermissionDenied('교전 참가자만 결과를 확인할 수 있습니다.')
    session = BattleSession.objects.select_for_update().get(pk=encounter.session_id)
    encounter.refresh_from_db()
    if not party_battle_complete(encounter):
        raise ValueError('계산기에서 공방을 완료해주세요. 첫 공방에서 기절하면 바로 종료됩니다.')
    if body.get('battle_version') != session.version:
        raise PartyConflict('계산기 상태가 바뀌었습니다. 현재 체력을 확인해주세요.')
    participants = [encounter.player1, encounter.player2]
    encounter.result = {'version': session.version, 'confirmed': [player.seat]}
    dealt = _battle_damage(session, encounter)
    encounter.result['damage'] = dealt
    encounter.result['damage_coins'] = [damage // 500 * 2 for damage in dealt]
    for participant, hp in zip(participants, [session.player1_hp, session.player2_hp]):
        participant.hp = max(0, min(participant.max_hp, hp))
        participant.battle_immune = False
    for participant, damage, coins in zip(participants, dealt, encounter.result['damage_coins']):
        participant.coins += coins
        if coins:
            _log(room, f'{participant.name}: 교전 피해 {damage} · {coins}코인 획득.')
    for index, participant in enumerate(participants):
        if encounter.snapshot['hp'][index] > 0 and participant.hp <= 0:
            _knock_out(room, participant, participants[1 - index])
        passive = session.player1_passive_state if index == 0 else session.player2_passive_state
        _set_flag(room, 'passive_states', participant, copy.deepcopy(passive))
    for participant in participants:
        participant.save()
    encounter.status = 'finished'
    if not encounter.snapshot.get('counter'):
        visit = encounter.snapshot.get('visit', _battle_visit(room, participants[0]))
        fought = room.document.get('fought_here') or {}
        if fought.get('visit') != visit:
            fought = {'visit': visit, 'targets': []}
        if participants[1].seat not in fought['targets']:
            fought['targets'].append(participants[1].seat)
        room.document['fought_here'] = fought
    encounter.finished_at = timezone.now()
    session.expires_at = timezone.now()
    session.save(update_fields=['expires_at', 'updated_at'])
    _log(room, '교전 결과 제출 완료. 남은 HP를 지도에 반영하고 FP를 초기화했습니다.')
    defender, attacker = participants[1], participants[0]
    if _flag(room, 'revenge', defender):
        room.document['revenge'].pop(str(defender.seat))
        if defender.hp > 0 and _targetable(room, attacker) and defender.position == attacker.position:
            room.document['counter_prompt'] = {'seat': defender.seat, 'target': attacker.seat, 'battle_id': encounter.pk}
            _log(room, f'{defender.name}: {attacker.name}에게 반격하거나 놓아줄 수 있습니다.')
    encounter.save(update_fields=['result', 'status', 'finished_at'])
    if encounter.status == 'finished':
        _resume_after_battle(room, encounter)


def perform_party_action(code, token, body):
    with transaction.atomic():
        room = PartyRoom.objects.select_for_update().get(code=code)
        _ensure_board(room)
        _live(room)
        player = room_player(room, token)
        if not player:
            raise PermissionDenied('참가자 권한이 필요합니다.')
        if body.get('expected_version') != room.version:
            raise PartyConflict('방 상태가 바뀌었습니다. 화면을 갱신해주세요.')
        action = body.get('action')
        encounter = room.encounters.filter(status='active').first()
        if action == 'ready' and room.status == 'lobby':
            player.ready = not player.ready
            player.save()
        elif action == 'start' and room.status == 'lobby':
            if not player.is_host:
                raise PermissionDenied('방장만 시작할 수 있습니다.')
            if room.players.count() < 2 or room.players.filter(ready=False).exists():
                raise ValueError('2명 이상 참여하고 모두 준비를 완료해야 합니다.')
            room.status = 'running'
            _log(room, '파티 시작! 각자 자기 턴에 코인 1개를 받습니다.')
            first = room.players.first()
            room.document['turn_order'] = list(room.players.values_list('seat', flat=True))
            room.document['turn'] = first.seat
            first.coins += 1
            _begin_turn(room, first)
        elif action in ('confirm_battle', 'cancel_battle') and encounter:
            if action == 'confirm_battle':
                _confirm_battle(room, player, encounter, body)
            else:
                if not player.is_host:
                    raise PermissionDenied('방장만 교전을 취소할 수 있습니다.')
                session = BattleSession.objects.select_for_update().get(pk=encounter.session_id)
                encounter.status = 'cancelled'
                encounter.finished_at = timezone.now()
                encounter.save(update_fields=['status', 'finished_at'])
                session.expires_at = timezone.now()
                session.save(update_fields=['expires_at'])
                for participant, fp in zip([encounter.player1, encounter.player2], encounter.snapshot['fp']):
                    participant.prepared_fp = fp
                    participant.save()
                _log(room, '방장이 교전을 취소했습니다. 시작 전 상태를 유지합니다.')
                if encounter.snapshot.get('counter_prompt'):
                    room.document['counter_prompt'] = encounter.snapshot['counter_prompt']
                _resume_after_battle(room, encounter)
        elif action in ('counterattack', 'skip_counter') and room.document.get('counter_prompt'):
            prompt = room.document['counter_prompt']
            if room.status != 'running' or encounter:
                raise ValueError('현재 반격할 수 없습니다.')
            if player.seat != prompt['seat']:
                raise PermissionDenied('반격 권한이 있는 플레이어만 선택할 수 있습니다.')
            if action == 'counterattack':
                target = room.players.select_related('character').get(seat=prompt['target'])
                _start_battle(room, player, target, counter=True)
            room.document.pop('counter_prompt')
            if action == 'skip_counter':
                _resume_after_battle(room)
        else:
            if room.status != 'running' or encounter:
                raise ValueError('현재 진행할 수 없는 행동입니다.')
            if player.seat != room.document['turn']:
                raise PermissionDenied('자기 턴에만 행동할 수 있습니다.')
            if room.document.get('counter_prompt'):
                raise ValueError('상대의 반격 선택을 기다려주세요.')
            if player.hp <= 0 and action not in ('end_turn', 'auto_end_turn'):
                raise ValueError('기절한 상태에서는 행동할 수 없습니다. 쉬는 턴을 마쳐주세요.')
            if _flag(room, 'hand_tasks', player) and action != 'ack_hand' and player.hp > 0:
                raise ValueError('손패를 모두 교체한 뒤 완료를 눌러주세요.')
            move = room.document['move']
            landed = room.document['landed']
            kind = board_for(room)['nodes'][player.position]['kind']
            prompt = room.document.get('move_prompt')
            event = room.document.get('event') or {}
            if event.get('pending'):
                if action != 'resolve_event' or body.get('event_version') != event['version'] or int(timezone.now().timestamp() * 1000) < event['reveal_until']:
                    raise ValueError('이벤트 카드를 표시하고 있습니다. 잠시 후 효과가 적용됩니다.')
                _apply_event(room, player)
                player.save()
            elif move and move.get('reveal_pending'):
                if action != 'advance' or int(timezone.now().timestamp() * 1000) < room.document['dice_roll']['end_at']:
                    raise ValueError('주사위 결과를 표시하고 있습니다. 잠시 후 이동을 시작합니다.')
                move.pop('reveal_pending')
                _start_move_path(room, player)
                _advance_forced_path(room, player)
            elif action == 'ack_hand' and _flag(room, 'hand_tasks', player):
                task = _flag(room, 'hand_tasks', player)
                if body.get('task_version') != task['version']:
                    raise PartyConflict('손패 교체 안내가 바뀌었습니다. 다시 확인해주세요.')
                room.document['hand_tasks'].pop(str(player.seat))
                _log(room, f'{player.name}: 손패 교체 완료.')
            elif action in ('attack_supply', 'skip_supply') and _supply_encounter(room, player):
                crate = _supply_encounter(room, player)
                if body.get('crate_id') != crate['id']:
                    raise PartyConflict('보급함이 바뀌었습니다. 현재 보급함을 확인해주세요.')
                if action == 'attack_supply':
                    speeds, damage = validate_supply_combo(body)
                    actual = min(crate['hp'], damage)
                    crate['hp'] -= actual
                    _log(room, f'{player.name}: 보급함에 카드 {len(speeds)}장 사용 · {actual}피해 (남은 HP {crate["hp"]}).')
                    if crate['hp'] == 0:
                        room.document['supplies'].remove(crate)
                        player.coins += 2
                        player.save(update_fields=['coins'])
                        _log(room, f'{player.name}: 보급함 파괴 · 2코인 획득.')
                finish_supply_visit(room, player, crate)
                if move:
                    room.document['move_prompt'] = _passing_prompt(room, player)
                    _start_move_path(room, player)
                    _advance_forced_path(room, player)
            elif action == 'roll' and not move and not landed:
                if _supply_encounter(room, player):
                    raise ValueError('보급함을 공격하거나 지나갈지 먼저 선택해주세요.')
                room.document['movement_started'] = True
                if player.hp <= 0:
                    raise ValueError('KO 상태에서는 이동할 수 없습니다.')
                double = room.document.get('double_dice', {}).pop(str(player.seat), False)
                smart = room.document.get('smart_dice', {}).pop(str(player.seat), None)
                dice_values = [smart if index == 0 and smart else secrets.randbelow(6) + 1 for index in range(2 if double else 1)]
                bonus = _movement_power(room) + room.document.pop('boost', 0)
                started_at = int(timezone.now().timestamp() * 1000)
                duration = max(0, int(getattr(settings, 'PARTY_ROLL_REVEAL_MS', 3200)))
                phase_at = lambda milliseconds: started_at + round(milliseconds * duration / 3200)
                room.document['dice_roll'] = {
                    'seat': player.seat, 'turn_number': room.document['turn_number'],
                    'version': room.version + 1, 'dice_values': dice_values, 'bonus': bonus,
                    'total': sum(dice_values) + bonus, 'started_at': started_at,
                    'settle_at': phase_at(900), 'number_at': phase_at(1250),
                    'add_at': phase_at(1700), 'count_at': phase_at(2050), 'total_at': phase_at(2500),
                    'end_at': started_at + duration,
                }
                room.document['move'] = {'dice': dice_values[0], 'dice_values': dice_values,
                                         'bonus': bonus, 'remaining': sum(dice_values) + bonus,
                                         'free_direction': bool(room.document.get('free_direction', {}).pop(str(player.seat), False)),
                                         'roll_version': room.version + 1, 'reveal_pending': duration > 0}
                room.document['arrival'] = None
                _log(room, f'{player.name}: 주사위 {" + ".join(map(str, dice_values))} · 추가 이동 {bonus}.')
                _start_move_path(room, player)
                _advance_forced_path(room, player)
            elif action == 'move' and move and not prompt:
                node = _number(body.get('node'), 0, len(board_for(room)['nodes']) - 1)
                if node not in forward_exits(room, player):
                    raise ValueError('표시된 진행 방향으로만 이동할 수 있습니다.')
                _start_move_path(room, player)
                _step(room, player, node)
                _advance_forced_path(room, player)
            elif action == 'advance' and move and not prompt:
                if len(forward_exits(room, player)) != 1:
                    raise ValueError('분기점에서는 지도 화살표로 방향을 선택해주세요.')
                _start_move_path(room, player)
                _advance_forced_path(room, player)
            elif action == 'continue_move' and move and prompt:
                room.document['move_prompt'] = None
                _start_move_path(room, player)
                _advance_forced_path(room, player)
            elif action == 'open_shop' and move and prompt and prompt.get('shop') and kind == 'shop':
                prompt['shop_open'] = True
                _log(room, f'{player.name}: 통과 중 상점을 열었습니다. 남은 이동은 유지됩니다.')
            elif action == 'stop_home' and move and prompt and (prompt.get('own_camp') or prompt.get('shared_camp')):
                _start_move_path(room, player)
                _land(room, player)
            elif action in ('transfer', 'skip_transfer') and landed and room.document.get('arrival') == 'transfer':
                if action == 'transfer':
                    target = board_for(room)['nodes'][player.position]['transfer_to']
                    _start_move_path(room, player)
                    player.position = target
                    room.document['movement_visit'] = room.document.get('movement_visit', 0) + 1
                    player.save(update_fields=['position'])
                    room.document['move_path']['nodes'].append(target)
                    room.document['move_path']['teleport'] = True
                    room.document.get('previous_positions', {}).pop(str(player.seat), None)
                    ring = '내순환' if board_for(room)['nodes'][target]['ring'] == 'inner' else '외순환'
                    _log(room, f'{player.name}: 교체 · {ring}으로 이동했습니다.')
                room.document['arrival'] = None
            elif action == 'charge' and landed and room.document.get('arrival') == 'charge':
                if room.document.get('charge_used_turn') == room.document['turn_number'] or player.hp <= 0:
                    raise ValueError('이번 턴의 돌격 이동을 이미 사용했습니다.')
                target = room.players.filter(seat=_number(body.get('target'), 0, 3)).exclude(pk=player.pk).first()
                if not target or not _targetable(room, target):
                    raise ValueError('이동할 상대를 선택해주세요.')
                _start_move_path(room, player)
                if player.position != target.position:
                    room.document['movement_visit'] = room.document.get('movement_visit', 0) + 1
                player.position = target.position
                room.document['move_path']['nodes'].append(player.position)
                room.document['move_path']['teleport'] = True
                room.document.get('previous_positions', {}).pop(str(player.seat), None)
                room.document['charge_used_turn'] = room.document['turn_number']
                _log(room, f'{player.name}: {target.name}의 위치로 돌격!')
                _land(room, player)
            elif action == 'skip_charge' and landed and room.document.get('arrival') == 'charge':
                room.document['arrival'] = None
            elif action == 'skip_challenge' and challenge_targets(room, player):
                room.document['challenge_declined'] = True
            elif action == 'challenge' and (landed or prompt or room.document.get('arrival') == 'dash'):
                target = room.players.select_related('character').filter(seat=_number(body.get('target'), 0, 3)).first()
                if not target:
                    raise ValueError('상대 플레이어를 선택해주세요.')
                _start_battle(room, player, target)
            elif action == 'buy_crystal' and _camp_available(room, player) and player.crystals < 3:
                cost = CRYSTAL_COSTS[player.crystals]
                if player.coins < cost or room.document.get('bought_turn') == room.document['turn_number']:
                    raise ValueError('코인이 부족하거나 이번 턴에 이미 결정을 구매했습니다.')
                _buy_crystal(room, player)
            elif action in ('choose_camp_gift', 'skip_camp_gift') and _camp_gift(room, player):
                if _flag(room, 'item_rewards', player):
                    raise ValueError('기존 거점 보상 아이템을 먼저 처리해주세요.')
                if action == 'choose_camp_gift':
                    item = body.get('item')
                    if not isinstance(item, str) or item not in _camp_gift(room, player)['items']:
                        raise ValueError('제시된 보상 아이템 중 하나를 선택해주세요.')
                    if len(player.items) < 3:
                        player.items.append(item)
                        player.save()
                    else:
                        _set_flag(room, 'item_rewards', player, item)
                    _log(room, f'{player.name}: 승점 구매 보상 · {display_board(room)["shop"][item]["label"]} 선택.')
                room.document.pop('camp_gift')
            elif action == 'buy_item' and _shop_available(room, player):
                item = _item_key(body.get('item'))
                if (not isinstance(item, str) or item not in _shop_offers(room) or len(player.items) >= 3 or
                    player.coins < SHOP[item]['price'] or room.document.get('shop_bought_turn') == room.document['turn_number']):
                    raise ValueError('구매할 수 없습니다. 코인과 아이템 상한(3개)을 확인해주세요.')
                player.coins -= SHOP[item]['price']
                player.items.append(item)
                room.document['shop_bought_turn'] = room.document['turn_number']
                _log(room, f'{player.name}: {display_board(room)["shop"][item]["label"]} 구매 · {SHOP[item]["price"]}코인.')
                player.save()
                if move and prompt:
                    room.document['move_prompt'] = _passing_prompt(room, player)
                    _start_move_path(room, player)
                    _advance_forced_path(room, player)
            elif action == 'skip_shop' and _shop_available(room, player):
                room.document['shop_closed_turn'] = room.document['turn_number']
                if move and prompt:
                    room.document['move_prompt'] = None
                    _start_move_path(room, player)
                    _advance_forced_path(room, player)
            elif action == 'claim_item' and room.document.get('item_rewards', {}).get(str(player.seat)):
                item = _item_key(room.document['item_rewards'][str(player.seat)])
                if body.get('discard') is not True:
                    index = _number(body.get('index'), 0, len(player.items) - 1)
                    player.items[index] = item
                    player.save()
                room.document['item_rewards'].pop(str(player.seat))
            elif action == 'use_item':
                _use_item(room, player, body)
            elif action in ('end_turn', 'auto_end_turn') and landed:
                if action == 'auto_end_turn' and not _can_auto_end_turn(room, player):
                    raise ValueError('남은 이동과 선택을 먼저 완료해주세요.')
                if room.document.get('arrival') == 'transfer':
                    raise ValueError('다른 순환로로 교체할지 먼저 선택해주세요.')
                if player.hp > 0 and _supply_encounter(room, player):
                    raise ValueError('보급함을 공격하거나 지나갈지 먼저 선택해주세요.')
                if player.hp > 0 and room.document.get('item_rewards', {}).get(str(player.seat)):
                    raise ValueError('획득한 아이템을 교체하거나 받지 않기를 선택해주세요.')
                if player.hp > 0 and _camp_gift(room, player):
                    raise ValueError('승점 구매 보상 아이템을 먼저 선택해주세요.')
                players = list(room.players.all())
                order = _turn_order(room, players)
                by_seat = {p.seat: p for p in players}
                index = order.index(player.seat)
                if index == len(players) - 1:
                    if any(p.crystals >= 3 for p in players):
                        best = max((p.crystals, p.coins) for p in players)
                        room.document['winners'] = [p.seat for p in players if (p.crystals, p.coins) == best]
                        room.status = 'finished'
                        _log(room, '파티 종료! 결정 수와 남은 코인으로 순위를 결정했습니다.')
                    else:
                        room.document['round'] += 1
                        added = spawn_supplies(room)
                        if added:
                            _log(room, f'보급함 {len(added)}개 등장! 지도에서 위치를 확인하세요.')
                        next_order = sorted(order, key=lambda seat: (-by_seat[seat].prepared_fp, -by_seat[seat].hp))
                        room.document['turn_order'] = next_order
                        room.document['order_change'] = {
                            'round': room.document['round'], 'from': order, 'to': next_order,
                            'version': room.version + 1,
                        } if next_order != order else None
                        order = next_order
                        index = -1
                        _log(room, '다음 라운드 순서: ' + ' → '.join(by_seat[seat].name for seat in order) + ' · FP, 체력 순')
                if room.status == 'running':
                    next_player = by_seat[order[(index + 1) % len(order)]]
                    room.document['turn'] = next_player.seat
                    room.document['turn_number'] += 1
                    next_player.coins += 1
                    _begin_turn(room, next_player)
            else:
                raise ValueError('현재 진행할 수 없는 행동입니다.')
        room.document['last_action'] = {'seat': player.seat, 'action': action, 'version': room.version + 1}
        _save_room(room)
        return room
