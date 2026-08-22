import json

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from card.models import Card, Character
from card.search import card_matches_search
from common.language import get_language, javascript_i18n, translated_character_field, ui_text
from deck.models import CardInDeck, Deck

from .event_buffer import recent_battle_event_payloads
from .automatic_services import (
    AutomaticRuntimeFailure,
    active_ai_policy,
    add_client_issue_report,
    add_issue_report,
    advance_ai_session,
    ai_policy_payload,
    automatic_mode_release,
    perform_automatic_command,
    reconcile_automatic_session,
)
from .game.engine import IllegalAction, StaleState
from .models import LumenSimulatorSession
from .presence import battle_presence_counts, simulator_presence_counts
from .realtime import broadcast_battle_session
from .realtime import broadcast_simulator_session
from .services import (
    battle_session_queryset,
    can_control_session,
    can_toggle_sudden_death,
    character_options_for_session,
    create_standalone_session,
    perform_session_action,
    serialize_session,
)
from .simulator_services import (
    can_view_deck_for_simulator,
    create_simulator_session,
    perform_simulator_action,
    role_for_token,
    serialize_simulator_card_metadata,
    serialize_simulator_events,
    serialize_simulator_session,
    simulator_queryset,
)


def _session_queryset():
    return battle_session_queryset()


def _get_session(view_token):
    return get_object_or_404(_session_queryset(), view_token=view_token)


def _json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except json.JSONDecodeError:
        return {}


def sim(req):
    language = get_language(req)
    characters = Character.objects.prefetch_related('translations').order_by('id')
    if req.method == 'POST':
        player1_character = get_object_or_404(Character, id=req.POST.get('player1_character'))
        player2_character = get_object_or_404(Character, id=req.POST.get('player2_character'))
        session = create_standalone_session(
            req.POST.get('player1_name', ''),
            req.POST.get('player2_name', ''),
            player1_character,
            player2_character,
            req.user,
        )
        return redirect('battlelog:sessionControl', view_token=session.view_token, control_token=session.control_token)

    return render(req, 'battlelog/sim_v2.html', {'characters': characters})


def simulatorStart(req):
    language = get_language(req)
    automatic_release = automatic_mode_release()
    active_policy = active_ai_policy() if automatic_release else None
    context = {
        'errors': [],
        'automatic_release': automatic_release,
        'ai_policy': ai_policy_payload(active_policy) if active_policy else None,
    }
    if req.method == 'POST':
        player1_deck_id = req.POST.get('player1_deck', '')
        player2_deck_id = req.POST.get('player2_deck', '')
        try:
            player1_deck = Deck.objects.select_related('character', 'author').get(id=player1_deck_id, deleted=False)
            player2_deck = Deck.objects.select_related('character', 'author').get(id=player2_deck_id, deleted=False)
        except (Deck.DoesNotExist, ValueError, TypeError):
            context['errors'].append('덱 ID를 확인해주세요.')
        else:
            if not can_view_deck_for_simulator(req.user, player1_deck):
                context['errors'].append('플레이어1 덱을 볼 권한이 없습니다.')
            if not can_view_deck_for_simulator(req.user, player2_deck):
                context['errors'].append('플레이어2 덱을 볼 권한이 없습니다.')
            if not context['errors']:
                requested_mode = req.POST.get('mode', 'manual')
                opponent_type = req.POST.get('opponent_type', 'human')
                player2_controller = (
                    LumenSimulatorSession.CONTROLLER_AI
                    if opponent_type == 'ai'
                    else LumenSimulatorSession.CONTROLLER_HUMAN
                )
                try:
                    session = create_simulator_session(
                        req.POST.get('player1_name', ''),
                        req.POST.get('player2_name', ''),
                        player1_deck,
                        player2_deck,
                        mode=requested_mode,
                        player2_controller=player2_controller,
                        ready_timeout_seconds=req.POST.get(
                            'ready_timeout_seconds', '30',
                        ),
                        effect_timeout_seconds=req.POST.get(
                            'effect_timeout_seconds', '60',
                        ),
                    )
                except ValueError as exc:
                    context['errors'].append(str(exc))
                else:
                    return redirect(
                        'battlelog:simulatorSeat',
                        view_token=session.view_token,
                        seat='p1',
                        seat_token=session.player1_token,
                    )

        context.update({
            'player1_name': req.POST.get('player1_name', '플레이어1'),
            'player2_name': req.POST.get('player2_name', '플레이어2'),
            'player1_deck': player1_deck_id,
            'player2_deck': player2_deck_id,
            'mode': req.POST.get('mode', 'manual'),
            'opponent_type': req.POST.get('opponent_type', 'human'),
            'ready_timeout_seconds': req.POST.get(
                'ready_timeout_seconds', '30',
            ),
            'effect_timeout_seconds': req.POST.get(
                'effect_timeout_seconds', '60',
            ),
        })

    context['errors'] = [ui_text(error, language) for error in context['errors']]
    return render(req, 'battlelog/simulator_start_v2.html', context)


@require_GET
def simulatorGuide(req):
    language = get_language(req)
    image_suffix = {
        'en': 'EN',
        'ja': 'JP',
    }.get(language, 'KR')
    guide_images = {
        'move_cards': f'images/가이드1{image_suffix}.png',
        'action_flow': f'images/가이드2{image_suffix}.png',
        'log': f'images/가이드3{image_suffix}.png',
        'passive': f'images/가이드4{image_suffix}.png',
        'card_effect': f'images/가이드5{image_suffix}.png',
    }
    return render(req, 'battlelog/simulator_guide_v2.html', {'guide_images': guide_images})


@require_GET
def simulatorDeckSearch(req):
    query = req.GET.get('q', '').strip()
    query_is_id = query.isdigit()
    if len(query) < 2 and not query_is_id:
        return JsonResponse([], safe=False)

    if query_is_id:
        search_q = Q(id=int(query))
    else:
        search_q = (
            Q(name__icontains=query)
            | Q(author__username__icontains=query)
            | Q(character__name__icontains=query)
        )

    decks = (
        Deck.objects.filter(deleted=False)
        .filter(search_q)
        .select_related('author', 'character')
        .order_by('-created', '-id')[:40]
    )
    if not req.user.is_authenticated or not req.user.is_staff:
        decks = [deck for deck in decks if can_view_deck_for_simulator(req.user, deck)]
        if not query_is_id:
            decks = [
                deck for deck in decks
                if deck.visibility == Deck.VISIBILITY_PUBLIC
                or (req.user.is_authenticated and deck.author_id == req.user.id)
            ]
    else:
        decks = list(decks)

    language = get_language(req)
    data = [
        {
            'id': deck.id,
            'name': deck.name,
            'author': deck.author.username,
            'character': translated_character_field(deck.character, language, 'name'),
            'version': deck.version,
            'visibility': ui_text(deck.get_visibility_display(), language),
            'is_owner': req.user.is_authenticated and deck.author_id == req.user.id,
        }
        for deck in decks[:20]
    ]
    return JsonResponse(data, safe=False)


def _get_simulator_session(view_token):
    return get_object_or_404(simulator_queryset(), view_token=view_token)


def _simulator_event_limit(req):
    try:
        return int(req.GET.get('event_limit') or 150)
    except (TypeError, ValueError):
        return 150


def _simulator_card_ids(req):
    raw_values = req.GET.getlist('ids')
    if not raw_values:
        raw_values = [req.GET.get('ids', '')]
    card_ids = []
    for raw in raw_values:
        for value in str(raw or '').split(','):
            value = value.strip()
            if value:
                card_ids.append(value)
            if len(card_ids) >= 200:
                return card_ids
    return card_ids


def simulatorView(req, view_token):
    return _render_simulator(req, view_token, '', '')


def simulatorSeat(req, view_token, seat, seat_token):
    session = _get_simulator_session(view_token)
    if role_for_token(session, seat, seat_token) not in ('p1', 'p2'):
        raise PermissionDenied()
    return _render_simulator(req, view_token, seat, seat_token)


def simulatorMobileView(req, view_token):
    return _render_simulator(req, view_token, '', '', template_name='battlelog/simulator_mobile_v2.html')


def simulatorMobileSeat(req, view_token, seat, seat_token):
    session = _get_simulator_session(view_token)
    if role_for_token(session, seat, seat_token) not in ('p1', 'p2'):
        raise PermissionDenied()
    return _render_simulator(req, view_token, seat, seat_token, template_name='battlelog/simulator_mobile_v2.html')


def _simulator_page_url(req, view_token, seat, seat_token, mobile=False):
    if seat in ('p1', 'p2') and seat_token:
        route = 'battlelog:simulatorMobileSeat' if mobile else 'battlelog:simulatorSeat'
        return req.build_absolute_uri(reverse(route, kwargs={
            'view_token': view_token,
            'seat': seat,
            'seat_token': seat_token,
        }))
    route = 'battlelog:simulatorMobileView' if mobile else 'battlelog:simulatorView'
    return req.build_absolute_uri(reverse(route, kwargs={'view_token': view_token}))


def _render_simulator(req, view_token, seat, seat_token, template_name='battlelog/simulator_session_v2.html'):
    language = get_language(req)
    session = _get_simulator_session(view_token)
    if role_for_token(session, seat, seat_token) in ('p1', 'p2'):
        was_automatic = session.mode == 'automatic'
        session = reconcile_automatic_session(session, both_players_disconnected=False)
        if session.mode == LumenSimulatorSession.MODE_AUTOMATIC:
            session = advance_ai_session(session)
        if was_automatic and session.mode != 'automatic':
            broadcast_simulator_session(session)
    state = serialize_simulator_session(session, seat, seat_token, language=language, include_events=False)
    context = {
        'session': session,
        'state': state,
        'seat': seat,
        'seat_token': seat_token,
        'view_url': req.build_absolute_uri(state['view_url']),
        'player1_url': req.build_absolute_uri(state['player1_url']) if state.get('player1_url') else '',
        'player2_url': req.build_absolute_uri(state['player2_url']) if state.get('player2_url') else '',
        'desktop_url': _simulator_page_url(req, view_token, seat, seat_token, mobile=False),
        'mobile_url': _simulator_page_url(req, view_token, seat, seat_token, mobile=True),
        'current_url': req.build_absolute_uri(),
        'simulator_i18n': javascript_i18n(language),
    }
    return render(req, template_name, context)


@require_GET
def simulatorState(req, view_token):
    session = _get_simulator_session(view_token)
    seat = req.GET.get('seat', '')
    seat_token = req.GET.get('seat_token', '')
    role = role_for_token(session, seat, seat_token)
    if role in ('p1', 'p2'):
        was_automatic = session.mode == 'automatic'
        session = reconcile_automatic_session(session, both_players_disconnected=False)
        if session.mode == LumenSimulatorSession.MODE_AUTOMATIC:
            session = advance_ai_session(session)
        if was_automatic and session.mode != 'automatic':
            broadcast_simulator_session(session)
    since_version = req.GET.get('since_version')
    if since_version and str(since_version) == str(session.version):
        return JsonResponse({
            'id': session.id,
            'version': session.version,
            'unchanged': True,
            'presence': simulator_presence_counts(session.view_token),
        })
    return JsonResponse(serialize_simulator_session(
        session,
        seat,
        seat_token,
        language=get_language(req),
        include_events=False,
        event_limit=_simulator_event_limit(req),
    ))


@require_GET
def simulatorEvents(req, view_token):
    session = _get_simulator_session(view_token)
    return JsonResponse(serialize_simulator_events(
        session,
        req.GET.get('seat', ''),
        req.GET.get('seat_token', ''),
        language=get_language(req),
        event_limit=_simulator_event_limit(req),
    ))


@require_GET
def simulatorCardMetadata(req, view_token):
    _get_simulator_session(view_token)
    return JsonResponse({
        'cards': serialize_simulator_card_metadata(_simulator_card_ids(req), language=get_language(req)),
    })


@require_POST
def simulatorAction(req, view_token):
    session = _get_simulator_session(view_token)
    body = _json_body(req)
    seat = body.get('seat', '')
    seat_token = body.get('seat_token', '')

    try:
        session = perform_simulator_action(session, body)
    except PermissionDenied:
        return JsonResponse({'ok': False, 'error': ui_text('조작 권한이 없습니다.', get_language(req))}, status=403)
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': ui_text(str(exc), get_language(req))}, status=400)

    broadcast_simulator_session(session)
    return JsonResponse({
        'ok': True,
        'state': serialize_simulator_session(session, seat, seat_token, language=get_language(req), include_events=False),
    })


@require_POST
def simulatorCommand(req, view_token):
    session = _get_simulator_session(view_token)
    body = _json_body(req)
    seat = body.get('seat', '')
    seat_token = body.get('seat_token', '')
    try:
        was_automatic = session.mode == 'automatic'
        session = reconcile_automatic_session(session, both_players_disconnected=False)
        if was_automatic and session.mode != 'automatic':
            broadcast_simulator_session(session)
            return JsonResponse({
                'ok': False,
                'error': '타이머 정산 오류로 세션을 수동 모드로 전환했습니다.',
                'code': 'automatic_fallback',
            }, status=409)
        session = perform_automatic_command(session, body)
        session = advance_ai_session(session)
    except PermissionDenied:
        return JsonResponse({'ok': False, 'error': ui_text('조작 권한이 없습니다.', get_language(req))}, status=403)
    except StaleState as exc:
        latest = _get_simulator_session(view_token)
        return JsonResponse({
            'ok': False,
            'error': str(exc),
            'code': 'stale_state',
            'state': serialize_simulator_session(
                latest, seat, seat_token,
                language=get_language(req), include_events=False,
            ),
        }, status=409)
    except IllegalAction as exc:
        return JsonResponse({'ok': False, 'error': str(exc), 'code': 'illegal_action'}, status=400)
    except AutomaticRuntimeFailure as exc:
        session = _get_simulator_session(view_token)
        broadcast_simulator_session(session)
        return JsonResponse({'ok': False, 'error': str(exc), 'code': 'automatic_fallback'}, status=409)
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)

    broadcast_simulator_session(session)
    return JsonResponse({
        'ok': True,
        'state': serialize_simulator_session(
            session, seat, seat_token, language=get_language(req), include_events=False,
        ),
    })


@require_POST
def simulatorReportIssue(req, view_token):
    session = _get_simulator_session(view_token)
    body = _json_body(req)
    role = role_for_token(session, body.get('seat', ''), body.get('seat_token', ''))
    if role not in ('p1', 'p2'):
        return JsonResponse({'ok': False, 'error': '제보 권한이 없습니다.'}, status=403)
    try:
        report_kind = str(body.get('kind') or 'user').strip()
        if report_kind == 'client_error':
            report, created = add_client_issue_report(
                session, role, body.get('diagnostic'),
                user_agent=req.META.get('HTTP_USER_AGENT', ''),
                user=req.user,
            )
        elif report_kind == 'user':
            requested_report_id = str(
                body.get('report_id')
                or (session.automation_failure or {}).get('report_id')
                or ''
            ).strip()
            report = add_issue_report(
                session, role, body.get('details'), user=req.user,
                report_id=body.get('report_id'),
            )
            created = not bool(requested_report_id)
        else:
            raise ValueError('지원하지 않는 제보 종류입니다.')
    except ValueError as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)
    return JsonResponse({
        'ok': True,
        'report_id': str(report.public_id),
        'status': report.status,
        'created': created,
        'deduplicated': not created,
    })


def sessionDetail(req, view_token):
    return _render_session(req, view_token, '')


def sessionControl(req, view_token, control_token):
    return _render_session(req, view_token, control_token)


def _render_session(req, view_token, control_token):
    language = get_language(req)
    session = _get_session(view_token)
    state = serialize_session(session, req.user, control_token, include_events=False, language=language)
    character_options = character_options_for_session(session, req.user, control_token, language=language)
    context = {
        'session': session,
        'state': state,
        'control_token': control_token,
        'can_control': can_control_session(req.user, session, control_token),
        'can_sudden_death': can_toggle_sudden_death(req.user, session, control_token),
        'character_options': character_options,
        'view_url': req.build_absolute_uri(state['view_url']),
        'control_url': req.build_absolute_uri(state['control_url']),
        'current_url': req.build_absolute_uri(),
        'battle_i18n': javascript_i18n(language),
    }
    return render(req, 'battlelog/session_v2.html', context)


@require_GET
def sessionState(req, view_token):
    session = _get_session(view_token)
    control_token = req.GET.get('control_token', '')
    since_version = req.GET.get('since_version')
    if since_version and str(since_version) == str(session.version):
        return JsonResponse({
            'id': session.id,
            'version': session.version,
            'unchanged': True,
            'presence': battle_presence_counts(session.view_token),
        })
    return JsonResponse(serialize_session(session, req.user, control_token, include_events=False, language=get_language(req)))


@require_GET
def sessionEvents(req, view_token):
    session = _get_session(view_token)
    return JsonResponse({'events': recent_battle_event_payloads(session.id)})


@require_POST
def sessionAction(req, view_token):
    session = _get_session(view_token)
    body = _json_body(req)
    control_token = body.get('control_token', '')

    try:
        session = perform_session_action(session, body, req.user, control_token)
    except PermissionDenied:
        return JsonResponse({'ok': False, 'error': ui_text('조작 권한이 없습니다.', get_language(req))}, status=403)
    except (TypeError, ValueError) as exc:
        return JsonResponse({'ok': False, 'error': ui_text(str(exc), get_language(req))}, status=400)

    broadcast_battle_session(session)
    return JsonResponse({
        'ok': True,
        'state': serialize_session(session, req.user, control_token, include_events=False, language=get_language(req)),
    })


def cardLoad(req):
    keyword = req.GET.get('keyword', '')
    if keyword:
        cards = Card.objects.prefetch_related('translations').order_by('id')
        data = [
            {'name': card.name, 'img': card.img}
            for card in cards
            if card_matches_search(card, keyword, include_keywords=False)
        ]
    else:
        data = []
    return JsonResponse(data, safe=False)

def deckLoad(req):
    id = req.GET.get('id', '')
    try:
        deck = Deck.objects.get(id=id)
    except Deck.DoesNotExist:
        data = {'status': '404'}
    else:
        data = {'status': '200'}
        cards = CardInDeck.objects.filter(deck=deck)
        data['deck'] = list(cards.values('hand','side','count','card__name', 'card__img'))
    return JsonResponse(data)

def stream(req):
    return render(req, 'battlelog/stream.html', {})
