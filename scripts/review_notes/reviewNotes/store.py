"""
The review file: one JSON file per shot, next to the scene - sh010_anim_v012.ma -> sh010_anim.review.json
(the _v012 is dropped, so the notes follow you when you version up; each note remembers its version).

Every change reads the file again just before saving (someone else may have saved meanwhile), then writes it
safely (a new file first, then swapped in; the one before is kept as .bak). A file that can't be read is never
overwritten: ReviewFileError says what's wrong.

No Maya in here - tested outside Maya.
"""

import copy
import datetime
import getpass
import json
import os
import re

SUFFIX = ".review.json"
FORMAT_VERSION = 1
TYPES = ("change", "fix", "add", "idea")
STATUSES = ("open", "in progress", "done")
VERSION_RE = re.compile(r"[._-]?v(\d+)$", re.IGNORECASE)


class ReviewFileError(Exception):
    pass


# ---------------- where the file is ----------------
def split_version(scene_path):
    """('sh010_anim', 'v012') from .../sh010_anim_v012.ma; ('sh010_anim', '') when there's no version."""
    base = os.path.splitext(os.path.basename(scene_path or ""))[0]
    m = VERSION_RE.search(base)
    if m and m.start() > 0:
        return base[:m.start()], "v" + m.group(1)
    return base, ""


def path_for_scene(scene_path):
    """The review file of a scene, or None for a scene that was never saved."""
    if not scene_path:
        return None
    shot, _ = split_version(scene_path)
    if not shot or shot.lower().startswith("untitled"):
        return None
    return os.path.join(os.path.dirname(os.path.abspath(scene_path)), shot + SUFFIX)


# ---------------- notes ----------------
def now():
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M")


def who():
    try:
        return getpass.getuser()
    except Exception:
        return "someone"


def make_note(camera, frame, hold=6, kind="change", text="", strokes=None, author=None, scene_version=""):
    """A new note (no id yet: add_note gives it one)."""
    return normalize_note({"camera": camera, "frame": int(frame), "hold": int(hold), "type": kind,
                           "status": "open", "text": text, "author": author or who(), "created": now(),
                           "scene_version": scene_version, "strokes": strokes or []})


def normalize_note(note):
    """Fills what's missing with defaults; keeps fields it doesn't know (a newer version's)."""
    n = dict(note)
    n.setdefault("id", "")
    n["camera"] = str(n.get("camera") or "")
    try:
        n["frame"] = int(round(float(n.get("frame", 0))))
    except (TypeError, ValueError):
        n["frame"] = 0
    try:
        n["hold"] = max(1, int(n.get("hold", 1)))
    except (TypeError, ValueError):
        n["hold"] = 1
    if n.get("type") not in TYPES:
        n["type"] = "change"
    if n.get("status") not in STATUSES:
        n["status"] = "open"
    n["text"] = str(n.get("text") or "")
    n.setdefault("author", "")
    n.setdefault("created", "")
    n.setdefault("scene_version", "")
    n.setdefault("replies", [])
    n.setdefault("picture", None)        # a small picture of the frame when the note was made (step 3)
    n.setdefault("pin", None)            # later: pinned to a control in 3D
    n["strokes"] = [s for s in (n.get("strokes") or []) if isinstance(s, dict)]
    return n


def empty(shot=""):
    return {"version": FORMAT_VERSION, "shot": shot, "notes": []}


def next_id(data):
    nums = [int(m.group(1)) for m in (re.match(r"n_(\d+)$", n.get("id", "")) for n in data["notes"]) if m]
    return "n_%04d" % (max(nums or [0]) + 1)


# ---------------- reading and writing ----------------
def read(path):
    """The review file as a dict (an empty review if there's no file yet)."""
    shot = os.path.basename(path)[:-len(SUFFIX)] if path.endswith(SUFFIX) else ""
    if not os.path.isfile(path):
        return empty(shot)
    try:
        with open(path) as f:
            data = json.load(f)
    except ValueError as e:
        backup = " (the version before is in %s.bak)" % os.path.basename(path) if os.path.isfile(path + ".bak") else ""
        raise ReviewFileError("The review file can't be read (%s): %s. Fix it or move it away%s."
                              % (e, path, backup))
    except (IOError, OSError) as e:
        raise ReviewFileError("The review file can't be opened: %s (%s)" % (path, e))
    if not isinstance(data, dict) or not isinstance(data.get("notes", []), list):
        raise ReviewFileError("This isn't a review file: %s" % path)
    if int(data.get("version", 1)) > FORMAT_VERSION:
        raise ReviewFileError("This review file was made by a newer Review Notes (format %s). Update the tool."
                              % data.get("version"))
    data.setdefault("shot", shot)
    data["notes"] = [normalize_note(n) for n in data.get("notes", []) if isinstance(n, dict)]
    return data


def write(path, data, backup=True):
    """Saves safely: a new file first, then swapped in; the one before is kept as .bak (unless backup=False:
    while you drag the eraser, so .bak keeps the file from before you started)."""
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    out = copy.deepcopy(data)
    out["version"] = FORMAT_VERSION
    tmp = path + ".saving"
    with open(tmp, "w") as f:
        json.dump(out, f, indent=1, sort_keys=False)
        f.write("\n")
    if os.path.isfile(path) and backup:
        try:
            if os.path.isfile(path + ".bak"):
                os.remove(path + ".bak")
            os.rename(path, path + ".bak")
        except OSError:
            pass
    os.replace(tmp, path)
    _cache.pop(path, None)


def add_note(path, note):
    """Adds a note (read again first) and saves. Returns the note with its id."""
    data = read(path)
    n = normalize_note(note)
    n["id"] = next_id(data)
    data["notes"].append(n)
    write(path, data)
    return n


def update_note(path, note_id, **changes):
    """Changes fields of one note (read again first) and saves. Returns the note, or None if it's gone."""
    data = read(path)
    for n in data["notes"]:
        if n["id"] == note_id:
            n.update(changes)
            n["updated"] = now()
            n.update(normalize_note(n))
            write(path, data)
            return n
    return None


def set_strokes(path, strokes_by_id, backup=True):
    """New strokes for several notes in one save (the eraser). Returns how many notes changed."""
    data = read(path)
    done = 0
    for n in data["notes"]:
        if n["id"] in strokes_by_id:
            n["strokes"] = strokes_by_id[n["id"]]
            n["updated"] = now()
            done += 1
    if done:
        write(path, data, backup)
    return done


def delete_note(path, note_id):
    data = read(path)
    keep = [n for n in data["notes"] if n["id"] != note_id]
    if len(keep) == len(data["notes"]):
        return False
    data["notes"] = keep
    write(path, data)
    return True


# ---------------- for drawing (every refresh) ----------------
_cache = {}


def notes_for_drawing(path):
    """The notes, read again only when the file changed. (notes, problem) - problem is '' or what's wrong."""
    if not path:
        return [], ""
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        return [], ""
    got = _cache.get(path)
    if got is None or got[0] != stamp:
        try:
            got = (stamp, read(path)["notes"], "")
        except ReviewFileError as e:
            got = (stamp, [], str(e))
        _cache[path] = got
    return got[1], got[2]
