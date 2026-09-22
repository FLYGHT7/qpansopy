"""Create latitude/longitude polygon cells for Area Minimum Altitude (AMA).

The module deliberately creates geometry only.  Obstacle, terrain and
altitude calculations belong to a later AMA assessment workflow; this tool
provides the exact 1 degree or 30 minute reference cells that those workflows
can consume.
"""

import datetime
import math
import os

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsFillSymbol,
    QgsGeometry,
    QgsProject,
    QgsRectangle,
    QgsSingleSymbolRenderer,
    QgsVectorFileWriter,
    QgsVectorLayer,
    Qgis,
)


GRID_STEPS = {"AMA_1": 1.0, "AMA_05": 0.5}
MAX_CELLS = 50000
WGS84_AUTHID = "EPSG:4326"


def grid_step(grid_type):
    """Return the cell size in degrees for a supported AMA grid type."""
    try:
        return GRID_STEPS[str(grid_type)]
    except KeyError as exc:
        raise ValueError("Unsupported AMA grid type: {0}".format(grid_type)) from exc


def _finite_extent(extent):
    values = (extent.xMinimum(), extent.yMinimum(), extent.xMaximum(), extent.yMaximum())
    return all(math.isfinite(float(value)) for value in values)


def _snap_indices(value_min, value_max, step):
    """Snap an extent outward and return integer grid indices."""
    factor = int(round(1.0 / step))
    epsilon = 1e-10
    return (
        math.floor(value_min * factor + epsilon),
        math.ceil(value_max * factor - epsilon),
    )


def snapped_grid_indices(extent, grid_type):
    """Return ``(west, south, east, north)`` integer cell indices.

    Indices are multiplied by 1 for 1 degree cells and by 2 for 30 minute
    cells.  The returned bounds are exclusive at east/north, as required by
    ``range`` when building complete cells.
    """
    step = grid_step(grid_type)
    if extent is None or not _finite_extent(extent):
        raise ValueError("AMA extent must contain finite coordinates")
    xmin = float(extent.xMinimum())
    xmax = float(extent.xMaximum())
    ymin = float(extent.yMinimum())
    ymax = float(extent.yMaximum())
    if xmin >= xmax or ymin >= ymax:
        raise ValueError("AMA extent must have a positive width and height")
    if xmin < -180.0 or xmax > 180.0 or ymin < -90.0 or ymax > 90.0:
        raise ValueError("AMA extent must be within longitude [-180, 180] and latitude [-90, 90]")

    west, east = _snap_indices(xmin, xmax, step)
    south, north = _snap_indices(ymin, ymax, step)
    factor = int(round(1.0 / step))
    west = max(-180 * factor, west)
    east = min(180 * factor, east)
    south = max(-90 * factor, south)
    north = min(90 * factor, north)
    if west >= east or south >= north:
        raise ValueError("AMA extent does not contain any grid cell")
    cell_count = (east - west) * (north - south)
    if cell_count > MAX_CELLS:
        raise ValueError("AMA grid would create {0} cells; maximum is {1}".format(cell_count, MAX_CELLS))
    return west, south, east, north


def _coordinate_token(value, axis, step):
    factor = int(round(1.0 / step))
    degrees = abs(int(value)) // factor
    minutes = 30 if factor == 2 and abs(int(value)) % 2 else 0
    hemisphere = ("N" if value >= 0 else "S") if axis == "lat" else ("E" if value >= 0 else "W")
    width = 2 if axis == "lat" or factor == 2 else 3
    return "{0}{1:0{2}d}{3}".format(
        hemisphere, degrees, width, "30" if minutes else "")


def cell_id(west, south, grid_type):
    """Build a deterministic, aviation-readable identifier for a cell."""
    step = grid_step(grid_type)
    return "{0}_{1}_{2}".format(
        grid_type,
        _coordinate_token(south, "lat", step),
        _coordinate_token(west, "lon", step),
    )


def _transform_extent(extent, source_crs):
    target_crs = QgsCoordinateReferenceSystem(WGS84_AUTHID)
    if source_crs is None or not source_crs.isValid():
        raise ValueError("A valid source CRS is required")
    if source_crs == target_crs:
        return QgsRectangle(extent)
    transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
    transformed = transform.transformBoundingBox(extent)
    if transformed.xMinimum() > transformed.xMaximum():
        raise ValueError("AMA extent crosses the antimeridian; select a non-wrapping extent")
    return transformed


def _layer_name(grid_type):
    return "AMA Grid - 1 degree" if grid_type == "AMA_1" else "AMA Grid - 30 minutes"


def _build_layer(indices, grid_type):
    west_i, south_i, east_i, north_i = indices
    step = grid_step(grid_type)
    layer = QgsVectorLayer("Polygon?crs={0}".format(WGS84_AUTHID), _layer_name(grid_type), "memory")
    provider = layer.dataProvider()
    provider.addAttributes([
        QgsField("cell_id", QVariant.String),
        QgsField("ama_type", QVariant.String),
        QgsField("south_lat", QVariant.Double),
        QgsField("west_lon", QVariant.Double),
        QgsField("north_lat", QVariant.Double),
        QgsField("east_lon", QVariant.Double),
    ])
    layer.updateFields()
    features = []
    for lat_i in range(south_i, north_i):
        south = lat_i * step
        north = (lat_i + 1) * step
        for lon_i in range(west_i, east_i):
            west = lon_i * step
            east = (lon_i + 1) * step
            feature = QgsFeature(layer.fields())
            feature.setGeometry(QgsGeometry.fromRect(QgsRectangle(west, south, east, north)))
            feature.setAttributes([
                cell_id(lon_i, lat_i, grid_type), grid_type,
                south, west, north, east,
            ])
            features.append(feature)
    provider.addFeatures(features)
    layer.updateExtents()
    symbol = QgsFillSymbol.createSimple({
        "color": "#1976D233",
        "outline_color": "#1976D2",
        "outline_width": "0.4",
    })
    layer.setRenderer(QgsSingleSymbolRenderer(symbol))
    layer.setLabelsEnabled(False)
    return layer


def _export_kml(layer, output_dir, grid_type):
    if not output_dir:
        raise ValueError("Choose an output folder before exporting KML")
    if not os.path.isdir(output_dir):
        raise ValueError("KML output folder does not exist: {0}".format(output_dir))
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, "{0}_{1}.kml".format(grid_type.lower(), stamp))
    result = QgsVectorFileWriter.writeAsVectorFormat(
        layer, path, "utf-8", QgsCoordinateReferenceSystem(WGS84_AUTHID), "KML"
    )
    if result[0] != QgsVectorFileWriter.NoError:
        raise RuntimeError("KML export failed: {0}".format(result[1]))
    return path


def run_ama_grid(iface, extent, source_crs, params=None):
    """Create an AMA grid layer and optionally export it to KML.

    ``params`` accepts ``grid_type`` (``AMA_1`` or ``AMA_05``),
    ``export_kml`` and ``output_dir``.  The function returns ``True`` after
    the layer has been added to the current QGIS project.
    """
    params = params or {}
    grid_type = params.get("grid_type", "AMA_1")
    transformed_extent = _transform_extent(extent, source_crs)
    indices = snapped_grid_indices(transformed_extent, grid_type)
    layer = _build_layer(indices, grid_type)
    kml_path = None
    if params.get("export_kml", False):
        kml_path = _export_kml(layer, params.get("output_dir", ""), grid_type)
    QgsProject.instance().addMapLayer(layer)
    if kml_path:
        iface.messageBar().pushMessage("QPANSOPY", "AMA grid exported to KML", level=Qgis.Success)
    iface.messageBar().pushMessage(
        "QPANSOPY", "Created {0} AMA grid cells".format(layer.featureCount()), level=Qgis.Success
    )
    return True
