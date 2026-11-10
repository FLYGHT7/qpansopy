# Migración gradual de QPANSOPY a QGIS 4 y Qt6

## Objetivo y forma de ejecución

Retirar PyQt5 y la compatibilidad QGIS 3, conservar únicamente QGIS 4 con Qt6
mediante `qgis.PyQt`, y eliminar `qt_compat.py` al terminar. Preservar cálculos,
geometrías, atributos, unidades, estilos y comportamiento funcional.

Usar GPT-6.1-Terra con `$qpansopy-qt6-migration continúa con la siguiente etapa`.
Cada invocación completa una etapa, sus pruebas y su commit local. La entrega
inicial es 00: skill, plan, catálogo y helpers; la migración funcional empieza
con las siguientes invocaciones. No seleccionar otro modelo desde la skill.

El catálogo [batches.json](batches.json) contiene archivos, dependencias, ramas,
pruebas, notas y evidencia por etapa. Los 86 Python y 27 formularios están
asignados una sola vez, incluidos cuatro scripts antiguos sin dock activo.
Actualizar el catálogo cuando se agreguen, muevan o eliminen archivos.

## Arranque y contexto reducido

Desde la raíz, ejecutar:

```bash
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/context.py
```

Leer solo la etapa seleccionada, su código y vecinos inmediatos. El helper
resuelve imports estáticos actuales y muestra pistas Graphify con sus límites.
Graphify cubría 80 de 86 Python al investigar; excluye `.ui`, es no dirigido y
registra 409 aristas con extremos colgantes y 49 aristas colapsadas. No deducir
dirección de llamadas ni completitud del grafo. Comparar hashes del manifiesto;
cuando falte o esté desactualizado, usar AST/rg sin reconstruirlo por etapa.
El AST tampoco resuelve todas las llamadas dinámicas ni los import wildcard.

`context.py --batch NN` inspecciona una etapa. `--audit` comprueba cobertura del
inventario y muestra hallazgos. `--json` entrega detalle para filtrar en un
script, sin pegar el grafo o catálogo completo al contexto del modelo.

## Secuencia aprobada

Las etapas compartidas preceden al orden por tamaño para mantener la carga y
validación del plugin. Los tamaños excluyen tests/XML. Slope y Secondary se
hacen después de Primary por dependencia; Holding requiere Wind Spiral.
Cada fila corresponde a una rama independiente, incluso los scripts antiguos.

| ID | Etapa | Slug de rama | Líneas Python propias |
|---|---|---|---:|
| 00 | Skill, plan e inventario | workflow | 0 |
| 01 | Pruebas Qt6 y stubs | test-harness | 0 |
| 02 | Contrato QGIS 4 y base Qt6 | foundation | 1152 |
| 03 | Diálogos compartidos | shared-dialogs | 908 |
| 04 | Arranque y contenedor del plugin | plugin-shell | 1513 |
| 05 | Script antiguo GNSS Waypoint | legacy-gnss-waypoint | 101 |
| 06 | PBN Target | pbn-target | 118 |
| 07 | Script antiguo CONV Initial Straight | legacy-conv-initial-straight | 202 |
| 08 | NDB | ndb | 203 |
| 09 | VOR | vor | 203 |
| 10 | PBN Enroute GNSS | pbn-enroute-gnss | 225 |
| 11 | GNSS Waypoint | gnss-waypoint | 272 |
| 12 | Script antiguo Conventional Holding Navaid | legacy-holding-navaid | 285 |
| 13 | Script antiguo RNAV Missed <15 NM | legacy-rnav-missed | 305 |
| 14 | AMA Grid | ama-grid | 331 |
| 15 | Object Selection | object-selection | 385 |
| 16 | Feature Merge | feature-merge | 395 |
| 17 | DME Tolerance | dme-tolerance | 408 |
| 18 | DME/DME Coverage | dme-dme-coverage | 409 |
| 19 | CONV Initial | conv-initial | 429 |
| 20 | Overhead Tolerance | overhead-tolerance | 471 |
| 21 | Point Filter | point-filter | 480 |
| 22 | Radial/Bearing Intersection | radial-bearing | 552 |
| 23 | Enroute VOR/VOR | enroute-vor-vor | 638 |
| 24 | Circling | circling | 718 |
| 25 | Basic ILS | basic-ils | 903 |
| 26 | SID Initial | sid-initial | 996 |
| 27 | Wind Spiral | wind-spiral | 1016 |
| 28 | Omnidirectional SID | omnidirectional-sid | 1035 |
| 29 | Primary Area Assessment | primary-assessment | 1078 |
| 30 | Slope Primary Area Assessment | slope-assessment | 623 |
| 31 | Secondary Area Assessment | secondary-assessment | 876 |
| 32 | Holding | holding | 1113 |
| 33 | OAS ILS | oas-ils | 1133 |
| 34 | VSS Straight/LOC | vss | 1320 |
| 35 | LNAV y segmentos | lnav | 1423 |
| 36 | Auditoría final y eliminación del shim | cleanup | 0 |

### Reglas de implementación

- **01:** actualizar stubs a API Qt6, corregir los cuatro errores SID y crear
  `test_qt6_plugin_runtime.py` para probar el registro, formularios, señales y
  ciclo mostrar/ocultar/reabrir/cerrar de las 27 herramientas. Añadirlo a las
  listas runtime siguientes; la acción Feature Merge también se valida.
- **02:** mínimo QGIS 4.0, máximo 4.99; guard de QGIS/Qt antes de importar el
  plugin desde classFactory. Probar rechazo con mocks. Mantener temporalmente
  exports del shim solo Qt6; mover preseed_active_layer a utils y reexportarlo
  hasta migrar todos los consumidores. Revisar también paquetes/constantes.
- **03–04:** retirar compatibilidad de diálogos y shell; QAction desde QtGui,
  enums canónicos. Mantener visor QTextBrowser cuando falte WebEngine.
- **05–35:** módulo + dock + UI + pruebas en el mismo cambio; imports directos,
  enums anidados y QMetaType.Type en campos, sin cambiar sus tipos reales.
  Preservar las funciones públicas y los formatos de salida. Crear pruebas
  runtime nominales donde no existan, además de los tests compartidos.
- Scripts antiguos: revisión AST y ejecución con iface/datos controlados en
  QGIS aislado; evitar importarlos indiscriminadamente o borrarlos por desuso.
- Formularios: cargar mediante uic Qt6 y crear los custom widgets QGIS.
  `Qt::Vertical` en XML no demuestra soporte Qt5 ni obliga a reemplazarlo.
- **36:** cero consumidores del shim; eliminarlo y sus stubs, registrar
  `deleted_files` y revisar todo el paquete, documentación y dependencias.
  Auditar aliases, import *, getattr y fallbacks manualmente además del helper.

La [referencia técnica](../../.agents/skills/qpansopy-qt6-migration/references/qt6-rules.md)
contiene reemplazos y fuentes oficiales. No ampliar la tarea a modernización
arbitraria, rediseños o cambios PANS-OPS.

## Git y avance persistente

Primera rama: `refactor/qt6-00-workflow` desde `origin/main`, inicialmente
`b7c7be080d1fc76609722294cdf3e24e146b7451`. Las siguientes se crean con `--no-track`
desde el commit verificado de la rama anterior, con el nombre exacto del catálogo.
Registrar la base en `base_commit`. Si una rama existe, comprobar su ascendencia
y reanudarla. Comprobar árbol limpio y preservar cambios ajenos antes de cambiar.

Estados: pending → in_progress → done o verified_unchanged. Usar blocked cuando
falte una condición necesaria. No saltar una etapa bloqueada. Guardar comandos,
resultados y limitaciones en evidence. Un estado terminado solo se consolida con
su commit; el helper exige el trailer alcanzable desde HEAD antes de saltarlo.
No guardar el SHA del propio commit dentro del archivo que contiene ese commit.

Añadir rutas explícitas y revisar diff/staged. Un commit agrupa código, UI, tests
y avance de una herramienta. Mensajes:

- 00: `chore(qt6): add migration workflow`
- 01: `test(qt6): prepare runtime validation`
- Restantes: `refactor(qt6): migrate <slug>`

Todos llevan un párrafo trailer `Qt6-Batch: NN`. No hacer commits en main,
configurar tracking, publicar ramas, abrir PR ni hacer merge durante estas
invocaciones. Las decisiones de esta tarea fueron autorizadas expresamente y
prevalecen sobre convenciones generales previas de CLAUDE.md. La última rama
contendrá la cadena completa. Si falla una etapa, corregir antes de declararla
completada; nunca crear un commit que oculte una regresión como éxito.

## Validación y criterios de cierre

Baseline investigada en main: 435 passed, 12 skipped, 1 failed, 4 errors en la
suite sin runtime. CAT E de Circling difiere de su expectativa: informar ese
fallo previo y conservar el comportamiento; corregirlo requiere otra tarea.
Los cuatro errores SID son stubs incompletos y se resuelven en 01. No añadir
xfail/skip ni cambiar expectativas para esconder regresiones.

QGIS disponible: 4.2.3, Qt/PyQt 6.12.0, Python 3.14.9. Verificados por archivo:
DME 45 passed, DME/DME 17 passed y dimensionado 4 passed. La suite runtime
combinada sufrió segfault al reinicializar QGIS; ejecutar archivos en procesos
independientes. En este equipo fue necesario desactivar el tema GTK en offscreen.

```bash
.venv/bin/python -m pytest -c tests/pytest.ini -m 'not qgis_runtime'
.venv/bin/python -m pytest -c tests/pytest.ini tests/integration/test_flake8_compliance.py
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/run_qgis_tests.py tests/integration/test_dme_tolerance_qgis.py tests/integration/test_dme_dme_coverage_qgis.py tests/integration/test_dock_sizing_qgis.py
```

El runner descubre bindings comunes, fija offscreen/Fusion y admite
`--extra-pythonpath RUTA` y `QGIS_PYTHON_PATH`. Comprueba QGIS 4/Qt6/PyQt6 antes
de ejecutar. Guarda logs/JUnit fuera del código; crashes, timeout, cero pruebas
ejecutadas o todo skipped no acreditan una validación. No instala dependencias.

Por etapa: suite sin runtime comparada contra la baseline; tests propios y
runtime pertinentes; guard Flake8 sin aumentar deuda; diff --check y revisión
manual. Si el ratchet baja, ajustar baseline solo para reflejar deuda eliminada.

Para cerrar: todas las etapas verificadas, 27 herramientas/formularios cargados,
pruebas nominales que conservan geometría/esquema, ciclo de docks, cancelación,
clipboard/previews pertinentes, visor con y sin WebEngine y rechazo de versiones
antiguas. Ejecutar todos los archivos runtime por separado y:

```bash
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/context.py --audit --require-clean
```

Exigir cero dependencias/imports operativos PyQt5, variantes Qt5/QGIS3 y referencias
al shim. La auditoría AST es auxiliar, no una prueba exhaustiva. Conservar menciones
históricas y cadenas de pruebas negativas. Documentar cualquier fallo previo aún
presente; no declarar toda la suite verde mientras siga fallando.
