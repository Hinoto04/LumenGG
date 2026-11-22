import json
import datetime

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


class CollectionExportTests(TestCase):
    def setUp(self):
        from card.models import Card, Character

        self.user = User.objects.create_user('exporter', password='test-password')
        character = Character.objects.create(name='니아', description='', group='', datas={}, img='')
        old = Pack.objects.create(name='옛 팩', code='OLD', released=datetime.date(2023, 1, 1))
        new = Pack.objects.create(name='새 팩', code='NEW', released=datetime.date(2024, 1, 1))
        fast = Card.objects.create(name='잽', type='공격', frame=3, character=character, img='')
        slow = Card.objects.create(name='강타', type='공격', frame=7, character=character, img='')

        def item(code, name, rare, card=None, pack=new):
            return CollectionCard.objects.create(card=card, pack=pack, code=code, name=name, rare=rare)

        self.slow_sr = item('NEW-002', '강타', 'SR', slow)
        self.slow_n = item('NEW-002', '강타', 'N', slow)
        self.slow_old = item('OLD-002', '강타', 'SP', slow, old)
        self.fast = item('NEW-001', '잽', 'N', fast)
        self.skin = item('NEW-S01', '니아, "스킨"', 'SP')
        self.plain = item('NEW-003', '하트 없음', 'N', fast)
        for collection_card, amount, category in (
            (self.slow_sr, 2, 1), (self.slow_n, 0, 3), (self.slow_old, 1, 1),
            (self.fast, 4, 2), (self.skin, 1, 5), (self.plain, 9, 0),
        ):
            Collected.objects.create(user=self.user, card=collection_card, amount=amount, category=category)
        other = User.objects.create_user('other', password='test-password')
        Collected.objects.create(user=other, card=self.plain, amount=1, category=1)

    def export(self, login=True, **params):
        if login:
            self.client.force_login(self.user)
        return self.client.get(reverse('collection:export'), params)

    def test_pure_format_matches_app_format(self):
        from collection.export import ExportEntry, ExportOptions, csv_field, format_collection_export

        entries = [ExportEntry('번개', 'ST1-001', 'SR', 2), ExportEntry('Say "Hi", ok', 'PR-1', '', 0)]
        self.assertEqual(
            format_collection_export(entries, ExportOptions(format='csv')),
            '\ufeff카드명,코드,레어도,갯수\r\n번개,ST1-001,SR,2\r\n"Say ""Hi"", ok",PR-1,,0\r\n',
        )
        self.assertEqual(
            format_collection_export(entries, ExportOptions(format='csv', code=False, amount=False)),
            '\ufeff카드명,레어도\r\n번개,SR\r\n"Say ""Hi"", ok",\r\n',
        )
        self.assertEqual(
            format_collection_export(entries, ExportOptions()),
            '번개 [ST1-001] (SR) x2\nSay "Hi", ok [PR-1] x0\n',
        )
        self.assertEqual(
            format_collection_export(entries, ExportOptions(code=False, rare=False, amount=False)),
            '번개\nSay "Hi", ok\n',
        )
        self.assertEqual(csv_field('a\nb'), '"a\nb"')

    def test_txt_export_without_filters_lists_everything_in_speed_order(self):
        response = self.export(format='txt', col_code='1', col_rare='1', col_amount='1')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain; charset=utf-8')
        self.assertRegex(response['Content-Disposition'], r'attachment; filename="lumen-favorites-\d{8}\.txt"')
        # 목록 화면 기본 정렬: 속도 없는 스킨 → 속도 3(이름순) → 속도 7(먼저 나온 팩 → 레어도 N < SR).
        self.assertEqual(response.content.decode('utf-8').splitlines(), [
            '니아, "스킨" [NEW-S01] (SP) x1',
            '잽 [NEW-001] (N) x4',
            '잽 [NEW-003] (N) x9',
            '강타 [OLD-002] (SP) x1',
            '강타 [NEW-002] (N) x0',
            '강타 [NEW-002] (SR) x2',
        ])

    def test_export_follows_list_filters_and_sort(self):
        # 분류(하트) 1 + 레어도 SR 필터: 검색 조건의 rare와 열 옵션 col_rare가 섞이지 않는다.
        response = self.export(format='csv', category='1', rare='SR', col_rare='1')
        self.assertEqual(response['Content-Type'], 'text/csv; charset=utf-8')
        self.assertTrue(response.content.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(response.content.decode('utf-8-sig'), '카드명,레어도\r\n강타,SR\r\n')
        # 팩 필터(code)와 코드순 정렬, 미보유만 보기.
        new = Pack.objects.get(code='NEW')
        self.assertEqual(
            self.export(format='txt', code=str(new.pk), sortValue='code', col_code='1').content.decode(),
            '잽 [NEW-001]\n강타 [NEW-002]\n강타 [NEW-002]\n잽 [NEW-003]\n니아, "스킨" [NEW-S01]\n',
        )
        self.assertEqual(self.export(format='txt', onlyZero='on', col_amount='1').content.decode(), '강타 x0\n')
        # 열을 모두 끄면 카드명만 남고, 따옴표는 이스케이프된다.
        self.assertEqual(self.export(format='csv', category='5').content.decode('utf-8-sig'),
                         '카드명\r\n"니아, ""스킨"""\r\n')

    def test_anonymous_export_has_no_counts(self):
        response = self.export(login=False, format='txt', col_amount='1', rare='SR')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), '강타 x0\n')

    def test_collection_page_export_form_carries_current_filters(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('collection:index'), {'rare': 'SR', 'category': 'any', 'page': '1'})
        self.assertContains(response, reverse('collection:export'))
        self.assertContains(response, '<input type="hidden" name="rare" value="SR">', html=False)
        self.assertContains(response, '<input type="hidden" name="category" value="any">', html=False)
        self.assertNotContains(response, '<input type="hidden" name="page"', html=False)
        self.assertContains(response, 'name="col_amount" value="1"')
