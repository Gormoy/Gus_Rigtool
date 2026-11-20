"""
Gus_Rigtool 5.7 - the new window (Qt): a sidebar with the rig's steps, a colour per area, cards, the next step.

    import gus_rigtool.main as gr; gr.show()        # the new window (Toolbox > Settings > Window: the old one)

How the pages are made: a page's own build() (the same code the old window runs) is recorded, then drawn in the
new look (render.py); every button and field keeps its name, so the tool's functions read and change them exactly
as before (proxy.py routes those names to the new widgets). Nothing a page does is written twice.
"""
