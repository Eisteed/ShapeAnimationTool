# Shape Animation Tool - Updated for Maya 2025 / Python 3
from . import main

sat_win = main.MainWindow()
sat_win.show()
sat_win.connectSignals()
sat_win.start()
