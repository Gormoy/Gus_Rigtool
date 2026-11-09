"""Small shared helpers: undo chunks, selection, saved settings, messages."""

import contextlib
import json

import maya.cmds as cmds


@contextlib.contextmanager
def undo_chunk(name="Gus_Rigtool"):
    """Everything inside is one Ctrl+Z."""
    cmds.undoInfo(openChunk=True, chunkName=name)
    try:
        yield
    finally:
        cmds.undoInfo(closeChunk=True)


def track_selection_order():
    try:
        cmds.selectPref(trackSelectionOrder=True)
    except Exception:
        pass


def nodes_with_attr(attr, node_type=None):
    """Nodes (long names) that have this attribute, in any namespace - a direct lookup, much
    faster than going through every node of the scene."""
    found = cmds.ls("*." + attr, recursive=True, objectsOnly=True, long=True) or []
    out = []
    for n in found:
        if n not in out and (node_type is None or cmds.objectType(n, isAType=node_type)):
            out.append(n)
    return out


def selected_transforms(ordered=True):
    """Selected transforms (shapes become their parent), in selection order, long names."""
    sel = []
    if ordered:
        sel = cmds.ls(orderedSelection=True, long=True, objectsOnly=True) or []
    if not sel:
        sel = cmds.ls(selection=True, long=True, objectsOnly=True) or []
    out = []
    for node in sel:
        if cmds.objectType(node, isAType="shape"):
            node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
        if node and cmds.objectType(node, isAType="transform") and node not in out:
            out.append(node)
    return out


def uuid(node):
    return cmds.ls(node, uuid=True)[0]


def path(node_uuid):
    found = cmds.ls(node_uuid, long=True)
    return found[0] if found else None


# --------------------------------------------------------------------- settings

def ls(items, **flags):
    """cmds.ls on a list that may be empty: Maya lists EVERY node for an empty list, this gives []."""
    if items is None or (isinstance(items, (list, tuple, set)) and not items):
        return []
    return cmds.ls(list(items) if isinstance(items, set) else items, **flags) or []


def load_setting(key, default):
    """A value saved with save_setting (any JSON type), or default."""
    var = "gusrig_" + key
    if cmds.optionVar(exists=var):
        try:
            return json.loads(cmds.optionVar(query=var))
        except (ValueError, TypeError):
            pass
    return default


def save_setting(key, value):
    cmds.optionVar(stringValue=("gusrig_" + key, json.dumps(value)))


def tool_settings(key, defaults):
    """
    Settings a tool opens with: Gus_Rigtool defaults, then your saved defaults
    (Settings tab), then the values you last used.
    """
    out = dict(defaults)
    out.update(load_setting("userDefaults", {}).get(key, {}))
    out.update(load_setting(key, {}))
    return out


def update_setting(key, name, value):
    """Change one option of a tool's saved settings."""
    current = load_setting(key, {})
    current[name] = value
    save_setting(key, current)


# --------------------------------------------------------------------- messages

def info(tool, message, level="ok"):
    """Print, and show on the Gus_Rigtool status line."""
    print("%s: %s" % (tool, message))
    _status("%s: %s" % (tool, message), level)


def warn(tool, message):
    cmds.warning("%s: %s" % (tool, message))
    _status("%s: %s" % (tool, message), "warn")


def _status(message, level):
    try:
        from gus_rigtool.core import ui
        ui.status(message, level)
    except Exception:
        pass


# --------------------------------------------------------------------- clipboard

def copy_to_clipboard(text):
    """Put text on the clipboard (Qt). Prints it instead when that is not possible."""
    try:
        try:
            from PySide6 import QtWidgets
        except ImportError:
            from PySide2 import QtWidgets
        QtWidgets.QApplication.clipboard().setText(text)
        return True
    except Exception:
        print(text)
        return False


# --------------------------------------------------------------------- export / import

PREFIX = "gusrig_"


def export_everything(path):
    """All Gus_Rigtool settings + data files (saved shapes, presets) into one JSON file."""
    import os
    import gus_rigtool
    out = {"version": gus_rigtool.__version__, "settings": {}, "data": {}}
    for var in cmds.optionVar(list=True) or []:
        if var.startswith(PREFIX):
            out["settings"][var] = cmds.optionVar(query=var)
    if os.path.isdir(gus_rigtool.DATA_DIR):
        for name in os.listdir(gus_rigtool.DATA_DIR):
            if name.endswith(".json"):
                with open(os.path.join(gus_rigtool.DATA_DIR, name), "r") as f:
                    out["data"][name] = f.read()
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    return len(out["settings"]), len(out["data"])


def import_everything(path):
    import os
    import gus_rigtool
    with open(path, "r") as f:
        data = json.load(f)
    for var, value in data.get("settings", {}).items():
        if var.startswith(PREFIX) and isinstance(value, str):
            cmds.optionVar(stringValue=(var, value))
    if not os.path.isdir(gus_rigtool.DATA_DIR):
        os.makedirs(gus_rigtool.DATA_DIR)
    for name, text in data.get("data", {}).items():
        if name.endswith(".json") and "/" not in name and "\\" not in name:
            with open(os.path.join(gus_rigtool.DATA_DIR, name), "w") as f:
                f.write(text)
    return len(data.get("settings", {})), len(data.get("data", {}))


def settable(plug):
    """True when the plug can be set (not locked, not connected)."""
    try:
        return cmds.getAttr(plug, settable=True)
    except (RuntimeError, ValueError):
        return False
