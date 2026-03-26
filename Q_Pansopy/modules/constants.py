# -*- coding: utf-8 -*-
"""
Physical and aeronautical constants for QPANSOPY calculations.

All values are from ICAO Doc 9613 and SI standard unless noted.
"""
from typing import Final

# Unit conversions
FT_TO_M: Final[float] = 0.3048       # feet → metres (exact)
NM_TO_M: Final[float] = 1852.0       # nautical miles → metres (exact)
KT_TO_MS: Final[float] = 0.514444    # knots → metres per second

# ILS surface geometry (ICAO Annex 10 / Doc 8168 values)
ILS_GROUND_LENGTH_M: Final[float] = 960.0   # ground surface half-length (m)
ILS_APPROACH_1_M: Final[float] = 3000.0     # first approach section length (m)
ILS_SPLAY_RATIO: Final[float] = 0.15        # lateral splay (15 %)
ILS_TRANSITION_SLOPE: Final[float] = 14.3   # transition surface slope (%)
