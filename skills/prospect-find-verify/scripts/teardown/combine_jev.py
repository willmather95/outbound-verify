#!/usr/bin/env python3
"""Combine Jev answers in code. Label = highest-probability category if >= 0.5, else 'unsure (human)'.
Usage: python3 combine_jev.py <dir with host-log.jsonl and form-log.jsonl>. KNOWN is the code vendor table; it overrides Jev, and every disagreement is printed.
Also flags where Jev disagrees with a code rule (known-vendor table)."""
import json, sys
KNOWN = {'google-analytics.com':'ad_or_analytics','analytics.google.com':'ad_or_analytics','doubleclick.net':'ad_or_analytics','googletagmanager.com':'ad_or_analytics','facebook.com':'ad_or_analytics','facebook.net':'ad_or_analytics',
 'hotjar.com':'session_recording','hotjar.io':'session_recording','luckyorange.net':'session_recording','leadconnectorhq.com':'form_or_crm','neuralityhealth.ai':'booking','callrail.com':'call_tracking','calltrk.com':'call_tracking','tctm.co':'call_tracking','calltrackingmetrics.com':'call_tracking','whatconverts.com':'call_tracking','clarity.ms':'session_recording','fullstory.com':'session_recording','mouseflow.com':'session_recording','tiktok.com':'ad_or_analytics','bing.com':'ad_or_analytics','bidr.io':'ad_or_analytics','localmed.com':'booking','nexhealth.com':'booking','zocdoc.com':'booking','dental4.me':'booking','amazon-adsystem.com':'ad_or_analytics','trustedtv.com':'ad_or_analytics'}
# Add per-run hosts the page itself proves (e.g. a Meta CAPI gateway named in the pixel config 'openbridge', a session-recorder loader named in an inline snippet) via EXTRA.
import os
KNOWN.update(json.loads(os.environ.get('EXTRA', '{}')))
cats = ['ad_or_analytics','session_recording','booking','call_tracking','form_or_crm','needed_service']
out = []
D = sys.argv[1] if len(sys.argv) > 1 else '.'
for l in open(f'{D}/host-log.jsonl'):
    r = json.loads(l); a = r.get('answers') or {}
    p = {c: a.get(c, {}).get('noul', 0) for c in cats}
    best = max(p, key=p.get)
    lab = best if p[best] >= 0.5 else 'unsure (human)'
    host = r['id'].split('|')[1]
    rule = next((v for k, v in KNOWN.items() if host.endswith(k)), None)
    out.append({'id': r['id'], 'jev_label': lab, 'p': {k: round(v, 2) for k, v in p.items()}, 'code_rule': rule, 'agree': (rule is None or rule == lab), 'model': r.get('model')})
json.dump(out, open(f'{D}/host-labels.json', 'w'), indent=1)
for o in out: print(o['id'], o['jev_label'], o['p'][o['jev_label']] if o['jev_label'] in o['p'] else '', 'RULE='+str(o['code_rule']) if o['code_rule'] else '', '' if o['agree'] else '<<DISAGREE')
print('---forms')
for l in open(f'{D}/form-log.jsonl'):
    r = json.loads(l); print(r['id'], {k: v.get('noul') for k, v in (r.get('answers') or {}).items()}, r.get('model'))
