"""
Persistent application settings for PySide6, declared as `attrs` classes and stored in `QSettings`.

Set the organization and application name (or call `configure`) before the first `get_config` call; see
`README.md` for a complete example.
"""

from pyside_config._core import (
    ConfigSignals,
    FieldInfo,
    GroupInfo,
    clean,
    clear_registry,
    clear_store,
    config,
    config_field,
    get_config,
    group_info,
    groups,
    iter_fields,
    reload,
    reset,
    restore_defaults,
    save,
    signals,
    sync,
    unregister,
)
from pyside_config._editor import GroupPage, SettingsDialog, create_editor
from pyside_config._hooks import EditorHooks, register_editor_hooks
from pyside_config._settings import configure, settings

__all__ = [
    "ConfigSignals",
    "EditorHooks",
    "FieldInfo",
    "GroupInfo",
    "GroupPage",
    "SettingsDialog",
    "clean",
    "clear_registry",
    "clear_store",
    "config",
    "config_field",
    "configure",
    "create_editor",
    "get_config",
    "group_info",
    "groups",
    "iter_fields",
    "register_editor_hooks",
    "reload",
    "reset",
    "restore_defaults",
    "save",
    "settings",
    "signals",
    "sync",
    "unregister",
]
