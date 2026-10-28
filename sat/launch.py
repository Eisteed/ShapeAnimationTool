"""Load SAT from this folder, including after a stale Maya import."""
import importlib.util
from pathlib import Path
import sys
import types


def _load_source(package, folder, name):
    full_name = package.__name__ + '.' + name
    spec = importlib.util.spec_from_file_location(full_name, str(folder / (name + '.py')))
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get(full_name)
    sys.modules[full_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        if previous is None:
            sys.modules.pop(full_name, None)
        else:
            sys.modules[full_name] = previous
        raise
    module = sys.modules[full_name]
    setattr(package, name, module)
    return module


def show():
    folder = Path(__file__).resolve().parent
    package_name = 'sat'
    package = sys.modules.get(package_name)
    if package is None:
        package = types.ModuleType(package_name)
        sys.modules[package_name] = package
    package.__path__ = [str(folder)]
    package.__file__ = str(folder / '__init__.py')
    package.__package__ = package_name
    package.__spec__ = importlib.util.spec_from_file_location(
        package_name, package.__file__, submodule_search_locations=[str(folder)])

    qt = sys.modules.get(package_name + '.Qt')
    if qt is None:
        qt = _load_source(package, folder, 'Qt')
    package.Qt = qt

    # Close before replacing the class definitions used by existing windows.
    for widget in qt.QtWidgets.QApplication.topLevelWidgets():
        if (type(widget).__module__ == package_name + '.main'
                and type(widget).__name__ == 'MainWindow'):
            widget.close()
            widget.deleteLater()

    for name in ('utils', 'mainWindow', 'main'):
        _load_source(package, folder, name)

    global window
    window = package.main.MainWindow()
    window.connectSignals()
    window.start()
    window.show()
    print('SAT loaded from: ' + package.main.__file__)
    return window
