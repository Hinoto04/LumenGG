"""Export what the isolated play dev server needs (read-only).

Reads the active automatic ruleset release, the active AI policy, every card
and character (with translations) and a few public decks for two characters,
and writes them to one JSON file. Nothing is written to the database.

    manage.py export_play_bundle --p1 3 --p2 2 --out ../.temp/play-dev/bundle.json

``scripts/serve_play_dev.py`` loads the file into a separate SQLite database.
"""

import json
from pathlib import Path

from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from card.models import Card, CardTranslation, Character, CharacterTranslation
from deck.game_validation import validate_automatic_deck
from deck.models import Deck

from battlelog.automatic_services import active_ai_policy, automatic_mode_release


def _rows(queryset, nulls=()):
    rows = serializers.serialize('python', queryset)
    for row in rows:
        for field in nulls:
            if field in row['fields']:
                row['fields'][field] = None
    return rows


class Command(BaseCommand):
    help = '플레이 개발 서버용 룰셋·AI 정책·카드·덱을 JSON으로 내보낸다(DB 읽기 전용).'

    def add_arguments(self, parser):
        parser.add_argument('--p1', type=int, default=3, help='플레이어1 캐릭터 ID (기본 3)')
        parser.add_argument('--p2', type=int, default=2, help='플레이어2 캐릭터 ID (기본 2)')
        parser.add_argument('--decks', type=int, default=3, help='캐릭터별로 가져올 공개 덱 수')
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        release = automatic_mode_release()
        if not release:
            raise CommandError('검증된 활성 자동 룰셋 릴리스가 없습니다.')
        policy = active_ai_policy()
        if not policy:
            raise CommandError('검증된 활성 AI 정책이 없습니다.')

        decks = {}
        for side in ('p1', 'p2'):
            character_id = options[side]
            decks[side] = self._decks(character_id, release.snapshot, options['decks'])
            if not decks[side]:
                raise CommandError(f'캐릭터 {character_id}의 자동 모드용 공개 덱을 찾지 못했습니다.')

        bundle = {
            'release': _rows([release], nulls=('created_by',))[0],
            'policy': _rows([policy])[0],
            'characters': _rows(Character.objects.order_by('pk'), nulls=('pack',)),
            'character_translations': _rows(CharacterTranslation.objects.order_by('pk')),
            'cards': _rows(Card.objects.order_by('pk')),
            'card_translations': _rows(CardTranslation.objects.order_by('pk')),
            'decks': decks,
        }
        out = Path(options['out'])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, ensure_ascii=False, default=str), encoding='utf-8')
        self.stdout.write(
            f'{out}: 릴리스 {release.version}, AI {policy.version}, 카드 {len(bundle["cards"])}장, '
            f'덱 p1 {len(decks["p1"])}개 / p2 {len(decks["p2"])}개'
        )

    def _decks(self, character_id, ruleset, limit):
        found = []
        candidates = (
            Deck.objects.filter(deleted=False, visibility=Deck.VISIBILITY_PUBLIC, character_id=character_id)
            .prefetch_related('cids')
            .order_by('-created', '-id')[:60]
        )
        for deck in candidates:
            report = validate_automatic_deck(deck, side='p1', ruleset=ruleset)
            if report.errors:
                continue
            found.append({
                'source_id': deck.pk,
                'name': deck.name,
                'character_id': deck.character_id,
                'trait_card_id': deck.trait_card_id,
                'cards': [
                    {'card_id': entry.card_id, 'count': entry.count, 'hand': entry.hand, 'side': entry.side}
                    for entry in deck.cids.all()
                ],
            })
            if len(found) >= limit:
                break
        return found
