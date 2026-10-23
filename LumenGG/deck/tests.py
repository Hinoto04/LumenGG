from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from datetime import date

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

    def test_character_page_uses_generated_minyeongi_icon(self):
        from collection.models import Pack
        pack = Pack.objects.create(name='CB03', code='CB03', released=date(2026, 1, 1))
        Character.objects.create(name='미녕이', localization_key='minyeongi', color='#ffffff', datas={}, pack=pack)

        response = self.client.get(reverse('card:character'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/static/character/minyeongi-icon.png')

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
        self.assertContains(response, 'data-trait-filter')
        self.assertNotContains(response, reverse('deck:importV2'))

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
