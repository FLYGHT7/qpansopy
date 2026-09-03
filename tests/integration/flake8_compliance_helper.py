"""Shared helpers for the Flake8 store-compliance check.

Used by both ``tests/integration/test_flake8_compliance.py`` and
``tests/scripts/gen_flake8_baseline.py`` so the exact same command and parsing
feed the test and the baseline generator.

The command mirrors what the QGIS Plugin Repository scanner does — Flake8 with
the plugin's own ``setup.cfg`` — invoked with ``--config`` so config discovery
does not depend on the caller's working directory (see the qgis-plugin-store-
compliance skill, Phase 2 "Gotcha 1").
"""

import collections
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
PLUGIN_REL = "Q_Pansopy"
PLUGIN_DIR = REPO_ROOT / PLUGIN_REL
SETUP_CFG = PLUGIN_DIR / "setup.cfg"
BASELINE_FILE = REPO_ROOT / "tests" / "fixtures" / "flake8_baseline.txt"

_LINE_RE = re.compile(r"^(?P<path>.+?):\d+:\d+: (?P<code>\S+) ")


def flake8_available():
    """True when ``python -m flake8`` can run in this interpreter."""
    try:
        import flake8  # noqa: F401
    except ImportError:
        return False
    return True


def run_flake8():
    """Run Flake8 over the plugin and return its raw stdout (findings text)."""
    # Target passed relative (cwd=repo root) so Flake8 reports plugin-relative
    # paths; --config kept absolute so discovery is cwd-independent.
    proc = subprocess.run(
        [sys.executable, "-m", "flake8",
         "--jobs", "1", "--config", str(SETUP_CFG), PLUGIN_REL],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    # Flake8 exits 1 for findings, but an interpreter-level crash can also use
    # exit 1 and leave stdout empty. Never misread that as a clean scan.
    crashed = proc.returncode == 1 and not proc.stdout.strip()
    if proc.returncode not in (0, 1) or crashed:
        raise RuntimeError(
            "flake8 invocation failed (exit {}):\n{}{}".format(
                proc.returncode, proc.stdout, proc.stderr
            )
        )
    return proc.stdout


def parse_counts(flake8_stdout):
    """Aggregate findings text into a ``Counter`` keyed by (rel_path, code)."""
    counts = collections.Counter()
    for line in flake8_stdout.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        path = m.group("path").replace("\\", "/")
        prefix = "Q_Pansopy/"
        if path.startswith(prefix):
            path = path[len(prefix):]
        counts[(path, m.group("code"))] += 1
    return counts


def current_counts():
    return parse_counts(run_flake8())


def load_baseline(path=BASELINE_FILE):
    """Parse the committed baseline file into a ``Counter``."""
    counts = collections.Counter()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        location, _, code_and_count = line.partition(": ")
        code, _, count = code_and_count.partition(" ")
        counts[(location, code)] += int(count)
    return counts


def format_counts(counts):
    """Render a ``Counter`` back into baseline-file body lines (sorted)."""
    return "".join(
        "{}: {} {}\n".format(loc, code, n)
        for (loc, code), n in sorted(counts.items())
    )
