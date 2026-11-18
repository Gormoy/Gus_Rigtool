"""
The shelf button and the hotkey commands call this module. Since the new window, everything is in:
  session.py  - the onion skin's state and actions (stays on when the windows close)
  window.py   - the window (Ghosts / Arcs / Settings)
  minibar.py  - the small bar over the viewport
"""
import maya.cmds as cmds

import onionSkinRenderer.session as session

OSR_WINDOW = None          # (old name, kept for older installers)


def show(develop=False, dockable=False):
    import onionSkinRenderer.window as window
    return window.show()


# hotkeys - Windows > Settings/Preferences > Hotkey Editor > Custom Scripts
def hk_toggle():
    session.get().toggle()


def hk_fill():
    session.get().fill()


def hk_toggle_arcs():
    s = session.get()
    s.setArcs("arcsShow", not s.prefs["arcsShow"])


def hk_mini_bar():
    import onionSkinRenderer.minibar as minibar
    bar = minibar.current()
    if bar is not None:
        try:
            if bar.isVisible():
                bar.closeByUser()
                return
        except RuntimeError:
            pass
    minibar.show()


def hk_next_key():
    now = cmds.currentTime(query=True)
    nxt = [k for k in session.get().keysOfOnion() if k > now + 1e-6]
    if nxt:
        cmds.currentTime(nxt[0])                       # auto fill brings the ghosts


def hk_previous_key():
    now = cmds.currentTime(query=True)
    prev = [k for k in session.get().keysOfOnion() if k < now - 1e-6]
    if prev:
        cmds.currentTime(prev[-1])
