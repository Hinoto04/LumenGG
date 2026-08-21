"""Read-only AI-vs-AI smoke test against the live card catalog.

This deliberately selects explicit legacy Card columns so it can be run before
the automatic-rule migrations are applied to production.  It never writes to
the database and builds draft definitions only in memory.
"""

import json
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from battlelog.game.catalog import CARD_RUNTIME_FIELDS, EXPECTED_CARD_COUNT
from battlelog.game.drafts import build_effect_draft
from battlelog.game.simulation import run_policy_game
from card.models import Card, Character


PLAYER_SIDES = ('p1', 'p2')
EXCLUDED_DECK_TYPES = {'특성', '토큰'}


def _card_payload(row, side, index, *, face_up=False):
    return {
        **{key: row.get(key) for key in CARD_RUNTIME_FIELDS},
        'instance_id': f'{side}-catalog-{index}',
        'kind': 'card',
        'owner': side,
        'face_up': bool(face_up),
    }


def _state_for_catalog(cards, characters, character_ids, *, priority='p1', rotation=0):
    players = {}
    for side, character_id in zip(PLAYER_SIDES, character_ids):
        character = characters[character_id]
        own_techniques = [
            row for row in cards
            if row.get('character_id') == character_id
            and row.get('type') not in EXCLUDED_DECK_TYPES
            and not row.get('ultimate')
        ]
        target_size = 30 if character_id == 15 else 20
        offset = int(rotation or 0) % max(1, len(own_techniques))
        rotated_own = own_techniques[offset:] + own_techniques[:offset]
        techniques = rotated_own[:target_size]
        if len(techniques) < target_size:
            if character_id == 15:
                # Chimera imports non-neutral, non-ultimate attacks, at most
                # three from each foreign character mark.
                per_character = Counter()
                supplements = []
                for row in cards:
                    mark = row.get('character_id')
                    if (
                        mark in {1, 15}
                        or row.get('type') != '공격'
                        or row.get('ultimate')
                        or per_character[mark] >= 3
                    ):
                        continue
                    per_character[mark] += 1
                    supplements.append(row)
            else:
                supplements = [
                    row for row in cards
                    if row.get('character_id') == 1
                    and row.get('type') not in EXCLUDED_DECK_TYPES
                    and not row.get('ultimate')
                    and row.get('code') not in {item.get('code') for item in techniques}
                ]
            techniques.extend(supplements[:target_size - len(techniques)])
        if len(techniques) != target_size:
            raise CommandError(
                f'캐릭터 {character_id}의 스모크 덱을 구성할 수 없습니다: '
                f'{len(techniques)}/{target_size}장'
            )
        passives = [
            row for row in cards
            if row.get('character_id') == character_id and row.get('type') == '특성'
        ]
        ultimates = [
            row for row in cards
            if row.get('character_id') == character_id and row.get('ultimate')
        ][:1]
        zones = {
            'character': [{
                'instance_id': f'{side}-character',
                'kind': 'character',
                'owner': side,
                'character_id': character_id,
                'name': character['name'],
                'face_up': True,
            }],
            'passive': [
                _card_payload(row, side, f'passive-{index}', face_up=True)
                for index, row in enumerate(passives, start=1)
            ],
            'battle': [],
            'hand': [
                _card_payload(row, side, index, face_up=False)
                for index, row in enumerate(techniques[:5], start=1)
            ],
            'list': [
                _card_payload(row, side, index + 5, face_up=True)
                for index, row in enumerate(techniques[5:14], start=1)
            ],
            'side': [
                _card_payload(row, side, index + 14, face_up=False)
                for index, row in enumerate(techniques[14:], start=1)
            ],
            'break': [],
            'lumen': [],
            'ultimate': [
                _card_payload(row, side, f'ultimate-{index}', face_up=True)
                for index, row in enumerate(ultimates, start=1)
            ],
        }
        players[side] = {
            'name': character['name'],
            'character': {
                'id': character_id,
                'name': character['name'],
            },
            'initial_hp': 5000,
            'hp': 5000,
            'fp': 0,
            'passive_state': {},
            'zones': zones,
        }
    return {
        'turn': 1,
        'phase': 'lumen',
        'priority_player': priority,
        'players': players,
    }


class Command(BaseCommand):
    help = (
        'Read the legacy catalog without writes and run AI-vs-AI draft-rule games. '
        'Useful before production migrations and ruleset publication.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--character1', type=int)
        parser.add_argument('--character2', type=int)
        parser.add_argument('--games', type=int, default=4)
        parser.add_argument('--start-index', type=int, default=0)
        parser.add_argument('--max-commands', type=int, default=2000)

    def handle(self, *args, **options):
        rows = list(Card.objects.order_by('id').values(*CARD_RUNTIME_FIELDS))
        if len(rows) != EXPECTED_CARD_COUNT:
            raise CommandError(
                f'전체 카탈로그가 필요합니다: {len(rows)}/{EXPECTED_CARD_COUNT}장'
            )
        if any(not str(row.get('code') or '').strip() for row in rows):
            raise CommandError('코드가 없는 카드가 있어 카탈로그 규칙을 만들 수 없습니다.')

        counts = Counter(
            row['character_id'] for row in rows
            if row.get('type') not in EXCLUDED_DECK_TYPES and not row.get('ultimate')
        )
        requested = [options.get('character1'), options.get('character2')]
        if any(value is None for value in requested):
            eligible = sorted(
                (character_id for character_id, count in counts.items() if count >= 20),
                key=lambda character_id: (-counts[character_id], character_id),
            )
            if len(eligible) < 2:
                raise CommandError('20장 덱을 만들 수 있는 캐릭터가 2명보다 적습니다.')
            character_ids = [
                requested[index] if requested[index] is not None else eligible[index]
                for index in range(2)
            ]
        else:
            character_ids = requested
        if any(counts[character_id] < 1 for character_id in character_ids):
            raise CommandError('선택한 캐릭터 중 스모크 덱에 넣을 기술이 없는 캐릭터가 있습니다.')

        characters = {
            row['id']: row
            for row in Character.objects.filter(id__in=character_ids).values('id', 'name')
        }
        if len(characters) != len(set(character_ids)):
            raise CommandError('선택한 캐릭터를 찾을 수 없습니다.')

        card_snapshots = {}
        ability_count = 0
        for row in rows:
            definition = build_effect_draft(row['code'], row.get('text') or '')
            ability_count += len(definition.get('abilities') or [])
            card_snapshots[str(row['code'])] = {
                **row,
                'effect_definition': definition,
            }
        ruleset = {
            'version': 'catalog-draft-smoke',
            'cards': card_snapshots,
        }

        game_count = max(1, int(options['games']))
        start_index = max(0, int(options['start_index']))
        max_commands = max(1, int(options['max_commands']))
        results = []
        for index in range(start_index, start_index + game_count):
            state = _state_for_catalog(
                rows,
                characters,
                character_ids,
                priority=PLAYER_SIDES[index % 2],
                rotation=index * 5,
            )
            try:
                result = run_policy_game(
                    state,
                    ruleset,
                    seed=f'catalog-draft-smoke-{index}',
                    max_commands=max_commands,
                )
                results.append({
                    'game': index + 1,
                    'completed': result.completed,
                    'commands': result.commands,
                    'winner': result.winner,
                    'reason': result.reason,
                    'error': result.error,
                })
            except Exception as exc:
                results.append({
                    'game': index + 1,
                    'completed': False,
                    'commands': 0,
                    'winner': None,
                    'reason': 'exception',
                    'error': f'{type(exc).__name__}: {exc}',
                })

        report = {
            'is_complete': all(item['completed'] for item in results),
            'read_only': True,
            'catalog_cards': len(rows),
            'abilities': ability_count,
            'characters': character_ids,
            'games': results,
        }
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not report['is_complete']:
            raise CommandError('실제 카탈로그 자동 대전에서 미완료 또는 예외가 발생했습니다.')
