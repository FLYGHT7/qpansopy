"""
Test data for validation of QPANSOPY calculations
Cases based on ICAO standards and real airports
"""

# Test cases with known values for VSS calculations
VSS_TEST_CASES = [
    {
        "name": "International Airport Standard",
        "description": "Typical international airport configuration",
        "params": {
            "rwy_width": "45",
            "thr_elev": "1500",
            "strip_width": "150",
            "OCH": "75",
            "RDH": "15",
            "VPA": "3.0",
            "thr_elev_unit": "m",
            "OCH_unit": "m",
            "RDH_unit": "m"
        },
        "expected_results": {
            "vpa_radians": 0.0524,
            "surface_type": "Straight In NPA"
        }
    },
    {
        "name": "Regional Airport",
        "description": "Small regional airport configuration",
        "params": {
            "rwy_width": "30",
            "thr_elev": "500",
            "strip_width": "80",
            "OCH": "50",
            "RDH": "10",
            "VPA": "3.5",
            "thr_elev_unit": "m",
            "OCH_unit": "m",
            "RDH_unit": "m"
        },
        "expected_results": {
            "vpa_radians": 0.0611,
            "surface_type": "Straight In NPA"
        }
    },
    {
        "name": "Mountain Airport",
        "description": "High elevation mountain airport with steep approach",
        "params": {
            "rwy_width": "45",
            "thr_elev": "3000",
            "strip_width": "140",
            "OCH": "100",
            "RDH": "20",
            "VPA": "4.5",
            "thr_elev_unit": "m",
            "OCH_unit": "m",
            "RDH_unit": "m"
        },
        "expected_results": {
            "vpa_radians": 0.0785,
            "surface_type": "Straight In NPA"
        }
    },
    {
        "name": "Feet Units Test",
        "description": "Validation of feet to meters conversion",
        "params": {
            "rwy_width": "150",  # feet
            "thr_elev": "4921",  # 1500m in feet
            "strip_width": "492", # 150m in feet
            "OCH": "246",        # 75m in feet
            "RDH": "49",         # 15m in feet
            "VPA": "3.0",
            "thr_elev_unit": "ft",
            "OCH_unit": "ft",
            "RDH_unit": "ft"
        },
        "expected_results": {
            "thr_elev_meters": 1500.0,
            "OCH_meters": 75.0,
            "RDH_meters": 15.0
        }
    }
]

# Edge cases for robust testing
EDGE_CASES = [
    {
        "name": "Minimum Values",
        "params": {
            "rwy_width": "23",
            "thr_elev": "0",
            "strip_width": "80",
            "OCH": "30",
            "RDH": "5",
            "VPA": "2.5"
        }
    },
    {
        "name": "Maximum Typical Values",
        "params": {
            "rwy_width": "60",
            "thr_elev": "4500",
            "strip_width": "300",
            "OCH": "200",
            "RDH": "50",
            "VPA": "6.0"
        }
    }
]

# Expected error cases
ERROR_CASES = [
    {
        "name": "Negative VPA",
        "params": {"VPA": "-1.0"},
        "expected_error": "VPA must be positive"
    },
    {
        "name": "Zero Runway Width",
        "params": {"rwy_width": "0"},
        "expected_error": "Runway width must be positive"
    },
    {
        "name": "Negative Elevation",
        "params": {"thr_elev": "-100"},
        "expected_error": "Negative elevation not typical"
    }
]

# Real airport data for validation
REAL_AIRPORTS = [
    {
        "name": "ICAO: KJFK - JFK International",
        "location": "New York, USA",
        "elevation_ft": 13,
        "elevation_m": 4,
        "runway_width_m": 46,
        "typical_vpa": 3.0
    },
    {
        "name": "ICAO: KDEN - Denver International",
        "location": "Denver, USA",
        "elevation_ft": 5434,
        "elevation_m": 1656,
        "runway_width_m": 46,
        "typical_vpa": 3.0
    },
    {
        "name": "ICAO: SBGR - Guarulhos International",
        "location": "São Paulo, Brazil",
        "elevation_ft": 2459,
        "elevation_m": 750,
        "runway_width_m": 45,
        "typical_vpa": 3.0
    }
]

# Wind Spiral test data
WIND_SPIRAL_TEST_CASES = [
    {
        "name": "Standard Rate Turn",
        "description": "Standard 3°/second turn rate",
        "params": {
            "airspeed_kts": 120,
            "bank_angle_deg": 20,
            "wind_speed_kts": 15,
            "wind_direction_deg": 270,
            "altitude_ft": 3000
        },
        "expected_results": {
            "turn_radius_m": 820,
            "turn_rate_deg_s": 3.0
        }
    },
    {
        "name": "Traffic Pattern",
        "description": "Typical traffic pattern parameters",
        "params": {
            "airspeed_kts": 90,
            "bank_angle_deg": 15,
            "wind_speed_kts": 10,
            "wind_direction_deg": 360,
            "altitude_ft": 1500
        },
        "expected_results": {
            "turn_radius_m": 500,
            "pattern_suitable": True
        }
    }
]

# ILS test data
ILS_TEST_CASES = [
    {
        "name": "CAT I ILS Standard",
        "description": "Standard CAT I ILS approach",
        "params": {
            "glide_slope_deg": 3.0,
            "localizer_width_deg": 5.0,
            "decision_height_ft": 200,
            "runway_width_m": 45,
            "threshold_elevation_m": 100
        },
        "expected_results": {
            "category": "CAT I",
            "min_rvr_m": 550
        }
    },
    {
        "name": "CAT II ILS Precision",
        "description": "CAT II precision approach",
        "params": {
            "glide_slope_deg": 3.0,
            "localizer_width_deg": 5.0,
            "decision_height_ft": 150,
            "runway_width_m": 45,
            "threshold_elevation_m": 200
        },
        "expected_results": {
            "category": "CAT II",
            "min_rvr_m": 300
        }
    }
]

# PBN test data
PBN_TEST_CASES = [
    {
        "name": "RNP 0.3 Approach",
        "description": "RNP 0.3 precision approach",
        "params": {
            "rnp_value_nm": 0.3,
            "approach_length_nm": 5.0,
            "descent_gradient_percent": 3.0,
            "decision_altitude_ft": 250
        },
        "expected_results": {
            "containment_width_m": 1111,
            "approach_feasible": True
        }
    },
    {
        "name": "RNP 1 Terminal",
        "description": "RNP 1 terminal area procedure",
        "params": {
            "rnp_value_nm": 1.0,
            "procedure_length_nm": 25,
            "altitude_change_ft": 5000,
            "max_bank_angle_deg": 25
        },
        "expected_results": {
            "corridor_width_m": 3704,
            "procedure_feasible": True
        }
    }
]

# Atmospheric test data (ISA conditions)
ATMOSPHERIC_TEST_DATA = [
    {
        "altitude_m": 0,
        "isa_temp_c": 15.0,
        "isa_pressure_hpa": 1013.25,
        "isa_density_kg_m3": 1.225
    },
    {
        "altitude_m": 1000,
        "isa_temp_c": 8.5,
        "isa_pressure_hpa": 898.7,
        "isa_density_kg_m3": 1.112
    },
    {
        "altitude_m": 3000,
        "isa_temp_c": -4.5,
        "isa_pressure_hpa": 701.1,
        "isa_density_kg_m3": 0.909
    },
    {
        "altitude_m": 5000,
        "isa_temp_c": -17.5,
        "isa_pressure_hpa": 540.2,
        "isa_density_kg_m3": 0.736
    }
]

# Mathematical constants for validation
AVIATION_CONSTANTS = {
    "GRAVITY_MS2": 9.80665,           # Standard gravity
    "EARTH_RADIUS_M": 6371000,        # Mean Earth radius
    "KNOTS_TO_MS": 0.514444,          # Knots to m/s conversion
    "FT_TO_M": 0.3048,                # Feet to meters conversion
    "NM_TO_M": 1852,                  # Nautical miles to meters
    "DEG_TO_RAD": 0.017453292519943295, # Degrees to radians
    "RAD_TO_DEG": 57.29577951308232,   # Radians to degrees
    "ISA_LAPSE_RATE": 0.0065,         # ISA temperature lapse rate K/m
    "ISA_SEA_LEVEL_TEMP": 288.15,     # ISA sea level temperature K
    "ISA_SEA_LEVEL_PRESSURE": 101325, # ISA sea level pressure Pa
    "STANDARD_RATE_TURN": 0.05235988, # 3°/s in radians/s
}

# Validation tolerances for different calculation types
VALIDATION_TOLERANCES = {
    "angle_conversion_rad": 1e-6,     # Angle conversion precision
    "distance_calculation_m": 1.0,    # Distance calculation tolerance
    "unit_conversion_percent": 0.1,   # Unit conversion tolerance
    "atmospheric_calculation": 0.05,  # 5% tolerance for atmospheric
    "navigation_accuracy_m": 10.0,    # Navigation calculation tolerance
    "geometric_calculation_m": 0.1,   # Geometric precision
    "performance_calculation": 0.02   # 2% for performance calculations
}
