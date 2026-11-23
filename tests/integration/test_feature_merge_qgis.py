"""Real-QGIS gates for Feature Merge: module, legacy dock and direct toolbar action."""
import json

import pytest

pytest.importorskip('qgis')
pytestmark = pytest.mark.qgis_runtime

from qgis.core import (  # noqa: E402
    Qgis, QgsFeature, QgsGeometry, QgsProject, QgsVectorLayer,
)
from qgis.PyQt.QtCore import QMetaType  # noqa: E402
from qgis.PyQt.QtWidgets import QApplication  # noqa: E402
from .test_qt6_plugin_runtime import plugin, qgis_app  # noqa: F401,E402


def make_layer(name, fields, rows, geometry='Point', crs='EPSG:32616'):
    uri = f'{geometry}?crs={crs}' + ''.join(f'&field={field}' for field in fields)
    layer = QgsVectorLayer(uri, name, 'memory')
    features = []
    for wkt, attributes in rows:
        feature = QgsFeature(layer.fields())
        feature.setGeometry(QgsGeometry.fromWkt(wkt))
        feature.setAttributes(attributes)
        features.append(feature)
    assert layer.dataProvider().addFeatures(features)[0]
    QgsProject.instance().addMapLayer(layer)
    return layer


def source_layers():
    first = make_layer('A', ['name:string', 'height:double'],
                       [('POINT (1 1)', ['a1', 10.5]), ('POINT (2 2)', ['a2', 20.0])])
    second = make_layer('B', ['name:string', 'code:integer'],
                        [('POINT (3 3)', ['b1', 7])])
    return first, second


def capture_messages(instance, monkeypatch):
    messages = []
    monkeypatch.setattr(instance.iface.messageBar(), 'pushMessage',
                        lambda title, text, level: messages.append((title, text, level)))
    return messages


def layers_named(name):
    return [layer for layer in QgsProject.instance().mapLayers().values()
            if layer.name() == name]


def merge_dock(instance, tmp_path):
    from Q_Pansopy.dockwidgets.utilities.qpansopy_feature_merge_dockwidget import (
        QPANSOPYFeatureMergeDockWidget,
    )
    dock = QPANSOPYFeatureMergeDockWidget(instance.iface)
    dock.outputFolderLineEdit.setText(str(tmp_path))
    return dock


def log_lines(dock):
    # Traceback continuation lines carry no "[HH:MM:SS] " prefix.
    return [line.split('] ', 1)[1] if line.startswith('[') else line
            for line in dock.logTextEdit.toPlainText().splitlines()]


def test_module_merges_union_schema_attributes_and_reports_counts(plugin):
    from Q_Pansopy.modules.utilities.feature_merge import merge_selected_layers

    instance, _ = plugin
    first, second = source_layers()
    result = merge_selected_layers(instance.iface, [first, second], 'M1')
    merged = result.pop('merged_layer')
    assert result == {
        'success': True, 'total_features': 3, 'layer_counts': {'A': 2, 'B': 1},
        'source_layers': ['A', 'B'], 'geometry_type': 'Point', 'crs': 'EPSG:32616',
    }
    assert layers_named('M1') == [merged]
    assert merged.wkbType() == Qgis.WkbType.Point
    assert merged.crs().authid() == 'EPSG:32616'
    assert [(field.name(), field.type()) for field in merged.fields()] == [
        ('name', QMetaType.Type.QString), ('height', QMetaType.Type.Double),
        ('code', QMetaType.Type.Int),
    ]
    assert [(feature.attributes(), feature.geometry().asWkt())
            for feature in merged.getFeatures()] == [
        (['a1', 10.5, None], 'Point (1 1)'),
        (['a2', 20.0, None], 'Point (2 2)'),
        (['b1', None, 7], 'Point (3 3)'),
    ]


def test_module_uses_layer_tree_selection_when_layers_are_not_given(plugin):
    from Q_Pansopy.modules.utilities.feature_merge import merge_selected_layers

    instance, selected = plugin
    selected.extend(source_layers())
    result = merge_selected_layers(instance.iface)
    assert result['total_features'] == 3
    assert result['merged_layer'].name() == 'Merged_Layer'


@pytest.mark.parametrize('case,message', [
    ('single', 'Select at least two vector layers.'),
    ('geometry', 'Geometry types differ between layers.'),
    ('crs', 'CRS differ between layers.'),
])
def test_module_rejects_incompatible_inputs_without_output(plugin, case, message):
    from Q_Pansopy.modules.utilities.feature_merge import merge_selected_layers

    instance, _ = plugin
    first, _ = source_layers()
    layers = [first]
    if case == 'geometry':
        layers.append(make_layer('L', [], [('LINESTRING (0 0, 1 1)', [])], 'LineString'))
    elif case == 'crs':
        layers.append(make_layer('C', [], [('POINT (0 0)', [])], 'Point', 'EPSG:4326'))
    before = set(QgsProject.instance().mapLayers())
    with pytest.raises(ValueError, match=message):
        merge_selected_layers(instance.iface, layers, 'X')
    assert set(QgsProject.instance().mapLayers()) == before


def test_dock_merges_selected_layers_logs_and_reports_success(plugin, monkeypatch, tmp_path):
    instance, selected = plugin
    messages = capture_messages(instance, monkeypatch)
    selected.extend(source_layers())
    dock = merge_dock(instance, tmp_path)
    try:
        assert dock.exportKmlCheckBox.isHidden() and not dock.exportKmlCheckBox.isChecked()
        assert dock.layerNameLineEdit.text() == 'Merged_Layer'
        dock.calculateButton.click()
        merged = layers_named('Merged_Layer')
        assert len(merged) == 1 and merged[0].featureCount() == 3
        assert messages == [
            ('QPANSOPY', 'Layer merging completed: 3 features merged', Qgis.MessageLevel.Success)]
        assert log_lines(dock)[-12:] == [
            'Starting layer merging...',
            'Merging 2 layers:',
            '  - A (2 features)',
            '  - B (1 features)',
            'Layer merging completed successfully!',
            'Merged layer: Merged_Layer',
            'Total features: 3',
            'Geometry type: Point',
            'CRS: EPSG:32616',
            '  A: 2 features',
            '  B: 1 features',
            "You can now use the 'Copy Parameters as JSON' button to copy the parameters "
            "for documentation.",
        ]
    finally:
        dock.close()
        dock.deleteLater()


def test_dock_copies_parameters_as_json(plugin, monkeypatch, tmp_path):
    instance, selected = plugin
    messages = capture_messages(instance, monkeypatch)
    selected.extend(source_layers())
    dock = merge_dock(instance, tmp_path)
    try:
        dock.copyParamsButton.click()
        copied = json.loads(QApplication.clipboard().text())
        assert copied['metadata']['plugin'] == 'QPANSOPY Feature Merge'
        assert copied['parameters'] == {
            'selected_layers': ['A', 'B'], 'merged_layer_name': 'Merged_Layer',
            'output_folder': str(tmp_path), 'kml_export': False,
        }
        # geometry_type keeps the numeric wkbType value (pre-existing behaviour).
        assert copied['layer_info'] == {
            'geometry_type': 1, 'crs': 'EPSG:32616', 'total_layers': 2, 'total_features': 3}
        assert messages == [('QPANSOPY', 'Feature Merge parameters copied to clipboard as JSON',
                             Qgis.MessageLevel.Success)]
    finally:
        dock.close()
        dock.deleteLater()


def test_dock_exports_merged_layer_to_kml(plugin, monkeypatch, tmp_path):
    from Q_Pansopy.modules.utilities.feature_merge import merge_selected_layers

    instance, _ = plugin
    merged = merge_selected_layers(instance.iface, list(source_layers()), 'M1')['merged_layer']
    messages = capture_messages(instance, monkeypatch)
    dock = merge_dock(instance, tmp_path)
    try:
        dock.export_results_to_kml(merged, str(tmp_path))
        exported = sorted(tmp_path.glob('feature_merge_*.kml'))
        assert len(exported) == 1
        assert exported[0].read_text(encoding='utf-8').count('<Placemark') == 3
        assert messages == [('QPANSOPY', 'Feature Merge results exported to KML',
                             Qgis.MessageLevel.Success)]
        assert log_lines(dock)[-1] == f'Merged layer exported to KML: {exported[0]}'
    finally:
        dock.close()
        dock.deleteLater()


@pytest.mark.parametrize('case,message,log', [
    ('single', 'Select at least two vector layers in the Layers panel.',
     'Error: Select at least two vector layers in the Layers panel.'),
    ('geometry', 'Geometry types differ between selected layers',
     "Error: Geometry type mismatch between layer 'A' and 'L'"),
    ('crs', 'CRS differ between selected layers',
     "Error: CRS mismatch between layer 'A' and 'C'"),
    ('blank_name', None, 'Error: Please enter a name for the merged layer'),
])
def test_dock_validation_creates_no_output(plugin, monkeypatch, tmp_path, case, message, log):
    instance, selected = plugin
    messages = capture_messages(instance, monkeypatch)
    first, second = source_layers()
    selected.append(first)
    if case == 'geometry':
        selected.append(make_layer('L', [], [('LINESTRING (0 0, 1 1)', [])], 'LineString'))
    elif case == 'crs':
        selected.append(make_layer('C', [], [('POINT (0 0)', [])], 'Point', 'EPSG:4326'))
    elif case == 'blank_name':
        selected.append(second)
    dock = merge_dock(instance, tmp_path)
    try:
        if case == 'blank_name':
            dock.layerNameLineEdit.setText('  ')
        dock.calculateButton.click()
        assert log_lines(dock)[-1] == log
        assert messages == ([] if message is None
                            else [('Error', message, Qgis.MessageLevel.Warning)])
        assert not layers_named('Merged_Layer')
    finally:
        dock.close()
        dock.deleteLater()


def test_dock_reports_runtime_failure_as_critical(plugin, monkeypatch, tmp_path):
    from Q_Pansopy.modules.utilities import feature_merge

    def failing_merge(*args, **kwargs):
        raise RuntimeError('controlled merge failure')

    instance, selected = plugin
    messages = capture_messages(instance, monkeypatch)
    selected.extend(source_layers())
    monkeypatch.setattr(feature_merge, 'merge_selected_layers', failing_merge)
    dock = merge_dock(instance, tmp_path)
    try:
        dock.calculateButton.click()
        assert 'Error during layer merging: controlled merge failure' in log_lines(dock)
        assert messages == [('Error', 'Layer merging failed: controlled merge failure',
                             Qgis.MessageLevel.Critical)]
        assert not layers_named('Merged_Layer')
    finally:
        dock.close()
        dock.deleteLater()


def test_toolbar_action_picks_unique_name_and_reports_success(plugin, monkeypatch, qgis_app):
    instance, selected = plugin
    messages = capture_messages(instance, monkeypatch)
    make_layer('Merged_Layer', [], [('POINT (9 9)', [])])
    first, second = source_layers()
    selected.extend([first, second])
    instance.actions[list(instance.modules).index('FeatureMerge')].trigger()
    qgis_app.processEvents()
    merged = layers_named('Merged_Layer_2')
    assert len(merged) == 1 and merged[0].featureCount() == 3
    assert messages == [('QPANSOPY', 'Feature Merge completed: 3 features',
                         Qgis.MessageLevel.Success)]
