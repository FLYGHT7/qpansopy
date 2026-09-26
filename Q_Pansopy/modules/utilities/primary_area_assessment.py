"""Generic primary-area terrain and obstacle assessment."""

from dataclasses import dataclass
import math
import os
from typing import Callable, List, Optional, Sequence, Tuple

try:
    from qgis.PyQt.QtCore import QMetaType
    _TYPE_DOUBLE = QMetaType.Type.Double
    _TYPE_INT = QMetaType.Type.Int
    _TYPE_STRING = QMetaType.Type.QString
except (ImportError, AttributeError):
    from qgis.PyQt.QtCore import QVariant
    _TYPE_DOUBLE = QVariant.Double
    _TYPE_INT = QVariant.Int
    _TYPE_STRING = QVariant.String
from qgis.core import (
    Qgis,
    QgsFeature,
    QgsField,
    QgsFields,
    QgsFillSymbol,
    QgsGeometry,
    QgsLayerNotesUtils,
    QgsMarkerSymbol,
    QgsMemoryProviderUtils,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
)

from ..constants import NM_TO_M


_BUFFER_SEGMENTS = 36


@dataclass(frozen=True)
class FieldMapping:
    """Fields used to normalize a survey layer."""

    identifier: str
    obstacle_type: str
    elevation: str
    tolerance: Optional[str]


@dataclass(frozen=True)
class SourceRecord:
    """A normalized terrain or survey point."""

    identifier: str
    layer_type: str
    obstacle_type: str
    coordinates: str
    elevation_m: float
    tolerance_m: float
    geometry: object


@dataclass(frozen=True)
class EvaluatedRecord:
    """A point after applying MOC and vertical tolerance."""

    identifier: str
    layer_type: str
    obstacle_type: str
    coordinates: str
    elevation_m: float
    tolerance_m: float
    applied_tolerance_m: float
    moc_m: float
    oca_m: float
    oca_ft: float
    oca_pub_increment: int
    oca_pub_ft: int
    geometry: object


@dataclass(frozen=True)
class AssessmentResult:
    """Layers and counts produced by one assessment run."""

    assessment_layer: Optional[object]
    control_layer: object
    assessed_count: int
    control_count: int
    warnings: Tuple[str, ...]


class AssessmentCancelled(Exception):
    """Raised when the user declines an incomplete-data assessment."""


class CrsValidationError(ValueError):
    """Raised when an assessment input lacks the required projected CRS."""


def _metres_to_map_units(distance_m: float, crs) -> float:
    """Convert metres to the linear units used by a projected CRS."""
    from qgis.core import QgsUnitTypes

    distance = _valid_nonnegative(distance_m, "Area buffer")
    if distance == 0:
        return 0.0
    try:
        metres = Qgis.DistanceUnit.Meters
    except AttributeError:
        metres = QgsUnitTypes.DistanceMeters
    factor = QgsUnitTypes.fromUnitToUnitFactor(metres, crs.mapUnits())
    if not math.isfinite(factor) or factor <= 0:
        raise ValueError(
            "The assessment area CRS must use supported linear units"
        )
    return distance * factor


def _buffer_mask_geometry(mask_geometry, area_buffer_m: float, crs):
    """Apply the optional metre buffer in the assessment CRS units."""
    distance = _valid_nonnegative(area_buffer_m, "Area buffer")
    if distance == 0:
        return mask_geometry
    map_distance = _metres_to_map_units(distance, crs)
    buffered = mask_geometry.buffer(map_distance, _BUFFER_SEGMENTS)
    if buffered.isNull() or buffered.isEmpty():
        raise ValueError("The assessment-area buffer could not be created")
    return buffered


def _valid_nonnegative(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite value of zero or greater")
    return number


def area_buffer_to_metres(value: float, unit: str) -> float:
    """Return an area-buffer UI value normalized to metres."""
    distance = _valid_nonnegative(value, "Area buffer")
    if unit == "NM":
        return distance * NM_TO_M
    if unit == "m":
        return distance
    raise ValueError(f"Unsupported area buffer unit: {unit}")


def _valid_oca_rounding(value: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(
            "OCA publication increment must be 1, 5, 10, or 100 ft"
        )
    if value not in (1, 5, 10, 100):
        raise ValueError(
            "OCA publication increment must be 1, 5, 10, or 100 ft"
        )
    return value


def evaluate_records(
    records: Sequence[SourceRecord],
    moc_m: float,
    override_tolerance_m: Optional[float] = None,
    oca_rounding_ft: int = 100,
) -> Tuple[List[EvaluatedRecord], List[EvaluatedRecord]]:
    """Evaluate normalized points and return all tied controlling obstacles."""
    moc = _valid_nonnegative(moc_m, "MOC")
    override = (
        None
        if override_tolerance_m is None
        else _valid_nonnegative(override_tolerance_m, "Tolerance override")
    )
    rounding = _valid_oca_rounding(oca_rounding_ft)
    evaluated: List[EvaluatedRecord] = []

    for record in records:
        values = _evaluation_values(record, moc, override)
        evaluated.append(_make_evaluated_record(
            record, moc, values, rounding
        ))

    if not evaluated:
        return [], []

    maximum = max(item.oca_m for item in evaluated)
    controls = [
        item for item in evaluated
        if math.isclose(item.oca_m, maximum, rel_tol=0.0, abs_tol=1e-9)
    ]
    return evaluated, controls


def _evaluation_values(record, moc, override):
    elevation = float(record.elevation_m)
    if not math.isfinite(elevation):
        raise ValueError(
            f"Elevation for obstacle '{record.identifier}' must be finite"
        )
    source_tolerance = _valid_nonnegative(
        record.tolerance_m,
        f"Vertical tolerance for obstacle '{record.identifier}'",
    )
    applied_tolerance = (
        override
        if record.layer_type == "survey" and override is not None
        else source_tolerance
    )
    return (
        elevation,
        source_tolerance,
        applied_tolerance,
        elevation + applied_tolerance + moc,
    )


def _make_evaluated_record(record, moc, values, oca_rounding_ft):
    elevation, source_tolerance, applied_tolerance, oca_m = values
    oca_ft = round(oca_m / 0.3048, 3)
    return EvaluatedRecord(
        identifier=record.identifier,
        layer_type=record.layer_type,
        obstacle_type=record.obstacle_type,
        coordinates=record.coordinates,
        elevation_m=elevation,
        tolerance_m=source_tolerance,
        applied_tolerance_m=applied_tolerance,
        moc_m=moc,
        oca_m=oca_m,
        oca_ft=oca_ft,
        oca_pub_increment=oca_rounding_ft,
        oca_pub_ft=math.ceil(oca_ft / oca_rounding_ft) * oca_rounding_ft,
        geometry=record.geometry,
    )


def _evaluate_control_records(
    records: Sequence[SourceRecord],
    moc_m: float,
    override_tolerance_m: Optional[float] = None,
    oca_rounding_ft: int = 100,
) -> Tuple[int, List[EvaluatedRecord]]:
    """Validate all records while materializing only controlling records."""
    moc = _valid_nonnegative(moc_m, "MOC")
    override = (
        None
        if override_tolerance_m is None
        else _valid_nonnegative(override_tolerance_m, "Tolerance override")
    )
    rounding = _valid_oca_rounding(oca_rounding_ft)
    assessed_count = 0
    maximum = None
    controls: List[EvaluatedRecord] = []

    for record in records:
        values = _evaluation_values(record, moc, override)
        oca_m = values[3]
        assessed_count += 1
        if maximum is None:
            maximum = oca_m
            controls = [_make_evaluated_record(
                record, moc, values, rounding
            )]
        elif oca_m > maximum:
            if math.isclose(oca_m, maximum, rel_tol=0.0, abs_tol=1e-9):
                controls.append(_make_evaluated_record(
                    record, moc, values, rounding
                ))
            else:
                maximum = oca_m
                controls = [_make_evaluated_record(
                    record, moc, values, rounding
                )]
        elif math.isclose(
                oca_m, maximum, rel_tol=0.0, abs_tol=1e-9):
            controls.append(_make_evaluated_record(
                record, moc, values, rounding
            ))

    return assessed_count, controls


def _selected_mask_features(area_layer, use_selected_area: bool):
    if use_selected_area:
        if area_layer.selectedFeatureCount() == 0:
            raise ValueError(
                "Use selected areas is enabled, but the area layer has no "
                "selected features"
            )
        return list(area_layer.selectedFeatures())
    return list(area_layer.getFeatures())


def _build_mask_geometry(
        area_layer, use_selected_area: bool, area_buffer_m: float = 0.0):
    features = _selected_mask_features(area_layer, use_selected_area)
    if not features:
        raise ValueError("The area layer contains no features")

    geometries = [
        QgsGeometry(feature.geometry())
        for feature in features
        if feature.hasGeometry() and not feature.geometry().isEmpty()
    ]
    if not geometries:
        raise ValueError("The selected assessment area has no valid geometry")

    mask_geometry = QgsGeometry.unaryUnion(geometries)
    if mask_geometry.isEmpty():
        raise ValueError("The assessment-area mask could not be created")

    return _buffer_mask_geometry(
        mask_geometry, area_buffer_m, area_layer.crs()
    )


def _point_from_geometry(geometry, identifier: str):
    if geometry.isMultipart():
        raise ValueError(
            f"Obstacle '{identifier}' has multipart geometry; use single points"
        )
    return geometry.asPoint()


def _coordinates(point) -> str:
    return f"{point.x():.3f}, {point.y():.3f}"


def _field_value(feature, field_name: str, label: str):
    value = feature[field_name]
    if value is None:
        raise ValueError(
            f"Feature {feature.id()} has no value in the {label} field "
            f"'{field_name}'"
        )
    return value


def _numeric_field_value(feature, field_name: str, label: str) -> float:
    value = _field_value(feature, field_name, label)
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"Feature {feature.id()} has a non-numeric value in the {label} "
            f"field '{field_name}'"
        ) from error


def _survey_records(obstacle_layer, mask_geometry, mapping, has_override):
    if obstacle_layer is None:
        return []
    if mapping is None:
        raise ValueError("Survey field mapping is required")

    available = set(obstacle_layer.fields().names())
    required = {
        "ID": mapping.identifier,
        "obstacle type": mapping.obstacle_type,
        "elevation": mapping.elevation,
    }
    if not has_override:
        required["vertical tolerance"] = mapping.tolerance
    missing = [
        f"{label} ('{name}')" for label, name in required.items()
        if not name or name not in available
    ]
    if missing:
        raise ValueError("Missing survey field mapping: " + ", ".join(missing))

    records = []
    for feature in obstacle_layer.getFeatures():
        geometry = feature.geometry()
        if not feature.hasGeometry() or geometry.isEmpty():
            continue
        if not mask_geometry.intersects(geometry):
            continue
        identifier = str(_field_value(
            feature, mapping.identifier, "ID"
        )).strip()
        if not identifier:
            raise ValueError(f"Feature {feature.id()} has an empty obstacle ID")
        point = _point_from_geometry(geometry, identifier)
        tolerance = (
            0.0
            if mapping.tolerance is None
            else _numeric_field_value(
                feature, mapping.tolerance, "vertical tolerance"
            )
        )
        records.append(SourceRecord(
            identifier=identifier,
            layer_type="survey",
            obstacle_type=str(_field_value(
                feature, mapping.obstacle_type, "obstacle type"
            )),
            coordinates=_coordinates(point),
            elevation_m=_numeric_field_value(
                feature, mapping.elevation, "elevation"
            ),
            tolerance_m=tolerance,
            geometry=QgsGeometry(geometry),
        ))
    return records


def _terrain_records(terrain_layer, mask_geometry, tolerance_m, band):
    if terrain_layer is None:
        return []
    if band > terrain_layer.bandCount():
        raise ValueError(
            f"Terrain band {band} does not exist in '{terrain_layer.name()}'"
        )

    raster_extent = terrain_layer.extent()
    mask_bounds = mask_geometry.boundingBox().intersect(raster_extent)
    if mask_bounds.isEmpty():
        return []

    width = terrain_layer.width()
    height = terrain_layer.height()
    if width <= 0 or height <= 0:
        raise ValueError("The terrain raster has no cells")
    pixel_width = raster_extent.width() / width
    pixel_height = raster_extent.height() / height
    col_start = max(0, math.floor(
        (mask_bounds.xMinimum() - raster_extent.xMinimum()) / pixel_width
    ))
    col_end = min(width, math.ceil(
        (mask_bounds.xMaximum() - raster_extent.xMinimum()) / pixel_width
    ))
    row_start = max(0, math.floor(
        (raster_extent.yMaximum() - mask_bounds.yMaximum()) / pixel_height
    ))
    row_end = min(height, math.ceil(
        (raster_extent.yMaximum() - mask_bounds.yMinimum()) / pixel_height
    ))
    block_width = col_end - col_start
    block_height = row_end - row_start
    if block_width <= 0 or block_height <= 0:
        return []

    block_extent = QgsRectangle(
        raster_extent.xMinimum() + col_start * pixel_width,
        raster_extent.yMaximum() - row_end * pixel_height,
        raster_extent.xMinimum() + col_end * pixel_width,
        raster_extent.yMaximum() - row_start * pixel_height,
    )
    block = terrain_layer.dataProvider().block(
        band, block_extent, block_width, block_height
    )
    if block is None or not block.isValid():
        raise RuntimeError("Terrain pixels could not be read")

    left = block_extent.xMinimum()
    top = block_extent.yMaximum()
    records = []
    sequence = 0
    for row in range(block_height):
        for column in range(block_width):
            if block.isNoData(row, column):
                continue
            point = QgsPointXY(
                left + (column + 0.5) * pixel_width,
                top - (row + 0.5) * pixel_height,
            )
            geometry = QgsGeometry.fromPointXY(point)
            if not mask_geometry.intersects(geometry):
                continue
            sequence += 1
            records.append(SourceRecord(
                identifier=f"DTM_{sequence:06d}",
                layer_type="DTM",
                obstacle_type="terrain",
                coordinates=_coordinates(point),
                elevation_m=float(block.value(row, column)),
                tolerance_m=tolerance_m,
                geometry=geometry,
            ))
    return records


def _output_fields():
    fields = QgsFields()
    for field in [
        QgsField("id", _TYPE_STRING, len=80),
        QgsField("layer_type", _TYPE_STRING, len=20),
        QgsField("obstacle_type", _TYPE_STRING, len=80),
        QgsField("coordinates", _TYPE_STRING, len=80),
        QgsField("elev", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("tolerances", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("applied_tolerance", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("area_eval", _TYPE_STRING, len=30),
        QgsField("moc_m", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("oca_m", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("oca_ft", _TYPE_DOUBLE, len=20, prec=3),
        QgsField("oca_pub_increment", _TYPE_INT, len=20),
        QgsField("oca_pub_ft", _TYPE_INT, len=20),
    ]:
        fields.append(field)
    return fields


def _result_layer(name: str, crs, records):
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        name, _output_fields(), QgsWkbTypes.Point, crs
    )
    provider = layer.dataProvider()
    features = []
    for record in records:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry(record.geometry))
        feature.setAttributes([
            record.identifier,
            record.layer_type,
            record.obstacle_type,
            record.coordinates,
            record.elevation_m,
            record.tolerance_m,
            record.applied_tolerance_m,
            "primary area",
            record.moc_m,
            record.oca_m,
            record.oca_ft,
            record.oca_pub_increment,
            record.oca_pub_ft,
        ])
        features.append(feature)
        if len(features) == 5000:
            if not provider.addFeatures(features)[0]:
                raise RuntimeError(
                    f"Could not populate result layer '{name}'"
                )
            features = []
    if features and not provider.addFeatures(features)[0]:
        raise RuntimeError(f"Could not populate result layer '{name}'")
    layer.updateExtents()
    return layer


def _buffer_result_layer(mask_geometry, crs):
    """Create the visible polygon showing the exact assessment mask."""
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        "Primary area buffer",
        QgsFields(),
        mask_geometry.wkbType(),
        crs,
    )
    feature = QgsFeature(layer.fields())
    feature.setGeometry(QgsGeometry(mask_geometry))
    if not layer.dataProvider().addFeatures([feature])[0]:
        raise RuntimeError("Could not populate the Primary area buffer layer")
    layer.updateExtents()
    layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": "128,0,255,45",
        "outline_color": "128,0,255,255",
        "outline_width": "0.8",
    }))
    return layer


def _style_results(assessment_layer, control_layer):
    if assessment_layer is not None:
        assessment_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({
            "name": "circle",
            "color": "220,0,0,255",
            "outline_style": "no",
            "size": "1.0",
        }))
    style_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
        "styles",
        "control_obstacle_primary_style.qml",
    )
    try:
        visual_categories = (
            control_layer.StyleCategory.AllVisualStyleCategories
        )
    except AttributeError:
        visual_categories = control_layer.AllVisualStyleCategories
    _, loaded = control_layer.loadNamedStyle(
        style_path,
        categories=visual_categories,
    )
    if not loaded:
        control_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({
            "name": "triangle",
            "color": "220,0,0,255",
            "outline_color": "120,0,0,255",
            "outline_width": "0.3",
            "size": "4.5",
        }))
    control_layer.triggerRepaint()


def _add_results_to_tree(
        assessment_layer, control_layer, buffer_layer=None):
    project = QgsProject.instance()
    layers = [control_layer]
    if assessment_layer is not None:
        layers.append(assessment_layer)
    if buffer_layer is not None:
        layers.append(buffer_layer)
    project.addMapLayers(layers, False)
    group = project.layerTreeRoot().insertGroup(0, "Obstacle assessment")
    group.addLayer(control_layer).setItemVisibilityChecked(True)
    if assessment_layer is not None:
        group.addLayer(assessment_layer).setItemVisibilityChecked(False)
    if buffer_layer is not None:
        group.addLayer(buffer_layer).setItemVisibilityChecked(True)


def _notes(
        moc_m, area_buffer_m, override_tolerance_m, oca_rounding_ft, warnings):
    override = (
        "disabled" if override_tolerance_m is None
        else f"{override_tolerance_m:g} m"
    )
    warning_text = "None" if not warnings else "; ".join(warnings)
    return (
        "<h3>Primary area obstacle assessment</h3>"
        f"<p>MOC: {moc_m:g} m<br>"
        f"Area buffer: {area_buffer_m:g} m<br>"
        f"Tolerance override: {override}<br>"
        f"OCA publication increment: {oca_rounding_ft} ft<br>"
        f"Data warnings: {warning_text}</p>"
    )


def _validate_crs(area_layer, terrain_layer, obstacle_layer):
    layers = (
        ("assessment area", area_layer),
        ("terrain", terrain_layer),
        ("survey", obstacle_layer),
    )
    for label, layer in layers:
        if layer is None:
            continue
        crs = layer.crs()
        if not crs.isValid() or crs.isGeographic():
            raise CrsValidationError(
                f"The {label} layer must use a valid projected CRS"
            )

    area_crs = area_layer.crs()
    for label, layer in (
        ("terrain", terrain_layer),
        ("survey", obstacle_layer),
    ):
        if layer is not None and layer.crs() != area_crs:
            raise CrsValidationError(
                f"The {label} layer must use the same CRS as the assessment area"
            )


def run_primary_area_assessment(
    iface,
    area_layer,
    terrain_layer=None,
    obstacle_layer=None,
    field_mapping: Optional[FieldMapping] = None,
    moc_m: float = 75.0,
    terrain_tolerance_m: float = 50.0,
    override_tolerance_m: Optional[float] = None,
    terrain_band: int = 1,
    use_selected_area: bool = True,
    confirm_missing: Optional[Callable[[Tuple[str, ...]], bool]] = None,
    area_buffer_m: float = 0.0,
    oca_rounding_ft: int = 100,
    load_all_points: bool = True,
) -> AssessmentResult:
    """Run a complete generic primary-area obstacle assessment."""
    del iface  # Kept in the public signature for consistency with plugin modules.
    if area_layer is None:
        raise ValueError("An assessment-area layer is required")
    if terrain_band < 1:
        raise ValueError("Terrain band must be one or greater")
    terrain_tolerance = _valid_nonnegative(
        terrain_tolerance_m, "Terrain vertical tolerance"
    )
    _valid_nonnegative(moc_m, "MOC")
    if override_tolerance_m is not None:
        _valid_nonnegative(override_tolerance_m, "Tolerance override")
    area_buffer_m = _valid_nonnegative(area_buffer_m, "Area buffer")
    _valid_oca_rounding(oca_rounding_ft)
    _validate_crs(area_layer, terrain_layer, obstacle_layer)

    mask_geometry = _build_mask_geometry(
        area_layer, use_selected_area, area_buffer_m
    )
    terrain_records = _terrain_records(
        terrain_layer, mask_geometry, terrain_tolerance, terrain_band
    )
    survey_records = _survey_records(
        obstacle_layer,
        mask_geometry,
        field_mapping,
        override_tolerance_m is not None,
    )

    warnings = []
    if not terrain_records:
        warnings.append("No terrain data was evaluated inside the mask")
    if not survey_records:
        warnings.append("No survey data was evaluated inside the mask")
    warning_tuple = tuple(warnings)
    if warning_tuple and confirm_missing is not None:
        if not confirm_missing(warning_tuple):
            raise AssessmentCancelled("Assessment cancelled by the user")

    records = terrain_records + survey_records
    if load_all_points:
        evaluated, controls = evaluate_records(
            records,
            moc_m=moc_m,
            override_tolerance_m=override_tolerance_m,
            oca_rounding_ft=oca_rounding_ft,
        )
        assessed_count = len(evaluated)
        assessment_layer = _result_layer(
            "Primary assessment", area_layer.crs(), evaluated
        )
    else:
        assessed_count, controls = _evaluate_control_records(
            records,
            moc_m=moc_m,
            override_tolerance_m=override_tolerance_m,
            oca_rounding_ft=oca_rounding_ft,
        )
        assessment_layer = None
    control_layer = _result_layer(
        "Control obstacle", area_layer.crs(), controls
    )
    _style_results(assessment_layer, control_layer)
    buffer_layer = (
        _buffer_result_layer(mask_geometry, area_layer.crs())
        if area_buffer_m > 0
        else None
    )

    layer_notes = _notes(
        moc_m, area_buffer_m, override_tolerance_m,
        oca_rounding_ft, warning_tuple
    )
    if assessment_layer is not None:
        QgsLayerNotesUtils.setLayerNotes(assessment_layer, layer_notes)
    QgsLayerNotesUtils.setLayerNotes(control_layer, layer_notes)
    if buffer_layer is not None:
        QgsLayerNotesUtils.setLayerNotes(buffer_layer, layer_notes)
    _add_results_to_tree(assessment_layer, control_layer, buffer_layer)

    return AssessmentResult(
        assessment_layer=assessment_layer,
        control_layer=control_layer,
        assessed_count=assessed_count,
        control_count=len(controls),
        warnings=warning_tuple,
    )
