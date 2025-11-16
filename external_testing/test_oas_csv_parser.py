#!/usr/bin/env python3
"""
Standalone checker for OAS constants section in CSV files used by OAS ILS CAT I Generator.
Validates presence of W/X/Y/Z planes with A,B,C coefficients (numeric),
mirroring the parsing approach in Q_Pansopy/modules/oas_ils.py but without QGIS deps.

Usage (PowerShell):
  python .\external_testing\test_oas_csv_parser.py "C:\path\to\pans_oas.csv"

Exit codes:
  0 = PASS (all planes present)
  1 = FAIL (missing or non-numeric constants)
  2 = ERROR (file not found / unexpected exception)
"""
import sys
import os
import re

STOP_SECTION = "---OAS Template coordinates -m(meters)"
TARGET_SECTION = "OAS constants"

SPLIT_RE = re.compile(r",|\s{2,}")
KEY_RE = re.compile(r"^([WXYZ])([ABC])$")  # Only base planes W/X/Y/Z


def parse_constants(csv_path):
    planes = {k: [None, None, None] for k in ("W plane", "X plane", "Y plane", "Z plane")}
    if not os.path.exists(csv_path):
        raise FileNotFoundError(csv_path)
    current_section = None
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            # Stop at template coordinates section
            if line.startswith("---") and line.strip() == STOP_SECTION:
                break
            # Section headers begin with ---
            if line.startswith("---"):
                current_section = line.strip("- \t\n")
                continue
            if current_section != TARGET_SECTION:
                continue
            # Split into key/value
            if "\t" in line:
                parts = [p.strip().rstrip(',') for p in line.split("\t") if p.strip()]
            else:
                parts = [p.strip().rstrip(',') for p in SPLIT_RE.split(line) if p.strip()]
            if len(parts) < 2:
                continue
            key = parts[0]
            value = parts[-1]
            m = KEY_RE.fullmatch(key)
            if not m:
                # Ignore primes or other constants (e.g., W'A). Only base WA/WB/WC etc.
                continue
            plane_letter, coeff = m.groups()
            idx = "ABC".index(coeff)
            try:
                val = float(value)
            except ValueError:
                val = None
            planes[f"{plane_letter} plane"][idx] = val
    return planes


def main(argv):
    if len(argv) < 2:
        print("Usage: python test_oas_csv_parser.py <path_to_csv>")
        return 1
    path = argv[1]
    try:
        planes = parse_constants(path)
        missing = []
        non_numeric = []
        for pname, coeffs in planes.items():
            for i, c in enumerate(coeffs):
                label = f"{pname} {'ABC'[i]}"
                if c is None:
                    missing.append(label)
                elif not isinstance(c, float):
                    non_numeric.append(label)
        if missing or non_numeric:
            if missing:
                print("FAIL: Missing coefficients:", ", ".join(missing))
            if non_numeric:
                print("FAIL: Non-numeric coefficients:", ", ".join(non_numeric))
            return 1
        print("PASS: CSV contains W/X/Y/Z planes with A,B,C numeric coefficients")
        for pname, coeffs in planes.items():
            print(f"  {pname}: A={coeffs[0]}, B={coeffs[1]}, C={coeffs[2]}")
        return 0
    except FileNotFoundError:
        print(f"ERROR: File not found: {path}")
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
