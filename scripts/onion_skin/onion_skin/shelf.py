"""
Onion Skin - a shelf button. Run once (Script Editor, Python tab):

    import sys
    sys.path.insert(0, r"C:\\Users\\you\\Downloads\\OnionSkin")
    import onion_skin.shelf as s; s.install()

The button goes on the shelf you have open; Maya keeps it with the shelf.
"""
import os

import maya.cmds as cmds
import maya.mel as mel

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def command():
    return "\n".join([
        "import sys",
        "p = r%r" % ROOT,
        "if p not in sys.path:",
        "    sys.path.insert(0, p)",
        "import onion_skin",
        "onion_skin.show()",
    ])


def install():
    shelf_top = mel.eval("$onionSkinTmp = $gShelfTopLevel")
    current = cmds.tabLayout(shelf_top, query=True, selectTab=True)
    cmds.shelfButton(parent=current, label="Onion", annotation="Onion Skin: 3D ghosts of the past / next keys",
                     image="pythonFamily.png", imageOverlayLabel="Onion", command=command(), sourceType="python")
    print("Onion Skin: shelf button added to '%s'." % current)
