import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from collection.models import Collected, CollectionCard, Pack


class CollectionCategoryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('collector', password='test-password')
        self.pack = Pack.objects.create(name='팩', code='CAT')
        self.items = [CollectionCard.objects.create(pack=self.pack, code=f'CAT-{i:03}', name=f'카드 {i}', rare='N',
                                                    img_sm=f'https://example.test/{i}.webp') for i in range(3)]
        self.client.force_login(self.user)

    def save(self, body):
        return self.client.post(reverse('collection:update_collected'), json.dumps(body), content_type='application/json')

    def test_save_category_without_touching_amount(self):
        Collected.objects.create(user=self.user, card=self.items[0], amount=3)
        result = self.save({'collected': {}, 'categories': {str(self.items[0].pk): 2, str(self.items[1].pk): 5}})
        self.assertEqual(result.json(), {'result': 'ok', 'failed': []})
        first = Collected.objects.get(user=self.user, card=self.items[0])
        self.assertEqual((first.amount, first.category), (3, 2))
        second = Collected.objects.get(user=self.user, card=self.items[1])
        self.assertEqual((second.amount, second.category), (0, 5))

        self.save({'collected': {str(self.items[0].pk): 4}})
        first.refresh_from_db()
        self.assertEqual((first.amount, first.category), (4, 2))

    def test_invalid_category_is_reported(self):
        result = self.save({'categories': {str(self.items[0].pk): 6, str(self.items[1].pk): 'x', '999999': 1}})
        self.assertEqual(sorted(result.json()['failed']), sorted([str(self.items[0].pk), str(self.items[1].pk), '999999']))
        self.assertFalse(Collected.objects.exists())

    def test_category_filter_and_heart_badges(self):
        Collected.objects.create(user=self.user, card=self.items[0], category=1)
        Collected.objects.create(user=self.user, card=self.items[1], category=3)

        def codes(**params):
            response = self.client.get(reverse('collection:index'), params)
            self.assertEqual(response.status_code, 200)
            return [item.code for item in response.context['data']]

        self.assertEqual(len(codes()), 3)
        self.assertEqual(codes(category='any'), ['CAT-000', 'CAT-001'])
        self.assertEqual(codes(category='3'), ['CAT-001'])
        self.assertEqual(len(codes(category='9')), 3)

        response = self.client.get(reverse('collection:index'))
        self.assertContains(response, 'data-collection-hearts')
        self.assertContains(response, '<span class="v2-heart v2-heart-1">&#9829;</span>', html=False)
        self.assertContains(response, 'data-category="3"')
