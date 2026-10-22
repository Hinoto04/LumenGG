"""Build the clean raster icon source gallery and refresh the review page."""
import html,json,re,sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'artifacts/calculator-character'
read=lambda p:json.loads(p.read_text(encoding='utf-8'))
manifest=read(root/'LumenGG/content/calculator-clean-icons.json')
labels=dict(zip(manifest,['중립 문장','차지','하울링','불씨','부서진 카드','청염','개러지','스파이더','디제스터 원','예지 토큰','단검','오버 리밋','다운 스탠스','예고','위압','암야','콕핏','잼 데이','하이텐션','빛의 루멘','은연','가디언','어쌔신','팔라딘']))
parts=['''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>깔끔한 UI · 새 아이콘 24종</title><style>
body{margin:24px;background:#0b111e;color:#eef2fb;font:16px system-ui}main{max-width:1250px;margin:auto}a{color:#b5d0ff}p{line-height:1.7;color:#bac8df}h1{font-size:27px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:14px}article{border:1px solid #35445e;background:#101725;padding:16px;border-radius:12px}h2{font-size:17px;margin:0 0 14px}.icons{display:flex;align-items:center;gap:12px}.slot{display:flex;align-items:center;justify-content:center;background:#172234;width:80px;height:80px;border:1px solid #687c9566;border-radius:8px}.on{border-color:#b5d0ff}.slot img{width:72px;height:72px;object-fit:contain}.idle img{opacity:.65}.old img{width:44px;height:44px}.small{margin-top:12px;display:flex;align-items:center;gap:10px;font-size:12px;color:#bac8df}.small img{width:44px;height:44px;object-fit:contain}.meta{font-size:12px}code{font-size:11px}article a{word-break:break-all}</style><main><h1>깔끔한 UI · 새 아이콘 24종</h1><p>전용 생성 이미지 14종 · 원작 카드 크롭 9종 · 예고장 복원 이미지 재사용 1종.<br>왼쪽은 이전 선 아이콘, 가운데는 새 비활성 상태, 오른쪽은 새 활성 상태입니다. 아래 44px 이미지는 작은 버튼에서의 크기입니다.</p><p><a href="review.html?revision=clean-icons-20261020">웹·Android 19명 화면 비교</a> · <a href="clean-sources/imagegen-prompts-v2.json">생성 프롬프트·원본 경로</a> · <a href="clean-v2-assets-report.json">원작 카드 출처·크롭·파일 검증</a></p><div class="grid">''']
base='../../LumenGG/static/v2/calculator-character/clean/'
for key,info in manifest.items():
    src=base+info['file'];source='../../'+info['source']
    method={'generated':'전용 생성 · 투명 원본','card':'원작 카드 크롭','restored-card':'기존 예고장 복원 재사용'}[info['kind']]
    parts.append(f'<article><h2>{labels[key]}</h2><div class="icons"><div class="slot old"><img src="{base+key}.png" alt="이전"></div><div class="slot idle"><img src="{src}" alt="비활성"></div><div class="slot on"><img src="{src}" alt="활성"></div></div><div class="small"><img src="{src}" alt="44px">44px 실제 크기</div><p class="meta">{method}<br><a href="{source}">원본</a> · <a href="{src}">적용 PNG</a>')
    if info.get('crop'):parts.append('<br>크롭 x, y, w, h: '+str(info['crop']))
    if info.get('card_code'):parts.append('<br>카드: '+html.escape(info['card_code']))
    parts.append('</p></article>')
parts.append('</div></main></html>')
(out/'clean-icon-review.html').write_text(''.join(parts),encoding='utf-8')
if '--icons-only' in sys.argv:sys.exit(0)
page=(out/'review.html').read_text(encoding='utf-8')
page=page.replace('<title>배경 정렬·밝기·깔끔한 계산기</title>','<title>깔끔한 계산기 · 전용 아이콘과 카드 크롭</title>')
page=page.replace('<h1>배경 정렬 · 밝기 · 깔끔한 계산기</h1>','<h1>깔끔한 계산기 · 전용 아이콘과 카드 크롭</h1>')
page=re.sub(r'<p class="note">.*?</p>','<p class="note">깔끔한 UI의 아이콘 24종을 전용 생성 이미지와 원작 카드 크롭으로 교체했습니다. 루트·델피·울프·비올라는 토큰의 고유 문양을 반영했고, 레기온은 실제 카드 그림을 사용합니다. 예고장은 카드 전체를, 잼 데이는 네 명의 얼굴을 유지합니다. 단색 배경과 정적인 상태 강조를 유지합니다.</p>',page,count=1)
page=page.replace('href="appearance-validation.json"','href="clean-v2-validation.json"')
page=page.replace(' · <a href="raster-assets.html">',' · <a href="clean-icon-review.html">새 아이콘 24종 · 이전/수정 비교</a> · <a href="raster-assets.html">')
page=page.replace('id="illustrated" aria-pressed="true"','id="illustrated" aria-pressed="false"').replace('id="clean" aria-pressed="false"','id="clean" aria-pressed="true"')
page=page.replace('id="illustrated-section">','id="illustrated-section" hidden>').replace('id="clean-section" hidden>','id="clean-section">')
page=page.replace('같은 배치 · 단색 패널과 선 아이콘','같은 배치 · 단색 패널과 캐릭터 전용 이미지')
page=page.replace('appearance-clean-web-','clean-v2-clean-web-').replace('appearance-clean-android-','clean-v2-clean-android-')
page=re.sub(r'<h2>검증 완료</h2><p>.*?</p>','<h2>검증 완료 · 2026-10-20</h2><p>모바일 타입 검사·테스트 64개, 웹 19명·5개 크기, Android 19명, Android·iOS 번들 포함 검사를 통과했습니다. 새 아이콘 24종은 웹·앱 바이트가 같으며, 번들에 이전 선 아이콘은 포함되지 않습니다. iOS 기기 화면은 미검증입니다.</p>',page,count=1)
page=re.sub(r'<p>깔끔한 아이콘:.*?</p>','<p><a href="clean-icon-review.html">새 아이콘 비교·원본</a> · <a href="clean-sources/imagegen-prompts-v2.json">built-in image_gen 프롬프트 14종</a> · <a href="clean-v2-assets-report.json">카드 크롭·출처·바이트 검증</a>. 이전 선 아이콘과 라이선스는 비교 기록으로 보관합니다.</p>',page,count=1)
(out/'review.html').write_text(page,encoding='utf-8')
web=read(out/'clean-v2-web-report.json');android=read(out/'clean-v2-android-report.json')
bundles=read(out/'clean-v2-bundle-report.json');assets=read(out/'clean-v2-assets-report.json')
validation={'date':'2026-10-20','scope':'clean UI raster icon replacement only','typecheck':'passed','mobile_tests':{'passed':64,'failed':0},'web':web,'android':android,'bundles':bundles,'assets':{'count':24,'generated':14,'card_crops':9,'restored_card_reused':1,'web_app_identical':all(a['web_app_identical'] for a in assets['assets'])},'ios_device':'not checked; platform export checked','backend':'No backend/action/state changes in this icon replacement; previous regression results remain in appearance-validation.json'}
(out/'clean-v2-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('Clean raster gallery and web / Android review refreshed.')
