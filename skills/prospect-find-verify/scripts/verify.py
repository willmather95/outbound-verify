"""Verify a prospect CSV: email seen on the practice's own site, live MX,
DSO block list, independence check, and full-arch proof.
Usage: python3 verify.py [input.csv] [output.csv] [config.json]
Input columns: name,city,url,email[,page_where_email_seen]
Status: VERIFIED (all checks pass) | REVIEW (independence unsure or no
full-arch proof; a human qualifies before sending) | FAIL."""
import csv, re, json, ssl, sys, os, urllib.request, urllib.parse, concurrent.futures as cf

IN  = sys.argv[1] if len(sys.argv) > 1 else "claude-find.csv"
OUT = sys.argv[2] if len(sys.argv) > 2 else "verified.csv"
CFG = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "dso-config.json")
cfg = json.load(open(CFG))
rx = lambda key: re.compile("|".join(cfg[key]), re.I)
DSO, GROUP, ARCH = rx("dso_block"), rx("group_language"), rx("full_arch_proof")
ctx = ssl.create_default_context()  # certificate verification ON

def get(u):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        return urllib.request.urlopen(req, timeout=20, context=ctx).read().decode("utf8", "ignore")
    except ssl.SSLError:
        return "__SSL_ERROR__"
    except Exception:
        return ""

def mx(d):
    try:
        r = urllib.request.urlopen("https://dns.google/resolve?type=MX&name=" + d, timeout=15, context=ctx)
        return [a["data"] for a in json.loads(r.read()).get("Answer", [])]
    except Exception:
        return []

def chk(r):
    n, c, u, e = [x.strip() for x in r[:4]]; e = e.lower()
    pg = r[4].strip() if len(r) > 4 else ""
    urls = [u] + ([pg] if pg.startswith("http") else []) + [urllib.parse.urljoin(u, p) for p in ("contact", "contact-us", "contact-us/")]
    html, on, where, ssl_bad = "", False, "", False
    for x in urls:
        h = get(x)
        if h == "__SSL_ERROR__": ssl_bad = True; continue
        html += h
        if e in h.lower() or e.replace("@", "&#64;") in h.lower(): on, where = True, x; break
    about = "".join(h for h in (get(urllib.parse.urljoin(u, p)) for p in cfg["about_paths"]) if h != "__SSL_ERROR__")
    text = html + about
    m = mx(e.split("@")[1]) if "@" in e else []
    dso = DSO.search(n + " " + text)
    grp = GROUP.search(text)
    arch = ARCH.search(text)
    reasons = []
    if not on: reasons.append("email not seen on own site")
    if not m: reasons.append("no MX record")
    if dso: reasons.append("DSO match: " + dso.group(0))
    if ssl_bad: reasons.append("SSL certificate error on some pages")
    independent = "no" if dso else ("unsure" if grp else "yes")
    if grp and not dso: reasons.append("group language: " + grp.group(0))
    if not arch: reasons.append("no full-arch proof found")
    if not on or not m or dso: status = "FAIL"
    elif independent == "unsure" or not arch or ssl_bad: status = "REVIEW"
    else: status = "VERIFIED"
    slug = re.sub(r"\W+", "-", n.lower())[:40]
    os.makedirs("pages", exist_ok=True)
    with open(f"pages/{slug}.html", "w") as f: f.write(text)
    return [n, c, u, e, on, where, " | ".join(m)[:60], independent, arch.group(0) if arch else "", status, "; ".join(reasons), slug]

rows = [r for r in csv.reader(open(IN)) if len(r) >= 4 and "@" in r[3]]
with cf.ThreadPoolExecutor(16) as ex: out = list(ex.map(chk, rows))
with open(OUT, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["practice", "city", "url", "email", "on_site", "seen_at", "mx", "independent", "full_arch_proof", "status", "reasons", "slug"])
    w.writerows(out)
for s in ("VERIFIED", "REVIEW", "FAIL"): print(s, sum(o[9] == s for o in out))
