"""Transactional adapters; the automatic engine starts only after confirmation."""
import copy
import secrets
from types import SimpleNamespace
from django.core.exceptions import PermissionDenied
from django.db import transaction
from .models import LumenSimulatorSession
from .preparation import apply_preparation


def state_from_preparation(preparation, names):
    from .simulator_services import _player_skeleton, _character_payload, _card_payload, _initial_turn_changes, _initial_counter_revisions
    state = {'turn': 1, 'phase': 'lumen', 'priority_player': secrets.choice(('p1', 'p2')),
             'timer': {'started_at': None, 'duration_seconds': 10}, 'turn_changes': _initial_turn_changes(), 'counter_revisions': _initial_counter_revisions(), 'players': {}}
    state['status'] = {s: {'requested': s == state['priority_player'], 'done': False} for s in ('p1', 'p2')}
    for side, entry in preparation['players'].items():
        snapshot, active = entry['registered'], entry['active']
        catalog = snapshot['catalog']
        trait = SimpleNamespace(**catalog[str(active['trait_card_id'])])
        char_data = {**{k: '' for k in ('img', 'sd_img', 'body_img', 'icon_img', 'color')}, **snapshot['character']}
        character = SimpleNamespace(**char_data)
        deck = SimpleNamespace(id=snapshot.get('deck_id'), name=snapshot.get('name', ''), schema_version=2, character=character, trait_card=trait, trait_card_id=trait.id)
        player = _player_skeleton(side, names[side], deck)
        from deck.game_validation import _character_deck_rules
        deck.character_id = character.id
        player['deck_rules'] = _character_deck_rules(deck)
        player['zones']['character'].append(_character_payload(character, side))
        player['zones']['passive'].append(_card_payload(trait, side, f'{side}-passive-1'))
        index = 0
        for row in active['cards']:
            card = SimpleNamespace(**catalog[str(row['card_id'])])
            for n in range(row['count']):
                zone = 'ultimate' if card.ultimate else 'hand' if n < row.get('hand', 0) else 'side' if n < row.get('hand', 0) + row.get('side', 0) else 'list'
                index += 1
                player['zones'][zone].append(_card_payload(card, side, f'{side}-card-{index}', face_up=zone in ('list', 'ultimate')))
        state['players'][side] = player
    return state


def perform_simulator_preparation(session, body):
    from .simulator_services import role_for_token, simulator_session_is_expired, simulator_session_expires_at
    with transaction.atomic():
        locked = LumenSimulatorSession.objects.select_for_update().select_related('ruleset_release').get(pk=session.pk)
        side = role_for_token(locked, body.get('seat', ''), body.get('seat_token', ''))
        if side not in ('p1', 'p2') or simulator_session_is_expired(locked) or getattr(locked, 'player1_controller' if side == 'p1' else 'player2_controller') != 'human':
            raise PermissionDenied()
        document = copy.deepcopy(locked.document)
        preparation = document.get('preparation')
        if not preparation:
            raise ValueError('이전 형식의 대전은 새 대전을 만들어 준비해주세요.')
        ruleset = locked.ruleset_release.snapshot if locked.ruleset_release_id else None
        state = document['state']
        finished = bool((state.get('engine') or {}).get('winner')) or any(p.get('hp', 1) <= 0 for p in state['players'].values())
        ai_sides = [s for s in ('p1', 'p2') if getattr(locked, 'player1_controller' if s == 'p1' else 'player2_controller') == 'ai']
        updated, start = apply_preparation(preparation, side, body, ruleset=ruleset, finished=finished, ai_sides=ai_sides)
        if updated is preparation:
            return locked
        if updated['game_number'] != preparation['game_number']:
            document.setdefault('games', []).append({k: copy.deepcopy(document.get(k)) for k in ('preparation', 'initial_state', 'state', 'events')})
            document['events'] = []
            for p in document['state']['players'].values():
                p.update(hp=0, initial_hp=0, passive_state={}, zones={z: [] for z in p['zones']})
            document['initial_state'] = copy.deepcopy(document['state'])
        if start:
            state = state_from_preparation(updated, {'p1': locked.player1_name, 'p2': locked.player2_name})
            if locked.mode == 'automatic':
                from .automatic_services import initialize_automatic_document
                initialized = initialize_automatic_document(state, locked.ruleset_release, seed=f'{locked.view_token}:game:{updated["game_number"]}', settings=document.get('pending_settings'))
                initialized.update({k: document[k] for k in ('games', 'ai_policy', 'pending_settings') if k in document})
                document = initialized
            else:
                document.update(initial_state=copy.deepcopy(state), state=state, events=[])
        document['preparation'] = updated
        locked.document = document
        locked.version += 1
        locked.expires_at = simulator_session_expires_at()
        locked.save(update_fields=['document', 'version', 'expires_at', 'updated_at'])
        return locked
