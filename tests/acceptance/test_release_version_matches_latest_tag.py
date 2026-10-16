"""Release version matches the newest tag.

Checks: the version in pyproject.toml equals beliefline.__version__ and the
newest release (v* git tag, or the newest
CHANGELOG release heading when tags are not fetched).
Expected: all three agree, so a release is never tagged with a different
number than the one the package reports.
Source: issue #7 (drift check: version_tags).
"""

import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _key(tag):
    return tuple(int(x) for x in re.findall(r"\d+", tag))


def test_release_version_matches_latest_tag():
    with open(os.path.join(ROOT, "pyproject.toml")) as f:
        pyproject = re.search(r'^version\s*=\s*"([^"]+)"', f.read(), re.M).group(1)
    with open(os.path.join(ROOT, "beliefline", "__init__.py")) as f:
        init = re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)
    out = subprocess.run(["git", "tag", "--list", "v*"], cwd=ROOT,
                         capture_output=True, text=True).stdout.split()
    with open(os.path.join(ROOT, "CHANGELOG.md")) as f:
        out += re.findall(r"^## (\d+\.\d+\.\d+)\b", f.read(), re.M)
    assert out, "no release tags or changelog releases found"
    latest = max(out, key=_key).lstrip("v")
    assert pyproject == init, "pyproject version %s differs from __init__ %s" % (pyproject, init)
    assert pyproject == latest, "version %s does not match latest tag %s" % (pyproject, latest)
