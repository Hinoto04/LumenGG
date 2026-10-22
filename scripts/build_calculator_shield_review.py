"""Save the Finf shield comparison and concrete validation evidence."""
import hashlib,json,re,zipfile
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'artifacts/calculator-character'
load=lambda p:json.loads(p.read_text(encoding='utf-8'))
web=load(out/'shield-web-report.json');android=load(out/'shield-android-report.json')
assert not web['errors'] and not android['errors']
assert 'pass 70' in (root/'.temp/shield-tests.log').read_text(encoding='utf-8')
assert 'Ran 47 tests' in (root/'.temp/shield-django.log').read_text(encoding='utf-8')
assert '\nOK\n' in (root/'.temp/shield-django.log').read_text(encoding='utf-8')
export=root/'.temp/calculator-shield-final-export'
metadata=load(export/'metadata.json')
assets=load(root/'LumenGG/content/calculator-clean-icons.json')
sha=lambda data:hashlib.sha256(data).hexdigest()
expected={key:sha((root/'mobile/assets/calculator-character/clean'/a['file']).read_bytes()) for key,a in assets.items()}
bundles={}
for platform,item in metadata['fileMetadata'].items():
    bundle=(export/item['bundle']).read_bytes()
    assert b'finf_shield' in bundle and b'shield_reset' in bundle
    asset_hashes={sha((export/a['path']).read_bytes()) for a in item['assets'] if a['ext']=='png'}
    assert all(value in asset_hashes for value in expected.values())
    bundles[platform]={'bundle_sha256':sha(bundle),'shield_actions_present':True,'shared_clean_icons':24}
apk=root/'mobile/android/app/build/outputs/apk/release/app-release.apk'
with zipfile.ZipFile(apk) as z:
    bundle=z.read('assets/index.android.bundle')
    assert b'finf_shield' in bundle and b'shield_reset' in bundle
validation={'date':'2026-10-20','expiry':'manual shield reset, as requested','typecheck':'passed','mobile_tests':{'passed':70,'failed':0},'django_api_tests':{'passed':47,'failed':0},'web':web,'android':android,'bundles':bundles,'android_apk':{'build':'passed','sha256':sha(apk.read_bytes()),'shield_actions_present':True},'ios_device':'not checked; export checked'}
(out/'shield-validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
html=['''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>핀프 · 보호막</title><style>body{margin:24px;background:#0b111e;color:#eef2fb;font:16px system-ui}main{max-width:1500px;margin:auto}h1{font-size:28px}h2{font-size:20px;margin-top:32px}p{color:#bac8df;line-height:1.7}a{color:#b5d0ff}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:#141e30;border:1px solid #35445e;border-radius:10px;padding:10px}figcaption{padding:8px;font-size:14px}img{width:100%;display:block}.note{padding:16px;border-left:3px solid #a9e4ff;background:#172237}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style><main><h1>핀프 · 보호막 시스템</h1><p class="note">보호막은 HP 오른쪽에 +NNN으로 표시합니다. 보호막+ / 초기화 / 보호막− 버튼으로 100씩 조정하며 연속 입력은 합산됩니다. 피해는 보호막부터 차감하고 초과분을 HP에 적용합니다. 턴이 끝나면 보호막의 초기화 버튼으로 직접 해제합니다.</p><p>핀프의 기본 HP 5500, 보호막 300에서 피해 500 → HP 5300, 보호막 0. 되돌리면 HP와 소모된 보호막을 함께 복원합니다. 아래 웹·Android는 독립된 검증 대전이므로 일부 수치와 활성 상태가 다릅니다.</p><p><a href="shield-validation.json">검증 결과</a> · <a href="../../docs/CALCULATOR_SHIELD.md">동작·저장·입력 큐 문서</a> · <a href="review.html">기존 UI 검토</a></p>''']
for title,web_file,app_file in [
    ('깔끔한 UI · 보호막 300','shield-web-clean-active.png','shield-android-clean-active.png'),
    ('피해 500 · 보호막 소진 후 HP 200 감소','shield-web-clean-overflow.png','shield-android-clean-overflow.png'),
    ('일러스트 UI','shield-web-illustrated.png','shield-android-illustrated.png'),
    ('기존 UI','shield-web-classic.png','shield-android-classic.png')]:
    html.append('<h2>'+title+'</h2><div class="pair">')
    for platform,file in [('웹',web_file),('Android',app_file)]:
        assert (out/file).exists()
        html.append(f'<figure><figcaption>{platform}</figcaption><a href="{file}"><img src="{file}" alt="{title} · {platform}"></a></figure>')
    html.append('</div>')
html.append('<h2>Android · 입력 대기 합계</h2><figure><img src="shield-android-pending.png" alt="보호막 연속 입력 대기 합계"></figure><p>타입 검사·모바일 테스트 70개, Django/API 테스트 47개, 웹 세 화면·5개 크기·3개 언어, Android 입력·저장 복원과 양 플랫폼 번들을 확인했습니다. iOS 기기 화면은 미검증입니다.</p></main></html>')
(out/'shield-review.html').write_text(''.join(html),encoding='utf-8')
review=out/'review.html';page=review.read_text(encoding='utf-8')
if 'href="shield-review.html"' not in page:
    page=page.replace('</h1>','</h1><p class="note"><a href="shield-review.html">핀프 보호막 · 신규 기능과 웹/Android 비교 보기</a> — 보호막 100 단위 입력, HP 오른쪽 수치, 초과 피해와 되돌리기를 지원합니다.</p>',1)
    review.write_text(page,encoding='utf-8')
print('Finf shield review and validation evidence saved.')
