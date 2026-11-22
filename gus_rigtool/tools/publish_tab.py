"""
Publish (5.7.10: its own file - it was part of Build's): Publish, Unpublish, Deliver to animators and their options.
In the new window: Check & publish > Publish; in the legacy look: on Build's page, as before.

    import gus_rigtool.main as gr; gr.show_tool("publish")

Lighter: Build's builder (modules, guides, limbs...) loads only when a button needs it.
"""

from gus_rigtool.newui.proxy import cmds   # maya.cmds; the new window's fields by name

from gus_rigtool.core import ui, utils

TOOL = "Publish"
_P, N, _w, _guard = ui.tool_helpers("p_publish_", TOOL)


def _refresh_build_list():
    """Build's module list shows 'published' - only if Build is open (it isn't loaded just for this)."""
    import sys
    bt = sys.modules.get("gus_rigtool.tools.build_tab")
    if bt is not None:
        try:
            bt.refresh_list()
        except Exception:
            pass


PUBLISH_BOOLS = [
    ("lock_groups", "Lock the groups (offset / space / rig groups)",
     "Animators only see controls: every group's channels are locked and hidden."),
    ("hide_locked", "Hide locked channels on controls", "Locked channels leave the channel box."),
    ("lock_fk_translate", "FK controls can't translate", "Lock translate on every FK control."),
    ("hide_joints", "Hide the joints (skeleton_grp)", "The skin still works."),
    ("geo_reference", "Geometry not selectable (geo_grp as reference)", "Click through the model to the controls."),
    ("sets", "Selection sets (rig_ctrls_set, a set per module, bind_joints_set)", ""),
    ("protect_networks", "Protect the networks (lock utility nodes)",
     "Utility nodes, driven keys and constraints can't be deleted or renamed by accident. Unpublish unlocks them."),
    ("default_pose", "Save the default pose on each control", "Reset pose and Gus Animtool's Reset go back to it."),
    ("run_checker", "Run the Checker on the rig after", "A report window shows what the Checker found."),
]


def _publish_options():
    from gus_rigtool.builder import publish
    o = dict(publish.DEFAULTS, run_checker=True)
    o.update(utils.load_setting("build_publish", {}) or {})
    return o


def _save_publish(*_):
    o = {}
    for key, _l, _t in PUBLISH_BOOLS:
        o[key] = cmds.checkBox(NP("Pub_" + key), query=True, value=True)
    o["guides"] = ["hide", "delete", "leave"][cmds.optionMenu(NP("Pub_guides"), query=True, select=True) - 1]
    utils.save_setting("build_publish", o)
    return o


def publish_rig(*_):
    from gus_rigtool.builder import publish
    o = _save_publish()
    from gus_rigtool.builder import guides
    if o["guides"] == "delete" and guides.module_groups():
        if cmds.confirmDialog(title="Publish - delete the guides", button=["Delete them", "Cancel"],
                              message="Without guides you can't go Back to guides or rebuild a module.\n"
                                      "Save a template first if you may need them.",
                              defaultButton="Cancel", cancelButton="Cancel", dismissString="Cancel") != "Delete them":
            return
    done = publish.publish(o)
    _refresh_build_list()
    from gus_rigtool.tools import home
    home.say_next("Build", "published.")
    if o.get("run_checker"):
        fails, warns, text = publish.check()
        ui.report_window("Gus_Rigtool - published rig",
                         "Published:\n  " + "\n  ".join(done) + "\n\nChecker on the rig: %d fail, %d warning\n\n%s"
                         % (fails, warns, text))


def _deliver(*_):
    from gus_rigtool.builder import deliver
    deliver.show()


def unpublish_rig(*_):
    from gus_rigtool.builder import publish
    publish.unpublish()
    _refresh_build_list()


SKIP_PUBLISH = {"on": False}     # 5.7.6: while the new window records Build (Publish has its own page there)
_PUB = {"p": None}               # the prefix of the Publish fields shown (Build's, or the Publish page's)


def NP(name):
    """A Publish field's name (on Build's page in the old window, on Check & publish > Publish in the new one)."""
    return (_PUB["p"] or _P["p"]) + name


def _publish_part(collapse=True, prefix=None):
    """Publish, Unpublish, Deliver and their options (5.7.6: on its own, so the new window can show it in Check &
    publish). prefix: the page's (Build's, in the legacy look)."""
    _PUB["p"] = prefix or _P["p"]
    ui.section("Publish (clean rig for animators)", collapse=collapse,
               help_text="Publish makes the built rig clean: groups locked, locked channels hidden, joints hidden, "
               "selection sets (rig_ctrls_set with a set per module, bind_joints_set), each control remembers "
               "its default pose (Reset pose and Gus Animtool go back to it), guides hidden. Then the Checker runs on "
               "the rig. Unpublish puts everything back; Build / Back to guides unpublish first.")
    po = _publish_options()
    for key, label, tip in PUBLISH_BOOLS:
        cmds.checkBox(NP("Pub_" + key), label=label, value=bool(po[key]), annotation=tip,
                      changeCommand=_w(_save_publish))
    cmds.rowLayout(numberOfColumns=2, columnWidth2=(110, 200), columnAttach=[(1, "right", 4), (2, "both", 2)])
    cmds.text(label="Guides")
    cmds.optionMenu(NP("Pub_guides"), changeCommand=_w(_save_publish),
                    annotation="hide: they stay (Back to guides still works). delete: smaller file, but no going "
                               "back to guides. leave: as they are.")
    for c in ("hide", "delete (no going back to guides)", "leave"):
        cmds.menuItem(label=c)
    cmds.optionMenu(NP("Pub_guides"), edit=True, select=1 + ["hide", "delete", "leave"].index(po["guides"]))
    cmds.setParent("..")
    ui.row(2, 170)
    cmds.button(label="Publish", height=28, backgroundColor=ui.MAIN_BG, command=_w(_guard(publish_rig)),
                annotation="Clean the built rig for animators (one undo). Unpublish puts it back.")
    cmds.button(label="Unpublish", height=28, command=_w(_guard(unpublish_rig)),
                annotation="Put back everything Publish changed (not deleted guides).")
    cmds.setParent("..")
    cmds.button(label="Deliver to animators...", height=26, command=_w(_guard(_deliver)),
                annotation="One folder: the published rig, the animator tools with your naming, the rig check and "
                           "a README (optionally zipped). Your scene stays as it is.")
    ui.end_section()


def build(prefix="p_publish_"):
    """Publish on its own page (5.7.6: the new window's Check & publish > Publish). Build's own functions run
    as usual; only the Publish fields live here."""
    _PUB["p"] = prefix
    keep = _P["p"]
    _P["p"] = prefix
    try:
        _publish_part(collapse=False)
    finally:
        _P["p"] = keep


build_publish_panel = build              # (its 5.7.6 name)
