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


def ini_store(path: Path) -> QtCore.QSettings:
    return QtCore.QSettings(str(path), QtCore.QSettings.Format.IniFormat)


@pytest.fixture
def ini_path(tmp_path: Path) -> Path:
    return tmp_path / "settings.ini"


@pytest.fixture(autouse=True)
def fresh_store(ini_path: Path) -> Iterator[QtCore.QSettings]:
    """An empty INI store and an empty registry for the duration of one test."""
    pyside_config.configure(lambda: ini_store(ini_path))
    pyside_config.clear_registry()
    yield pyside_config.settings()
    pyside_config.clear_registry()
    pyside_config.configure(None)


@pytest.fixture
def changes() -> Iterator[list[tuple[str, str, object]]]:
    """Every `sig_value_changed` emission during the test, as `(group, name, value)`."""
    received: list[tuple[str, str, object]] = []

    def record(group: str, name: str, value: object) -> None:
        received.append((group, name, value))

    pyside_config.signals().sig_value_changed.connect(record)
    yield received
    pyside_config.signals().sig_value_changed.disconnect(record)


def restart(ini_path: Path) -> None:
    """Flushes the store, then drops it and the registry, as if the process had exited and started again."""
    pyside_config.sync()
    pyside_config.clear_registry()
    pyside_config.configure(lambda: ini_store(ini_path))
