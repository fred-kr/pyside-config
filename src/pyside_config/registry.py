import typing as t

from .base import ConfigBase


class ConfigRegistry:
    def __init__(self) -> None:
        self._configs: dict[str, ConfigBase] = {}

    def register_config(self, name: str, config_class: t.Type[ConfigBase]) -> None:
        self._configs[name] = config_class.from_qsettings()

    def get_config(self, name: str) -> ConfigBase:
        return self._configs[name]

    def update_value(self, group: str, key: str, value: t.Any) -> None:
        if group not in self._configs:
            return

        config = self._configs[group]
        if hasattr(config, key):
            setattr(config, key, value)
            config.to_qsettings()

    def save_all(self) -> None:
        for config in self._configs.values():
            config.to_qsettings()

    def reset_all(self) -> None:
        for config in self._configs.values():
            config.restore_defaults()


config_registry = ConfigRegistry()
del ConfigRegistry
