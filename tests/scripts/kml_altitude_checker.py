"""
KML Altitude Checker

Validates that a KML file uses absolute altitude mode and that coordinates include Z values.
Usage:
  python kml_altitude_checker.py <path_to_kml>
Exit codes:
  0 - PASS, all checks OK
  1 - FAIL, altitudeMode not absolute or Z values missing
  2 - ERROR, file not found or parse error
"""
import sys
import os
from xml.etree import ElementTree as ET

KML_NS = 'http://www.opengis.net/kml/2.2'


def has_z_in_coordinates(coord_text: str) -> bool:
    if not coord_text:
        return False
    # coordinates are like: lon,lat,alt lon,lat,alt ...
    for token in coord_text.strip().split():
        parts = token.split(',')
        if len(parts) < 3:
            return False
    return True


def main():
    if len(sys.argv) < 2:
        print('Usage: python kml_altitude_checker.py <path_to_kml>')
        return 2
    path = sys.argv[1]
    if not os.path.exists(path):
        print(f'ERROR: File not found: {path}')
        return 2

    try:
        # Load and normalize gx:altitudeMode
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        content = content.replace('<gx:altitudeMode>', '<altitudeMode>').replace('</gx:altitudeMode>', '</altitudeMode>')
        root = ET.fromstring(content)

        ns = {'kml': KML_NS}
        problems = []

        # Check altitudeMode absolute for all geometries
        for tag in ['Polygon', 'MultiGeometry', 'LineString', 'LinearRing', 'Point']:
            for geom in root.findall(f'.//{{{KML_NS}}}{tag}'):
                am = geom.find(f'{{{KML_NS}}}altitudeMode')
                if am is None or (am.text or '').strip() != 'absolute':
                    problems.append(f'altitudeMode not absolute in <{tag}>')

        # Check Z in coordinates
        for coords in root.findall(f'.//{{{KML_NS}}}coordinates'):
            if not has_z_in_coordinates(coords.text or ''):
                problems.append('coordinates without Z values found')
                break

        if problems:
            print('FAIL:')
            for p in problems:
                print(f'  - {p}')
            return 1

        print('PASS: KML uses altitudeMode=absolute and includes Z coordinates')
        return 0
    except Exception as e:
        print(f'ERROR: Could not parse KML: {e}')
        return 2


if __name__ == '__main__':
    sys.exit(main())
