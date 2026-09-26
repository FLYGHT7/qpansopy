from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

pytest.importorskip("qgis")

from qgis.core import QgsRectangle  # noqa: E402

from Q_Pansopy.modules.utilities.ama_grid import (  # noqa: E402
    cell_id,
    grid_step,
    snapped_grid_indices,
)


def test_supported_grid_steps_and_ids():
    assert grid_step("AMA_1") == 1.0
    assert grid_step("AMA_05") == 0.5
    assert cell_id(-1, 0, "AMA_1") == "AMA_1_N00_W001"
    assert cell_id(-1, 1, "AMA_05") == "AMA_05_N0030_W0030"


@pytest.mark.parametrize("grid_type, expected", [
    ("AMA_1", (-2, -2, 2, 2)),
    ("AMA_05", (-3, -3, 3, 3)),
])
def test_extent_snaps_outward(grid_type, expected):
    extent = QgsRectangle(-1.1, -1.1, 1.1, 1.1)
    assert snapped_grid_indices(extent, grid_type) == expected


def test_extent_rejects_antimeridian_order_and_huge_grid():
    with pytest.raises(ValueError, match="positive width"):
        snapped_grid_indices(QgsRectangle(2, 0, 1, 1, normalize=False), "AMA_1")
    with pytest.raises(ValueError, match="maximum"):
        snapped_grid_indices(QgsRectangle(-180, -90, 180, 90), "AMA_05")


def test_output_crs_selector_defaults_to_project_crs():
    ui_path = (
        Path(__file__).parents[2]
        / "Q_Pansopy/ui/utilities/qpansopy_ama_grid_dockwidget.ui"
    )
    root = ET.parse(ui_path).getroot()
    combo = root.find(".//widget[@name='outputCrsComboBox']")
    assert combo is not None
    labels = [item.findtext("./property[@name='text']/string") for item in combo.findall("item")]
    assert labels == ["Project CRS (PCS)", "WGS84 (EPSG:4326)"]
