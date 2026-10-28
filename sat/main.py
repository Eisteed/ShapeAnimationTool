# Shape Animation Tool - Updated for Maya 2025 / Python 3
import maya.cmds as cmds
import maya.mel as mel
import maya.OpenMayaUI as omui
import maya.OpenMaya as om

from functools import partial
from .Qt import QtCore, QtWidgets, QtGui
try:
    from shiboken6 import wrapInstance
except ImportError:
    try:
        from shiboken2 import wrapInstance
    except ImportError:
        from shiboken import wrapInstance

import os
import importlib
import importlib.util
import webbrowser
import logging
import inspect
from . import mainWindow
from . import utils

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
moduleName = __name__.split('.')[0]

# Find module path using importlib (Python 3 compatible)
spec = importlib.util.find_spec(moduleName)
if spec and spec.origin:
    modulePath = os.path.dirname(os.path.abspath(spec.origin))
else:
    modulePath = os.path.dirname(os.path.abspath(__file__))

version = '2.2'

def mayaMainWindow():
    mainWindowPtr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(mainWindowPtr), QtWidgets.QWidget)


debug = False
v = mel.eval('about -version')

class MainWindow(QtWidgets.QMainWindow, mainWindow.Ui_MainWindow):

    def __init__(self, parent=mayaMainWindow()):
        super(MainWindow, self).__init__(parent)
        self.setupUi(self)
        logger.debug('Start ' + inspect.stack()[0][3])
        self.meshes = []
        self.curLayer = ''
        self.curMesh = ''
        self.bs1 = ''
        self.bs_name = ''
        self.editMode = False
        self._changingEdit = False
        self._timeJob = None
        self._selectionJob = None
        self._timelineConnection = None
        self._timelineOriginal = None
        self._timelineSlider = None
        self.curFrame = 0
        self.keyFrames = []
        self.brushMode = 1
        self.setWindowTitle('Shape Animation Tool ' + version)
        self.sculpt_btn.setStyleSheet('')
        return

    def updateFrame(self, sculptOff=True, *args):
        logger.debug('Start ' + inspect.stack()[0][3])
        if (self.editMode and sculptOff and not self._changingEdit
                and cmds.currentTime(query=True) != self.curFrame):
            self.sculpt_btn.setChecked(False)
        try:
            if self.isVisible():
                currentKey = cmds.currentTime(query=True)
                for i in range(len(self.keyFrames)):
                    if self.keyFrames[i] == currentKey:
                        self.keyData_label.setText(str(i + 1) + ' / ' + str(len(self.keyFrames)))
                        self.key_btn.setStyleSheet('background-color: #5f2626')
                        return

                self.key_btn.setStyleSheet('')
                self.keyData_label.setText('- / ' + str(len(self.keyFrames)))
        except:
            pass

        return

    def start(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        sel = cmds.ls(sl=1)
        satNode = cmds.ls('sat')
        if len(satNode) == 0:
            cmds.createNode('network', n='sat')
            cmds.addAttr('sat', longName='time', attributeType='float')
            cmds.connectAttr('time1.outTime', 'sat.time')
        cmds.select('sat', add=True)
        try:
            self.loadData()
        except:
            pass

        if self._timeJob is not None and cmds.scriptJob(exists=self._timeJob):
            cmds.scriptJob(kill=self._timeJob, force=True)
        self._timeJob = cmds.scriptJob(
            event=['timeChanged', partial(self.updateFrame, True)])
        self.fillGeoList()
        self.updateUI()
        if self.editMode:
            cmds.currentTime(self.curFrame)
            self.sculpt_btn.setChecked(True)
        self.actionUse_Artisan_Tool.setEnabled(self.editMode)
        self.actionUse_Components.setEnabled(self.editMode)
        self.actionReset_Shape_to_Default.setEnabled(self.editMode)
        if len(sel) > 0:
            cmds.select(sel)
        self._timelineSlider = mel.eval('$tmpVar=$gPlayBackSlider')
        self._timelineConnection = cmds.selectionConnection()
        if self._selectionJob is not None and cmds.scriptJob(exists=self._selectionJob):
            cmds.scriptJob(kill=self._selectionJob, force=True)
        self._selectionJob = cmds.scriptJob(
            event=['SelectionChanged', self.refreshTimeline])
        self.refreshTimeline()
        return

    def _colorShapeKeys(self, blendshape):
        curves = cmds.listConnections(blendshape + '.weight', source=True,
                                      destination=False, type='animCurve') or []
        if curves:
            cmds.keyframe(list(set(curves)), edit=True, tickDrawSpecial=True)

    def _restoreTimeline(self):
        if self._timelineOriginal is not None:
            # Avoid replacing another tool's connection if it took ownership.
            current = cmds.timeControl(self._timelineSlider, query=True,
                                       mainListConnection=True)
            if current == self._timelineConnection:
                cmds.timeControl(self._timelineSlider, edit=True,
                                 mainListConnection=self._timelineOriginal)
            self._timelineOriginal = None

    def refreshTimeline(self, *args):
        if not self._timelineConnection:
            return
        selected = cmds.ls(selection=True, objectsOnly=True, long=True) or []
        transforms = set(selected)
        for node in selected:
            transforms.update(cmds.listRelatives(node, parent=True, fullPath=True) or [])
        targets = []
        for layer in self.meshes:
            mesh = layer.rsplit('_LR', 1)[0]
            paths = set(cmds.ls(mesh, long=True) or [])
            if self.editMode and layer == self.curLayer and self.bs1:
                paths.update(cmds.ls(self.bs1, long=True) or [])
            blendshape = layer + '_satBS'
            if (paths.intersection(transforms) or blendshape in selected
                    or any(n.rsplit('|', 1)[-1] == blendshape for n in selected)):
                if cmds.objExists(blendshape):
                    targets.append(blendshape)
        if not targets:
            self._restoreTimeline()
            return
        if self._timelineOriginal is None:
            self._timelineOriginal = cmds.timeControl(
                self._timelineSlider, query=True, mainListConnection=True)
        cmds.selectionConnection(self._timelineConnection, edit=True, clear=True)
        for node in selected + targets:
            cmds.selectionConnection(self._timelineConnection, edit=True, select=node)
        for node in targets:
            self._colorShapeKeys(node)
        cmds.timeControl(self._timelineSlider, edit=True,
                         mainListConnection=self._timelineConnection)
        cmds.timeControl(self._timelineSlider, edit=True, forceRefresh=True)

    def connectSignals(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        self.add_btn.clicked.connect(self.addMesh)
        self.pick_btn.clicked.connect(self.pickMesh)
        self.remove_btn.clicked.connect(self.removeMesh)
        self.geo_listWidget.currentItemChanged.connect(self.selectMeshInList)
        self.geo_listWidget.itemClicked.connect(self.onOffBs)
        self.key_btn.clicked.connect(self.setKey)
        self.prevKey_btn.clicked.connect(partial(self.stepKey, 'prev'))
        self.nextKey_btn.clicked.connect(partial(self.stepKey, 'next'))
        self.deleteKey_btn.clicked.connect(self.deleteKey)
        self.sculpt_btn.toggled.connect(self.sculpt)
        self.brush_btn.clicked.connect(self.brush)
        self.points_btn.clicked.connect(self.points)
        self.resetShape_btn.clicked.connect(self.resetShape)
        self.actionAdd.triggered.connect(self.addMesh)
        self.actionPick.triggered.connect(self.pickMesh)
        self.actionRemove.triggered.connect(self.removeMesh)
        self.actionRemove_All.triggered.connect(self.removeAllMeshes)
        self.actionSet_Key.triggered.connect(self.setKey)
        self.actionDelete_Key.triggered.connect(self.deleteKey)
        self.actionDelete_All_Keys.triggered.connect(self.deleteAllKeys)
        self.actionPrevious_Key.triggered.connect(partial(self.stepKey, 'prev'))
        self.actionNext_Key.triggered.connect(partial(self.stepKey, 'next'))
        self.actionBrush_Tool_Window.triggered.connect(self.showBrushWindow)
        self.actionEdit_Mode_2.triggered.connect(self.scultpMenuOn)
        self.actionUse_Artisan_Tool.triggered.connect(self.brush)
        self.actionUse_Components.triggered.connect(self.points)
        self.actionReset_Shape_to_Default.triggered.connect(self.resetShape)
        self.actionHome_Page.triggered.connect(self.homePage)
        return

    def updateUI(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        ui = False
        if self.geo_listWidget.count() == 0:
            ui = False
        else:
            for index in range(self.geo_listWidget.count()):
                check_box = self.geo_listWidget.item(index)
                if self.curLayer == check_box.text():
                    if check_box.checkState() == QtCore.Qt.CheckState.Checked:
                        ui = True
                    else:
                        ui = False
                    break

        if ui:
            self.remove_btn.setEnabled(True)
            self.groupBox_3.setEnabled(True)
            self.groupBox_4.setEnabled(True)
        else:
            self.remove_btn.setEnabled(False)
            self.groupBox_3.setEnabled(False)
            self.groupBox_4.setEnabled(False)
        return

    def onOffBs(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        for index in range(self.geo_listWidget.count()):
            check_box = self.geo_listWidget.item(index)
            state = check_box.checkState()
            try:
                if state == QtCore.Qt.CheckState.Checked:
                    cmds.setAttr(check_box.text() + '_satBS.envelope', 1)
                else:
                    cmds.setAttr(check_box.text() + '_satBS.envelope', 0)
            except:
                pass

        self.updateUI()
        self.refreshTimeline()
        return

    def selectMeshInList(self, curr, prev):
        logger.debug('Start ' + inspect.stack()[0][3])
        try:
            self.curLayer = curr.text()
            self.curMesh = curr.text().split('_LR')[0]
            self.bs_name = self.curLayer + '_satBS'
        except:
            pass

        self.saveData()
        self.getKeytimes()
        self.updateFrame(True)
        if cmds.objExists(self.curMesh):
            cmds.select(self.curMesh)
        if cmds.objExists(self.bs_name):
            cmds.select(self.bs_name, add=1)
        return

    def addMesh(self):
        logger.debug('Start ' + inspect.stack()[0][3])

        def setLayerName(name):
            i = 1
            layer = name + '_LR1'
            while layer in self.meshes:
                i += 1
                layer = name + '_LR' + str(i)

            return layer

        shape = cmds.ls(sl=True, dag=True, noIntermediate=True, geometry=True)
        if len(shape) == 0:
            return
        mesh = cmds.listRelatives(shape, parent=True)[0]
        self.curMesh = mesh
        self.curLayer = setLayerName(mesh)
        self.meshes.append(self.curLayer)
        self.fillGeoList()
        self.saveData()
        self.geo_groupBox.setEnabled(True)
        self.updateUI()
        cmds.select(self.curMesh)
        return

    def removeMesh(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        if len(self.meshes) == 0:
            return
        try:
            cmds.delete(self.bs_name)
        except:
            pass

        self.meshes.remove(self.curLayer)
        try:
            self.curLayer = self.meshes[-1]
        except:
            self.curLayer = ''

        self.keyFrames = []
        self.fillGeoList()
        self.updateUI()
        self.saveData()
        self.updateFrame('')
        return

    def pickMesh(self):
        ctx = 'pickShapeCtx'

        def onPress():
            vpX, vpY, _ = cmds.draggerContext(ctx, query=True, anchorPoint=True)
            pos = om.MPoint()
            dir = om.MVector()
            hitpoint = om.MFloatPoint()
            omui.M3dView().active3dView().viewToWorld(int(vpX), int(vpY), pos, dir)
            floatHitPoint = om.MFloatPoint()
            floatHitPoint.setCast(pos)
            distances = []
            objects = []
            pos2 = om.MFloatPoint(pos.x, pos.y, pos.z)
            for mesh in cmds.ls(type='mesh'):
                selectionList = om.MSelectionList()
                selectionList.add(mesh)
                dagPath = om.MDagPath()
                selectionList.getDagPath(0, dagPath)
                fnMesh = om.MFnMesh(dagPath)
                intersection = fnMesh.closestIntersection(om.MFloatPoint(pos2), om.MFloatVector(dir), None, None, False, om.MSpace.kWorld, 99999, False, None, hitpoint, None, None, None, None, None)
                if intersection:
                    meshName = fnMesh.name()
                    # Check if mesh is intermediate or hidden using cmds (PyMEL-free)
                    isIntermediate = cmds.getAttr(meshName + '.intermediateObject')
                    isVisible = cmds.getAttr(meshName + '.visibility')
                    if not isIntermediate and isVisible:
                        dist = hitpoint.distanceTo(floatHitPoint)
                        distances.append(dist)
                        objects.append(meshName)

            if len(objects) > 0:
                closestDist = distances[0]
                closestId = 0
                for d_id, d in enumerate(distances):
                    if d < closestDist:
                        closestDist = d
                        closestId = d_id

                cmds.select(objects[closestId])
                self.addMesh()
            return

        if cmds.draggerContext(ctx, exists=True):
            cmds.deleteUI(ctx)
        cmds.draggerContext(ctx, pressCommand=onPress, name=ctx, cursor='crossHair')
        cmds.setToolTo(ctx)
        return

    def fillGeoList(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        self.geo_listWidget.clear()
        curItem = ''
        for mesh in self.meshes:
            meshItem = QtWidgets.QListWidgetItem(mesh)
            meshItem.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsSelectable | QtCore.Qt.ItemIsUserCheckable)
            meshItem.setFont(QtGui.QFont('Verdana', 10))
            meshItem.setCheckState(QtCore.Qt.Checked)
            self.geo_listWidget.addItem(meshItem)
            if mesh == self.curLayer:
                curItem = meshItem

        try:
            self.geo_listWidget.setCurrentItem(curItem)
        except:
            pass

        def setCheckLayers():
            for index in range(self.geo_listWidget.count()):
                check_box = self.geo_listWidget.item(index)
                try:
                    state = cmds.getAttr(check_box.text() + '_satBS.envelope')
                    if state == 1.0:
                        check_box.setCheckState(QtCore.Qt.CheckState.Checked)
                    else:
                        check_box.setCheckState(QtCore.Qt.CheckState.Unchecked)
                except:
                    pass

            return

        setCheckLayers()
        return

    def removeAllMeshes(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        if len(self.meshes) == 0:
            return
        for mesh in self.meshes:
            bs_name = self.returnName(mesh) + '_satBS'
            try:
                cmds.delete(bs_name)
            except:
                pass

        self.meshes = []
        self.keyFrames = []
        self.fillGeoList()
        self.updateUI()
        self.saveData()
        self.updateFrame('')
        return

    def sculpt(self, on, *args):
        if self._changingEdit or (on and self.editMode and self.bs1):
            return
        self._changingEdit = True
        try:
            self._setEditMode(on)
        except Exception:
            if on:
                self._setEditMode(False)
            raise
        finally:
            self._changingEdit = False
            blocked = self.sculpt_btn.blockSignals(True)
            self.sculpt_btn.setChecked(self.editMode)
            self.sculpt_btn.blockSignals(blocked)

    def _setEditMode(self, on):
        logger.debug('Start Sculpt')
        self.editMode = on
        self.curFrame = cmds.currentTime(query=True)
        utils.pyToAttr('sat.sculptMode', self.editMode)
        utils.pyToAttr('sat.currentFrame', self.curFrame)
        if on:
            if not cmds.objExists(self.bs_name):
                self.setKey()
            else:
                crvs = cmds.listConnections(self.bs_name, t='animCurve')
                currentTime = cmds.currentTime(query=True)
                if currentTime not in self.keyFrames:
                    self.setKey()
            shapes = cmds.listAttr(self.curLayer + '_satBS.w', m=True) or []
            target = next((sh for sh in shapes
                           if cmds.getAttr(self.bs_name + '.' + sh) > 0.1), None)
            if target is None:
                raise RuntimeError('No active shape target at the current frame.')
            target_index = target.split('_')[-1]
            self.bs1 = cmds.duplicate(
                self.curMesh, n=self.curMesh.rsplit('|', 1)[-1] + '_temp_shape')[0]
            if not cmds.objExists('sat.tempMesh'):
                cmds.addAttr('sat', longName='tempMesh', attributeType='message')
            cmds.connectAttr(self.bs1 + '.message', 'sat.tempMesh', force=True)
            cmds.setAttr(self.bs1 + '.tx', lock=0)
            cmds.setAttr(self.bs1 + '.ty', lock=0)
            cmds.setAttr(self.bs1 + '.tz', lock=0)
            cmds.setAttr(self.bs1 + '.rx', lock=0)
            cmds.setAttr(self.bs1 + '.ry', lock=0)
            cmds.setAttr(self.bs1 + '.rz', lock=0)
            cmds.setAttr(self.bs1 + '.sx', lock=0)
            cmds.setAttr(self.bs1 + '.sy', lock=0)
            cmds.setAttr(self.bs1 + '.sz', lock=0)
            self.removeIntermediateShape(self.bs1)
            self.fixShapeName(self.bs1)
            par = cmds.listRelatives(self.bs1, p=True)
            if par is not None:
                self.bs1 = cmds.parent(self.bs1, w=True)[0]
            currentPanel = cmds.getPanel(withFocus=1)
            try:
                state = cmds.isolateSelect(currentPanel, q=1, state=1)
                if state == 1:
                    cmds.isolateSelect(currentPanel, addSelected=1)
            except:
                pass

            n = target_index
            temp_shape = cmds.listRelatives(self.bs1, shapes=True, noIntermediate=True, fullPath=True)[0]
            cmds.connectAttr(temp_shape + '.worldMesh[0]', self.bs_name + '.inputTarget[0].inputTargetGroup[%s].inputTargetItem[6000].inputGeomTarget' % n)
            cmds.select(self.bs1)
            if self.brushMode == 1:
                self.brush()
            else:
                self.setSelectionMode(True)
            self.geo_groupBox.setEnabled(False)
            self.prevKey_btn.setEnabled(False)
            self.key_btn.setEnabled(False)
            self.nextKey_btn.setEnabled(False)
            self.deleteKey_btn.setEnabled(False)
            self.sculpt_btn.setStyleSheet('background-color: rgb(0, 80, 40)')
            self.brush_btn.setEnabled(True)
            self.points_btn.setEnabled(True)
            self.resetShape_btn.setEnabled(True)
            self._originalLodVisibility = cmds.getAttr(self.curMesh + '.lodVisibility')
            cmds.setAttr(self.curMesh + '.lodVisibility', False)
            self.actionUse_Artisan_Tool.setEnabled(True)
            self.actionUse_Components.setEnabled(True)
            self.actionReset_Shape_to_Default.setEnabled(True)
        else:
            # Turning off sculpt mode
            if cmds.selectMode(q=True, component=True):
                self.setSelectionMode()
            # Delete the temporary sculpt mesh
            if self.bs1 and cmds.objExists(self.bs1):
                cmds.delete(self.bs1)
            self.bs1 = ''
            mel.eval('SelectTool')
            cmds.select(clear=True)
            if cmds.objExists(self.curMesh):
                cmds.select(self.curMesh)
            if cmds.objExists(self.bs_name):
                cmds.select(self.bs_name, add=True)
            self.geo_groupBox.setEnabled(True)
            self.prevKey_btn.setEnabled(True)
            self.key_btn.setEnabled(True)
            self.nextKey_btn.setEnabled(True)
            self.deleteKey_btn.setEnabled(True)
            self.sculpt_btn.setStyleSheet('')
            self.brush_btn.setEnabled(False)
            self.points_btn.setEnabled(False)
            self.resetShape_btn.setEnabled(False)
            if cmds.objExists(self.curMesh):
                cmds.setAttr(self.curMesh + '.lodVisibility', getattr(self, '_originalLodVisibility', True))
            self.actionUse_Artisan_Tool.setEnabled(False)
            self.actionUse_Components.setEnabled(False)
            self.actionReset_Shape_to_Default.setEnabled(False)
        return

    def scultpMenuOn(self):
        self.sculpt_btn.setChecked(not self.sculpt_btn.isChecked())
        return

    def setSelectionMode(self, component=False):
        logger.debug('Start ' + inspect.stack()[0][3])
        if not component:
            if cmds.selectMode(q=True, component=True):
                cmds.select(self.bs1)
                mel.eval('SelectToggleMode')
                mel.eval('hilite -u %s' % self.bs1)
                mel.eval('select -r %s' % self.bs1)
                mel.eval('SelectTool')
        else:
            cmds.select(self.bs1)
            mel.eval('SelectVertexMask')
            mel.eval('hilite %s' % self.bs1)
            mel.eval('SelectTool')
            cmds.TranslateToolWithSnapMarkingMenu()
            cmds.MarkingMenuPopDown()
        return

    def brush(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        self.brushMode = 1
        if cmds.selectMode(q=True, component=True):
            self.setSelectionMode()
        mel.eval('SetMeshGrabTool;')
        return

    def points(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        self.brushMode = 3
        self.setSelectionMode(True)
        return

    def resetShape(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        currentTime = cmds.currentTime(query=True)
        if cmds.objExists(self.bs_name):
            for i in range(0, len(self.keyFrames)):
                t = self.keyFrames[i]
                if t == currentTime:
                    shapes = cmds.listAttr(self.curLayer + '_satBS.w', m=True)
                    for sh in shapes:
                        v = cmds.getAttr(self.curLayer + '_satBS.' + sh)
                        if v > 0.1:
                            cmds.setAttr(self.bs_name + '.envelope', 0)
                            bs0 = cmds.duplicate(self.curMesh, n='shape_init')[0]
                            cmds.setAttr(self.bs_name + '.envelope', 1)
                            self.removeIntermediateShape(bs0)
                            self.fixShapeName(bs0)
                            bs = cmds.blendShape(bs0, self.bs1, tc=0)[0]
                            cmds.setAttr(bs + '.' + bs0, 1)
                            cmds.delete(self.bs1, constructionHistory=True)
                            cmds.delete(bs0)
                            cmds.select(self.bs1)

        return

    def setKey(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        if len(self.meshes) == 0:
            return

        def getFirstFreeTargetIdPair():
            bsId0 = 0
            if cmds.objExists(self.bs_name):
                while cmds.attributeQuery('shape_' + str(bsId0), node=self.bs_name, exists=True):
                    bsId0 += 1

            bsId1 = bsId0 + 1
            if cmds.objExists(self.bs_name):
                while cmds.attributeQuery('shape_' + str(bsId1), node=self.bs_name, exists=True):
                    bsId1 += 1

            return (
             bsId0, bsId1)

        currentTime = cmds.currentTime(query=True)
        if ':' in self.curLayer:
            ns = self.curLayer.split(':')[0]
        else:
            ns = ''
        if cmds.objExists(self.bs_name):
            for keyTime in self.keyFrames:
                if keyTime == currentTime:
                    return

        self.keyFrames.append(currentTime)
        self.keyFrames = sorted(self.keyFrames)
        bsId0, bsId1 = getFirstFreeTargetIdPair()
        bs0_name = 'shape_' + str(bsId0)
        bs1_name = 'shape_' + str(bsId1)
        bs1 = cmds.duplicate(self.curMesh, n=bs1_name)[0]
        try:
            cmds.setAttr(self.bs_name + '.envelope', 0)
            bs0 = cmds.duplicate(self.curMesh, n=bs0_name)[0]
            cmds.setAttr(self.bs_name + '.envelope', 1)
        except:
            bs0 = cmds.duplicate(self.curMesh, n=bs0_name)[0]

        self.removeIntermediateShape(bs0)
        self.removeIntermediateShape(bs1)
        self.fixShapeName(bs0)
        self.fixShapeName(bs1)
        cmds.select(bs0)
        cmds.select(bs1, add=True)
        cmds.select(self.curMesh, add=True)
        if not cmds.objExists(self.bs_name):
            cmds.blendShape(n=self.bs_name)
        else:
            cmds.blendShape(self.bs_name, e=True, t=(self.curMesh, bsId0, bs0, 1.0))
            cmds.blendShape(self.bs_name, e=True, t=(self.curMesh, bsId1, bs1, 1.0))
        cmds.delete(bs0)
        cmds.delete(bs1)
        crvs = cmds.listConnections(self.bs_name, t='animCurve')
        if crvs is not None:
            for c in crvs:
                cmds.setKeyframe(c, v=0)
                cmds.keyTangent(c, edit=True, weightedTangents=True)
                cmds.keyTangent(c, edit=True, weightedTangents=False)

            times = cmds.keyframe(crvs[0], query=True, tc=True)
            for t in times:
                cmds.setKeyframe(self.bs_name + '.' + bs1_name, t=t, v=0)

        cmds.setKeyframe(self.bs_name + '.' + bs1_name, v=1)
        self._colorShapeKeys(self.bs_name)
        cmds.setAttr(self.bs_name + '.' + bs1_name, 1)
        if 'multDL' in cmds.allNodeTypes():
            multNode = cmds.createNode('multDL', n=bs1_name + '_mult')
            input1, input2, output = '.input1', '.input2', '.output'
        else:
            multNode = cmds.createNode('multiplyDivide', n=bs1_name + '_mult')
            input1, input2, output = '.input1X', '.input2X', '.outputX'
        cmds.setAttr(multNode + input2, -1)
        cmds.connectAttr(self.bs_name + '.' + bs1_name, multNode + input1)
        cmds.connectAttr(multNode + output, self.bs_name + '.' + bs0_name)
        self.saveData()
        cmds.select(self.curMesh)
        cmds.select(self.bs_name, add=True)
        self.updateFrame(False)
        return

    def deleteKey(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        if len(self.meshes) == 0:
            return
        currentTime = cmds.currentTime(query=True)
        if cmds.objExists(self.bs_name):
            for i in range(0, len(self.keyFrames)):
                t = self.keyFrames[i]
                if t == currentTime:
                    shapes = cmds.listAttr(self.curLayer + '_satBS.w', m=True)
                    for sh in shapes:
                        v = cmds.getAttr(self.curLayer + '_satBS.' + sh)
                        if v < -0.1:
                            n = sh.split('_')[-1]
                            bs0 = cmds.duplicate(self.curMesh, n=sh)[0]
                            self.removeIntermediateShape(bs0)
                            self.fixShapeName(bs0)
                            cmds.connectAttr(sh + 'Shape.worldMesh[0]', self.bs_name + '.inputTarget[0].inputTargetGroup[%s].inputTargetItem[6000].inputGeomTarget' % n)
                            cmds.blendShape(self.bs_name, edit=True, remove=True, t=(self.curMesh, int(n), bs0, 1.0))
                            cmds.delete(bs0)

                    shapes = cmds.listAttr(self.curLayer + '_satBS.w', m=True)
                    for sh in shapes:
                        v = cmds.getAttr(self.curLayer + '_satBS.' + sh)
                        if v > 0.1:
                            n = sh.split('_')[-1]
                            bs0 = cmds.duplicate(self.curMesh, n=sh)[0]
                            self.removeIntermediateShape(bs0)
                            self.fixShapeName(bs0)
                            cmds.connectAttr(sh + 'Shape.worldMesh[0]', self.bs_name + '.inputTarget[0].inputTargetGroup[%s].inputTargetItem[6000].inputGeomTarget' % n)
                            cmds.blendShape(self.bs_name, edit=True, remove=True, t=(self.curMesh, int(n), bs0, 1.0))
                            cmds.delete(bs0)
                            cmds.delete(sh + '_mult')

                    cmds.cutKey(self.bs_name, time=(currentTime, currentTime))
                    self.keyFrames.remove(currentTime)
                    self.saveData()
                    self.updateFrame(True)
                    cmds.select(self.curMesh, self.bs_name)
                    return

        return

    def deleteAllKeys(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        if len(self.meshes) == 0:
            return
        if cmds.objExists(self.bs_name):
            shapes = cmds.listAttr(self.curLayer + '_satBS.w', m=True)
            for sh in shapes:
                n = sh.split('_')[-1]
                bs0 = cmds.duplicate(self.curMesh, n=sh)[0]
                self.removeIntermediateShape(bs0)
                self.fixShapeName(bs0)
                cmds.connectAttr(sh + 'Shape.worldMesh[0]', self.bs_name + '.inputTarget[0].inputTargetGroup[%s].inputTargetItem[6000].inputGeomTarget' % n)
                cmds.blendShape(self.bs_name, edit=True, remove=True, t=(self.curMesh, int(n), bs0, 1.0))
                cmds.delete(bs0)
                try:
                    cmds.delete(sh + '_mult')
                except:
                    pass

            self.keyFrames = []
            self.saveData()
            self.updateFrame(True)
            cmds.select(self.curMesh)
            cmds.select(self.bs_name, add=True)
            return
        return

    def stepKey(self, direction):
        logger.debug('Start ' + inspect.stack()[0][3])
        currentTime = cmds.currentTime(query=True)
        prevKeyId = []
        nextKeyId = []
        for i in range(0, len(self.keyFrames)):
            t = self.keyFrames[i]
            if t < currentTime:
                prevKeyId.append(t)
            elif t > currentTime:
                nextKeyId.append(t)

        prevKeyId.sort()
        nextKeyId.sort()
        if len(prevKeyId) > 0:
            prevKey = prevKeyId[-1]
        else:
            prevKey = 'none'
        if len(nextKeyId) > 0:
            nextKey = nextKeyId[0]
        else:
            nextKey = 'none'
        if direction == 'prev' and len(prevKeyId) > 0:
            cmds.currentTime(prevKey)
        elif direction == 'next' and len(nextKeyId) > 0:
            cmds.currentTime(nextKey)
        elif direction == 'prev' and len(self.keyFrames) > 0:
            cmds.currentTime(self.keyFrames[0])
        elif direction == 'next' and len(self.keyFrames) > 0:
            cmds.currentTime(self.keyFrames[-1])
        self.updateFrame(True)
        return

    def getKeytimes(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        try:
            animCrv = cmds.listConnections(self.bs_name, t='animCurve')[0]
            self.keyFrames = cmds.keyframe(animCrv, query=True, tc=True)
        except:
            self.keyFrames = []

        return

    def saveData(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        utils.pyToAttr('sat.meshes', self.meshes)
        utils.pyToAttr('sat.curMesh', self.curLayer)
        utils.pyToAttr('sat.sculptMode', self.editMode)
        return

    def loadData(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        self.meshes = utils.attrToPy('sat.meshes')
        self.curLayer = utils.attrToPy('sat.curMesh')
        # Finish an interrupted session before rebuilding the window. Deleting
        # the connected target lets Maya retain its edited blendshape data.
        if cmds.objExists('sat.tempMesh'):
            for mesh in cmds.listConnections('sat.tempMesh', source=True, destination=False) or []:
                cmds.delete(mesh)
            source_mesh = self.curLayer.rsplit('_LR', 1)[0]
            if cmds.objExists(source_mesh):
                cmds.setAttr(source_mesh + '.lodVisibility', True)
        self.editMode = False
        try:
            self.curFrame = utils.attrToPy('sat.currentFrame')
        except:
            pass

        self.getKeytimes()
        return

    def removeIntermediateShape(self, transform):
        logger.debug('Start ' + inspect.stack()[0][3])
        children = cmds.listRelatives(transform, fullPath=True)
        for c in children:
            if cmds.getAttr(c + '.intermediateObject'):
                cmds.delete(c)

        return

    def fixShapeName(self, transformName):
        logger.debug('Start ' + inspect.stack()[0][3])
        shape = cmds.pickWalk(transformName, d='down')[0]
        cmds.rename(shape, transformName + 'Shape')
        return

    def returnName(self, obj):
        logger.debug('Start ' + inspect.stack()[0][3])
        name = obj
        if ':' in obj:
            name = obj.split(':')[1]
        return name

    def showBrushWindow(self):
        logger.debug('Start ' + inspect.stack()[0][3])
        mel.eval('toolPropertyWindow -inMainWindow true;')
        return

    def homePage(self):
        logger.debug('Start Show HomePage')
        url = 'https://github.com/Eisteed/ShapeAnimationTool'
        webbrowser.open(url, new=2)
        return

    def closeEvent(self, *args, **kwargs):
        logger.debug('Close ')
        if self.editMode:
            self.sculpt(False)
        if self._timeJob is not None and cmds.scriptJob(exists=self._timeJob):
            cmds.scriptJob(kill=self._timeJob, force=True)
        self._timeJob = None
        if self._selectionJob is not None and cmds.scriptJob(exists=self._selectionJob):
            cmds.scriptJob(kill=self._selectionJob, force=True)
        self._selectionJob = None
        self._restoreTimeline()
        if self._timelineConnection:
            cmds.deleteUI(self._timelineConnection)
            self._timelineConnection = None
        super(MainWindow, self).closeEvent(*args, **kwargs)
        return
