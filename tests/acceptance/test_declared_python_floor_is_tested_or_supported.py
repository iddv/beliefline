"""The Python version Beliefline promises is either supported or tested in CI.

Expected: the floor in pyproject.toml's requires-python (which the README also
states) is a version CI actually runs, or is not end of life. Python 3.9 reached
end of life on 2025-10-31, so a 3.9 floor needs a 3.9 job in the CI matrix;
otherwise the floor must be raised (to 3.10+) with README and pyproject agreeing.
Source: issue #3 "Decide the Python floor: raise to 3.10+ or test 3.9 in CI"
"""

import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EOL_BELOW = (3, 10)  # 3.9 is end of life since 2025-10-31


def _read(*p):
    with open(os.path.join(ROOT, *p)) as f:
        return f.read()


def test_declared_python_floor_is_tested_or_supported():
    m = re.search(r'requires-python\s*=\s*"\s*>=\s*(\d+)\.(\d+)', _read("pyproject.toml"))
    assert m, "pyproject.toml has no requires-python >=X.Y"
    floor = (int(m.group(1)), int(m.group(2)))
    readme = re.search(r"Python (\d+)\.(\d+)\+", _read("README.md"))
    assert readme and (int(readme.group(1)), int(readme.group(2))) == floor, \
        "README Python version disagrees with pyproject requires-python"
    ci = _read(".github", "workflows", "test.yml")
    tested = {(int(a), int(b)) for a, b in re.findall(r'["\']?(\d+)\.(\d+)["\']?', ci)}
    assert floor >= EOL_BELOW or floor in tested, \
        "declared Python floor %d.%d is end of life and not tested in CI" % floor
