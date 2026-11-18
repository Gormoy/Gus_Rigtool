"""
Onion Skin - see-through 3D ghosts of whatever you pick, at its past / next keys or every N frames. Seen in every
camera, for several characters at once. Standalone: needs nothing but Maya 2024+ (no PyMEL).

    import onion_skin; onion_skin.show()
"""

__version__ = "1.0.0"


def show():
    from onion_skin import ui
    return ui.show()
