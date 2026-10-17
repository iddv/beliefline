"""The supported Python floor is 3.10, and pyproject and the README say the same thing.

Expected: pyproject.toml `requires-python` is ">=3.10" (so pip refuses 3.9) and the README
names "Python 3.10+" and no longer promises 3.9.
Source: issue #3, "Raise the Python floor to 3.10 (pyproject, README, charter)".
"""

import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_python_floor_is_3_10():
    m = re.search(r'^requires-python\s*=\s*"([^"]+)"', _read("pyproject.toml"), re.M)
    assert m, "pyproject.toml has no requires-python"
    assert m.group(1).replace(" ", "") == ">=3.10", "pyproject requires-python is %s, expected >=3.10" % m.group(1)
    readme = _read("README.md")
    assert "Python 3.10+" in readme, "README does not promise Python 3.10+"
    assert "Python 3.9" not in readme, "README still promises Python 3.9"
