"""Capture the replacement clean raster icons on the task-owned review emulator."""
import json,sys,time
from pathlib import Path
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT
from check_android_visuals import start,scroll_setup,click_counter

checks=[]
try:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:
        adb('shell','settings','put','global',setting,'0')
    for _ in range(20):
        if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
        time.sleep(.5)
    tap('계산기 설정')
    for _ in range(10):
        items=nodes()
        if any(n.get('text')=='화면 스타일' for n,b in items):break
        scroll_setup(items,up=True)
    tap('깔끔하게');tap('닫기')
    themes=json.loads(Path('LumenGG/content/calculator-ui.json').read_text(encoding='utf-8'))
    for i in range(0,len(themes),2):
        pair=themes[i:i+2]
        if len(pair)==1:pair+=pair
        start(pair[0]['name'],pair[1]['name'])
        active=[]
        if pair[0]['theme_key']=='root':tap('차지');active.append('Root charge')
        if pair[0]['theme_key']=='rita':
            tap('빛의 루멘');tap('가디언');tap('암야');active+=['Lumen','Guardian','Dark Night']
        if pair[0]['theme_key']=='viola':
            click_counter('은연 카운터','+1');active.append('Viola 1/3')
        items=nodes()
        assert not any(n.get('scrollable')=='true' for n,b in items),'passive scrolling'
        for player in [1,2]:
            prefix='플레이어'+str(player)
            hp=next(b for n,b in items if n.get('content-desc','').startswith(prefix+' HP ') and '대미지' in n.get('content-desc',''))
            fp=next(b for n,b in items if n.get('content-desc')==prefix+' FP +1')
            assert (hp[0]+hp[2]<fp[0]+fp[2])==(player==1)
        name='clean-v2-clean-android-'+'-'.join(t['theme_key'] for t in pair)+'.png';capture(name)
        checks.append({'themes':[t['theme_key'] for t in pair],'no_scroll':True,'symmetric':True,'active':active,'screenshot':name})
        print('Clean raster passed '+' / '.join(t['name'] for t in pair),flush=True)
    (OUT/'clean-v2-android-report.json').write_text(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
finally:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:
        adb('shell','settings','put','global',setting,'1.0')
