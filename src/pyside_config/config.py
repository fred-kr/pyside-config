import typing as t

import attrs
from bidict import bidict
from loguru import logger
from PySide6 import QtCore, QtWidgets

if t.TYPE_CHECKING:
    from ._base import ConfigBase

config_registry: bidict[str, "ConfigBase"] = bidict()


def register(config_class: t.Type["ConfigBase"], name: str | None = None, overwrite: bool = False) -> None:
    """
    Adds an instance of the provided config class to the `config_registry` dictionary.

    If an instance of the passed config class already exists as a value in the `config_registry` dictionary, the
    existing instance is removed. A new instance of the provided config class is created via its `from_qsettings` method
    and added to the `config_registry` dictionary with the provided name.

    Args:
        config_class (Type[ConfigBase]): The config class to add to the `config_registry` dictionary.
        name (str | None, optional): The name under which the config class is registered. If None, the class name
        will be used.
        overwrite (bool, optional): Whether to overwrite an existing config class with the same name. Defaults to
        False.
    """
    name = name or config_class.__name__
    config_instance = config_class.from_qsettings()

    if name in config_registry and overwrite or name not in config_registry:
        config_registry[name] = config_instance
    else:
        logger.error(f"'{name}' already used for '{config_registry[name]}'.")
        return


def get(name: str) -> "ConfigBase":
    """
    Returns the config class registered under the provided name.

    Args:
        name (str): The name of the config class.

    Returns:
        Config: The config class registered under the provided name.
    """
    return config_registry[name]


def update_name(old_name: str, new_name: str) -> None:
    """
    Updates the name under which a config class is registered.

    Args:
        old_name (str): The old name of the config class.
        new_name (str): The new name of the config class.
    """
    if old_name not in config_registry:
        logger.error(f"No config class registered with name '{old_name}'")
        return
    config_registry[new_name] = config_registry.pop(old_name)


def save() -> None:
    """
    Saves the current values of all registered configuration classes to QSettings.
    """
    for config_class in config_registry.values():
        config_class.to_qsettings()


def reset(include: t.Iterable[str] | None = None) -> None:
    """
    Resets the values of the configs registered under the provided names to their default values.

    If no names are provided, all registered configs are reset to their default values.

    Args:
        include (Iterable[str] | None, optional): An iterable of config names to reset or `None` to reset all
        configs.
    """
    if not include:
        for config_class in config_registry.values():
            config_class.restore_defaults()
    else:
        for name in include:
            if name not in config_registry:
                logger.warning(f"No config class registered with name '{name}'")
                continue
            config_registry[name].restore_defaults()


def clean(include: t.Iterable[str] | None = None) -> None:
    """
    Cleans QSettings by removing all settings or only specific registered config groups.

    If no `include` list is provided, all settings are cleared. Otherwise, only the settings related to the
    specified config names are removed.

    Args:
        include (Iterable[str] | None, optional): A list of registered config names to clean from QSettings. If
        None, all settings will be cleared.
    """
    if not QtWidgets.QApplication.instance():
        raise RuntimeError("QApplication is not initialized")
    qsettings = QtCore.QSettings()

    if not include:
        qsettings.clear()
    else:
        for name in include:
            if name not in config_registry:
                logger.warning(f"No config class registered with name '{name}'")
                continue
            if name in qsettings.childGroups():
                qsettings.remove(name)

    qsettings.sync()


def available() -> list[str]:
    """
    Get a list of all currently registered config names.

    Returns:
        list[str]: A list of all registered config names.
    """
    return list(config_registry.keys())


def update_value(group: str, key: str, value: t.Any) -> None:
    """
    Updates the value of the config class registered under the provided name.

    Args:
        name (str): The name of the config class.
        value (Any): The new value to set.
    """
    if group not in config_registry:
        logger.error(f"No config class registered with name '{group}'")
        return

    if hasattr(config_registry[group], key):
        setattr(config_registry[group], key, value)
    else:
        logger.error(f"No attribute '{key}' in config class '{group}'")

    save()


def create_snapshot() -> dict[str, t.Any]:
    """
    Creates a snapshot of the current state of all registered configuration groups.

    The snapshot contains the current values of all attributes in each configuration group.

    Returns:
        dict[str, Any]: A dictionary where keys are the names of registered configuration groups and values are
        dictionaries representing the current state of each group's attributes.
    """
    return {key: attrs.asdict(inst) for key, inst in config_registry.items()}


def restore_snapshot(snapshot: dict[str, t.Any]) -> None:
    """
    Restores the state of all registered configuration groups from a snapshot.

    The snapshot should be a dictionary where keys are group names and values are dictionaries representing the
    state of the group's attributes. Each attribute in the snapshot is restored to its value in the provided
    snapshot.

    Args:
        snapshot (dict[str, Any]): A dictionary representing the snapshot of the configuration groups' state to
        restore.
    """
    for grp, grp_dict in snapshot.items():
        for key, value in grp_dict.items():
            update_value(grp, key, value)


def create_editor(parent: QtWidgets.QWidget | None = None, include: t.Iterable[str] | None = None) -> QtWidgets.QDialog:
    """
    Creates a QDialog with tabs for each registered config class.

    If no `include` list is provided, all registered configs are created. Otherwise, only the configs related
    to the specified config names are created.

    Args:
        parent (QtWidgets.QWidget | None, optional): The parent widget for the dialog. Defaults to None.
        include (Iterable[str] | None, optional): An iterable of config names to create editors for or `None` to
        create editors for all registered configs.

    Returns:
        QtWidgets.QDialog: A QDialog with tabs for each registered config class.
    """
    dlg = QtWidgets.QDialog(parent)
    dlg.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    dlg.setModal(True)
    dlg.setWindowTitle("Settings")

    btn_box = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
    )
    btn_box.accepted.connect(dlg.accept)
    btn_box.rejected.connect(dlg.reject)

    tab_widget = QtWidgets.QTabWidget()
    for name, inst in config_registry.items():
        if not include or name in include:
            tab = inst.create_editor()
            tab_widget.addTab(tab, name)

    layout = QtWidgets.QVBoxLayout()
    layout.addWidget(tab_widget)
    layout.addWidget(btn_box)

    dlg.setLayout(layout)
    dlg.resize(800, 600)

    return dlg
