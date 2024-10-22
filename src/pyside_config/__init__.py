from PySide6 import QtWidgets

if not QtWidgets.QApplication.organizationName() or not QtWidgets.QApplication.applicationName():
    raise RuntimeError("App name and organization must be set before importing `pyside_config`.")

from ._pyside_config import (
    QTYPE_KEY,
    EditorWidgetInfo,
    clean,
    config,
    create_editor,
    create_snapshot,
    get_config,
    rename_config,
    reset,
    restore_snapshot,
    save,
    update_value,
)

__all__ = [
    "config",
    "get_config",
    "clean",
    "create_editor",
    "create_snapshot",
    "reset",
    "restore_snapshot",
    "save",
    "rename_config",
    "update_value",
    "EditorWidgetInfo",
    "QTYPE_KEY",
]
