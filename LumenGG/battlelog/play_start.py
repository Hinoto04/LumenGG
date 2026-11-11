"""Shared entry for creating simulator sessions.

Used by the legacy start page (form), the game client lobby (JSON) and the
mobile API (JWT), so deck permission and trait checks stay identical.
"""

from urllib.parse import urlencode

from django.urls import reverse

from deck.models import Deck

from .models import LumenSimulatorSession
from .simulator_services import can_view_deck_for_simulator, create_simulator_session

DECK_NOT_FOUND = '덱 ID를 확인해주세요.'


def _load_deck(deck_id):
    try:
        return Deck.objects.select_related('character', 'author').get(id=int(deck_id), deleted=False)
    except (Deck.DoesNotExist, ValueError, TypeError):
        raise ValueError(DECK_NOT_FOUND) from None


def start_session(
    user,
    *,
    player1_deck_id,
    player2_deck_id,
    mode='manual',
    opponent='human',
    player1_name='',
    player2_name='',
    ready_timeout_seconds='30',
    effect_timeout_seconds='60',
    regulation_version_id=None,
    player2_user=None,
):
    """Create a session or raise ValueError with a user-facing (Korean) message.

    ``player2_user`` is the second human's own account (rooms and quick match:
    each player picks only their own deck, so each deck is checked against the
    player who chose it). Without it both decks are checked against ``user``.

    Errors that concern one deck are joined with spaces, matching the order the
    legacy start page reported them.
    """
    player1_deck = _load_deck(player1_deck_id)
    player2_deck = _load_deck(player2_deck_id)
    errors = []
    if not can_view_deck_for_simulator(user, player1_deck):
        errors.append('플레이어1 덱을 볼 권한이 없습니다.')
    if not can_view_deck_for_simulator(player2_user if player2_user is not None else user, player2_deck):
        errors.append('플레이어2 덱을 볼 권한이 없습니다.')
    if errors:
        raise PermissionError(errors)

    from deck.regulations import accessible_versions
    from deck.traits import trait_choices

    for deck in (player1_deck, player2_deck):
        if not deck.trait_card_id and trait_choices(deck.character_id).count() > 1:
            raise ValueError('덱 작성 화면에서 사용할 특성을 선택해주세요.')
    regulation_version = None
    if regulation_version_id:
        regulation_version = accessible_versions(user).filter(pk=regulation_version_id).first()
        if not regulation_version:
            raise ValueError('선택할 수 없는 규정입니다.')
    player2_controller = (
        LumenSimulatorSession.CONTROLLER_AI if opponent == 'ai' else LumenSimulatorSession.CONTROLLER_HUMAN
    )
    return create_simulator_session(
        player1_name,
        player2_name,
        player1_deck,
        player2_deck,
        mode=mode,
        regulation_version=regulation_version,
        player2_controller=player2_controller,
        ready_timeout_seconds=ready_timeout_seconds,
        effect_timeout_seconds=effect_timeout_seconds,
    )


# Passive panels the game client renders itself (play/src/components/
# CharacterPassive.tsx and the configurable controls in Manual.tsx). Matched
# against the panel HTML the server sends, like the client does.
GAME_CLIENT_PASSIVE_MARKERS = (
    'data-config-passive-panel', 'data-nia-panel', 'data-cmyk-panel',
    'data-yohan-panel', 'data-tao-panel',
)


def uses_custom_passive_ui(session):
    """Whether a seat's character needs a passive panel only the legacy simulator has.

    Configurable passives (``options.controls``) and the ported character
    panels (Nia, CMYK, Yohan, Tao) work in the game client. A new
    character-specific template keeps opening the legacy page until it is
    ported too.
    """
    from types import SimpleNamespace

    from card.models import Character
    from deck.traits import setup_character

    from .services import _passive_ui

    state = (session.document or {}).get('state') or {}
    for player in (state.get('players') or {}).values():
        selected = player.get('character') or {}
        character = Character.objects.filter(pk=selected.get('id')).first()
        if not character:
            continue
        if selected.get('trait_card_id'):
            character = setup_character(character, SimpleNamespace(
                id=selected['trait_card_id'], trait_config=selected.get('trait_config', {}),
            ))
        ui = _passive_ui(character, context='simulator') or {}
        if (ui.get('options') or {}).get('controls'):
            continue
        html = str(ui.get('html') or '')
        if not html and not ui.get('js'):
            continue
        if not any(marker in html for marker in GAME_CLIENT_PASSIVE_MARKERS):
            return True
    return False


def opens_in_game_client(session, *, legacy=False):
    """Automatic sessions always; manual ones unless the legacy page is needed or asked for."""
    if session.mode == LumenSimulatorSession.MODE_AUTOMATIC:
        return True
    return not legacy and not uses_custom_passive_ui(session)


def play_url(view_token, seat='', seat_token=''):
    """Address of the game client (play/) for an automatic session."""
    query = {'game': view_token}
    if seat in ('p1', 'p2') and seat_token:
        query.update(seat=seat, token=seat_token)
    return f'{reverse("battlelog:play")}?{urlencode(query)}'


def session_links(session):
    """Seat and spectator links of a new automatic session, for the creator only."""
    links = {
        'view_token': session.view_token,
        'seats': {'p1': session.player1_token},
        'urls': {
            'p1': play_url(session.view_token, 'p1', session.player1_token),
            'viewer': play_url(session.view_token),
        },
    }
    if session.player2_controller == LumenSimulatorSession.CONTROLLER_HUMAN:
        links['seats']['p2'] = session.player2_token
        links['urls']['p2'] = play_url(session.view_token, 'p2', session.player2_token)
    return links
