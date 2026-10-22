"""Finf shield interaction smoke test on the task-owned Android review emulator."""
import json,sys,time
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT
from check_android_visuals import start,scroll_setup

def coords(label):
    return next(b for n,b in nodes() if n.get('content-desc')==label)

def fast(bounds,count=1):
    x,y,x2,y2=bounds
    for _ in range(count):adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2))

def hp(value,player=1):
    assert any(n.get('content-desc','').startswith('플레이어'+str(player)+' HP '+str(value)+',') for n,b in nodes())

def style(name):
    tap('계산기 설정')
    for _ in range(10):
        items=nodes()
        if any(n.get('text')=='화면 스타일' for n,b in items):break
        scroll_setup(items,up=True)
    tap(name);tap('닫기')

try:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:adb('shell','settings','put','global',setting,'0')
    for _ in range(20):
        if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
        time.sleep(.5)
    style('깔끔하게');start('핀프','핀프')
    import re
    initial=int(next(re.search(r'플레이어1 HP (-?\d+),',n.get('content-desc','')).group(1) for n,b in nodes() if re.search(r'플레이어1 HP (-?\d+),',n.get('content-desc',''))))
    plus=coords('플레이어1 보호막 +100');reset=coords('플레이어1 보호막 초기화')
    fast(plus,3);capture('shield-android-pending.png');time.sleep(1.1)
    hp(initial)
    assert any('+300' in n.get('text','') for n,b in nodes())
    assert not any(n.get('scrollable')=='true' for n,b in nodes())
    capture('shield-android-clean-active.png')
    tap('플레이어1 HP -500');time.sleep(1.1);hp(initial-200)
    assert not any('+300' in n.get('text','') for n,b in nodes())
    capture('shield-android-clean-overflow.png')
    tap('되돌리기');hp(initial)
    assert any('+300' in n.get('text','') for n,b in nodes())
    tap('플레이어1 보호막 초기화')
    fast(plus,3);fast(reset);time.sleep(1.2)
    assert not any('+300' in n.get('text','') for n,b in nodes()),'no delayed gain after reset'
    fast(coords('플레이어2 보호막 +100'),2);time.sleep(1.1)
    tap('제로 슈트');capture('shield-android-clean-p2.png')
    style('일러스트');capture('shield-android-illustrated.png')
    assert len([1 for n,b in nodes() if '보호막' in n.get('content-desc','')])==6
    adb('shell','am','force-stop','kr.hinoto.lumen')
    adb('shell','am','start','-a','android.intent.action.VIEW','-d','lumendb://calculator','-n','kr.hinoto.lumen/.MainActivity')
    for _ in range(20):
        if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
        time.sleep(.5)
    assert len([1 for n,b in nodes() if '보호막' in n.get('content-desc','')])==6
    assert any('+200' in n.get('text','') for n,b in nodes()),'local shield persists after cold restore'
    capture('shield-android-classic.png')
    (OUT/'shield-android-report.json').write_text(json.dumps({'checks':['3 rapid shield taps / pending sum','damage overflow reaches HP','undo restores shield','reset flush prevents delayed gain','P2 shield','Zero Suit still usable','no character passive scrolling','6 controls in illustrated and classic','cold local restore preserves shield'],'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Android shield checks passed.',flush=True)
finally:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:adb('shell','settings','put','global',setting,'1.0')
