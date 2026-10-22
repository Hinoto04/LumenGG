"""Package shared calculator art and code-native transparent emblems.

Run after updating artifacts/calculator-character/generated-sources.json.
Only image format/size is changed; the generated artwork is preserved.
"""
import json
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'LumenGG/static/v2/calculator-character'
APP = ROOT / 'mobile/assets/calculator-character'
THEMES = json.loads((ROOT / 'LumenGG/content/calculator-ui.json').read_text(encoding='utf-8'))


def emblem(item):
    image = Image.new('RGBA', (512, 512))
    d = ImageDraw.Draw(image)
    color, light = item['accent'], item['secondary']
    def line(points, width=12, fill=color):
        d.line(points, fill=fill, width=width, joint='curve')
    def circle(box, width=9, fill=color):
        d.ellipse(box, outline=fill, width=width)
    def radial(n, r1, r2, offset=0):
        for i in range(n):
            a = offset + i * math.tau / n
            line([(256 + r1*math.cos(a), 256 + r1*math.sin(a)),
                  (256 + r2*math.cos(a), 256 + r2*math.sin(a))], 8)
    def star(n=4, outer=150, inner=50):
        points=[]
        for i in range(n*2):
            a=i*math.pi/n-math.pi/2
            r=outer if i%2==0 else inner
            points.append((256+r*math.cos(a),256+r*math.sin(a)))
        d.polygon(points, fill=color)
    motif = item['motif']
    circle((40,40,472,472), 3)
    if motif == 'crest':
        line([(256,90),(384,154),(366,306),(256,420),(146,306),(128,154),(256,90)])
        star(4,105,35)
    elif motif == 'eye':
        line([(70,256),(150,168),(256,128),(362,168),(442,256),(362,344),(256,384),(150,344),(70,256)])
        circle((175,175,337,337)); d.ellipse((238,190,274,322),fill=light)
    elif motif == 'core':
        circle((115,115,397,397),18); circle((182,182,330,330),12,light); radial(8,158,192,math.pi/8)
        d.polygon([(256,195),(288,256),(256,317),(224,256)],fill=light)
    elif motif in ('gear','cockpit'):
        radial(12 if motif=='gear' else 4,132,190,math.pi/4)
        circle((120,120,392,392),20); circle((198,198,314,314),12,light)
        if motif=='cockpit':
            line([(102,370),(102,128),(170,86)],8); line([(410,370),(410,128),(342,86)],8)
    elif motif=='card':
        line([(160,98),(364,136),(330,418),(126,380),(160,98)],14)
        d.polygon([(256,170),(310,254),(256,338),(202,254)],fill=light)
    elif motif=='claw':
        for i in range(3):
            x=140+i*85
            d.polygon([(x,115),(x+48,85),(x+10,345),(x-26,416),(x-10,280)],fill=color)
    elif motif=='ribbon':
        d.arc((120,80,365,330),210,530,fill=color,width=22)
        d.arc((150,190,395,440),30,350,fill=light,width=16)
        star(4,56,16)
    elif motif=='balance':
        circle((108,108,404,404),14)
        d.pieslice((116,116,396,396),90,270,fill=color)
        d.ellipse((186,116,326,256),fill=color)
        d.ellipse((186,256,326,396),fill=(10,14,25,255))
        d.ellipse((235,165,277,207),fill=light)
        d.ellipse((235,305,277,347),fill=color)
        radial(8,169,192,math.pi/8)
    elif motif=='star':
        star(6,174,68); circle((195,195,317,317),8,light)
    elif motif in ('dagger','blade'):
        d.polygon([(256,70),(289,280),(256,330),(223,280)],fill=color)
        line([(176,326),(336,326)],14,light); line([(256,326),(256,430)],18)
        if motif=='blade':
            d.arc((70,120,440,420),20,160,fill=light,width=10)
            line([(300,160),(406,90)],8)
    elif motif=='flame':
        d.polygon([(256,62),(307,198),(353,158),(389,288),(352,391),(256,438),(163,390),(121,294),(205,171),(190,289)],fill=color)
        d.polygon([(256,237),(302,329),(256,396),(215,335)],fill=light)
    elif motif=='reticle':
        circle((124,124,388,388),10); circle((201,201,311,311),10,light)
        radial(4,155,205); radial(12,124,139)
    elif motif=='web':
        radial(8,20,198,math.pi/8)
        for r in (65,118,174):
            points=[(256+r*math.cos(i*math.pi/4+math.pi/8),256+r*math.sin(i*math.pi/4+math.pi/8)) for i in range(9)]
            line(points,6)
        d.ellipse((231,218,281,294),fill=light)
    elif motif=='flower':
        for i in range(5):
            a=i*math.tau/5-math.pi/2; x=256+92*math.cos(a); y=256+92*math.sin(a)
            circle((x-67,y-67,x+67,y+67),12)
        d.ellipse((220,220,292,292),fill=light)
    elif motif=='fracture':
        for points in [[(245,70),(282,182),(256,226),(206,162)],[(335,142),(418,258),(302,244)],[(302,292),(366,402),(270,440)],[(205,278),(214,421),(102,334)],[(80,208),(180,116),(186,229)]]:
            d.polygon(points,fill=color)
    elif motif=='wave':
        for i,h in enumerate([52,99,148,73,121,179,88,133,63]):
            x=106+i*36
            line([(x,256-h),(x,256+h)],16, color if i%3==0 else light if i%3==1 else '#eea3dc')
    elif motif=='moon':
        d.arc((112,90,400,412),60,300,fill=color,width=48)
        d.polygon([(327,125),(341,165),(382,179),(341,193),(327,234),(313,193),(272,179),(313,165)],fill=light)
    return image.resize((256,256),Image.Resampling.LANCZOS)


def main():
    sources_path=ROOT/'artifacts/calculator-character/generated-sources.json'
    sources=json.loads(sources_path.read_text(encoding='utf-8')) if sources_path.exists() else {}
    asset_lines=[]
    for item in THEMES:
        key=item['theme_key']; folder=WEB/key; app=APP/key
        folder.mkdir(parents=True,exist_ok=True); app.mkdir(parents=True,exist_ok=True)
        emblem(item).save(folder/'emblem.png')
        if key in sources:
            with Image.open(sources[key]) as source:
                source.convert('RGB').resize((1024,1024),Image.Resampling.LANCZOS).save(folder/'background.webp',quality=83,method=6)
        if not (folder/'background.webp').exists():
            raise FileNotFoundError(f'Missing generated background: {key}')
        for filename in ('emblem.png','background.webp'):
            shutil.copyfile(folder/filename, app/filename)
        asset_lines.append(f'  {key}: {{ background: require("../assets/calculator-character/{key}/background.webp"), emblem: require("../assets/calculator-character/{key}/emblem.png") }},')
    shutil.copyfile(ROOT/'LumenGG/content/calculator-ui.json',ROOT/'mobile/src/calculator-themes.json')
    (ROOT/'mobile/src/calculator-art.ts').write_text('// Generated by scripts/build_calculator_assets.py.\nexport const calculatorArt: Record<string, {background: number; emblem: number}> = {\n'+'\n'.join(asset_lines)+'\n};\n',encoding='utf-8')
    print(f'Packaged {len(THEMES)} backgrounds and transparent emblems for web and app.')


if __name__=='__main__':
    main()
