# -*- coding: utf-8 -*-
"""Pure International Standard Atmosphere temperature calculations."""
from typing import Literal, TypedDict


METRES_TO_FEET = 3.28084
ISA_SEA_LEVEL_TEMPERATURE_C = 15.0
ISA_LAPSE_RATE_C_PER_FOOT = 0.00198


class ISACalculation(TypedDict):
    """Serializable result returned by :func:`calculate_isa_variation`."""

    method: Literal['calculated']
    isa_temperature: float
    elevation_feet: float
    elevation_original: float
    elevation_unit: str
    temperature_reference: float
    isa_variation_calculated: float


def calculate_isa_variation(
        elevation: float, elevation_unit: str,
        reference_temperature_c: float) -> ISACalculation:
    """Calculate temperature deviation from ISA at an aerodrome elevation.

    ``reference_temperature_c`` is the observed/reference temperature in
    degrees Celsius. Elevation may be provided in feet or metres.
    """
    if elevation_unit not in ('ft', 'm'):
        raise ValueError(
            'Unsupported elevation unit: {0}'.format(elevation_unit))

    elevation_original = float(elevation)
    temperature_reference = float(reference_temperature_c)
    elevation_feet = (
        elevation_original * METRES_TO_FEET
        if elevation_unit == 'm' else elevation_original
    )
    isa_temperature = (
        ISA_SEA_LEVEL_TEMPERATURE_C
        - ISA_LAPSE_RATE_C_PER_FOOT * elevation_feet
    )
    isa_variation = temperature_reference - isa_temperature

    return {
        'method': 'calculated',
        'isa_temperature': isa_temperature,
        'elevation_feet': elevation_feet,
        'elevation_original': elevation_original,
        'elevation_unit': elevation_unit,
        'temperature_reference': temperature_reference,
        'isa_variation_calculated': isa_variation,
    }
