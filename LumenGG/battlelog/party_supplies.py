"""Public supply crates; physical cards and their effects stay at the table."""
import secrets

from .party_board import board_for


SUPPLY_HP = 800


def spawn_supplies(room):
    completed = room.document['round'] - 1
    if completed <= 0 or completed % 3 or room.document.get('supply_spawn_round', 0) >= completed:
        return []
    crates = room.document.setdefault('supplies', [])
    occupied = {crate['node'] for crate in crates}
    occupied.update(room.players.values_list('position', flat=True))
    candidates = [tile['id'] for tile in board_for(room)['nodes'] if tile['id'] not in occupied]
    added = []
    for node in secrets.SystemRandom().sample(candidates, min(3, len(candidates))):
        crate = {'id': f'{completed}:{node}', 'node': node, 'hp': SUPPLY_HP,
                 'max_hp': SUPPLY_HP, 'spawn_round': room.document['round']}
        crates.append(crate)
        added.append(crate)
    room.document['supply_spawn_round'] = completed
    return added


def supply_visit(room, player):
    return [room.document['turn_number'], player.seat, player.position, room.document.get('movement_visit', 0)]


def supply_at(room, player):
    visit = supply_visit(room, player)
    handled = room.document.get('supply_visits', {})
    return next((crate for crate in room.document.get('supplies', [])
                 if crate['node'] == player.position and crate['hp'] > 0 and handled.get(crate['id']) != visit), None)


def finish_supply_visit(room, player, crate):
    room.document.setdefault('supply_visits', {})[crate['id']] = supply_visit(room, player)


def validate_supply_combo(body):
    speeds = body.get('speeds')
    damage = body.get('damage')
    if (not isinstance(speeds, list) or not speeds or
            any(isinstance(speed, bool) or not isinstance(speed, int) for speed in speeds) or
            any(following <= previous for previous, following in zip(speeds, speeds[1:]))):
        raise ValueError('사용한 카드의 속도를 작은 수부터, 같은 수 없이 입력해주세요.')
    if isinstance(damage, bool) or not isinstance(damage, int) or damage <= 0:
        raise ValueError('콤보 보정과 카드 효과를 적용한 최종 피해를 입력해주세요.')
    return speeds, damage
