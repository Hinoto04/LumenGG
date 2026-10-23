import copy
import json
import tempfile
import uuid
from pathlib import Path
from unittest.mock import patch
from django.contrib.auth.models import User, AnonymousUser
from django.core.exceptions import ValidationError, PermissionDenied
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from . import test_regulations as fixtures
from .models import Regulation, RegulationVersion, ReserveCardInDeck
from .regulations import DEFAULT_RULES
from .validation import snapshot_deck


class FeatureApiTests(TestCase):
    setUp = fixtures.RegulationTests.setUp

    def version(self, **rules):
        return RegulationVersion.objects.create(regulation=Regulation.objects.create(name='Local', owner=self.user), version='1', rules={**DEFAULT_RULES, **rules})

    def test_policy_ownership_and_private_deck_options(self):
        version = self.version()
        other = User.objects.create_user('other')
        client = APIClient()
        client.force_authenticate(other)
        response = client.post('/api/mobile/v1/regulations', {'name':'Local', 'version':'2', 'regulation_id':version.regulation_id, 'rules':DEFAULT_RULES}, format='json')
        self.assertEqual(response.status_code, 403)
        self.deck.visibility = 'private'
        self.deck.save()
        self.assertEqual(client.get('/deck/options', {'deck_id':self.deck.pk}).status_code,403)
        client.force_authenticate(self.user)
        self.assertEqual(client.get('/deck/options', {'deck_id':self.deck.pk}).status_code,200)
        self.client.force_login(self.user)
        browser = self.client.get('/deck/options', {'deck_id':self.deck.pk})
        self.assertEqual(browser.status_code,200)
        self.assertIn(version.pk, [row['id'] for row in browser.json()['versions']])

    def test_legacy_sync_cannot_erase_modern_reserve(self):
        from mobile_api.sync import apply_sync
        ReserveCardInDeck.objects.create(deck=self.deck,card=self.other)
        op = {'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':str(self.deck.mobile_id),'action':'upsert','data':{'name':'old','character_id':self.character.pk,'cards':[]}}
        result = apply_sync(self.user,[op])
        self.assertFalse(result['results'][0]['ok'])
        self.assertEqual(self.deck.reserve_entries.count(),1)
        self.deck.refresh_from_db()
        self.assertEqual(self.deck.name,'Test')

    def test_v2_sync_keeps_incomplete_drafts(self):
        from mobile_api.sync import apply_sync, deck_payload
        payload = deck_payload(self.deck)
        payload['cards'] = payload['cards'][:2]
        op = {'schema_version':2,'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':str(self.deck.mobile_id),'action':'upsert','data':payload}
        result=apply_sync(self.user,[op])
        self.assertTrue(result['results'][0]['ok'],result)
        self.assertEqual(self.deck.cids.count(),2)

    def test_copy_retains_foreign_policy_and_import_creates_owned_policy(self):
        from .views.views import copy_deck_instance
        from mobile_api.sync import deck_payload, apply_sync
        version=self.version(reserve_limit=2)
        self.deck.regulation_version=version;self.deck.save()
        recipient=User.objects.create_user('recipient')
        copied=copy_deck_instance(self.deck,recipient)
        payload=deck_payload(copied)
        def operation(deck,data):return {'schema_version':2,'operation_id':str(uuid.uuid4()),'entity':'deck','entity_id':str(deck.mobile_id),'action':'upsert','data':data}
        self.assertTrue(apply_sync(recipient,[operation(copied,payload)])['results'][0]['ok'])
        imported=copy_deck_instance(self.deck,recipient)
        imported.regulation_version=None;imported.save()
        data=deck_payload(self.deck);data['imported_regulation']=data['regulation']
        self.assertTrue(apply_sync(recipient,[operation(imported,data)])['results'][0]['ok'])
        imported.refresh_from_db()
        self.assertEqual(imported.regulation_version.regulation.owner_id,recipient.pk)
        self.assertNotEqual(imported.regulation_version_id,version.pk)

    def test_trait_reset_and_inactive_controls(self):
        from battlelog.services import create_standalone_session, perform_session_action
        self.other.trait_config={'initial_hp':4000,'initial_passive_state':{'new':{'count':4}},'battle_passive_ui':{'options':{'controls':[{'type':'counter','key':'new','label':'New','initial':4}]}}}
        self.other.save()
        session=create_standalone_session('A','B',self.character,self.character,trait_ids=[self.other.pk,self.trait.pk])
        self.assertEqual(session.player1_initial_hp,4000)
        with self.assertRaises(ValueError):
            perform_session_action(session,{'action':'passive','target':'p1','key':'inactive','value':True},control_token=session.control_token)
        session=perform_session_action(session,{'action':'passive','target':'p1','key':'new','value':9},control_token=session.control_token)
        session=perform_session_action(session,{'action':'reset_session'},control_token=session.control_token)
        self.assertEqual(session.player1_passive_state['new']['count'],4)
        self.assertEqual(session.player1_hp,4000)

    def test_optional_deck_tournament_remains_unchecked(self):
        from tournament.models import Tournament, TournamentParticipant, TournamentDeckSubmission
        from tournament.services import revalidate_submissions
        tournament = Tournament.objects.create(name='No deck required', organizer=self.user,
            regulation_version=self.version(), decklist_required_count=0)
        participant = TournamentParticipant.objects.create(tournament=tournament, user=self.user)
        submission = TournamentDeckSubmission.objects.create(participant=participant, deck=self.deck, slot=1)
        submission.snapshot['cards'] = []
        submission.save(update_fields=['snapshot'])
        self.assertEqual(revalidate_submissions(tournament, require_all=True), [])
        submission.refresh_from_db()
        self.assertIsNone(submission.validation['is_valid'])

    def test_immutable_submission_and_calculator_preparation(self):
        from tournament.models import Tournament,TournamentParticipant,TournamentDeckSubmission,TournamentRound,TournamentMatch
        from tournament.services import revalidate_submissions
        from battlelog.services import get_or_create_tournament_session,serialize_session
        from mobile_api.calculators import perform_mobile_action
        version=self.version()
        opponent=User.objects.create_user('opponent')
        tournament=Tournament.objects.create(name='Match',organizer=self.user,regulation_version=version,decklist_required_count=1)
        p1=TournamentParticipant.objects.create(tournament=tournament,user=self.user)
        p2=TournamentParticipant.objects.create(tournament=tournament,user=opponent)
        frozen=snapshot_deck(self.deck,version)
        for p in (p1,p2):TournamentDeckSubmission.objects.create(participant=p,deck=self.deck,snapshot=frozen)
        self.deck.cids.filter(card=self.cards[19]).delete()
        self.assertEqual(revalidate_submissions(tournament,require_all=True),[])
        tournament.status='running';tournament.save()
        round=TournamentRound.objects.create(tournament=tournament,number=1,set_count=3)
        match=TournamentMatch.objects.create(round=round,table_no=1,player1=p1,player2=p2)
        session=get_or_create_tournament_session(match)
        self.assertEqual(session.preparation['status'],'editing')
        public=serialize_session(session,AnonymousUser())
        self.assertNotIn('registered',public['preparation']['players']['p1'])
        for side,user in (('p1',self.user),('p2',opponent)):
            session=perform_mobile_action(session.view_token,{'action':'preparation','target':side,'preparation_action':'ready','request_id':str(uuid.uuid4()),'action_id':str(uuid.uuid4()),'expected_version':session.version,'preparation_version':session.preparation['version']},user=user)
        self.assertEqual(session.preparation['status'],'playing')
        self.assertEqual(session.player1_hp,5000)
        self.assertEqual(len(session.sets.get(set_number=1).setup_snapshot['players']['p1']['active']['cards']),20)
        next_version=self.version()
        tournament.regulation_version=next_version
        with self.assertRaises(ValidationError):tournament.save()

    def test_schema_two_catalog_does_not_replace_legacy_release(self):
        from mobile_api.catalog import publish_catalog
        with tempfile.TemporaryDirectory() as directory, override_settings(MOBILE_CATALOG_ROOT=directory,MOBILE_CATALOG_FETCH_IMAGES=False):
            legacy,_=publish_catalog(schema_version=1)
            modern,_=publish_catalog(schema_version=2)
            client=APIClient()
            self.assertEqual(client.get('/api/mobile/v1/catalog/manifest').data['release_version'],legacy.version)
            result=client.get('/api/mobile/v1/catalog/manifest?schema_version=2&client_version=1.1.0')
            self.assertEqual(result.data['release_version'],modern.version)
            legacy.refresh_from_db();self.assertTrue(legacy.active)
