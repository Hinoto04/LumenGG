from django.contrib.auth.models import Permission, User
from django.test import TestCase
from django.urls import reverse

from .models import Card, CardTranslation, Character
from .search import card_matches_search, card_matches_search_exact
from common.language import LANGUAGE_SESSION_KEY


class CardUpdateLocalizationTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='니아',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/nia.webp',
        )
        self.card = Card.objects.create(
            name='원본 카드',
            ruby='원본 루비',
            type='공격',
            frame=5,
            damage=300,
            pos='상단',
            body='손',
            special='',
            code='TST-001',
            hit='2',
            guard='-2',
            counter='콤보',
            g_top='방어',
            g_mid='',
            g_bot='',
            character=self.character,
            text='원본 효과',
            detail_text='원본 보충 설명',
            keyword='원본 태그',
            hiddenKeyword='원본 숨김',
            search='원본 검색',
        )
        self.user = User.objects.create_user('card-admin', password='password')
        self.user.user_permissions.add(Permission.objects.get(
            codename='change_card',
            content_type__app_label='card',
        ))
        self.user.user_permissions.add(Permission.objects.get(
            codename='tag_update',
            content_type__app_label='card',
        ))
        self.client.force_login(self.user)

    def test_update_page_uses_current_language_translation(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.get(reverse('card:update', args=[self.card.id]))

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_translation_update'])
        self.assertEqual(response.context['form'].fields['name'].widget.attrs['placeholder'], '원본 카드')

    def test_update_writes_translation_without_changing_source_card(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.post(reverse('card:update', args=[self.card.id]), {
            'name': 'Translated Card',
            'ruby': 'Translated Ruby',
            'text': 'Translated effect',
            'detail_text': 'Translated note',
            'keyword': 'translated tag',
            'hiddenKeyword': 'translated hidden',
            'search': 'translated search',
        })

        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.name, '원본 카드')
        self.assertEqual(self.card.text, '원본 효과')

        translation = CardTranslation.objects.get(card=self.card, language='en')
        self.assertEqual(translation.name, 'Translated Card')
        self.assertEqual(translation.text, 'Translated effect')
        self.assertEqual(translation.keyword, 'translated tag')

    def test_detail_tag_form_uses_current_language_translation(self):
        CardTranslation.objects.create(
            card=self.card,
            language='en',
            name='Translated Card',
            keyword='translated tag',
            hiddenKeyword='translated hidden',
            search='translated search',
        )
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.get(reverse('card:detail', args=[self.card.id]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['tag_edit']['values']['keyword'], 'translated tag')
        self.assertEqual(response.context['tag_edit']['values']['hidden'], 'translated hidden')
        self.assertEqual(response.context['tag_edit']['values']['search'], 'translated search')
        self.assertEqual(response.context['tag_edit']['placeholders']['keyword'], '원본 태그')

    def test_tag_update_writes_current_language_translation(self):
        session = self.client.session
        session[LANGUAGE_SESSION_KEY] = 'en'
        session.save()

        response = self.client.post(reverse('card:editCardTag', args=[self.card.id]), {
            'keyword': 'english tag/',
            'hidden': 'english hidden',
            'search': 'english search/',
        })

        self.assertEqual(response.status_code, 302)
        self.card.refresh_from_db()
        self.assertEqual(self.card.keyword, '원본 태그')
        self.assertEqual(self.card.hiddenKeyword, '원본 숨김')
        self.assertEqual(self.card.search, '원본 검색')

        translation = CardTranslation.objects.get(card=self.card, language='en')
        self.assertEqual(translation.keyword, 'english tag/')
        self.assertEqual(translation.hiddenKeyword, 'english hidden')
        self.assertEqual(translation.search, 'english search/')


class CardSearchNormalizationTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(
            name='세츠메이',
            description='',
            group='루멘콘덴서',
            datas={},
            img='https://example.com/setsumei.webp',
        )
        self.card = Card.objects.create(
            name='세츠메이 킥',
            code='ST1-018',
            character=self.character,
            img='https://example.com/card.webp',
            keyword='콤보 시동기/',
        )
        CardTranslation.objects.create(
            card=self.card,
            language='en',
            name='Setsumei Kick',
            keyword='Combo Starter',
        )

    def test_search_ignores_case_spaces_and_punctuation(self):
        self.assertTrue(card_matches_search(self.card, 'setsumeikick'))
        self.assertTrue(card_matches_search(self.card, 'SETSUMEI-KICK'))
        self.assertTrue(card_matches_search(self.card, 'setsumei   kick!!!'))

    def test_exact_search_uses_normalized_card_names(self):
        self.assertTrue(card_matches_search_exact(self.card, 'setsumei-kick'))
        self.assertFalse(card_matches_search_exact(self.card, 'setsumei'))
