"""Generic primary-area terrain and obstacle assessment."""

from dataclasses import dataclass
import math
from typing import Callable, List, Optional, Sequence, Tuple

try:
    from qgis.PyQt.QtCore import QMetaType
    _TYPE_DOUBLE = QMetaType.Type.Double
    _TYPE_STRING = QMetaType.Type.QString
except (ImportError, AttributeError):
    from qgis.PyQt.QtCore import QVariant
    _TYPE_DOUBLE = QVariant.Double
    _TYPE_STRING = QVariant.String
from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerNotesUtils,
    QgsMarkerSymbol,
    QgsMemoryProviderUtils,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsWkbTypes,
)


@dataclass(frozen=True)
class FieldMapping:
    """Fields used to normalize an obstacle layer."""

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
    geometry: object


@dataclass(frozen=True)
class AssessmentResult:
    """Layers and counts produced by one assessment run."""

    assessment_layer: object
    control_layer: object
    assessed_count: int
    control_count: int
    warnings: Tuple[str, ...]


class AssessmentCancelled(Exception):
    """Raised when the user declines an incomplete-data assessment."""


def _valid_nonnegative(value: float, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite value of zero or greater")
    return number


def evaluate_records(
    records: Sequence[SourceRecord],
    moc_m: float,
    override_tolerance_m: Optional[float] = None,
) -> Tuple[List[EvaluatedRecord], List[EvaluatedRecord]]:
    """Evaluate normalized points and return all tied controlling obstacles."""
    moc = _valid_nonnegative(moc_m, "MOC")
    override = (
        None
        if override_tolerance_m is None
        else _valid_nonnegative(override_tolerance_m, "Tolerance override")
    )
    evaluated: List[EvaluatedRecord] = []

    for record in records:
        elevation = float(record.elevation_m)
        if not math.isfinite(elevation):
            raise ValueError(
                f"Elevation for obstacle '{record.identifier}' must be finite"
            )
        source_tolerance = _valid_nonnegative(
            record.tolerance_m,
            f"Vertical tolerance for obstacle '{record.identifier}'",
        )
        applied_tolerance = source_tolerance if override is None else override
        oca_m = elevation + applied_tolerance + moc
        evaluated.append(EvaluatedRecord(
            identifier=record.identifier,
            layer_type=record.layer_type,
            obstacle_type=record.obstacle_type,
            coordinates=record.coordinates,
            elevation_m=elevation,
            tolerance_m=source_tolerance,
            applied_tolerance_m=applied_tolerance,
            moc_m=moc,
            oca_m=oca_m,
            oca_ft=round(oca_m / 0.3048, 3),
            geometry=record.geometry,
        ))

    if not evaluated:
        return [], []

    maximum = max(item.oca_m for item in evaluated)
    controls = [
        item for item in evaluated
        if math.isclose(item.oca_m, maximum, rel_tol=0.0, abs_tol=1e-9)
    ]
    return evaluated, controls


def _selected_mask_features(area_layer, use_selected_area: bool):
    if use_selected_area:
        if area_layer.selectedFeatureCount() == 0:
            raise ValueError(
                "Use selected areas is enabled, but the area layer has no "
                "selected features"
            )
        return list(area_layer.selectedFeatures())
    return list(area_layer.getFeatures())


def _build_mask_geometry(area_layer, use_selected_area: bool):
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

    return mask_geometry


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
        raise ValueError("Obstacle field mapping is required")

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
        raise ValueError("Missing obstacle field mapping: " + ", ".join(missing))

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


def _style_results(assessment_layer, control_layer):
    assessment_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({
        "name": "circle",
        "color": "220,0,0,255",
        "outline_style": "no",
        "size": "1.0",
    }))
    control_layer.renderer().setSymbol(QgsMarkerSymbol.createSimple({
        "name": "triangle",
        "color": "220,0,0,255",
        "outline_color": "120,0,0,255",
        "outline_width": "0.3",
        "size": "4.5",
    }))


def _add_results_to_tree(assessment_layer, control_layer):
    project = QgsProject.instance()
    project.addMapLayers([control_layer, assessment_layer], False)
    group = project.layerTreeRoot().insertGroup(0, "Obstacle assessment")
    group.addLayer(control_layer).setItemVisibilityChecked(True)
    group.addLayer(assessment_layer).setItemVisibilityChecked(False)


def _notes(moc_m, override_tolerance_m, warnings):
    override = (
        "disabled" if override_tolerance_m is None
        else f"{override_tolerance_m:g} m"
    )
    warning_text = "None" if not warnings else "; ".join(warnings)
    return (
        "<h3>Primary area obstacle assessment</h3>"
        f"<p>MOC: {moc_m:g} m<br>"
        f"Tolerance override: {override}<br>"
        f"Data warnings: {warning_text}</p>"
    )


def _validate_crs(area_layer, terrain_layer, obstacle_layer):
    area_crs = area_layer.crs()
    if not area_crs.isValid() or area_crs.isGeographic():
        raise ValueError("The assessment area must use a valid projected CRS")
    for label, layer in (
        ("terrain", terrain_layer),
        ("obstacle", obstacle_layer),
    ):
        if layer is not None and layer.crs() != area_crs:
            raise ValueError(
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
    _validate_crs(area_layer, terrain_layer, obstacle_layer)

    mask_geometry = _build_mask_geometry(
        area_layer, use_selected_area
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
        warnings.append("No obstacle data was evaluated inside the mask")
    warning_tuple = tuple(warnings)
    if warning_tuple and confirm_missing is not None:
        if not confirm_missing(warning_tuple):
            raise AssessmentCancelled("Assessment cancelled by the user")

    evaluated, controls = evaluate_records(
        terrain_records + survey_records,
        moc_m=moc_m,
        override_tolerance_m=override_tolerance_m,
    )
    assessment_layer = _result_layer(
        "Primary assessment", area_layer.crs(), evaluated
    )
    control_layer = _result_layer(
        "Control obstacle", area_layer.crs(), controls
    )
    _style_results(assessment_layer, control_layer)

    layer_notes = _notes(moc_m, override_tolerance_m, warning_tuple)
    QgsLayerNotesUtils.setLayerNotes(assessment_layer, layer_notes)
    QgsLayerNotesUtils.setLayerNotes(control_layer, layer_notes)
    _add_results_to_tree(assessment_layer, control_layer)

    return AssessmentResult(
        assessment_layer=assessment_layer,
        control_layer=control_layer,
        assessed_count=len(evaluated),
        control_count=len(controls),
        warnings=warning_tuple,
    )
