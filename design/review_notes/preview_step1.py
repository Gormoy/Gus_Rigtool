"""
Preview of Review Notes step 1 without Maya: the tool's own drawing code (scripts/review_notes/reviewNotes/draw.py)
on a stand-in view, with a review file made by its own store.py - what Gus should see after rn.sample().

    python3 design/review_notes/preview_step1.py      # writes design/review_notes/step1_*.png
"""

import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "review_notes"))
sys.path.insert(0, HERE)

from preview_tryit import RENDER, VIEW, W, H, background, frame_label, paint  # noqa: E402
from reviewNotes import draw, store  # noqa: E402

RED, YELLOW = [1.0, 0.30, 0.26], [1.0, 0.82, 0.25]
ARC = [{"tool": "bezier", "color": RED, "width": 3, "closed": False, "anchors": [
    [[0.30, 0.70], [0.30, 0.70], [0.33, 0.30]], [[0.45, 0.18], [0.37, 0.18], [0.53, 0.18]],
    [[0.60, 0.70], [0.57, 0.30], [0.60, 0.70]]]},
    {"tool": "arrow", "color": RED, "width": 3, "points": [[0.45, 0.42], [0.45, 0.26]]}]
CONTACT = [{"tool": "circle", "color": YELLOW, "width": 3, "points": [[0.40, 0.72], [0.52, 0.90]]},
           {"tool": "arrow", "color": YELLOW, "width": 3, "points": [[0.70, 0.60], [0.53, 0.78]]}]


def main():
    path = os.path.join(tempfile.mkdtemp(), "sh010_anim.review.json")
    store.add_note(path, store.make_note("shotCam", 1001, 6, "change",
                                         "Sample note: arc too flat here, push the peak higher.", ARC))
    b = store.add_note(path, store.make_note("shotCam", 1007, 4, "fix", "Contact: the foot slides. Lock it.",
                                             CONTACT))
    store.update_note(path, b["id"], status="done")
    notes = store.read(path)["notes"]
    gate = draw.gate_rect(VIEW, RENDER, W, H)
    for name, frame, opts in (("step1_note", 1003, draw.Options()),
                              ("step1_done", 1008, draw.Options()),
                              ("step1_only_open", 1008, draw.Options(only_open=True))):
        items = draw.build_items(notes, draw.camera_names("shotCam"), frame, gate, opts)
        img = frame_label(paint(background(gate, "shotCam"), items), frame)
        img.convert("RGB").save(os.path.join(HERE, name + ".png"))
        print("wrote", name, len(items), "items")


if __name__ == "__main__":
    main()
