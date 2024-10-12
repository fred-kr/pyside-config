import inspect
import typing as t

import attrs
from attr._make import Factory
from attrs import NOTHING
from PySide6 import QtCore, QtGui, QtWidgets
from pyside_widgets import SettingCard

from . import config

if t.TYPE_CHECKING:
    from . import EditorWidgetInfo

SETTER_METADATA_KEY = "__setter"
NOTHING_TYPE = t.Literal[NOTHING]


def get_setting_path(inst_or_cls: attrs.AttrsInstance | t.Type[attrs.AttrsInstance], attr: t.Any) -> str:
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


def update_qsettings[T](inst: attrs.AttrsInstance, attr: t.Any, value: T) -> T:
    """
    Updates the QSettings with the specified attribute and value.

    Args:
        inst (attrs.AttrsInstance):
            The instance of the attrs-based class containing the attribute to update.
        attr (Any):
            The attribute being updated.
        value (T):
            The value to set for the given attribute, can be any type supported by QSettings.

    Returns:
        T: The value that was set in the settings.
    """
    path = get_setting_path(inst, attr)
    settings = QtCore.QSettings()
    if path:
        if isinstance(value, QtGui.QColor):
            settings.setValue(path, value.name())
        else:
            settings.setValue(path, value)
        settings.sync()
    return value


@attrs.define
class ConfigBase:
    @classmethod
    def __attrs_init_subclass__(cls) -> None:
        config.register(cls)

    @classmethod
    def from_qsettings(cls) -> t.Self:
        """
        Creates an instance of the config class and initializes it with values from QSettings. If no values are found in
        QSettings, the field's default value will be used.
        """
        settings = QtCore.QSettings()
        init_values = {}
        for field in attrs.fields(cls):
            path = get_setting_path(cls, field)
            value = settings.value(path, field.default)
            if isinstance(value, Factory):
                value = value.factory()  # type: ignore
            init_values[field.name] = value

        return cls(**init_values)

    def to_qsettings(self) -> None:
        """
        Saves the attributes of the current instance to QSettings.
        """
        settings = QtCore.QSettings()
        for field in attrs.fields(self.__class__):
            path = get_setting_path(self, field)
            value = getattr(self, field.name)
            settings.setValue(path, value)

        settings.sync()

    def restore_defaults(self) -> None:
        """
        Restores the default values for all attributes of the instance.
        """
        for field in attrs.fields(self.__class__):
            setattr(self, field.name, field.default)

        self.to_qsettings()

    def create_editor(
        self, *, style: t.Literal["fusion", "windows11", "windows"] | None = None, **kwargs: t.Any
    ) -> QtWidgets.QWidget:
        """
        Creates a dynamic editor interface for the class, populating it with widgets based on defined fields.

        Args:
            style (Literal["fusion", "windows11", "windows"] | None, optional): Style to use for the editor widget. If
                None, the default style of the application will be used.
            **kwargs: Additional keyword arguments passed to the widget factory.

        Returns:
            QtWidgets.QWidget: A QWidget containing the dynamically created editor interface.
        """
        container_widget = QtWidgets.QWidget()

        if style is not None:
            container_style = QtWidgets.QStyleFactory.create(style)
            container_widget.setStyle(container_style)

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
            getattr(editor_widget, editor_info.sig_value_changed).connect(
                lambda val, f=field: setattr(self, f.name, val)
            )

            if editor_widget_properties is not None:
                editor_widget_properties.apply_to_widget(editor_widget)

            description = field.metadata.get("description", None)

            card = SettingCard(
                title=editor_info.label, editor_widget=editor_widget, description=description, icon=editor_info.icon
            )

            layout.addWidget(card)

        return container_widget


@attrs.define
class WidgetPropertiesBase[W: QtWidgets.QWidget]:
    """
    Base class for widget properties.
    """

    styleSheet: str | None = attrs.field(default="", metadata={SETTER_METADATA_KEY: "setStyleSheet"})

    def apply_to_widget(self, widget: W) -> None:
        """
        Applies the current values of the class attributes to the specified widget.

        This method iterates through the fields of the class and sets the corresponding properties on the provided
        widget, using defined setter methods.

        Args:
            widget (W): The widget to which the attribute values will be applied.
        """
        for field in attrs.fields(self.__class__):
            property_value = getattr(self, field.name)
            if field.name == "styleSheet" and property_value == "":  # allow using None to clear a style sheet
                continue
            getattr(widget, field.metadata[SETTER_METADATA_KEY])(property_value)
