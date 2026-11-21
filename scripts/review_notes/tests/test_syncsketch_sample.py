"""
syncsketch_sample.py with made-up SyncSketch answers (no network): pages, picking, the auth header, the
file it writes, and that nothing secret ends up in it.

    python3 scripts/review_notes/tests/test_syncsketch_sample.py
"""

import builtins
import io
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import syncsketch_sample as ss  # noqa: E402

PAGES = {
    "/api/v1/project/": [{"objects": [{"id": 1, "name": "Tree short"}], "meta": {"next": None}}],
    "/api/v1/review/": [{"objects": [{"id": 7, "name": "anim dailies", "uuid": "u7"}], "meta": {"next": None}}],
    "/api/v1/item/": [{"objects": [{"id": 70, "name": "sh010_v012.mov", "type": "video", "fps": 24,
                                    "width": 1920, "height": 1080}], "meta": {"next": None}}],
    "/api/v1/frame/": [
        {"objects": [{"id": 1, "frame": 5, "type": "sketch", "data": {"paths": []}, "creator": {"api_key": "X"}}],
         "meta": {"next": "/api/v1/frame/?page=2"}},
        {"objects": [{"id": 2, "frame": 9, "type": "comment", "text": "lift it", "auth_token": "Y"}],
         "meta": {"next": None}}],
}


class Answer(object):
    def __init__(self, data):
        self.data = data

    def read(self):
        return json.dumps(self.data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.home = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.home, "Desktop"))
        self.calls = []
        self.served = {k: list(v) for k, v in PAGES.items()}

        def urlopen(req, timeout=None):
            self.calls.append((req.full_url, req.headers.get("Authorization")))
            path = req.full_url[len(ss.HOST):].split("?")[0]
            return Answer(self.served[path].pop(0))
        self.old = (ss.urlopen, ss.KEYS, os.path.expanduser, builtins.input, ss.getpass.getpass)
        ss.urlopen = urlopen
        ss.KEYS = os.path.join(self.home, ".review_notes_syncsketch.json")
        os.path.expanduser = lambda p: p.replace("~", self.home)
        answers = iter(["gus@example.com", "1", "1", "1"])
        builtins.input = lambda *a: next(answers)
        ss.getpass.getpass = lambda *a: "k" * 40

    def tearDown(self):
        ss.urlopen, ss.KEYS, os.path.expanduser, builtins.input, ss.getpass.getpass = self.old
        shutil.rmtree(self.home)

    def test_saves_the_notes_without_secrets(self):
        out = io.StringIO()
        old, sys.stdout = sys.stdout, out
        try:
            ss.main()
        finally:
            sys.stdout = old
        path = os.path.join(self.home, "Desktop", "syncsketch_sample_70.json")
        with open(path) as f:
            data = json.load(f)
        self.assertEqual([f["id"] for f in data["frames"]], [1, 2])          # both pages
        self.assertEqual(data["item"]["width"], 1920)
        text = json.dumps(data)
        self.assertNotIn("api_key", text)
        self.assertNotIn("auth_token", text)
        self.assertNotIn("k" * 40, text)
        self.assertTrue(all(a == "apikey gus@example.com:" + "k" * 40 for _, a in self.calls))
        self.assertIn("item__id=70", self.calls[3][0])
        self.assertEqual(oct(os.stat(ss.KEYS).st_mode & 0o777), "0o600")      # only Gus can read the key file
        self.assertIn("2 note(s) (1 drawing(s))", out.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=1)
