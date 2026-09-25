import os
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("qgis")

from qgis.core import (  # noqa: E402
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
)

from Q_Pansopy.modules.utilities.ama_grid import run_ama_grid  # noqa: E402


class _MessageBar:
    def pushMessage(self, *args, **kwargs):
        return None


class _Iface:
    def __init__(self, canvas_crs):
        self.canvas_crs = canvas_crs

    def messageBar(self):
        return _MessageBar()

    def mapCanvas(self):
        return self

    def mapSettings(self):
        return self

    def destinationCrs(self):
        return self.canvas_crs


def _result_layer():
    return list(QgsProject.instance().mapLayers().values())[-1]


def test_run_ama_grid_adds_exact_wgs84_cells():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    result = run_ama_grid(
        _Iface(QgsCoordinateReferenceSystem("EPSG:4326")),
        QgsRectangle(-1, -1, 1, 1),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        {"grid_type": "AMA_1", "output_crs": "wgs84"},
    )
    assert result is True
    layer = _result_layer()
    assert layer.crs().authid() == "EPSG:4326"
    assert layer.featureCount() == 4
    assert {feature["ama_type"] for feature in layer.getFeatures()} == {"AMA_1"}
    assert all(feature["cell_id"] for feature in layer.getFeatures())


def test_run_ama_grid_defaults_to_projected_crs_and_preserves_cell_edge():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    projected_crs = QgsCoordinateReferenceSystem("EPSG:32631")
    run_ama_grid(
        _Iface(projected_crs),
        QgsRectangle(0, 0, 1, 1),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        {"grid_type": "AMA_1"},
    )
    layer = _result_layer()
    assert layer.crs() == projected_crs
    assert layer.featureCount() == 1
    feature = next(layer.getFeatures())
    assert feature["west_lon"] == 0
    assert feature["east_lon"] == 1
    assert len(feature.geometry().asPolygon()[0]) > 5
    transform = QgsCoordinateTransform(
        QgsCoordinateReferenceSystem("EPSG:4326"), projected_crs, project
    )
    edge_midpoint = transform.transform(QgsPointXY(0.5, 1))
    boundary = QgsGeometry.fromPolylineXY(feature.geometry().asPolygon()[0])
    assert boundary.distance(
        QgsGeometry.fromPointXY(edge_midpoint)
    ) < 1


@pytest.mark.parametrize("canvas_crs", [
    QgsCoordinateReferenceSystem("EPSG:4326"),
    QgsCoordinateReferenceSystem("EPSG:4978"),
    QgsCoordinateReferenceSystem(),
])
def test_run_ama_grid_rejects_non_projected_canvas_crs(canvas_crs):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    with pytest.raises(ValueError, match="projected CRS"):
        run_ama_grid(
            _Iface(canvas_crs),
            QgsRectangle(0, 0, 1, 1),
            QgsCoordinateReferenceSystem("EPSG:4326"),
            {"grid_type": "AMA_1"},
        )
    assert not project.mapLayers()


def test_run_ama_grid_can_export_kml(tmp_path):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    run_ama_grid(
        _Iface(QgsCoordinateReferenceSystem("EPSG:32631")),
        QgsRectangle(0, 0, 0.5, 0.5),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        {"grid_type": "AMA_05", "export_kml": True, "output_dir": str(tmp_path)},
    )
    assert _result_layer().crs().authid() == "EPSG:32631"
    kml_files = [name for name in os.listdir(tmp_path) if name.endswith(".kml")]
    assert len(kml_files) == 1
    root = ET.parse(tmp_path / kml_files[0]).getroot()
    coordinates = next(node.text for node in root.iter() if node.tag.endswith("coordinates"))
    for position in coordinates.split():
        longitude, latitude = (float(value) for value in position.split(",")[:2])
        assert -180 <= longitude <= 180
        assert -90 <= latitude <= 90
