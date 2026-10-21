"""Generic terrain and survey assessment against a sloping surface."""

from dataclasses import dataclass
from html import escape
import math
from typing import Callable, Literal, Optional, Tuple

from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerNotesUtils,
    QgsMarkerSymbol,
    QgsMemoryProviderUtils,
    QgsProject,
    QgsRendererCategory,
    QgsVectorLayer,
    QgsWkbTypes,
)

from . import primary_area_assessment as primary


@dataclass(frozen=True)
class SlopeRecord:
    """A normalized point and its unrounded surface comparison."""

    source: primary.SourceRecord
    applied_tolerance_m: float
    x_dist: float
    surface_z: float
    clearance: float

    @property
    def penetrates(self) -> Literal['clear', 'penetrates']:
        return 'penetrates' if self.clearance < 0 else 'clear'


@dataclass(frozen=True)
class SlopeAssessmentResult:
    """Output layers and processing counts for a slope assessment."""

    assessment_layer: QgsVectorLayer
    assessed_count: int
    penetration_count: int
    warnings: Tuple[str, ...]
    buffer_layer: Optional[QgsVectorLayer] = None


def _surface_parameters(elevation_m: float, angle_deg: float) -> Tuple[float, float]:
    elevation = float(elevation_m)
    if not math.isfinite(elevation):
        raise ValueError('Surface elevation must be finite')
    angle = float(angle_deg)
    if not math.isfinite(angle) or not -90.0 < angle < 90.0:
        raise ValueError('Slope angle must be finite and strictly between -90 and 90 degrees')
    return elevation, math.tan(math.radians(angle))


def _evaluate_point(
    record: primary.SourceRecord,
    distance_m: float,
    surface_elevation_m: float,
    gradient: float,
    override_tolerance_m: Optional[float],
) -> SlopeRecord:
    distance = primary._valid_nonnegative(distance_m, 'Reference distance')
    _, _, applied_tolerance, effective_elevation = primary._evaluation_values(
        record, 0.0, override_tolerance_m
    )
    surface_z = surface_elevation_m + distance * gradient
    clearance = surface_z - effective_elevation
    if not math.isfinite(surface_z) or not math.isfinite(clearance):
        raise ValueError(f"Surface comparison for obstacle '{record.identifier}' must be finite")
    return SlopeRecord(record, applied_tolerance, distance, surface_z, clearance)


def evaluate_point(
    record: primary.SourceRecord,
    distance_m: float,
    surface_elevation_m: float,
    slope_angle_deg: float,
    override_tolerance_m: Optional[float] = None,
) -> SlopeRecord:
    """Compare one point to a surface at a perpendicular distance in metres."""
    elevation, gradient = _surface_parameters(surface_elevation_m, slope_angle_deg)
    override = (
        None if override_tolerance_m is None else
        primary._valid_nonnegative(override_tolerance_m, 'Tolerance override')
    )
    return _evaluate_point(record, distance_m, elevation, gradient, override)


def _result_layer(crs, records) -> QgsVectorLayer:
    fields = QgsFields()
    for name in ('id', 'layer_type', 'obstacle_type'):
        fields.append(QgsField(name, primary._TYPE_STRING, len=80))
    for name in ('elev', 'tolerances', 'applied_tolerance'):
        fields.append(QgsField(name, primary._TYPE_DOUBLE, len=20, prec=3))
    fields.append(QgsField('area_eval', primary._TYPE_STRING, len=40))
    for name in ('x_dist', 'surface_z', 'clearance'):
        fields.append(QgsField(name, primary._TYPE_DOUBLE, len=20, prec=3))
    fields.append(QgsField('penetrates', primary._TYPE_STRING, len=20))
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        'Slope primary assessment', fields, QgsWkbTypes.Point, crs
    )
    features = []
    for record in records:
        source = record.source
        feature = QgsFeature(fields)
        feature.setGeometry(QgsGeometry(source.geometry))
        feature.setAttributes([
            source.identifier, source.layer_type, source.obstacle_type,
            source.elevation_m, source.tolerance_m, record.applied_tolerance_m,
            'slope primary area', record.x_dist, record.surface_z,
            record.clearance, record.penetrates,
        ])
        features.append(feature)
    if features and not layer.dataProvider().addFeatures(features)[0]:
        raise RuntimeError('Could not populate the slope assessment layer')
    layer.updateExtents()
    categories = []
    for status, shape, color in (
        ('clear', 'circle', '35,139,69,255'),
        ('penetrates', 'triangle', '215,25,32,255'),
    ):
        symbol = QgsMarkerSymbol.createSimple({
            'name': shape, 'color': color, 'outline_style': 'no', 'size': '1.0',
        })
        categories.append(QgsRendererCategory(status, symbol, status))
    layer.setRenderer(QgsCategorizedSymbolRenderer('penetrates', categories))
    return layer


def run_slope_primary_area_assessment(
    iface,
    area_layer: QgsVectorLayer,
    reference_layer: QgsVectorLayer,
    terrain_layer=None,
    obstacle_layer: Optional[QgsVectorLayer] = None,
    field_mapping: Optional[primary.FieldMapping] = None,
    surface_elevation_m: float = 0.0,
    slope_angle_deg: float = 0.0,
    terrain_tolerance_m: float = 50.0,
    override_tolerance_m: Optional[float] = None,
    terrain_band: int = 1,
    use_selected_area: bool = True,
    confirm_missing: Optional[Callable[[Tuple[str, ...]], bool]] = None,
    area_buffer_m: float = 0.0,
) -> SlopeAssessmentResult:
    """Evaluate every point against the extended straight reference baseline.

    Distance is absolute on both sides and independent of line direction.
    Positive angles rise away from the baseline; negative angles descend.
    """
    del iface
    if area_layer is None or not area_layer.isValid():
        raise ValueError('A valid assessment-area layer is required')
    if area_layer.geometryType() != QgsWkbTypes.PolygonGeometry:
        raise ValueError('The assessment area must contain polygons')
    if terrain_layer is None and obstacle_layer is None:
        raise ValueError('Please select a terrain or survey layer')
    for label, layer in (('terrain', terrain_layer), ('survey', obstacle_layer)):
        if layer is not None and not layer.isValid():
            raise ValueError(f'A valid {label} layer is required')
    if obstacle_layer is not None and obstacle_layer.geometryType() != QgsWkbTypes.PointGeometry:
        raise ValueError('The survey layer must contain points')
    elevation, gradient = _surface_parameters(surface_elevation_m, slope_angle_deg)
    terrain_tolerance = primary._valid_nonnegative(terrain_tolerance_m, 'Terrain vertical tolerance')
    override = (
        None if override_tolerance_m is None else
        primary._valid_nonnegative(override_tolerance_m, 'Tolerance override')
    )
    buffer_m = primary._valid_nonnegative(area_buffer_m, 'Area buffer')
    if terrain_band < 1:
        raise ValueError('Terrain band must be one or greater')
    primary._validate_crs(area_layer, terrain_layer, obstacle_layer)

    # Reuse the established straight-axis validation, without secondary AOI clipping.
    from .secondary_area_assessment import (
        _linear_unit_factor, _reference_axis, _signed_offset,
    )

    _, origin, ux, uy = _reference_axis(reference_layer)
    if reference_layer.crs() != area_layer.crs():
        raise primary.CrsValidationError('The reference line must use the same CRS as the assessment area')
    factor = _linear_unit_factor(area_layer.crs())
    mask = primary._build_mask_geometry(area_layer, use_selected_area, buffer_m)
    terrain_records = primary._terrain_records(terrain_layer, mask, terrain_tolerance, terrain_band)
    survey_records = primary._survey_records(obstacle_layer, mask, field_mapping, override is not None)
    warnings = []
    if not terrain_records:
        warnings.append('No terrain data was evaluated inside the mask')
    if not survey_records:
        warnings.append('No survey data was evaluated inside the mask')
    warning_tuple = tuple(warnings)
    if warning_tuple and confirm_missing is not None and not confirm_missing(warning_tuple):
        raise primary.AssessmentCancelled('Assessment cancelled by the user')

    evaluated = [
        _evaluate_point(
            source,
            abs(_signed_offset(source.geometry.asPoint(), origin, ux, uy)) * factor,
            elevation, gradient, override,
        )
        for source in terrain_records + survey_records
    ]
    assessment_layer = _result_layer(area_layer.crs(), evaluated)
    buffer_layer = primary._buffer_result_layer(mask, area_layer.crs()) if buffer_m > 0 else None
    if buffer_layer is not None:
        buffer_layer.setName('Slope primary area buffer')
    override_note = 'disabled' if override is None else f'{override:g} m'
    notes = (
        '<h3>Slope primary-area assessment</h3><p>'
        f'Surface elevation: {elevation:g} m<br>'
        f'Slope angle: {float(slope_angle_deg):g} degrees<br>'
        f'Reference line: {escape(reference_layer.name())}<br>'
        'Absolute perpendicular distance to the extended reference line.<br>'
        'Positive angles rise away from the line; negative angles descend.<br>'
        f'Area buffer: {buffer_m:g} m<br>'
        f'Terrain tolerance: {terrain_tolerance:g} m<br>'
        f'Survey tolerance override: {override_note}<br>'
        'Clearance = surface elevation - (point elevation + applied tolerance).<br>'
        'Negative clearance penetrates; zero clearance is clear.<br>'
        f'Data warnings: {escape("; ".join(warnings)) if warnings else "None"}</p>'
    )
    layers = [assessment_layer]
    if buffer_layer is not None:
        layers.append(buffer_layer)
    for layer in layers:
        QgsLayerNotesUtils.setLayerNotes(layer, notes)
    project = QgsProject.instance()
    project.addMapLayers(layers, False)
    group = project.layerTreeRoot().insertGroup(0, 'Obstacle assessment')
    for layer in layers:
        group.addLayer(layer).setItemVisibilityChecked(True)
    return SlopeAssessmentResult(
        assessment_layer, len(evaluated),
        sum(record.penetrates == 'penetrates' for record in evaluated),
        warning_tuple, buffer_layer,
    )
