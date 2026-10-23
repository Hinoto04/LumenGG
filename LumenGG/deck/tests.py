from django.contrib.auth.models import User
from django.apps import apps
from django.test import TestCase
from django.urls import reverse
from datetime import date
import importlib

from card.models import Card, Character
from common.models import SiteSettings
from collection.models import CollectionCard, Pack
from deck.models import Deck, Regulation, RegulationVersion, ReserveCardInDeck


class DeckBuilderV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('builder', password='test-password')
        self.character = Character.objects.create(name='Tester', color='#123456', datas={})
        SiteSettings.objects.create(name='갯수예외처리카드', setting={})
        self.client.force_login(self.user)

    def test_desktop_builder_has_scroll_picker_and_reserve_zone(self):
        response = self.client.get(reverse('deck:create'), HTTP_USER_AGENT='Desktop')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="v2-deck-character-picker"')
        self.assertContains(response, 'grid-template-columns: repeat(2, var(--size))')
        self.assertContains(response, 'id="v2ZoneReserve"')
        self.assertContains(response, 'id="ReserveCount"')
        self.assertContains(response, 'data-reserve-toggle')
        self.assertContains(response, 'data-reserve-zone hidden')
        self.assertContains(response, '>무금제<')
        self.assertNotContains(response, '어떠한 덱 구성 규칙도 적용하지 않음')
        self.assertContains(response, 'v2-deck-extensions is-inline')
        self.assertNotContains(response, '규정 작성·복사')

    def test_builder_hides_setsumei_and_starts_without_character_selection(self):
        Character.objects.create(name='세츠메이', color='#ffffff', datas={})

        response = self.client.get(reverse('deck:create'), HTTP_USER_AGENT='Desktop')

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'aria-label="세츠메이"')
        self.assertNotContains(response, 'name="char" value="1" aria-label="Tester" checked')

    def test_trait_options_are_ordered_by_first_release(self):
        later = Card.objects.create(name='나중 특성', code='TST-PS-002', character=self.character, type='특성')
        earlier = Card.objects.create(name='먼저 특성', code='TST-PS-001', character=self.character, type='특성')
        late_pack = Pack.objects.create(name='나중 팩', code='LATE', released='2026-02-01')
        early_pack = Pack.objects.create(name='먼저 팩', code='EARLY', released='2025-01-01')
        CollectionCard.objects.create(card=later, pack=late_pack, code='LATE-PS')
        CollectionCard.objects.create(card=earlier, pack=early_pack, code='EARLY-PS')

        response = self.client.get(reverse('deck:options'))

        self.assertEqual(response.status_code, 200)
        traits = [item for item in response.json()['traits'] if item['character_id'] == self.character.pk]
        self.assertEqual([item['id'] for item in traits], [earlier.pk, later.pk])

    def test_options_include_public_regulation_versions(self):
        regulation = Regulation.objects.create(name='26.12 금제')
        version = RegulationVersion.objects.create(
            regulation=regulation,
            version='1',
            effective_date=date(2026, 12, 1),
            rules={},
        )

        response = self.client.get(reverse('deck:options'))

        self.assertEqual(response.status_code, 200)
        item = next(item for item in response.json()['versions'] if item['id'] == version.pk)
        self.assertEqual(item['name'], '26.12 금제')
        self.assertEqual(item['effective_date'], '2026-12-01')
        self.assertNotIn('기본 규정', [item['name'] for item in response.json()['versions']])

    def test_character_page_uses_minyeongi_character_icon(self):
        from collection.models import Pack
        pack = Pack.objects.create(name='CB03', code='CB03', released=date(2026, 1, 1))
        Character.objects.create(
            name='미녕이', localization_key='minyeongi', color='#ffffff', datas={}, pack=pack,
            icon_img='https://images.example/CharacterIcon/CB03.webp',
        )

        response = self.client.get(reverse('card:character'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'https://images.example/CharacterIcon/CB03.webp')

    def test_mobile_builder_has_scroll_picker_and_reserve_zone(self):
        response = self.client.get(reverse('deck:createMobile'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="v2-deck-character-picker"')
        self.assertContains(response, 'id="v2ZoneReserve"')
        self.assertContains(response, 'data-reserve-toggle')
        self.assertContains(response, 'data-reserve-zone hidden')
        self.assertNotContains(response, 'data-mobile-character-select')

    def test_deck_search_has_stable_filters_without_import_action(self):
        response = self.client.get(reverse('deck:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="v2-search-row v2-deck-search-row"')
        self.assertContains(response, 'id="v2DeckSearchCharacterPicker"')
        self.assertContains(response, 'type="checkbox" name="char"')
        self.assertContains(response, 'data-trait-filter-field hidden')
        self.assertContains(response, 'data-trait-filter')
        self.assertContains(response, 'data-regulation-filter')
        self.assertContains(response, '<option value="">전체</option>', count=2, html=True)
        self.assertNotContains(response, '>통계<')
        self.assertNotContains(response, 'id="v2FilterToggle"')
        self.assertNotContains(response, reverse('deck:importV2'))

    def test_deck_search_trait_filter_appears_after_character_and_defaults_to_all(self):
        first_trait = Card.objects.create(
            name='첫 특성', code='TST-PS-101', character=self.character, type='특성',
        )
        second_trait = Card.objects.create(
            name='둘째 특성', code='TST-PS-102', character=self.character, type='특성',
        )
        first_deck = Deck.objects.create(
            name='첫 특성 덱', author=self.user, character=self.character, trait_card=first_trait,
        )
        second_deck = Deck.objects.create(
            name='둘째 특성 덱', author=self.user, character=self.character, trait_card=second_trait,
        )

        all_traits = self.client.get(reverse('deck:index'), {'char': self.character.pk})
        self.assertNotContains(all_traits, 'data-trait-filter-field hidden')
        self.assertContains(all_traits, first_deck.name)
        self.assertContains(all_traits, second_deck.name)

        one_trait = self.client.get(reverse('deck:index'), {
            'char': self.character.pk,
            'trait_card_id': first_trait.pk,
        })
        self.assertContains(one_trait, first_deck.name)
        self.assertNotContains(one_trait, second_deck.name)

    def test_deck_search_filters_unrestricted_and_named_regulations(self):
        regulation = Regulation.objects.create(name='검색 금제')
        version = RegulationVersion.objects.create(
            regulation=regulation,
            version='1',
            rules={},
        )
        unrestricted = Deck.objects.create(
            name='Unrestricted result', author=self.user, character=self.character,
        )
        regulated = Deck.objects.create(
            name='Regulated result', author=self.user, character=self.character,
            regulation_version=version,
        )

        response = self.client.get(reverse('deck:index'), {'regulation_version_id': 'unrestricted'})
        self.assertContains(response, unrestricted.name)
        self.assertNotContains(response, regulated.name)

        response = self.client.get(reverse('deck:index'), {'regulation_version_id': version.pk})
        self.assertNotContains(response, unrestricted.name)
        self.assertContains(response, regulated.name)

    def test_basic_regulation_data_migration_converts_decks_to_unrestricted(self):
        regulation = Regulation.objects.create(name='기본 규정')
        version = RegulationVersion.objects.create(regulation=regulation, version='1', rules={})
        deck = Deck.objects.create(
            name='기본 규정 덱', author=self.user, character=self.character,
            regulation_version=version,
        )
        migration = importlib.import_module('deck.migrations.0017_unrestrict_basic_regulation_decks')

        migration.unrestrict_basic_regulation_decks(apps, None)

        deck.refresh_from_db()
        self.assertIsNone(deck.regulation_version_id)

    def test_detail_places_reserve_zone_in_deck_board(self):
        character = Character.objects.first()
        regulation = Regulation.objects.create(name='테스트 금제', owner=self.user)
        regulation_version = RegulationVersion.objects.create(
            regulation=regulation,
            version='2026.10',
            rules={},
        )
        deck = Deck.objects.create(
            name='Reserve layout',
            author=self.user,
            character=character,
            regulation_version=regulation_version,
        )
        reserve = Card.objects.create(
            name='Reserve Card',
            character=character,
            img='https://example.com/reserve.webp',
            img_mid='https://example.com/reserve-mid.webp',
        )
        ReserveCardInDeck.objects.create(deck=deck, card=reserve, count=2)

        response = self.client.get(reverse('deck:detail', args=[deck.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="v2-deck-zone v2-deck-zone-reserve"')
        self.assertContains(response, 'v2-deck-reserve-item', count=2)
        self.assertContains(response, '2장')
        self.assertContains(response, '금제 · 테스트 금제')

    def test_detail_hides_empty_reserve_zone(self):
        character = Character.objects.first()
        deck = Deck.objects.create(name='No reserve', author=self.user, character=character)

        response = self.client.get(reverse('deck:detail', args=[deck.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'id="Reserve"')
        self.assertNotContains(response, 'data-deck-copy-zone="교체 덱"')
        self.assertContains(response, '금제 · 무금제')
