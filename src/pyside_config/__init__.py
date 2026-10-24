"""
Persistent application settings for PySide6, declared as `attrs` classes and stored in `QSettings`.

Set the organization and application name (or call `configure`) before the first `@config` class is declared;
see `README.md` for a complete example.
"""

from pyside_config._core import (
    DESCRIPTION_KEY,
    EDITOR_KEY,
    QTYPE_KEY,
    ConfigInstance,
    ConfigSignals,
    EditorWidgetInfo,
    FieldInfo,
    clean,
    config,
    config_field,
    create_snapshot,
    get_config,
    groups,
    iter_fields,
    reset,
    restore_snapshot,
    save,
    signals,
    unregister,
    update_value,
)
from pyside_config._editor import create_editor
from pyside_config._hooks import DEFAULT_HOOKS, EditorHooks, hooks_for, register_editor_hooks
from pyside_config._settings import coerce, configure, settings
from pyside_config.properties import SETTER_KEY

__all__ = [
    "DEFAULT_HOOKS",
    "DESCRIPTION_KEY",
    "EDITOR_KEY",
    "QTYPE_KEY",
    "SETTER_KEY",
    "ConfigInstance",
    "ConfigSignals",
    "EditorHooks",
    "EditorWidgetInfo",
    "FieldInfo",
    "clean",
    "coerce",
    "config",
    "config_field",
    "configure",
    "create_editor",
    "create_snapshot",
    "get_config",
    "groups",
    "hooks_for",
    "iter_fields",
    "register_editor_hooks",
    "reset",
    "restore_snapshot",
    "save",
    "settings",
    "signals",
    "unregister",
    "update_value",
]
