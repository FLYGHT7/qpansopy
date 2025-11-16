# QPANSOPY External Testing Framework

## Overview

Comprehensive external testing system for QPANSOPY mathematical formulas and calculations. This framework provides formula validation without modifying production code.

## Features

- **Formula Validation**: Direct testing of mathematical calculations across all QPANSOPY modules
- **Comprehensive Coverage**: VSS, Wind Spiral, ILS, PBN, and general conversion tests
- **Real-world Scenarios**: Tests with actual airport data and ICAO standards
- **Detailed Reporting**: JSON reports with execution statistics and error analysis
- **Production Safe**: External testing approach with no impact on production code

## Quick Start

### Simple Execution (Recommended)

```bash
# Run comprehensive formula validator (main validator)
python qpansopy_formula_validator_final.py

# Run simplified formula validator (lightweight)
python simplified_formula_validator.py

# Or use batch file
run_formula_validation.bat
```

## Test Categories

### 1. VSS (Visual Segment Surface) Tests

- **Unit Conversions**: Degrees/radians, feet/meters
- **Trigonometry**: Horizontal distance, slope calculations
- **Validation**: Parameter range checking

### 2. Wind Spiral Tests

- **Atmospheric**: ISA temperature calculations
- **Geometry**: Turn radius, spiral coordinates
- **Navigation**: Ground speed with wind
- **Performance**: Standard rate turns

### 3. ILS (Instrument Landing System) Tests

- **Approach Surfaces**: Height and width calculations
- **Signal Processing**: Localizer beam geometry
- **Standards**: CAT I/II/III requirements
- **Navigation**: Decision height calculations

### 4. PBN (Performance Based Navigation) Tests

- **Accuracy**: RNP value conversions and validation
- **Geometry**: Turn radius, fly-by waypoints
- **Performance**: Descent gradient limits
- **Safety**: Obstacle clearance areas

### 5. General Conversion Tests

- **Constants**: Aviation unit conversion factors
- **Precision**: Mathematical function accuracy
- **Integration**: Real-world airport scenarios

## Current Test Results

### Latest Validation Status ✅

- **Total Tests**: 24 formula validation tests
- **Success Rate**: 100%
- **Categories**: 13 test categories all passing
- **Coverage**: All major QPANSOPY calculation modules

### Test Categories Performance

- Unit Conversion: 2/2 (100%) ✅
- Trigonometry: 4/4 (100%) ✅
- Atmospheric: 1/1 (100%) ✅
- Geometry: 5/5 (100%) ✅
- Navigation: 3/3 (100%) ✅
- Performance: 2/2 (100%) ✅
- All other categories: 100% ✅

## File Structure

```
external_testing/
├── README.md                           # This documentation
├── IMPLEMENTATION_SUMMARY.md           # Complete implementation summary
├── requirements.txt                    # Python dependencies
├── qpansopy_formula_validator_final.py # Main comprehensive validator (✅ Recommended)
├── simplified_formula_validator.py     # Lightweight validator (✅ Working)
├── run_formula_validation.bat         # Windows batch runner
├── test_data/                         # Test datasets and scenarios
└── results/                           # Test execution reports (auto-generated)
```

## Formula Coverage

### Mathematical Functions Tested

- **Trigonometry**: sin, cos, tan, atan calculations
- **Unit Conversions**: Aviation standard conversions
- **Geometry**: Circle, spiral, and surface calculations
- **Physics**: Turn dynamics and atmospheric calculations
- **Navigation**: RNP accuracy and waypoint geometry

### Validation Standards

- **ICAO Annex 14**: Runway and approach surface standards
- **ICAO PANS-OPS**: Procedure design criteria
- **DO-236C**: RNP/RNAV navigation requirements
- **Industry Standards**: Aviation calculation best practices

## Important Notes

- **DOES NOT modify production code**
- **Uses direct mathematical validation**
- **Validates calculation logic independently**
- **All tests currently passing (100% success rate)**
- **Ready for continuous integration**

## KML altitude validation helper

To verify a generated KML is exported with absolute altitudes (not clamped to ground):

1. Use the helper script:

```pwsh
python .\kml_altitude_checker.py "C:\\path\\to\\generated.kml"
```

2. Open the KML in Google Earth and ensure 3D surfaces show above terrain. The checker validates:

- All geometry nodes contain `<altitudeMode>absolute</altitudeMode>`
- Coordinates include Z values (lon,lat,alt)
- **Test cases based on aeronautical standards**
