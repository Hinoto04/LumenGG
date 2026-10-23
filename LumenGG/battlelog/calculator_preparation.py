import copy
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied
from deck.traits import setup_character, selected_trait
from deck.validation import card_snapshot, baseline
from .preparation import create_preparation, apply_preparation, preparation_view


def resolved_character(session, side):
    character = getattr(session, 'player1_character' if side == 'p1' else 'player2_character')
    if not character:
        return None
    preparation = session.preparation or {}
    selected = (preparation.get('traits') or {}).get(side)
    frozen_character = (preparation.get('characters') or {}).get(side)
    if preparation.get('players'):
        player = preparation['players'].get(side) or {}
        active, registered = player.get('active') or {}, player.get('registered') or {}
        selected = (registered.get('catalog') or {}).get(str(active.get('trait_card_id')))
        frozen_character = registered.get('character')
    if selected:
        if frozen_character:
            character = SimpleNamespace(**frozen_character)
        return setup_character(character, SimpleNamespace(**selected))
    return character


def set_standalone_traits(session, ids):
    from .services import initial_hp_for_character, initial_passive_state_for_character
    session.preparation = {'traits': {}, 'characters': {}}
    for side, trait_id in zip(('p1', 'p2'), ids):
        prefix = 'player1' if side == 'p1' else 'player2'
        character = getattr(session, prefix + '_character')
        trait = selected_trait(character.id, trait_id, required=True)
        setattr(session, prefix + '_trait_card', trait)
        session.preparation['traits'][side] = card_snapshot(trait)
        session.preparation['characters'][side] = {'id': character.id, 'name': character.name, 'datas': copy.deepcopy(character.datas),
                                                 **{k: getattr(character, k, '') for k in ('img', 'sd_img', 'body_img', 'icon_img', 'color')}}
        resolved = setup_character(character, trait)
        hp = initial_hp_for_character(resolved)
        setattr(session, prefix + '_initial_hp', hp)
        setattr(session, prefix + '_hp', hp)
        setattr(session, prefix + '_passive_state', initial_passive_state_for_character(resolved))


def initialize_tournament_preparation(session):
    tournament = session.tournament_match.round.tournament
    modern = bool(tournament.regulation_version_id)
    registrations = {}
    for side in ('p1', 'p2'):
        participant = getattr(session.tournament_match, 'player1' if side == 'p1' else 'player2')
        submissions = list(participant.deck_submissions.select_related('deck')) if participant else []
        modern = modern or any(s.deck.schema_version >= 2 for s in submissions)
        registrations[side] = submissions[0].snapshot if len(submissions) == 1 else None
    if modern and tournament.decklist_required_count:
        session.preparation = create_preparation(registrations)
        for prefix in ('player1', 'player2'):
            setattr(session, prefix + '_hp', 0)
            setattr(session, prefix + '_initial_hp', 0)
            setattr(session, prefix + '_passive_state', {})
        session.save()


def payload(session, user, control_token=''):
    if not (session.preparation or {}).get('players'):
        return None
    from .services import is_tournament_operator, _player_participant_for_target
    tournament = session.tournament_match.round.tournament
    operator = bool(user and is_tournament_operator(user, tournament))
    side = next((s for s in ('p1', 'p2') if (_player_participant_for_target(session, s) and _player_participant_for_target(session, s).user_id == getattr(user, 'id', None))), 'viewer')
    result = preparation_view(session.preparation, side, operator=operator)
    result['can_prepare'] = side in ('p1', 'p2') or operator
    result['role'] = side
    for target in ('p1', 'p2'):
        if target == side or operator:
            participant = _player_participant_for_target(session, target)
            result['players'][target]['submissions'] = [{'id': s.pk, 'name': s.snapshot.get('name', s.deck.name), 'character_id': s.snapshot.get('character_id', s.deck.character_id), 'trait_card_id': s.snapshot.get('trait_card_id'), 'trait_name': (s.snapshot.get('catalog', {}).get(str(s.snapshot.get('trait_card_id'))) or {}).get('name', '미지정')} for s in participant.deck_submissions.select_related('deck')]
    return result


def perform(session, body, user):
    from .services import tournament_match_is_open, is_tournament_operator, _player_participant_for_target
    if not session.tournament_match_id or not (session.preparation or {}).get('players'):
        raise ValueError('대회 준비 세션이 아닙니다.')
    side = body.get('target')
    participant = _player_participant_for_target(session, side)
    if side not in ('p1', 'p2') or not participant or not (participant.user_id == getattr(user, 'id', None) or is_tournament_operator(user, session.tournament_match.round.tournament)):
        raise PermissionDenied()
    if session.tournament_match.round.tournament.status != 'running' or not tournament_match_is_open(session):
        raise PermissionDenied()
    preparation = copy.deepcopy(session.preparation)
    body = {**body, 'expected_version': body.get('preparation_version', body.get('expected_version'))}
    registration = None
    if body.get('preparation_action') == 'select_deck':
        submission = participant.deck_submissions.filter(pk=body.get('submission_id')).first()
        if not submission or not submission.snapshot:
            raise ValueError('제출한 덱을 선택해주세요.')
        registration = submission.snapshot
    preparation, start = apply_preparation(preparation, side, body, registration=registration)
    session.preparation = preparation
    if start:
        from .preparation_services import state_from_preparation
        state = state_from_preparation(preparation, {'p1': session.player1_name, 'p2': session.player2_name})
        from card.models import Character
        for target in ('p1', 'p2'):
            player = state['players'][target]
            prefix = 'player1' if target == 'p1' else 'player2'
            setattr(session, prefix + '_character', Character.objects.get(pk=player['character']['id']))
            setattr(session, prefix + '_trait_card_id', player['character']['trait_card_id'])
            for field in ('hp', 'initial_hp', 'fp', 'passive_state'):
                setattr(session, prefix + '_' + field, player[field])
        from .services import ensure_current_set
        current = ensure_current_set(session)
        current.setup_snapshot = copy.deepcopy(preparation)
        for prefix in ('player1', 'player2'):
            setattr(current, prefix + '_start_hp', getattr(session, prefix + '_hp'))
        current.save()
    session.save()
    return session
