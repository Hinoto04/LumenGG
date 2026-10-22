"""Device-only appearance preferences and shared clean HUD on the review emulator."""
import json,re,sys,time
from pathlib import Path
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT
from check_android_visuals import start,scroll_setup

def click(bounds,times=1):
    x,y,x2,y2=bounds
    for _ in range(times):
        adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2));time.sleep(.15)

def open_display():
    print('Opening display settings',flush=True)
    tap('계산기 설정')
    time.sleep(.6)
    for _ in range(10):
        items=nodes()
        if any(n.get('text')=='화면 스타일' for n,b in items):return
        scroll_setup(items,up=True)
    raise AssertionError('Display settings unavailable')

def resource_state():
    return sorted((n.get('content-desc'),n.get('checked'),n.get('selected')) for n,b in nodes()
        if n.get('content-desc') and n.get('content-desc')!='계산기 설정')

for _ in range(20):
    if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
    time.sleep(.5)
open_display();tap('일러스트');tap('권장 밝기');tap('닫기')
start('키스','울프')
tap('플레이어1 HP -100');time.sleep(1.2);tap('예고')
before=resource_state()
capture('appearance-illustrated-android-35.png')
open_display()
for name,count in [('배경 밝기 +10',7),('배경 밝기 −10',10)]:
    bound=next(b for n,b in nodes() if n.get('content-desc')==name)
    click(bound,count)
    expected=100 if '+' in name else 0
    assert any(n.get('text')=='배경 밝기 · '+str(expected)+'%' for n,b in nodes()),'brightness '+str(expected)
    tap('닫기');assert resource_state()==before,'brightness changed game state'
    capture('appearance-illustrated-android-'+str(expected)+'.png');open_display()
    print('Brightness passed '+str(expected),flush=True)
tap('권장 밝기');tap('깔끔하게');tap('닫기')
assert resource_state()==before,'clean style changed game state'
capture('appearance-clean-android-keith-wolf.png')
# Restore the preference and session after a cold launch.
adb('shell','am','force-stop','kr.hinoto.lumen')
adb('shell','am','start','-a','android.intent.action.VIEW','-d','lumendb://calculator?ui=character','-n','kr.hinoto.lumen/.MainActivity')
for _ in range(20):
    if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
    time.sleep(.5)
assert resource_state()==before,'cold restore changed game state'
open_display()
assert not any(n.get('text','').startswith('배경 밝기') for n,b in nodes()),'clean preference restore hides illustrated brightness controls'
tap('닫기')
themes=json.loads(Path('LumenGG/content/calculator-ui.json').read_text(encoding='utf-8'))
checks=[]
for i in range(0,len(themes),2):
    pair=themes[i:i+2]
    if len(pair)==1:pair+=pair
    start(pair[0]['name'],pair[1]['name'])
    items=nodes()
    assert not any(n.get('scrollable')=='true' for n,b in items),'passive scrolling'
    for player in [1,2]:
        prefix='플레이어'+str(player)
        hp=next(b for n,b in items if n.get('content-desc','').startswith(prefix+' HP ') and '대미지' in n.get('content-desc',''))
        fp=next(b for n,b in items if n.get('content-desc')==prefix+' FP +1')
        assert (hp[0]+hp[2]<fp[0]+fp[2])==(player==1)
    name='appearance-clean-android-'+'-'.join(t['theme_key'] for t in pair)+'.png';capture(name)
    checks.append({'themes':[t['theme_key'] for t in pair],'no_scroll':True,'symmetric':True,'screenshot':name})
    print('Clean passed '+' / '.join(t['name'] for t in pair),flush=True)
(OUT/'appearance-android-report.json').write_text(json.dumps({'checks':checks,'brightness':[0,35,100],'state_preserved':True,'cold_restore':True,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
