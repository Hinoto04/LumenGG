"""The first offline Party board. Card play and hand management stay at the table."""
import math
from django.templatetags.static import static


def octagon_point(index, size, radius):
    cut = radius * math.tan(math.pi / 8)
    vertices = [(-cut, -radius), (cut, -radius), (radius, -cut), (radius, cut),
                (cut, radius), (-cut, radius), (-radius, cut), (-radius, -cut)]
    edge = index * 8 / size
    start = int(edge)
    fraction = edge - start
    a, b = vertices[start], vertices[(start + 1) % 8]
    return (a[0] + (b[0] - a[0]) * fraction, a[1] + (b[1] - a[1]) * fraction)

TILE_TYPES = {
    'camp': {'label': '거점', 'icon': '⌂', 'description': '도착 시, 코인을 지불하고 승점을 구매 가능'},
    'dash': {'label': '질주', 'icon': '»', 'description': '도착하면 주사위를 한 번 더 굴려 이동합니다.'},
    'charge': {'label': '돌격', 'icon': '⚔', 'description': '다른 플레이어를 선택해 그 위치로 이동하고 교전할 수 있습니다. 이동하지 않고 턴을 마칠 수도 있습니다.'},
    'shop': {'label': '상점', 'icon': '▣', 'description': '아이템을 1개 구입할 수 있습니다.'},
    'prepare': {'label': '준비', 'icon': '↗', 'description': '도착 시, FP 획득'},
    'disaster': {'label': '재앙', 'icon': '!', 'description': '도착한 플레이어는 300 데미지를 받습니다.'},
    'fortune': {'label': '횡재', 'icon': '●', 'description': '도착 시, 1~3코인을 받습니다.'},
    'event': {'label': '이벤트', 'icon': '?', 'description': '도착 시, 무작위 이벤트가 발생합니다.'},
    'transfer': {'label': '교체', 'icon': '⇄', 'description': '도착 시, 다른 순환로로 이동할지 선택합니다.'},
}
SHOP = {
    'heal': {'label': '붕대', 'description': 'HP 200 회복', 'target': 'self'},
    'heal_kit': {'label': '회복 키트', 'description': 'HP 400 회복', 'target': 'self'},
    'prepare': {'label': '전투 준비', 'description': 'FP 4 획득', 'target': 'self'},
    'hurry': {'label': '빨리 빨리', 'description': '다음 이동 주사위는 2개', 'target': 'self'},
    'brick': {'label': '벽돌 투척', 'description': '4칸 내 캐릭터 하나에게 500 데미지', 'target': 'player', 'range': 4, 'damage': 500},
    'gun': {'label': '조잡한 총', 'description': '6칸 내 캐릭터 하나에게 300 데미지', 'target': 'player', 'range': 6, 'damage': 300},
    'redirect': {'label': '이쪽으로', 'description': '다음 이동 시작 방향을 자유롭게 결정', 'target': 'self'},
    'roadblock': {'label': '통행 금지', 'description': '8칸 내 지점에 설치. 지나려는 캐릭터를 그 칸에 정지시키고 제거', 'target': 'tile', 'range': 8},
    'shield': {'label': '효과 보호막', 'description': '다음 아이템 피해를 막음', 'target': 'self'},
    'training': {'label': '기술 수련', 'description': '손패를 모두 버리고 최대 손패까지 획득', 'target': 'self'},
    'cloak': {'label': '투명 망토', 'description': '다음 자기 턴까지 전투 및 아이템의 대상이 되지 않음', 'target': 'self'},
    'smart_dice': {'label': '스마트 주사위', 'description': '다음 이동 주사위 하나의 눈을 1~6으로 지정', 'target': 'number'},
    'revenge': {'label': '너 죽고 나 죽자', 'description': '다음 전투를 받은 뒤 공격자에게 반격 가능', 'target': 'self'},
}
for item in SHOP.values():
    item.update(price=3, image='')
OUTER = ['camp', 'fortune', 'prepare', 'disaster', 'dash', 'shop'] * 4
INNER = ['charge', 'event', 'prepare', 'disaster', 'charge', 'event', 'fortune', 'dash']
CRYSTAL_COSTS = [6, 10, 15]
EVENTS = {
    'discard': ('패 말살', '모든 플레이어는 실물 패에서 무작위로 3장씩 버리세요. 패가 3장 미만이면 모두 버립니다.'),
    'rich': ('부자가 될거야', '모든 플레이어가 2코인씩 얻습니다.'),
    'swamp': ('끈적한 늪', '이벤트를 밟은 플레이어 FP -2.'),
    'hurry': ('빨리 빨리', '모든 플레이어가 다음 이동 주사위를 2개 굴립니다.'),
    'chance': ('찬스!', '이벤트를 밟은 플레이어 FP +9.'),
    'home': ('모두 제자리로', '모든 플레이어가 자기 거점으로 돌아갑니다. 거점 효과는 발생하지 않습니다.'),
    'box': ('아이템 상자', '이벤트를 밟은 플레이어의 아이템 창이 가득 찰 때까지 무작위 아이템을 받습니다.'),
    'poison': ('식중독', '모든 플레이어는 다음 자기 턴부터 3턴 동안 턴 시작마다 500 데미지를 받습니다.'),
}


def legacy_board():
    nodes = []
    for node_id, kind in enumerate(OUTER + INNER):
        inner = node_id >= 24
        index, size, radius = (node_id - 24, 8, 23) if inner else (node_id, 24, 43)
        # Straight octagonal edges, with stable IDs and exits for existing rooms.
        x, y = octagon_point(index, size, radius)
        exits = [24 + (index + 1) % 8, 24 + (index - 1) % 8] if inner else [(index + 1) % 24, (index - 1) % 24]
        if inner and index % 2 == 0:
            exits.append(index // 2 * 6)
        elif not inner and index % 6 == 0:
            exits.append(24 + index // 6 * 2)
        background = f'camp-{index // 6 + 1}' if kind == 'camp' else kind
        nodes.append({
            'id': node_id, 'kind': kind, **TILE_TYPES[kind], 'exits': exits,
            'background_img': static(f'v2/party-icons/v1/{background}.png'),
            'x': round(50 + x, 2), 'y': round(50 + y, 2), 'ring': 'inner' if inner else 'outer',
        })
    return {'version': 1, 'name': '루멘 순환 광장', 'shape': 'octagon', 'nodes': nodes, 'shop': SHOP,
            'crystal_costs': CRYSTAL_COSTS, 'events': [{'id': key, 'label': value[0], 'description': value[1]} for key, value in EVENTS.items()]}


EVENT_IMAGES = dict(zip(EVENTS, ['hand-annihilation', 'going-to-be-rich', 'sticky-swamp',
    'everyone-hurry', 'chance', 'everyone-go-home', 'item-chest', 'food-poisoning']))


def board():
    # Four interior stops on each outer edge; two on each inner edge.
    outer = ['transfer', 'dash', 'charge', 'prepare', 'disaster', 'camp', 'fortune', 'dash', 'shop', 'disaster'] * 4
    inner = ['transfer', 'charge', 'event', 'dash', 'disaster', 'prepare'] * 4
    inner[5] = inner[17] = 'camp'
    transfer_colors = ('vermilion', 'magenta', 'cobalt', 'slate')
    nodes = []
    for node_id, kind in enumerate(outer + inner):
        inside = node_id >= 40
        index, count, radius, base = (node_id - 40, 24, 43, 40) if inside else (node_id, 40, 43 * 5 / 3, 0)
        x, y = octagon_point(index, count, radius)
        owner = (index - 5) // 10 if not inside and kind == 'camp' else None
        background = f'camp-{owner + 1}' if owner is not None else kind if kind != 'transfer' else None
        tile = {'id': node_id, 'kind': kind, **TILE_TYPES[kind],
                'exits': [base + (index + 1) % count, base + (index - 1) % count],
                'clockwise': base + (index + 1) % count,
                'x': round(50 + x, 2), 'y': round(50 + y, 2),
                'ring': 'inner' if inside else 'outer', 'owner_seat': owner}
        if background:
            tile['background_img'] = static(f'v2/party-icons/v1/{background if owner is not None or kind != "camp" else "camp-1"}.png')
        if inside and kind == 'camp':
            tile.update(shared=True, label='공용 거점', description='통과 중 정지 가능 · 도착 시, 코인을 지불하고 승점을 구매 가능')
            tile['background_img'] = static('v2/party-icons/v2/camp-shared.png')
        if kind == 'transfer':
            pair = index // 6 if inside else index // 10
            tile['transfer_to'] = pair * 10 if inside else 40 + pair * 6
            tile['background_img'] = static(f'v2/party-icons/v2/transfer-{transfer_colors[pair]}.png')
        nodes.append(tile)
    return {'version': 2, 'name': '루멘 순환 광장', 'shape': 'octagon', 'nodes': nodes,
            'homes': [5, 15, 25, 35], 'bounds': {'min': -26, 'max': 126},
            'shop': SHOP, 'crystal_costs': CRYSTAL_COSTS,
            'events': [{'id': key, 'label': value[0], 'description': value[1],
                        'image': static(f'v2/party-events/v1/{EVENT_IMAGES[key]}.png')} for key, value in EVENTS.items()]}


LEGACY_BOARD = legacy_board()
BOARD = board()


def board_for(room):
    return BOARD if room.document.get('board_version', 1) >= 2 else LEGACY_BOARD


def home_for(room, seat):
    return board_for(room).get('homes', [0, 6, 12, 18])[seat]


def range_exits(tile):
    # A transfer counts as one step for item range, but is never a walking road.
    return tile['exits'] + ([tile['transfer_to']] if 'transfer_to' in tile else [])


def nearby(origin, destination, distance, board=None):
    """Range on the current board, including the optional transfer hop."""
    visited = {origin}
    board = board or BOARD
    frontier = {origin}
    for _ in range(distance):
        frontier = {other for here in frontier for other in range_exits(board['nodes'][here])} - visited
        visited |= frontier
    return destination in visited
