import copy
import json
import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from battlelog.automatic_services import _pin_release_card_data
from battlelog.game.catalog import (
    CARD_RUNTIME_FIELDS,
    _card_snapshot,
    active_ruleset_release,
)
from battlelog.game.review import review_automatic_definition
from battlelog.game.schema import validate_effect_definition
from battlelog.game.simulation import run_policy_game
from battlelog.management.commands.smoke_automatic_catalog import (
    _state_for_catalog,
)
from battlelog.management.console import console_safe_json
from card.models import Card, Character


def _browser_review_section(markdown, character_name):
    marker = f'## {character_name}'
    start = str(markdown or '').find(marker)
    if start < 0:
        return ''
    following = str(markdown).find('\n## ', start + len(marker))
    return str(markdown)[start:following if following >= 0 else None]


def _browser_review_chunks(section):
    """Split one character section into independently attributable evidence."""
    chunks = []
    current = []

    def flush():
        if current:
            chunks.append('\n'.join(current))
            current.clear()

    for raw_line in str(section or '').splitlines():
        line = raw_line.strip()
        if not line:
            flush()
            continue
        if line.startswith('|'):
            flush()
            chunks.append(line)
            continue
        if line.startswith('#'):
            flush()
            continue
        if re.match(r'^[-*]\s+', line):
            flush()
        current.append(line)
    flush()
    return chunks


def _browser_evidence_for_codes(markdown, character_name, codes):
    section = _browser_review_section(markdown, character_name)
    chunks = _browser_review_chunks(section)
    verified = set()
    recheck = set()
    mentioned = set()
    for code in codes:
        matching = [chunk for chunk in chunks if str(code) in chunk]
        if matching:
            mentioned.add(code)
        if any('재확인 대기' in chunk for chunk in matching):
            recheck.add(code)
            continue
        if any(
            (
                '브라우저' in chunk
                and ('확인' in chunk or '완료' in chunk)
            )
            or (
                chunk.startswith('|')
                and re.search(
                    r'\|\s*(?:완료|브라우저 확인)'
                    r'(?:\s*[;,·/]\s*[^|]+)?\s*\|?$',
                    chunk,
                )
            )
            for chunk in matching
        ):
            verified.add(code)
    return {
        'section_found': bool(section),
        'mentioned': mentioned,
        'verified': verified,
        'recheck': recheck,
        'missing': set(codes) - verified - recheck,
    }


def _review_summary(definition, snapshot):
    result = review_automatic_definition(
        copy.deepcopy(definition),
        card_has_text=bool(str(snapshot.get('text') or '').strip()),
        card_snapshot=copy.deepcopy(snapshot),
    )
    scenarios = [
        scenario
        for ability in result.abilities
        for scenario in ability.scenarios
    ]
    return {
        'passed': bool(result.passed),
        'reason': str(result.reason or ''),
        'ability_count': len(result.abilities),
        'scenario_count': len(scenarios),
        'live_pipeline_scenario_count': sum(
            str(scenario.get('execution_path') or '').endswith('_pipeline')
            for scenario in scenarios
        ),
        'failed_scenarios': [
            str(scenario.get('name') or '')
            for scenario in scenarios if not scenario.get('passed')
        ],
    }


def _apply_supplement_synergy_fixture(
    state, character_id, rows, candidate_snapshot,
):
    """Place trait supplements in their active setup zone for smoke games.

    A generic 20-card catalog deck can accidentally put Parts-like supplement
    cards in the normal hand/list slots.  Character integration games instead
    model the post-game-start state: the base deck remains 20 cards and the
    maximum legal supplement set is face-up in Lumen.  Dedicated card reviews
    still verify the optional game-start selection itself.
    """
    cards = candidate_snapshot.get('cards') or {}
    passive_definitions = [
        (cards.get(str(row.get('code') or '')) or {}).get(
            'effect_definition',
        ) or {}
        for row in rows
        if row.get('character_id') == character_id
        and str(row.get('type') or '') == '특성'
    ]
    supplements = [
        supplement
        for definition in passive_definitions
        for supplement in (
            (definition.get('deck_rules') or {}).get('supplements') or []
        )
        if str((supplement.get('where') or {}).get('token_key') or '')
    ]
    if not supplements:
        return []
    neutral_rows = [
        row for row in rows
        if row.get('character_id') == 1
        and str(row.get('type') or '') not in {'특성', '토큰'}
        and not row.get('ultimate')
    ]
    fixtures = []
    for supplement in supplements:
        token_key = str(supplement['where']['token_key'])
        maximum = max(0, int(supplement.get('max_count') or 0))
        lumen_limits = [
            max(0, int(limit.get('max') or 0))
            for definition in passive_definitions
            for limit in definition.get('zone_limits') or []
            if (
                str(limit.get('zone') or '') == 'lumen'
                and str((limit.get('where') or {}).get('token_key') or '')
                == token_key
            )
        ]
        if lumen_limits:
            maximum = min(maximum, min(lumen_limits))
        supplement_rows = [
            row for row in rows
            if (
                ((cards.get(str(row.get('code') or '')) or {}).get(
                    'effect_definition',
                ) or {}).get('token_key') == token_key
            )
        ]
        if not supplement_rows or maximum < 1:
            continue
        selected_rows = supplement_rows[:maximum]
        selected_codes = {str(row.get('code') or '') for row in selected_rows}
        for side, player in (state.get('players') or {}).items():
            zones = player.get('zones') or {}
            current_codes = {
                str(card.get('code') or '')
                for zone_cards in zones.values() if isinstance(zone_cards, list)
                for card in zone_cards
            }
            neutral_candidates = [
                row for row in neutral_rows
                if str(row.get('code') or '') not in current_codes
            ]
            neutral_index = 0
            replaced = []
            for zone in ('hand', 'list', 'side'):
                zone_cards = zones.get(zone) or []
                for index, card in enumerate(list(zone_cards)):
                    definition = (
                        cards.get(str(card.get('code') or '')) or {}
                    ).get('effect_definition') or {}
                    if definition.get('token_key') != token_key:
                        continue
                    if neutral_index >= len(neutral_candidates):
                        raise CommandError(
                            f'{token_key} 보충 카드를 제외한 20장 덱을 '
                            '구성할 공용 기술이 부족합니다.'
                        )
                    replacement = neutral_candidates[neutral_index]
                    neutral_index += 1
                    zone_cards[index] = {
                        **copy.deepcopy(replacement),
                        'instance_id': str(card.get('instance_id')),
                        'kind': 'card', 'owner': side,
                        'face_up': zone == 'list',
                    }
                    replaced.append(str(card.get('code') or ''))
            for index, row in enumerate(selected_rows, start=1):
                zones.setdefault('lumen', []).append({
                    **copy.deepcopy(row),
                    'instance_id': f'{side}-audit-{token_key}-{index}',
                    'kind': 'card', 'owner': side, 'face_up': True,
                })
            fixtures.append({
                'player': side, 'token_key': token_key,
                'placed_zone': 'lumen',
                'placed_codes': sorted(selected_codes),
                'replaced_main_codes': sorted(replaced),
            })
    return fixtures


class Command(BaseCommand):
    help = (
        '활성 규칙 릴리스를 캐릭터·특성·얼티밋 단위로 재검증하고, '
        '동일 캐릭터 자동 대전에서 도달한 카드·효과를 보고한다.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--character', action='append', default=[],
            help='캐릭터 ID, localization_key 또는 표시 이름. 반복 가능.',
        )
        parser.add_argument('--games', type=int, default=2)
        parser.add_argument('--max-commands', type=int, default=1200)
        parser.add_argument('--skip-games', action='store_true')
        parser.add_argument(
            '--verbose', action='store_true',
            help='카드별 상세 결과를 포함한다.',
        )
        parser.add_argument(
            '--browser-review-file',
            default=str(
                Path(settings.BASE_DIR).parent
                / 'AUTOMATIC_EFFECT_BROWSER_REVIEW_KO.md'
            ),
            help='카드별 브라우저 근거를 감사할 Markdown 파일.',
        )

    def handle(self, *args, **options):
        release = active_ruleset_release()
        if not release:
            raise CommandError('활성 규칙 릴리스가 없습니다.')
        characters = list(Character.objects.order_by('id'))
        requested = {
            str(value or '').strip().casefold()
            for value in options['character'] if str(value or '').strip()
        }
        if requested:
            selected = [
                character for character in characters
                if {
                    str(character.id),
                    str(getattr(character, 'localization_key', '') or '').casefold(),
                    str(character).casefold(),
                } & requested
            ]
            matched = {
                token for token in requested
                if any(token in {
                    str(character.id),
                    str(getattr(character, 'localization_key', '') or '').casefold(),
                    str(character).casefold(),
                } for character in selected)
            }
            if matched != requested:
                raise CommandError(
                    '캐릭터를 찾을 수 없습니다: '
                    + ', '.join(sorted(requested - matched))
                )
        else:
            # Character 1 is the neutral mark, not a playable character.
            selected = [character for character in characters if character.id != 1]

        all_cards = list(Card.objects.order_by('id'))
        rows = list(Card.objects.order_by('id').values(*CARD_RUNTIME_FIELDS))
        rows_by_code = {str(row.get('code') or ''): row for row in rows}
        database_cards = {
            str(card.code or ''): card
            for card in all_cards
        }
        released_cards = (release.snapshot or {}).get('cards') or {}
        candidate_snapshot = copy.deepcopy(release.snapshot)
        candidate_snapshot['cards'] = {
            str(card.code or ''): _card_snapshot(card) for card in all_cards
        }
        ruleset = {
            **candidate_snapshot,
            'version': f'{release.version}+database-candidate',
        }
        browser_review_path = Path(options['browser_review_file']).resolve()
        browser_review_markdown = (
            browser_review_path.read_text(encoding='utf-8')
            if browser_review_path.is_file() else ''
        )
        reports = []
        for character in selected:
            own_rows = [
                row for row in rows if row.get('character_id') == character.id
            ]
            card_reports = []
            for row in own_rows:
                code = str(row.get('code') or '')
                snapshot = copy.deepcopy(released_cards.get(code) or {})
                definition = copy.deepcopy(snapshot.get('effect_definition') or {})
                database_card = database_cards.get(code)
                database_definition = copy.deepcopy(
                    (database_card.effect_definition if database_card else {}) or {}
                )
                release_matches_database = (
                    json.dumps(definition, ensure_ascii=False, sort_keys=True)
                    == json.dumps(
                        database_definition, ensure_ascii=False, sort_keys=True,
                    )
                )
                schema_issues = validate_effect_definition(
                    definition,
                    require_coverage=True,
                    card_has_text=bool(str(snapshot.get('text') or '').strip()),
                ) if definition else []
                review = (
                    _review_summary(definition, snapshot)
                    if definition and not schema_issues else {
                        'passed': False,
                        'reason': '릴리스 효과 정의 또는 스키마가 없습니다.',
                        'ability_count': 0,
                        'scenario_count': 0,
                        'live_pipeline_scenario_count': 0,
                        'failed_scenarios': [],
                    }
                )
                database_schema_issues = validate_effect_definition(
                    database_definition,
                    require_coverage=True,
                    card_has_text=bool(
                        str((database_card.text if database_card else '') or '').strip()
                    ),
                ) if database_definition else []
                database_review = (
                    review
                    if release_matches_database else _review_summary(
                        database_definition,
                        {**snapshot, **row,
                         'effect_definition': database_definition},
                    )
                ) if database_definition and not database_schema_issues else {
                    'passed': False,
                    'reason': 'DB 효과 정의 또는 스키마가 없습니다.',
                    'ability_count': 0,
                    'scenario_count': 0,
                    'live_pipeline_scenario_count': 0,
                    'failed_scenarios': [],
                }
                card_reports.append({
                    'code': code,
                    'name': str(snapshot.get('name') or row.get('name') or code),
                    'type': str(snapshot.get('type') or row.get('type') or ''),
                    'ultimate': bool(snapshot.get('ultimate') or row.get('ultimate')),
                    'released': bool(snapshot),
                    'reviewed': definition.get('reviewed') is True,
                    'release_matches_database': release_matches_database,
                    'database_reviewed': database_definition.get('reviewed') is True,
                    'database_schema_issue_count': len(database_schema_issues),
                    'database_passed': bool(database_review['passed']),
                    'database_reason': str(database_review['reason'] or ''),
                    'database_triggered_ability_ids': [
                        str(ability.get('id') or '')
                        for ability in database_definition.get('abilities') or []
                        if (ability.get('trigger') or {}).get('event')
                    ],
                    'schema_issue_count': len(schema_issues),
                    'schema_issues': [
                        {'path': issue.path, 'code': issue.code, 'message': issue.message}
                        for issue in schema_issues
                    ],
                    **review,
                })

            game_reports = []
            synergy_fixtures = []
            reached_used = set()
            reached_resolved = set()
            reached_abilities = set()
            if not options['skip_games']:
                character_payload = {
                    character.id: {'id': character.id, 'name': str(character)},
                }
                for index in range(max(1, int(options['games']))):
                    state = _state_for_catalog(
                        rows, character_payload,
                        [character.id, character.id],
                        priority='p1' if index % 2 == 0 else 'p2',
                        rotation=index * 5,
                    )
                    game_fixtures = _apply_supplement_synergy_fixture(
                        state, character.id, rows, candidate_snapshot,
                    )
                    synergy_fixtures.extend(game_fixtures)
                    state = _pin_release_card_data(state, candidate_snapshot)
                    result = run_policy_game(
                        state, ruleset,
                        seed=f'character-audit:{release.version}:{character.id}:{index}',
                        max_commands=max(1, int(options['max_commands'])),
                    )
                    coverage = result.coverage or {}
                    reached_used.update(coverage.get('used_card_codes') or [])
                    reached_resolved.update(coverage.get('resolved_card_codes') or [])
                    reached_abilities.update(coverage.get('resolved_ability_ids') or [])
                    game_reports.append({
                        'index': index + 1,
                        'completed': bool(result.completed),
                        'commands': int(result.commands),
                        'winner': result.winner,
                        'reason': result.reason,
                        'error': result.error,
                        'coverage': coverage,
                    })

            own_codes = {str(row.get('code') or '') for row in own_rows}
            own_triggered_ability_ids = {
                ability_id
                for item in card_reports
                for ability_id in item['database_triggered_ability_ids']
                if ability_id
            }
            passive_codes = sorted(
                code for code in own_codes
                if str((rows_by_code.get(code) or {}).get('type') or '') == '특성'
            )
            ultimate_codes = sorted(
                code for code in own_codes
                if bool((rows_by_code.get(code) or {}).get('ultimate'))
            )
            passed_cards = sum(
                item['database_reviewed']
                and not item['database_schema_issue_count']
                and item['database_passed']
                for item in card_reports
            )
            browser_evidence = _browser_evidence_for_codes(
                browser_review_markdown, str(character), own_codes,
            )
            reports.append({
                'character_id': character.id,
                'character_key': str(
                    getattr(character, 'localization_key', '') or ''
                ),
                'character_name': str(character),
                'card_count': len(card_reports),
                'passed_card_count': passed_cards,
                'failed_card_codes': [
                    item['code'] for item in card_reports
                    if not (
                        item['database_reviewed']
                        and not item['database_schema_issue_count']
                        and item['database_passed']
                    )
                ],
                'stale_release_card_codes': [
                    item['code'] for item in card_reports
                    if not item['release_matches_database']
                ],
                'release_failed_card_codes': [
                    item['code'] for item in card_reports
                    if not (
                        item['released'] and item['reviewed']
                        and not item['schema_issue_count'] and item['passed']
                    )
                ],
                'live_pipeline_card_codes': sorted(
                    item['code'] for item in card_reports
                    if item['live_pipeline_scenario_count']
                ),
                'passive_codes': passive_codes,
                'ultimate_codes': ultimate_codes,
                'browser_section_found': browser_evidence['section_found'],
                'browser_verified_card_codes': sorted(
                    browser_evidence['verified']
                ),
                'browser_recheck_pending_card_codes': sorted(
                    browser_evidence['recheck']
                ),
                'browser_missing_card_codes': sorted(
                    browser_evidence['missing']
                ),
                'browser_card_coverage_percent': round(
                    100 * len(browser_evidence['verified'])
                    / max(1, len(own_codes)),
                    1,
                ),
                'headless_games_completed': sum(
                    item['completed'] for item in game_reports
                ),
                'headless_game_count': len(game_reports),
                'headless_used_own_codes': sorted(reached_used & own_codes),
                'headless_resolved_own_codes': sorted(reached_resolved & own_codes),
                'headless_resolved_ability_ids': sorted(reached_abilities),
                'headless_reached_own_ability_ids': sorted(
                    reached_abilities & own_triggered_ability_ids
                ),
                'headless_unreached_own_ability_ids': sorted(
                    own_triggered_ability_ids - reached_abilities
                ),
                'headless_triggered_ability_coverage_percent': round(
                    100 * len(reached_abilities & own_triggered_ability_ids)
                    / max(1, len(own_triggered_ability_ids)),
                    1,
                ),
                'headless_passive_effect_reached': bool(
                    reached_resolved & set(passive_codes)
                ),
                'headless_ultimate_used': bool(
                    reached_used & set(ultimate_codes)
                ),
                'synergy_fixtures': synergy_fixtures,
                **({'cards': card_reports, 'games': game_reports}
                   if options['verbose'] else {}),
            })

        report = {
            'ruleset_version': release.version,
            'headless_ruleset_version': ruleset['version'],
            'character_count': len(reports),
            'all_structural_reviews_passed': all(
                item['passed_card_count'] == item['card_count']
                for item in reports
            ),
            'all_headless_games_completed': all(
                item['headless_games_completed'] == item['headless_game_count']
                for item in reports
            ),
            'browser_review_file': str(browser_review_path),
            'browser_review_status': (
                'passed' if browser_review_markdown and all(
                    item['browser_section_found']
                    and not item['browser_recheck_pending_card_codes']
                    and not item['browser_missing_card_codes']
                    for item in reports
                ) else 'pending'
            ),
            'characters': reports,
        }
        self.stdout.write(console_safe_json(report, self.stdout))
