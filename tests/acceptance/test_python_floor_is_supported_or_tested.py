"""The Python version the project promises is either supported or tested in CI.

Expected: the minimum Python in pyproject's requires-python is not end of life
(3.10 or newer), or else the CI workflow runs that exact version. Today the floor
is 3.9 (EOL 2025-10-31) and CI only runs 3.12, so the promise is untested.
Source: "issue #3: Decide the Python floor: raise to 3.10+ or test 3.9 in CI"
"""

import os, re


def test_python_floor_is_supported_or_tested():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    py = open(os.path.join(root, "pyproject.toml")).read()
    m = re.search(r'requires-python\s*=\s*"\s*>=\s*(\d+)\.(\d+)', py)
    assert m, "pyproject.toml has no requires-python >=X.Y"
    floor = (int(m.group(1)), int(m.group(2)))
    wf = open(os.path.join(root, ".github", "workflows", "test.yml")).read()
    tested = {tuple(int(x) for x in v.split(".")[:2])
              for v in re.findall(r'(\d+\.\d+)(?:\.\d+)?', " ".join(re.findall(r'python-version[^\n]*(?:\n\s+-[^\n]*)*', wf)))}
    assert floor >= (3, 10) or floor in tested, \
        "requires-python floor %d.%d is end of life and not tested in CI (CI runs %s)" % (floor + (sorted(tested),))
