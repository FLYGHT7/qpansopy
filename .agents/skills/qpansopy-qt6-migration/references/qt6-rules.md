# Reglas técnicas para QGIS 4 y Qt6

## Contrato y preservación

- El plugin requiere QGIS 4, Qt6 y PyQt6. Importa Qt mediante `qgis.PyQt`, sin
  fallbacks a bindings standalone ni a Qt5. No mezcles bindings.
- Antes de retirar soporte, declara `qgisMinimumVersion=4.0` y conserva
  `qgisMaximumVersion=4.99`. `classFactory` debe rechazar versiones antiguas con
  un mensaje claro antes de importar el plugin completo. Prueba el rechazo
  mediante mocks aislados; no instales PyQt5 para probarlo.
- No cambies fórmulas PANS-OPS, tolerancias numéricas, campos, nombres de capas,
  unidades, selección, estilos, contenido JSON `parameters` ni valores iniciales.
- No aproveches la migración para rediseñar, reorganizar módulos o modernizar
  APIs QGIS que funcionan en el destino y no pertenecen al soporte retirado.

## Cambios que debes buscar

| Patrón anterior | Destino |
|---|---|
| `QVariant.String` en `QgsField` | `QMetaType.Type.QString` |
| `QVariant.Int/Double/LongLong/Bool` en campos | Miembro correspondiente de `QMetaType.Type` |
| `Qt.AlignTop`, `Qt.Vertical`, `Qt.NoPen` | `Qt.AlignmentFlag.AlignTop`, `Qt.Orientation.Vertical`, `Qt.PenStyle.NoPen` |
| Flags de `QDockWidget`, `QSizePolicy`, `QFormLayout` | Enum anidado real de su clase |
| `QAction` desde `QtWidgets` | `qgis.PyQt.QtGui.QAction` |
| `QgsWkbTypes.LineGeometry` | `Qgis.GeometryType.Line` |
| Niveles `Qgis.Info/Warning/Success/Critical` | `Qgis.MessageLevel.*` |
| `QgsAction.GenericPython` | `QgsAction.ActionType.GenericPython` |
| `exec_()` | `exec()`; verificar resultado y cancelación |
| `QRegExp` y validador antiguo | `QRegularExpression` y `QRegularExpressionValidator` |

Confirma nombres y firmas con el runtime instalado y documentación oficial.
No reemplaces enums por enteros ni por clases de mentira en producción.
El detector AST es deliberadamente acotado: no detecta todo acceso dinámico,
alias de módulos o miembros que llegan por `import *`. Complementa con `rg`
y revisión del alcance; su salida limpia por sí sola no acredita la migración.

Busca `getattr`, `hasattr` y `except AttributeError` que seleccionan APIs antiguas.
Retira únicamente las ramas de compatibilidad Qt5/QGIS3. Mantén comprobaciones
de controles opcionales, ciclo de vida y disponibilidad de WebEngine o estilos.

## Transición del shim

En 02, implementa sus exports restantes solo con Qt6/QGIS4 para no romper los
docks pendientes. Mueve `preseed_active_layer` a `utils.py`, preserva el
comportamiento y reexpórtalo temporalmente desde el shim. En cada herramienta,
cambia el import al helper real y usa enums/imports canónicos directamente.
En 36, elimina el shim y sus stubs cuando no tenga consumidores. El fallback
QTextBrowser del inspector se mantiene porque no es compatibilidad Qt5.

## Formularios, acciones y scripts antiguos

- Carga los `.ui` con `qgis.PyQt.uic` del runtime Qt6 y crea el dock para probar
  custom widgets QGIS, validadores y señales. No hagas reemplazos masivos de XML:
  `Qt::Vertical` también puede ser sintaxis válida del formulario en Qt6.
- Prueba mostrar, ocultar, reabrir y cerrar docks; cancelar diálogos; restaurar
  cursor; copiar tablas y limpiar rubber bands donde corresponda.
- Feature Merge usa una acción directa en el registro; incluye su dock y UI
  antiguos en 16 aunque no sean la ruta activa.
- Cuatro scripts antiguos ejecutan operaciones al cargarse. No los importes como
  smoke test: revisa AST, prepara datos en un proceso QGIS aislado y ejecútalos
  con un `iface` controlado. Preserva su modalidad de uso.
- Cambia stubs al mismo tiempo que consumidores. No mantengas fallbacks en
  producción solo porque un stub sigue exponiendo una API antigua.

## Evidencia y fuentes

La baseline y los nodeids conocidos están en el plan/registro. No añadas xfail,
skips ni cambios de expectativas para disimular regresiones. El fallo CAT E
preexistente se informa; su corrección funcional requiere otra tarea.
El runner aísla archivos porque se observó un segfault al reinicializar QGIS en
la suite combinada. Su preflight solo importa bindings; no crea QgsApplication.

- [Migración y metadatos del repositorio oficial](https://plugins.qgis.org/docs/migrate-qgis4)
- [Guía Qt5/Qt6 de QGIS](https://github.com/qgis/QGIS/wiki/Plugin-migration-to-be-compatible-with-Qt5-and-Qt6)
- [Cookbook oficial: campos y QMetaType](https://docs.qgis.org/latest/en/docs/pyqgis_developer_cookbook/vector.html)

Verifica la documentación de la versión objetivo antes de adoptar un reemplazo.
No ejecutes el script oficial de conversión sobre todo el repositorio: cada
diff debe pertenecer a la etapa en curso.
