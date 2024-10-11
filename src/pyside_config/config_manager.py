import functools
import typing as t

import attrs
from loguru import logger
from PySide6 import QtCore, QtWidgets

if t.TYPE_CHECKING:
    from ._base import ConfigBase


__all__ = ["ConfigManager"]


def singleton[T](cls: t.Type[T]) -> t.Callable[..., T]:
    """
    A decorator that ensures a class is a singleton, meaning only one instance of the class exists.

    Args:
        cls (Type[T]): The class to be made a singleton.

    Returns:
        Callable[..., T]: A callable that returns the singleton instance of the class.
    """
    instances: dict[t.Type[T], T] = {}

    @functools.wraps(cls)
    def wrapper(*args: t.Any, **kwargs: t.Any) -> T:
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper


@singleton
class ConfigManager:
    __slots__ = ()

    _registry: dict[str, "ConfigBase"] = {}

    @classmethod
    def register(cls, config_class: t.Type["ConfigBase"], name: str | None = None) -> None:
        """
        Registers a configuration class with the ConfigManager.

        This method creates an instance of the config class, saves its default values to QSettings, and registers it
        under the specified name or the class name if no name is provided.

        Args:
            config_class (Type[ConfigBase]): The configuration class to register.
            name (str | None, optional): The name under which the config class is registered. If None, the class name
            will be used.
        """
        inst = config_class.from_qsettings()
        inst.to_qsettings()  # create default values if they don't yet exist in QSettings
        if name:
            cls._registry[name] = inst
        else:
            cls._registry[config_class.__name__] = inst

    @classmethod
    def save(cls) -> None:
        """
        Saves the current values of all registered configuration classes to QSettings.

        This method iterates over all registered configuration instances and saves their current values to the
        persistent QSettings store.
        """
        for inst in cls._registry.values():
            inst.to_qsettings()

    @classmethod
    def restore_defaults(cls, include: t.Iterable[str] | None = None) -> None:
        """
        Resets the values of the configs registered under the provided names to their default values.

        If no names are provided, all registered configs are reset to their default values.

        Args:
            include (Iterable[str] | None, optional): An iterable of config names to reset or `None` to reset all
            configs.
        """
        if not include:
            for config_class in cls._registry.values():
                config_class.restore_defaults()
        else:
            for name in include:
                if name not in cls._registry:
                    logger.warning(f"No config class registered with name '{name}'")
                    continue
                cls._registry[name].restore_defaults()

    @classmethod
    def create_editor_window(
        cls, parent: QtWidgets.QWidget | None = None, include: t.Iterable[str] | None = None
    ) -> QtWidgets.QDialog:
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

        for name, inst in cls._registry.items():
            if include and name not in include:
                continue
            editor = inst.create_editor()
            tab_widget.addTab(editor, name)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(tab_widget)
        layout.addWidget(btn_box)

        dlg.setLayout(layout)
        dlg.resize(800, 600)

        return dlg

    @classmethod
    def clean(cls, include: t.Iterable[str] | None = None) -> None:
        """
        Cleans QSettings by removing all settings or only specific registered config groups.

        If no `include` list is provided, all settings are cleared. Otherwise, only the settings related to the
        specified config names are removed.

        Args:
            include (Iterable[str] | None, optional): A list of registered config names to clean from QSettings. If
            None, all settings will be cleared.
        """
        qsettings = QtCore.QSettings()

        if not include:
            qsettings.clear()
        else:
            for name in include:
                if name not in cls._registry:
                    logger.warning(f"No config class registered with name '{name}'")
                    continue
                if name in qsettings.childGroups():
                    qsettings.remove(name)

        qsettings.sync()

    @classmethod
    def update_value(cls, group: str, key: str, value: t.Any) -> None:
        """
        Updates the value of a specific attribute in a registered configuration group.

        If the configuration group or attribute does not exist, an error is logged.

        Args:
            group (str): The name of the registered configuration group.
            key (str): The attribute name within the configuration group to update.
            value (Any): The new value to set for the specified attribute.
        """
        if group not in cls._registry:
            logger.error(f"No config class registered with name '{group}'")
            return

        if hasattr(cls._registry[group], key):
            setattr(cls._registry[group], key, value)
        else:
            logger.error(f"No attribute '{key}' in config class '{group}'")

        cls.save()

    @classmethod
    def create_snapshot(cls) -> dict[str, t.Any]:
        """
        Creates a snapshot of the current state of all registered configuration groups.

        The snapshot contains the current values of all attributes in each configuration group.

        Returns:
            dict[str, Any]: A dictionary where keys are the names of registered configuration groups and values are
            dictionaries representing the current state of each group's attributes.
        """
        return {key: attrs.asdict(inst) for key, inst in cls._registry.items()}

    @classmethod
    def restore_snapshot(cls, snapshot: dict[str, t.Any]) -> None:
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
                cls.update_value(grp, key, value)
