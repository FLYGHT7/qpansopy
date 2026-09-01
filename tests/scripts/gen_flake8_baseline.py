#!/usr/bin/env python3
"""Regenerate tests/fixtures/flake8_baseline.txt from the current tree.

Run this only after legitimately *reducing* Flake8 findings (fixing code or
adding a scoped, documented rule to Q_Pansopy/setup.cfg) — it rewrites the
ratchet that tests/integration/test_flake8_compliance.py enforces.

    python tests/scripts/gen_flake8_baseline.py
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from integration.flake8_compliance_helper import (  # noqa: E402
    BASELINE_FILE,
    current_counts,
    flake8_available,
    format_counts,
)

_HEADER = """\
# Flake8 compliance baseline for the Q_Pansopy plugin.
#
# Each line is:  <plugin-relative path>: <flake8 code> <count>
# i.e. the pre-existing findings that `flake8 --config=Q_Pansopy/setup.cfg Q_Pansopy`
# still reports, accepted as tracked tech debt (see setup.cfg "Unblocked by: TD-00x").
#
# tests/integration/test_flake8_compliance.py enforces this file:
#   - FAILS if a NEW (path, code) appears or an existing count grows  -> a regression;
#     new code must be flake8-clean under the plugin setup.cfg.
#   - FAILS if a listed finding disappears or a count shrinks         -> debt was paid
#     down; regenerate this file so the ratchet keeps the number honest.
#
# Regenerate after legitimately reducing findings:
#   python tests/scripts/gen_flake8_baseline.py
#
# Total: {total} findings.
"""


def main():
    if not flake8_available():
        sys.exit("flake8 is not installed; `pip install -r tests/requirements.txt`")
    counts = current_counts()
    body = format_counts(counts)
    BASELINE_FILE.write_text(
        _HEADER.format(total=sum(counts.values())) + body, encoding="utf-8"
    )
    print("Wrote {} ({} findings).".format(BASELINE_FILE, sum(counts.values())))


if __name__ == "__main__":
    main()
