import enum
from pathlib import Path
from typing import Any, cast

import attrs
import pytest
from conftest import reopen_store
from PySide6 import QtCore

import pyside_config as qconfig
from pyside_config import ConfigInstance, coerce, config, config_field, get_config


class Method(enum.StrEnum):
    Fast = "fast"
    Slow = "slow"


class Level(enum.IntEnum):
    Low = 1
    High = 2


def declare_group(name: str = "Demo", hidden: bool = False):
    @config(group_name=name, hidden=hidden)
    class Demo:
        count: int = config_field(default=3, description="A count")
        ratio: float = config_field(default=0.5)
        enabled: bool = config_field(default=False)
        method: Method = config_field(default=Method.Fast)
        level: Level = config_field(default=Level.Low)
        tags: list[str] = config_field(factory=list)
        blob: QtCore.QByteArray = config_field(factory=QtCore.QByteArray)
        maybe: int | None = config_field(default=None)
        converted: str = config_field(default="x", converter=str.upper)

    return Demo


# --- coerce -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "type_", "expected"),
    [
        ("5", int, 5),
        ("5.0", int, 5),
        (True, int, 1),
        ("true", bool, True),
        ("false", bool, False),
        ("0", bool, False),
        (1, bool, True),
        ("2.5", float, 2.5),
        (None, str, ""),
        (7, str, "7"),
        ("fast", Method, Method.Fast),
        ("Slow", Method, Method.Slow),
        ("2", Level, Level.High),
        (2, Level, Level.High),
        (None, list[str], []),
        ("one", list[str], ["one"]),
        ("", list[str], []),
        (["1", "2"], list[int], [1, 2]),
        (("a",), tuple[str, ...], ("a",)),
        (None, int | None, None),
        ("4", int | None, 4),
        ("b", str | None, "b"),
        (None, QtCore.QByteArray, QtCore.QByteArray()),
        (b"ab", QtCore.QByteArray, QtCore.QByteArray(b"ab")),
        ("c:/x", Path, Path("c:/x")),
        ("hi", str, "hi"),
    ],
)
def test_coerce(value, type_, expected):
    assert coerce(value, type_) == expected


@pytest.mark.parametrize(("value", "type_"), [("maybe", bool), ("x", int), ("nope", Method), (None, Method)])
def test_coerce_rejects(value, type_):
    with pytest.raises((ValueError, TypeError)):
        coerce(value, type_)


# --- declaration and registry --------------------------------------------------------------------------------------


def test_defaults_when_store_is_empty():
    Demo = declare_group()
    demo = get_config(Demo)
    assert demo.count == 3
    assert demo.method is Method.Fast
    assert demo.tags == []
    assert demo.blob == QtCore.QByteArray()
    assert demo.maybe is None
    assert get_config("Demo") is demo


def test_get_config_unknown():
    with pytest.raises(KeyError):
        get_config("Nope")

    class NotRegistered: ...

    with pytest.raises(KeyError):
        get_config(NotRegistered)


def test_duplicate_group_name_raises():
    declare_group()
    with pytest.raises(ValueError):
        declare_group()


def test_registration_does_not_write_defaults(fresh_store: QtCore.QSettings):
    declare_group()
    assert fresh_store.allKeys() == []


# --- assignment ----------------------------------------------------------------------------------------------------


def test_assignment_coerces_and_writes(fresh_store: QtCore.QSettings):
    demo = get_config(declare_group())
    raw = cast(Any, demo)  # assignments below are deliberately of the wrong static type
    raw.count = "7"
    raw.enabled = "true"
    raw.method = "slow"
    raw.level = "2"
    raw.tags = ("a", "b")
    assert demo.count == 7 and isinstance(demo.count, int)
    assert demo.enabled is True
    assert demo.method is Method.Slow
    assert demo.level is Level.High
    assert demo.tags == ["a", "b"]
    assert fresh_store.value("Demo/count") == 7
    assert fresh_store.value("Demo/method") == "slow"


def test_assignment_runs_converter():
    demo = get_config(declare_group())
    demo.converted = "abc"
    assert demo.converted == "ABC"


def test_assignment_rejects_bad_value():
    demo = get_config(declare_group())
    with pytest.raises(ValueError):
        cast(Any, demo).count = "many"
    assert demo.count == 3


def test_signal_emitted_on_change_only(qtbot):
    demo = get_config(declare_group())
    received: list[tuple[str, str, object]] = []
    qconfig.signals().sig_value_changed.connect(lambda g, k, v: received.append((g, k, v)))
    demo.count = 3  # unchanged
    demo.count = 4
    demo.method = Method.Slow
    qconfig.signals().sig_value_changed.disconnect()
    assert received == [("Demo", "count", 4), ("Demo", "method", Method.Slow)]


# --- persistence ---------------------------------------------------------------------------------------------------


def test_round_trip_through_ini(ini_path: Path):
    Demo = declare_group()
    demo = get_config(Demo)
    demo.count = 9
    demo.ratio = 1.25
    demo.enabled = True
    demo.method = Method.Slow
    demo.level = Level.High
    demo.tags = ["one"]  # one-element lists come back as a plain str from INI
    demo.blob = QtCore.QByteArray(b"\x00\x01geometry")
    demo.maybe = 12
    qconfig.save()

    qconfig.configure(lambda: QtCore.QSettings(str(ini_path), QtCore.QSettings.Format.IniFormat))
    reloaded = cast(Any, cast(type[ConfigInstance], Demo).from_qsettings())
    assert reloaded.count == 9
    assert reloaded.ratio == 1.25
    assert reloaded.enabled is True
    assert reloaded.method is Method.Slow
    assert reloaded.level is Level.High
    assert reloaded.tags == ["one"]
    assert reloaded.blob == QtCore.QByteArray(b"\x00\x01geometry")
    assert reloaded.maybe == 12


def test_corrupt_stored_value_falls_back_to_default(ini_path: Path, fresh_store: QtCore.QSettings):
    fresh_store.setValue("Demo/count", "garbage")
    fresh_store.setValue("Demo/method", "unknown")
    demo = get_config(declare_group())
    assert demo.count == 3
    assert demo.method is Method.Fast


def test_save_writes_everything(ini_path: Path):
    demo = get_config(declare_group())
    qconfig.save()
    store = reopen_store(ini_path)
    assert int(store.value("Demo/count")) == 3
    assert store.value("Demo/method") == "fast"
    assert demo.count == 3


def test_reset_and_clean(fresh_store: QtCore.QSettings):
    demo = get_config(declare_group())
    other = get_config(declare_group("Other"))
    demo.count = 5
    other.count = 6
    qconfig.reset(exclude=["Other"])
    assert demo.count == 3 and other.count == 6
    qconfig.clean(exclude=["Other"])
    assert fresh_store.childGroups() == ["Other"]
    qconfig.clean()
    assert fresh_store.allKeys() == []


def test_snapshot_round_trip():
    demo = get_config(declare_group())
    snapshot = qconfig.create_snapshot()
    demo.count = 50
    demo.method = Method.Slow
    qconfig.restore_snapshot(snapshot)
    assert demo.count == 3 and demo.method is Method.Fast


def test_update_value_errors():
    declare_group()
    with pytest.raises(ValueError):
        qconfig.update_value("Nope", "count", 1)
    with pytest.raises(ValueError):
        qconfig.update_value("Demo", "nope", 1)


# --- introspection -------------------------------------------------------------------------------------------------


def test_iter_fields_and_hidden():
    declare_group()
    declare_group("Secret", hidden=True)
    visible = list(qconfig.iter_fields(include_hidden=False))
    assert {f.group for f in visible} == {"Demo"}
    count = next(f for f in visible if f.name == "count")
    assert count.description == "A count" and count.default == 3 and count.type is int and count.label is None
    assert {f.group for f in qconfig.iter_fields()} == {"Demo", "Secret"}
    assert list(qconfig.groups()) == ["Demo", "Secret"]


def test_unregister():
    declare_group()
    qconfig.unregister("Demo")
    assert qconfig.groups() == {}
    declare_group()  # same name can be used again


def test_qtype_override(fresh_store: QtCore.QSettings):
    fresh_store.setValue("Q/value", "3")

    @config(group_name="Q")
    class Q:
        value: object = config_field(default=0, qtype=int)

    assert get_config(Q).value == 3


def test_plain_attrs_metadata_still_works():
    @config(group_name="Legacy")
    class Legacy:
        count: int = attrs.field(default=1, metadata={qconfig.DESCRIPTION_KEY: "legacy"})

    info = next(qconfig.iter_fields())
    assert info.description == "legacy" and get_config(Legacy).count == 1
