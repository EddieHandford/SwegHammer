"""AUDIT D scratch: extract per-unit Feel No Pain from the raw Death Guard
BSData catalog (ground truth), independent of parsed.json / overrides."""
import gzip, re, xml.etree.ElementTree as ET

path = 'data/bsdata/cache/Chaos - Death Guard.cat.gz'
with gzip.open(path, 'rt', encoding='utf-8') as f:
    raw = f.read()
# strip namespace for easy tag matching
raw_ns = re.sub(r'\sxmlns="[^"]+"', '', raw, count=1)
root = ET.fromstring(raw_ns)

fnp_re = re.compile(r'Feel No Pain (\d)\+', re.I)

def gather_text(el):
    parts = []
    for e in el.iter():
        for attr in ('name',):
            pass
        if e.text:
            parts.append(e.text)
    return ' '.join(parts)

# Walk top-level unit selectionEntries
def unit_entries(el):
    for se in el.iter('selectionEntry'):
        t = se.get('type')
        if t in ('unit','model'):
            yield se

seen = {}
for se in root.iter('selectionEntry'):
    if se.get('type') not in ('unit','model'):
        continue
    name = se.get('name')
    # collect all descendant text + characteristic values mentioning FNP
    fnps = set()
    for e in se.iter():
        txt = e.text or ''
        for m in fnp_re.finditer(txt):
            fnps.add(m.group(1))
        # characteristics named 'Feel No Pain'
    # also check infoLink names
    has_infolink = any(il.get('name')=='Feel No Pain' for il in se.iter('infoLink'))
    if name not in seen:
        seen[name] = (fnps, has_infolink)

for name in sorted(seen):
    fnps, il = seen[name]
    if fnps or il:
        print('%-40s FNP=%s infoLink=%s' % (name[:40], sorted(fnps) if fnps else '-', il))
