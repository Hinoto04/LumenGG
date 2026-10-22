"""Timer geometry and debounced passive interactions on the task review AVD."""
import json,sys,time
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT
from check_android_visuals import start,scroll_setup

def fast(bounds,times=1):
    x,y,x2,y2=bounds
    for _ in range(times):
        adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2));time.sleep(.08)

def counter(label,filled=False):
    matches=[b for n,b in nodes() if n.get('content-desc','').startswith(label+' ') and n.get('content-desc','').endswith(' −1' if filled else ' +1') and n.get('enabled')=='true']
    assert matches,label
    # Keep tapping a slot whose action stays the same throughout the burst:
    # the top (last-to-fill) vertical slot, or the rightmost horizontal slot.
    if label in ['양','음']:
        return (max if filled else min)(matches,key=lambda b:b[1])
    if label=='하울링 카운터':
        return max(matches,key=lambda b:b[1])
    return max(matches,key=lambda b:b[0])

def check_no_scroll():assert not any(n.get('scrollable')=='true' for n,b in nodes())

try:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:adb('shell','settings','put','global',setting,'0')
    for _ in range(20):
        if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
        time.sleep(.5)
    tap('계산기 설정')
    for _ in range(10):
        items=nodes()
        if any(n.get('text')=='화면 스타일' for n,b in items):break
        scroll_setup(items,up=True)
    tap('깔끔하게');tap('닫기')
    start('비올라','타오')
    bounds=next(b for n,b in nodes() if n.get('content-desc')=='타이머')
    before=json.loads((OUT/'passive-input-timer-before.json').read_text())
    assert bounds[3]-bounds[1]>before['height']*1.4,(before,bounds)
    capture('passive-input-android-timer-after.png')
    print('Timer enlargement passed.',flush=True)
    fast(counter('은연 카운터'),3);capture('passive-input-android-preview.png');time.sleep(1.1)
    assert any('은연 카운터 3/3' in n.get('content-desc','') for n,b in nodes())
    tap('기록')
    rows=[n.get('content-desc','') for n,b in nodes() if '은연' in n.get('content-desc','') and '→' in n.get('content-desc','')]
    assert len(rows)==1 and '0 → 3' in rows[0],rows
    capture('passive-input-android-one-record.png');tap('닫기')
    print('Viola immediate preview and one final history record passed.',flush=True)
    fast(counter('양'),4);fast(counter('음'),4)
    assert all(n.get('enabled')=='false' for n,b in nodes() if n.get('content-desc','').startswith(('양 ','음 ')))
    tap('+100DMG');time.sleep(.2);capture('passive-input-android-tao-harmony.png')
    fast(counter('음',True),2);time.sleep(1.1)
    assert not any(n.get('text')=='+100DMG' for n,b in nodes())
    check_no_scroll()
    print('Tao harmony activation, choice lock and clear passed.',flush=True)
    start('울프','리타')
    fast(counter('하울링 카운터'),5);tap('위압');time.sleep(1.1)
    assert any('하울링 카운터 0/5' in n.get('content-desc','') for n,b in nodes())
    roles={n.get('content-desc'):b for n,b in nodes() if n.get('content-desc') in ['가디언','어쌔신','팔라딘']}
    for name in ['가디언','어쌔신','팔라딘']:fast(roles[name])
    time.sleep(1.1)
    assert any(n.get('content-desc')=='팔라딘' and n.get('selected')=='true' for n,b in nodes())
    capture('passive-input-android-wolf-rita.png');tap('기록')
    role_rows=[n.get('content-desc','') for n,b in nodes() if '레기온' in n.get('content-desc','') and '→' in n.get('content-desc','')]
    assert len(role_rows)==1,role_rows
    print('Wolf token consumption and Rita final-choice history passed.',flush=True)
    tap('닫기');tap('서든 데스');tap('확인');check_no_scroll()
    assert any('남은 턴' in n.get('text','') for n,b in nodes())
    capture('passive-input-android-sudden.png')
    adb('shell','am','force-stop','kr.hinoto.lumen')
    adb('shell','am','start','-a','android.intent.action.VIEW','-d','lumendb://calculator','-n','kr.hinoto.lumen/.MainActivity')
    for _ in range(20):
        if any(n.get('content-desc')=='계산기 설정' for n,b in nodes()):break
        time.sleep(.5)
    restored=nodes()
    assert {'울프','리타'} <= {n.get('text') for n,b in restored}
    assert sum(n.get('content-desc','').startswith(('플레이어1 HP 1000,','플레이어2 HP 1000,')) for n,b in restored)==2
    capture('passive-input-android-classic.png')
    (OUT/'passive-input-android-report.json').write_text(json.dumps({'before_timer':before,'after_timer':{'bounds':bounds,'height':bounds[3]-bounds[1]},'checks':['larger timer box and digits','3 taps produce one 0 to 3 history record','immediate token preview','Tao choice lock and clear','Wolf activation consumes tokens','Rita choices produce one final history record','sudden death tools fit','classic cold restore'],'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Android: larger timer, coalesced records, conditional passives and classic restore passed.',flush=True)
finally:
    for setting in ['transition_animation_scale','window_animation_scale','animator_duration_scale']:adb('shell','settings','put','global',setting,'1.0')
