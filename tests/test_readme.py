"""
Runs the README.

Every `python` block of `README.md` is joined, in order, into one script that runs in its own process. Its output
must equal the README's `text` blocks, joined in order. The script gets a temporary INI store and an event loop
that returns at once, because the first example calls `app.exec()`.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

README = Path(__file__).parent.parent / "README.md"

PREAMBLE = """\
import sys
from PySide6 import QtCore, QtWidgets
import pyside_config

pyside_config.configure(lambda: QtCore.QSettings(sys.argv[1], QtCore.QSettings.Format.IniFormat))
QtWidgets.QApplication.exec = lambda *args: 0

"""


def blocks(language: str) -> list[str]:
    return re.findall(rf"^```{language}\n(.*?)^```", README.read_text(encoding="utf-8"), flags=re.M | re.S)


def test_readme_examples_run_and_print_what_the_readme_shows(tmp_path: Path) -> None:
    script = tmp_path / "readme_examples.py"
    script.write_text(PREAMBLE + "\n".join(blocks("python")), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-W", "error::DeprecationWarning", str(script), str(tmp_path / "settings.ini")],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "".join(blocks("text"))
