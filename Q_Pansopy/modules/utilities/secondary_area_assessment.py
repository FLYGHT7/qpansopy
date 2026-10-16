"""Straight generic secondary-area terrain and obstacle assessment."""

from dataclasses import dataclass, replace
import math
from typing import Optional, Tuple

from qgis.core import (
    QgsFeature,
    QgsField,
    QgsFields,
    QgsGeometry,
    QgsLayerNotesUtils,
    QgsLineSymbol,
    QgsMemoryProviderUtils,
    QgsPointXY,
    QgsProject,
    QgsUnitTypes,
    QgsWkbTypes,
)

from . import primary_area_assessment as primary


@dataclass(frozen=True)
class SecondaryRecord:
    """A source record with its secondary-area geometry measurements."""

    source: object
    moc_m: float
    y_dist: float
    e_dist: float
    ws: float
    area_fid: int
    area_part: int
    axis_perpendicular: Optional[QgsGeometry] = None
    wall_perpendicular: Optional[QgsGeometry] = None

    @property
    def geometry(self):
        return self.source.geometry

    @property
    def oca_m(self):
        return self.source.oca_m


@dataclass(frozen=True)
class SecondaryResult:
    assessment_layer: Optional[object]
    control_layer: object
    exterior_layer: Optional[object]
    assessed_count: int
    control_count: int
    warnings: Tuple[str, ...]
    axis_perpendicular_layer: Optional[object] = None
    wall_perpendicular_layer: Optional[object] = None


def _reference_axis(reference_layer):
    if reference_layer is None or not reference_layer.isValid():
        raise ValueError("A valid reference-line layer is required")
    if reference_layer.selectedFeatureCount() != 1:
        raise ValueError("Select exactly one reference line")
    feature = next(reference_layer.getSelectedFeatures())
    geometry = feature.geometry()
    if geometry.isNull() or geometry.isEmpty():
        raise ValueError("The selected reference line has no geometry")
    if QgsWkbTypes.geometryType(geometry.wkbType()) != QgsWkbTypes.LineGeometry:
        raise ValueError("The reference feature must be a straight line")
    if geometry.isMultipart():
        raise ValueError("The reference line must be a single straight line")
    points = geometry.asPolyline()
    if len(points) < 2:
        raise ValueError("The reference line must contain at least two points")
    origin = points[0]
    dx = points[-1].x() - origin.x()
    dy = points[-1].y() - origin.y()
    length = math.hypot(dx, dy)
    if length <= 0:
        raise ValueError("The reference line must have non-zero length")
    ux, uy = dx / length, dy / length
    for point in points[1:-1]:
        cross = (point.x() - origin.x()) * uy - (point.y() - origin.y()) * ux
        if abs(cross) > max(1e-7, length * 1e-9):
            raise ValueError("The reference line must be straight")
    return feature, origin, ux, uy


def _signed_offset(point, origin, ux, uy):
    return (point.x() - origin.x()) * -uy + (point.y() - origin.y()) * ux


def _projection(point, origin, ux, uy):
    return (point.x() - origin.x()) * ux + (point.y() - origin.y()) * uy


def _polygon_parts(feature):
    geometry = feature.geometry()
    if geometry.isNull() or geometry.isEmpty():
        return []
    if QgsWkbTypes.isMultiType(geometry.wkbType()):
        parts = geometry.asMultiPolygon()
        return [QgsGeometry.fromPolygonXY(part) for part in parts if part]
    polygon = geometry.asPolygon()
    return [QgsGeometry.fromPolygonXY(polygon)] if polygon else []


def _linear_unit_factor(crs):
    factor = QgsUnitTypes.fromUnitToUnitFactor(
        crs.mapUnits(), QgsUnitTypes.DistanceMeters
    )
    if not math.isfinite(factor) or factor <= 0:
        raise primary.CrsValidationError(
            "The assessment CRS must use supported linear units"
        )
    return factor


def _component_specs(area_layer, use_selected_area, origin, ux, uy):
    features = primary._selected_mask_features(area_layer, use_selected_area)
    factor = _linear_unit_factor(area_layer.crs())
    specs = []
    for feature in features:
        for part_index, geometry in enumerate(_polygon_parts(feature), 1):
            offsets = [_signed_offset(point, origin, ux, uy)
                       for point in geometry.vertices()]
            nonzero = [value for value in offsets if abs(value) > 1e-7]
            if not offsets or not nonzero:
                raise ValueError(
                    f"Area feature {feature.id()} part {part_index} "
                    "does not lie on one side of the reference line"
                )
            signs = {1 if value > 0 else -1 for value in nonzero}
            if len(signs) != 1:
                raise ValueError(
                    f"Area feature {feature.id()} part {part_index} crosses "
                    "the reference line; each secondary side must be a "
                    "separate polygon"
                )
            sign = next(iter(signs))
            exterior_offset = max(offsets, key=lambda value: abs(value))
            if exterior_offset * sign <= 0:
                raise ValueError("Could not identify the exterior area edge")
            specs.append({
                "fid": int(feature.id()),
                "part": part_index,
                "geometry": geometry,
                "sign": sign,
                "outer": exterior_offset,
                "factor": factor,
                "projections": [_projection(point, origin, ux, uy)
                                for point in geometry.vertices()],
            })
    if not specs:
        raise ValueError("The selected area contains no polygon geometry")
    return specs


def _line_parts(geometry):
    """Extract linear pieces, ignoring isolated boundary-touch points."""
    if geometry.isNull() or geometry.isEmpty():
        return []
    if (geometry.type() == QgsWkbTypes.LineGeometry
            and not geometry.isMultipart()):
        return [geometry]
    if (geometry.isMultipart()
            or QgsWkbTypes.flatType(geometry.wkbType())
            == QgsWkbTypes.GeometryCollection):
        return [line for part in geometry.asGeometryCollection()
                for line in _line_parts(part)]
    return []


def _clip_perpendicular(point, target, area, tolerance):
    """Keep only the clipped ray interval connected to its obstacle endpoint."""
    length = point.distance(target)
    if length <= tolerance:
        return QgsGeometry()
    dx = (target.x() - point.x()) / length
    dy = (target.y() - point.y()) / length
    segment = QgsGeometry.fromPolylineXY([QgsPointXY(point), target])
    clipped = segment.intersection(area)
    if clipped.isNull():
        raise ValueError("Could not clip the perpendicular to the AOI")
    intervals = []
    for part in _line_parts(clipped):
        positions = [
            (vertex.x() - point.x()) * dx + (vertex.y() - point.y()) * dy
            for vertex in part.vertices()
        ]
        if positions:
            intervals.append((max(0.0, min(positions)),
                              min(length, max(positions))))
    # A clipped line can re-enter the AOI beyond a hole or another arm.
    # Stop at the first gap instead of adding those disconnected fragments.
    endpoint = 0.0
    for start, end in sorted(intervals):
        if start > endpoint + tolerance:
            break
        endpoint = max(endpoint, end)
    if endpoint <= tolerance:
        return QgsGeometry()
    return QgsGeometry.fromPolylineXY([
        QgsPointXY(point),
        QgsPointXY(point.x() + dx * endpoint, point.y() + dy * endpoint),
    ])


def _perpendiculars_for_point(point, spec, origin, ux, uy):
    """Project toward the axis and the exterior wall on this AOI's side."""
    point = QgsPointXY(point)
    projection = _projection(point, origin, ux, uy)
    axis_target = QgsPointXY(origin.x() + ux * projection,
                             origin.y() + uy * projection)
    wall_target = QgsPointXY(axis_target.x() - uy * spec["outer"],
                             axis_target.y() + ux * spec["outer"])
    tolerance = 1e-6 / spec["factor"]
    return (
        _clip_perpendicular(point, axis_target, spec["geometry"], tolerance),
        _clip_perpendicular(point, wall_target, spec["geometry"], tolerance),
    )


def _moc_for_point(point, spec, origin, ux, uy, base_m, perpendiculars=None):
    if perpendiculars is None:
        perpendiculars = _perpendiculars_for_point(point, spec, origin, ux, uy)
    y_dist, e_dist = (
        line.length() * spec["factor"] for line in perpendiculars
    )
    width = y_dist + e_dist
    if width <= 0:
        raise ValueError("Secondary-area width must be greater than zero")
    ratio = min(1.0, max(0.0, e_dist / width))
    return base_m * ratio, y_dist, e_dist, width


def _collect_records(area_layer, terrain_layer, obstacle_layer, field_mapping,
                     base_m, terrain_tolerance_m, override_tolerance_m,
                     terrain_band, use_selected_area, confirm_missing,
                     reference_layer):
    reference, origin, ux, uy = _reference_axis(reference_layer)
    del reference
    specs = _component_specs(area_layer, use_selected_area, origin, ux, uy)
    area_geometries = [spec["geometry"] for spec in specs]
    mask = QgsGeometry.unaryUnion(area_geometries)
    terrain_records = primary._terrain_records(
        terrain_layer, mask,
        primary._valid_nonnegative(terrain_tolerance_m,
                                   "Terrain vertical tolerance"),
        terrain_band,
    )
    survey_records = primary._survey_records(
        obstacle_layer, mask, field_mapping,
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
            raise primary.AssessmentCancelled(
                "Assessment cancelled by the user"
            )

    records = []
    for source in terrain_records + survey_records:
        point = source.geometry.asPoint()
        matching = [spec for spec in specs
                    if spec["geometry"].intersects(source.geometry)]
        if not matching:
            continue
        candidates = []
        for spec in matching:
            try:
                perpendiculars = _perpendiculars_for_point(
                    point, spec, origin, ux, uy
                )
                moc, y_dist, e_dist, width = _moc_for_point(
                    point, spec, origin, ux, uy, base_m, perpendiculars
                )
            except ValueError as error:
                raise ValueError(
                    f"Obstacle '{source.identifier}', area {spec['fid']} "
                    f"part {spec['part']}: {error}"
                ) from error
            evaluated, _ = primary.evaluate_records(
                [source], moc,
                override_tolerance_m=override_tolerance_m,
                oca_rounding_ft=1,
            )
            candidates.append(SecondaryRecord(
                source=evaluated[0], moc_m=moc, y_dist=y_dist,
                e_dist=e_dist, ws=width, area_fid=spec["fid"],
                area_part=spec["part"],
                axis_perpendicular=perpendiculars[0],
                wall_perpendicular=perpendiculars[1],
            ))
        records.append(max(candidates, key=lambda item: (
            item.moc_m, -item.area_fid, -item.area_part
        )))
    return records, warning_tuple, specs, origin, ux, uy


def _secondary_fields():
    fields = primary._output_fields()
    for field in (
        QgsField("y_dist", primary._TYPE_DOUBLE, len=20, prec=3),
        QgsField("e_dist", primary._TYPE_DOUBLE, len=20, prec=3),
        QgsField("ws", primary._TYPE_DOUBLE, len=20, prec=3),
        QgsField("moc_base_m", primary._TYPE_DOUBLE, len=20, prec=3),
        QgsField("area_fid", primary._TYPE_INT, len=20),
        QgsField("area_part", primary._TYPE_INT, len=20),
    ):
        fields.append(field)
    return fields


def _secondary_layer(name, crs, records, base_m):
    fields = _secondary_fields()
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        name, fields, QgsWkbTypes.Point, crs
    )
    provider = layer.dataProvider()
    features = []
    for item in records:
        record = item.source
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry(record.geometry))
        feature.setAttributes([
            record.identifier, record.layer_type, record.obstacle_type,
            record.elevation_m, record.tolerance_m,
            record.applied_tolerance_m, "secondary area", item.moc_m,
            record.oca_m, record.oca_ft, record.oca_pub_increment,
            record.oca_pub_ft, item.y_dist, item.e_dist, item.ws, base_m,
            item.area_fid, item.area_part,
        ])
        features.append(feature)
        if len(features) >= 5000:
            if not provider.addFeatures(features)[0]:
                raise RuntimeError(f"Could not populate result layer '{name}'")
            features = []
    if features and not provider.addFeatures(features)[0]:
        raise RuntimeError(f"Could not populate result layer '{name}'")
    layer.updateExtents()
    return layer


def _exterior_layer(specs, crs, origin, ux, uy):
    fields = QgsFields()
    fields.append(QgsField("area_fid", primary._TYPE_INT))
    fields.append(QgsField("area_part", primary._TYPE_INT))
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        "Secondary exterior reference lines", fields, QgsWkbTypes.LineString,
        crs,
    )
    features = []
    extension = 100.0
    for spec in specs:
        padding = extension / spec["factor"]
        start = min(spec["projections"]) - padding
        end = max(spec["projections"]) + padding
        offset = spec["outer"]
        points = [
            QgsPointXY(origin.x() + ux * start - uy * offset,
                       origin.y() + uy * start + ux * offset),
            QgsPointXY(origin.x() + ux * end - uy * offset,
                       origin.y() + uy * end + ux * offset),
        ]
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPolylineXY(points))
        feature.setAttributes([spec["fid"], spec["part"]])
        features.append(feature)
    if not layer.dataProvider().addFeatures(features)[0]:
        raise RuntimeError("Could not create secondary exterior reference lines")
    layer.updateExtents()
    layer.renderer().setSymbol(QgsLineSymbol.createSimple({
        "line_color": "255,170,0,255", "line_width": "0.8",
        "line_style": "dash",
    }))
    return layer


def _perpendicular_layer(name, crs, records, geometry_attribute,
                         distance_attribute, color):
    """Create the measured segments for all evaluated terrain/survey points."""
    fields = QgsFields()
    for field in (
        QgsField("id", primary._TYPE_STRING, len=80),
        QgsField("layer_type", primary._TYPE_STRING, len=20),
        QgsField("area_fid", primary._TYPE_INT),
        QgsField("area_part", primary._TYPE_INT),
        QgsField("distance_m", primary._TYPE_DOUBLE, len=20, prec=3),
    ):
        fields.append(field)
    layer = QgsMemoryProviderUtils.createMemoryLayer(
        name, fields, QgsWkbTypes.LineString, crs
    )
    provider = layer.dataProvider()
    features = []
    for record in records:
        geometry = getattr(record, geometry_attribute)
        if geometry is None or geometry.isEmpty():
            continue
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry(geometry))
        feature.setAttributes([
            record.source.identifier, record.source.layer_type,
            record.area_fid, record.area_part,
            getattr(record, distance_attribute),
        ])
        features.append(feature)
        if len(features) == 5000:
            if not provider.addFeatures(features)[0]:
                raise RuntimeError(f"Could not populate result layer '{name}'")
            features = []
    if features and not provider.addFeatures(features)[0]:
        raise RuntimeError(f"Could not populate result layer '{name}'")
    layer.updateExtents()
    layer.renderer().setSymbol(QgsLineSymbol.createSimple({
        "line_color": color, "line_width": "0.5",
    }))
    return layer


def run_secondary_area_assessment(
        iface, area_layer, reference_layer, terrain_layer=None,
        obstacle_layer=None, field_mapping=None, moc_m=75.0,
        terrain_tolerance_m=50.0, override_tolerance_m=None,
        terrain_band=1, use_selected_area=True, confirm_missing=None,
        oca_rounding_ft=100, load_all_points=False,
        load_exterior_lines=False):
    """Evaluate selected secondary polygons against a selected straight axis."""
    del iface
    if area_layer is None:
        raise ValueError("A secondary-area layer is required")
    if terrain_layer is None and obstacle_layer is None:
        raise ValueError("Please select a terrain or survey layer")
    base_m = primary._valid_nonnegative(moc_m, "Base MOC")
    primary._valid_nonnegative(terrain_tolerance_m,
                               "Terrain vertical tolerance")
    if override_tolerance_m is not None:
        primary._valid_nonnegative(override_tolerance_m,
                                   "Tolerance override")
    primary._valid_oca_rounding(oca_rounding_ft)
    if terrain_band < 1:
        raise ValueError("Terrain band must be one or greater")
    primary._validate_crs(area_layer, terrain_layer, obstacle_layer)
    if reference_layer is None or reference_layer.crs() != area_layer.crs():
        raise primary.CrsValidationError(
            "The reference line must use the same CRS as the assessment area"
        )
    _reference_axis(reference_layer)
    records, warnings, specs, origin, ux, uy = _collect_records(
        area_layer, terrain_layer, obstacle_layer, field_mapping,
        base_m, terrain_tolerance_m, override_tolerance_m,
        terrain_band, use_selected_area, confirm_missing, reference_layer,
    )

    # Apply the requested publication increment after variable MOC evaluation.
    evaluated = []
    for item in records:
        source = item.source
        values = primary._evaluation_values(
            source, item.moc_m, override_tolerance_m
        )
        source = primary._make_evaluated_record(
            source, item.moc_m, values, oca_rounding_ft
        )
        evaluated.append(replace(item, source=source))
    assessed_count = len(evaluated)
    if evaluated:
        maximum = max(item.oca_m for item in evaluated)
        controls = [item for item in evaluated if math.isclose(
            item.oca_m, maximum, rel_tol=0.0, abs_tol=1e-9
        )]
    else:
        controls = []
    assessment_layer = (
        _secondary_layer("Secondary assessment", area_layer.crs(),
                         evaluated, base_m)
        if load_all_points else None
    )
    control_layer = _secondary_layer(
        "Control obstacle", area_layer.crs(), controls, base_m
    )
    primary._style_results(assessment_layer, control_layer)
    exterior_layer = (
        _exterior_layer(specs, area_layer.crs(), origin, ux, uy)
        if load_exterior_lines else None
    )
    axis_perpendicular_layer = _perpendicular_layer(
        "Secondary perpendiculars to reference axis", area_layer.crs(),
        evaluated, "axis_perpendicular", "y_dist", "37,99,235,255",
    )
    wall_perpendicular_layer = _perpendicular_layer(
        "Secondary perpendiculars to exterior walls", area_layer.crs(),
        evaluated, "wall_perpendicular", "e_dist", "192,38,211,255",
    )
    override_note = (
        "disabled" if override_tolerance_m is None
        else f"{override_tolerance_m:g} m"
    )
    notes = (
        "<h3>Straight secondary-area obstacle assessment</h3>"
        f"<p>Base MOC: {base_m:g} m<br>"
        f"Reference line: {reference_layer.name()}<br>"
        f"Terrain tolerance: {terrain_tolerance_m:g} m<br>"
        f"Survey tolerance override: {override_note}<br>"
        "Variable MOC is proportional to distance from the outer edge.<br>"
        "Perpendicular distances are clipped to the AOI from each obstacle.<br>"
        f"OCA publication increment: {oca_rounding_ft} ft<br>"
        f"Data warnings: {'None' if not warnings else '; '.join(warnings)}</p>"
    )
    for layer in (assessment_layer, control_layer, exterior_layer,
                  axis_perpendicular_layer, wall_perpendicular_layer):
        if layer is not None:
            QgsLayerNotesUtils.setLayerNotes(layer, notes)
    project = QgsProject.instance()
    layers = [control_layer, axis_perpendicular_layer, wall_perpendicular_layer]
    if assessment_layer is not None:
        layers.append(assessment_layer)
    if exterior_layer is not None:
        layers.append(exterior_layer)
    project.addMapLayers(layers, False)
    group = project.layerTreeRoot().insertGroup(0, "Obstacle assessment")
    for layer in layers:
        group.addLayer(layer).setItemVisibilityChecked(
            layer is control_layer or layer is axis_perpendicular_layer
            or layer is wall_perpendicular_layer
        )
    return SecondaryResult(
        assessment_layer, control_layer, exterior_layer, assessed_count,
        len(controls), warnings,
        axis_perpendicular_layer, wall_perpendicular_layer,
    )
