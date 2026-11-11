import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import uuid
from unittest.mock import patch
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from card.models import Card, Character
from collection.models import Pack, CollectionCard, Collected
from common.models import SiteSettings
from qna.models import QNA, QNARelation
from deck.models import Deck, CardInDeck, DeckLike
from battlelog.services import create_standalone_session, serialize_session, perform_session_action
from mobile_api.catalog import publish_catalog
from mobile_api.sync import apply_sync
from mobile_api.models import CatalogRelease, SyncReceipt, CalculatorReceipt
from mobile_api.calculators import perform_mobile_action, mobile_state, StaleCalculator
from rest_framework.exceptions import ValidationError
from django.core.exceptions import PermissionDenied


class MobileDeckBrowseTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='deck_owner')
        self.other = User.objects.create_user(username='other_player')
        self.character = Character.objects.create(name='캐릭터', description='', group='test', datas={})
        self.card = Card.objects.create(name='카드', character=self.character, type='공격')
        self.public = self.make_deck(self.other, '콤보 공개', 'public')
        self.private = self.make_deck(self.other, '숨긴 덱', 'private')
        self.unlisted = self.make_deck(self.other, '링크 덱', 'unlisted')
        self.mine = self.make_deck(self.owner, '내 비공개 덱', 'private')
        self.deleted = self.make_deck(self.other, '삭제 덱', 'public', deleted=True)
        CardInDeck.objects.create(deck=self.public, card=self.card, count=3, hand=1, side=1)
        self.client = APIClient()

    def make_deck(self, author, name, visibility, **kwargs):
        return Deck.objects.create(author=author, character=self.character, name=name,
                                   visibility=visibility, description='<p>설명</p>', **kwargs)

    def test_public_search_excludes_private_unlisted_and_deleted(self):
        result = self.client.get('/api/mobile/v1/decks')
        self.assertEqual(result.status_code, 200)
        self.assertEqual([d['id'] for d in result.data['decks']], [self.public.pk])
        self.assertEqual(result.data['decks'][0]['author']['username'], self.other.username)
        for query in ['콤보', 'other_player']:
            self.assertEqual(self.client.get('/api/mobile/v1/decks', {'q': query}).data['count'], 1)
        self.assertEqual(self.client.get('/api/mobile/v1/decks', {'character_id': 999}).data['count'], 0)

    def test_public_list_sorts_like_web(self):
        older = self.make_deck(self.owner, '오래된 인기 덱', 'public', version='AWL')
        Deck.objects.filter(pk=older.pk).update(created=self.public.created.replace(year=2000))
        self.public.version = 'LMI'
        self.public.save(update_fields=['version'])
        DeckLike.objects.create(deck=older, author=self.other, like=True)
        DeckLike.objects.create(deck=older, author=self.owner, like=True)
        DeckLike.objects.create(deck=self.public, author=self.owner, like=False)

        def ids(sort=None):
            params = {'sort': sort} if sort else {}
            return [d['id'] for d in self.client.get('/api/mobile/v1/decks', params).data['decks']]

        self.assertEqual(ids(), [self.public.pk, older.pk])
        self.assertEqual(ids('recent'), [self.public.pk, older.pk])
        self.assertEqual(ids('version'), [self.public.pk, older.pk])
        self.assertEqual(ids('like'), [older.pk, self.public.pk])
        likes = {d['id']: d['like_count'] for d in self.client.get('/api/mobile/v1/decks', {'sort': 'like'}).data['decks']}
        self.assertEqual(likes, {older.pk: 2, self.public.pk: 0})
        self.assertEqual(self.client.get('/api/mobile/v1/decks', {'sort': 'nope'}).status_code, 400)

    def test_mine_requires_authentication_and_returns_only_owner(self):
        self.assertEqual(self.client.get('/api/mobile/v1/decks?scope=mine').status_code, 401)
        self.client.force_authenticate(self.owner)
        result = self.client.get('/api/mobile/v1/decks?scope=mine')
        self.assertEqual([d['id'] for d in result.data['decks']], [self.mine.pk])
        self.assertEqual(self.client.get('/api/mobile/v1/decks?scope=mine&q=없음').data['count'], 0)

    def test_detail_checks_visibility_and_preserves_zone_counts(self):
        result = self.client.get(f'/api/mobile/v1/decks/{self.public.pk}')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data['cards'], [{'card_id': self.card.pk, 'count': 3, 'hand': 1, 'side': 1}])
        self.assertEqual(result.data['description'], '<p>설명</p>')
        self.assertEqual(self.client.get(f'/api/mobile/v1/decks/{self.unlisted.pk}').status_code, 200)
        for deck in [self.private, self.mine, self.deleted]:
            self.assertEqual(self.client.get(f'/api/mobile/v1/decks/{deck.pk}').status_code, 404)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.get(f'/api/mobile/v1/decks/{self.mine.pk}').status_code, 200)
        self.assertEqual(self.client.get(f'/api/mobile/v1/decks/{self.private.pk}').status_code, 404)

    def test_endpoints_are_read_only(self):
        self.client.force_authenticate(self.owner)
        for method in ['post', 'put', 'patch', 'delete']:
            for path in ['/api/mobile/v1/decks', f'/api/mobile/v1/decks/{self.mine.pk}']:
                self.assertEqual(getattr(self.client, method)(path, {}, format='json').status_code, 405)
        self.mine.refresh_from_db()
        self.assertFalse(self.mine.deleted)

    def test_pagination_and_invalid_parameters(self):
        for i in range(31):
            self.make_deck(self.other, f'페이지 {i}', 'public')
        first = self.client.get('/api/mobile/v1/decks')
        second = self.client.get('/api/mobile/v1/decks?page=2')
        self.assertEqual((first.data['count'], len(first.data['decks']), first.data['next_page']), (32, 30, 2))
        self.assertEqual((len(second.data['decks']), second.data['next_page']), (2, None))
        self.assertFalse({d['id'] for d in first.data['decks']} & {d['id'] for d in second.data['decks']})
        for query in ['page=0', 'page=no', 'character_id=-1', 'character_id=x', 'scope=other']:
            self.assertEqual(self.client.get('/api/mobile/v1/decks?' + query).status_code, 400)


    def test_bookmark_put_list_flag_and_filter(self):
        path = f'/api/mobile/v1/decks/{self.public.pk}/bookmark'
        self.assertEqual(self.client.put(path, {'bookmarked': True}, format='json').status_code, 401)
        self.client.force_authenticate(self.owner)
        self.assertEqual(self.client.put(path, {'bookmarked': 'yes'}, format='json').status_code, 400)
        self.assertEqual(self.client.post(path, {'bookmarked': True}, format='json').status_code, 405)
        for deck in [self.private, self.deleted]:
            self.assertEqual(self.client.put(f'/api/mobile/v1/decks/{deck.pk}/bookmark', {'bookmarked': True}, format='json').status_code, 404)
        DeckLike.objects.create(deck=self.public, author=self.owner, like=True)
        for _ in range(2):  # 같은 요청을 다시 보내도 토글되지 않는다.
            result = self.client.put(path, {'bookmarked': True}, format='json')
            self.assertEqual(result.data, {'id': self.public.pk, 'bookmarked': True, 'bookmark_count': 1})
        like = DeckLike.objects.get(deck=self.public, author=self.owner)
        self.assertTrue(like.like and like.bookmark)
        self.client.put(f'/api/mobile/v1/decks/{self.unlisted.pk}/bookmark', {'bookmarked': True}, format='json')
        self.client.put(f'/api/mobile/v1/decks/{self.mine.pk}/bookmark', {'bookmarked': True}, format='json')

        listed = self.client.get('/api/mobile/v1/decks').data['decks']
        self.assertEqual([(d['id'], d['bookmarked']) for d in listed], [(self.public.pk, True)])
        self.assertTrue(self.client.get(f'/api/mobile/v1/decks/{self.public.pk}').data['bookmarked'])
        ids = lambda **params: {d['id'] for d in self.client.get('/api/mobile/v1/decks', {'bookmarked': '1', **params}).data['decks']}
        self.assertEqual(ids(), {self.public.pk, self.unlisted.pk, self.mine.pk})
        self.assertEqual(ids(scope='mine'), {self.mine.pk})
        self.assertEqual(ids(q='링크'), {self.unlisted.pk})
        self.assertEqual(self.client.get('/api/mobile/v1/decks', {'bookmarked': 'x'}).status_code, 400)
        self.assertEqual(apply_sync(self.owner, [])['deck_bookmarks'], sorted([self.public.pk, self.unlisted.pk, self.mine.pk]))

        result = self.client.put(path, {'bookmarked': False}, format='json')
        self.assertEqual(result.data['bookmarked'], False)
        self.assertTrue(DeckLike.objects.get(deck=self.public, author=self.owner).like)
        self.assertFalse(self.client.get(f'/api/mobile/v1/decks/{self.public.pk}').data['bookmarked'])

        self.client.force_authenticate(None)
        self.assertEqual(self.client.get('/api/mobile/v1/decks', {'bookmarked': '1'}).status_code, 401)
        self.assertFalse(self.client.get('/api/mobile/v1/decks').data['decks'][0]['bookmarked'])

@override_settings(MOBILE_CATALOG_FETCH_IMAGES=False)
class MobileApiTests(TestCase):
    def setUp(self):
        self.root = tempfile.TemporaryDirectory()
        self.addCleanup(self.root.cleanup)
        self.override = override_settings(MOBILE_CATALOG_ROOT=Path(self.root.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user(username='mobile_user', password='test_password_739')
        self.other = User.objects.create_user(username='other_user', password='test_password_739')
        self.character = Character.objects.create(name='모바일 캐릭터', description='', group='테스트', datas={'hand':{'5000':5,'2000':3}}, img='')
        self.cards = [Card.objects.create(name=f'카드 {i}', code=f'MOB-AT-{i:03}', character=self.character, type='공격', frame=i+1, damage=100) for i in range(5)]
        self.pack = Pack.objects.create(name='모바일 팩', code='MOB')
        self.item = CollectionCard.objects.create(card=self.cards[0],character=self.character,pack=self.pack,name='카드',code='MOB-001',rare='N')
        self.qna = QNA.objects.create(title='질문',question='Q?',answer='A!')
        QNARelation.objects.create(qna=self.qna,card=self.cards[0])
        SiteSettings.objects.update_or_create(name='갯수예외처리카드',defaults={'setting':{}})
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def deck_operation(self, deck_uuid=None, name='덱'):
        return {'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':str(deck_uuid or uuid.uuid4()),'action':'upsert',
                'data':{'name':name,'character_id':self.character.id,'cards':[{'card_id':c.pk,'count':1,'hand':0,'side':0} for c in self.cards], 'visibility':'private'}}

    def collection_operation(self, amount):
        return {'operation_id':str(uuid.uuid4()),'entity':'collection','entity_id':self.item.pk,'action':'upsert','data':{'amount':amount}}

    def test_catalog_is_valid_and_hash_matches(self):
        release, changed = publish_catalog()
        self.assertTrue(changed)
        path=Path(self.root.name)/release.filename
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),release.sha256)
        with sqlite3.connect(path) as db:
            self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
            row=json.loads(db.execute('SELECT data FROM entries WHERE kind=? AND id=?',('qna',self.qna.pk)).fetchone()[0])
            self.assertEqual(row['card_ids'],[self.cards[0].pk])
        again, changed=publish_catalog()
        db.close()
        self.assertFalse(changed)
        self.assertEqual(release.pk,again.pk)

    def test_card_qna_and_rule_changes_publish_new_versions(self):
        releases=[]
        for change in ('initial','card','qna','rule','relation'):
            if change=='card':
                self.cards[0].detail_text='변경';self.cards[0].save()
            elif change=='qna':
                self.qna.answer='새 답변';self.qna.save()
            elif change=='rule':
                SiteSettings.objects.filter(name='갯수예외처리카드').update(setting={str(self.cards[0].pk):2})
            elif change=='relation':
                QNARelation.objects.create(qna=self.qna,card=self.cards[1])
            release,changed=publish_catalog();self.assertTrue(changed);releases.append(release)
        self.assertEqual(len({r.sha256 for r in releases}),5)
        self.assertEqual(CatalogRelease.objects.filter(active=True).count(),1)
        self.assertTrue(all((Path(self.root.name)/r.filename).exists() for r in releases))

    def test_failed_publish_preserves_active_release(self):
        first,_=publish_catalog()
        with patch('mobile_api.catalog.read_snapshot',side_effect=ValueError('bad snapshot')):
            with self.assertRaises(ValueError):publish_catalog()
        self.assertEqual(CatalogRelease.objects.get(active=True).pk,first.pk)

    def test_manifest_compatibility_etag_and_anonymous_download(self):
        release,_=publish_catalog(schema_version=1)
        anonymous=APIClient()
        result=anonymous.get('/api/mobile/v1/catalog/manifest')
        self.assertEqual(result.status_code,200)
        self.assertEqual(result.data['sha256'],release.sha256)
        self.assertEqual(anonymous.get('/api/mobile/v1/catalog/manifest',HTTP_IF_NONE_MATCH='"'+release.version+'"').status_code,304)
        self.assertEqual(anonymous.get('/api/mobile/v1/catalog/manifest?client_version=bad').status_code,400)
        file=anonymous.get('/api/mobile/v1/catalog/files/'+release.version)
        self.assertEqual(file.status_code,200)
        self.assertEqual(hashlib.sha256(b''.join(file.streaming_content)).hexdigest(),release.sha256)
        self.assertEqual(anonymous.get('/api/mobile/v1/catalog/images/not-a-hash.webp').status_code,404)

    def test_sync_creates_deck_once(self):
        op=self.deck_operation()
        a=apply_sync(self.user,[op]);b=apply_sync(self.user,[op])
        self.assertEqual(len(a['decks']),1);self.assertEqual(a['decks'],b['decks'])
        self.assertEqual(Deck.objects.filter(author=self.user).count(),1)
        self.assertEqual(SyncReceipt.objects.count(),1)

    def test_last_arrival_wins_and_old_retry_does_not_overwrite(self):
        old=self.collection_operation(2);new=self.collection_operation(7)
        apply_sync(self.user,[old]);apply_sync(self.user,[new]);apply_sync(self.user,[old])
        self.assertEqual(Collected.objects.get(user=self.user,card=self.item).amount,7)
        apply_sync(self.user,[self.collection_operation(0)])
        self.assertEqual(Collected.objects.get(user=self.user,card=self.item).amount,0)

    def test_collection_category_sync_and_old_clients_keep_category(self):
        op = self.collection_operation(2)
        op['data']['category'] = 4
        response = apply_sync(self.user, [op])
        self.assertEqual(response['collection'], [{'card_id': self.item.pk, 'amount': 2, 'category': 4}])
        apply_sync(self.user, [self.collection_operation(5)])  # 예전 앱: category 없음
        saved = Collected.objects.get(user=self.user, card=self.item)
        self.assertEqual((saved.amount, saved.category), (5, 4))
        for bad in [6, -1, True, '2']:
            op = self.collection_operation(1)
            op['data']['category'] = bad
            self.assertFalse(apply_sync(self.user, [op])['results'][0]['ok'])
        saved.refresh_from_db()
        self.assertEqual((saved.amount, saved.category), (5, 4))

    def test_operation_id_cannot_change_payload(self):
        op=self.collection_operation(2);apply_sync(self.user,[op]);op['data']['amount']=3
        with self.assertRaises(ValidationError):apply_sync(self.user,[op])

    def test_accounts_are_isolated(self):
        operation=self.deck_operation();apply_sync(self.user,[operation]);response=apply_sync(self.other,[operation])
        self.assertFalse(response['results'][0]['ok']);self.assertEqual(response['decks'],[])
        self.assertEqual(APIClient().get('/api/mobile/v1/sync').status_code,401)

    def test_invalid_and_locked_decks_keep_existing_contents(self):
        operation=self.deck_operation();apply_sync(self.user,[operation]);deck=Deck.objects.get(author=self.user)
        deck.locked=True;deck.save()
        changed=self.deck_operation(deck.mobile_id,name='수정')
        response=apply_sync(self.user,[changed]);self.assertFalse(response['results'][0]['ok'])
        deck.refresh_from_db();self.assertEqual(deck.name,'덱');self.assertEqual(deck.cids.count(),5)
        invalid=self.deck_operation();invalid['data']['cards'][0]['hand']=-1
        self.assertFalse(apply_sync(self.user,[invalid])['results'][0]['ok'])

    def test_partial_batch_and_soft_delete(self):
        invalid=self.collection_operation(-1);valid=self.deck_operation()
        response=apply_sync(self.user,[invalid,valid])
        self.assertFalse(response['results'][0]['ok']);self.assertTrue(response['results'][1]['ok'])
        delete={'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':valid['entity_id'],'action':'delete'}
        self.assertTrue(apply_sync(self.user,[delete])['decks'][0]['deleted'])

    def test_deleting_a_never_uploaded_draft_and_malformed_collection(self):
        delete={'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':str(uuid.uuid4()),'action':'delete'}
        self.assertTrue(apply_sync(self.user,[delete])['results'][0]['ok'])
        malformed=self.collection_operation(2);malformed['data']=[]
        self.assertFalse(apply_sync(self.user,[malformed])['results'][0]['ok'])

    def session(self):
        return create_standalone_session('p1','p2',self.character,self.character,self.user)

    def test_viewer_never_receives_control_url_or_scripts(self):
        session=self.session();state=mobile_state(session)
        self.assertFalse(state['can_control']);self.assertNotIn('control_url',state)
        self.assertNotIn('passive_ui',state['players']['p1']['character'])
        self.assertEqual(serialize_session(session)['control_url'],'')
        self.assertTrue(mobile_state(session,session.control_token)['can_control'])

    def test_calculator_duplicate_and_stale_action(self):
        session=self.session();body={'action_id':str(uuid.uuid4()),'expected_version':session.version,'action':'hp','target':'p1','amount':-100}
        updated=perform_mobile_action(session.view_token,body,session.control_token)
        again=perform_mobile_action(session.view_token,body,session.control_token)
        self.assertEqual(updated.player1_hp,4900);self.assertEqual(again.player1_hp,4900)
        self.assertEqual(CalculatorReceipt.objects.count(),1)
        body['action_id']=str(uuid.uuid4())
        with self.assertRaises(StaleCalculator):perform_mobile_action(session.view_token,body,session.control_token)
        with self.assertRaises(PermissionDenied):perform_mobile_action(session.view_token,body,'bad')

    def test_shared_passive_events_preserve_before_and_after_values(self):
        session = self.session()
        for value in (2, 3):
            body = {'action_id': str(uuid.uuid4()), 'expected_version': session.version,
                    'action': 'passive', 'target': 'p2', 'key': 'test_counter',
                    'value': value, 'label': '테스트 카운터'}
            session = perform_mobile_action(session.view_token, body, session.control_token)
        events = mobile_state(session, session.control_token)['events']
        event = next(event for event in events if event.get('payload', {}).get('key') == 'test_counter')
        self.assertEqual(event['target'], 'p2')
        self.assertEqual(event['payload']['before_state']['value'], 2)
        self.assertEqual(event['payload']['after_state']['value'], 3)

    def test_calculator_api_and_expiration(self):
        anon=APIClient();session=self.session()
        body={'action_id':str(uuid.uuid4()),'expected_version':session.version,'action':'hp','target':'p1','amount':-100}
        url=f'/api/mobile/v1/calculators/{session.view_token}/action'
        self.assertEqual(anon.post(url,body,format='json').status_code,403)
        response=anon.post(url,body,format='json',HTTP_X_CALCULATOR_CONTROL=session.control_token)
        self.assertEqual(response.status_code,200)
        body['action_id']=str(uuid.uuid4());self.assertEqual(anon.post(url,body,format='json',HTTP_X_CALCULATOR_CONTROL=session.control_token).status_code,409)
        session.expires_at=timezone.now()-timedelta(seconds=1);session.save()
        self.assertEqual(anon.post(url,body,format='json',HTTP_X_CALCULATOR_CONTROL=session.control_token).status_code,400)

    def test_login_refresh_rotation_and_logout(self):
        anon=APIClient();result=anon.post('/api/mobile/v1/auth/login',{'username':self.user.username,'password':'test_password_739'},format='json')
        self.assertEqual(result.status_code,200)
        old=result.data['refresh'];renewed=anon.post('/api/mobile/v1/auth/refresh',{'refresh':old},format='json')
        self.assertEqual(renewed.status_code,200)
        self.assertEqual(anon.post('/api/mobile/v1/auth/refresh',{'refresh':old},format='json').status_code,401)
        anon.credentials(HTTP_AUTHORIZATION='Bearer '+renewed.data['access'])
        self.assertEqual(anon.get('/api/mobile/v1/sync').status_code,200)
        self.assertEqual(anon.post('/api/mobile/v1/auth/logout',{'refresh':renewed.data['refresh']},format='json').status_code,200)

    def test_local_image_change_updates_catalog_without_app_release(self):
        media=Path(self.root.name)/'media';media.mkdir();(media/'webpsm').mkdir()
        image=media/'webpsm'/'card.webp';image.write_bytes(b'first image')
        self.cards[0].img_sm='https://images.hinoto.kr/webpsm/card.webp';self.cards[0].save()
        with override_settings(MOBILE_CATALOG_FETCH_IMAGES=True,MEDIA_ROOT=media):
            first,_=publish_catalog();image.write_bytes(b'changed image content')
            second,changed=publish_catalog()
        self.assertTrue(changed);self.assertNotEqual(first.sha256,second.sha256)
