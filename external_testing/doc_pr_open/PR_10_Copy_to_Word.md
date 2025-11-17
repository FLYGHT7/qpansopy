# PR: Copy to Word – Structured table using output feature parameters (Issue #10)

Status: Verified (2025-11-16)
Type: Enhancement / UX
Issue: Copy to Word (#10)

## Summary

Implements a Word-friendly, structured table for "Copy to Word" that prefers reading parameters from the output feature field `parameters`, matching the behavior of the PANS-OPS web calculator. This reduces manual reformatting and ensures the copied values reflect the last calculation results on the map.

## Changes

- Wind Spiral Dockwidget (`Q_Pansopy/dockwidgets/utilities/qpansopy_wind_spiral_dockwidget.py`):
  - Enhanced `copy_parameters_for_word()` to:
    - Scan project vector layers for a `parameters` field containing `calculation_type = "Wind Spiral"`.
    - Parse JSON and feed values to `modules.wind_spiral.copy_parameters_table()` to produce a formatted table (PARAMETER | VALUE | UNIT).
    - Fallback to current UI values only if no suitable layer/feature is found.
  - Result: The copied table is consistent, ready for Word, and sourced from the generated output by default.
- Existing modules already aligned:
  - Basic ILS Dockwidget reads `parameters` from output layers and formats a Word table.
  - OAS ILS Dockwidget reads `parameters` from output layers and formats a Word table.
  - VSS currently formats from UI values; layer-backed copy can be added later if needed (not required by this issue).

## Rationale

- Aligns desktop plugin behavior with the PANS-OPS web calculator: one-click, ready-to-paste tables.
- Pulls from output features to avoid discrepancy between UI state and generated results.

## How to Test

1. Generate a Wind Spiral (ensure it creates a layer with a `parameters` field).
2. Click "Copy for Word" in the Wind Spiral dockwidget.
3. Paste in Word (or any editor) and validate the table:
   - Heading: "QPANSOPY WIND SPIRAL PARAMETERS".
   - Rows like:
     - Aerodrome Elevation | value | ft/m
     - Temperature Reference | value | °C
     - ISA Calculated | value | °C
     - ISA Variation | value | °C
     - IAS | value | kt
     - Altitude | value | ft/m
     - Bank Angle | value | °
     - Wind Speed | value | kt
     - Turn Direction | value | (no unit)
4. Optional: Delete/rename the output layer and retry. The function will fall back to the current UI values.

## Acceptance Criteria Checklist

- [x] Copy to Word outputs a structured table (PARAMETER | VALUE | UNIT).
- [x] Wind Spiral copy prefers reading from the output layer `parameters` field.
- [x] If no output layer is found, function falls back to current UI values.
- [x] No regressions in Basic ILS and OAS ILS copy-to-Word behavior.

## Verification

- Wind Spiral: Verified. `copy_parameters_for_word()` in `Q_Pansopy/dockwidgets/utilities/qpansopy_wind_spiral_dockwidget.py` prioritizes reading `parameters` from the generated layer (with `calculation_type = "Wind Spiral"`). Pasting into Word shows the header "QPANSOPY WIND SPIRAL PARAMETERS" and the expected rows (Aerodrome Elevation, Temperature Reference, ISA Calculated, ISA Variation, IAS, Altitude, Bank Angle, Wind Speed, Turn Direction). If the layer is removed/renamed, it falls back to UI values.
- Basic ILS: Verified. `copy_parameters_for_word()` in `Q_Pansopy/dockwidgets/ils/qpansopy_ils_dockwidget.py` reads `parameters` and builds a ready-to-paste Word table, including units and surface type when available.
- OAS ILS: Verified. `copy_parameters_for_word()` in `Q_Pansopy/dockwidgets/ils/qpansopy_oas_ils_dockwidget.py` reads `parameters` and builds a table with the expected mappings and units.
- VSS: Out of scope for #10. It generates a table from UI values. Layer-backed copy can be added later if we want a unified behavior.

## Testing Instructions

These tests run without QGIS installed by using lightweight stubs for `qgis.*` imports.

1. Create and activate a virtual environment (Windows PowerShell):

```powershell
cd "C:\Users\andre_27o\Desktop\qpansopy"
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
```

2. Install test dependencies directly (recommended to avoid extras):

```powershell
python -m pip install pytest==7.4.4 pytest-cov==4.1.0 numpy==1.24.3
```

3. Run the test suite:

```powershell
pytest -q external_testing\tests
```

4. Run a focused subset (examples):

```powershell
# Only table formatter tests
pytest -q external_testing\tests -k format_parameters_table

# Only Wind Spiral table tests
pytest -q external_testing\tests -k wind_spiral

# Only OAS CSV parser tests
pytest -q external_testing\tests -k oas_csv
```

Notes:

- The file `external_testing/tests/conftest.py` installs QGIS stubs during tests, so importing `Q_Pansopy.modules.*` works without a QGIS runtime.
- If you prefer to use the requirements file and encounter issues, install the three packages explicitly as shown above.

## Extending Tests to Other Modules

- Add new tests under `external_testing/tests/` following the existing style:
  - `test_wind_spiral_table.py` validates Word-table output for Wind Spiral.
  - `test_basic_ils_table.py` validates Word-table output for Basic ILS.
  - `test_oas_csv_parser_pytest.py` validates the CSV constants parser.
- To drive tests from JSON (as proposed in Issue #31), place JSON files under `external_testing/test_data/` and load them in tests, e.g.:

```python
import json, pathlib
case = json.loads(pathlib.Path("external_testing/test_data/my_case.json").read_text())
# pass case["params"] into the module function and assert against case["expected_results"]
```

- For VSS and OAS ILS Word tables, mirror the Wind Spiral and Basic ILS tests by calling their `copy_parameters_table` (if available) or verifying the dockwidgets’ formatting helpers.

## Notes

- The formatter uses `modules.wind_spiral.copy_parameters_table()` and `utils.format_parameters_table` to maintain consistent layout across tools.
- If desired, a similar layer-backed copy can be added to VSS in a follow-up; not required to close this issue.
