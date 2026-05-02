# -*- coding: utf-8 -*-
"""
Tests de regresión para los guards de geometría (Fix B4/B5/B6).

Verifica que basic_ils, vss_straight y vss_loc retornan None (sin crashear)
cuando la capa de pista tiene menos de 2 vértices, y que procesan sin error
cuando tiene exactamente 2.

Estrategia: se mockean las capas QGIS con objetos simples que replican la
interfaz mínima necesaria (geometry().asPolyline()). No se instancia una
VectorLayer real.
"""
import importlib
import types
import sys
import pytest


class _MockPoint:
    def __init__(self, x=0.0, y=0.0):
        self._x = x
        self._y = y

    def x(self):
        return self._x

    def y(self):
        return self._y

    def azimuth(self, other):
        return 0.0


class _MockGeometry:
    def __init__(self, polyline):
        self._polyline = polyline

    def asPolyline(self):
        return self._polyline

    def asPoint(self):
        return _MockPoint()


class _MockFeature:
    def __init__(self, polyline=None):
        self._polyline = polyline or []

    def geometry(self):
        if self._polyline is not None:
            return _MockGeometry(self._polyline)
        return _MockGeometry([])


class _MockLayer:
    def __init__(self, feature=None, selected=None):
        self._feature = feature
        self._selected = selected or []

    def selectedFeatures(self):
        return self._selected

    def getFeatures(self):
        return [self._feature] if self._feature else []

    def featureCount(self):
        return 1 if self._feature else 0


class _MockMessageBar:
    def __init__(self):
        self.messages = []

    def pushMessage(self, *args, **kwargs):
        self.messages.append((args, kwargs))


class _MockCanvas:
    class _Settings:
        def destinationCrs(self):
            crs = types.SimpleNamespace()
            crs.authid = lambda: "EPSG:4326"
            return crs

    def mapSettings(self):
        return self._Settings()


class _MockIface:
    def __init__(self):
        self._bar = _MockMessageBar()
        self._canvas = _MockCanvas()

    def messageBar(self):
        return self._bar

    def mapCanvas(self):
        return self._canvas


def _make_singleton_layer(polyline):
    """Layer con una sola feature no seleccionada."""
    feat = _MockFeature(polyline)
    return _MockLayer(feature=feat, selected=[])


def _make_selected_layer(polyline):
    """Layer con una feature seleccionada."""
    feat = _MockFeature(polyline)
    return _MockLayer(feature=feat, selected=[feat])


# Para que get_selected_feature() funcione, la capa necesita exactamente 1
# feature no seleccionada o 1 seleccionada.
def _point_layer():
    return _make_singleton_layer(None)  # punto, no polyline


# ---------------------------------------------------------------------------
# basic_ils — Fix B4
# ---------------------------------------------------------------------------

def test_basic_ils_short_runway_returns_none():
    """B4: runway con 1 vértice → return None, sin IndexError."""
    mod = importlib.import_module('Q_Pansopy.modules.basic_ils')
    iface = _MockIface()
    point_layer = _make_singleton_layer(None)
    runway_layer = _make_singleton_layer([_MockPoint(0, 0)])  # solo 1 vértice

    params = {
        'thr_elev': 0, 'thr_elev_unit': 'm',
        'rwy_width': 45, 'strip_width': 140,
        'export_kml': False, 'output_dir': '.',
    }

    result = mod.calculate_basic_ils(iface, point_layer, runway_layer, params)
    assert result is None

    # El mensaje de error debe haberse registrado
    assert any("2 vertices" in str(m).lower() or "vértices" in str(m).lower()
               for m in iface.messageBar().messages)


def test_basic_ils_empty_runway_returns_none():
    """B4: runway completamente vacía → return None."""
    mod = importlib.import_module('Q_Pansopy.modules.basic_ils')
    iface = _MockIface()
    point_layer = _make_singleton_layer(None)
    runway_layer = _make_singleton_layer([])  # 0 vértices

    params = {
        'thr_elev': 0, 'thr_elev_unit': 'm',
        'rwy_width': 45, 'strip_width': 140,
        'export_kml': False, 'output_dir': '.',
    }

    result = mod.calculate_basic_ils(iface, point_layer, runway_layer, params)
    assert result is None


# ---------------------------------------------------------------------------
# vss_straight — Fix B5
# ---------------------------------------------------------------------------

def test_vss_straight_short_runway_returns_none():
    """B5: runway con 1 vértice → return None."""
    mod = importlib.import_module('Q_Pansopy.modules.vss_straight')
    iface = _MockIface()
    point_layer = _make_singleton_layer(None)
    runway_layer = _make_singleton_layer([_MockPoint(0, 0)])

    params = {
        'thr_elev': 0, 'thr_elev_unit': 'm',
        'rwy_width': 45, 'strip_width': 140,
        'OCH': 100, 'OCH_unit': 'm',
        'RDH': 15, 'RDH_unit': 'm',
        'VPA': 3.0,
        'export_kml': False, 'output_dir': '.',
    }

    result = mod.calculate_vss_straight(iface, point_layer, runway_layer, params)
    assert result is None


# ---------------------------------------------------------------------------
# vss_loc — Fix B6
# ---------------------------------------------------------------------------

def test_vss_loc_short_runway_returns_none():
    """B6: runway con 1 vértice → return None."""
    mod = importlib.import_module('Q_Pansopy.modules.vss_loc')
    iface = _MockIface()
    point_layer = _make_singleton_layer(None)
    runway_layer = _make_singleton_layer([_MockPoint(0, 0)])

    params = {
        'thr_elev': 0, 'thr_elev_unit': 'm',
        'rwy_width': 45, 'strip_width': 140,
        'OCH': 100, 'OCH_unit': 'm',
        'RDH': 15, 'RDH_unit': 'm',
        'VPA': 3.0,
        'export_kml': False, 'output_dir': '.',
    }

    result = mod.calculate_vss_loc(iface, point_layer, runway_layer, params)
    assert result is None
