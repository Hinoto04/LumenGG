"""Private, versioned pre-game selection shared by calculators and simulators."""
import copy
import hashlib
import json
import uuid
from deck.validation import baseline, validate

SIDES = ('p1', 'p2')


def create_preparation(registrations, *, number=1, ai_sides=()):
    players = {}
    for side in SIDES:
        registered = copy.deepcopy(registrations[side])
        players[side] = {'registered': registered, 'active': baseline(registered) if registered else None, 'ready': side in ai_sides}
    return {'version': 1, 'game_number': number, 'status': 'editing', 'players': players, 'receipts': {}}


def apply_preparation(preparation, side, body, *, ruleset=None, finished=False, ai_sides=(), registration=None):
    if side not in SIDES:
        raise ValueError('자신의 좌석만 준비할 수 있습니다.')
    try:
        request_id = str(uuid.UUID(str(body['request_id'])))
    except (KeyError, ValueError, TypeError) as exc:
        raise ValueError('준비 요청 번호가 올바르지 않습니다.') from exc
    fingerprint = hashlib.sha256(json.dumps({'side': side, 'body': body}, sort_keys=True).encode()).hexdigest()
    old = preparation.get('receipts', {}).get(request_id)
    if old:
        if old != fingerprint:
            raise ValueError('요청 번호를 다른 입력에 재사용할 수 없습니다.')
        return preparation, False
    if body.get('expected_version') != preparation['version']:
        raise ValueError('준비 정보가 변경되었습니다. 최신 상태를 확인해주세요.')
    if body.get('preparation_action') == 'next_game':
        if preparation['status'] != 'playing' or not finished:
            raise ValueError('게임 종료 후 다음 게임을 준비할 수 있습니다.')
        result = next_preparation(preparation, ai_sides=ai_sides)
        result['receipts'][request_id] = fingerprint
        return result, False
    if preparation['status'] != 'editing':
        raise ValueError('게임 시작 후에는 교체할 수 없습니다.')
    action = body.get('preparation_action')
    result = copy.deepcopy(preparation)
    player = result['players'][side]
    if action == 'cancel':
        player['ready'] = False
    elif action == 'select_deck':
        if registration is None or player['ready']:
            raise ValueError('준비 중에 제출 덱을 선택해주세요.')
        player.update(registered=copy.deepcopy(registration), active=baseline(registration))
    elif action in ('save', 'ready'):
        if not player['registered']:
            raise ValueError('제출 덱을 선택해주세요.')
        if player['ready']:
            raise ValueError('준비 완료를 철회한 뒤 수정해주세요.')
        candidate = body.get('active', player['active'])
        report = validate(player['registered'], stage='setup' if action == 'ready' else 'draft', active=candidate, ruleset=ruleset)
        if not report['is_valid']:
            # This response is sent only to the authenticated player making it.
            raise ValueError('; '.join(i['message'] for i in report['issues'] if i['severity'] == 'error'))
        player['active'] = copy.deepcopy(candidate)
        player['ready'] = action == 'ready'
    else:
        raise ValueError('지원하지 않는 준비 요청입니다.')
    start = all(p['ready'] for p in result['players'].values())
    if start:
        # Revalidate both players using the same immutable policy and release.
        for p in result['players'].values():
            report = validate(p['registered'], stage='setup', active=p['active'], ruleset=ruleset)
            if not report['is_valid']:
                raise ValueError('확정할 수 없는 준비 상태입니다.')
        result['status'] = 'playing'
    result['version'] += 1
    result['receipts'][request_id] = fingerprint
    result['receipts'] = dict(list(result['receipts'].items())[-128:])
    return result, start


def next_preparation(previous, *, ai_sides=()):
    result = create_preparation({s: p['registered'] for s, p in previous['players'].items()}, number=previous['game_number'] + 1, ai_sides=ai_sides)
    result['version'] = previous['version'] + 1
    result['receipts'] = copy.deepcopy(previous.get('receipts', {}))
    return result


def preparation_view(preparation, side='viewer', *, operator=False):
    if not preparation:
        return None
    result = {k: preparation[k] for k in ('version', 'game_number', 'status')}
    result['players'] = {}
    for target, player in preparation['players'].items():
        row = {'ready': player['ready']}
        if target == side or operator:
            row.update(registered=copy.deepcopy(player['registered']), active=copy.deepcopy(player['active']))
        elif preparation['status'] == 'playing':
            policy = (player.get('registered') or {}).get('regulation_rules', {})
            if policy.get('reserve_public'):
                row['reserve_cards'] = copy.deepcopy(player['registered']['reserve_cards'])
            if policy.get('swaps_public'):
                # Disclosure of composition never discloses opening hand/side placement.
                row['active'] = {k: copy.deepcopy(player['active'][k]) for k in ('character_id', 'trait_card_id')}
                row['active']['cards'] = [{k: e[k] for k in ('card_id', 'count')} for e in player['active']['cards']]
            visible = {e['card_id'] for e in row.get('reserve_cards', [])}
            visible.update(e['card_id'] for e in row.get('active', {}).get('cards', []))
            if row.get('active', {}).get('trait_card_id'):
                visible.add(row['active']['trait_card_id'])
            if visible:
                row['public_catalog'] = {str(pk): {k: player['registered']['catalog'][str(pk)].get(k) for k in ('name', 'code', 'img_sm')} for pk in visible}
        result['players'][target] = row
    return result
