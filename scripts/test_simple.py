import pytest
from main_app import MainWindow

def test_init(qtbot):
    window = MainWindow()
    qtbot.add_widget(window)
    assert window is not None
