"""Export real cards for the game client fixtures (read-only).

Reads two characters and a handful of their cards from the configured
database and writes them as JSON.  Nothing is written to the database.
``battlelog.test_play_protocol`` builds its scripted game from this file when
``LUMEN_PLAY_SAMPLE`` points at it (see scripts/export-play-fixtures.ps1).
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from card.models import Card, Character

from ...game.catalog import _character_snapshot
from ...services import character_hand_table, hand_limit_for_hp, initial_hp_for_character
from ...simulator_services import _card_payload, _localized_card_metadata


def _character(value):
    query = Character.objects.all()
    character = (
        query.filter(id=int(value)).first() if str(value).isdigit()
        else query.filter(name=value).first()
    )
    if character is None:
        raise CommandError(f'캐릭터를 찾을 수 없습니다: {value}')
    return character


def _pick(character, *, attacks, defenses, extra):
    base = Card.objects.filter(character=character).order_by('code', 'id')
    attack = list(base.filter(type='공격', ultimate=False, frame__isnull=False)[:attacks + extra])
    defense = list(base.filter(type='수비')[:defenses])
    ultimate = list(base.filter(ultimate=True).exclude(type__in=['특성', '토큰'])[:1])
    if len(attack) < attacks + extra or len(defense) < defenses:
        raise CommandError(f'{character.name}의 공격·수비 카드가 부족합니다.')
    return attack[:attacks] + defense, attack[attacks:], ultimate


class Command(BaseCommand):
    help = '게임 클라이언트 픽스처용 실제 카드 샘플을 JSON으로 내보낸다(DB 읽기 전용).'

    def add_arguments(self, parser):
        parser.add_argument('--p1', default='3', help='P1 캐릭터 id 또는 이름 (기본 3: 루트)')
        parser.add_argument('--p2', default='2', help='P2 캐릭터 id 또는 이름 (기본 2: 니아)')
        parser.add_argument('--attacks', type=int, default=3)
        parser.add_argument('--out', required=True)

    def handle(self, *args, **options):
        sample = {'players': {}, 'cards': {}}
        for side in ('p1', 'p2'):
            character = _character(options[side])
            hand, listed, ultimate = _pick(
                character, attacks=options['attacks'], defenses=1, extra=2,
            )
            zones = {'hand': hand, 'list': listed, 'ultimate': ultimate}
            payload_zones = {}
            for zone, cards in zones.items():
                payload_zones[zone] = [
                    _card_payload(
                        card, side, f'{side}-{zone}-{card.code or card.id}',
                        face_up=(zone == 'list'),
                    )
                    for card in cards
                ]
                for card in cards:
                    # GET simulator/<token>/card-metadata/ 와 같은 값
                    sample['cards'][str(card.id)] = _localized_card_metadata(card, 'ko')
            initial_hp = initial_hp_for_character(character)
            sample['players'][side] = {
                'name': character.name,
                'initial_hp': initial_hp,
                'character': {
                    'id': character.id,
                    'name': character.name,
                    'img': character.body_img or character.sd_img or character.img,
                    'icon_img': character.icon_img,
                    'color': character.color,
                    'hand_table': character_hand_table(character),
                    'hand_limit': hand_limit_for_hp(character, initial_hp),
                },
                # 실제 공개 룰셋과 같은 형태(catalog._character_snapshot)
                'ruleset_character': _character_snapshot(character),
                'zones': payload_zones,
            }
        out = Path(options['out'])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(sample, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        names = ' vs '.join(sample['players'][side]['name'] for side in ('p1', 'p2'))
        self.stdout.write(f'{names}: 카드 {len(sample["cards"])}장 → {out}')
