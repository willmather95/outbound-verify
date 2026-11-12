#!/usr/bin/env python3
"""Pull the tag list from a public GTM container JS: tag function, event name, measurement ID,
and trigger conditions (predicates). Code only, no model."""
import re, json, sys
t = open(sys.argv[1]).read()
i = t.find('"resource":')
j = t.find('{', i); depth = 0
for k in range(j, len(t)):
    if t[k] == '{': depth += 1
    elif t[k] == '}':
        depth -= 1
        if depth == 0: break
res = json.loads(t[j:k+1])
macros = res.get('macros', [])
def mval(x):
    if isinstance(x, list) and x and x[0] == 'macro': 
        m = macros[x[1]]; return 'macro:' + m.get('function', '') + (':' + str(m.get('vtp_name', m.get('vtp_varType', ''))) if m else '')
    if isinstance(x, list) and x and x[0] == 'escape': return mval(x[1])
    if isinstance(x, list) and x and x[0] == 'template': return ''.join(str(mval(y)) for y in x[1:])
    return x
preds = res.get('predicates', [])
def pdesc(n):
    p = preds[n]; return f"{p.get('function')}({mval(p.get('arg0'))} ~ {mval(p.get('arg1'))})"
rules = res.get('rules', [])
fire = {}
for r in rules:
    ifs = [pdesc(x) for c in r if c[0] == 'if' for x in c[1:]]
    unl = [pdesc(x) for c in r if c[0] == 'unless' for x in c[1:]]
    for c in r:
        if c[0] == 'add':
            for tg in c[1:]: fire.setdefault(tg, []).append({'if': ifs, 'unless': unl})
for n, tag in enumerate(res.get('tags', [])):
    keep = {k: mval(v) for k, v in tag.items() if k in ('function', 'vtp_eventName', 'vtp_tagId', 'vtp_measurementIdOverride', 'vtp_conversionId', 'vtp_conversionLabel', 'vtp_html', 'vtp_url', 'tag_id', 'vtp_trackingId')}
    if 'vtp_html' in keep: keep['vtp_html'] = str(keep['vtp_html'])[:300]
    print(n, json.dumps(keep), '| fires:', json.dumps(fire.get(n, []))[:400])
