"""
Small node helpers shared by the whole tool (4.2.0) - one copy instead of a private one in every module, so they
can't drift apart.

    long_name(n)    : the full path, or None (the first match when several share the name)
    unique_long(n)  : the full path only when exactly one node has that name, else None
    short(n)        : the name without its path (None stays None)
    parent_of(n)    : the full path of the parent, or None
    world_matrix(n) : the 16 numbers of the world matrix
    world_pos(n)    : world translation
"""

import maya.cmds as cmds


def long_name(n):
    found = cmds.ls(n, long=True) or []
    return found[0] if found else None


def unique_long(n):
    found = cmds.ls(n, long=True) or []
    return found[0] if len(found) == 1 else None


def short(n):
    return n.split("|")[-1] if n else n


def parent_of(n):
    return (cmds.listRelatives(n, parent=True, fullPath=True) or [None])[0]


def world_matrix(n):
    return cmds.xform(n, query=True, worldSpace=True, matrix=True)


def world_pos(n):
    return cmds.xform(n, query=True, worldSpace=True, translation=True)
