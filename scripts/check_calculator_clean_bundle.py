"""Confirm both exported platforms include every new icon and no old line icons."""
import hashlib,json
from pathlib import Path
root=Path(__file__).resolve().parent.parent
out=root/'artifacts/calculator-character'
export=root/'.temp/calculator-clean-v2-export'
metadata=json.loads((export/'metadata.json').read_text(encoding='utf-8'))
manifest=json.loads((root/'LumenGG/content/calculator-clean-icons.json').read_text(encoding='utf-8'))
web=root/'LumenGG/static/v2/calculator-character/clean'
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
expected={key:digest(web/a['file']) for key,a in manifest.items()}
old={key:digest(web/(key+'.png')) for key in manifest}
report={}
for platform,data in metadata['fileMetadata'].items():
    hashes={digest(export/a['path']) for a in data['assets'] if a['ext']=='png'}
    missing=[key for key,sha in expected.items() if sha not in hashes]
    obsolete=[key for key,sha in old.items() if sha in hashes]
    assert not missing,(platform,missing)
    assert not obsolete,(platform,obsolete)
    report[platform]={'new_icons_in_bundle':len(expected),'missing':missing,'old_line_icons_in_bundle':obsolete,'bundle':data['bundle']}
(out/'clean-v2-bundle-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
print('Android + iOS exports: all 24 new clean icons, no obsolete line icons.')
