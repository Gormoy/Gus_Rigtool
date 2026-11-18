"""
Onion Skin - Live: the ghosts follow you. When the frame changes they update once Maya is idle (never during
playback - they catch up when it stops). Before a save they are taken out of the scene, after it they come back.
A new or opened scene empties the list.
"""

import maya.cmds as cmds

from onion_skin import core

JOBS = []
CALLBACKS = []
STATE = {"pending": False, "status": None}     # status: a function(text) the window gives, to show what happened


def _say(text):
    fn = STATE.get("status")
    if fn:
        try:
            fn(text)
        except Exception:
            pass


def playing():
    try:
        return bool(cmds.play(query=True, state=True))
    except RuntimeError:
        return False


def schedule(*_):
    """Update once Maya is idle (several frame changes in a row = one update)."""
    if STATE["pending"] or not int(core.opt("live")):
        return
    STATE["pending"] = True
    cmds.evalDeferred(run, lowestPriority=True)


def run():
    STATE["pending"] = False
    if playing() or not int(core.opt("live")) or not core.TARGETS:
        return None
    try:
        got = core.update()
    except RuntimeError as e:
        _say(str(e))
        return None
    except Exception as e:                          # never let a ghost problem break your animation work
        _say("ghosts not updated: %s" % e)
        return None
    _say(summary(got))
    return got


def summary(got):
    parts = []
    for cid, frames in sorted(got.get("frames", {}).items()):
        parts.append("%s: %s" % (cid, ", ".join("%g" % f for f in frames) or "none"))
    text = "; ".join(parts) or "no ghosts"
    if got.get("notes"):
        text += "  (" + "; ".join(got["notes"]) + ")"
    return text


def _before_save(*_):
    try:
        core.clear(keep_targets=True)              # the ghosts never go into your file
    except Exception:
        pass


def _after_save(*_):
    schedule()


def _scene_changed(*_):
    core.clear(keep_targets=False)
    _say("new scene: the list is empty - add your characters again")


def start():
    stop()
    JOBS.append(cmds.scriptJob(event=["timeChanged", schedule]))
    JOBS.append(cmds.scriptJob(conditionFalse=["playingBack", schedule]))
    JOBS.append(cmds.scriptJob(event=["SceneOpened", _scene_changed]))
    JOBS.append(cmds.scriptJob(event=["NewSceneOpened", _scene_changed]))
    try:
        import maya.api.OpenMaya as om
        CALLBACKS.append(om.MSceneMessage.addCallback(om.MSceneMessage.kBeforeSave, _before_save))
        CALLBACKS.append(om.MSceneMessage.addCallback(om.MSceneMessage.kAfterSave, _after_save))
    except Exception:
        pass


def stop():
    for j in JOBS:
        try:
            if cmds.scriptJob(exists=j):
                cmds.scriptJob(kill=j, force=True)
        except Exception:
            pass
    del JOBS[:]
    try:
        import maya.api.OpenMaya as om
        for c in CALLBACKS:
            om.MMessage.removeCallback(c)
    except Exception:
        pass
    del CALLBACKS[:]
