"""Qt for Review Notes' window: PySide2 (Maya 2024 and older), PySide6 if that's what Maya has (as the onion skin)."""
try:
    from PySide2 import QtCore, QtGui, QtWidgets          # noqa: F401
    import shiboken2 as shiboken                           # noqa: F401
except ImportError:                                        # pragma: no cover - Maya 2025+
    from PySide6 import QtCore, QtGui, QtWidgets           # noqa: F401
    import shiboken6 as shiboken                           # noqa: F401


def maya_main_window():
    """Maya's main window (the parent of our window), or None outside Maya."""
    try:
        import maya.OpenMayaUI as omui
        ptr = omui.MQtUtil.mainWindow()
        if ptr:
            return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
    except Exception:
        pass
    return None
