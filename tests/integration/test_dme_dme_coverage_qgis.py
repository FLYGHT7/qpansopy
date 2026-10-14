"""QGIS runtime checks for DME/DME coverage geometry and output layers."""

import math
from pathlib import Path

import pytest

pytest.importorskip("qgis")
pytestmark = pytest.mark.qgis_runtime

from qgis.PyQt.QtCore import QVariant  # noqa: E402
from qgis.core import (  # noqa: E402
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsFeature,
    QgsField,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsVectorLayer,
)
from qgis.PyQt.QtGui import QColor, QImage, QPainter  # noqa: E402
from qgis.PyQt.QtSvg import QSvgRenderer  # noqa: E402
from qgis.PyQt.QtWidgets import QMainWindow  # noqa: E402

from Q_Pansopy.modules.pbn.dme_dme_coverage import (  # noqa: E402
    MAX_DOC_NM,
    NM_TO_M,
    _doc_value,
    run_dme_dme_coverage,
)
from Q_Pansopy.dockwidgets.pbn.qpansopy_dme_dme_coverage_dockwidget import (  # noqa: E402
    QPANSOPYDMEDMECoverageDockWidget,
)


@pytest.fixture(scope="module", autouse=True)
def qgis_app():
    existing = QgsApplication.instance()
    app = existing or QgsApplication([], False)
    if existing is None:
        app.initQgis()
    yield app
    if existing is None:
        app.exitQgis()


class _MessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _Iface:
    def __init__(self):
        self.bar = _MessageBar()

    def messageBar(self):
        return self.bar


def _dme_layer(project, crs="EPSG:4326", docs=(150.0, 250.0)):
    layer = QgsVectorLayer("Point?crs={0}".format(crs), "DMEs", "memory")
    layer.dataProvider().addAttributes([QgsField("DOC_NM", QVariant.Double)])
    layer.updateFields()
    source_crs = QgsCoordinateReferenceSystem("EPSG:4326")
    target_crs = QgsCoordinateReferenceSystem(crs)
    transform = QgsCoordinateTransform(source_crs, target_crs, project)
    longitude_delta = 20.0 / (60.0 * math.cos(math.radians(14.0)))
    features = []
    for longitude, doc in zip((-87.0, -87.0 + longitude_delta), docs):
        point = transform.transform(QgsPointXY(longitude, 14.0))
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromPointXY(point))
        feature.setAttributes([doc])
        features.append(feature)
    layer.dataProvider().addFeatures(features)
    layer.updateExtents()
    layer.selectByIds([feature.id() for feature in layer.getFeatures()])
    project.addMapLayer(layer)
    return layer


@pytest.fixture(autouse=True)
def clear_project():
    project = QgsProject.instance()
    project.removeAllMapLayers()
    project.layerTreeRoot().removeAllChildren()
    yield
    project.removeAllMapLayers()
    project.layerTreeRoot().removeAllChildren()


def _output_layers(project):
    return {layer.name(): layer for layer in project.mapLayers().values()
            if layer.name().startswith("DME_DME_")}


def test_coverage_builds_two_valid_lobes_and_optional_construction_layers():
    project = QgsProject.instance()
    layer = _dme_layer(project)
    iface = _Iface()
    log = []

    assert run_dme_dme_coverage(iface, layer, {
        "doc_field": "DOC_NM",
        "include_construction_layers": True,
        "log": log.append,
    })

    outputs = _output_layers(project)
    assert set(outputs) == {
        "DME_DME_Coverage", "DME_DME_Construction", "DME_DME_Excluded_Areas",
    }
    coverage = outputs["DME_DME_Coverage"]
    assert coverage.crs().isValid()
    assert coverage.crs().mapUnits().name == "Meters"
    assert coverage.wkbType() != 0
    result = next(coverage.getFeatures())
    assert coverage.fields().names() == [
        "A_FID", "B_FID", "D_NM", "DOC_A_NM", "DOC_B_NM", "DOC_FIELD",
    ]
    assert result["DOC_A_NM"] == 150.0
    assert result["DOC_B_NM"] == MAX_DOC_NM
    assert result["DOC_FIELD"] == "DOC_NM"
    assert result.geometry().isGeosValid()
    assert len(result.geometry().asMultiPolygon()) == 2
    assert result.geometry().area() > 0
    assert any("capped from 250 NM" in message for message in log)

    d = result["D_NM"] * NM_TO_M
    point_a, point_b = [
        QgsCoordinateTransform(
            layer.crs(), coverage.crs(), project
        ).transform(feature.geometry().asPoint())
        for feature in sorted(layer.getFeatures(), key=lambda item: item.id())
    ]
    midpoint = QgsPointXY((point_a.x() + point_b.x()) / 2,
                          (point_a.y() + point_b.y()) / 2)
    normal = QgsPointXY(
        -(point_b.y() - point_a.y()) / d,
        (point_b.x() - point_a.x()) / d,
    )
    for sign in (-1, 1):
        inside = QgsPointXY(midpoint.x() + sign * normal.x() * 10 * NM_TO_M,
                            midpoint.y() + sign * normal.y() * 10 * NM_TO_M)
        assert result.geometry().contains(QgsGeometry.fromPointXY(inside))

    along = QgsPointXY((point_b.x() - point_a.x()) / d,
                       (point_b.y() - point_a.y()) / d)

    def sample(along_nm, cross_nm):
        return QgsPointXY(
            midpoint.x() + along.x() * along_nm * NM_TO_M
            + normal.x() * cross_nm * NM_TO_M,
            midpoint.y() + along.y() * along_nm * NM_TO_M
            + normal.y() * cross_nm * NM_TO_M,
        )

    def angle_at(along_nm, cross_nm):
        point = sample(along_nm, cross_nm)
        vector_a = (point_a.x() - point.x(), point_a.y() - point.y())
        vector_b = (point_b.x() - point.x(), point_b.y() - point.y())
        dot = sum(a * b for a, b in zip(vector_a, vector_b))
        norms = math.hypot(*vector_a) * math.hypot(*vector_b)
        return math.degrees(math.acos(max(-1.0, min(1.0, dot / norms))))

    for along_nm, cross_nm in [(0, 0), (0, 1), (0, 40), (-d / (2 * NM_TO_M), 0.5)]:
        sample_point = sample(along_nm, cross_nm)
        angle_valid = 30 <= angle_at(along_nm, cross_nm) <= 150
        doc_valid = (
            sample_point.distance(point_a) < 150 * NM_TO_M
            and sample_point.distance(point_b) < 200 * NM_TO_M
        )
        no_update = min(
            sample_point.distance(point_a), sample_point.distance(point_b)
        ) <= NM_TO_M
        expected_inside = angle_valid and doc_valid and not no_update
        actual_inside = result.geometry().contains(
            QgsGeometry.fromPointXY(sample_point))
        assert actual_inside is expected_inside
    assert result.geometry().contains(QgsGeometry.fromPointXY(sample(
        -d / (2 * NM_TO_M), 2)))

    construction = outputs["DME_DME_Construction"]
    assert construction.featureCount() == 7
    assert construction.fields().names() == ["Role", "Radius_NM"]
    assert {feature["Role"] for feature in construction.getFeatures()} == {
        "DOC_A", "DOC_B", "ANGLE_PLUS", "ANGLE_MINUS",
        "NO_UPDATE_A", "NO_UPDATE_B", "BASELINE",
    }
    excluded = outputs["DME_DME_Excluded_Areas"]
    assert {feature["Role"] for feature in excluded.getFeatures()} == {
        "CENTRAL", "NO_UPDATE_A", "NO_UPDATE_B",
    }
    group = project.layerTreeRoot().children()[0]
    assert len(group.children()) == 3


def test_construction_toggle_keeps_the_same_coverage_and_null_doc_defaults():
    project = QgsProject.instance()
    layer = _dme_layer(project, docs=(None, None))
    iface = _Iface()
    log = []
    assert run_dme_dme_coverage(iface, layer, {
        "doc_field": "DOC_NM", "include_construction_layers": False,
        "log": log.append,
    })
    outputs = _output_layers(project)
    assert set(outputs) == {"DME_DME_Coverage"}
    feature = next(outputs["DME_DME_Coverage"].getFeatures())
    coverage_wkb = feature.geometry().asWkb()
    assert feature["DOC_A_NM"] == MAX_DOC_NM
    assert feature["DOC_B_NM"] == MAX_DOC_NM
    assert all("DOC is NULL" in message for message in log if "DOC " in message)

    group = project.layerTreeRoot().children()[0]
    project.removeMapLayer(outputs["DME_DME_Coverage"])
    project.layerTreeRoot().removeChildNode(group)
    assert run_dme_dme_coverage(iface, layer, {
        "doc_field": "DOC_NM", "include_construction_layers": True,
    })
    outputs = _output_layers(project)
    assert next(outputs["DME_DME_Coverage"].getFeatures()).geometry().asWkb() == coverage_wkb
    assert set(outputs) == {
        "DME_DME_Coverage", "DME_DME_Construction", "DME_DME_Excluded_Areas",
    }


def test_coverage_is_crs_independent_and_station_roles_follow_fid():
    project = QgsProject.instance()
    geographic_layer = _dme_layer(project)
    geographic_layer.selectByIds(
        [feature.id() for feature in reversed(list(geographic_layer.getFeatures()))])
    assert run_dme_dme_coverage(_Iface(), geographic_layer, {
        "doc_field": "DOC_NM", "include_construction_layers": False,
    })
    geographic_outputs = _output_layers(project)
    geographic_feature = next(geographic_outputs["DME_DME_Coverage"].getFeatures())
    geographic_area = geographic_feature.geometry().area()
    assert geographic_feature["A_FID"] < geographic_feature["B_FID"]

    project.removeAllMapLayers()
    project.layerTreeRoot().removeAllChildren()
    projected_layer = _dme_layer(project, crs="EPSG:32616")
    assert run_dme_dme_coverage(_Iface(), projected_layer, {
        "doc_field": "DOC_NM", "include_construction_layers": False,
    })
    projected_feature = next(_output_layers(project)["DME_DME_Coverage"].getFeatures())
    assert math.isclose(projected_feature.geometry().area(), geographic_area,
                        rel_tol=1e-7)


def test_invalid_selection_and_doc_values_are_rejected_without_outputs():
    project = QgsProject.instance()
    layer = _dme_layer(project)
    iface = _Iface()
    layer.selectByIds([next(layer.getFeatures()).id()])
    with pytest.raises(ValueError, match="exactly two"):
        run_dme_dme_coverage(iface, layer)
    assert not _output_layers(project)

    feature = next(layer.getFeatures())
    layer.startEditing()
    layer.changeAttributeValue(feature.id(), 0, 0.0)
    layer.commitChanges()
    layer.selectByIds([item.id() for item in layer.getFeatures()])
    with pytest.raises(ValueError, match="greater than zero"):
        run_dme_dme_coverage(iface, layer, {"doc_field": "DOC_NM"})
    assert not _output_layers(project)


def test_non_overlapping_doc_circles_return_no_output():
    project = QgsProject.instance()
    layer = _dme_layer(project, docs=(5.0, 5.0))
    features = sorted(layer.getFeatures(), key=lambda item: item.id())
    # Move the second DME to 20 NM from the first: the two 5 NM DOC circles
    # have no overlap, so the pair cannot yield a dual-DME update area.
    layer.startEditing()
    first = features[0].geometry().asPoint()
    longitude_delta = 20.0 / (60.0 * math.cos(math.radians(first.y())))
    layer.changeGeometry(
        features[1].id(),
        QgsGeometry.fromPointXY(QgsPointXY(
            first.x() + longitude_delta, first.y())))
    layer.commitChanges()
    log = []
    assert not run_dme_dme_coverage(
        _Iface(), layer, {"doc_field": "DOC_NM", "log": log.append})
    assert any("DOC circles do not overlap" in message for message in log)
    assert not _output_layers(project)


def test_dock_form_calculates_coverage():
    project = QgsProject.instance()
    layer = _dme_layer(project)

    class _DockIface:
        def __init__(self):
            self.window = QMainWindow()
            self.bar = _MessageBar()

        def mainWindow(self):
            return self.window

        def activeLayer(self):
            return layer

        def messageBar(self):
            return self.bar

    dock = QPANSOPYDMEDMECoverageDockWidget(_DockIface())
    assert dock.dmeLayerComboBox.currentLayer() == layer
    assert dock.docFieldComboBox.itemText(0) == "Not provided — use 200 NM"
    assert dock.docFieldComboBox.count() == 2
    dock.docFieldComboBox.setCurrentIndex(1)
    dock.calculateButton.click()
    assert set(_output_layers(project)) == {
        "DME_DME_Coverage", "DME_DME_Construction", "DME_DME_Excluded_Areas",
    }
    feature = next(_output_layers(project)["DME_DME_Coverage"].getFeatures())
    assert feature["DOC_A_NM"] == 150.0
    assert feature["DOC_B_NM"] == 200.0
    assert "completed successfully" in dock.logTextEdit.toPlainText()
    dock.close()


def test_icon_keeps_overlap_transparent_and_lobes_orange():
    icon_path = Path(__file__).parents[2] / "Q_Pansopy" / "icons" / "dme_dme_coverage.svg"
    renderer = QSvgRenderer(str(icon_path))
    assert renderer.isValid()
    image = QImage(32, 32, QImage.Format.Format_ARGB32)
    background = QColor("#ffffff")
    image.fill(background)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    assert image.pixelColor(16, 16) == background
    assert image.pixelColor(5, 16) == QColor("#F59E0B")


@pytest.mark.parametrize(
    "value,expected",
    [(None, (MAX_DOC_NM, "defaulted to 200 NM (DOC is NULL)")),
     (150, (150.0, "using 150 NM DOC")),
     (250, (MAX_DOC_NM, "capped from 250 NM to 200 NM"))],
)
def test_doc_value_default_and_cap(value, expected):
    layer = QgsVectorLayer("None?field=DOC:double", "doc", "memory")
    feature = QgsFeature(layer.fields())
    feature["DOC"] = value
    assert _doc_value(feature, "DOC", "A") == expected


@pytest.mark.parametrize("value", [0, -1, float("nan"), float("inf")])
def test_doc_value_rejects_nonpositive_and_nonfinite_values(value):
    layer = QgsVectorLayer("None?field=DOC:double", "doc", "memory")
    feature = QgsFeature(layer.fields())
    feature["DOC"] = value
    with pytest.raises(ValueError, match="greater than zero"):
        _doc_value(feature, "DOC", "A")
