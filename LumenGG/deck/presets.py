"""Publish reviewed common regulations by stable original card codes."""
import copy
import json
from datetime import date
from itertools import combinations
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction

from card.models import Card
from .models import Regulation, RegulationVersion
from .regulations import DEFAULT_RULES, normalize_regulation_rules


PRESET_ROOT = Path(__file__).with_name('regulation_presets')


def load_preset(key):
    # Only packaged presets are accepted, never an arbitrary filesystem path.
    if key not in {p.stem for p in PRESET_ROOT.glob('*.json')}:
        raise ValidationError('등록되지 않은 금제 규칙입니다.')
    return json.loads((PRESET_ROOT / f'{key}.json').read_text(encoding='utf-8'))


def rules_for_preset(preset):
    banned = preset['banned_cards']
    groups = preset['choose_one_groups']
    references = banned + [card for group in groups for card in group['cards']]
    cards = {card.code: card for card in Card.objects.filter(code__in=[r['code'] for r in references])}
    missing = sorted({r['code'] for r in references} - cards.keys())
    if missing:
        raise ValidationError('금제 대상 카드가 없습니다: ' + ', '.join(missing))
    for reference in references:
        card = cards[reference['code']]
        if card.name != reference['name']:
            raise ValidationError(f"금제 카드 이름을 확인해주세요: {reference['code']}")
    scope = preset['scope']
    pairs = []
    seen = set()
    for group in groups:
        ids = [cards[r['code']].pk for r in group['cards']]
        if len(ids) < 2 or len(ids) != len(set(ids)):
            raise ValidationError('택1 묶음에는 서로 다른 카드가 2종 이상 필요합니다.')
        # A forbidden all-of-N combination would still permit two cards from
        # a three/four-card group. Pairwise combinations enforce choose-one.
        for pair in combinations(ids, 2):
            key = tuple(sorted(pair))
            if key not in seen:
                seen.add(key)
                pairs.append({'card_ids': list(pair), 'scope': scope})
    return normalize_regulation_rules({
        **copy.deepcopy(DEFAULT_RULES),
        'bans': [{'card_ids': [cards[r['code']].pk], 'scope': scope} for r in banned],
        'combinations': pairs,
    })


@transaction.atomic
def publish_preset(key):
    preset = load_preset(key)
    rules = rules_for_preset(preset)
    effective_date = date.fromisoformat(preset['effective_date']) if preset.get('effective_date') else None
    # Serializing against the oldest common rule also avoids duplicate preset
    # publication when two management commands are run concurrently.
    Regulation.objects.select_for_update().filter(owner__isnull=True).order_by('pk').first()
    existing = RegulationVersion.objects.select_related('regulation').filter(
        regulation__owner__isnull=True, regulation__name=preset['name'], version=preset['version'],
    ).first()
    if existing:
        if existing.rules != rules or existing.effective_date != effective_date or existing.source != preset.get('source', ''):
            raise ValidationError('같은 이름과 버전으로 다른 규칙이 게시되어 있습니다. 기존 규칙은 변경하지 않습니다.')
        return existing, False
    regulation = Regulation.objects.filter(owner__isnull=True, name=preset['name']).first()
    if not regulation:
        regulation = Regulation.objects.create(name=preset['name'])
    version = RegulationVersion.objects.create(regulation=regulation, version=preset['version'],
        effective_date=effective_date, source=preset.get('source', ''), rules=rules)
    return version, True
