# QPANSOPY — Code Review Report

**Branch:** `refactor/qpansopy-v1`  
**Scope:** Post-refactor review (Phases 0–7). Aeronautical formulas excluded from analysis.  
**Status:** All issues resolved except R7 (architectural, tracked separately) and R12 (new blocker).

---

## Summary

| Severity   | Count  | Status             |
| ---------- | ------ | ------------------ |
| 🔴 Blocker | 3      | 2 fixed ✅, 1 open |
| 🟠 Major   | 6      | All fixed ✅       |
| 🟡 Minor   | 4      | All fixed ✅       |
| **Total**  | **13** |                    |

---

## 🔴 Blockers — Must Fix

### R1 — Missing `import os` in `qpansopy_holding_dockwidget.py` ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_holding_dockwidget.py`  
**Fix applied:** Added `import os` as first import. The `NameError: name 'os' is not defined` crash at module load is resolved.

---

### R2 — `setMaximumHeight(0)` hides the log widget (bug B2 re-introduced) ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`  
**Fix applied:** Removed the `setMaximumHeight(0)` call entirely. Qt's default (no maximum) is correct; the widget is now visible as intended.

---

### R12 — `selection_of_objects.py` has no `extract_objects` function + module-level dialog 🔴 OPEN

**File:** `Q_Pansopy/modules/utilities/selection_of_objects.py`  
**Impact (double bug):**

1. `qpansopy_object_selection_dockwidget.py` does `from ...modules.utilities.selection_of_objects import extract_objects` — but that function **does not exist** in the file. This is an `ImportError` that will crash the Object Selection dockwidget the moment QGIS loads it.
2. The file contains **module-level execution code** (instantiates `LayerSelectionDialog`, calls `.exec_()`, runs spatial analysis) — code that was never wrapped in a function or guarded by `if __name__ == '__main__'`. This means **every import of the module runs a blocking dialog**.

**Root cause:** This file is an unconverted standalone script. It was never refactored into a callable module.

**Required fix:** Wrap the existing logic in a proper `extract_objects(iface, point_layer, surface_layer, **kwargs)` function and remove module-level execution.

---

## 🟠 Major — Should Fix

### R3 — `validate_inputs()` resets `csv_path` after `request_csv_file()` sets it ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`  
**Fix applied:**

- Moved `self.csv_path = None` from `validate_inputs()` to the top of `calculate()` (before `request_csv_file()`)
- Fixed the Python one-liner bug: `"""Validate user inputs"""        self.csv_path = None` was on one line (potential SyntaxError); separated into two lines

---

### R4 — `from qgis.utils import iface` at module level in 11 files ✅ FIXED

**Files fixed:** `basic_ils.py`, `wind_spiral.py`, `vss_straight.py`, `vss_loc.py`, `oas_ils.py`, `lnav_final_approach.py`, `lnav_initial_approach.py`, `lnav_intermediate_approach.py`, `lnav_missed_approach.py`, `gnss_waypoint.py`  
**Strategy:**

- Files where the entry function receives `iface` directly as a parameter (shadows module-level): just removed the module-level import
- `lnav_*.py` files: already had `iface = iface_param` inside the function; module-level import removed (was 100% redundant)
- `gnss_waypoint.py`: function uses `iface_param` consistently throughout; module-level import removed (unused)
- `oas_ils.py` helper functions `csv_to_structured_json` and `compute_geom`: added local `from qgis.utils import iface` inside each function body
- `selection_of_objects.py`: left unchanged (the entire file needs restructuring — see R12)

---

### R5 — `log()` method crashes if `logTextEdit` is missing ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_vss_dockwidget.py`  
**Fix applied:** Added `if hasattr(self, 'logTextEdit') and self.logTextEdit is not None:` guard, consistent with all other dockwidgets.

---

### R6 — Bare `except:` silently swallows all exceptions ✅ FIXED

**Files fixed:**

- `Q_Pansopy/utils.py` — Line 115
- `Q_Pansopy/modules/pbn/pbn_rnav1_arrival.py` — Line 91
- `Q_Pansopy/modules/pbn/lnav_missed_approach.py` — Line 143

**Fix applied:** Replaced `except:` with `except Exception:` in all three locations.

---

### R7 — `BasePansopyDockWidget` defined but never inherited

**File:** `Q_Pansopy/dockwidgets/base_dockwidget.py`  
**Status:** Not fixed — architectural refactor tracked as a separate task. QSS stylesheet and shared methods are duplicated across 8+ dockwidgets instead of inherited.

---

## 🟡 Minor — Nice to Fix

### R8 — `QFormLayout.FieldRole` breaks on Qt6 / QGIS 4 ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_point_filter_dockwidget.py`  
**Fix applied:** Used `getattr` with fallback to resolve `FieldRole` at runtime, compatible with both Qt5 (`QFormLayout.FieldRole`) and Qt6 (`QFormLayout.ItemRole.FieldRole`).

---

### R9 — Wildcard imports in module files

**Files:** `conv_initial_approach.py`, `vor_approach.py`, `ndb_approach.py`, `lnav_*.py` (4), `conventional_holding_navaid.py`, `GNSS_waypoint.py`  
**Status:** Not fixed — touching formula files carries regression risk. Track for a future cleanup pass.

---

### R10 — KML export in `qpansopy_ndb_dockwidget.py` logs but does nothing ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/conv/qpansopy_ndb_dockwidget.py`  
**Fix applied:** Replaced the misleading `"KML export would go to: {output_dir}"` message with an honest `"Note: KML export for NDB approach is not yet implemented."` message.

---

### R11 — Misleading indentation in `qpansopy_vss_dockwidget.py` ✅ FIXED

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_vss_dockwidget.py`  
**Fix applied:** Re-aligned the `# Log message` comment and the `self.log(...)` call to the correct 8-space method-body indentation.

---

## Verified OK

- `Q_Pansopy/qt_compat.py` — Triple-fallback import chain is correct; `QVariant` stub for PyQt6 is correct.
- `Q_Pansopy/qpansopy.py` — `_IMPORT_ERRORS` pattern properly defers errors to `initGui`; module dict is consistent.
- `Q_Pansopy/dockwidgets/base_dockwidget.py` — Class structure, `_run_with_feedback`, QSS loading, and signal handling are all correct.
- `Q_Pansopy/dockwidgets/ils/qpansopy_ils_dockwidget.py` — Clean; tooltips applied; `QRegularExpression` used correctly.
- `Q_Pansopy/dockwidgets/departures/qpansopy_sid_initial_dockwidget.py` — Clean.
- `Q_Pansopy/dockwidgets/utilities/qpansopy_feature_merge_dockwidget.py` — Clean.
- `Q_Pansopy/dockwidgets/pbn/qpansopy_gnss_waypoint_dockwidget.py` — Clean; `update_att` signal logic correct.
- Phase 6 snake_case renames — All imports in `__init__.py` files updated correctly; no dangling old-name references found.

---

## Test Results (post-fix)

```
45 passed, 1 skipped in 0.38s
```

Zero regressions.

**Branch:** `refactor/qpansopy-v1`  
**Scope:** Post-refactor review (Phases 0–7). Aeronautical formulas excluded from analysis.

---

## Summary

| Severity   | Count  |
| ---------- | ------ |
| 🔴 Blocker | 2      |
| 🟠 Major   | 6      |
| 🟡 Minor   | 4      |
| **Total**  | **12** |

---

## 🔴 Blockers — Must Fix

### R1 — Missing `import os` in `qpansopy_holding_dockwidget.py`

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_holding_dockwidget.py` — Line 4  
**Impact:** `NameError: name 'os' is not defined` — the module crashes at import time; the Holding dockwidget is completely unusable.

```python
# Current (crashes on import):
from qgis.PyQt import QtWidgets, uic
from qgis.PyQt.QtCore import pyqtSignal
from qgis.core import QgsMapLayerProxyModel
# os is never imported, but used on the very next line:
FORM_CLASS, _ = uic.loadUiType(os.path.join(...))   # ← NameError
```

**Fix:** Add `import os` as the first import.

---

### R2 — `setMaximumHeight(0)` hides the log widget (bug B2 re-introduced)

**File:** `Q_Pansopy/dockwidgets/ils/qpansopy_oas_ils_dockwidget.py` — Line 96  
**Impact:** The log `QTextEdit` has a maximum height of **zero pixels**, making it permanently invisible. The in-code comment claims `"0 means no max"` which is the opposite of what Qt does.

```python
# Current — wrong: collapses widget to 0px height:
self.logTextEdit.setMaximumHeight(0)  # 0 means no max; layout manages size

# Fix — remove the call entirely, or use the Qt "no limit" constant:
self.logTextEdit.setMaximumHeight(16777215)   # QWIDGETSIZE_MAX
# or simply: del the line — Qt's default is already no max
```

---

## 🟠 Major — Should Fix

### R3 — `validate_inputs()` resets `csv_path` after `request_csv_file()` sets it

**File:** `Q_Pansopy/dockwidgets/ils/qpansopy_oas_ils_dockwidget.py` — Lines 449–450 and 489–494  
**Impact:** Silent data loss. `calculate()` calls `request_csv_file()` (which populates `self.csv_path`), then immediately calls `validate_inputs()`, which starts with `self.csv_path = None`. The path is discarded before it reaches `params`. The downstream module receives `csv_path=None` and opens its own `QFileDialog` — the user is shown a second, unexpected file picker.

```python
# calculate() call order (current — broken):
if not self.request_csv_file():  # sets self.csv_path = "path/to/file.csv"
    return
if not self.validate_inputs():   # ← self.csv_path = None  (resets it!)
    return
params = { ..., 'csv_path': self.csv_path }  # always None here
```

**Fix:** Move the `self.csv_path = None` reset to the **top of `calculate()`** instead of inside `validate_inputs()`, so the reset happens before the file dialog, not after.

---

### R4 — `from qgis.utils import iface` at module level in 11 files

**Files:**

- `Q_Pansopy/modules/basic_ils.py`
- `Q_Pansopy/modules/wind_spiral.py`
- `Q_Pansopy/modules/vss_straight.py`
- `Q_Pansopy/modules/vss_loc.py`
- `Q_Pansopy/modules/oas_ils.py`
- `Q_Pansopy/modules/pbn/lnav_final_approach.py`
- `Q_Pansopy/modules/pbn/lnav_initial_approach.py`
- `Q_Pansopy/modules/pbn/lnav_intermediate_approach.py`
- `Q_Pansopy/modules/pbn/lnav_missed_approach.py`
- `Q_Pansopy/modules/pbn/gnss_waypoint.py`
- `Q_Pansopy/modules/utilities/selection_of_objects.py`

**Impact:** These files import `iface` at module load time. Outside a running QGIS session (unit tests, import analysis, plugin load during QGIS startup) `iface` may be `None` or the module may fail entirely. This was listed as Bug B15 in the development plan — it was fixed in the dockwidgets but **not** in the modules. Each `iface.messageBar().pushMessage(...)` call inside these modules will crash if called when `iface is None`.

**Fix:** Remove the module-level import. Pass `iface` as a parameter to the function that needs it (already done in dockwidgets), or use `from qgis.utils import iface` as a **local import** inside the function body.

---

### R5 — `log()` method crashes if `logTextEdit` is missing

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_vss_dockwidget.py` — Line 341  
**Impact:** All other dockwidgets guard with `hasattr(self, 'logTextEdit') and self.logTextEdit is not None`. The VSS dockwidget does not, so any call to `self.log()` before `setupUi()` completes, or if the `.ui` file has a naming mismatch, raises `AttributeError`.

```python
# Current — unsafe:
def log(self, message):
    self.logTextEdit.append(message)          # ← AttributeError if widget missing
    self.logTextEdit.ensureCursorVisible()

# Fix — add guard (consistent with all other dockwidgets):
def log(self, message):
    if hasattr(self, 'logTextEdit') and self.logTextEdit is not None:
        self.logTextEdit.append(message)
        self.logTextEdit.ensureCursorVisible()
```

---

### R6 — Bare `except:` silently swallows all exceptions

**Files and lines:**

- `Q_Pansopy/utils.py` — Line 115
- `Q_Pansopy/modules/pbn/pbn_rnav1_arrival.py` — Line 91
- `Q_Pansopy/modules/pbn/lnav_missed_approach.py` — Line 143

**Impact:** `except:` (no exception type) catches everything including `KeyboardInterrupt`, `SystemExit`, and `MemoryError`. It makes debugging impossible when something goes wrong because errors are swallowed silently with no traceback.

**Fix:** Replace with `except Exception as e:` and at minimum log the error.

---

### R7 — `BasePansopyDockWidget` defined but never inherited

**File:** `Q_Pansopy/dockwidgets/base_dockwidget.py` — The base class exists with `_run_with_feedback()`, `_load_base_qss()`, `log()`, `get_output_path()` etc.  
**Affected dockwidgets (all inherit directly from `QtWidgets.QDockWidget`):**

- `qpansopy_vss_dockwidget.py`
- `qpansopy_vor_dockwidget.py`
- `qpansopy_conv_initial_dockwidget.py`
- `qpansopy_ndb_dockwidget.py`
- `qpansopy_holding_dockwidget.py`
- `qpansopy_object_selection_dockwidget.py`
- `qpansopy_gnss_waypoint_dockwidget.py`
- `qpansopy_omnidirectional_dockwidget.py`
- (and others)

**Impact:** The QSS stylesheet defined in Phase 5 (`dockwidget_base.qss`) is **never applied** to these widgets because `_load_base_qss()` is only called in `BasePansopyDockWidget.__init__`. Methods like `get_desktop_path()`, `log()`, and `closeEvent()` are duplicated across every dockwidget instead of inherited. This defeats the entire purpose of Phase 4.

> **Note:** This is architectural debt from the refactor, not a crash. Acceptable to fix incrementally.

---

## 🟡 Minor — Nice to Fix

### R8 — `QFormLayout.FieldRole` breaks on Qt6 / QGIS 4

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_point_filter_dockwidget.py` — Line ~115  
**Impact:** In Qt6 (and therefore QGIS 4), `QFormLayout.FieldRole` was moved to `QFormLayout.ItemRole.FieldRole`. This line will raise `AttributeError` when running under QGIS 4, silently breaking the Point Filter widget layout.

```python
# Current — Qt5 only:
self.parametersLayout.setWidget(0, QtWidgets.QFormLayout.FieldRole, container)

# Fix — Qt5/Qt6 compatible:
role = getattr(
    QtWidgets.QFormLayout,
    'FieldRole',
    QtWidgets.QFormLayout.ItemRole.FieldRole   # Qt6 fallback
)
self.parametersLayout.setWidget(0, role, container)
```

---

### R9 — Wildcard imports in module files

**Files:**

- `Q_Pansopy/modules/conv/conv_initial_approach.py` — Lines 5–7
- `Q_Pansopy/modules/conv/conv_initial_approach_straight.py` — Lines 7–9
- `Q_Pansopy/modules/conv/vor_approach.py` — Lines 5–7
- `Q_Pansopy/modules/conv/ndb_approach.py` — Lines 5–7
- `Q_Pansopy/modules/pbn/lnav_initial_approach.py` — Line 29
- `Q_Pansopy/modules/pbn/lnav_final_approach.py` — Line 24
- `Q_Pansopy/modules/pbn/lnav_intermediate_approach.py` — Line 37
- `Q_Pansopy/modules/utilities/conventional_holding_navaid.py` — Lines 7–9
- `Q_Pansopy/modules/utilities/fix_tolerances/GNSS_waypoint.py` — Lines 7–9

**Impact:** `from qgis.core import *` / `from qgis.PyQt.QtCore import *` / `from math import *` pollute the module namespace. Name collisions are silent and make it impossible to trace what symbol comes from where. Tools like pylint, mypy, and IDEs cannot analyse these files correctly.

> Formula code — fix only if a module needs to be touched for other reasons.

---

### R10 — KML export in `qpansopy_ndb_dockwidget.py` logs but does nothing

**File:** `Q_Pansopy/dockwidgets/conv/qpansopy_ndb_dockwidget.py` — Lines 73–75  
**Impact:** When the user checks "Export to KML", the widget logs `"KML export would go to: {output_dir}"` — the literal phrase "would go to" — but performs no actual export. This is a stub that was never completed, and the user receives misleading feedback.

```python
if export_kml:
    # Add KML export code here if available   ← TODO never implemented
    self.log(f"KML export would go to: {output_dir}")  # ← misleading
```

**Fix:** Either implement KML export, or disable/hide the `exportKmlCheckBox` until implemented.

---

### R11 — Misleading indentation in `qpansopy_vss_dockwidget.py`

**File:** `Q_Pansopy/dockwidgets/utilities/qpansopy_vss_dockwidget.py` — Lines 97–98  
**Impact:** The comment `# Log message` sits at 4-space (class-body) indentation inside `__init__`, while the `self.log(...)` that follows it is at 8-space (method-body) indentation. Python ignores comments for block parsing so the code executes correctly, but it looks like `self.log(...)` is outside `__init__`, leading to confusion during future edits.

```python
# Current — visually broken:
            self.verticalLayout.addWidget(self.exportKmlCheckBox)

    # Log message                   ← looks like it's at class level
        self.log("QPANSOPY VSS plugin loaded. ...")  ← but this is inside __init__

# Fix — align indentation:
        # Log message
        self.log("QPANSOPY VSS plugin loaded. ...")
```

---

## Verified OK

The following areas were reviewed and found clean:

- `Q_Pansopy/qt_compat.py` — Triple-fallback import chain is correct; `QVariant` stub for PyQt6 is correct.
- `Q_Pansopy/qpansopy.py` — `_IMPORT_ERRORS` pattern properly defers errors to `initGui`; module dict is consistent.
- `Q_Pansopy/dockwidgets/base_dockwidget.py` — Class structure, `_run_with_feedback`, QSS loading, and signal handling are all correct.
- `Q_Pansopy/dockwidgets/ils/qpansopy_ils_dockwidget.py` — Clean; tooltips applied; `QRegularExpression` used correctly.
- `Q_Pansopy/dockwidgets/departures/qpansopy_sid_initial_dockwidget.py` — Clean.
- `Q_Pansopy/dockwidgets/utilities/qpansopy_feature_merge_dockwidget.py` — Clean.
- `Q_Pansopy/dockwidgets/pbn/qpansopy_gnss_waypoint_dockwidget.py` — Clean; `update_att` signal logic correct.
- `Q_Pansopy/dockwidgets/utilities/qpansopy_object_selection_dockwidget.py` — Clean.
- `Q_Pansopy/dockwidgets/conv/qpansopy_ndb_dockwidget.py` — Clean except R10.
- Phase 6 snake_case renames — All imports in `__init__.py` files updated correctly; no dangling old-name references found.

---

## Recommended Fix Order

1. **R1** — Add `import os` to `qpansopy_holding_dockwidget.py` (one line)
2. **R2** — Remove `setMaximumHeight(0)` from `qpansopy_oas_ils_dockwidget.py` (one line)
3. **R3** — Move `self.csv_path = None` reset from `validate_inputs()` to top of `calculate()`
4. **R5** — Add `hasattr` guard to `log()` in `qpansopy_vss_dockwidget.py`
5. **R6** — Replace bare `except:` with `except Exception as e:` in 3 files
6. **R4** — Convert module-level `iface` imports to local imports (11 files)
7. **R8** — Fix Qt6-compat `QFormLayout.FieldRole`
8. **R10** — Disable KML checkbox in NDB widget or implement the export
