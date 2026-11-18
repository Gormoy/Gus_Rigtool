import maya.api.OpenMayaRender as omr

"""
adding hud elements
(noPyMEL copy) also draws the arcs (onionSkinRenderer/arcs.py) on top of everything
"""
class viewRenderHUDRender(omr.MHUDRender):
    def __init__(self, owner=None):
        omr.MHUDRender.__init__(self)

        self.target = None
        self.owner = owner

    def __del__(self):
        self.target = None
        self.owner = None

    def targetOverrideList(self):
        if self.target is not None:
            return [self.target]
        return None

    def setRenderTarget(self, target):
        self.target = target

    def hasUIDrawables(self):
        return True

    def addUIDrawables(self, drawManager2D, frameContext):
        owner = self.owner
        if owner is None or not owner.arcs.show or not owner.arcs.points:
            return
        try:
            import onionSkinRenderer.arcs as arcs
            arcs.draw(owner.arcs, drawManager2D, frameContext, owner.currentFrame,
                      owner.relativePastTint, owner.relativeFutureTint)
        except Exception as e:                      # a drawing problem must never break the viewport
            if not getattr(self, "_told", False):
                self._told = True
                print("onionSkinRenderer: arcs not drawn: %s" % e)
