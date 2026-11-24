"""대전 클라이언트용: 효과로 바뀐 카드 수치·판정을 카드마다 알려 준다.

카드 이미지에는 인쇄된 값만 있으므로, 속도·대미지처럼 수정자로 바뀌는 값과
위치·특수 판정처럼 카드에 직접 덮어쓰인 값을 인쇄값과 비교해
``stat_changes``(필드 추가만)로 내려보낸다. 클라이언트는 이를 이미지 위에 덧씌운다.
"""

# 수정자(modifiers)를 거쳐 계산되는 수치. card_stat으로 현재값을 구한다.
NUMERIC_STATS = ('frame', 'damage')
# 카드 dict에 직접 바뀌어 쓰이는 판정(modify_judgment 등).
JUDGMENT_FIELDS = ('pos', 'special', 'hit', 'guard', 'counter', 'g_top', 'g_mid', 'g_bot')
# 효과로 수치가 바뀔 수 있는, 기술을 쓰거나 고르는 존. 덱·브레이크·루멘 존은 보지 않는다.
WATCHED_ZONES = ('battle', 'hand', 'side', 'ultimate')


def _plain(value):
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _number(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


def card_changes(engine, card, owner):
    """카드 하나의 {필드: {'base': 인쇄값, 'current': 현재값}}. 바뀐 것이 없으면 빈 dict."""
    printed = engine._printed_card_snapshot(card)
    changes = {}
    for stat in NUMERIC_STATS:
        base = _number(printed.get(stat))
        if base is None:
            continue
        current = _number(engine.card_stat(card, stat, owner))
        if current is not None and current != base:
            changes[stat] = {'base': base, 'current': current}
    for field in JUDGMENT_FIELDS:
        base = _plain(printed.get(field))
        current = _plain(card.get(field))
        if base != current:
            changes[field] = {'base': base, 'current': current}
    return changes


def collect_card_changes(engine):
    """instance_id → 바뀐 값. 역할에 따른 공개 여부는 상태를 거른 쪽에서 붙일 때 정해진다."""
    result = {}
    players = (engine.state or {}).get('players') or {}
    for owner, player in players.items():
        zones = (player or {}).get('zones') or {}
        for zone in WATCHED_ZONES:
            for card in zones.get(zone) or []:
                if not isinstance(card, dict) or not card.get('instance_id') or not card.get('code'):
                    continue
                try:
                    changes = card_changes(engine, card, owner)
                except Exception:  # 표시용 부가 정보라 계산 실패가 응답을 막지 않는다.
                    continue
                if changes:
                    result[str(card['instance_id'])] = changes
    return result


def attach_card_changes(state, changes):
    """걸러진 상태의 보이는 카드(instance_id가 있는 카드)에만 stat_changes를 붙인다."""
    if not changes:
        return state
    for player in ((state or {}).get('players') or {}).values():
        for cards in ((player or {}).get('zones') or {}).values():
            for card in cards or []:
                if not isinstance(card, dict) or card.get('hidden'):
                    continue
                found = changes.get(str(card.get('instance_id') or ''))
                if found:
                    card['stat_changes'] = found
    return state
