# Shape Animation Tool - Updated for Maya 2025 / Python 3
import maya.cmds as cmds
import pickle
import os
import importlib.util


def pyToAttr(objAttr, data):
    """
    Write (pickle) Python data to the given Maya obj.attr.  This data can
    later be read back (unpickled) via attrToPy().

    Arguments:
    objAttr : string : a valid object.attribute name in the scene.  If the
            object exists, but the attribute doesn't, the attribute will be added.
            The if the attribute already exists, it must be of type 'string', so
            the Python data can be written to it.
    data : some Python data :  Data that will be pickled to the attribute
            in question.
    """
    obj, attr = objAttr.split('.')
    # Ensure the object exists first
    if not cmds.objExists(obj):
        cmds.createNode('network', n=obj)
        cmds.addAttr(obj, longName='time', attributeType='float')
        cmds.connectAttr('time1.outTime', obj + '.time')
    if not cmds.objExists(objAttr):
        cmds.addAttr(obj, longName=attr, dataType='string')
    if cmds.getAttr(objAttr, type=True) != 'string':
        raise Exception("Object '%s' already has an attribute called '%s', but it isn't type 'string'" % (obj, attr))
    # Use protocol 0 for ASCII-safe string representation
    stringData = pickle.dumps(data, protocol=0).decode('latin-1')
    cmds.setAttr(objAttr, edit=True, lock=False)
    cmds.setAttr(objAttr, stringData, type='string')
    cmds.setAttr(objAttr, edit=True, lock=True)


def attrToPy(objAttr):
    """
    Take previously stored (pickled) data on a Maya attribute (put there via
    pyToAttr() ) and read it back (unpickle) to valid Python values.

    Arguments:
    objAttr : string : A valid object.attribute name in the scene.  And of course,
            it must have already had valid Python data pickled to it.

    Return : some Python data :  The reconstituted, unpickled Python data.
    """
    stringAttrData = str(cmds.getAttr(objAttr))
    loadedData = pickle.loads(stringAttrData.encode('latin-1'))
    return loadedData


def compileUI():
    from pyside6uic import compileUi
    print('!!!')
    spec = importlib.util.find_spec('sat2')
    if spec and spec.origin:
        modulePath = os.path.dirname(os.path.abspath(spec.origin))
    else:
        modulePath = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(modulePath, 'mainWindow.py'), 'w') as pyfile:
        compileUi(os.path.join(modulePath, 'mainWindow.ui'), pyfile, False, 4, False)
    with open(os.path.join(modulePath, 'aboutWindow.py'), 'w') as pyfile2:
        compileUi(os.path.join(modulePath, 'aboutWindow.ui'), pyfile2, False, 4, False)
