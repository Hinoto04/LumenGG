import re,sys,subprocess,xml.etree.ElementTree as ET,time,json
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')
ADB=r'C:\Users\admln\AppData\Local\Android\Sdk\platform-tools\adb.exe'
OUT=Path('artifacts/calculator-character'); XML=Path('.temp/calculator-ui.xml')
def adb(*args):return subprocess.check_output([ADB,'-s','emulator-5554',*args],stderr=subprocess.STDOUT,timeout=30).decode('utf-8',errors='replace')
def nodes():
 for attempt in range(3):
  output=adb('shell','uiautomator','dump','/sdcard/calculator-ui.xml')
  if 'ERROR:' not in output:break
  time.sleep(.5)
 if 'ERROR:' in output:raise RuntimeError('UIAutomator did not refresh its snapshot: '+output.strip())
 adb('pull','/sdcard/calculator-ui.xml',str(XML))
 result=[]
 for n in ET.parse(XML).iter('node'):
  coords=list(map(int,re.findall(r'\d+',n.get('bounds',''))))
  if len(coords)==4 and coords[2]>coords[0] and coords[3]>coords[1]:result.append((n,coords))
 return result
def tap(label):
 items=nodes()
 matches=[(n,b) for n,b in items if n.get('content-desc')==label] or [(n,b) for n,b in items if n.get('text')==label]
 if not matches and (label in ['+100DMG','+1FP'] or label.startswith(('양 ','음 '))):
  scrolls=[b for n,b in items if n.get('scrollable')=='true']
  x,y,x2,y2=max(scrolls,key=lambda b:b[0]);cx=(x+x2)//2
  start,end=(y2-30,y+30) if label in ['+100DMG','+1FP'] else (y+30,y2-30)
  adb('shell','input','swipe',str(cx),str(start),str(cx),str(end),'800')
  items=nodes()
  matches=[(n,b) for n,b in items if n.get('content-desc')==label] or [(n,b) for n,b in items if n.get('text')==label]
 if not matches:raise ValueError('Missing target: '+label)
 n,(x,y,x2,y2)=matches[0];adb('shell','input','tap',str((x+x2)//2),str((y+y2)//2));time.sleep(.15)
def capture(name):
 adb('shell','screencap','-p','/sdcard/calculator-review.png');adb('pull','/sdcard/calculator-review.png',str(OUT/name))
if __name__ == '__main__':
 for label in ['양','음']:
  items=nodes()
  reset=next(n.get('content-desc') for n,b in items if n.get('content-desc','').startswith(label+' ') and '초기화' in n.get('content-desc',''))
  tap(reset)
 capture('android-root-tao.png')
 tap('플레이어1 HP -100');capture('android-hp-pending.png');time.sleep(1)
 assert any('플레이어1 HP 4900,' in n.get('content-desc','') for n,b in nodes())
 tap('되돌리기');assert any('플레이어1 HP 5000,' in n.get('content-desc','') for n,b in nodes())
 tap('차지')
 for label in ['양 +1']*4+['음 +1']*4:tap(label)
 tap('+100DMG');capture('android-tao-harmony.png')
 nodes(); assert any(n.get('text')=='조화' for n in ET.parse(XML).iter('node'))
 tap('양 -1');nodes(); assert any(n.get('text')=='조화' for n in ET.parse(XML).iter('node'))
 tap('양 -1');nodes(); assert not any(n.get('text')=='조화' for n in ET.parse(XML).iter('node'))
 (OUT/'android-interaction-report.json').write_text(json.dumps({'checks':['HP queue','undo','Root charge','Tao harmony activation, retention, clear'],'errors':[]},indent=2))
 print('Android: queued HP, undo, Root charge, Tao activation/retention/clear passed.')
