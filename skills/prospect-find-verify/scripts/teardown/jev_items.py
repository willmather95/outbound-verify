#!/usr/bin/env python3
"""Build Jev items from capture HARs (code side; evidence only, never field values).
Usage: python3 jev_items.py <outdir> <first-party domain[,alias...]> <capture prefix> [<capture prefix> ...]
Writes <outdir>/host-items.jsonl (one item per third-party host). Form items are written by hand from
analyze_capture.py output as {"id","page","builder","field_labels":[...]} lines in <outdir>/form-items.jsonl."""
import json, sys
from urllib.parse import urlsplit
outdir, first, caps = sys.argv[1], sys.argv[2].split(','), sys.argv[3:]
SKIP = ('fonts.gstatic.com', 'fonts.googleapis.com', 'maps.gstatic.com', 'i.ytimg.com', 'yt3.ggpht.com')
items = {}
for c in caps:
    for e in json.load(open(c + '.har'))['log']['entries']:
        u = urlsplit(e['request']['url']); h = u.hostname
        if not h or h in SKIP or any(h == f or h.endswith('.' + f) for f in first): continue
        it = items.setdefault(h, {'id': f'{first[0]}|{h}', 'host': h, 'example_paths': set(), 'page': e.get('pageref')})
        if len(it['example_paths']) < 5: it['example_paths'].add(u.path[:70])
with open(f'{outdir}/host-items.jsonl', 'a') as f:
    for it in items.values():
        it['example_paths'] = sorted(it['example_paths']); f.write(json.dumps(it) + '\n')
print(len(items), 'host items')
