"""Collect timer/passive-input evidence after the web and Android review checks."""
import hashlib
import html
import json
import zipfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / 'artifacts/calculator-character'
TEMP = ROOT / '.temp'


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


web = load(OUT / 'passive-input-web-report.json')
android = load(OUT / 'passive-input-android-report.json')
assert not web['errors'] and not android['errors']
assert 'pass 80' in (TEMP / 'passive-input-tests.log').read_text(encoding='utf-8')
django = (TEMP / 'passive-input-django.log').read_text(encoding='utf-8')
assert 'Ran 47 tests' in django and '\nOK\n' in django
assert 'BUILD SUCCESSFUL' in (TEMP / 'passive-input-gradle.log').read_text(encoding='utf-8')

export = TEMP / 'calculator-passive-input-export'
metadata = load(export / 'metadata.json')
icons = load(ROOT / 'LumenGG/content/calculator-clean-icons.json')
expected = {sha((ROOT / 'mobile/assets/calculator-character/clean' / item['file']).read_bytes()) for item in icons.values()}
bundles = {}
for platform, item in metadata['fileMetadata'].items():
    bundle = (export / item['bundle']).read_bytes()
    assert b'compactPassiveActions' in bundle and b'projectPassiveInputs' in bundle
    assets = {sha((export / asset['path']).read_bytes()) for asset in item['assets'] if asset['ext'] == 'png'}
    assert expected <= assets
    bundles[platform] = {'bytes': len(bundle), 'sha256': sha(bundle), 'passive_queue_present': True, 'shared_clean_icons': len(expected)}
assert set(bundles) == {'android', 'ios'}
apk = ROOT / 'mobile/android/app/build/outputs/apk/release/app-release.apk'
with zipfile.ZipFile(apk) as archive:
    bundle = archive.read('assets/index.android.bundle')
    assert b'compactPassiveActions' in bundle and b'projectPassiveInputs' in bundle

before = android['before_timer']
after = android['after_timer']
ratio = after['height'] / before['height']
assert ratio > 1.4
assert after['bounds'][2] - after['bounds'][0] == before['width']
for label, source, bounds in [
    ('before', 'passive-input-timer-before.png', before['bounds']),
    ('after', 'passive-input-android-timer-after.png', after['bounds']),
]:
    with Image.open(OUT / source) as image:
        image.crop(bounds).save(OUT / f'passive-input-timer-{label}-crop.png')

validation = {
    'date': '2026-10-22', 'typecheck': 'passed',
    'mobile_tests': {'passed': 80, 'failed': 0},
    'django_api_tests': {'passed': 47, 'failed': 0},
    'web': web, 'android': android, 'timer_height_ratio': ratio,
    'bundles': bundles,
    'android_apk': {'build': 'passed', 'sha256': sha(apk.read_bytes()), 'passive_queue_present': True},
    'ios_device': 'not checked; export checked',
}
(OUT / 'passive-input-validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

page = ['''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>타이머 확대 · 패시브 입력 누적</title><style>body{margin:24px;background:#0b111e;color:#eef2fb;font:16px system-ui}main{max-width:1500px;margin:auto}h1{font-size:28px}h2{font-size:21px;margin-top:32px}p{color:#bac8df;line-height:1.7}a{color:#b5d0ff}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:#141e30;border:1px solid #35445e;border-radius:10px;padding:10px;min-width:0}figcaption{padding:8px;font-size:14px}img{width:100%;display:block}.timer img{max-width:240px;margin:auto}.note{padding:16px;border-left:3px solid #a9e4ff;background:#172237}details{margin:14px 0}summary{cursor:pointer;padding:14px;background:#172235}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style><main><h1>타이머 확대 · 패시브 입력 누적</h1><p class="note">모바일 타이머 상자와 숫자를 확대했습니다. 웹·앱의 패시브는 즉시 미리보기하고, 마지막 입력 후 0.9초에 같은 항목의 최종값을 확정합니다. 비올라 토큰 세 번은 0 → 3 기록 하나로 남습니다.</p><p><a href="passive-input-validation.json">전체 검증 결과</a> · <a href="../../docs/CALCULATOR_PASSIVE_INPUT.md">구현·동작 문서</a> · <a href="review.html">계산기 UI 검토</a></p>''']
page.append(f'<h2>Android 타이머 · 높이 {before["height"]}px → {after["height"]}px ({ratio:.2f}배)</h2><p>같은 에뮬레이터에서 측정했습니다. 상자 폭은 유지하고 남는 세로 공간을 사용합니다. 이전 캡처는 일러스트, 수정 캡처는 깔끔한 스타일이며 중앙 타이머를 잘라 비교했습니다.</p><div class="pair timer">')
for label, title in [('before', '이전'), ('after', '수정')]:
    page.append(f'<figure><figcaption>{title}</figcaption><img src="passive-input-timer-{label}-crop.png" alt="{title} 타이머"></figure>')
page.append('</div>')


def figure(file, caption):
    assert (OUT / file).exists(), file
    safe = html.escape(caption)
    return f'<figure><figcaption>{safe}</figcaption><a href="{file}"><img loading="lazy" src="{file}" alt="{safe}"></a></figure>'


for title, items in [
    ('빠른 3회 입력 · 즉시 표시와 기록 하나', [('passive-input-android-preview.png', 'Android · 비올라 세 칸'), ('passive-input-android-one-record.png', 'Android · 0 → 3 기록 하나')]),
    ('조건이 있는 패시브', [('passive-input-android-tao-harmony.png', 'Android · 타오 조화 +100DMG'), ('passive-input-android-wolf-rita.png', 'Android · 울프 위압 토큰 소비 / 리타 팔라딘 선택')]),
    ('서든 데스와 기존 계산기', [('passive-input-android-sudden.png', 'Android · 타이머와 추가 턴 도구'), ('passive-input-android-classic.png', 'Android · 기존 UI에서 같은 로컬 대전 복원')]),
]:
    page.append('<h2>' + title + '</h2><div class="pair">')
    page.extend(figure(file, caption) for file, caption in items)
    page.append('</div>')

page.append('<h2>웹 · 19명 입력 확인</h2><p>조작 가능한 모든 패시브의 전송 대기, 최종값 병합, 서버 수치 일치와 패시브 영역 스크롤 없음을 확인했습니다. 웹과 Android는 별도 검증 대전입니다.</p>')
names_ko = dict(zip(
    ['setsumei', 'nia', 'root', 'delphy', 'keith', 'wolf', 'viola', 'tao', 'rita', 'rev', 'rin', 'yohan', 'jezebel', 'iomong', 'chimera', 'muyeong', 'finf', 'cmyk', 'minyeong'],
    ['세츠메이', '니아', '루트', '델피', '키스', '울프', '비올라', '타오', '리타', '레브', '린', '요한', '이제벨', '이오몽', '키메라', '무영', '핀프', 'CMYK', '미녕이'],
))
for pair in web['report']:
    names = pair['themes']
    file = 'passive-input-web-' + '-'.join(names) + '.png'
    page.append('<details><summary>' + html.escape(' · '.join(dict.fromkeys(names_ko[name] for name in names))) + '</summary>' + figure(file, f'{pair["inputs"]}회 입력 → 최종 상태 {pair["stored_actions"]}개 · 전송 배치 1개') + '</details>')
page.append('<details><summary>기존 웹 · 타오</summary>' + figure('passive-input-web-classic.png', '기존 타오 · 카운터와 조화를 한 배치로 저장') + '</details>')
page.append('<h2>검증 완료 · 2026-10-22</h2><p>모바일 타입 검사와 테스트 80개, Django/API 47개, 웹 19명과 Android 대표 상태 확인, Android·iOS 번들, Android 검토 APK 빌드를 통과했습니다. iOS 실제 기기 화면은 미검증입니다.</p></main></html>')
(OUT / 'passive-input-review.html').write_text('\n'.join(page), encoding='utf-8')
index = OUT / 'review.html'
text = index.read_text(encoding='utf-8')
if 'href="passive-input-review.html"' not in text:
    text = text.replace('<p class="note">', '<p class="note"><a href="passive-input-review.html">타이머 확대 · 패시브 0.9초 누적 입력 · 최신 검증 보기</a></p><p class="note">', 1)
    index.write_text(text, encoding='utf-8')
print(json.dumps({'timer_height_ratio': ratio, 'bundles': bundles, 'review': str(OUT / 'passive-input-review.html')}, ensure_ascii=False))
