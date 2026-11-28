"""대전 진행 방식(단판·매치·무한)과 같은 상대와 이어 하는 게임의 전적.

덱 준비가 있는 대전은 한 판이 끝나면 같은 상대와 다음 게임을 이어 할 수 있다
(``preparation_action: next_game``). 퀵 매치는 시작할 때 방식을 고르고, 같은 방식을
고른 플레이어끼리만 짝을 짓는다. 방식은 세션 문서 ``match.format``에 남긴다.

- single: 단판. 한 판이 끝나면 대전도 끝난다.
- bo3: 3판 2선승. 먼저 2승한 쪽이 매치를 이긴다(무승부 판은 승수에 넣지 않는다).
- endless: 무한. 원할 때까지 다음 게임을 이어 한다.

``match``가 없는 세션(방·AI 대전·예전 세션)은 예전처럼 다음 게임을 제한하지 않는다.
"""

MATCH_SINGLE = 'single'
MATCH_BEST_OF_THREE = 'bo3'
MATCH_ENDLESS = 'endless'
MATCH_FORMATS = (MATCH_SINGLE, MATCH_BEST_OF_THREE, MATCH_ENDLESS)
# 방식을 보내지 않는 예전 앱의 퀵 매치는 예전처럼 다음 게임을 제한하지 않는다.
DEFAULT_QUICK_FORMAT = MATCH_ENDLESS
WINS_TO_TAKE = {MATCH_BEST_OF_THREE: 2}


def normalize_match_format(value, default=DEFAULT_QUICK_FORMAT):
    value = str(value or '').strip() or default
    if value not in MATCH_FORMATS:
        raise ValueError('대전 진행 방식이 올바르지 않습니다.')
    return value


def game_winner(state):
    """끝난 게임의 승자('p1'·'p2'), 무승부·진행 중이면 None."""
    state = state or {}
    winner = (state.get('engine') or {}).get('winner')
    if winner in ('p1', 'p2'):
        return winner
    players = state.get('players') or {}
    if (state.get('engine') or {}).get('status') == 'finished' or not state.get('engine'):
        down = [side for side in ('p1', 'p2') if side in players and (players[side].get('initial_hp') or 0) > 0 and players[side].get('hp', 1) <= 0]
        if len(down) == 1:
            return 'p2' if down[0] == 'p1' else 'p1'
    return None


def game_finished(state):
    state = state or {}
    engine = state.get('engine') or {}
    if engine.get('status') == 'finished' or engine.get('winner'):
        return True
    players = (state.get('players') or {}).values()
    return any((p.get('initial_hp') or 0) > 0 and p.get('hp', 1) <= 0 for p in players)


def match_view(document):
    """화면에 보여 줄 진행 방식과 전적. 방식이 없는 세션은 None."""
    document = document or {}
    match = document.get('match') or {}
    fmt = match.get('format')
    if fmt not in MATCH_FORMATS:
        return None
    preparation = document.get('preparation') or {}
    wins = {'p1': 0, 'p2': 0}
    played = 0
    for game in document.get('games') or []:
        played += 1
        winner = game_winner(game.get('state'))
        if winner:
            wins[winner] += 1
    current_finished = preparation.get('status') == 'playing' and game_finished(document.get('state'))
    if current_finished:
        played += 1
        winner = game_winner(document.get('state'))
        if winner:
            wins[winner] += 1
    target = WINS_TO_TAKE.get(fmt)
    if fmt == MATCH_SINGLE:
        over = played >= 1 and current_finished
        match_winner = game_winner(document.get('state')) if over else None
    elif target:
        leader = next((side for side, count in wins.items() if count >= target), None)
        over = bool(leader)
        match_winner = leader
    else:
        over = False
        match_winner = None
    return {
        'format': fmt,
        'game_number': preparation.get('game_number') or 1,
        'wins': wins,
        'wins_needed': target,
        'over': over,
        'winner': match_winner,
    }


def ensure_next_game_allowed(document):
    view = match_view(document)
    if not view or not view['over']:
        return
    if view['format'] == MATCH_SINGLE:
        raise ValueError('단판 대전은 다음 게임이 없습니다. 새 대전을 시작해 주세요.')
    raise ValueError('매치가 끝났습니다. 새 대전을 시작해 주세요.')
