# line icons (24x24, stroke) instead of emoji
IC = {
 "spine": '<circle cx="12" cy="4" r="2"/><rect x="9" y="8" width="6" height="3" rx="1"/><rect x="9" y="13" width="6" height="3" rx="1"/><rect x="9" y="18" width="6" height="3" rx="1"/>',
 "arm": '<circle cx="4" cy="6" r="2"/><circle cx="12" cy="10" r="2"/><circle cx="19" cy="17" r="2"/><path d="M6 7l4 2 M13.5 11.5l4 4"/>',
 "leg": '<circle cx="10" cy="3" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="10" cy="20" r="2"/><path d="M10.4 5l1.2 5 M11.6 14l-1.2 4 M12 20h7"/>',
 "tail": '<path d="M3 18c5 0 6-10 11-10s5 6 8 4"/><circle cx="3" cy="18" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="8" r="1.6"/><circle cx="21" cy="11" r="1.6"/>',
 "ears": '<path d="M8 21c-3-5-4-12-2-17 3 3 4 10 4 17 M16 21c0-7 1-14 4-17 2 5 1 12-2 17"/>',
 "head": '<circle cx="12" cy="10" r="7"/><path d="M9 21h6"/>',
 "bulb": '<path d="M9 18h6 M10 21h4 M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.6 1 2.5h6c0-.9.2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
 "pin": '<path d="M15 3l6 6-3 1-4 4 1 4-2 2-4-4-5 5 M9 13L5 9l2-2 4 1 4-4z"/>',
 "brush": '<path d="M18 3l3 3-9 9-3-3z M9 12c-3 0-5 2-5 5 0 1-1 2-2 2 2 2 7 2 8-1 1-2 0-4-1-6z"/>',
 "rig": '<circle cx="12" cy="4" r="2"/><path d="M12 6v8 M12 9l-6 3 M12 9l6 3 M12 14l-4 7 M12 14l4 7"/>',
}
def icon(name, size=28, color="currentColor", w=1.7):
    return ('<svg viewBox="0 0 24 24" width="%d" height="%d" fill="none" stroke="%s" stroke-width="%s" '
            'stroke-linecap="round" stroke-linejoin="round" style="display:block;margin:0 auto">%s</svg>' % (size, size, color, w, IC[name]))
