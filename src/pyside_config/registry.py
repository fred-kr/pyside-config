import functools
import typing as t

from loguru import logger
from PySide6 import QtCore, QtWidgets

if t.TYPE_CHECKING:
    from .base import ConfigBase


__all__ = ["ConfigRegistry"]


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
class ConfigRegistry:
    __slots__ = ()

    _registry: dict[str, "ConfigBase"] = {}

    @classmethod
    def register(cls, config_class: t.Type["ConfigBase"], name: str | None = None) -> None:
        """
        Registers a configuration class in the registry.

        This method creates an instance of the config class, saves its default values to QSettings,
        and registers it under the specified name or the class name if no name is provided.

        Args:
            config_class (Type[ConfigBase]): The configuration class to register.
            name (str | None, optional): The name under which the config class is registered.
                If None, the class name will be used.
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

        This method iterates over all registered configuration instances and saves their
        current values to the persistent QSettings store.
        """
        for inst in cls._registry.values():
            inst.to_qsettings()

    @classmethod
    def restore_defaults(cls, include: t.Iterable[str] | None = None) -> None:
        """
        Restores the default values for the specified or all registered configuration classes.

        Args:
            include (Iterable[str] | None, optional): A list of registered config names for which
                to restore defaults. If None, the defaults for all registered configurations are restored.
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
    def create_dialog(
        cls, parent: QtWidgets.QWidget | None = None, include: t.Iterable[str] | None = None
    ) -> QtWidgets.QDialog:
        """
        Creates a QDialog with tabs containing inputs for each registered configuration class.

        Each registered configuration class will have its own tab in the dialog, where users can
        edit the configuration values.

        Args:
            parent (QtWidgets.QWidget | None, optional): The parent widget for the dialog.
                Defaults to None.
            include (Iterable[str] | None, optional): A list of registered config names for which
                to create an editor tab. If None, tabs for all registered configs are created.

        Returns:
            QtWidgets.QDialog: A dialog window that allows the user to edit configuration settings.
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

        If no `include` list is provided, all settings are cleared. Otherwise, only the settings
        related to the specified config names are removed.

        Args:
            include (Iterable[str] | None, optional): A list of registered config names to clean
                from QSettings. If None, all settings will be cleared.

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
