from PySide6 import QtWidgets

if not QtWidgets.QApplication.organizationName() or not QtWidgets.QApplication.applicationName():
    raise RuntimeError("App name and organization must be set before importing `pyside_config`.")

from .config import config_define

__all__ = ["config_define"]
