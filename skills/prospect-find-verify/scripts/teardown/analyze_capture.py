#!/usr/bin/env python3
# Usage: python3 analyze_capture.py <capture prefix>   (the <out> given to capture.mjs; reads <out>.har and <out>.pN.dom.html)
# VENDORS below is the code vendor list that sits on top of Jev labels.
"""Deterministic parsing of a capture: forms, fields (names/labels only), iframes, scripts,
tel: numbers, tracker IDs, vendor fingerprints, and per-request tracker details. Never prints values
of form fields (there are none: nothing was typed)."""
import json, re, sys, glob
from urllib.parse import urlsplit, parse_qsl
from bs4 import BeautifulSoup

P = sys.argv[1]; d = P.split('/')[-1]; har = json.load(open(P + '.har'))
ents = har['log']['entries']; pages = har['log']['pages']
VENDORS = {'callrail':'CallRail','calltrk':'CallRail','swap.js':'CallRail','whatconverts':'WhatConverts','calltrackingmetrics':'CallTrackingMetrics','tctm.co':'CallTrackingMetrics',
 'adit.com':'Adit','weave':'Weave','getweave':'Weave','localmed':'LocalMed','nexhealth':'NexHealth','zocdoc':'Zocdoc','neuralityhealth':'Neurality Health',
 'flexbook':'Flex','modento':'Modento','yapi':'YAPI','lighthouse360':'Lighthouse 360','birdeye':'Birdeye','podium':'Podium','tawk.to':'tawk.to','gravityforms':'Gravity Forms','gform':'Gravity Forms',
 'wpcf7':'Contact Form 7','usebasin':'Basin','squarespace':'Squarespace','showit':'Showit','userway':'UserWay','accessibe':'accessiBe','gp-assets':'GP assets','hubspot':'HubSpot','clarity.ms':'Microsoft Clarity',
 'hotjar':'Hotjar','reviewwave':'ReviewWave','smilesnap':'SmileSnap','dentalqore':'DentalQore','sesamecommunications':'Sesame','doctible':'Doctible','revenuewell':'RevenueWell','solutionreach':'Solutionreach','jotform':'Jotform','recaptcha':'reCAPTCHA','cleantalk':'CleanTalk'}
out = {'domain': d, 'pages': []}
for p in pages:
    n = p['n']; h = open(f'{P}.p{n}.dom.html', errors='ignore').read(); s = BeautifulSoup(h, 'html.parser')
    pg = {'n': n, 'url': p['url'], 'final': p['finalUrl'], 'shot': f'{P}.p{n}.png', 'forms': [], 'iframes': [], 'scripts': [], 'tel': [], 'ids': [], 'vendors': []}
    for f in s.find_all('form'):
        fields = []
        for i in f.find_all(['input', 'textarea', 'select']):
            if (i.get('type') or '').lower() in ('hidden', 'submit', 'button'): 
                if (i.get('type') or '').lower()=='hidden': fields.append({'name': i.get('name'), 'type': 'hidden'})
                continue
            lab = ''
            if i.get('id'):
                l = s.find('label', attrs={'for': i.get('id')}); lab = l.get_text(' ', strip=True) if l else ''
            fields.append({'name': i.get('name'), 'type': i.get('type') or i.name, 'label': lab[:60], 'placeholder': (i.get('placeholder') or '')[:60], 'aria': (i.get('aria-label') or '')[:60]})
        pg['forms'].append({'action': f.get('action'), 'method': f.get('method'), 'id': f.get('id'), 'class': ' '.join(f.get('class') or [])[:80], 'fields': fields, 'snippet': str(f)[:300]})
    # Formless inputs (e.g. Showit)
    loose = [i for i in s.find_all(['input', 'textarea']) if not i.find_parent('form') and (i.get('type') or '').lower() not in ('hidden','submit','button','search')]
    if loose: pg['loose_inputs'] = [{'name': i.get('name'), 'placeholder': (i.get('placeholder') or '')[:60], 'snippet': str(i)[:200]} for i in loose]
    pg['iframes'] = sorted(set(i.get('src') or i.get('data-src') or '' for i in s.find_all('iframe')))
    pg['scripts'] = sorted(set(x.get('src') for x in s.find_all('script') if x.get('src')))
    pg['tel'] = sorted(set(re.findall(r'tel:([+\d().\-\s]{7,20})', h)))
    pg['ids'] = sorted(set(re.findall(r'\b(GTM-[A-Z0-9]{5,9}|G-[A-Z0-9]{8,12}|AW-\d{8,12}|UA-\d+-\d+)\b', h)))
    low = h.lower(); pg['vendors'] = sorted(set(v for k, v in VENDORS.items() if k in low))
    out['pages'].append(pg)
# request-level
reqs = []
for e in ents:
    u = urlsplit(e['request']['url']); q = dict(parse_qsl(u.query, keep_blank_values=True))
    rec = {'page': e.get('pageref'), 'method': e['request']['method'], 'host': u.hostname, 'path': u.path[:100], 'status': e['response'].get('status'), 'iframe': e.get('_inIframeSession')}
    if u.hostname and ('facebook.com' in u.hostname and u.path.startswith('/tr')):
        rec['meta'] = {'id': q.get('id'), 'ev': q.get('ev'), 'dl': q.get('dl', '')[:120], 'udff_keys': sorted(k for k in q if k.startswith('udff') or k.startswith('ud['))}
    if u.hostname and 'connect.facebook.net' in u.hostname and '/signals/config/' in u.path: rec['meta_config'] = u.path
    if u.hostname and ('google-analytics.com' in u.hostname or 'analytics.google.com' in u.hostname) and 'collect' in u.path:
        body = (e['request'].get('postData') or {}).get('text', '')
        evs = re.findall(r'(?:^|&|\n)en=([^&\n]+)', body) + ([q['en']] if 'en' in q else [])
        rec['ga'] = {'tid': q.get('tid'), 'en': evs, 'dl': q.get('dl', '')[:120]}
    if u.hostname and ('doubleclick' in u.hostname or 'googleadservices' in u.hostname) and ('conversion' in u.path or 'viewthrough' in u.path or 'rmkt' in u.path):
        rec['gads'] = {'path': u.path[:80], 'label': q.get('label')}
    reqs.append(rec)
out['requests'] = reqs
# Meta config: automatic advanced matching flags (pixel config script). Look for 'automaticMatching' in fetched config? Not in HAR bodies; record URL only.
json.dump(out, open(P + '.analysis.json', 'w'), indent=1)
# print compact
for pg in out['pages']:
    print('PAGE', pg['n'], pg['url'], '->', pg['final'])
    print('  ids', pg['ids'], 'tel', pg['tel'], 'vendors', pg['vendors'])
    print('  iframes', [x[:140] for x in pg['iframes']])
    print('  scripts3p', [x[:120] for x in pg['scripts'] if d.split('.')[0] not in x and not x.startswith('/')])
    for f in pg['forms']: print('  FORM', f['action'], f['method'], f['id'], f['class'], [(x.get('name'), x.get('type'), x.get('label') or x.get('placeholder') or x.get('aria')) for x in f['fields']])
    if pg.get('loose_inputs'): print('  LOOSE', [(x['name'], x['placeholder']) for x in pg['loose_inputs']])
seen = set()
for r in reqs:
    for k in ('meta', 'ga', 'gads', 'meta_config'):
        if k in r:
            key = (k, json.dumps(r[k], sort_keys=True), r['page'])
            if key in seen: continue
            seen.add(key); print('  REQ', r['page'][-40:] if r['page'] else '', k, r[k])
hosts = sorted(set(r['host'] for r in reqs if r['host'] and r['iframe']))
print('  iframe-session hosts', hosts)
