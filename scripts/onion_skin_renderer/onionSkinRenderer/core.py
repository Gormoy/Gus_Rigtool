import maya.api.OpenMaya as om
import maya.cmds as cmds
import onionSkinRenderer.extras as extras
import onionSkinRenderer.arcs as arcs
import maya.api.OpenMayaRender as omr
import maya.api.OpenMayaAnim as oma
import maya.api.OpenMayaUI as omui
import os
import inspect
import traceback
import collections

import onionSkinRenderer.core_clearRender as clearRender
import onionSkinRenderer.core_hudRender as hudRender
import onionSkinRenderer.core_presentTarget as presentTarget
import onionSkinRenderer.core_quadRender as quadRender
import onionSkinRenderer.core_sceneRender as sceneRender



"""
This code is a render override for displaying onion skin overlays in the 3D viewport
It uses render targets to store the rendered onion skins. Unfortunately as of now it
doesn't interactively update the onion skins on the fly. Instead it just saves the onion skin
of the current frame and displays a saved onion skin from a different frame if available.
"""





"""
Constants & Debug Variables
When something goes wrong, turning these on will
dump info in the script editor
"""
DEBUG = False
PLUGIN_NAME = "Onion Skin Renderer"


"""
Tells maya to use the new api
"""
def maya_useNewAPI():
    pass





# globally available instance of renderer
OSR_INSTANCE = None



'''
Initialize the plugin

This manually registers the osr as a plugin in maya.
Several reasons to do this
- some studios don't allow users to add stuff to their C drive
- convenience, it is a lot easier for users to copy a folder to their scripts directory and be done
- as a plugin I can't get to the OSR_INSTANCE (sth to do with python namespaces i guess)

It feels a bit hacky, but it works anyway

However the downside is that if the tool crashes or for some other reason
doesn't finish the unitializeOverride() function, you need to restart maya for it to work again
'''

def initializeOverride():
    if DEBUG: print('initialize Renderer')
    try:
        # register the path to the plugin
        omr.MRenderer.getShaderManager().addShaderPath(os.path.dirname(os.path.abspath(inspect.stack()[0][1])))
        global OSR_INSTANCE
        OSR_INSTANCE = ViewRenderOverride("onionSkinRenderer")
        OSR_INSTANCE.createCallbacks()
        omr.MRenderer.registerOverride(OSR_INSTANCE)
    except:
        traceback.print_exc()
        raise Exception("Failed to register plugin %s" %PLUGIN_NAME)
        

# un-init
def uninitializeOverride():
    if DEBUG: print('unitiliazide Renderer')
    try:
        global OSR_INSTANCE
        if OSR_INSTANCE is not None:
            omr.MRenderer.deregisterOverride(OSR_INSTANCE)
            OSR_INSTANCE.deleteCallbacks()
            OSR_INSTANCE.__del__()
            OSR_INSTANCE = None
    except:
        traceback.print_exc()
        raise Exception("Failed to unregister plugin %s" % PLUGIN_NAME)
        





"""
This is the main class for the render overide.
The main thing it does is handling inputs from the controller and rendering the passes.
Think of passes as photoshop layers getting merged and then sent to the screen.
The class holds all the buffered onion skins.
The onion skins are rendered on top of the normal viewport, one after the other.
So there is a render pass for each displayed onion skin
"""
# (noPyMEL copy) helpers -------------------------------------------------------------------------------------
def onionPanel():
    """The viewport that shows the onion skins, or None."""
    try:
        for p in cmds.getPanel(type="modelPanel") or []:
            if cmds.modelEditor(p, query=True, rendererOverrideName=True) == "onionSkinRenderer":
                return p
    except Exception:
        pass
    return None


def onionCamera():
    """The camera of the viewport that shows the onion skins (long name), or None."""
    p = onionPanel()
    if not p:
        return None
    try:
        cam = cmds.modelEditor(p, query=True, camera=True)
        return (cmds.ls(cam, long=True) or [cam])[0]
    except Exception:
        return None


def cameraMoves(cam):
    """True when the camera (or anything above it) is animated or driven: its onion pictures can't line up."""
    if not cam or not cmds.objExists(cam):
        return False
    node = cam
    if cmds.nodeType(node) == "camera":
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [node])[0]
    while node:
        for a in ("translate", "rotate", "translateX", "translateY", "translateZ", "rotateX", "rotateY", "rotateZ"):
            if cmds.listConnections(node + "." + a, source=True, destination=False):
                return True
        node = (cmds.listRelatives(node, parent=True, fullPath=True) or [None])[0]
    return False


MAX_GHOSTS = 12
FAINT = 0.15                # "only the one I'm animating": the others' ghosts at this much


class Character(object):
    """One character on the onion skin: its picture pass (draws only its meshes), its ghosts (index -> blend
    pass), its pinned ghosts (frame -> blend pass) and its light table pass."""

    def __init__(self, owner, key, names, ghosts, serial):
        self.key = key
        self.names = list(names)
        self.showGhosts = bool(ghosts)
        self.serial = serial
        self.owner = owner
        sel = om.MSelectionList()
        for n in self.names:
            try:
                sel.add(n)
            except Exception:
                pass
        self.objects = owner.flattenSelectionList(sel)
        self.capture = sceneRender.OSSceneRender("onionCapture%d" % serial, omr.MClearOperation.kClearAll)
        self.capture.setSceneFilter(omr.MSceneRender.kRenderShadedItems)
        self.capture.setDrawSelectionFilter(True)
        self.capture.setObjectFilterList(self.objects)
        self.ghosts = {}
        self.pinned = {}
        self.wash = None

    def quad(self, name, frame):
        q = quadRender.OSQuadRender("%s_%d_%s" % (name, self.serial, frame), omr.MClearOperation.kClearNone,
                                    int(frame), self.owner)
        q.hasKey = True
        return q


class ViewRenderOverride(omr.MRenderOverride):
    """The onion skin's drawing. Every screen refresh: the normal view, then a picture of each onion character
    alone (kept per frame), then - light table - the other characters made see-through, then each character's
    ghosts blended on top, then the HUD (arcs) and the result on screen."""

    def __init__(self, name):
        super(ViewRenderOverride, self).__init__(name)
        self.UIName = PLUGIN_NAME
        self.operation = 0
        self.currentFrame = 0

        # pictures: frame -> {character key: [target, name]} (all characters are photographed together)
        self.onionSkinBuffer = {}
        self.onionSkinBufferQueue = collections.deque()
        self.maxOnionSkinBufferSize = 200
        self._serial = 0

        self.characters = []                 # [Character]
        self.ghostOpacity = {}               # ghost index (-2, -1, 1...) -> its opacity in %
        self.pinnedFrames = {}               # frame -> opacity in %
        self.absoluteBlendPasses = self.pinnedFrames     # (old name)
        self.relativeStep = 1
        self.relativeKeyDisplay = True
        self.mainKeysOnly = False
        self._keysCache = {}

        self.relativeFutureTint = [255, 130, 20]
        self.relativePastTint = [40, 120, 255]
        self.absoluteTint = [125, 0, 0]
        self.tintStrength = 1.0
        self.globalOpacity = 1.0
        self.onionSkinDisplayType = 0
        self.outlineWidth = 3
        self.drawBehind = 0                  # in front of the character, like Toon Boom Harmony
        self.fade = 0.6

        # light table: the characters you're not animating, see-through
        self.lightTable = False
        self.lightStrength = 0.5
        self.activeKey = None
        self.onlyActive = False
        self.lightBackground = om.MSelectionList()

        self.lastView = None
        self.hideWhilePlaying = True
        self.opsThisFrame = None
        self.arcs = arcs.Arcs()
        self.animEditedCallbackId = None
        self.timeCallbackId = 0
        self.cameraMovedCallbackIds = []
        self.autoClearBuffer = True

        # fixed passes
        self.clearPass = clearRender.viewRenderClearRender("clearPass")
        self.clearPass.setOverridesColors(False)
        self.standardPass = sceneRender.OSSceneRender("standardPass", omr.MClearOperation.kClearNone)
        self.HUDPass = hudRender.viewRenderHUDRender(self)
        self.presentTarget = presentTarget.viewRenderPresentTarget("presentTarget")
        self.bgClear = clearRender.viewRenderClearRender("lightTableClear")
        self.bgClear.setOverridesColors(False)
        self.bgPass = sceneRender.OSSceneRender("lightTableBackground", omr.MClearOperation.kClearNone)
        self.bgPass.setDrawSelectionFilter(True)
        self.renderOperations = [self.clearPass, self.standardPass, self.HUDPass, self.presentTarget]

        # targets
        self.standardTargetDescr = omr.MRenderTargetDescription()
        self.standardTargetDescr.setName("standardTarget")
        self.standardTargetDescr.setRasterFormat(omr.MRenderer.kR8G8B8A8_UNORM)
        self.blendTargetDescr = omr.MRenderTargetDescription()
        self.blendTargetDescr.setName("onionTarget")
        self.blendTargetDescr.setRasterFormat(omr.MRenderer.kR8G8B8A8_UNORM)
        self.bgTargetDescr = omr.MRenderTargetDescription()
        self.bgTargetDescr.setName("lightTableTarget")
        self.bgTargetDescr.setRasterFormat(omr.MRenderer.kR8G8B8A8_UNORM)

        self.targetMgr = omr.MRenderer.getRenderTargetManager()
        self.standardTarget = self.targetMgr.acquireRenderTarget(self.standardTargetDescr)
        self.bgTarget = None
        for p in (self.clearPass, self.standardPass, self.HUDPass, self.presentTarget):
            p.setRenderTarget(self.standardTarget)

    def __del__(self):
        self.clearPass = self.standardPass = self.HUDPass = self.presentTarget = None
        self.bgClear = self.bgPass = None
        self.renderOperations = None
        self.characters = []
        self.clearOnionSkinBuffer(False)
        if self.targetMgr:
            for t in (self.standardTarget, self.bgTarget):
                if t:
                    self.targetMgr.releaseRenderTarget(t)
        self.standardTarget = self.bgTarget = None
        self.targetMgr = None

    # ------------------------------------------------------------------ drawing
    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def setup(self, destination):
        w, h = omr.MRenderer.outputTargetSize()[:2]
        for d in (self.standardTargetDescr, self.blendTargetDescr, self.bgTargetDescr):
            d.setWidth(w)
            d.setHeight(h)
        # another camera or viewport size: the old pictures don't fit any more
        view = (onionCamera(), w, h)
        if self.lastView is not None and view != self.lastView:
            self.clearOnionSkinBuffer(False)
        self.lastView = view
        self.standardTarget.updateDescription(self.standardTargetDescr)
        self.currentFrame = now = oma.MAnimControl.currentTime().value

        ops = [self.clearPass, self.standardPass]
        playingHidden = self.hideWhilePlaying and oma.MAnimControl.isPlaying()
        if playingHidden or not self.characters:
            self.opsThisFrame = ops + [self.HUDPass, self.presentTarget]
            return

        # a picture of each character alone, on this frame
        current = self._pictures(now)
        for ch in self.characters:
            ch.capture.setRenderTarget(current[ch.key][0])
            ch.capture.setObjectFilterList(ch.objects)
            ops.append(ch.capture)

        # light table: the others see-through (blended towards the scene drawn without them)
        if self.lightTableOn():
            if self.bgTarget is None:
                self.bgTarget = self.targetMgr.acquireRenderTarget(self.bgTargetDescr)
            else:
                self.bgTarget.updateDescription(self.bgTargetDescr)
            self.bgClear.setRenderTarget(self.bgTarget)
            self.bgPass.setRenderTarget(self.bgTarget)
            self.bgPass.setObjectFilterList(self.lightBackground)
            ops += [self.bgClear, self.bgPass]
            for ch in self.characters:
                if ch.key == self.activeKey:
                    continue
                if ch.wash is None:
                    ch.wash = ch.quad("lightTable", 0)
                    ch.wash.typeOverride = 3
                    ch.wash.drawBehindOverride = 0
                    ch.wash.useGlobalOpacity = False      # the ghosts' opacity isn't the light table's
                ch.wash.setActive(True)
                ch.wash.setRenderTarget(self.standardTarget)
                ch.wash.setInputTargets(self.standardTarget, self.bgTarget)
                ch.wash.setStencilTarget(current[ch.key][0])
                ch.wash.setOpacity(self.lightStrength)
                ch.wash.setTint((1.0, 1.0, 1.0, 1.0))
                ops.append(ch.wash)

        # ghosts: pinned frames, then before / after
        for ch in self.characters:
            if not ch.showGhosts:
                continue
            stencil = current[ch.key][0]
            for frame, q in sorted(ch.pinned.items()):
                pic = self._picture(frame, ch.key)
                if pic is None or frame == now:
                    continue
                self._ready(q, pic, stencil, self._tint(self.absoluteTint),
                            self.pinnedFrames.get(frame, 50) / 100.0 * self._faint(ch))
                ops.append(q)
            for idx, q in sorted(ch.ghosts.items()):
                if self.relativeKeyDisplay:
                    if not q.hasKey:
                        continue
                    frame = q.frame
                else:
                    frame = idx * self.relativeStep + now
                pic = self._picture(frame, ch.key)
                if pic is None:
                    continue
                tint = self.relativeFutureTint if frame > now else self.relativePastTint
                self._ready(q, pic, stencil, self._tint(tint), self.ghostOpacityFor(ch, idx))
                ops.append(q)
        self.opsThisFrame = ops + [self.HUDPass, self.presentTarget]

    def _ready(self, q, pic, stencil, tint, opacity):
        q.setActive(True)
        q.setRenderTarget(self.standardTarget)
        q.setInputTargets(self.standardTarget, pic)
        q.setStencilTarget(stencil)
        q.setTint(tint)
        q.setOpacity(opacity)

    def _tint(self, rgb):
        out = []
        for c in rgb[:3]:
            v = c / 255.0
            out.append(v / self.lerp(1.0, v, self.tintStrength) if v > 0 else 0.0)
        return (out[0], out[1], out[2], 1.0)

    def _faint(self, ch):
        if self.onlyActive and self.activeKey is not None and ch.key != self.activeKey:
            return FAINT
        return 1.0

    def ghostOpacityFor(self, ch, idx):
        base = self.ghostOpacity.get(idx, 50) / 100.0
        return base * (self.fade ** max(abs(idx) - 1, 0)) * self._faint(ch)

    def lightTableOn(self):
        return (self.lightTable and len(self.characters) > 1 and
                self.activeKey in [c.key for c in self.characters])

    def _picture(self, frame, key):
        got = self.onionSkinBuffer.get(frame, {}).get(key)
        return got[0] if got else None

    def _pictures(self, frame):
        """This frame's picture of every character (made, or resized to the viewport)."""
        entry = self.onionSkinBuffer.get(frame)
        if entry is None:
            entry = self.onionSkinBuffer[frame] = {}
            self.onionSkinBufferQueue.append(frame)
            while len(self.onionSkinBufferQueue) > max(self.maxOnionSkinBufferSize, 1):
                self.deleteOldestOnionSkinBuffer()
        for ch in self.characters:
            got = entry.get(ch.key)
            if got is None:
                self._serial += 1
                name = "onionTarget%d" % self._serial
                self.blendTargetDescr.setName(name)
                entry[ch.key] = [self.targetMgr.acquireRenderTarget(self.blendTargetDescr), name]
            else:
                self.blendTargetDescr.setName(got[1])
                got[0].updateDescription(self.blendTargetDescr)
        return entry

    def startOperationIterator(self):
        self.operation = 0
        return True

    def renderOperation(self):
        return self._ops()[self.operation]

    def _ops(self):
        return self.opsThisFrame if self.opsThisFrame is not None else self.renderOperations

    def nextRenderOperation(self):
        self.operation += 1
        return self.operation < len(self._ops())

    def uiName(self):
        return self.UIName

    # ------------------------------------------------------------------ pictures
    def clearOnionSkinBuffer(self, refresh=True):
        if self.targetMgr is not None:
            for entry in self.onionSkinBuffer.values():
                for target, _name in entry.values():
                    self.targetMgr.releaseRenderTarget(target)
        self.onionSkinBuffer.clear()
        self.onionSkinBufferQueue.clear()
        if refresh:
            self.refresh()

    def deleteOldestOnionSkinBuffer(self):
        frame = self.onionSkinBufferQueue.popleft()
        entry = self.onionSkinBuffer.pop(frame, {})
        if self.targetMgr is not None:
            for target, _name in entry.values():
                self.targetMgr.releaseRenderTarget(target)

    def lerp(self, start, end, factor):
        if 0 < factor < 1:
            return (factor * start) + ((1 - factor) * end)
        return start

    def neededFrames(self):
        """The frames whose pictures the ghosts need right now (Fill / auto fill visit them)."""
        now = oma.MAnimControl.currentTime().value
        frames = set()
        for ch in self.characters:
            if not ch.showGhosts:
                continue
            for idx, q in ch.ghosts.items():
                if self.relativeKeyDisplay:
                    if q.hasKey:
                        frames.add(q.frame)
                else:
                    frames.add(idx * self.relativeStep + now)
            frames.update(ch.pinned.keys())
        frames.discard(now)
        return sorted(frames)

    def countGhosts(self):
        """(ghosts showing, frames still waiting for their picture)."""
        now = oma.MAnimControl.currentTime().value
        showing = 0
        for ch in self.characters:
            if not ch.showGhosts:
                continue
            for idx, q in ch.ghosts.items():
                if self.relativeKeyDisplay and not q.hasKey:
                    continue
                frame = q.frame if self.relativeKeyDisplay else idx * self.relativeStep + now
                if self._picture(frame, ch.key) is not None:
                    showing += 1
            showing += len([f for f in ch.pinned if self._picture(f, ch.key) is not None])
        waiting = len([f for f in self.neededFrames() if f not in self.onionSkinBuffer or
                       any(c.key not in self.onionSkinBuffer[f] for c in self.characters)])
        return showing, waiting

    # ------------------------------------------------------------------ characters and ghosts
    def setCharacters(self, characters):
        """[(key, mesh names, show ghosts)] - each character gets its own pictures, keys and ghosts."""
        self.characters = []
        for key, names, ghosts in characters:
            self._serial += 1
            self.characters.append(Character(self, key, names, ghosts, self._serial))
        self._keysCache.clear()
        self.clearOnionSkinBuffer(False)
        self._rebuildGhosts()
        self.setRelativeFrames(None)
        self.refresh()

    def setGhostSlots(self, opacities):
        """{ghost index: opacity %} - the ghosts each character shows (indices with 0 % are left out)."""
        self.ghostOpacity = dict((int(i), float(v)) for i, v in opacities.items() if v > 0)
        self._rebuildGhosts()
        self.setRelativeFrames(None)
        self.refresh()

    def setPinned(self, opacities):
        """{frame: opacity %} - frames whose ghosts stay wherever you go."""
        self.pinnedFrames.clear()
        self.pinnedFrames.update(dict((int(f), float(v)) for f, v in opacities.items()))
        self._rebuildGhosts()
        self.refresh()

    def _rebuildGhosts(self):
        for ch in self.characters:
            for idx in list(ch.ghosts):
                if idx not in self.ghostOpacity:
                    ch.ghosts.pop(idx)
            for idx in self.ghostOpacity:
                if idx not in ch.ghosts:
                    ch.ghosts[idx] = ch.quad("ghost", idx)
                    ch.ghosts[idx].hasKey = not self.relativeKeyDisplay
            for f in list(ch.pinned):
                if f not in self.pinnedFrames:
                    ch.pinned.pop(f)
            for f in self.pinnedFrames:
                if f not in ch.pinned:
                    ch.pinned[f] = ch.quad("pinned", f)

    def _keys(self, ch):
        k = (ch.key, bool(self.mainKeysOnly))
        if k not in self._keysCache:
            try:
                self._keysCache[k] = extras.character_keys(ch.names, self.mainKeysOnly)
            except Exception:
                self._keysCache[k] = []
        return self._keysCache[k]

    def characterHasKeys(self, key):
        ch = next((c for c in self.characters if c.key == key), None)
        return bool(ch and self._keys(ch))

    def setRelativeFrames(self, value):
        """Keys mode: each character's ghosts on its own past / next keys."""
        if not self.relativeKeyDisplay:
            return
        if self.hideWhilePlaying and oma.MAnimControl.isPlaying():
            return                                    # nothing to show while playing: no work either
        now = oma.MAnimControl.currentTime().value
        for ch in self.characters:
            past, nxt = extras.around(self._keys(ch), now, MAX_GHOSTS)
            for idx, q in ch.ghosts.items():
                seq = past if idx < 0 else nxt
                n = abs(idx)
                if n <= len(seq):
                    q.hasKey = True
                    q.setFrame(seq[-n] if idx < 0 else seq[n - 1])
                else:
                    q.hasKey = False

    def setRelativeDisplayMode(self, value):
        self.relativeKeyDisplay = bool(value)
        for ch in self.characters:
            for idx, q in ch.ghosts.items():
                q.setFrame(idx)
                q.hasKey = not self.relativeKeyDisplay
        if self.relativeKeyDisplay:
            self.setRelativeFrames(None)
        self.refresh()

    def setLightTable(self, on, strength, activeKey, onlyActive, background):
        """The light table: on / off, how see-through (0-1), the character you animate (the others fade), its
        ghosts only (the others' very faint), and the scene without the faded characters (mesh names)."""
        self.lightTable = bool(on)
        self.lightStrength = max(0.0, min(1.0, float(strength)))
        self.activeKey = activeKey
        self.onlyActive = bool(onlyActive)
        sel = om.MSelectionList()
        for n in background or []:
            try:
                sel.add(n)
            except Exception:
                pass
        self.lightBackground = self.flattenSelectionList(sel)
        self.refresh()

    def animationChanged(self, *args):
        """A key or curve changed: the characters' keys are read again, the arcs recorded again."""
        self._keysCache.clear()
        self.arcs.animationChanged(*args)

    def flattenSelectionList(self, selList):
        flatList = om.MSelectionList()
        selIter = om.MItSelectionList(selList)
        while not selIter.isDone():
            obj = selIter.getDependNode()
            if selIter.itemType() == 0:
                if selIter.hasComponents():
                    flatList.add(selIter.getComponent())
                elif obj.hasFn(om.MFn.kDagNode):
                    flatList.add(selIter.getDagPath())
            elif obj.hasFn(om.MFn.kSet):
                flatList.merge(self.flattenSelectionList(om.MFnSet(obj).getMembers(False)))
            selIter.next()
        return flatList

    # ------------------------------------------------------------------ callbacks
    def cameraMovedCB(self, msg, plug1, plug2, payload):
        """You moved the camera by hand: the pictures no longer line up (animated cameras aren't affected)."""
        if (msg == 2056 and self.autoClearBuffer and
                (self.isPlugInteresting(plug1, 'translate') or self.isPlugInteresting(plug1, 'rotate'))):
            self.clearOnionSkinBuffer(False)

    def isPlugInteresting(self, plug, targetPlug):
        mfn_dep = om.MFnDependencyNode(plug.node())
        return plug == mfn_dep.findPlug(targetPlug, True)

    def refresh(self):
        try:
            omui.M3dView.refresh(omui.M3dView.active3dView(), all=True)
        except Exception:
            pass

    def createCallbacks(self):
        self.timeCallbackId = om.MEventMessage.addEventCallback('timeChanged', self.setRelativeFrames)
        dgIter = om.MItDependencyNodes(om.MFn.kCamera)
        while not dgIter.isDone():
            shape = om.MFnDagNode(dgIter.thisNode())
            transform = shape.parent(0)
            if transform is not None:
                self.cameraMovedCallbackIds.append(
                    om.MNodeMessage.addAttributeChangedCallback(transform, self.cameraMovedCB))
            dgIter.next()
        try:
            self.animEditedCallbackId = oma.MAnimMessage.addAnimCurveEditedCallback(self.animationChanged)
        except Exception:
            self.animEditedCallbackId = None

    def deleteCallbacks(self):
        om.MEventMessage.removeCallback(self.timeCallbackId)
        for cb in self.cameraMovedCallbackIds:
            om.MMessage.removeCallback(cb)
        self.cameraMovedCallbackIds = []
        if self.animEditedCallbackId is not None:
            try:
                om.MMessage.removeCallback(self.animEditedCallbackId)
            except Exception:
                pass
            self.animEditedCallbackId = None

    # ------------------------------------------------------------------ settings
    def setAutoClearBuffer(self, value):
        self.autoClearBuffer = value

    def setMaxBuffer(self, value):
        self.maxOnionSkinBufferSize = int(value)
        while len(self.onionSkinBufferQueue) > max(self.maxOnionSkinBufferSize, 1):
            self.deleteOldestOnionSkinBuffer()
        self.refresh()

    def getMaxBuffer(self):
        return self.maxOnionSkinBufferSize

    def setRelativeStep(self, value):
        self.relativeStep = int(value)
        self.refresh()

    def setOnionSkinDisplayMode(self, onionSkinDisplayType):
        self.onionSkinDisplayType = int(onionSkinDisplayType)
        self.refresh()

    def setOutlineWidth(self, width):
        self.outlineWidth = int(width)
        self.refresh()

    def getOutlineWidth(self):
        return self.outlineWidth

    def setDrawBehind(self, value):
        self.drawBehind = int(value)
        self.refresh()

    def getDrawBehind(self):
        return self.drawBehind

    def setTint(self, rgba, target):
        if target == 'relative_futureTint_btn':
            self.relativeFutureTint = list(rgba)
        elif target == 'relative_pastTint_btn':
            self.relativePastTint = list(rgba)
        elif target == 'absolute_tint_btn':
            self.absoluteTint = list(rgba)
        self.refresh()

    def setTintStrength(self, strength):
        self.tintStrength = strength / 100.0
        self.refresh()

    def setGlobalOpacity(self, opacity):
        self.globalOpacity = max(0.0, min(1.0, opacity / 100.0))
        self.refresh()

    def setFade(self, value):
        self.fade = max(0.0, min(1.0, float(value)))
        self.refresh()
