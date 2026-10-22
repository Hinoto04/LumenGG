"""Smoke test for the task-owned Android review emulator, in Korean local mode."""
import json,time,sys
sys.path.insert(0,'scripts')
from check_android_calculator import adb,nodes,tap,capture,OUT

def select_character(player,name):
    label='플레이어'+str(player)+': '+name
    for _ in range(6):
        items=nodes()
        found=[(n,b) for n,b in items if n.get('content-desc')==label and b[2]-b[0]>80]
        if found:
            n,(x,y,x2,y2)=found[0]
            adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2))
            return
        strips=sorted([b for n,b in items if n.get('scrollable')=='true' and b[2]-b[0]>4*(b[3]-b[1])])
        x,y,x2,y2=strips[player-1]
        adb('shell','input','swipe',str(x2-80),str((y+y2)//2),str(x+80),str((y+y2)//2),'900')
    raise ValueError(label)

def start(a,b):
    if not any(n.get('text')=='새 계산기 시작' for n,box in nodes()):
        tap('계산기 설정')
    # Display preferences may occupy the first part of the setup sheet.
    for _ in range(5):
        items=nodes()
        strips=[box for n,box in items if n.get('scrollable')=='true' and box[2]-box[0]>4*(box[3]-box[1])]
        if len(strips)>=2:break
        scroll_setup(items)
    select_character(1,a);select_character(2,b)
    for _ in range(5):
        items=nodes()
        if any(n.get('text')=='새 계산기 시작' for n,box in items):break
        scroll_setup(items)
    tap('새 계산기 시작')
    time.sleep(2)

def scroll_setup(items,up=False):
    scrolls=[box for n,box in items if n.get('scrollable')=='true' and box[2]-box[0]<4*(box[3]-box[1])]
    if not scrolls:
        time.sleep(.5)
        return
    x,y,x2,y2=max(scrolls,key=lambda box:(box[2]-box[0])*(box[3]-box[1]))
    start,end=(y+30,y2-30) if up else (y2-30,y+30)
    adb('shell','input','swipe',str((x+x2)//2),str(start),str((x+x2)//2),str(end),'500')
    time.sleep(.3)

def click_counter(prefix,delta):
    items=nodes()
    matches=[(n,b) for n,b in items if n.get('content-desc','').startswith(prefix+' ') and n.get('content-desc','').endswith(' '+delta) and n.get('enabled')=='true']
    assert matches,prefix+' '+delta
    n,(x,y,x2,y2)=matches[-1]
    adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2))
    time.sleep(.2)

if __name__ == "__main__":
    checks=[]
    start('비올라','타오')
    items=nodes()
    assert not any(n.get('scrollable')=='true' for n,b in items)
    assert not any(n.get('text') in ['비올라','타오','플레이어1','플레이어2'] for n,b in items)
    capture('android-visual-viola-tao.png')
    for _ in range(3):click_counter('은연 카운터','+1')
    click_counter('은연 카운터','−1')
    assert any('은연 카운터 2/3' in n.get('content-desc','') for n,b in nodes())
    checks.append('Viola contiguous increase/decrease and original token marks')
    for name in ['양','음']:
        for _ in range(4):click_counter(name,'+1')
    items=nodes()
    assert all(n.get('enabled')=='false' for n,b in items if n.get('content-desc','').startswith(('양 ','음 ')))
    tap('+100DMG');time.sleep(1)
    capture('android-visual-tao-harmony.png')
    assert any(n.get('text')=='+100DMG' for n,b in nodes())
    assert not any(n.get('scrollable')=='true' for n,b in nodes())
    click_counter('양','−1');click_counter('양','−1')
    assert not any(n.get('text')=='+100DMG' for n,b in nodes())
    checks.append('Tao choice lock, selected effect, counters resume and harmony clears')
    start('리타','레브')
    tap('빛의 루멘');tap('가디언');time.sleep(1)
    assert not any(n.get('scrollable')=='true' for n,b in nodes())
    capture('android-visual-rita.png')
    tap('가디언')
    checks.append('Rita Lumen and original-card role select/off; six-dagger panel fits without scrolling')
    adb('shell','am','force-stop','kr.hinoto.lumen')
    adb('shell','am','start','-a','android.intent.action.VIEW','-d','lumendb://calculator','-n','kr.hinoto.lumen/.MainActivity')
    for _ in range(20):
        if any(n.get('text')=='리타' for n,b in nodes()):break
        time.sleep(.5)
    else:raise AssertionError('Classic cold restoration did not complete')
    capture('android-visual-classic.png')
    checks.append('Classic default restores the same local session')
    (OUT/'android-visual-report.json').write_text(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'checks':checks,'errors':[]},ensure_ascii=False))
