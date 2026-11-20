"""Qt for Maya 2024 (PySide2) and Maya 2025+ (PySide6)."""
try:
    from PySide6 import QtCore, QtGui, QtWidgets          # noqa: F401
    from PySide6 import QtSvg                              # noqa: F401
    import shiboken6 as shiboken                           # noqa: F401
    QT6 = True
except ImportError:
    from PySide2 import QtCore, QtGui, QtWidgets          # noqa: F401
    from PySide2 import QtSvg                              # noqa: F401
    import shiboken2 as shiboken                           # noqa: F401
    QT6 = False


def maya_widget(name, kind="layout"):
    """The Qt widget of a Maya UI control / layout (by its name), or None."""
    try:
        import maya.OpenMayaUI as omui
    except ImportError:
        return None
    ptr = {"layout": omui.MQtUtil.findLayout, "control": omui.MQtUtil.findControl,
           "window": omui.MQtUtil.findWindow}[kind](name)
    if not ptr:
        return None
    return shiboken.wrapInstance(int(ptr), QtWidgets.QWidget)
