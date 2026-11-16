"""CB04 2차 공개분(CMYK·델피·부쿠키·타오) 자동 효과 초안의 엔진 동작 테스트."""

from django.test import SimpleTestCase

from .game.drafts import build_effect_draft
from .test_automatic_engine import attack, base_state, defense
from . import test_cb04_automatic as first_wave
from .test_cb04_automatic import bukuki


DRUM_DEFINITION = {
    'schema_version': 1, 'reviewed': True, 'no_effect': False,
    'abilities': [{
        'id': 'test-drum-n1', 'kind': 'effect', 'mode': 'mandatory', 'timing': 'use',
        'visibility': 'public', 'draft_compiled': True,
        'effects': [{'op': 'change_fp', 'player': {'controller': True}, 'amount': 1}],
        'condition': {'op': 'all', 'conditions': [
            {'op': 'equals', 'left': 'context.source_card.attached_to',
             'right': {'path': 'context.event_card.instance_id'}},
            {'op': 'card_matches', 'card': {'path': 'context.event_card'},
             'where': {'character_key': 'cmyk'}},
        ]},
        'trigger': {'event': 'use'}, 'active_when_attached': True,
        'dedupe_trigger_key': 'cmyk:set:drum',
    }],
}


def cmyk(card):
    card['character_key'] = 'cmyk'
    return card


def tao(card):
    card['character_key'] = 'tao'
    return card


class CB04SecondWaveAutomaticEffectTests(SimpleTestCase):
    engine_for = first_wave.CB04AutomaticEffectTests.engine_for
    resolve = first_wave.CB04AutomaticEffectTests.resolve
    frost = first_wave.CB04AutomaticEffectTests.frost

    def use(self, engine, card, event='use', **extra):
        engine._fire(event, {
            'controller': card['owner'], 'source_card': card,
            'source_card_instance_id': card['instance_id'], **extra,
        })
        self.resolve(engine)

    def blocked(self, engine, kind, side):
        return any(
            item.get('op') == 'prevent' and item.get('kind') == kind and item.get('player') == side
            for item in engine.engine_state.get('replacements') or []
        )

    def test_fan_service_blocks_clash_only_with_a_set_card_and_gains_list_once(self):
        for attached in (False, True):
            with self.subTest(attached=attached):
                host = cmyk(attack('host', 'p1', code='CB04-AT-035', frame=11))
                setter = cmyk(attack('setter', 'p1', code='SET-001'))
                state = base_state([], [])
                state['players']['p1']['zones']['battle'] = [host, setter]
                engine = self.engine_for(state, [host, setter], seed=f'fan-service-{attached}')
                if attached:
                    engine.attach_card('setter', 'host', controller='p1')
                self.use(engine, host, 'before_judgment')
                self.assertEqual(self.blocked(engine, 'clash', 'p2'), attached)

        listed = [attack(f'listed-{index}', 'p1', code=f'LIST-{index}') for index in range(3)]
        host = cmyk(attack('host', 'p1', code='CB04-AT-035'))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [host]
        state['players']['p1']['zones']['list'] = listed
        engine = self.engine_for(state, [host, *listed], seed='fan-service-gain')
        decision_options = []
        engine._fire('hit', {'controller': 'p1', 'source_card': host, 'source_card_instance_id': 'host'})
        decision = engine.engine_state['pending_decision']
        self.assertEqual(decision['maximum'], 2)
        decision_options = [item['id'] for item in decision['options']]
        engine._submit_decision('p1', decision['id'], decision_options[:2])
        engine._continue()
        self.use(engine, host, 'combo')
        self.assertEqual(len(engine.state['players']['p1']['zones']['hand']), 2)
        self.assertEqual(len(engine.state['players']['p1']['zones']['list']), 1)

    def test_chromatic_alternate_replaces_set_drum_fp_with_damage(self):
        for with_drum in (False, True):
            with self.subTest(with_drum=with_drum):
                host = cmyk(attack('host', 'p1', code='CB04-AT-036', frame=5, damage=300))
                drum = cmyk(attack('drum', 'p1', code='DRUM-001'))
                drum['text'] = '①[[token:drum]](<[[character:cmyk]]> 기술에 세트된 경우, 사용 시 1FP를 얻는다.)'
                state = base_state([], [])
                state['players']['p1']['zones']['battle'] = [host, drum]
                engine = self.engine_for(state, [host, drum], seed=f'chromatic-{with_drum}')
                engine.ruleset['cards']['DRUM-001']['effect_definition'] = DRUM_DEFINITION
                if with_drum:
                    engine.attach_card('drum', 'host', controller='p1')

                self.use(engine, host)

                self.assertEqual(engine.state['players']['p1']['fp'], 0)
                self.assertEqual(engine.card_stat(host, 'damage', 'p1'), 500 if with_drum else 300)

    def test_chromatic_alternate_drum_without_the_replacement_still_gains_fp(self):
        host = cmyk(attack('host', 'p1', code='OTHER-HOST', damage=300))
        drum = cmyk(attack('drum', 'p1', code='DRUM-001'))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [host, drum]
        engine = self.engine_for(state, [host, drum], seed='plain-drum')
        engine.ruleset['cards']['DRUM-001']['effect_definition'] = DRUM_DEFINITION
        engine.attach_card('drum', 'host', controller='p1')

        self.use(engine, host)

        self.assertEqual(engine.state['players']['p1']['fp'], 1)

    def test_rainbow_train_dodges_non_combo_and_gains_one_per_set_card(self):
        train = cmyk(defense('train', 'p1', top='회피', mid='회피'))
        train['code'] = 'CB04-AT-037'
        combo_attack = attack('combo-attack', 'p2', hit='콤보')
        plain_attack = attack('plain-attack', 'p2', hit='3')
        set_cards = [cmyk(attack(f'set-{index}', 'p1', code=f'SET-{index}')) for index in range(2)]
        listed = [attack(f'listed-{index}', 'p1', code=f'LIST-{index}') for index in range(3)]
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [train, *set_cards]
        state['players']['p1']['zones']['list'] = listed
        engine = self.engine_for(
            state, [train, combo_attack, plain_attack, *set_cards, *listed], seed='rainbow-train',
        )
        self.assertFalse(engine._defense_judgment_allowed(train, combo_attack, 'dodge', 'p2'))
        self.assertTrue(engine._defense_judgment_allowed(train, plain_attack, 'dodge', 'p2'))
        for card in set_cards:
            engine.attach_card(card['instance_id'], 'train', controller='p1')

        engine._fire('dodge', {'controller': 'p1', 'source_card': train, 'source_card_instance_id': 'train'})
        decision = engine.engine_state['pending_decision']
        self.assertEqual((decision['minimum'], decision['maximum']), (2, 2))
        self.resolve(engine)

        self.assertEqual(engine.state['players']['p1']['fp'], 2)
        self.assertEqual(len(engine.state['players']['p1']['zones']['hand']), 2)

    def test_garage_token_is_a_token_or_counter(self):
        definition = build_effect_draft('CB04-TK-001', '')
        self.assertEqual(definition['token_key'], 'garage')
        self.assertEqual(definition['token_usage'], ['token', 'counter'])

    def test_silent_out_counter_break_gives_frost_and_dodge_gives_three_fp(self):
        silent = bukuki(attack('silent', 'p1', code='CB04-AT-003', frame=6, damage=400))
        listed = attack('listed', 'p1', code='LIST-001')
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [silent]
        state['players']['p1']['zones']['list'] = [listed]
        engine = self.engine_for(state, [silent, listed], seed='silent-out')

        self.use(engine, silent, 'opponent_dodge')
        self.assertEqual(engine.state['players']['p2']['fp'], 3)
        self.use(engine, silent, 'counter')
        self.assertIsNotNone(engine._find_card('listed', owner='p1', zone='break'))
        self.assertTrue(self.frost(engine, 'p2'))
        engine._refresh_continuous_rules()
        self.assertEqual(engine.card_stat(silent, 'damage', 'p1'), 600)

    def test_glasskate_break_from_list_sends_side_bukuki_to_lumen(self):
        skate = bukuki(attack('skate', 'p1', code='CB04-AT-004', frame=7))
        listed = attack('listed', 'p1', code='LIST-001')
        side_bukuki = bukuki(attack('side-bukuki', 'p1', code='CB04-AT-011'))
        side_other = attack('side-other', 'p1', code='OTHER-SIDE')
        fast = attack('fast', 'p2', frame=8)
        slow = attack('slow', 'p2', frame=9)
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [skate]
        state['players']['p1']['zones']['list'] = [listed]
        state['players']['p1']['zones']['side'] = [side_bukuki, side_other]
        engine = self.engine_for(state, [skate, listed, side_bukuki, side_other, fast, slow], seed='glasskate')
        self.assertTrue(engine._defense_judgment_allowed(skate, fast, 'dodge', 'p2'))
        self.assertFalse(engine._defense_judgment_allowed(skate, slow, 'dodge', 'p2'))

        self.use(engine, skate, 'hit')

        self.assertIsNotNone(engine._find_card('listed', owner='p1', zone='break'))
        self.assertIsNotNone(engine._find_card('side-bukuki', owner='p1', zone='lumen'))
        self.assertIsNotNone(engine._find_card('side-other', owner='p1', zone='side'))

    def test_glacial_bloom_breaks_from_lumen_on_opponent_hit_for_shield_and_fp(self):
        bloom = bukuki(attack('bloom', 'p1', code='CB04-AT-006', frame=8))
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = [bloom]
        engine = self.engine_for(state, [bloom], seed='glacial-bloom')

        engine._fire('opponent_hit', {'controller': 'p2'})
        self.assertIsNone(engine.engine_state.get('pending_decision'))
        engine._fire('opponent_hit', {'controller': 'p1'})
        self.resolve(engine)

        self.assertIsNotNone(engine._find_card('bloom', owner='p1', zone='break'))
        self.assertEqual(engine.state['players']['p1']['fp'], 3)
        self.assertEqual(sum(item.get('amount', 0) for item in engine.engine_state['shields']['p1']), 400)

    def test_glacial_bloom_clash_changes_opponent_hit_judgment(self):
        definition = build_effect_draft('CB04-AT-006', '')
        self.assertEqual(definition['defense_rules'], [{'judgment': 'clash', 'max_speed': 8}])
        clash = next(item for item in definition['abilities'] if item['id'] == 'cb04-at-006-n1')
        self.assertEqual(clash['effects'], [{
            'op': 'modify_judgment', 'player': {'opponent': True}, 'field': 'hit', 'value': '-2',
        }])

    def test_drunken_spirit_fixes_speeds_spends_yang_and_gains_yin_in_yin_state(self):
        spirit = tao(attack('spirit', 'p1', code='CB04-AT-021', frame=13, damage=500))
        enemy = attack('enemy', 'p2', frame=7)
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [spirit]
        state['players']['p2']['zones']['battle'] = [enemy]
        engine = self.engine_for(state, [spirit, enemy], seed='drunken-spirit')
        engine.change_counter('p1', 'yang', 1)
        engine.set_passive('p1', 'yin', value=True)

        engine._fire('before_judgment', {
            'controller': 'p1', 'source_card': spirit, 'source_card_instance_id': 'spirit',
            'controller_speed': 13, 'opponent_speed': 7,
        })
        decision = engine.engine_state['pending_decision']
        engine._submit_decision('p1', decision['id'], ['1'])
        engine._continue()
        self.resolve(engine)

        counters = engine.state['players']['p1']['passive_state']
        self.assertEqual(counters['yang'].get('count'), 0)
        self.assertEqual(counters['yin'].get('count'), 1)
        self.assertTrue(any(item.get('op') == 'fix_speed' for item in engine.engine_state.get('modifiers') or []))

        engine.set_passive('p1', 'harmony', value=True)
        self.use(engine, spirit, 'hit')
        self.assertEqual(engine.card_stat(spirit, 'damage', 'p1'), 900)

    def test_twin_tail_fp_depends_on_yang_counters_and_yang_state(self):
        for yang_state, expected in ((False, 1), (True, 3)):
            with self.subTest(yang_state=yang_state):
                tail = tao(attack('tail', 'p1', code='CB04-AT-022', frame=10))
                state = base_state([], [])
                state['players']['p1']['zones']['battle'] = [tail]
                engine = self.engine_for(state, [tail], seed=f'twin-tail-{yang_state}')
                engine.change_counter('p1', 'yang', 3)
                # 팔괘엔진이 관리하는 「양」 상태 값을 카운터 수와 별도로 지정한다.
                engine.state['players']['p1']['passive_state']['yang']['value'] = yang_state

                self.use(engine, tail, 'before_judgment')

                self.assertEqual(engine.state['players']['p1']['fp'], expected)

    def test_drunken_spirit_yin_text_is_decided_when_triggered(self):
        # Q-AUTO-019: 「음」 문구는 유발 시점의 상태로 정해지고, 해결 중 상태 변화는 반영하지 않는다.
        for yin_at_trigger, yin_after_removal, expected in ((False, True, None), (True, False, 1)):
            with self.subTest(yin_at_trigger=yin_at_trigger):
                spirit = tao(attack('spirit', 'p1', code='CB04-AT-021', frame=13))
                enemy = attack('enemy', 'p2', frame=7)
                state = base_state([], [])
                state['players']['p1']['zones']['battle'] = [spirit]
                state['players']['p2']['zones']['battle'] = [enemy]
                engine = self.engine_for(state, [spirit, enemy], seed=f'spirit-snapshot-{yin_at_trigger}')
                engine.change_counter('p1', 'yang', 1)
                engine.set_passive('p1', 'yin', value=yin_at_trigger)

                engine._fire('before_judgment', {
                    'controller': 'p1', 'source_card': spirit, 'source_card_instance_id': 'spirit',
                    'controller_speed': 13, 'opponent_speed': 7,
                })
                decision = engine.engine_state['pending_decision']
                engine.set_passive('p1', 'yin', value=yin_after_removal)
                engine._submit_decision('p1', decision['id'], ['1'])
                engine._continue()
                self.resolve(engine)

                yin = engine.state['players']['p1']['passive_state']['yin']
                self.assertEqual(yin.get('count'), expected)

    def test_twin_tail_yang_text_is_decided_when_triggered(self):
        tail = tao(attack('tail', 'p1', code='CB04-AT-022', frame=10))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [tail]
        engine = self.engine_for(state, [tail], seed='twin-tail-snapshot')
        engine.change_counter('p1', 'yang', 3)
        engine.state['players']['p1']['passive_state']['yang']['value'] = True

        engine.resolver.collect('before_judgment', {
            'controller': 'p1', 'source_card': tail, 'source_card_instance_id': 'tail',
        })
        engine.state['players']['p1']['passive_state']['yang']['value'] = False
        engine.resolver.drain()
        self.resolve(engine)

        self.assertEqual(engine.state['players']['p1']['fp'], 3)

    def test_twin_tail_combo_end_gains_own_battle_techniques_only(self):
        tail = tao(attack('tail', 'p1', code='CB04-AT-022'))
        combo_card = attack('combo-card', 'p1', code='COMBO-001')
        enemy = attack('enemy', 'p2', code='ENEMY-001')
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [tail, combo_card]
        state['players']['p2']['zones']['battle'] = [enemy]
        engine = self.engine_for(state, [tail, combo_card, enemy], seed='twin-tail-combo-end')
        ability = next(
            item for item in build_effect_draft('CB04-AT-022', '')['abilities']
            if item['id'] == 'cb04-at-022-n3'
        )

        engine.resolver.execute_effects(ability['effects'], {
            'controller': 'p1', 'opponent': 'p2', 'source_card': tail, 'source_card_instance_id': 'tail',
        })

        self.assertEqual(
            sorted(card['instance_id'] for card in engine.state['players']['p1']['zones']['hand']),
            ['combo-card', 'tail'],
        )
        self.assertIsNotNone(engine._find_card('enemy', owner='p2', zone='battle'))

    def test_arctic_javelin_blocks_opponent_fp_from_attack_effects_only(self):
        javelin = bukuki(attack('javelin', 'p1', code='CB04-AT-010', frame=12))
        enemy_attack = attack('enemy-attack', 'p2', code='ENEMY-ATK')
        enemy_defense = defense('enemy-defense', 'p2')
        own_attack = attack('own-attack', 'p1', code='OWN-ATK')
        state = base_state([], [])
        state['players']['p1']['zones']['lumen'] = [javelin]
        engine = self.engine_for(state, [javelin, enemy_attack, enemy_defense, own_attack], seed='arctic-javelin')
        engine._refresh_continuous_rules()
        gain = {'op': 'change_fp', 'player': {'controller': True}, 'amount': 2}

        for card, side in ((enemy_attack, 'p2'), (enemy_defense, 'p2'), (own_attack, 'p1')):
            engine.resolver.execute_effect(gain, {
                'controller': side, 'opponent': 'p1' if side == 'p2' else 'p2',
                'source_card': card, 'source_card_instance_id': card['instance_id'],
            })

        self.assertEqual(engine.state['players']['p2']['fp'], 2)
        self.assertEqual(engine.state['players']['p1']['fp'], 2)

        # Q-AUTO-015: 자신의 공격 기술 효과로 상대가 얻는 FP는 막지 않는다
        # (윈터 팽스·사일런트 아웃의 '상대는 N FP를 얻는다').
        engine.resolver.execute_effect(
            {'op': 'change_fp', 'player': {'opponent': True}, 'amount': 3},
            {'controller': 'p1', 'opponent': 'p2',
             'source_card': own_attack, 'source_card_instance_id': own_attack['instance_id']},
        )
        self.assertEqual(engine.state['players']['p2']['fp'], 5)

    def test_arctic_javelin_moves_from_list_to_lumen_on_own_clash(self):
        javelin = bukuki(attack('javelin', 'p1', code='CB04-AT-010'))
        state = base_state([], [])
        state['players']['p1']['zones']['list'] = [javelin]
        engine = self.engine_for(state, [javelin], seed='arctic-javelin-clash')

        engine._fire('clash', {'controller': 'p2'})
        self.assertIsNotNone(engine._find_card('javelin', owner='p1', zone='list'))
        engine._fire('clash', {'controller': 'p1'})
        self.resolve(engine)
        self.assertIsNotNone(engine._find_card('javelin', owner='p1', zone='lumen'))

    def test_frostborn_rules_and_frost_damage(self):
        definition = build_effect_draft('CB04-AT-011', '')
        self.assertEqual(definition['combo_rules'], [{'min_combo': 4}])
        frostborn = bukuki(attack('frostborn', 'p1', code='CB04-AT-011', frame=13, damage=600))
        state = base_state([], [])
        state['players']['p1']['zones']['battle'] = [frostborn]
        engine = self.engine_for(state, [frostborn], seed='frostborn')
        engine._refresh_continuous_rules()
        self.assertTrue(self.blocked(engine, 'clash', 'p2'))
        engine.set_passive('p2', 'frost', value=True)
        engine._refresh_continuous_rules()
        self.assertEqual(engine.card_stat(frostborn, 'damage', 'p1'), 800)

    def test_cold_release_drains_fp_and_gives_frost_only_without_damage(self):
        for damage_received, expected_fp in ((0, 2), (300, 10)):
            with self.subTest(damage_received=damage_received):
                release = bukuki(defense('release', 'p1'))
                release['code'] = 'CB04-AT-013'
                state = base_state([], [], p2_fp=10)
                state['players']['p1']['zones']['battle'] = [release]
                engine = self.engine_for(state, [release], seed=f'cold-release-{damage_received}')

                self.use(engine, release, 'after_judgment', controller_damage_received=damage_received)

                self.assertEqual(engine.state['players']['p2']['fp'], expected_fp)
                self.assertEqual(bool(self.frost(engine, 'p2')), damage_received == 0)
