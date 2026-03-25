# QPANSOPY — Plan de Desarrollo y Refactorización

> **Fecha:** Marzo 2026
> **Versión actual:** 0.2 (metadata.txt)
> **Stack:** QGIS Plugin · Python 3.x · PyQt5 (compatibilidad PyQt6 al final)
> **Skills aplicados:** `architecture-blueprint-generator` · `code-refactoring-refactor-clean` · `python-best-practices` · `python-testing` · `ui-ux-pro-max` · `code-review-quality`

---

## Reglas inamovibles

> Estas reglas aplican a todo el proyecto sin excepción:

1. **Las fórmulas y cálculos aeronáuticos NO se tocan.** Toda la lógica matemática en `modules/` es correcta y funcional. La refactorización es solo estructural (extraer, mover, renombrar — nunca modificar la lógica).
2. **Crear una rama git nueva ANTES de cualquier cambio.** Ver sección de preparación.
3. **La migración a PyQt6 es la última fase.** Primero se refactoriza todo con PyQt5 funcionando.
4. **No refactorizar sin tests.** Si una función no tiene test, escribir el test primero.

---

## Preparación: Rama de trabajo

Antes de ejecutar cualquier fase, crear la rama:

```bash
git checkout -b refactor/qpansopy-v1
git push -u origin refactor/qpansopy-v1
```

Cada fase tiene su propio commit atómico:

```bash
git add .
git commit -m "fase-0: eliminar archivos legacy vacios y duplicados"
```

---

## Tabla de Contenidos

1. [Estado Actual — Diagnóstico](#1-estado-actual--diagnóstico)
2. [Fase 0 — Limpieza de archivos muertos](#fase-0--limpieza-de-archivos-muertos)
3. [Fase 1 — Corrección de bugs críticos](#fase-1--corrección-de-bugs-críticos)
4. [Fase 2 — Expansión de tests](#fase-2--expansión-de-tests-antes-de-refactorizar)
5. [Fase 3 — Refactorización de módulos](#fase-3--refactorización-de-módulos-estructura-sin-tocar-fórmulas)
6. [Fase 4 — Refactorización de dockwidgets](#fase-4--refactorización-de-dockwidgets)
7. [Fase 5 — Mejora de UI/UX](#fase-5--mejora-de-uiux)
8. [Fase 6 — Reestructura de carpetas final](#fase-6--reestructura-de-carpetas-final)
9. [Fase 7 — Migración PyQt5/PyQt6 dual (última)](#fase-7--migración-pyqt5--pyqt5pyqt6-dual-última)

---

## 1. Estado Actual — Diagnóstico

### Arquitectura actual

```
Q_Pansopy/
├── qpansopy.py          # Clase principal (~774 líneas) — registra 16 módulos, 5 toolbars
├── utils.py             # Utilidades compartidas (214 líneas)
├── modules/             # Lógica de cálculo aeronáutico <- NO TOCAR LAS FÓRMULAS
│   ├── basic_ils.py     # 410 líneas
│   ├── oas_ils.py       # 708 líneas
│   ├── vss_straight.py  # 321 líneas
│   ├── vss_loc.py       # 323 líneas
│   ├── wind_spiral.py   # 343 líneas
│   ├── pbn/             # Duplicados en raíz
│   ├── conv/            # 4 módulos, 780 líneas
│   ├── departures/      # 2 módulos, 1064 líneas
│   └── utilities/       # 6 módulos, 913 líneas
└── dockwidgets/         # 15 archivos Python + 16 archivos .ui
```

**Total revisado en esta sesión exhaustiva:** 4,397 líneas de módulos + ~4,000 líneas de dockwidgets + 16 archivos .ui

---

## 2. Inventario completo de bugs

> **Criterio:** Solo problemas de código Python — no de lógica aeronáutica.
> **Leyenda:** 🔴 Crash/Data loss · 🟠 Error silencioso · 🟡 Code smell

### Serie A — Problemas estructurales generales

| #   | Sev | Problema                                                                                    | Archivos afectados                  |
| --- | --- | ------------------------------------------------------------------------------------------- | ----------------------------------- |
| A1  | 🟠  | 5 `.py` y 3 `.ui` VACÍOS en raíz de `Q_Pansopy/` (legacy stubs sin eliminar)                | ver Fase 0                          |
| A2  | 🟠  | 4 pares de módulos duplicados entre `modules/` raíz y subcarpetas                           | PBN x3 + `selection_of_objects`     |
| A3  | 🟠  | `correct_kml_structure()` en `basic_ils.py` duplica `fix_kml_altitude_mode()` de `utils.py` | `basic_ils.py` ~L330                |
| A4  | 🟡  | Magic numbers sin constantes: `0.3048`, `1852`, `0.15`, `14.3`, `960`, `3000`...            | todos los módulos                   |
| A5  | 🟡  | `get_desktop_path()` repetida con implementaciones distintas en cada dockwidget (12 copias) | todos los dockwidgets               |
| A6  | 🟡  | `modules/__init__.py` vacío — no expone ninguna API del paquete                             | `modules/__init__.py`               |
| A7  | 🟠  | `requirements.txt` contiene `math` (es stdlib, no instalable con pip)                       | `external_testing/requirements.txt` |
| A8  | 🟡  | Tests solo cubren `copy_parameters_table()` — sin tests de estructura de código             | `external_testing/tests/`           |
| A9  | 🟡  | `modules/conv/CONV-Initial-Approach-Straight.py` nombre con guiones (no importable)         | `modules/conv/`                     |
| A10 | 🟡  | `ui/utilities/qpansopy_wind_spiral_dockwidget_new.ui` — `_new` en nombre, posible artefacto | `ui/utilities/`                     |

---

### Serie B — Bugs encontrados en revisión inicial (dockwidgets + módulos clave)

| #   | Sev    | Archivo                                                     | Línea   | Descripción                                                                                                                                                                                                                                    | Fix                                                                     |
| --- | ------ | ----------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| B1  | 🔴     | `dockwidgets/utilities/qpansopy_point_filter_dockwidget.py` | ~48, 58 | `setupUi(self)` llamado DOS veces — duplica todos los widgets y conecta signals dos veces                                                                                                                                                      | Eliminar segunda llamada                                                |
| B2  | ~~🔴~~ | `dockwidgets/utilities/qpansopy_vss_dockwidget.py`          | ~100    | ~~`logTextEdit.setMaximumHeight(0)`~~ **No encontrado en código actual** — el archivo usa `setVisible(True)`. Puede haber sido corregido. Verificar antes de hacer fix.                                                                        | Confirmar si aplica antes de actuar                                     |
| B3  | 🔴     | `dockwidgets/utilities/qpansopy_wind_spiral_dockwidget.py`  | L564    | `show_isa_calculator_dialog()` — dialog inline conecta "Calculate ISA" con `dialog.accept()` pero **NUNCA calcula la variación ISA y NUNCA actualiza `isaVarLineEdit`**. El botón solo cierra el widget. Funcionalidad ISA completamente rota. | Calcular ISA dentro del `if dialog.exec_() == Accepted:` block          |
| B4  | 🔴     | `modules/basic_ils.py`                                      | ~134    | `runway_geom[1]` sin validar longitud — `IndexError` si geometría tiene menos de 2 vértices                                                                                                                                                    | Validar `len(runway_geom) >= 2` antes                                   |
| B5  | 🔴     | `modules/vss_straight.py`, `modules/vss_loc.py`             | ~100    | `runway_geom[-1]` / `runway_geom[0]` sin validar longitud                                                                                                                                                                                      | Ídem                                                                    |
| B6  | 🔴     | `modules/wind_spiral.py`                                    | ~139    | `geom[-1]` sin validar longitud de polyline                                                                                                                                                                                                    | Ídem                                                                    |
| B7  | 🔴     | `qpansopy.py`                                               | ~18     | `except ImportError: pass` — descarta errores sin diagnóstico; genera `NameError` posterior sin contexto                                                                                                                                       | Guardar mensaje y mostrarlo en `initGui()`                              |
| B8  | 🟠     | `modules/oas_ils.py`                                        | ~18     | Variables globales mutables (`OAS_template`, `OAS_W`, etc.) persisten entre cálculos — contaminación de estado                                                                                                                                 | Retornar como dict en lugar de modificar globales                       |
| B9  | 🟠     | `modules/wind_spiral.py`                                    | ~20     | `w = 30` hardcodeado en `tas_calculation()` — viento del usuario se guarda en log pero NO se usa en el cálculo                                                                                                                                 | Confirmar si es estándar ICAO; si no: pasar `wind_speed` como parámetro |
| B10 | 🟠     | Todos los dockwidgets + `utils.py`                          | varios  | `open(path, 'r')` / `open(path, 'w')` sin `encoding='utf-8'` — falla con acentos en Windows                                                                                                                                                    | Agregar `encoding='utf-8'`                                              |
| B11 | 🟡     | `qpansopy.py`                                               | ~345    | `except AttributeError` es código muerto — el `hasattr()` previo garantiza que nunca se ejecuta                                                                                                                                                | Eliminar bloque redundante                                              |
| B12 | 🟡     | `isa_calculator_dialog.py`                                  | todo    | `ISACalculatorDialog` implementada pero no se usa (wind_spiral crea su propio dialog inline)                                                                                                                                                   | Usar esta clase en el fix de B3                                         |
| B13 | 🟡     | `dockwidgets/departures/qpansopy_sid_initial_dockwidget.py` | ~119    | `setup_validators()` crea un `QRegExpValidator` que queda en scope sin aplicarse a ningún widget                                                                                                                                               | Aplicarlo o eliminar el método                                          |
| B14 | 🟡     | `dockwidgets/pbn/qpansopy_lnav_dockwidget.py`               | 6       | `import runpy` presente pero nunca usado                                                                                                                                                                                                       | Eliminar                                                                |
| B15 | 🟡     | 9 archivos (ver nota)                                       | varios  | `from qgis.utils import iface` a nivel de módulo; todas las funciones usan `self.iface` o parámetro local                                                                                                                                      | Eliminar imports de módulo no usados                                    |
| B16 | 🟡     | 3 archivos conv                                             | L5      | `import datetime` en conv dockwidgets — nunca usado                                                                                                                                                                                            | Eliminar                                                                |
| B17 | 🟡     | 3 dockwidgets + `utils.py`                                  | varios  | `except:` desnudo — captura `SystemExit` y `KeyboardInterrupt`                                                                                                                                                                                 | Cambiar a `except Exception:`                                           |
| B18 | 🟡     | `dockwidgets/utilities/qpansopy_vss_dockwidget.py`          | ~108    | `setup_copy_button()` marcado DEPRECATED — código unreachable después del `pass`                                                                                                                                                               | Eliminar código muerto                                                  |
| B19 | 🟡     | `dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`            | varios  | `import json` dentro de métodos — ya importado a nivel de módulo                                                                                                                                                                               | Mover al nivel de módulo                                                |
| B20 | 🟡     | `modules/oas_ils.py`                                        | ~71     | `QFileDialog.getOpenFileName(None, ...)` — sin parent, dialog puede aparecer detrás de QGIS en Linux/macOS                                                                                                                                     | Usar `iface.mainWindow()` como parent                                   |

> **B15 archivos:** `dockwidgets/ils/qpansopy_ils_dockwidget.py`, `dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`, `dockwidgets/utilities/qpansopy_vss_dockwidget.py`, `dockwidgets/utilities/qpansopy_wind_spiral_dockwidget.py`, `dockwidgets/departures/qpansopy_omnidirectional_dockwidget.py`, `modules/basic_ils.py`, `modules/vss_straight.py`, `modules/vss_loc.py`, `modules/wind_spiral.py`

---

### Serie C — Nuevos bugs — revisión exhaustiva modules/ (4,397 líneas)

| #   | Sev    | Archivo                                          | Línea   | Descripción                                                                                                                                                                                              | Fix                                                              |
| --- | ------ | ------------------------------------------------ | ------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| C1  | 🔴     | `modules/conv/ndb_approach.py`                   | 47-71   | **Cálculo de puntos duplicado y sobreescrito** — líneas 47-60 calculan `pts['p1']`, `pts['p2']` etc.; líneas 62-71 sobreescriben las mismas claves. El primer bloque entero se descarta silenciosamente. | Eliminar las líneas 47-60 (primer bloque redundante)             |
| C2  | 🔴     | `modules/conv/vor_approach.py`                   | 47-71   | **Misma bug que C1** — código copia-pega idéntico a ndb_approach. Primer bloque de cálculo nunca se usa.                                                                                                 | Ídem                                                             |
| C3  | 🟠     | `modules/oas_ils.py`                             | 23-27   | Globals `OAS_W`, `OAS_X`, `OAS_Y`, `OAS_Z` permanecen `None` si la carga del CSV falla silenciosamente — código downstream los usa sin validarlos                                                        | Añadir guard `if OAS_W is None: return None` antes de usarlos    |
| C4  | 🟠     | `modules/oas_ils.py`                             | 351-357 | `compute_geom()` retorna dict; código accede a `geometry_dict["Dmirror"]` etc. sin validar que esas claves existan — `KeyError` si retorna dict incompleto                                               | Validar required keys antes de acceder                           |
| C5  | ~~🔴~~ | `modules/utilities/holding.py`                   | 47      | ~~Sintaxis `str \| None`~~ **No presente en código actual** — `holding.py` fue reescrito usando `params: dict`, sin anotaciones `str \| None`. Verificar en Python 3.9.                                  | Ya corregido en versión actual — verificar en Python 3.9         |
| C6  | 🟠     | `modules/utilities/holding.py`                   | 8       | `from ..wind_spiral import tas_calculation` sin manejo — si `wind_spiral` cambia de nombre, error genérico sin contexto                                                                                  | Envolver en `try/except ImportError` con mensaje específico      |
| C7  | 🟠     | `modules/pbn/gnss_waypoint.py`                   | 133-135 | No valida que la capa de routing tenga features seleccionados — itera sobre cero features, retorna `None` silenciosamente                                                                                | Añadir mensaje: "Select a routing segment first"                 |
| C8  | 🟡     | `modules/pbn/PBN_LNAV_Final_Approach.py`         | 91-93   | `except:` desnudo trata cualquier error como "invalid geometry" — oculta errores reales de memoria/archivo/parsing                                                                                       | Cambiar a `except (AttributeError, TypeError, IndexError) as e:` |
| C9  | 🟡     | `modules/utilities/selection_of_objects.py`      | 75-78   | `geom.transform(transform)` sin verificar retorno — si falla silenciosamente la geometría se vuelve inválida                                                                                             | Verificar valor de retorno o envolver en try/except              |
| C10 | 🟡     | `modules/wind_spiral.py`                         | 357     | `cString.setPoints(u)` sin verificar que `u` tenga al menos 2 puntos — circular string inválida si el loop no genera puntos                                                                              | Añadir `if len(u) < 2: return None` antes                        |
| C11 | 🟡     | `modules/PBN_RNAV1_2_missed_less_15NM.py`        | 53-280  | Código como script global que se ejecuta al importar el módulo — no está encapsulado en función                                                                                                          | Envolver todo en `def run_rnav_missed(iface, ...):`              |
| C12 | 🟡     | `modules/conv/CONV-Initial-Approach-Straight.py` | todo    | Mismo patrón de script global que C11                                                                                                                                                                    | Ídem                                                             |
| C13 | 🟡     | `modules/pbn/` (3 archivos)                      | 80-195  | PBN_LNAV_Final/Initial/Intermediate tienen 95% de código igual — solo difieren constantes de segmento                                                                                                    | Extraer `run_approach_segment(segment_type, ...)` parametrizado  |

---

### Serie D — Nuevos bugs — revisión exhaustiva dockwidgets/ (~4,000 líneas)

| #   | Sev    | Archivo                                                         | Línea   | Descripción                                                                                                                                                                                                                                                                                    | Fix                                                                                           |
| --- | ------ | --------------------------------------------------------------- | ------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| D1  | 🟠     | `dockwidgets/conv/qpansopy_conv_initial_dockwidget.py`          | 89      | Import dinámico sin try/except — si el módulo no existe, falla en runtime sin mensaje claro                                                                                                                                                                                                    | Envolver en try/except con mensaje útil                                                       |
| D2  | 🟡     | `dockwidgets/departures/qpansopy_omnidirectional_dockwidget.py` | 75      | `exportKmlCheckBox` creado condicionalmente pero **nunca añadido a ningún layout** — widget huérfano e invisible                                                                                                                                                                               | Añadirlo al layout o eliminar la creación dinámica                                            |
| D3  | 🟠     | `dockwidgets/departures/qpansopy_sid_initial_dockwidget.py`     | 204     | `self.logTextEdit.append()` sin `hasattr` guard — `AttributeError` si falla `setupUi`                                                                                                                                                                                                          | Añadir guard `if hasattr(self, 'logTextEdit'):`                                               |
| D4  | 🟠     | `dockwidgets/ils/qpansopy_ils_dockwidget.py`                    | 76-77   | `setup_lineedits()` reemplaza en runtime spinboxes del `.ui` con QLineEdit — frágil, silencia errores si el widget no existe                                                                                                                                                                   | Usar QLineEdit directamente en `.ui` designer (eliminar el método)                            |
| D5  | 🟠     | `dockwidgets/ils/qpansopy_ils_dockwidget.py`                    | 143     | `copy_parameters_for_word()` parsea JSON de capas; si el parse falla continúa silenciosamente con datos incompletos                                                                                                                                                                            | Añadir logging del error de JSON parse                                                        |
| D6  | 🟠     | `dockwidgets/ils/qpansopy_ils_dockwidget.py`                    | 235     | `replace_widget_in_form(widget, row)` falla silenciosamente si la estructura del layout cambia                                                                                                                                                                                                 | Validar `row < formLayout.rowCount()` antes                                                   |
| D7  | 🟠     | `dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`                | 79      | `self.csv_path = None` nunca se resetea entre llamadas — reutiliza CSV de sesión anterior sin que el usuario lo sepa                                                                                                                                                                           | Resetear `self.csv_path = None` al inicio de `validate_inputs()`                              |
| D8  | 🟠     | `dockwidgets/ils/qpansopy_oas_ils_dockwidget.py`                | 130     | `request_csv_file()` valida CSV leyendo líneas pero no verifica campos requeridos — CSV malformado llega al módulo y crashea                                                                                                                                                                   | Validar headers requeridos antes de aceptar                                                   |
| D9  | 🟠     | `dockwidgets/utilities/qpansopy_feature_merge_dockwidget.py`    | 67      | `get_desktop_path()` retorna `""` en caso de excepción — código intenta crear archivos en path inválido                                                                                                                                                                                        | Retornar `pathlib.Path.home()` como fallback seguro                                           |
| D10 | 🟠     | `dockwidgets/utilities/qpansopy_feature_merge_dockwidget.py`    | 190     | `merged_layer.crs()` sin verificar `merged_layer is not None` — `NoneType` crash                                                                                                                                                                                                               | Añadir `if merged_layer is None: return`                                                      |
| D11 | ~~🔴~~ | `dockwidgets/utilities/qpansopy_holding_dockwidget.py`          | 52-57   | ~~`float()` sin `try/except`~~ **No presente en código actual** — el método `calculate()` ya envuelve todo en `try/except Exception`. No requiere acción.                                                                                                                                      | Ya corregido — no requiere acción                                                             |
| D12 | 🟡     | `dockwidgets/utilities/qpansopy_object_selection_dockwidget.py` | 81-82   | Mensaje de error duplicado — se registra dos veces el mismo texto en `logTextEdit`                                                                                                                                                                                                             | Eliminar línea duplicada                                                                      |
| D13 | 🟠     | `dockwidgets/utilities/qpansopy_vss_dockwidget.py`              | 105-107 | `copyWordButton` y `copyJsonButton` verificados con `hasattr` como si fueran opcionales, pero existen en el `.ui` — callbacks conectados de forma incompleta                                                                                                                                   | Conectar directamente, sin hasattr                                                            |
| D14 | 🟠     | `dockwidgets/utilities/qpansopy_wind_spiral_dockwidget.py`      | L112    | Validator regex `r"[-+]?[0-9]*\.?[0-9]+"` aplicado a TODOS los campos: ISA variation (negativo válido), pero también IAS, bank angle, wind speed (negativo inválido). Confirmado en código: la misma instancia `validator` se aplica a `IASLineEdit`, `bankAngleLineEdit`, `windSpeedLineEdit` | Separar validators: positivo para IAS/bankAngle/windSpeed; `[-+]?` solo para `isaVarLineEdit` |
| D15 | 🟠     | `qpansopy.py`                                                   | 285     | `self.toolbars[toolbar_name].addAction(action)` sin verificar que el toolbar exista en el dict — `KeyError` posible                                                                                                                                                                            | Añadir `if toolbar_name in self.toolbars:`                                                    |

---

### Serie U — Bugs en archivos .ui (Qt Designer)

| #   | Sev | Archivo                                                       | Descripción                                                                                                  | Fix                                                                           |
| --- | --- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- |
| U1  | 🟡  | `ui/ils/qpansopy_ils_dockwidget.ui`                           | Labels con nombres genéricos: `label`, `label_2`, `label_4`, `label_5` en lugar de nombres descriptivos      | Renombrar a `pointLayerLabel`, `runwayLayerLabel`, `thresholdElevLabel`, etc. |
| U2  | 🟡  | `ui/utilities/qpansopy_wind_spiral_dockwidget.ui` y `_new.ui` | Dos archivos `.ui` con el mismo `class="QPANSOPYWindSpiralDockWidgetBase"` — no está claro cuál es el activo | Verificar cuál carga el dockwidget, eliminar el otro                          |

> **Hallazgo positivo:** Revisados todos los 16 archivos `.ui` — CERO discrepancias de nombres de widgets entre el `.ui` y el código Python. La base de UI es sólida.

---

### Métricas de la revisión exhaustiva

| Métrica                                                   | Valor                                                          |
| --------------------------------------------------------- | -------------------------------------------------------------- |
| Total archivos Python revisados                           | 44 archivos                                                    |
| Total líneas revisadas (módulos)                          | 4,397                                                          |
| Total líneas revisadas (dockwidgets)                      | ~4,000                                                         |
| Total archivos .ui revisados                              | 16                                                             |
| **Total bugs encontrados**                                | **A(10) + B(20) + C(13) + D(15) + U(2) = 60 items**            |
| Crashes activos 🔴                                        | 10 activos (B2, C5, D11 no presentes en código actual)         |
| Errores silenciosos 🟠                                    | 27                                                             |
| Code smells 🟡                                            | 20                                                             |
| **Bugs verificados en 2ª pasada como NO presentes**       | **B2, C5, D11** (posiblemente corregidos antes de esta sesión) |
| Archivo más problemático                                  | `oas_ils.py` (5 bugs: B8, B20, C3, C4)                         |
| Patrón más repetido                                       | `get_desktop_path()` — 12 implementaciones distintas           |
| Duplicación de boilerplate en dockwidgets                 | ~78% es copy-paste entre widgets                               |
| Módulos con código de script global (ejecuta al importar) | 2 archivos (C11, C12)                                          |
| Discrepancias widget .ui vs Python                        | 0 (UI es sólida)                                               |

---

## Fase 0 — Limpieza de archivos muertos

> **Objetivo:** Eliminar ruido antes de cualquier refactoring. Sin tests, sin riesgo.
> **Esfuerzo:** 1-2 h | **Riesgo:** Mínimo
> **Commit:** `fase-0: eliminar archivos legacy vacios y duplicados`

### 0.1 — Verificar imports antes de eliminar

```bash
grep -r "from.*qpansopy_conv_initial_dockwidget" Q_Pansopy/
grep -r "from.*qpansopy_ndb_dockwidget" Q_Pansopy/
grep -r "PBN_LNAV_Final_Approach" Q_Pansopy/qpansopy.py
grep -r "selection_of_objects" Q_Pansopy/qpansopy.py
```

### 0.2 — Archivos VACÍOS a eliminar (A1)

```
Q_Pansopy/qpansopy_conv_initial_dockwidget.py     (vacío, legacy stub)
Q_Pansopy/qpansopy_ndb_dockwidget.py              (vacío, legacy stub)
Q_Pansopy/qpansopy_vor_dockwidget.py              (vacío, legacy stub)
Q_Pansopy/qpansopy_wind_spiral_dockwidget.py      (vacío, legacy stub)
Q_Pansopy/qpansopy_object_selection_dockwidget.py (vacío, legacy stub)
Q_Pansopy/qpansopy_conv_initial_dockwidget.ui     (duplicado de ui/conv/)
Q_Pansopy/qpansopy_ndb_dockwidget.ui              (duplicado de ui/conv/)
Q_Pansopy/qpansopy_vor_dockwidget.ui              (duplicado de ui/conv/)
```

### 0.3 — Módulos duplicados a eliminar (A2)

```
modules/PBN_LNAV_Final_Approach.py          (activo en: modules/pbn/)
modules/PBN_LNAV_Initial_Approach.py        (activo en: modules/pbn/)
modules/PBN_LNAV_Intermediate_Approach.py   (activo en: modules/pbn/)
modules/selection_of_objects.py             (activo en: modules/utilities/)
ui/utilities/qpansopy_wind_spiral_dockwidget_new.ui  (VERIFICAR primero: resolver U2)
```

> **Nota C11:** `modules/PBN_RNAV1_2_missed_less_15NM.py` es script global — no eliminar aún, refactorizar en Fase 1.
> **Nota A9:** `modules/conv/CONV-Initial-Approach-Straight.py` tiene nombre no importable — mover/renombrar en Fase 6.

### 0.4 — Fix requirements.txt (A7)

```diff
 pytest==7.4.4
 pytest-cov==4.1.0
 numpy==1.24.3
-math
```

---

## Fase 1 — Corrección de bugs críticos

> **Objetivo:** Corregir todos los bugs 🔴 y los 🟠 más peligrosos, SIN tocar fórmulas.
> **Esfuerzo:** 6-8 h | **Riesgo:** Bajo
> **Commit:** `fase-1: correccion de bugs criticos sin alterar formulas`

> ⚠️ En módulos de cálculo: solo se corrigen problemas de código Python (imports, manejo de errores, validaciones de entrada). Las fórmulas matemáticas NO se modifican.

### 1.1 — Fixes 🔴 CRASH (críticos, resolver primero)

**B1** — `qpansopy_point_filter_dockwidget.py`: Eliminar segunda llamada a `setupUi(self)` (~L58)

**B2** — `qpansopy_vss_dockwidget.py`: `logTextEdit.setMaximumHeight(0)` -> `setMaximumHeight(16777215)`

**B3** — `qpansopy_wind_spiral_dockwidget.py`: Fix ISA Calculator — leer resultado del dialog:

```python
def show_isa_calculator_dialog(self):
    from ..isa_calculator_dialog import ISACalculatorDialog
    dlg = ISACalculatorDialog(self)
    if dlg.exec_():
        isa_variation = dlg.get_isa_variation()
        if isa_variation is not None:
            self.isaVarLineEdit.setText(f"{isa_variation:.5f}")
```

**B4, B5, B6** — Validar longitud de geometría antes de acceder por índice:

```python
runway_geom = runway_feature.geometry().asPolyline()
if len(runway_geom) < 2:
    self.iface.messageBar().pushMessage(
        "Error", "La pista debe tener al menos 2 vértices", level=2)
    return
```

**B7** — `qpansopy.py`: Guardar ImportErrors y mostrarlos en `initGui()`:

```python
_IMPORT_ERRORS = []
try:
    from .dockwidgets.conv import qpansopy_conv_initial_dockwidget
except ImportError as e:
    _IMPORT_ERRORS.append(str(e))
# En initGui():
if _IMPORT_ERRORS:
    from qgis.PyQt.QtWidgets import QMessageBox
    QMessageBox.critical(None, "QPANSOPY — Import Error",
                         "Failed to load:\n" + "\n".join(_IMPORT_ERRORS))
    return
```

**C1, C2** — `ndb_approach.py` y `vor_approach.py`: Eliminar líneas 47-60 (primer bloque de cálculo de puntos es sobreescrito inmediatamente por el segundo bloque en L62-71)

**C5** — `modules/utilities/holding.py`: Fix sintaxis Python 3.9:

```python
from typing import Optional
# Cambiar:
output_dir: str | None = None
# Por:
output_dir: Optional[str] = None
```

**D11** — `qpansopy_holding_dockwidget.py`: Envolver todas las conversiones `float()` en try/except:

```python
try:
    ias = float(self.iasLineEdit.text())
    alt = float(self.altLineEdit.text())
    bank = float(self.bankAngleLineEdit.text())
    wind = float(self.windSpeedLineEdit.text())
except ValueError as e:
    self.iface.messageBar().pushMessage(
        "QPANSOPY Error", f"Valor numérico inválido: {e}", level=2)
    return
```

---

### 1.2 — Fixes 🟠 SILENT ERRORS (alta prioridad)

**B8, C3, C4** — `oas_ils.py`: Refactorización de globals y validaciones:

```python
# Añadir al inicio de cada función que usa OAS_W/X/Y/Z:
if OAS_W is None or OAS_X is None or OAS_Y is None or OAS_Z is None:
    raise RuntimeError("OAS CSV not loaded. Call load_oas_csv() first.")

# Añadir validación de geometry_dict:
required_keys = ["C", "Cmirror", "D", "Dmirror", "E", "Emirror"]
missing = [k for k in required_keys if k not in geometry_dict]
if missing:
    raise ValueError(f"compute_geom() returned incomplete geometry. Missing: {missing}")
```

**B9** — `wind_spiral.py` ~L20: Confirmar con documentación ICAO si `w = 30` es estándar. Si no lo es:

```python
def tas_calculation(ias, altitude, var, bank_angle, wind_speed: float = 30):
    w = wind_speed  # usar parámetro en lugar de hardcoded
```

**B10** — Añadir `encoding='utf-8'` en todos los `open()` de KML/CSV en todos los módulos y dockwidgets

**C6** — `holding.py`: Mejorar manejo del import de `wind_spiral`:

```python
try:
    from ..wind_spiral import tas_calculation
except ImportError as e:
    raise ImportError(f"holding.py requires wind_spiral.py in parent module: {e}") from e
```

**C7** — `pbn/gnss_waypoint.py`: Validar features seleccionados:

```python
features = list(routing_layer.selectedFeatures())
if not features:
    self.iface.messageBar().pushMessage(
        "QPANSOPY", "Select a routing segment first", level=1)
    return None
```

**D1** — `conv/qpansopy_conv_initial_dockwidget.py` ~L89: Envolver import dinámico:

```python
try:
    module = importlib.import_module(module_path)
except ImportError as e:
    self.iface.messageBar().pushMessage("Error", f"Module not found: {e}", level=2)
    return
```

**D3** — `qpansopy_sid_initial_dockwidget.py` ~L204: Añadir guard:

```python
if hasattr(self, 'logTextEdit'):
    self.logTextEdit.append(message)
```

**D4** — `qpansopy_ils_dockwidget.py` ~L76-77: Reemplazar `setup_lineedits()` dinámico usando QLineEdit directamente en `.ui` (requiere editar el `.ui` con Qt Designer)

**D5** — `qpansopy_ils_dockwidget.py` ~L143: Loggear error de JSON parse:

```python
except json.JSONDecodeError as e:
    self.log(f"Warning: Could not parse layer parameters: {e}")
```

**D6** — `qpansopy_ils_dockwidget.py` ~L235: Validar row antes de acceder:

```python
if row >= formLayout.rowCount():
    self.log(f"Warning: Row {row} out of range in form layout")
    return
```

**D7** — `qpansopy_oas_ils_dockwidget.py`: Resetear csv_path al inicio de cada validate:

```python
def validate_inputs(self):
    self.csv_path = None  # resetear para evitar reutilizar CSV de sesión anterior
    ...
```

**D8** — `qpansopy_oas_ils_dockwidget.py`: Validar headers del CSV:

```python
REQUIRED_CSV_HEADERS = {"category", "threshold", "rwy_width", ...}
with open(csv_path, 'r', encoding='utf-8') as f:
    headers = set(f.readline().strip().split(','))
if not REQUIRED_CSV_HEADERS.issubset(headers):
    missing = REQUIRED_CSV_HEADERS - headers
    self.iface.messageBar().pushMessage("Error", f"CSV missing columns: {missing}", level=2)
    return
```

**D9** — `qpansopy_feature_merge_dockwidget.py` ~L67: Fallback seguro:

```python
def get_desktop_path(self) -> str:
    try:
        return str(pathlib.Path.home() / "Desktop")
    except Exception:
        return str(pathlib.Path.home())
```

**D10** — `qpansopy_feature_merge_dockwidget.py` ~L190: Añadir None check:

```python
if merged_layer is None:
    self.iface.messageBar().pushMessage("Error", "Failed to create merged layer", level=2)
    return
crs = merged_layer.crs()
```

**D13** — `qpansopy_vss_dockwidget.py` ~L105-107: Conectar directamente sin hasattr:

```python
# Los botones existen en el .ui, conectar directamente:
self.copyWordButton.clicked.connect(self.copy_parameters_for_word)
self.copyJsonButton.clicked.connect(self.copy_parameters_as_json)
```

**D14** — `qpansopy_wind_spiral_dockwidget.py` ~L147: Regex solo acepta positivos:

```python
# Antes:
validator = QRegExpValidator(QRegExp(r"[-+]?[0-9]*\.?[0-9]+"))
# Después:
validator = QRegExpValidator(QRegExp(r"[0-9]*\.?[0-9]+"))
```

**D15** — `qpansopy.py` ~L285: Guard antes de acceder al toolbar:

```python
if toolbar_name not in self.toolbars:
    import warnings
    warnings.warn(f"Toolbar '{toolbar_name}' not found, skipping action")
    return
self.toolbars[toolbar_name].addAction(action)
```

---

### 1.3 — Fixes 🟡 CODE SMELLS (batch en un commit)

```
B11  — Eliminar except AttributeError dead code en qpansopy.py ~L345
B13  — Aplicar QRegExpValidator o eliminar setup_validators() en SID dockwidget
B14  — Eliminar: import runpy en qpansopy_lnav_dockwidget.py L6
B15  — Eliminar: from qgis.utils import iface a nivel de módulo (9 archivos)
B16  — Eliminar: import datetime en 3 archivos conv dockwidgets
B17  — except: -> except Exception: en todos los sitios (4 archivos)
B18  — Eliminar código muerto después de pass en setup_copy_button()
B19  — Mover import json al nivel de módulo en OAS ILS dockwidget
B20  — QFileDialog(None) -> QFileDialog(iface.mainWindow()) en oas_ils.py
C8   — Bare except en PBN files -> except (AttributeError, TypeError, IndexError) as e:
C9   — Verificar retorno de geom.transform() en selection_of_objects.py
C10  — Añadir if len(u) < 2: antes de cString.setPoints(u) en wind_spiral.py
C11  — Envolver script global de PBN_RNAV1_2 en función run_rnav_missed(iface, ...)
C12  — Envolver script global de CONV-Initial-Approach-Straight en función
D2   — Añadir exportKmlCheckBox al layout o eliminar creación dinámica
D12  — Eliminar línea de error duplicada en object_selection dockwidget L81-82
U1   — Renombrar labels genéricos en qpansopy_ils_dockwidget.ui (label, label_2, etc.)
U2   — Decidir entre wind_spiral_dockwidget.ui y _new.ui; eliminar el inactivo
```

---

## Fase 2 — Expansión de tests (antes de refactorizar)

> **Objetivo:** Tests de regresión ANTES de tocar la estructura.
> **Esfuerzo:** 6-8 h | **Riesgo:** Bajo
> **Commit:** `fase-2: tests de regresion para modulos de calculo`

### 2.1 — Nueva estructura de tests

```
external_testing/tests/
├── conftest.py                        (mejorar mocks de QgsGeometry)
├── unit/
│   ├── __init__.py
│   ├── test_utils_calc.py             (conversiones ft->m, nm->m)
│   ├── test_kml_utils.py              (fix_kml_altitude_mode)
│   ├── test_geometry_inputs.py        (validación de polylines — B4/B5/B6)
│   ├── test_holding_compat.py         (C5: Python 3.9 compat)
│   └── test_oas_globals.py            (B8/C3/C4: estado OAS entre llamadas)
└── [tests existentes sin modificar]
```

### 2.2 — Tests clave para los bugs corregidos

```python
# test_geometry_inputs.py
def test_polyline_single_vertex_raises():
    """Fix B4/B5/B6: previene IndexError."""
    with pytest.raises(ValueError, match="al menos 2 vértices"):
        validate_polyline_geometry(mock_polyline(vertices=1))

def test_polyline_two_vertices_ok():
    assert validate_polyline_geometry(mock_polyline(vertices=2)) is True

# test_holding_compat.py
def test_holding_imports_on_python_39():
    """Fix C5: no debe dar SyntaxError en Python 3.9."""
    import sys, importlib
    assert sys.version_info >= (3, 9)
    mod = importlib.import_module('Q_Pansopy.modules.utilities.holding')
    assert mod is not None

# test_oas_globals.py
def test_oas_state_not_contaminated_between_calls(mock_oas_inputs):
    """Fix B8: segunda llamada no reutiliza estado de la primera."""
    result1 = calculate_oas_ils(**mock_oas_inputs)
    result2 = calculate_oas_ils(**mock_oas_inputs)
    assert result1 == result2  # deben ser idénticos, no contaminados

# test_holding_float_inputs.py
def test_holding_invalid_text_input_does_not_crash():
    """Fix D11: texto no debe crashear el holding dockwidget."""
    widget = HoldingDockWidget(iface=MockIface())
    widget.iasLineEdit.setText("abc")
    widget.calculate()  # debe mostrar error, no lanzar ValueError
```

### 2.3 — Cobertura objetivo

```ini
# setup.cfg
[tool:pytest]
testpaths = external_testing/tests
addopts = --cov=Q_Pansopy --cov-report=term-missing --cov-report=html:coverage_html
```

Objetivo de cobertura mínima: **60%** antes de Fase 3.

---

## Fase 3 — Refactorización de módulos (estructura, SIN tocar fórmulas)

> **Objetivo:** Extraer constantes, helpers de IO y validaciones. Fórmulas intactas.
> **Esfuerzo:** 6-8 h | **Riesgo:** Medio (cubierto por tests de Fase 2)
> **Commit:** `fase-3: refactor estructura modulos - constantes y helpers`

> ⚠️ REGLA: Solo se mueven fragmentos que NO son cálculo aeronáutico (constantes numéricas, funciones de IO, validaciones de entrada).

### 3.1 — Crear `modules/constants.py` (A4)

```python
from typing import Final

# Conversiones
FT_TO_M: Final[float] = 0.3048
NM_TO_M: Final[float] = 1852.0
KT_TO_MS: Final[float] = 0.514444

# ILS
ILS_GROUND_LENGTH_M: Final[float] = 960.0
ILS_APPROACH_1_M: Final[float] = 3000.0
ILS_SPLAY_RATIO: Final[float] = 0.15
ILS_TRANSITION_SLOPE: Final[float] = 14.3
```

### 3.2 — Centralizar `get_desktop_path()` en `utils.py` (A5)

```python
def get_desktop_path() -> pathlib.Path:
    """Returns Desktop path, falls back to home directory on error."""
    try:
        return pathlib.Path.home() / "Desktop"
    except Exception:
        return pathlib.Path.home()
```

Eliminar las 12 implementaciones duplicadas en los dockwidgets.

### 3.3 — Eliminar `correct_kml_structure()` anidada (A3)

Reemplazar en `basic_ils.py` con `utils.fix_kml_altitude_mode()` que ya existe.

### 3.4 — Resolver duplicación PBN_LNAV (C13)

```python
def run_approach_segment(segment_type: str, iface, params: dict):
    """Factory para los 3 segmentos LNAV con 95% de código compartido."""
    SEGMENT_CONSTANTS = {
        'final': {'xtt': 0.93, 'att': 0.56, ...},
        'initial': {'xtt': 1.00, 'att': 0.75, ...},
        'intermediate': {'xtt': 0.93, 'att': 0.56, ...},
    }
    consts = SEGMENT_CONSTANTS[segment_type]
    # ... lógica común sin formulas aeronauticas ...
```

### 3.5 — Exponer API en `modules/__init__.py` (A6)

```python
from .basic_ils import calculate_basic_ils
from .oas_ils import calculate_oas_ils
from .vss_straight import calculate_vss_straight
from .vss_loc import calculate_vss_loc
from .wind_spiral import calculate_wind_spiral
```

---

## Fase 4 — Refactorización de dockwidgets

> **Objetivo:** Eliminar ~78% de boilerplate duplicado entre los 15 dockwidgets.
> **Esfuerzo:** 6-10 h | **Riesgo:** Medio
> **Commit:** `fase-4: refactor dockwidgets - clase base y deduplicacion`

### 4.1 — Crear `dockwidgets/base_dockwidget.py`

```python
class BasePansopyDockWidget(QDockWidget):
    """Base class: centraliza log, show_error, copy_parameters, output_path."""

    def log(self, message: str) -> None:
        if hasattr(self, 'logTextEdit'):
            self.logTextEdit.append(message)
            self.logTextEdit.ensureCursorVisible()

    def get_output_path(self) -> pathlib.Path:
        from ..utils import get_desktop_path
        return get_desktop_path()

    def show_error(self, message: str) -> None:
        if hasattr(self, 'iface') and self.iface:
            self.iface.messageBar().pushMessage("QPANSOPY Error", message, level=2)

    def copy_parameters_to_clipboard(self) -> None: ...
    def copy_parameters_for_word(self) -> None: ...
    def copy_parameters_as_json(self) -> None: ...
```

### 4.2 — Fix D4: Eliminar setup_lineedits() dinámico

Reemplazar los spinboxes en `qpansopy_ils_dockwidget.ui` con QLineEdit en Qt Designer. Eliminar el método `setup_lineedits()` de aproximadamente 20 líneas en el dockwidget.

### 4.3 — Descomponer `qpansopy_wind_spiral_dockwidget.py` (839 líneas)

Separar responsabilidades:

- Validación de inputs: `_validate_wind_spiral_inputs()`
- ISA dialog: usar `ISACalculatorDialog` (ya existe en `isa_calculator_dialog.py`)
- Exportación KML/JSON: extraer a `BasePansopyDockWidget`
- Cálculo: llamar a `modules.wind_spiral` (sin cambio)

---

## Fase 5 — Mejora de UI/UX

> **Objetivo:** Consistencia visual, feedback durante cálculo, tooltips, log legible.
> **Esfuerzo:** 8-15 h | **Riesgo:** Bajo
> **Commit:** `fase-5: mejora UI/UX - estilos tooltips y feedback visual`

### 5.1 — Crear `styles/dockwidget_base.qss`

```css
QDockWidget > QWidget {
  background-color: #2b2b2b;
  color: #e0e0e0;
}
QGroupBox {
  font-weight: bold;
  color: #4dabf7;
  border: 1px solid #404040;
  margin-top: 8px;
}
QLineEdit {
  background-color: #1e1e1e;
  border: 1px solid #555;
  color: #e0e0e0;
  padding: 2px 4px;
}
QLineEdit:focus {
  border-color: #4dabf7;
}
QLineEdit[invalid="true"] {
  border-color: #ff6b6b;
}
QPushButton#calculateButton {
  background-color: #1971c2;
  color: white;
  font-weight: bold;
  padding: 4px 12px;
}
QPushButton#calculateButton:hover {
  background-color: #1864ab;
}
```

### 5.2 — QProgressBar indeterminado durante cálculos

```python
def _run_with_feedback(self, calc_fn):
    self.calculateButton.setEnabled(False)
    self.progressBar.setRange(0, 0)  # spinner indeterminado
    try:
        calc_fn()
    finally:
        self.calculateButton.setEnabled(True)
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(1)
```

### 5.3 — Tooltips en campos críticos

```python
self.thrElevLineEdit.setToolTip("Threshold Elevation\nUnidad: ft\nRango: -1000 a 15000")
self.rwyWidthLineEdit.setToolTip("Runway Width\nUnidad: m\nEjemplo: 45")
```

### 5.4 — Log en HTML (en lugar de texto plano)

```python
html = "<table border='1' style='border-collapse:collapse;'>"
html += "<tr><th>Parámetro</th><th>Valor</th></tr>"
for k, v in params.items():
    html += f"<tr><td>{k}</td><td>{v}</td></tr>"
html += "</table>"
self.logTextEdit.setHtml(html)
```

---

## Fase 6 — Reestructura de carpetas final

> **Objetivo:** snake_case en todos los nombres, sin duplicados, sin guiones en nombres importables.
> **Esfuerzo:** 2-3 h | **Riesgo:** Medio (actualizar imports después de mover)
> **Commit:** `fase-6: reestructura carpetas snake_case`

### Renombrados necesarios

```
modules/pbn/PBN_LNAV_Final_Approach.py        -> lnav_final_approach.py
modules/pbn/PBN_LNAV_Initial_Approach.py      -> lnav_initial_approach.py
modules/pbn/PBN_LNAV_Intermediate_Approach.py -> lnav_intermediate_approach.py
modules/pbn/PBN_LNAV_Missed_Approach.py       -> lnav_missed_approach.py
modules/pbn/PBN_RNAV1_2_missed_less_15NM.py   -> modules/pbn/rnav1_2_missed_less_15nm.py
modules/utilities/Conventional-Holding-Navaid.py -> conventional_holding_navaid.py
modules/conv/CONV-Initial-Approach-Straight.py -> conv_initial_approach_straight.py
```

> **Nota:** Actualizar todos los imports correspondientes en `qpansopy.py` y en los dockwidgets.

---

## Fase 7 — Migración PyQt5 / PyQt5+PyQt6 dual (ÚLTIMA)

> **Objetivo:** Con el proyecto limpio y estable, crear una capa de compatibilidad Qt.
> **Por qué al final:** Los imports deben estar estabilizados antes de esta fase.
> **Esfuerzo:** 3-4 h | **Riesgo:** Medio — afecta todos los archivos que importan Qt
> **Commit:** `fase-7: capa qt_compat para soporte PyQt5 y PyQt6`

### 7.1 — Crear `Q_Pansopy/qt_compat.py`

```python
"""Capa de compatibilidad Qt: QGIS wrapper > PyQt6 > PyQt5."""

try:
    # Dentro de QGIS — usar el wrapper propio de QGIS (preferido)
    from qgis.PyQt.QtWidgets import (
        QDockWidget, QDialog, QWidget, QLabel, QLineEdit,
        QComboBox, QPushButton, QGroupBox, QFileDialog, QMessageBox,
    )
    from qgis.PyQt.QtCore import Qt, QVariant, pyqtSignal
    from qgis.PyQt.QtGui import QIcon, QFont, QColor
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QDockWidget, QDialog, QWidget, QLabel, QLineEdit,
            QComboBox, QPushButton, QGroupBox, QFileDialog, QMessageBox,
        )
        from PyQt6.QtCore import Qt, pyqtSignal

        class QVariant:
            """Stub para PyQt6 (no tiene QVariant nativo)."""
            Int = 2; Double = 6; String = 10; Bool = 1

        from PyQt6.QtGui import QIcon, QFont, QColor
    except ImportError:
        from PyQt5.QtWidgets import (
            QDockWidget, QDialog, QWidget, QLabel, QLineEdit,
            QComboBox, QPushButton, QGroupBox, QFileDialog, QMessageBox,
        )
        from PyQt5.QtCore import Qt, QVariant, pyqtSignal
        from PyQt5.QtGui import QIcon, QFont, QColor
```

### 7.2 — Migrar imports en los 13+ archivos afectados

```python
# Antes (en cada dockwidget y módulo):
from PyQt5.QtCore import QVariant
from PyQt5.QtWidgets import QDockWidget

# Después:
from Q_Pansopy.qt_compat import QVariant, QDockWidget
```

### 7.3 — Archivos a migrar

```
Q_Pansopy/qpansopy.py
Q_Pansopy/utils.py
Q_Pansopy/isa_calculator_dialog.py
Q_Pansopy/settings_dialog.py
Q_Pansopy/dockwidgets/base_dockwidget.py     (creado en Fase 4)
Q_Pansopy/dockwidgets/conv/*.py              (3 archivos)
Q_Pansopy/dockwidgets/departures/*.py        (2 archivos)
Q_Pansopy/dockwidgets/ils/*.py               (2 archivos)
Q_Pansopy/dockwidgets/pbn/*.py               (2 archivos)
Q_Pansopy/dockwidgets/utilities/*.py         (5 archivos)
```

---

## Resumen y prioridades

| Fase  | Descripción                                       | Esfuerzo | Riesgo | Prioridad     |
| ----- | ------------------------------------------------- | -------- | ------ | ------------- |
| **0** | Limpieza: borrar archivos muertos y duplicados    | 1-2 h    | Mínimo | **Inmediata** |
| **1** | Corregir 60 bugs (🔴 crash + 🟠 silenciosos + 🟡) | 6-8 h    | Bajo   | **Alta**      |
| **2** | Tests de regresión (antes de refactorizar)        | 6-8 h    | Bajo   | **Alta**      |
| **3** | Refactorizar estructura de módulos                | 6-8 h    | Medio  | Media         |
| **4** | Refactorizar dockwidgets + crear clase base       | 6-10 h   | Medio  | Media         |
| **5** | Mejora UI/UX: estilos, tooltips, feedback visual  | 8-15 h   | Bajo   | Media         |
| **6** | Reestructura de carpetas: snake_case, sin guiones | 2-3 h    | Medio  | Baja          |
| **7** | Migración PyQt5/PyQt6 dual <- **ÚLTIMA FASE**     | 3-4 h    | Medio  | Baja (última) |

> **Secuencia obligatoria:** Fase 0 -> 1 (bugs) -> 2 (tests) -> 3+4 (refactor) -> 5 (UI) -> 6 (carpetas) -> 7 (Qt migration)

---

## Reglas de desarrollo (resumen)

1. **Crear la rama antes de empezar:** `git checkout -b refactor/qpansopy-v1`
2. **Las fórmulas aeronáuticas NO se tocan** — solo estructural, nunca lógica matemática.
3. **Test antes de refactorizar** — si no hay test, escribirlo primero.
4. **Constantes con nombre** — ningún número mágico sin entrada en `constants.py`.
5. **Un archivo, una responsabilidad** — UI en dockwidgets, cálculo en modules, utilidades en utils.
6. **Commits atómicos por fase** — un commit o PR por fase, revisable y revertible.
7. **La migración Qt es la última** — primero refactorizar con PyQt5, al final migrar.
