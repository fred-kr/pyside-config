import inspect
import typing as t

import attrs
from attr._make import Factory
from bidict import bidict
from loguru import logger
from PySide6 import QtCore, QtGui, QtWidgets
from pyside_widgets import SettingCard

if t.TYPE_CHECKING:
    from .properties import WidgetPropertiesBase

QTYPE_KEY = "__qtype"  # This key's value should be a valid argument to the `type` argument of `QtCore.QSettings.value`


class ConfigInstance(attrs.AttrsInstance):
    """
    Protocol for a config class.
    """

    @classmethod
    def from_qsettings(cls) -> t.Self: ...

    def to_qsettings(self) -> None: ...

    def restore_defaults(self) -> None: ...

    def create_editor(self, **kwargs: t.Any) -> QtWidgets.QWidget: ...


config_registry: bidict[str, ConfigInstance] = bidict()


def register(config_class: t.Type[ConfigInstance], name: str | None = None, overwrite: bool = False) -> None:
    """
    Adds an instance of the provided config class to the `config_registry` dictionary.

    If an instance of the passed config class already exists as a value in the `config_registry` dictionary, the
    existing instance is removed. A new instance of the provided config class is created via its `from_qsettings` method
    and added to the `config_registry` dictionary with the provided name.

    Args:
        config_class (Type[ConfigInstance]): The config class to add to the `config_registry` dictionary.
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


def get(name: str) -> ConfigInstance:
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


@attrs.define
class EditorWidgetInfo[W: QtWidgets.QWidget]:
    label: str
    widget_factory: t.Callable[..., W]
    sig_value_changed: str
    set_value_method: str
    icon: QtGui.QIcon | None = None
    widget_properties: "WidgetPropertiesBase[W] | None" = None


def _get_setting_path(inst_or_cls: attrs.AttrsInstance | t.Type[attrs.AttrsInstance], attr: t.Any) -> str:
    """
    Generates a setting path string based on the class or instance and the provided attribute.

    Args:
        inst_or_cls (attrs.AttrsInstance | type[attrs.AttrsInstance]):
            The instance or class of the attrs-based class.
        attr (Any):
            The attribute whose name will be used to generate the path.

    Returns:
        str: The generated setting path in the format `ClassName/attribute_name`.
    """
    class_name = inst_or_cls.__name__ if inspect.isclass(inst_or_cls) else inst_or_cls.__class__.__name__
    return f"{class_name}/{attr.name}"


def update_qsettings[T](inst: attrs.AttrsInstance, attr: "attrs.Attribute[t.Any]", value: T) -> T:
    """
    Updates the QSettings with the specified attribute and value.

    Args:
        inst (attrs.AttrsInstance):
            The instance of the attrs-based class containing the attribute to update.
        attr (attrs.Attribute):
            The attribute being updated.
        value (T):
            The value to set for the given attribute, can be any type supported by QSettings.

    Returns:
        T: The value that was set in the settings.
    """
    path = _get_setting_path(inst, attr)
    settings = QtCore.QSettings()
    if path:
        settings.setValue(path, value)
        settings.sync()
    return value


def _get_field_default(field: "attrs.Attribute[t.Any]") -> t.Any | None:
    default = field.default
    return default.factory() if isinstance(default, Factory) else default  # type: ignore


def _from_qsettings(cls: t.Type[ConfigInstance]) -> ConfigInstance:
    settings = QtCore.QSettings()
    init_values = {}
    for field in attrs.fields(cls):
        path = _get_setting_path(cls, field)
        default = _get_field_default(field)
        qtype: type | None = field.metadata.get(QTYPE_KEY, None)
        if qtype is not None:
            value = settings.value(path, defaultValue=default, type=qtype)
        else:
            value = settings.value(path, defaultValue=default)
        init_values[field.name] = value
    return cls(**init_values)


def _to_qsettings(self: ConfigInstance) -> None:
    settings = QtCore.QSettings()
    for field in attrs.fields(self.__class__):
        path = _get_setting_path(self, field)
        value = getattr(self, field.name)
        settings.setValue(path, value)
    settings.sync()


def _restore_defaults(self: ConfigInstance) -> None:
    for field in attrs.fields(self.__class__):
        default = _get_field_default(field)
        setattr(self, field.name, default)


def _create_editor(self: ConfigInstance, **kwargs: t.Any) -> QtWidgets.QWidget:
    container_widget = QtWidgets.QWidget()

    layout = QtWidgets.QVBoxLayout(container_widget)
    layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignTop)

    for field in attrs.fields(self.__class__):
        editor_info: "EditorWidgetInfo[QtWidgets.QWidget] | None" = field.metadata.get("editor", None)
        if not editor_info:
            continue

        editor_widget = editor_info.widget_factory(**kwargs)
        editor_widget_properties = editor_info.widget_properties

        value = getattr(self, field.name)

        # Set the initial value of the editor
        getattr(editor_widget, editor_info.set_value_method)(value)

        # Update the config value whenever the editor's valueChanged (varies depending on the widget type) signal is emitted
        getattr(editor_widget, editor_info.sig_value_changed).connect(lambda val, f=field: setattr(self, f.name, val))

        if editor_widget_properties is not None:
            editor_widget_properties.apply_to_widget(editor_widget)

        description = field.metadata.get("description", None)

        card = SettingCard(
            title=editor_info.label, editor_widget=editor_widget, description=description, icon=editor_info.icon
        )
        layout.addWidget(card)

    return container_widget


def config_define(target_cls: type) -> t.Type[ConfigInstance]:
    """
    Extension of the `attrs.define` decorator that adds methods for interacting with QSettings and registers the class
    with the `config` module.
    """
    attrs_class = attrs.define(target_cls, eq=False, on_setattr=update_qsettings)

    attrs_class.from_qsettings = classmethod(_from_qsettings)
    attrs_class.to_qsettings = _to_qsettings
    attrs_class.restore_defaults = _restore_defaults
    attrs_class.create_editor = _create_editor

    register(attrs_class)

    return attrs_class
