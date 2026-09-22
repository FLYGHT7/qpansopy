import os

import pytest

pytest.importorskip("qgis")

from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsProject,
    QgsRectangle,
)

from Q_Pansopy.modules.utilities.ama_grid import run_ama_grid  # noqa: E402


class _MessageBar:
    def pushMessage(self, *args, **kwargs):
        return None


class _Iface:
    def messageBar(self):
        return _MessageBar()


@pytest.fixture(scope="module", autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


def test_run_ama_grid_adds_exact_wgs84_cells(tmp_path):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    result = run_ama_grid(
        _Iface(),
        QgsRectangle(-1, -1, 1, 1),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        {"grid_type": "AMA_1"},
    )
    assert result is True
    layer = list(project.mapLayers().values())[-1]
    assert layer.crs().authid() == "EPSG:4326"
    assert layer.featureCount() == 4
    assert {feature["ama_type"] for feature in layer.getFeatures()} == {"AMA_1"}
    assert all(feature["cell_id"] for feature in layer.getFeatures())


def test_run_ama_grid_can_export_kml(tmp_path):
    project = QgsProject.instance()
    project.removeAllMapLayers()
    run_ama_grid(
        _Iface(),
        QgsRectangle(0, 0, 0.5, 0.5),
        QgsCoordinateReferenceSystem("EPSG:4326"),
        {"grid_type": "AMA_05", "export_kml": True, "output_dir": str(tmp_path)},
    )
    assert any(name.endswith(".kml") for name in os.listdir(tmp_path))
