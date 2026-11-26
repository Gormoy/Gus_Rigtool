"""
5.8.0: do something once, a moment after the last change, and never while the animation plays (Gus: "as you
suggest" - the picker catches up when playback stops). The same rule Gus_Rigtool's window got in 5.7.9.

    from gus_animtool.look.later import Later
    self._later = Later(self.refresh, owner=self)     # then, on every change:  self._later()

Outside Maya (the tests) it runs at once.
"""

from .qt import QtCore

DELAY = 80                     # ms after the last change (a drag-select: once, not 50 times)
WHILE_PLAYING = 300            # ms: look again until playback stops


def in_maya():
    try:
        import maya.OpenMayaUI                  # noqa: F401
        return True
    except ImportError:
        return False


def playing():
    try:
        import maya.cmds as cmds
        return bool(cmds.play(query=True, state=True))
    except Exception:
        return False


class Later(object):
    def __init__(self, fn, owner=None, delay=DELAY):
        self.fn, self.owner, self.delay = fn, owner, delay
        self.timer = None
        self.runs = 0

    def __call__(self, *_):
        if not in_maya():
            return self._run()
        if self.timer is None:
            self.timer = QtCore.QTimer(self.owner)
            self.timer.setSingleShot(True)
            self.timer.timeout.connect(self._fire)
        self.timer.start(self.delay)
        return None

    def _fire(self):
        if playing():
            self.timer.start(WHILE_PLAYING)
            return
        self._run()

    def _run(self):
        self.runs += 1
        try:
            return self.fn()
        except RuntimeError:                    # its widget was closed meanwhile
            return None
