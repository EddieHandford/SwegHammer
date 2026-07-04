"""AUDIT D scratch: dump full ability text for specific DG units from raw catalog."""
import gzip, re, xml.etree.ElementTree as ET
path = 'data/bsdata/cache/Chaos - Death Guard.cat.gz'
with gzip.open(path,'rt',encoding='utf-8') as f:
    raw = f.read()
raw_ns = re.sub(r'\sxmlns="[^"]+"','',raw,count=1)
root = ET.fromstring(raw_ns)
targets = ['Plague Marines','Blightlord Terminators','Deathshroud Terminators','Plaguebearers','Mortarion','Poxwalkers']
for se in root.iter('selectionEntry'):
    if se.get('type') not in ('unit','model'): continue
    nm = se.get('name')
    if nm not in targets: continue
    # collect ability profile texts + T/W/Sv characteristics
    print('\n===== %s =====' % nm)
    for prof in se.iter('profile'):
        pt = prof.get('typeName','')
        if pt in ('Abilities','Unit'):
            chars = []
            for c in prof.iter('characteristic'):
                val = (c.text or '').strip()
                chars.append('%s=%s' % (c.get('name'), val[:120]))
            print('  [%s: %s] %s' % (pt, prof.get('name'), ' | '.join(chars)))
    # infoLinks
    ils = [il.get('name') for il in se.iter('infoLink')]
    fnpil = [x for x in ils if x=='Feel No Pain']
    print('  FNP infoLinks:', fnpil)
    targets.remove(nm)
    if not targets: break
