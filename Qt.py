# Qt.py - Updated for Maya 2025 / Python 3
# Provides a unified Qt interface supporting PySide6, PySide2, PyQt5
"""Map all bindings to a unified Qt interface

This module replaces itself with the most desirable binding.

Default resolution order for Maya 2025+:
    - PySide6 (Maya 2025+)
    - PySide2 (Maya 2017-2024)
    - PyQt5

Usage:
    >> from Qt import QtWidgets, QtCore, QtGui
    >> button = QtWidgets.QPushButton("Hello World")

"""
import os
import sys

self = sys.modules[__name__]
self.__version__ = '3.0'
self.__added__ = list()
self.__remapped__ = list()
self.__modified__ = list()
self.__qt_version__ = '0.0.0'
self.__binding__ = 'None'
self.__binding_version__ = '0.0.0'
self.load_ui = lambda fname: None
self.translate = lambda context, sourceText, disambiguation, n: None
self.setSectionResizeMode = lambda *args, **kwargs: None


def convert(lines):
    """Convert compiled .ui file from PySide2/PySide6 to Qt.py"""
    def parse(line):
        line = line.replace('from PySide6 import', 'from Qt import')
        line = line.replace('from PySide2 import', 'from Qt import')
        line = line.replace('QtWidgets.QApplication.translate', 'Qt.QtCompat.translate')
        return line

    parsed = list()
    for line in lines:
        line = parse(line)
        parsed.append(line)

    return parsed


def _remap(object, name, value, safe=True):
    """Prevent accidental assignment of existing members"""
    if os.getenv('QT_TESTING') is not None and safe:
        if hasattr(object, name):
            raise AttributeError('Cannot override existing name: %s.%s' % (
                object.__name__, name))
        if type(object).__name__ != 'module':
            raise AttributeError("%s != 'module': Cannot alter anything but modules" % object)
    elif hasattr(object, name):
        self.__modified__.append(name)
    self.__remapped__.append(name)
    setattr(object, name, value)


def _add(object, name, value):
    """Append to self, accessible via Qt.QtCompat"""
    self.__added__.append(name)
    setattr(self, name, value)


def _pyside6():
    """Setup PySide6 (Maya 2025+)"""
    import PySide6
    from PySide6 import QtGui, QtWidgets, QtCore, QtUiTools
    _remap(QtCore, 'QStringListModel', QtCore.QStringListModel)
    _add(PySide6, '__binding__', PySide6.__name__)
    _add(PySide6, 'load_ui', lambda fname: QtUiTools.QUiLoader().load(fname))
    _add(PySide6, 'translate', lambda context, sourceText, disambiguation, n: QtCore.QCoreApplication.translate(context, sourceText, disambiguation, n))
    _add(PySide6, 'setSectionResizeMode', QtWidgets.QHeaderView.setSectionResizeMode)
    _maintain_backwards_compatibility(PySide6)
    return PySide6


def _pyside2():
    """Setup PySide2 (Maya 2017-2024)"""
    import PySide2
    from PySide2 import QtGui, QtWidgets, QtCore, QtUiTools
    _remap(QtCore, 'QStringListModel', QtGui.QStringListModel)
    _add(PySide2, '__binding__', PySide2.__name__)
    _add(PySide2, 'load_ui', lambda fname: QtUiTools.QUiLoader().load(fname))
    _add(PySide2, 'translate', lambda context, sourceText, disambiguation, n: QtCore.QCoreApplication.translate(context, sourceText, disambiguation, n))
    _add(PySide2, 'setSectionResizeMode', QtWidgets.QHeaderView.setSectionResizeMode)
    _maintain_backwards_compatibility(PySide2)
    return PySide2


def _pyqt5():
    """Setup PyQt5"""
    import PyQt5.Qt
    from PyQt5 import QtCore, QtWidgets, uic
    _remap(QtCore, 'Signal', QtCore.pyqtSignal)
    _remap(QtCore, 'Slot', QtCore.pyqtSlot)
    _remap(QtCore, 'Property', QtCore.pyqtProperty)
    _add(PyQt5, '__binding__', PyQt5.__name__)
    _add(PyQt5, 'load_ui', lambda fname: uic.loadUi(fname))
    _add(PyQt5, 'translate', lambda context, sourceText, disambiguation, n: QtCore.QCoreApplication.translate(context, sourceText, disambiguation, n))
    _add(PyQt5, 'setSectionResizeMode', QtWidgets.QHeaderView.setSectionResizeMode)
    _maintain_backwards_compatibility(PyQt5)
    return PyQt5


def _log(text, verbose):
    if verbose:
        sys.stdout.write(text + '\n')


def init():
    """Try loading each binding in turn

    Resolution order: PySide6 -> PySide2 -> PyQt5

    """
    preferred = os.getenv('QT_PREFERRED_BINDING')
    verbose = os.getenv('QT_VERBOSE') is not None
    bindings = (_pyside6, _pyside2, _pyqt5)

    if preferred:
        if preferred == 'None':
            self.__wrapper_version__ = self.__version__
            return
        preferred = preferred.split(os.pathsep)
        available = {
            'PySide6': _pyside6,
            'PySide2': _pyside2,
            'PyQt5': _pyqt5,
        }
        try:
            bindings = [available[binding] for binding in preferred]
        except KeyError:
            raise ImportError('Available preferred Qt bindings: ' + ', '.join(preferred))

    for binding in bindings:
        _log('Trying %s' % binding.__name__, verbose)
        try:
            binding = binding()
        except ImportError as e:
            _log(' - ImportError("%s")' % e, verbose)
            continue
        else:
            binding.__shim__ = self
            binding.QtCompat = self
            sys.modules.update({
                __name__: binding,
                __name__ + '.QtWidgets': binding.QtWidgets,
                __name__ + '.QtCore': binding.QtCore,
                __name__ + '.QtGui': binding.QtGui,
            })
            return

    raise ImportError('No Qt binding were found.')


def _maintain_backwards_compatibility(binding):
    """Add members found in prior versions"""
    for member in ('__binding__', '__binding_version__', '__qt_version__', '__added__',
                   '__remapped__', '__modified__', 'convert', 'load_ui', 'translate'):
        setattr(binding, member, getattr(self, member))
        self.__added__.append(member)

    setattr(binding, '__wrapper_version__', self.__version__)
    self.__added__.append('__wrapper_version__')


if __name__ != '__main__':
    init()
