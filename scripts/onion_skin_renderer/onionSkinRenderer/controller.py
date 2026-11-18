import onionSkinRenderer.mayacompat as pm   # was: import pymel.core as pm (PyMEL not needed)
import maya.cmds as cmds
import os
import json
import inspect
from PySide2 import QtWidgets, QtCore
import maya.OpenMayaUI as omui
from shiboken2 import wrapInstance
from maya.app.general.mayaMixin import MayaQWidgetDockableMixin

import onionSkinRenderer.core as core
import onionSkinRenderer.extras as extras
import onionSkinRenderer.ui_window as ui_window
import onionSkinRenderer.wdgt_Frame as wdgt_Frame
import onionSkinRenderer.wdgt_MeshListObj as wdgt_MeshListObj
import onionSkinRenderer.wdgt_Preferences as wdgt_Preferences

import onionSkinRenderer.core_clearRender as clearRender
import onionSkinRenderer.core_hudRender as hudRender
import onionSkinRenderer.core_presentTarget as presentTarget
import onionSkinRenderer.core_quadRender as quadRender
import onionSkinRenderer.core_sceneRender as sceneRender


'''
2017, 2018 and 2019 Version
using pyside2
'''

'''
Naming Conventions:
    Global variables: are in caps, seperated by "_"
    os: abbreviation for onion skin
    osr: abbreviation for onion skin renderer
'''


DEBUG_ALL = False


# wrapper to get mayas main window
def getMayaMainWindow():
    mayaPtr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(mayaPtr), QtWidgets.QMainWindow)



# global variable holding the instance of the window
OSR_WINDOW = None

# convenient function to open the osr ui
def show(develop = False, dockable = False):
    global OSR_WINDOW
    if develop:
        reload(core)
        reload(clearRender)
        reload(hudRender)
        reload(presentTarget)
        reload(quadRender)
        reload(sceneRender)
        reload(wdgt_Frame)
        reload(ui_window)	
        reload(wdgt_MeshListObj)
        reload(wdgt_Preferences)

    try:
        OSR_WINDOW.close()
    except:
        pass
    
    OSR_WINDOW = OSRController()
    # if somebody reads this because they want to make it dockable
    # please contact me. I'd like to have it dockable as well
    # but it just never works
    OSR_WINDOW.show()
    


'''
ONION SKIN RENDERER MAIN UI
This class is the main ui window. It manages all user events and links to the core
'''
class OSRController(QtWidgets.QMainWindow, ui_window.Ui_onionSkinRenderer):

    # 
    def __init__(self, parent = getMayaMainWindow()):
        super(OSRController, self).__init__(parent)
        # the dockable feature creates this control that needs to be deleted manually
        # otherwise it throws an error that this name already exists
        self.deleteControl('onionSkinRendererWorkspaceControl')
        
        # This registers the override in maya
        # I previously had it as plugin, but this made it impossible to get
        # the OSR_INSTANCE (sth to do with python namespaces i guess)
        # so i just call init myself.
        # It feels a bit hacky, but it works anyway
        core.initializeOverride()
        # member variables
        self.targetObjectsSet = set()
        self.absoluteFramesSet = set()
        self.preferences = {}
        self.relativeFrameCount = 8
        self.toolPath = os.path.dirname(os.path.abspath(inspect.stack()[0][1]))
        self.activeEditor = None

        # create the ui from the compiled qt designer file
        self.setupUi(self)

        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)

        self.createConnections()
        self.addExtras()

        # load settings from the settings file
        self.loadSettings()

    # (noPyMEL copy) a Fill button and a moving-camera warning under the Toggle button
    def addExtras(self):
        layout = self.toggleRenderer_btn.parentWidget().layout()
        self.fill_btn = QtWidgets.QPushButton("Fill onion skins (visit the frames once)")
        self.fill_btn.setMinimumSize(QtCore.QSize(40, 26))
        self.fill_btn.setToolTip("Steps through the frames the onion skins need, then back to your frame - "
                                 "so they show without scrubbing.")
        self.fill_btn.clicked.connect(self.fillLater)
        self.cameraWarning_lbl = QtWidgets.QLabel("")
        self.cameraWarning_lbl.setWordWrap(True)
        self.cameraWarning_lbl.setStyleSheet("color: rgb(255, 170, 60);")
        self.cameraWarning_lbl.hide()
        index = layout.indexOf(self.toggleRenderer_btn)
        layout.insertWidget(index + 1, self.fill_btn)
        layout.insertWidget(index + 2, self.cameraWarning_lbl)

    # the camera moves in the shot: its pictures can't line up - say so (Maya's Ghosting works in 3D)
    def checkCamera(self):
        cam = core.onionCamera()
        if cam and core.cameraMoves(cam):
            self.cameraWarning_lbl.setText(
                "%s moves (animated or constrained): onion skins are pictures of the view, so they drift with the "
                "camera. For this shot use Maya's Visualize > Ghost Selected." % cam.split("|")[-1])
            self.cameraWarning_lbl.show()
        else:
            self.cameraWarning_lbl.hide()

    # Fill runs once the click is over (heavy work inside a click can crash Maya)
    def fillLater(self):
        cmds.evalDeferred(self.fill, lowestPriority=True)

    def fill(self):
        if not core.onionPanel():
            print("onionSkinRenderer: Toggle the onion skins on in a viewport first")
            return
        try:
            core.OSR_INSTANCE.setRelativeFrames(None)     # the past / next keys as they are now
        except Exception as e:
            print(e)
        frames = core.OSR_INSTANCE.neededFrames()
        if not frames:
            print("onionSkinRenderer: no onion frames to fill - turn some on (past / next keys, or frames)")
            return
        now = cmds.currentTime(query=True)
        try:
            for f in frames:
                cmds.currentTime(f, update=True)
                cmds.refresh(force=True)
        finally:
            cmds.currentTime(now, update=True)          # always back to your frame
            cmds.refresh(force=True)
        print("onionSkinRenderer: filled %d frame(s): %s" % (len(frames), ", ".join("%g" % f for f in frames)))

    #
    def closeEvent(self, event):
        # when the UI is closed, deactivate the override
        if DEBUG_ALL: print('close event start')
        self.saveSettings()
        core.uninitializeOverride()
        if DEBUG_ALL: print('close event end')
    
    # special event for the dockable feature
    def dockCloseEventTriggered(self, event):
        if DEBUG_ALL: print('dock close event start')
        self.saveSettings()
        core.uninitializeOverride()
        if DEBUG_ALL: print('dock close event end')

    # code from https://gist.github.com/liorbenhorin/217bfb7e54c6f75b9b1b2b3d73a1a43a
    def deleteControl(self, control):
        if DEBUG_ALL: print('delete Control')
        if cmds.workspaceControl(control, q=True, exists=True):
            cmds.workspaceControl(control, e=True, close=True)
            cmds.deleteUI(control, control=True)

    #
    def createConnections(self):
        self.targetObjects_add_btn.clicked.connect(self.addSelectedToTargetObjects)
        self.targetObjects_remove_btn.clicked.connect(self.removeSelectedFromTargetObjects)
        self.targetObjects_clear_btn.clicked.connect(self.clearTargetObjects)

        self.toggleRenderer_btn.clicked.connect(self.toggleRenderer)
        self.globalOpacity_slider.sliderMoved.connect(self.setGlobalOpacity)
        self.onionType_cBox.currentTextChanged.connect(self.setOnionSkinDisplayMode)
        self.drawBehind_chkBx.stateChanged.connect(self.setDrawBehind)

        self.tint_type_cBox.currentTextChanged.connect(self.setTintType)
        self.relative_futureTint_btn.clicked.connect(self.pickColor)
        self.relative_pastTint_btn.clicked.connect(self.pickColor)
        self.relative_tint_strength_slider.sliderMoved.connect(self.setTintStrength)
        self.relative_keyframes_chkbx.clicked.connect(self.toggleRelativeKeyframeDisplay)
        self.relative_step_spinBox.valueChanged.connect(self.setRelativeStep)

        self.absolute_tint_btn.clicked.connect(self.pickColor)
        self.absolute_addCrnt_btn.clicked.connect(self.addAbsoluteTargetFrame)
        self.absolute_add_btn.clicked.connect(self.addAbsoluteTargetFrameFromSpinbox)
        self.absolute_clear_btn.clicked.connect(self.clearAbsoluteTargetFrames)

        self.settings_clearBuffer.triggered.connect(self.clearBuffer)
        self.settings_autoClearBuffer.triggered.connect(self.setAutoClearBuffer)
        self.settings_preferences.triggered.connect(self.changePrefs)
        self.settings_saveSettings.triggered.connect(self.saveSettings)

        self.targetObjects_grp.clicked.connect(self.toggleGroupBox)
        self.onionSkinFrames_grp.clicked.connect(self.toggleGroupBox)
        self.onionSkinSettings_grp.clicked.connect(self.toggleGroupBox)



    # ------------------
    # UI REFRESH

    # 
    def refreshObjectList(self):
        self.targetObjects_list.clear()
        for obj in self.targetObjectsSet:
            listWidget = TargetObjectListWidget()
            listWidget.object_label.setText(obj.nodeName())
            listWidget.object_remove_btn.clicked.connect(lambda _=None,b_obj = obj: self.removeTargetObject(b_obj))
            listItem = QtWidgets.QListWidgetItem()
            listItem.setSizeHint(listWidget.sizeHint())
            self.targetObjects_list.addItem(listItem)
            self.targetObjects_list.setItemWidget(listItem, listWidget)

    # 
    def refreshRelativeFrame(self):
        activeFrames = []
        # clear the frame of all widgets first
        for child in self.relative_frame.findChildren(OnionListFrame):
            if child.frame_visibility_btn.isChecked():
                activeFrames.append(int(child.frame_number.text()))
            child.setParent(None)
        
        # fill the relative frames list
        for index in range(self.relativeFrameCount + 1):
            if not index-self.relativeFrameCount/2 == 0:
                listWidget = OnionListFrame()
                frame = index-self.relativeFrameCount/2
                listWidget.frame_number.setText(str(int(frame)))
                listWidget.frame_opacity_slider.setValue(75/abs(index-self.relativeFrameCount/2))
                listWidget.frame_visibility_btn.toggled.connect(self.toggleRelativeTargetFrame)
                if frame in activeFrames: 
                    listWidget.frame_visibility_btn.setChecked(True)
                    activeFrames.remove(frame)
                listWidget.frame_opacity_slider.sliderMoved.connect(self.setOpacityForRelativeTargetFrame)
                self.relative_frame_layout.addWidget(listWidget)

        # remove all remaining frames from onion skin renderer
        # since their visibility is no longer accesible from ui
        for frame in activeFrames:
            core.OSR_INSTANCE.removeRelativeOnion(frame)

    # 
    def refreshAbsoluteFrameTargetsList(self):
        # remove any entries that don't exist anymore
        framesInList = []
        for i in reversed(range(self.absolute_list.count())):
            frame = self.absolute_list.item(i).data(QtCore.Qt.UserRole)
            framesInList.append(frame)
            if frame not in self.absoluteFramesSet:
                self.absolute_list.takeItem(i)
        
        # add any missing entry
        for frame in self.absoluteFramesSet:
            if frame not in framesInList:
                listWidget = OnionListFrame()
                listWidget.frame_number.setText(str(frame))
                listWidget.frame_opacity_slider.setValue(core.OSR_INSTANCE.getOpacityOfAbsoluteFrame(frame))
                listWidget.addRemoveButton()
                listWidget.frame_visibility_btn.setChecked(core.OSR_INSTANCE.absoluteTargetFrameExists(frame))
                listWidget.frame_remove_btn.clicked.connect(lambda _=None,b_frame = frame: self.removeAbsoluteTargetFrame(b_frame))
                listWidget.frame_visibility_btn.toggled.connect(self.toggleAbsoluteTargetFrame)
                listWidget.frame_opacity_slider.sliderMoved.connect(self.setOpacityForAbsoluteTargetFrame)
                listItem = QtWidgets.QListWidgetItem()
                listItem.setData(QtCore.Qt.UserRole, frame)
                listItem.setSizeHint(listWidget.sizeHint())
                # insert item at correct position
                correctRow = 0
                for i in range(self.absolute_list.count()):
                    if frame < self.absolute_list.item(i).data(QtCore.Qt.UserRole):
                        break
                    correctRow = i+1
                
                self.absolute_list.insertItem(correctRow, listItem)
                self.absolute_list.setItemWidget(listItem, listWidget)




    # ---------------------------
    # CONNECTIONS

    # 
    def addSelectedToTargetObjects(self):
        # (noPyMEL copy) a control adds its character's meshes, a group the meshes inside it
        sel = cmds.ls(selection=True, long=True) or []
        meshes = extras.meshes_for(sel)
        if not meshes:
            print("onionSkinRenderer: no visible meshes found for the selection")
            return
        cmds.select(meshes, replace=True)
        try:
            core.OSR_INSTANCE.addSelectedTargetObject()
        finally:
            if sel:
                cmds.select(sel, replace=True)
            else:
                cmds.select(clear=True)
        for m in meshes:
            self.targetObjectsSet.add(pm.Node(m))
        self.refreshObjectList()
        print("onionSkinRenderer: added %d mesh(es)" % len(meshes))
    
    # 
    def removeSelectedFromTargetObjects(self):
        core.OSR_INSTANCE.removeSelectedTargetObject()
        for obj in pm.selected():
            if obj in self.targetObjectsSet:
                self.targetObjectsSet.remove(obj)
        self.refreshObjectList()

    #
    def removeTargetObject(self, obj):
        try:
            core.OSR_INSTANCE.removeTargetObject(obj.fullPath())
        except:
            core.OSR_INSTANCE.removeTargetObject(obj.nodeName())
        self.targetObjectsSet.remove(obj)
        self.refreshObjectList()

    #
    def clearTargetObjects(self):
        core.OSR_INSTANCE.clearTargetObjects()
        self.targetObjectsSet.clear()
        self.refreshObjectList()

    # 
    def toggleRelativeTargetFrame(self):
        sender = self.sender()
        frame = sender.parent().findChild(QtWidgets.QLabel, 'frame_number').text()
        sliderValue = sender.parent().findChild(QtWidgets.QSlider, 'frame_opacity_slider').value()
        if sender.isChecked():
            core.OSR_INSTANCE.addRelativeTargetFrame(frame, sliderValue)
        else:
            core.OSR_INSTANCE.removeRelativeTargetFrame(frame)

    #
    def toggleRelativeKeyframeDisplay(self):
        sender = self.sender()
        core.OSR_INSTANCE.setRelativeDisplayMode(self.sender().isChecked())
        self.saveSettings()

    # 
    def addAbsoluteTargetFrame(self, **kwargs):
        frame = kwargs.setdefault('frame', int(pm.animation.getCurrentTime()))
        if frame not in self.absoluteFramesSet:
            core.OSR_INSTANCE.addAbsoluteTargetFrame(frame, 50)
            self.absoluteFramesSet.add(frame)
            self.refreshAbsoluteFrameTargetsList()

    #
    def addAbsoluteTargetFrameFromSpinbox(self):
        frame = self.sender().parent().findChild(QtWidgets.QSpinBox, 'absolute_add_spinBox').value()
        self.addAbsoluteTargetFrame(frame = frame)

    #
    def toggleAbsoluteTargetFrame(self):
        sender = self.sender()
        frame = sender.parent().findChild(QtWidgets.QLabel, 'frame_number').text()
        sliderValue = sender.parent().findChild(QtWidgets.QSlider, 'frame_opacity_slider').value()
        if sender.isChecked():
            core.OSR_INSTANCE.addAbsoluteTargetFrame(frame, sliderValue)
        else:
            core.OSR_INSTANCE.removeAbsoluteTargetFrame(frame)
    
    #
    def removeAbsoluteTargetFrame(self, frame):
        core.OSR_INSTANCE.removeAbsoluteTargetFrame(frame)
        self.absoluteFramesSet.remove(frame)
        self.refreshAbsoluteFrameTargetsList()

    #
    def clearAbsoluteTargetFrames(self):
        core.OSR_INSTANCE.clearAbsoluteTargetFrames()
        self.absoluteFramesSet.clear()
        self.refreshAbsoluteFrameTargetsList()

    # 
    def clearBuffer(self):
        core.OSR_INSTANCE.clearOnionSkinBuffer()

    # 
    def pickColor(self):
        color = QtWidgets.QColorDialog.getColor()
        if color.isValid():
            self.setOnionSkinColor(self.sender(), color.getRgb())
        self.saveSettings()

    #
    def setOpacityForRelativeTargetFrame(self):
        opacity = self.sender().value()
        frame = self.sender().parent().findChild(QtWidgets.QLabel, 'frame_number').text()
        core.OSR_INSTANCE.setOpacityForRelativeTargetFrame(frame, opacity)

    #
    def setOpacityForAbsoluteTargetFrame(self):
        opacity = self.sender().value()
        frame = self.sender().parent().findChild(QtWidgets.QLabel, 'frame_number').text()
        core.OSR_INSTANCE.setOpacityForAbsoluteTargetFrame(int(frame), opacity)

    # 
    def setTintStrength(self):
        core.OSR_INSTANCE.setTintStrength(
            self.sender().value()
        )

    # 
    def setAutoClearBuffer(self):
        value = self.sender().isChecked()
        core.OSR_INSTANCE.setAutoClearBuffer(value)

    #
    def changePrefs(self):
        prefUi = PreferencesWindow(self)
        if prefUi.exec_():
            values = prefUi.getValues()
            core.OSR_INSTANCE.setMaxBuffer(values['maxBuffer'])
            core.OSR_INSTANCE.setOutlineWidth(values['outlineWidth'])
            core.OSR_INSTANCE.setTintSeed(values['tintSeed'])
            self.relativeFrameCount = values['relativeKeyCount']*2
            self.refreshRelativeFrame()
            self.saveSettings()
            
    #     
    def setRelativeStep(self):
        core.OSR_INSTANCE.setRelativeStep(self.sender().value())
        self.saveSettings()     

    # togle active or saved editor between onion Skin Renderer and vp2
    def toggleRenderer(self):
        # (noPyMEL copy) the viewport you last clicked in gets the onion skins - not always the first one found -
        # others are switched off, and the old pictures are cleared: they were taken from another view
        panel = cmds.getPanel(withFocus=True)
        if not panel or cmds.getPanel(typeOf=panel) != "modelPanel":
            visible = [p for p in cmds.getPanel(visiblePanels=True) or [] if cmds.getPanel(typeOf=p) == "modelPanel"]
            panel = visible[0] if visible else None
        if not panel:
            print("onionSkinRenderer: click in the viewport you want first")
            return
        editor = pm.uitypes.ModelEditor(panel)
        try:
            core.OSR_INSTANCE.clearOnionSkinBuffer(False)
        except Exception as e:
            print(e)
        try:
            if editor.getRendererOverrideName() == 'onionSkinRenderer':
                editor.setRendererOverrideName('')
            else:
                for other in cmds.getPanel(type="modelPanel") or []:
                    if other != panel:
                        o = pm.uitypes.ModelEditor(other)
                        if o.getRendererOverrideName() == 'onionSkinRenderer':
                            o.setRendererOverrideName('')
                editor.setRendererOverrideName('onionSkinRenderer')
            self.activeEditor = editor
            self.checkCamera()
        except Exception as e:
            print(e)


    # 
    def setGlobalOpacity(self):
        core.OSR_INSTANCE.setGlobalOpacity(self.sender().value())

    #
    def setOnionSkinDisplayMode(self):
        core.OSR_INSTANCE.setOnionSkinDisplayMode(self.onionType_cBox.currentIndex())

    #
    def setDrawBehind(self):
        core.OSR_INSTANCE.setDrawBehind(self.drawBehind_chkBx.isChecked())

    #
    def toggleGroupBox(self):
        h = self.sender().maximumHeight()

        if h > 100000:
            self.sender().setMaximumHeight(14)
        else:
            self.sender().setMaximumHeight(200000)

    #
    def setTintType(self):
        tintType = self.tint_type_cBox.currentIndex()
        if tintType == 0:
            self.constant_col_widget.setMaximumHeight(16777215)
            self.constant_col_widget.setEnabled(True)
        else:
            self.constant_col_widget.setMaximumHeight(0)    
            self.constant_col_widget.setEnabled(False)
        core.OSR_INSTANCE.setTintType(tintType)

            
            



    # UTILITY
    # 
    def setOnionSkinColor(self, btn, rgba):
            btn.setStyleSheet('background-color: rgb(%s,%s,%s);'%(rgba[0], rgba[1], rgba[2]))
            core.OSR_INSTANCE.setTint(rgba, btn.objectName())

    #
    def loadSettings(self):
        with open(os.path.join(self.toolPath,'settings.txt')) as json_file:  
            self.preferences = json.load(json_file)
            self.settings_autoClearBuffer.setChecked(self.preferences.setdefault('autoClearBuffer',True))
            core.OSR_INSTANCE.setAutoClearBuffer(self.preferences.setdefault('autoClearBuffer',True))

            self.relative_keyframes_chkbx.setChecked(self.preferences.setdefault('displayKeyframes',True))
            core.OSR_INSTANCE.setRelativeDisplayMode(self.preferences.setdefault('displayKeyframes',True))

            self.setOnionSkinColor(self.relative_futureTint_btn, self.preferences.setdefault('rFutureTint',[0,0,125]))
            self.setOnionSkinColor(self.relative_pastTint_btn, self.preferences.setdefault('rPastTint',[0,125,0]))
            self.setOnionSkinColor(self.absolute_tint_btn, self.preferences.setdefault('aTint', [125,0,0]))
            core.OSR_INSTANCE.setTintSeed(self.preferences.setdefault('tintSeed', 0))
            self.tint_type_cBox.setCurrentIndex(self.preferences.setdefault('tintType',0))


            self.onionType_cBox.setCurrentIndex(self.preferences.setdefault('onionType',1))
            self.drawBehind_chkBx.setChecked(self.preferences.setdefault('drawBehind', False))

            self.relativeFrameCount = self.preferences.setdefault('relativeFrameAmount',8)
            self.refreshRelativeFrame()
            activeRelativeFrames = self.preferences.setdefault('activeRelativeFrames',[])
            for child in self.relative_frame.findChildren(OnionListFrame):
                if int(child.frame_number.text()) in activeRelativeFrames:
                    child.frame_visibility_btn.setChecked(True)

            self.relative_step_spinBox.setValue(self.preferences.setdefault('relativeStep', 1))

            core.OSR_INSTANCE.setMaxBuffer(self.preferences.setdefault('maxBufferSize', 200))
            core.OSR_INSTANCE.setOutlineWidth(self.preferences.setdefault('outlineWidth',3))

    
    # save values into a json file
    def saveSettings(self):
        if DEBUG_ALL: print('start save')
        data = {}
        data['autoClearBuffer'] = self.settings_autoClearBuffer.isChecked()
        data['displayKeyframes'] = self.relative_keyframes_chkbx.isChecked()
        data['rFutureTint'] = self.extractRGBFromStylesheet(self.relative_futureTint_btn.styleSheet())
        data['rPastTint'] = self.extractRGBFromStylesheet(self.relative_pastTint_btn.styleSheet())
        data['aTint'] = self.extractRGBFromStylesheet(self.absolute_tint_btn.styleSheet())
        data['tintSeed'] = core.OSR_INSTANCE.getTintSeed()
        data['tintType'] = self.tint_type_cBox.currentIndex()
        data['relativeFrameAmount'] = self.relativeFrameCount
        data['relativeStep'] = self.relative_step_spinBox.value()
        data['maxBufferSize'] = core.OSR_INSTANCE.getMaxBuffer()
        data['outlineWidth'] = core.OSR_INSTANCE.getOutlineWidth()
        data['onionType'] = self.onionType_cBox.currentIndex()
        data['drawBehind'] = self.drawBehind_chkBx.isChecked()
        data['activeRelativeFrames'] = self.getActiveRelativeFrameIndices()

        with open(os.path.join(self.toolPath,'settings.txt'), 'w') as outfile:  
            json.dump(data, outfile)
        if DEBUG_ALL: print('end save')
        
    # 
    def extractRGBFromStylesheet(self, s):
        return list(map(int,(s[s.find("(")+1:s.find(")")]).split(',')))

    def getActiveRelativeFrameIndices(self):
        activeFrames = []
        # clear the frame of all widgets first
        for child in self.relative_frame.findChildren(OnionListFrame):
            if child.frame_visibility_btn.isChecked():
                activeFrames.append(int(child.frame_number.text()))
        return activeFrames





'''
FRAME WIDGET
the widget for displaying a frame in a list. includes visibility, opacity slider
and on demand a remove button   
'''
class OnionListFrame(QtWidgets.QWidget, wdgt_Frame.Ui_onionSkinFrame_layout):
    def __init__(self, parent = getMayaMainWindow()):
        super(OnionListFrame, self).__init__(parent)
        self.setupUi(self)

    def addRemoveButton(self):
        self.frame_remove_btn = QtWidgets.QPushButton('rm')
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Minimum)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.frame_remove_btn.sizePolicy().hasHeightForWidth())
        self.frame_remove_btn.setSizePolicy(sizePolicy)
        self.frame_remove_btn.setMinimumSize(QtCore.QSize(16, 16))
        self.frame_remove_btn.setMaximumSize(QtCore.QSize(16, 16))
        self.frame_widget_layout.addWidget(self.frame_remove_btn)
        


'''
OBJECT WIDGET
the widget for displaying an object in a list
'''
class TargetObjectListWidget(QtWidgets.QWidget, wdgt_MeshListObj.Ui_onionSkinObject_layout):
    def __init__(self, parent = getMayaMainWindow()):
        super(TargetObjectListWidget, self).__init__(parent)
        self.setupUi(self)



'''
Settings Dialog
in this window the user can set some preferences
'''
class PreferencesWindow(QtWidgets.QDialog, wdgt_Preferences.Ui_onionSkinRendererPreferences):
    def __init__(self, parent):
        super(PreferencesWindow, self).__init__(parent)
        self.setupUi(self)
        self.relativeKeyCount_spinBox.setValue(parent.relativeFrameCount/2)
        self.maxBuffer_spinBox.setValue(core.OSR_INSTANCE.getMaxBuffer())
        self.outlineWidth_spinBox.setValue(core.OSR_INSTANCE.getOutlineWidth())
        self.tintSeed_spinBox.setValue(core.OSR_INSTANCE.getTintSeed())

    def getValues(self):
        values = {}
        values['maxBuffer'] = self.maxBuffer_spinBox.value()
        values['relativeKeyCount'] = self.relativeKeyCount_spinBox.value()
        values['outlineWidth'] = self.outlineWidth_spinBox.value()
        values['tintSeed'] = self.tintSeed_spinBox.value()
        return values