"""UI smoke on the task-owned emulator; uses the bundled offline catalog only."""
import json,re,sys,time
from pathlib import Path
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT
from check_android_visuals import start

spec=json.loads(Path('LumenGG/content/calculator-passives.json').read_text(encoding='utf-8'))
themes=json.loads(Path('LumenGG/content/calculator-ui.json').read_text(encoding='utf-8'))
checks=[]
oct19='--oct19' in sys.argv
# A cold embedded-JS launch may still be showing the Android splash screen.
for _ in range(20):
    current=nodes()
    if any(n.get('content-desc')=='계산기 설정' or n.get('text')=='새 계산기 시작' for n,b in current):break
    time.sleep(.5)
else:raise AssertionError('Calculator did not finish startup')
def click_at(bounds):
    x,y,x2,y2=bounds
    adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2))
    time.sleep(.15)
for i in range(0,len(themes),2):
    pair=themes[i:i+2]
    if len(pair)==1:pair=pair+pair
    if oct19 and not any(t['theme_key'] in ['keith','rev','yohan','iomong','cmyk'] for t in pair):continue
    start(pair[0]['name'],pair[1]['name'])
    for player,t in enumerate(pair,1):
        if t['theme_key'] in ['tao','rita']:continue
        for c in spec[t['theme_key']]['controls']:
            label=c['label']
            if c['type']=='counter':
                items=nodes()
                screen_width=max(b[2] for n,b in items)
                matches=[(n,b) for n,b in items if n.get('content-desc','').startswith(label+' ') and n.get('content-desc','').endswith(' +1') and ((b[0]+b[2])<screen_width)==(player==1)]
                if not matches:raise ValueError('Missing counter '+label)
                if c.get('max'):
                    old=int(re.search(r' (\d+)/',matches[0][0].get('content-desc')).group(1))
                    # Last logical slot is bottom/right in each bespoke layout.
                    bound=max((b for n,b in matches),key=lambda b:(b[1],b[0]))
                    for _ in range(c['max']-old):click_at(bound)
                    assert any((label+' '+str(c['max'])+'/'+str(c['max'])) in n.get('content-desc','') for n,b in nodes()),label
                else:
                    for _ in range(2):click_at(matches[0][1])
            elif c['type'] in ['toggle','thresholdAction']:
                tap(label)
                assert any(n.get('content-desc')==label and n.get('checked')=='true' for n,b in nodes()),label+' activation'
            elif c['type']=='status':
                tap_label='플레이어'+str(player)+' HP -500'
                bound=next(b for n,b in nodes() if n.get('content-desc')==tap_label)
                for _ in range(5):click_at(bound)
                time.sleep(1.1)
    items=nodes()
    assert not any(n.get('scrollable')=='true' for n,b in items),'passive scrolling'
    if any(t['theme_key']=='iomong' for t in pair):
        assert not any('영물' in n.get('content-desc','') or n.get('content-desc','').startswith('364 ') for n,b in items),'obsolete Iomong controls'
    for player in [1,2]:
        prefix='플레이어'+str(player)
        hp=next(b for n,b in items if n.get('content-desc','').startswith(prefix+' HP ') and '대미지' in n.get('content-desc',''))
        fp=next(b for n,b in items if n.get('content-desc')==prefix+' FP +1')
        assert (hp[0]+hp[2]<fp[0]+fp[2])==(player==1),'mirrored resources'
    name='android-bespoke-'+'-'.join(t['theme_key'] for t in pair)+'.png'
    capture(name)
    checks.append({'themes':[t['theme_key'] for t in pair],'no_scroll':True,'symmetric_resources':True,'screenshot':name})
    print('Passed '+' / '.join(t['name'] for t in pair),flush=True)
(OUT/('android-oct19-report.json' if oct19 else 'android-bespoke-report.json')).write_text(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
