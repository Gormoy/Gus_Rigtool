# 3.14 navigation: Home steps from the scene, 'where am I' line, Simple / Full view, Guide pages and web page,
# every 'Go' / 'Take me there' points at a section that exists, next-step hints
exec(open("fakemaya.py").read()); exec(open("fakeui.py").read())
import os
import tempfile
from unittest import mock
for name in ("scriptJob", "headsUpDisplay", "playbackOptions", "workspace", "channelBox", "iconTextCheckBox",
             "shelfLayout", "nodeIconButton", "colorIndexSliderGrp", "canvas", "image", "palettePort",
             "attrColorSliderGrp", "swatchDisplayPort", "checkBoxGrp", "textFieldButtonGrp", "radioCollection",
             "radioButton", "iconTextRadioButton", "iconTextRadioCollection", "intSlider", "floatSlider",
             "fileDialog2", "evalDeferred", "showWindow"):
    if not hasattr(cmds, name):
        setattr(cmds, name, mock.MagicMock(return_value=1))
cmds.objectTypeUI = lambda c: (UI.get(c.split("|")[-1]) or {}).get("kind", "")
from gus_rigtool import registry
from gus_rigtool.core import ui, utils
from gus_rigtool.tools import home, guide
errors = []
ui.report_error = lambda e, where="": errors.append("%s: %s: %s" % (where, type(e).__name__, e))

print("every tool in one category:", sorted(k for c in registry.CATEGORIES for k in c[2]) ==
      sorted(t[0] for t in registry.TOOLS))
print("stage tools known:", all(registry.get(s[3]) for s in registry.STAGES))

# --- view mode: new users simple, old installs full, remembered
utils.save_setting("viewMode", None)
print("new user:", ui.view_mode())
utils.save_setting("viewMode", None); utils.save_setting("panelWidths", {"main": 400})
print("old install:", ui.view_mode())
utils.save_setting("viewMode", "simple")
print("remembered:", ui.view_mode())

# --- sections: every section title of every tool (Full view: nothing marked)
def titles(key):
    _cur[0] = None
    cmds.columnLayout("root_" + key)
    ui._build_tool(key, "t_%s_" % key)
    return [v.get("label") for k, v in UI.items() if v.get("kind") == "frameLayout" and v.get("label")]

utils.save_setting("viewMode", "simple")
UI.clear(); _cur[0] = None
skin_titles = titles("skin")
print("simple skin sections:", skin_titles)
print("advanced ones start folded:", all(v.get("collapse") for v in UI.values()
                                         if v.get("kind") == "frameLayout" and "(advanced)" in str(v.get("label"))))
utils.save_setting("viewMode", "full")
UI.clear()
print("full skin sections:", titles("skin"))
print("plain titles:", ui._plain_title("2.  Copy skin   (advanced)"), "|", ui._plain_title("Bind"))

# every Home 'Go' and Guide 'Take me there' goes to a section that is really there
targets = [(s[3], s[4]) for s in registry.STAGES] + [(t, sec) for p in guide.PAGES for _x, t, sec in p[3] if sec]
missing = []
for tool in sorted(set(t for t, _s in targets)):
    UI.clear()
    have = [ui._plain_title(t) for t in titles(tool)]
    for t, sec in targets:
        if t == tool and not any(h == sec or h.startswith(sec) for h in have):
            missing.append((t, sec))
print("sections that don't exist:", missing or "none")

# --- where am I
for key in ("build", "skin", "shapes", "checker", "select", "home"):
    UI.clear(); _cur[0] = None; cmds.columnLayout("w_" + key)
    ui.where_line(key)
    print("where %-8s" % key, [v.get("label") for v in UI.values() if v.get("kind") in ("text", "button")])

# --- Home: empty scene -> guides next
print("state, empty scene:", home.state())
print("advice:", home.advice(home.state()[1]))
UI.clear(); _cur[0] = None; cmds.columnLayout("home_root")
ui._build_tool("home", "m_home_")
print("home marks:", [UI["m_home_Mark%d" % i].get("label") for i in range(len(registry.STAGES))])
print("home go buttons:", [UI["m_home_Go%d" % i].get("label") for i in range(len(registry.STAGES))])
# scene states, faked
for g, b, s, p in ((1, 0, 0, 0), (1, 1, 0, 0), (1, 1, 1, 0), (1, 1, 1, 1)):
    with mock.patch.object(home, "_guides_done", return_value=bool(g)), \
            mock.patch.object(home, "_built", return_value=bool(b)), \
            mock.patch.object(home, "_skinned", return_value=bool(s)), \
            mock.patch.object(home, "_published", return_value=bool(p)):
        st, nxt = home.state()
        print("guides %d built %d skinned %d published %d ->" % (g, b, s, p), [st[k[0]] for k in registry.STAGES],
              "next:", nxt)
        print("   status line:", home.say_next("Build", "done."))
        print("   home marks:", [UI["m_home_Mark%d" % i].get("label") for i in range(len(registry.STAGES))])

# --- Guide window and web page
UI.clear(); _cur[0] = None
cmds.window = lambda *a, **k: False if k.get("exists") else (a[0] if a else "win")
guide.show()
print("guide page 1:", UI[guide.BODY] and [v.get("label") for v in UI.values()
                                           if v.get("kind") == "text" and v.get("parent", "").endswith(guide.BODY)][:2])
guide.page(3)
print("guide page 4 buttons:", sum(1 for v in UI.values() if v.get("label") == "Take me there" and v.get("parent") in
                                     (cmds.columnLayout(guide.BODY, query=True, childArray=True) or [])),
      "| back on:", UI[guide.WIN + "Back"].get("enable"), "| next on:", UI[guide.WIN + "Next"].get("enable"))
guide.page(99)
print("past the end -> last page:", guide._page["i"] == len(guide.PAGES) - 1, "| next on:",
      UI[guide.WIN + "Next"].get("enable"))
path = os.path.join(tempfile.mkdtemp(), "guide.html")
guide.export_html(path)
text = open(path).read()
print("web page: every page:", all(("id='%s'" % p[0]) in text for p in guide.PAGES),
      "| pictures:", text.count("data:image/png;base64"), "| dark mode:", "prefers-color-scheme" in text,
      "| where line:", "Skin &gt; Bind" in text)
print("errors:", errors or "none")
