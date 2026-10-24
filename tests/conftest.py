"""
Every test gets an empty INI-backed `QSettings` in a temporary directory and an empty registry.

`pyside_config.configure` injects the store, so no organization or application name is needed and the tests never
touch the user's real settings. Widgets run on the `offscreen` platform plugin (pytest-qt's `qtbot` fixture
creates the `QApplication`).
"""

import os
from collections.abc import Iterator
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6 import QtCore

import pyside_config
from pyside_config import _core


@pytest.fixture
def ini_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.ini"


@pytest.fixture(autouse=True)
def fresh_store(ini_path: Path) -> Iterator[QtCore.QSettings]:
    """An empty INI store and an empty registry for the duration of one test."""
    pyside_config.configure(lambda: QtCore.QSettings(str(ini_path), QtCore.QSettings.Format.IniFormat))
    _core._registry.clear()
    _core._class_names.clear()
    yield pyside_config.settings()
    _core._registry.clear()
    _core._class_names.clear()
    pyside_config.configure(None)


def reopen_store(ini_path: Path) -> QtCore.QSettings:
    """Flushes the current store and returns a new `QSettings` reading the same file, as a fresh process would."""
    pyside_config.settings().sync()
    return QtCore.QSettings(str(ini_path), QtCore.QSettings.Format.IniFormat)
