# Testing Guide — Q_Pansopy

## Overview

Tests live in `tests/` at the project root. They run **without a QGIS installation** — a
stub layer in `conftest.py` replaces all QGIS imports so the pure-math and structural
parts of each module can be verified in a standard Python environment.

```
tests/
├── conftest.py        — QGIS stubs + load_cases fixture (shared by all tests)
├── pytest.ini         — configuration and markers
├── requirements.txt   — test dependencies
├── fixtures/
│   └── json/          — parametrized test cases (inputs + expected outputs)
├── unit/              — pure-math and smoke tests (fast, no QGIS)
├── integration/       — table/format tests (stub-based, slightly heavier)
└── scripts/           — standalone formula validators (not pytest)
```

---

## Prerequisites

Python 3.9+ and the test dependencies:

```bash
pip install -r tests/requirements.txt
```

---

## Running tests

All commands are run from `tests/`:

```bash
cd tests
```

| Goal | Command |
|------|---------|
| Run all tests | `pytest` |
| Unit tests only | `pytest unit/` |
| Integration tests only | `pytest integration/` |
| Single file | `pytest unit/test_pbn_target.py -v` |
| Single test | `pytest unit/test_pbn_target.py::test_15nm_buffer_radius_metres -v` |
| With coverage report | `pytest --cov=Q_Pansopy --cov-report=html` |
| Stop on first failure | `pytest -x` |
| Show print output | `pytest -s` |

---

## Test tiers

### `unit/` — Pure-math and smoke tests

These tests do not depend on QGIS geometry or layer creation. They verify:

- **Pure math functions**: ISA temperature, TAS, turn radius, splay widths, UTM zone selection.
- **Smoke imports**: every production module can be imported cleanly and exposes its `run_*` function.

| File | What it tests |
|------|---------------|
| `test_utils_calc.py` | `ISA_temperature()`, `tas_calculation()` in `wind_spiral.py` |
| `test_pbn_target.py` | UTM zone formula, buffer radii, `pbn_target` import |
| `test_pbn_modules.py` | All `lnav_*`, `gnss_waypoint`, `pbn_rnav1_arrival` smoke |
| `test_conv_math.py` | NDB 10.3° and VOR 7.8° splay formulas, conv module smoke |
| `test_sid.py` | `calculate_isa_temperature()`, `calculate_tas_and_turn_parameters()`, SID smoke |
| `test_utilities.py` | holding, conventional_holding_navaid, point_filter smoke |
| `test_kml_utils.py` | KML altitude fix utilities |
| `test_holding_compat.py` | Import compatibility for `holding.py` |
| `test_oas_globals.py` | OAS global state |
| `test_geometry_inputs.py` | Geometry input validation (mock-based) |

### `integration/` — Table and format tests

These tests import production modules (with QGIS stubs) and verify that parameter
tables and formatted output strings are well-formed:

`test_wind_spiral_table.py`, `test_vss_tables.py`, `test_basic_ils_table.py`,
`test_oas_ils_table.py`, `test_format_parameters_table.py`,
`test_selection_of_objects_table.py`, `test_oas_csv_parser_pytest.py`

### `scripts/` — Standalone validators

Not pytest tests. Run directly with Python to generate JSON reports in `scripts/results/`:

```bash
cd tests/scripts
python qpansopy_formula_validator_final.py
python simplified_formula_validator.py
python kml_altitude_checker.py path/to/file.kml
```

---

## JSON fixture format

Parametrized test cases are stored in `tests/fixtures/json/`. Each file is a JSON array:

```json
[
  {
    "id": "human-readable-test-id",
    "description": "What this case tests and why",
    "inputs": {
      "param1": 0.0,
      "param2": 15.0
    },
    "expected": {
      "result_field": 0.0,
      "tolerance": 0.05
    }
  }
]
```

- `id` — shown in pytest output as the test name.
- `tolerance` — absolute tolerance in the same unit as the result field.
- Add a `description` so the intent is clear when a test fails months later.

| Fixture file | Used by |
|---|---|
| `pbn_target_cases.json` | `test_pbn_target.py` — UTM zone + hemisphere |
| `conv_ndb_cases.json` | `test_conv_math.py` — NDB secondary width at distance |
| `conv_vor_cases.json` | `test_conv_math.py` — VOR secondary width at distance |
| `sid_isa_cases.json` | `test_sid.py` — ISA temperature at elevation |

---

## Adding tests for a new module

1. **Identify pure-math functions** in the module (inputs/outputs are numbers or
   plain Python, not `QgsGeometry` / `QgsVectorLayer`).

2. **Create a JSON fixture** in `tests/fixtures/json/<module>_cases.json` with at
   least: sea-level / standard case, one edge case, one realistic airport case.

3. **Create `tests/unit/test_<module>.py`** following this skeleton:

   ```python
   import importlib, json, pathlib, pytest

   _CASES = json.loads(
       (pathlib.Path(__file__).parent.parent / 'fixtures' / 'json' / '<module>_cases.json')
       .read_text(encoding='utf-8')
   )

   def _mod():
       return importlib.import_module('Q_Pansopy.modules.<path>.<module>')

   def test_module_imports_cleanly():
       assert _mod() is not None

   def test_main_function_exists():
       assert callable(getattr(_mod(), 'run_<module>', None))

   @pytest.mark.parametrize("case", _CASES, ids=[c["id"] for c in _CASES])
   def test_calculation(case):
       result = _mod().pure_math_function(**case["inputs"])
       tol = case["expected"]["tolerance"]
       assert abs(result - case["expected"]["value"]) <= tol
   ```

4. **Run the new tests**: `cd tests && pytest unit/test_<module>.py -v`

5. All tests must be green before opening a PR.

---

## What is NOT tested here

The main `run_*` function in every module creates `QgsVectorLayer`, adds features,
applies styles, and calls `QgsProject.instance().addMapLayers()`. These operations
require a live QGIS instance and cannot be exercised in this test suite.

To test these, load the plugin in QGIS, open the relevant dockwidget, and run the
calculation manually. The test plan in each PR document lists the manual steps.
