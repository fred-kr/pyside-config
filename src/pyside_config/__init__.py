import typing as t

from .base import ConfigBase
from .registry import config_registry, new_config

__all__ = ["config_registry", "new_config", "register_config"]


def register_config(name: str, config_class: t.Type[ConfigBase]) -> None:
    config_registry.register_config(name, config_class)
