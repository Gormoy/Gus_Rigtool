"""
Review Notes - get ONE SyncSketch review's notes as a file, so the import can be built on real data.
Runs on your Mac, in the Terminal (plain Python 3, nothing to install):

    "/Applications/Autodesk/maya2024/Maya.app/Contents/bin/mayapy" ~/Downloads/review_notes/syncsketch_sample.py

1. The first time it asks for your SyncSketch user name (your email) and API key (SyncSketch > your
   settings > Developer Options). It keeps them in ~/.review_notes_syncsketch.json, readable only by you.
   Never paste the key in a chat.
2. Pick the project, the review and the video (numbers).
3. It writes syncsketch_sample_<video id>.json on your Desktop: the video's details and its notes
   (drawings and comments) exactly as SyncSketch sends them. Look at it before you send it: it has the
   reviewers' names.

Based on SyncSketch's own Python library (github.com/syncsketch/python-api): header auth
"Authorization: apikey <user>:<key>", /api/v1/project/, /api/v1/review/?project__id=,
/api/v1/item/?reviews__id=, /api/v1/frame/?item__id=&active=1. Their API needs an Enterprise account.
"""

import getpass
import json
import os
import stat
import sys

try:
    from urllib.error import HTTPError, URLError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
except ImportError:                       # pragma: no cover - Python 2
    sys.exit("Use Python 3 (or Maya's mayapy).")

HOST = "https://syncsketch.com"
KEYS = os.path.join(os.path.expanduser("~"), ".review_notes_syncsketch.json")


def credentials():
    if os.path.isfile(KEYS):
        with open(KEYS) as f:
            got = json.load(f)
        if got.get("username") and got.get("api_key"):
            return got["username"], got["api_key"]
    print("SyncSketch user name (the email you log in with):")
    user = input("> ").strip()
    key = getpass.getpass("SyncSketch API key (Settings > Developer Options; it won't show as you type): ").strip()
    with open(KEYS, "w") as f:
        json.dump({"username": user, "api_key": key}, f)
    os.chmod(KEYS, stat.S_IRUSR | stat.S_IWUSR)
    print("Kept in %s (only you can read it). Delete that file to type them again." % KEYS)
    return user, key


def get(path, auth, **params):
    """Every page of a SyncSketch list (or one object)."""
    url = HOST + path + ("?" + urlencode(params) if params else "")
    out = []
    while url:
        req = Request(url, headers={"Authorization": "apikey %s:%s" % auth, "Accept": "application/json"})
        try:
            with urlopen(req, timeout=60) as r:
                data = json.loads(r.read().decode("utf-8"))
        except HTTPError as e:
            if e.code in (401, 403):
                sys.exit("SyncSketch said no (%d): wrong user name / key, or your plan has no API access "
                         "(it needs Enterprise). Delete %s to type them again." % (e.code, KEYS))
            sys.exit("SyncSketch answered %d for %s" % (e.code, path))
        except URLError as e:
            sys.exit("Can't reach SyncSketch: %s" % e.reason)
        if not isinstance(data, dict) or "objects" not in data:
            return data
        out += data["objects"]
        nxt = (data.get("meta") or {}).get("next")
        url = HOST + nxt if nxt else None
    return out


def pick(things, what, label):
    if not things:
        sys.exit("No %s found." % what)
    print("\n%s:" % what.capitalize())
    for i, t in enumerate(things, 1):
        print("  %2d  %s" % (i, label(t)))
    while True:
        answer = input("Number > ").strip()
        if answer.isdigit() and 1 <= int(answer) <= len(things):
            return things[int(answer) - 1]


def no_secrets(value):
    """Drops anything that looks like a key or token before the file is written."""
    if isinstance(value, dict):
        return {k: no_secrets(v) for k, v in value.items()
                if not any(w in k.lower() for w in ("api_key", "apikey", "token", "password", "secret"))}
    if isinstance(value, list):
        return [no_secrets(v) for v in value]
    return value


def main():
    auth = credentials()
    project = pick(get("/api/v1/project/", auth, active=1), "projects", lambda p: p.get("name"))
    review = pick(get("/api/v1/review/", auth, project__id=project["id"], active=1), "reviews",
                  lambda r: r.get("name"))
    item = pick(get("/api/v1/item/", auth, reviews__id=review["id"], active=1), "videos and pictures",
                lambda i: "%s  (%s)" % (i.get("name"), i.get("type", "")))
    frames = get("/api/v1/frame/", auth, item__id=item["id"], active=1)
    out = {"what": "Review Notes - SyncSketch sample", "project": project.get("name"),
           "review": {k: review.get(k) for k in ("id", "name", "uuid")},
           "item": item, "frames": frames}
    path = os.path.join(os.path.expanduser("~/Desktop"), "syncsketch_sample_%s.json" % item["id"])
    with open(path, "w") as f:
        json.dump(no_secrets(out), f, indent=1)
    sketches = sum(1 for f in frames if f.get("type") != "comment")
    print("\nSaved %s: %d note(s) (%d drawing(s)). Have a look, then send it." % (path, len(frames), sketches))


if __name__ == "__main__":
    main()
