"""Isolated visual-review server. Only writes under the repository's .temp/."""
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
directory = root / '.temp/deck-regulations-review'
directory.mkdir(parents=True, exist_ok=True)
os.environ['DJANGO_SETTINGS_MODULE'] = 'LumenGG.test_settings'
os.environ['LUMENGG_TEST_SQLITE_PATH'] = str(directory / 'review.sqlite')
sys.path.insert(0, str(root / 'LumenGG'))
import django
django.setup()
from django.core.management import call_command
call_command('migrate', interactive=False, verbosity=0)
from django.conf import settings
settings.ALLOWED_HOSTS = ['127.0.0.1', 'localhost']
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from card.models import Character, Card
from common.models import SiteSettings
from deck.models import Deck, CardInDeck, ReserveCardInDeck, Regulation, RegulationVersion
from deck.regulations import DEFAULT_RULES
from deck.validation import snapshot_deck
from battlelog.simulator_services import create_simulator_session
from battlelog.services import create_standalone_session

user, _ = User.objects.get_or_create(username='local-review', defaults={'is_staff': True})
SiteSettings.objects.get_or_create(name='갯수예외처리카드', defaults={'setting': {}})
Character.objects.get_or_create(pk=1, defaults={'name':'세츠메이','datas':{}})
character, _ = Character.objects.get_or_create(name='루트', defaults={'datas':{'hand':{'5000':5}}, 'localization_key':'root'})
image = '/static/v2/calculator-character/root/emblem.png'
traits = []
for n in (1, 2):
    trait, _ = Card.objects.get_or_create(code=f'REVIEW-PS-{n:03}', defaults={'name':f'특성 {n}', 'type':'특성','character':character,'img':image,'img_sm':image,
        'effect_definition':{'deck_rules':{'main_size':20}},
        'trait_config':{'initial_passive_state':{f'charge_{n}':{'count':n}},'battle_passive_ui':{'options':{'controls':[{'type':'counter','key':f'charge_{n}','label':f'차지 {n}','initial':n}]}}}})
    traits.append(trait)
cards = []
for n in range(21):
    card, _ = Card.objects.get_or_create(code=f'REVIEW-AT-{n:03}', defaults={'name':f'검증 기술 {n+1}', 'type':'공격','character':character,'img':image,'img_mid':image,'img_sm':image,'frame':n%10+1,'damage':100})
    cards.append(card)
regulation, _ = Regulation.objects.get_or_create(name='교체 검증 규정', owner=user)
version, _ = RegulationVersion.objects.get_or_create(regulation=regulation, version='1', defaults={'rules':{**DEFAULT_RULES,'reserve_limit':3,'technique_swap_limit':2,'trait_swap_limit':1,'ultimate_swap_limit':1}})
deck, created = Deck.objects.get_or_create(name='교체 덱 검증', author=user, defaults={'character':character,'trait_card':traits[0],'regulation_version':version,'schema_version':2,'visibility':'public'})
if created:
    CardInDeck.objects.bulk_create([CardInDeck(deck=deck,card=c,hand=int(i<5),side=int(i>=14)) for i,c in enumerate(cards[:20])])
    ReserveCardInDeck.objects.create(deck=deck,card=traits[1])
    ReserveCardInDeck.objects.create(deck=deck,card=cards[20])
simulator = create_simulator_session('플레이어1','플레이어2',deck,deck)
calculator = create_standalone_session('플레이어1','플레이어2',character,character,trait_ids=[traits[0].pk,traits[1].pk])
manifest={'builder':reverse('deck:update',args=[deck.pk]),'mobile_builder':reverse('deck:updateMobileV2',args=[deck.pk]),'detail':reverse('deck:detail',args=[deck.pk]),'regulations':reverse('deck:manageRegulations'),
          'simulator':reverse('battlelog:simulatorSeat',args=[simulator.view_token,'p1',simulator.player1_token]),'opponent':reverse('battlelog:simulatorSeat',args=[simulator.view_token,'p2',simulator.player2_token]),
          'calculator':reverse('battlelog:sessionControl',args=[calculator.view_token,calculator.control_token])+'?ui=character'}
(directory/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
def local_login(request):
    login(request,user,backend='django.contrib.auth.backends.ModelBackend')
    target=request.GET.get('page','/deck/')
    return HttpResponseRedirect(target if target.startswith('/') and not target.startswith('//') else '/deck/')
from LumenGG.urls import urlpatterns
urlpatterns.insert(0,path('review-login/',local_login))
print('Review server: http://127.0.0.1:8873/review-login/',flush=True)
call_command('runserver','127.0.0.1:8873',use_reloader=False,insecure=True)
