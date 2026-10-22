"""The supported Python floor is 3.10, and pyproject, README and AGENTS.md agree.

Expected: pyproject's requires-python is ">=3.10"; the README and the AGENTS.md stack line
both say "Python 3.10+" and neither still promises 3.9.
Source: issue #3 "Raise the Python floor to 3.10 (pyproject, README, charter)".
"""

import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _read(name):
    with open(os.path.join(ROOT, name), encoding="utf-8") as f:
        return f.read()


def test_python_floor_is_3_10():
    m = re.search(r'requires-python\s*=\s*"([^"]+)"', _read("pyproject.toml"))
    assert m and m.group(1).replace(" ", "") == ">=3.10", "pyproject requires-python is %r, want >=3.10" % (m and m.group(1))
    for name in ("README.md", "AGENTS.md"):
        text = _read(name)
        assert "Python 3.10+" in text, "%s does not say Python 3.10+" % name
        assert "Python 3.9" not in text, "%s still promises Python 3.9" % name
