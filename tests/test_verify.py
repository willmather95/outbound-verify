"""Offline test for verify.py: urlopen is replaced with made-up fixture pages and MX answers.

  python3 -m unittest discover tests
"""
import csv
import io
import json
import os
import runpy
import sys
import tempfile
import unittest
import urllib.parse
import urllib.request
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "skills/prospect-find-verify/scripts/verify.py"
CONFIG = ROOT / "skills/prospect-find-verify/scripts/dso-config.json"
PAGES = json.loads((ROOT / "tests/fixtures/pages.json").read_text())
MX = json.loads((ROOT / "tests/fixtures/mx.json").read_text())

EXPECTED = {
    "Bright Smile Implant Studio": ("VERIFIED", ""),
    "Lakeside Family Dental": ("REVIEW", "group language"),
    "Aspen Dental - Riverside": ("FAIL", "DSO match"),
    "Oak Street Dentistry": ("FAIL", "email not seen on own site"),
    "Harbor Implant Center": ("FAIL", "no MX record"),
    "Maple Grove Smiles": ("REVIEW", "no full-arch proof"),
}


def fake_urlopen(req, timeout=None, context=None):
    url = req.full_url if hasattr(req, "full_url") else req
    assert context is not None, "verify.py must pass a TLS context (cert checks on)"
    if url.startswith("https://dns.google/resolve"):
        name = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["name"][0]
        body = json.dumps({"Answer": [{"data": d} for d in MX.get(name, [])]})
        return io.BytesIO(body.encode())
    if url in PAGES:
        return io.BytesIO(PAGES[url].encode())
    raise urllib.error.HTTPError(url, 404, "not found", {}, None)


class VerifyGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        out = os.path.join(cls.tmp, "verified.csv")
        cwd = os.getcwd()
        os.chdir(cls.tmp)  # verify.py writes pages/<slug>.html next to the output
        try:
            with mock.patch.object(urllib.request, "urlopen", fake_urlopen), \
                 mock.patch.object(sys, "argv", ["verify.py", str(ROOT / "examples/sample-find.csv"), out, str(CONFIG)]), \
                 mock.patch("sys.stdout", new_callable=io.StringIO) as so:
                runpy.run_path(str(SCRIPT), run_name="__main__")
                cls.printed = so.getvalue()
        finally:
            os.chdir(cwd)
        cls.rows = {r["practice"]: r for r in csv.DictReader(open(out))}

    def test_every_row_gets_the_expected_status_and_reason(self):
        self.assertEqual(set(self.rows), set(EXPECTED))
        for name, (status, reason) in EXPECTED.items():
            with self.subTest(name=name):
                self.assertEqual(self.rows[name]["status"], status, self.rows[name]["reasons"])
                self.assertIn(reason, self.rows[name]["reasons"])

    def test_html_entity_email_counts_as_on_site(self):
        self.assertEqual(self.rows["Maple Grove Smiles"]["on_site"], "True")

    def test_summary_counts(self):
        self.assertIn("VERIFIED 1", self.printed)
        self.assertIn("REVIEW 2", self.printed)
        self.assertIn("FAIL 3", self.printed)


if __name__ == "__main__":
    unittest.main()
