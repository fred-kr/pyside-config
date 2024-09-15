import enum
import typing as t

from PySide6 import QtCore, QtGui, QtWidgets

ItemDataRole = QtCore.Qt.ItemDataRole


class EnumComboBox[T: enum.Enum](QtWidgets.QComboBox):
    sig_current_enum_changed = QtCore.Signal(enum.Enum)

    def __init__(self, enum_class: t.Type[T], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._enum_class = enum_class
        self._enum_model = QtGui.QStandardItemModel(self)

        self.set_enum_class(enum_class)
        self.currentIndexChanged.connect(self._on_current_index_changed)

    def set_enum_class(
        self,
        enum_class: t.Type[T],
        text_data: t.Callable[[T], str] | None = None,
        icon_data: t.Callable[[T], QtGui.QIcon] | None = None,
    ) -> None:
        self._enum_model.clear()

        for enum_member in enum_class:
            name = text_data(enum_member) if text_data is not None else enum_member.name
            item = QtGui.QStandardItem(name)
            item.setData(enum_member, role=ItemDataRole.UserRole)
            if icon_data is not None:
                item.setIcon(icon_data(enum_member))
            self._enum_model.appendRow(item)

        self.setModel(self._enum_model)

    def current_enum(self) -> T | None:
        data = self.currentData(role=ItemDataRole.UserRole)
        return None if data not in self._enum_class else data

    def set_current_enum(self, value: T) -> None:
        index = self.findData(value, role=ItemDataRole.UserRole)
        if index >= 0:
            self.setCurrentIndex(index)

    @QtCore.Slot(int)
    def _on_current_index_changed(self, index: int) -> None:
        enum_member = self.current_enum()
        if enum_member is not None:
            self.sig_current_enum_changed.emit(enum_member)
