import typing as t

from bidict import ON_DUP_RAISE, OnDup, bidict
from PySide6 import QtCore, QtWidgets

from ._handlers import DEFAULT_EDITORS

if t.TYPE_CHECKING:
    from ._pyside_config import ConfigInstance


class ConfigManagerBase(QtCore.QObject):
    def __init__(
        self, configs: t.Iterable[type["ConfigInstance"]] | None = None, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)

        self._mutex = QtCore.QMutex()
        self._editor_registry = DEFAULT_EDITORS
        self._configs: bidict[str, type["ConfigInstance"]] = bidict()

        if configs is not None:
            self.register_configs(configs)

    def register_configs(self, configs: t.Iterable[type["ConfigInstance"]], *, on_dup: OnDup = ON_DUP_RAISE) -> None:
        self._configs.putall([(config.__group_prefix__, config) for config in configs], on_dup=on_dup)

    def register_config(self, config: type["ConfigInstance"], *, on_dup: OnDup = ON_DUP_RAISE) -> None:
        self._configs.put(config.__group_prefix__, config, on_dup=on_dup)

    def unregister_config(self, name: str) -> None:
        del self._configs[name]
