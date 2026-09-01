"""Store-compliance guard: keep Flake8 findings from growing.

The QGIS Plugin Repository runs Flake8 on every uploaded plugin; a rising count
delays approval. Instead of re-running the qgis-plugin-store-compliance skill by
hand, this test runs the same check (``flake8 --config=Q_Pansopy/setup.cfg
Q_Pansopy``) and compares it against ``tests/fixtures/flake8_baseline.txt``:

* new code that is not Flake8-clean -> ``test_no_new_flake8_findings`` fails;
* debt paid down without updating the baseline -> ``test_flake8_baseline_is_tight``
  fails, telling you to regenerate it (ratchet).
"""

import pytest

from .flake8_compliance_helper import (
    BASELINE_FILE,
    current_counts,
    flake8_available,
    format_counts,
    load_baseline,
)

pytestmark = pytest.mark.integration

_SKIP_NO_FLAKE8 = "flake8 is not installed (see tests/requirements.txt)"


@pytest.fixture(scope="module")
def counts():
    if not flake8_available():
        pytest.skip(_SKIP_NO_FLAKE8)
    return current_counts()


def _delta_lines(delta):
    return "\n".join(
        "  {}: {} {:+d}".format(loc, code, n)
        for (loc, code), n in sorted(delta.items())
    )


def test_no_new_flake8_findings(counts):
    """Every finding present now must already be in the baseline."""
    baseline = load_baseline()
    new = counts - baseline  # Counter subtraction drops zero/negative entries
    assert not new, (
        "New Flake8 findings not in {}:\n{}\n\n"
        "New code must pass `flake8 --config=Q_Pansopy/setup.cfg Q_Pansopy`. "
        "Fix the finding, or (only for accepted tech debt) add a scoped rule to "
        "Q_Pansopy/setup.cfg per-file-ignores with an 'Unblocked by:' note."
    ).format(BASELINE_FILE.name, _delta_lines(new))


def test_flake8_baseline_is_tight(counts):
    """The baseline must not over-count: shrink it whenever debt is paid down."""
    baseline = load_baseline()
    resolved = baseline - counts
    assert not resolved, (
        "These baselined Flake8 findings are gone or reduced:\n{}\n\n"
        "Nice — now regenerate the baseline so the ratchet stays honest:\n"
        "  python tests/scripts/gen_flake8_baseline.py\n"
        "Expected new baseline body:\n{}"
    ).format(_delta_lines(resolved), format_counts(counts))
