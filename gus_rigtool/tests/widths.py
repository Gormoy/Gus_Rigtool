# shared by test_page_widths: build every page with the fake UI and estimate how wide each one needs to be
CH = 7                                   # px per character (Maya's UI font, about)
def _kids(name):
    return [n for n, v in UI.items() if v.get("parent") == name]
def _label_w(v):
    lab = v.get("label")
    return max(len(x) for x in str(lab).split("\n")) * CH + 16 if lab else 0
def need(name, out=None):
    """Smallest width the control needs (px); records culprits [(width, kind, name, why)]."""
    v = UI.get(name) or {}
    kind = v.get("kind")
    kids = _kids(name)
    w = 0
    why = ""
    if kind == "rowLayout":
        cw = {}
        for key in ("columnWidth",):
            for c in v.get(key) or []:
                cw[c[0]] = c[1]
        for i in range(2, 7):
            vals = v.get("columnWidth%d" % i)
            if vals:
                for j, x in enumerate(vals):
                    cw[j + 1] = x
        adj = v.get("adjustableColumn")
        tot = 0
        for i, k in enumerate(kids):
            kw = need(k, out)
            fixed = cw.get(i + 1)
            if fixed is not None and (adj != i + 1):
                tot += max(fixed, 0)
            else:
                tot += kw
        w, why = tot, "row %s" % sorted(cw.items())
    elif kind == "rowColumnLayout":
        cols = v.get("columnWidth") or []
        w, why = sum(c[1] for c in cols) + 10, "grid %s" % cols
        n = int(v.get("numberOfColumns") or 1)
        if not cols:
            w = sum(need(k, out) for k in kids[:n])
    elif kind in ("columnLayout", "frameLayout", "scrollLayout", "formLayout", "tabLayout", "gridLayout",
                  "flowLayout", None):
        w = max([need(k, out) for k in kids] + [0])
        if kind == "frameLayout":
            w += 12
        if v.get("width") and not v.get("adjustableColumn"):
            w = max(w, v.get("width"))
    elif kind == "text":
        if v.get("wordWrap"):
            w = v.get("width") or 0
        else:
            w = v.get("width") or _label_w(v)
            why = "text %r" % str(v.get("label"))[:60]
    elif kind in ("button", "checkBox", "iconTextButton", "symbolButton"):
        w = v.get("width") or _label_w(v) + (14 if kind == "checkBox" else 0)
        why = "%s %r" % (kind, str(v.get("label"))[:60])
    elif kind in ("radioButtonGrp", "floatSliderGrp", "intSliderGrp", "textFieldGrp", "floatFieldGrp",
                  "intFieldGrp", "optionMenuGrp", "colorSliderGrp", "checkBoxGrp"):
        ws = [x for k2, x in v.items() if k2.startswith("columnWidth") and isinstance(x, (list, tuple))
              for x in ([x] if isinstance(x, int) else x) if isinstance(x, int)]
        w = sum(ws) if ws else 250
        why = "%s %s" % (kind, ws)
    else:
        w = v.get("width") or 60
    if out is not None and why:
        out.append((w, kind, name, why))
    return w
