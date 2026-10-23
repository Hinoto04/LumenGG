import copy
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render
from deck.validation import validate, snapshot_deck
from deck.regulations import accessible_versions
from .models import TournamentDeckSubmission


def detail(request, id, submission_id):
    from .views import _can_view_submitted_deck, _is_operator
    submission = get_object_or_404(TournamentDeckSubmission.objects.select_related('participant__tournament', 'deck__character', 'deck__regulation_version'), pk=submission_id, participant__tournament_id=id)
    tournament = submission.participant.tournament
    if not _can_view_submitted_deck(request.user, tournament, submission.deck):
        raise PermissionDenied()
    snapshot = copy.deepcopy(submission.snapshot or snapshot_deck(submission.deck, tournament.regulation_version))
    can_private = _is_operator(request.user, tournament) or submission.participant.user_id == getattr(request.user, 'id', None)
    catalog = snapshot['catalog']
    def entries(rows):
        return [{**catalog[str(row['card_id'])], 'count': row['count']} for row in rows if str(row['card_id']) in catalog]
    trait = catalog.get(str(snapshot.get('trait_card_id')))
    sections = [{'title': '등록 특성', 'cards': [{**trait, 'count': 1}] if trait else []}, {'title': '등록 기본 구성', 'cards': entries(snapshot['cards'])}]
    if can_private or (snapshot.get('regulation_rules') or {}).get('reserve_public'):
        sections.append({'title': '등록 교체 덱', 'cards': entries(snapshot['reserve_cards'])})
    versions = accessible_versions(request.user)
    current_report = None
    if request.GET.get('regulation_version_id'):
        version = get_object_or_404(versions, pk=request.GET['regulation_version_id'])
        snapshot['regulation_version_id'] = version.pk
        snapshot['regulation_rules'] = version.rules
        current_report = validate(snapshot)
    visible_submission = copy.copy(submission)
    if not can_private:
        visible_submission.validation = {**submission.validation, 'issues': []}
        if current_report:
            current_report['issues'] = []
    return render(request, 'tournament/submission_v2.html', {'submission': visible_submission, 'tournament': tournament, 'sections': sections, 'current_report': current_report, 'versions': versions})
