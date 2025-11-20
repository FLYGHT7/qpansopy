import textwrap
from pathlib import Path

from external_testing.test_oas_csv_parser import parse_constants


def test_parse_constants_minimal(tmp_path: Path):
    content = textwrap.dedent(
        """
        ---OAS constants
        WA, 1.0
        WB, 2.0
        WC, 3.0
        XA, 4.0
        XB, 5.0
        XC, 6.0
        YA, 7.0
        YB, 8.0
        YC, 9.0
        ZA, 10.0
        ZB, 11.0
        ZC, 12.0
        ---OAS Template coordinates -m(meters)
        (rest omitted)
        """
    ).strip()
    csv_path = tmp_path / "oas_constants.csv"
    csv_path.write_text(content, encoding="utf-8")

    planes = parse_constants(str(csv_path))
    assert planes["W plane"] == [1.0, 2.0, 3.0]
    assert planes["X plane"] == [4.0, 5.0, 6.0]
    assert planes["Y plane"] == [7.0, 8.0, 9.0]
    assert planes["Z plane"] == [10.0, 11.0, 12.0]