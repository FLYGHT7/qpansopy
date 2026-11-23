import os
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("qgis")
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsGeometry,
    QgsMapLayerProxyModel,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from qgis.PyQt.QtGui import QColor  # noqa: E402

from Q_Pansopy.modules.utilities.ama_grid import run_ama_grid  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402


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


def _capturing_iface(canvas_crs):
    iface = _Iface(canvas_crs)
    messages = []
    iface.messageBar = lambda: SimpleNamespace(
        pushMessage=lambda *args, **kwargs: messages.append((args, kwargs["level"])))
    return iface, messages


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
    iface, messages = _capturing_iface(QgsCoordinateReferenceSystem("EPSG:32631"))
    run_ama_grid(
        iface,
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
    assert messages == [
        (("QPANSOPY", "AMA grid exported to KML"), Qgis.MessageLevel.Success),
        (("QPANSOPY", "Created 1 AMA grid cells"), Qgis.MessageLevel.Success),
    ]


def test_run_ama_grid_preserves_schema_attributes_geometry_style_and_messages():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
    iface, messages = _capturing_iface(wgs84)
    run_ama_grid(iface, QgsRectangle(-1, -1, 1, 1), wgs84,
                 {"grid_type": "AMA_1", "output_crs": "wgs84"})
    layer = _result_layer()
    assert layer.name() == "AMA Grid - 1 degree"
    assert layer.wkbType() == Qgis.WkbType.Polygon
    assert [(field.name(), field.type()) for field in layer.fields()] == [
        ("cell_id", QMetaType.Type.QString), ("ama_type", QMetaType.Type.QString),
        ("south_lat", QMetaType.Type.Double), ("west_lon", QMetaType.Type.Double),
        ("north_lat", QMetaType.Type.Double), ("east_lon", QMetaType.Type.Double),
    ]
    expected = [
        ["AMA_1_S01_W001", "AMA_1", -1.0, -1.0, 0.0, 0.0],
        ["AMA_1_S01_E000", "AMA_1", -1.0, 0.0, 0.0, 1.0],
        ["AMA_1_N00_W001", "AMA_1", 0.0, -1.0, 1.0, 0.0],
        ["AMA_1_N00_E000", "AMA_1", 0.0, 0.0, 1.0, 1.0],
    ]
    features = list(layer.getFeatures())
    assert [feature.attributes() for feature in features] == expected
    for feature, (_, _, south, west, north, east) in zip(features, expected):
        assert feature.geometry().equals(
            QgsGeometry.fromRect(QgsRectangle(west, south, east, north)))
    renderer = layer.renderer()
    assert renderer.type() == "singleSymbol"
    symbol = renderer.symbol()
    # "#1976D233" is parsed as #AARRGGBB (pre-existing behaviour, preserved).
    assert symbol.color().name(QColor.NameFormat.HexArgb) == "#1976d233"
    assert symbol.symbolLayer(0).strokeColor().name(QColor.NameFormat.HexArgb) == "#ff1976d2"
    assert symbol.symbolLayer(0).strokeWidth() == pytest.approx(0.4)
    assert not layer.labelsEnabled()
    assert messages == [
        (("QPANSOPY", "Created 4 AMA grid cells"), Qgis.MessageLevel.Success)]


def _ama_dock(plugin):
    instance, _ = plugin
    QgsProject.instance().removeAllMapLayers()
    instance.toggle_dock("AMAGrid")
    return instance, instance.modules["AMAGrid"]["GUI_INSTANCE"]


def _ama_outputs():
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if layer.name().startswith("AMA Grid")]


def test_dock_creates_project_crs_grid_from_canvas_extent(plugin, qgis_app):
    instance, dock = _ama_dock(plugin)
    assert dock.extentLayerComboBox.filters() == QgsMapLayerProxyModel.Filter.All
    assert not dock.extentLayerComboBox.isEnabled()
    canvas = instance.iface.mapCanvas()
    # About lon -86.8..-86.7, lat 14.47..14.56: inside the single 1 degree cell N14/W087.
    canvas.setExtent(QgsRectangle(520000, 1600000, 530000, 1610000))
    qgis_app.processEvents()
    dock.calculateButton.click()
    outputs = _ama_outputs()
    assert len(outputs) == 1
    assert outputs[0].crs().authid() == "EPSG:32616"
    assert [feature["cell_id"] for feature in outputs[0].getFeatures()] == ["AMA_1_N14_W087"]
    assert "Created 1° × 1° (AMA_1) AMA grid from map canvas." in dock.logTextEdit.toPlainText()


def test_dock_creates_wgs84_half_degree_grid_from_layer_extent(plugin):
    _, dock = _ama_dock(plugin)
    source = QgsVectorLayer("Point?crs=EPSG:4326", "AMA source", "memory")
    features = []
    for x, y in ((-0.9, -0.9), (0.9, 0.9)):
        feature = QgsFeature()
        feature.setGeometry(QgsGeometry.fromPointXY(QgsPointXY(x, y)))
        features.append(feature)
    assert source.dataProvider().addFeatures(features)[0]
    source.updateExtents()
    QgsProject.instance().addMapLayer(source)
    dock.extentSourceComboBox.setCurrentIndex(1)
    assert dock.extentLayerComboBox.isEnabled()
    dock.extentLayerComboBox.setLayer(source)
    dock.amaSizeComboBox.setCurrentIndex(1)
    dock.outputCrsComboBox.setCurrentIndex(1)
    dock.calculateButton.click()
    outputs = _ama_outputs()
    assert len(outputs) == 1
    assert outputs[0].name() == "AMA Grid - 30 minutes"
    assert outputs[0].crs().authid() == "EPSG:4326"
    assert outputs[0].featureCount() == 16
    assert "Created 30′ × 30′ (AMA_05) AMA grid from AMA source." in dock.logTextEdit.toPlainText()


def test_dock_reports_missing_extent_layer_as_warning(plugin, monkeypatch):
    instance, dock = _ama_dock(plugin)
    messages = []
    monkeypatch.setattr(instance.iface.messageBar(), "pushMessage",
                        lambda title, text, level: messages.append((title, text, level)))
    dock.extentSourceComboBox.setCurrentIndex(1)
    dock.extentLayerComboBox.setLayer(None)
    dock.calculateButton.click()
    assert "Error: Select a layer for the extent source" in dock.logTextEdit.toPlainText()
    assert messages == [
        ("QPANSOPY", "Select a layer for the extent source", Qgis.MessageLevel.Warning)]
    assert not _ama_outputs()
