from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import TestCase, override_settings
from card.models import Character
from .party_services import create_room, join_room, perform_party_action, serialize_room, PartyConflict, _land
from .party_supplies import spawn_supplies
from .services import perform_session_action


@override_settings(PARTY_ROLL_REVEAL_MS=0, PARTY_EVENT_REVEAL_MS=0)
class PartyEconomySupplyTests(TestCase):
    def setUp(self):
        character = Character.objects.create(name='보급함 테스트', description='', group='', datas={})
        self.room, self.host = create_room({'character_id':character.pk})
        self.room, self.guest = join_room(self.room.code, {'character_id':character.pk})
        self.room, self.third = join_room(self.room.code, {'character_id':character.pk})
        self.assertEqual(list(self.room.players.values_list('coins',flat=True)),[0,0,0])
        for p in [self.host,self.guest,self.third]: self.act('ready',p)
        self.act('start')

    def act(self, action, player=None, **data):
        self.room.refresh_from_db()
        self.room = perform_party_action(self.room.code,(player or self.host).token,
            {'action':action,'expected_version':self.room.version,**data})

    def state(self, player=None):
        self.room.refresh_from_db()
        return serialize_room(self.room,(player or self.host).token)

    def crate(self, position=3, hp=800, landed=True):
        self.host.refresh_from_db();self.host.position=position;self.host.save()
        crate={'id':'test-crate','node':position,'hp':hp,'max_hp':800,'spawn_round':1}
        self.room.document.update(supplies=[crate],landed=landed,move=None,move_prompt=None,arrival=None)
        self.room.save()
        return crate

    def rollover(self, round):
        self.room.refresh_from_db()
        self.room.document.update(round=round,turn=2,landed=True,move=None,move_prompt=None,arrival=None)
        self.room.save();self.act('end_turn',self.third)

    def battle(self):
        for p in [self.host,self.guest]:
            p.refresh_from_db();p.position=3;p.save()
        self.room.document['landed']=True;self.room.save()
        self.act('challenge',target=1)
        return self.room.encounters.get(status='active').session

    def calc(self, session, action, **data):
        return perform_session_action(session,{'action':action,**data},control_token=session.control_token)

    def finish(self, session, count=2):
        for index in range(count):session=self.calc(session,'party_exchange',expected_exchange=index)
        self.act('confirm_battle',battle_version=session.version)

    def test_starting_balance_is_zero_and_turn_income_is_still_one(self):
        self.assertEqual([p['coins'] for p in self.state()['players']],[1,0,0])

    def test_each_side_earns_two_coins_per_full_500_total_damage_in_battle(self):
        session=self.battle()
        session=self.calc(session,'hp',target='p2',amount=-400)
        session=self.calc(session,'party_exchange',expected_exchange=0)
        session=self.calc(session,'hp',target='p2',amount=-600)
        session=self.calc(session,'hp',target='p1',amount=-999)
        session=self.calc(session,'party_exchange',expected_exchange=1)
        self.act('confirm_battle',battle_version=session.version)
        self.assertEqual([p['coins'] for p in self.state()['players']],[5,2,0])
        with self.assertRaises(ValueError):self.act('confirm_battle',battle_version=session.version)
        self.assertEqual([p['coins'] for p in self.state()['players']],[5,2,0])

    def test_damage_counts_before_healing_but_undo_and_overkill_are_excluded(self):
        session=self.battle()
        session=self.calc(session,'hp',target='p2',amount=-1500)
        session=self.calc(session,'undo')
        session=self.calc(session,'hp',target='p2',amount=-700)
        session=self.calc(session,'hp',target='p2',amount=600)
        session=self.calc(session,'hp',target='p2',amount=-50000)
        self.finish(session,1)
        state=self.state()
        # 700 + 4900 effective damage, rounded down once per battle; KO adds 5.
        self.assertEqual(state['players'][0]['coins'],1+22+5)
        self.assertEqual(state['players'][0]['crystals'],1)
        self.assertEqual(state['players'][1]['hp'],0)

    def test_cancelled_battle_never_pays_partial_damage(self):
        session=self.battle();self.calc(session,'hp',target='p2',amount=-1500)
        self.act('cancel_battle')
        self.assertEqual(self.state()['players'][0]['coins'],1)

    def test_item_knockout_pays_five_coins_without_battle_damage_bonus(self):
        self.host.refresh_from_db();self.host.items=['brick'];self.host.save()
        self.guest.hp=100;self.guest.position=6;self.guest.save()
        self.act('use_item',item='brick',target=1)
        self.assertEqual(self.state()['players'][0]['coins'],6)
        self.assertEqual(self.state()['players'][0]['crystals'],1)

    def test_fortune_roll_is_one_to_three(self):
        for value in [0,1,2]:
            self.host.refresh_from_db();self.host.position=6;before=self.host.coins
            self.room.refresh_from_db()
            with patch('battlelog.party_services.secrets.randbelow',return_value=value) as roll:
                _land(self.room,self.host)
            self.assertEqual(roll.call_args.args,(3,))
            self.assertEqual(self.host.coins-before,value+1)

    def test_three_crates_spawn_after_three_complete_rounds_and_old_crates_persist(self):
        self.rollover(2);self.assertEqual(self.state()['supplies'],[])
        self.rollover(3);first=self.state()['supplies']
        self.assertEqual(len(first),3)
        self.assertEqual(len({c['node'] for c in first}),3)
        self.assertTrue(all(c['hp']==800 for c in first))
        self.assertFalse(set(c['node'] for c in first)&set(self.room.players.values_list('position',flat=True)))
        self.room.document['supplies'][0]['hp']=200;self.room.save()
        self.assertEqual(spawn_supplies(self.room),[])
        self.rollover(6);state=self.state()
        self.assertEqual(len(state['supplies']),6)
        self.assertEqual(len({c['node'] for c in state['supplies']}),6)
        self.assertEqual(next(c for c in state['supplies'] if c['id']==first[0]['id'])['hp'],200)

    def test_passing_supply_pauses_without_landing_effect_then_resumes_after_attack(self):
        self.crate()
        self.host.position=2;self.host.save()
        self.room.document.update(landed=False,move={'remaining':3},move_prompt=None);self.room.save()
        self.act('advance')
        state=self.state()
        self.assertEqual(state['players'][0]['position'],3)
        self.assertEqual(state['players'][0]['fp'],0)
        self.assertEqual(state['move']['remaining'],2)
        self.assertEqual(state['move_prompt']['supply'],'test-crate')
        self.act('attack_supply',crate_id='test-crate',speeds=[2,6,9,12],damage=400)
        state=self.state()
        self.assertEqual(state['supplies'][0]['hp'],400)
        self.assertEqual(state['players'][0]['position'],5)
        self.assertEqual(state['players'][0]['hp'],5000)
        self.assertEqual(state['players'][0]['fp'],0)

    def test_exact_landing_effect_occurs_once_and_supply_choice_blocks_auto_end(self):
        self.crate();self.host.position=2;self.host.save()
        self.room.document.update(landed=False,move={'remaining':1});self.room.save()
        self.act('advance');state=self.state()
        self.assertEqual(state['players'][0]['fp'],2)
        self.assertFalse(state['can_auto_end_turn'])
        with self.assertRaises(ValueError):self.act('auto_end_turn')
        self.act('skip_supply',crate_id='test-crate')
        self.assertTrue(self.state()['can_auto_end_turn'])
        self.assertEqual(self.state()['players'][0]['fp'],2)
        self.assertEqual(self.state()['supplies'][0]['hp'],800)

    def test_supply_combo_has_no_card_count_limit_and_destruction_pays_only_two_coins(self):
        self.crate()
        self.act('attack_supply',crate_id='test-crate',speeds=list(range(100)),damage=10000)
        state=self.state()
        self.assertEqual(state['supplies'],[])
        self.assertEqual(state['players'][0]['coins'],3)
        self.assertEqual(state['players'][0]['crystals'],0)
        with self.assertRaises(ValueError):self.act('attack_supply',crate_id='test-crate',speeds=[1],damage=800)

    def test_invalid_or_stale_combo_does_not_consume_the_choice(self):
        self.crate()
        for speeds,damage in [([],800),([3,3],800),([5,2],800),([True,4],800),([1],0),([1],-100),([1],True)]:
            with self.assertRaises(ValueError):self.act('attack_supply',crate_id='test-crate',speeds=speeds,damage=damage)
            self.assertEqual(self.state()['supply_encounter']['hp'],800)
        with self.assertRaises(PartyConflict):self.act('attack_supply',crate_id='old',speeds=[1],damage=800)
        with self.assertRaises(PermissionDenied):self.act('attack_supply',self.guest,crate_id='test-crate',speeds=[1],damage=800)

    def test_partial_combo_is_once_per_visit_but_another_player_can_finish(self):
        self.crate()
        self.act('attack_supply',crate_id='test-crate',speeds=[3,7],damage=400)
        self.assertIsNone(self.state()['supply_encounter'])
        with self.assertRaises(ValueError):self.act('attack_supply',crate_id='test-crate',speeds=[8],damage=400)
        self.guest.position=3;self.guest.save()
        self.room.document.update(turn=1,turn_number=2);self.room.save()
        self.act('attack_supply',self.guest,crate_id='test-crate',speeds=[1,5,9],damage=400)
        self.assertEqual(self.state()['supplies'],[])
        self.assertEqual(self.state()['players'][1]['coins'],2)

    def test_dash_waits_for_supply_choice_before_rolling_again(self):
        self.crate(position=1,landed=False)
        self.room.document['arrival']='dash';self.room.save()
        with self.assertRaises(ValueError):self.act('roll')
        self.act('skip_supply',crate_id='test-crate')
        self.act('roll')

    def test_public_supply_positions_do_not_leak_participant_permissions(self):
        self.crate()
        state=serialize_room(self.room)
        self.assertEqual(state['supplies'][0]['node'],3)
        self.assertIsNone(state['supply_encounter'])
        self.assertNotIn(self.host.token,str(state))

    def test_buffered_damage_is_not_lost_or_double_counted_during_flush(self):
        session=self.battle()
        session=self.calc(session,'hp',target='p2',amount=-500)
        event=session.events.get(event_type='hp')
        record={'session_id':session.pk,'event_uid':str(event.event_uid),'event_type':'hp','target':'p2',
                'hp_before':5000,'hp_after':4500,'amount':-500,'created_at':event.created_at.isoformat()}
        with patch('battlelog.event_buffer.pending_event_records',return_value=[record]):
            self.finish(session)
        self.assertEqual(self.state()['players'][0]['coins'],3)

    def test_declined_pvp_then_supply_choice_resumes_remaining_move(self):
        self.crate()
        self.host.position=2;self.host.save()
        self.guest.position=3;self.guest.save()
        self.room.document.update(landed=False,move={'remaining':3},move_prompt=None);self.room.save()
        self.act('advance');self.act('skip_challenge')
        self.act('skip_supply',crate_id='test-crate')
        self.assertEqual(self.state()['players'][0]['position'],5)

    def test_camp_purchase_reward_and_supply_choices_both_remain_available(self):
        self.crate(position=5)
        self.host.coins=3;self.host.save()
        _land(self.room,self.host);self.room.save()
        state=self.state()
        self.assertIsNotNone(state['camp_gift'])
        self.assertIsNotNone(state['supply_encounter'])
        self.act('skip_camp_gift')
        self.act('skip_supply',crate_id='test-crate')
        self.assertTrue(self.state()['can_auto_end_turn'])
