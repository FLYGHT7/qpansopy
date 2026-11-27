---
name: qpansopy-qt6-migration
description: Migra QPANSOPY gradualmente a QGIS 4 y Qt6, retirando PyQt5 por herramienta con ramas, commits, pruebas y avance persistente. Usar para continuar o revisar esta migración concreta.
---

# Migración Qt6 de QPANSOPY

Ejecuta **una etapa por invocación**. El destino aprobado es QGIS 4 + Qt6
mediante `qgis.PyQt`, con eliminación final de `qt_compat.py`. Preserva cálculos,
geometrías, atributos, unidades, estilos y comportamiento de las herramientas.
El usuario selecciona GPT-6.1-Terra; esta skill no modifica el modelo del agente.

## Entrada mínima

Desde la raíz del repositorio:

```bash
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/context.py
```

El helper solo lee archivos y Git. Selecciona la primera etapa sin completar,
incluyendo una etapa bloqueada; no la salta. Rechaza estados terminados sin un
commit con trailer `Qt6-Batch: NN` alcanzable desde HEAD.

Lee la salida, la sección de la etapa en
[el plan](../../../../plans/qt6-only/PLAN.md) y
[las reglas Qt6](references/qt6-rules.md) cuando corresponda cambiar código.
El [registro](../../../../plans/qt6-only/batches.json) es la fuente del orden,
alcance, ramas y pruebas. No cargues el JSON completo ni el grafo completo en
el contexto: usa `--batch NN`, `--audit` o `--json` y filtra antes de mostrar.

## Trabajo de una etapa

1. Comprueba `git status --short --branch`, rama y HEAD. Conserva trabajo ajeno.
   No uses stash, reset ni cambio forzado automáticamente.
2. La etapa 00 nace de `origin/main`. Para las siguientes, exige las dependencias
   completadas y verifica que la rama base contiene sus commits. Crea la rama
   indicada con `git switch --no-track -c RAMA COMMIT_BASE`, usando el tip
   verificado de `parent_branch`. Registra ese SHA en `base_commit`.
   Si la rama ya existe, comprueba su ascendencia y reanúdala. Tras un clone,
   puedes identificar la base en HEAD por el trailer de su etapa; no necesitas
   recrear todas las ramas anteriores. No configures tracking.
3. Marca la etapa `in_progress`. Lee sus archivos y los vecinos inmediatos que
   afecten al cambio. Graphify es una pista: sus aristas no dirigidas no indican
   quién llama a quién. Confirma referencias en fuente y `.ui`. Si falta el
   grafo o está desactualizado, continúa con AST y `rg`; no reconstruyas todo.
4. Migra exclusivamente el alcance de la etapa y sus pruebas. Consulta
   `source_files`, `support_files`, `unit_tests` y `runtime_tests` del registro.
   Si necesitas tocar un consumidor externo para preservar la carga, registra
   el motivo y el alcance adicional, sin dar su herramienta por migrada.
5. Ejecuta las pruebas de la etapa, la suite sin runtime y el guard Flake8.
   Ejecuta cada archivo QGIS por separado con el runner. Compara fallos contra
   la baseline del plan; un fallo nuevo o una prueba omitida no es éxito.
6. Añade evidencia breve al registro: comandos, resultados, archivos sin cambios
   que revisaste, limitaciones y pruebas nuevas. Usa `done` al verificar cambios,
   o `verified_unchanged` si ya cumplía los requisitos y lo comprobaste.
   Este estado solo queda consolidado al crear el commit correspondiente.
7. Redacta el borrador indicado en `pr_draft` del registro:
   `docs/pyqt-migration/pr-NN-<slug>.md`, siguiendo los PR existentes en docs/.
   Usa título `# PR — ...`, Summary (problema y resultado), Changes,
   Verification (resultados reales, fallos previos y límites) y Local delivery
   (rama, base, dependencia de la etapa anterior). Describe el delta de esta
   etapa contra su rama padre; no inventes issues ni números de pruebas.
   Estos borradores quedan locales e ignorados: no añadas docs/ al índice.
8. Revisa `git diff --check`, el diff y los archivos staged. Añade rutas
   explícitas, nunca `git add .`. Haz un commit local con código/UI/pruebas y
   registro juntos. Usa `refactor(qt6): migrate <slug>` y el trailer
   `Qt6-Batch: NN`; para 00 usa `chore(qt6): add migration workflow` y para 01
   `test(qt6): prepare runtime validation`.
9. Actualiza el borrador PR con el SHA del commit creado. Reejecuta el helper: debe reconocer el commit y mostrar la siguiente etapa.
   Termina indicando rama, SHA, resultados, enlace al borrador PR y siguiente paso. **No empieces otra
   etapa**, no publiques, no abras PR ni hagas merge.

Si una prueba falla por una regresión de esta etapa, corrígela antes del commit.
Si no puedes resolverla, registra `blocked`, evidencia y siguiente acción; no
crees un commit de migración supuestamente terminado ni avances otra etapa.
Al retomar, vuelve a verificar los cambios y su base. Si un commit falló después
de marcar `done`, considera ese estado provisional: el helper impedirá saltarlo.

Las decisiones específicas de este plan (ramas encadenadas, commits locales y
artefactos versionados) fueron autorizadas expresamente por el usuario y
prevalecen para esta tarea sobre las convenciones generales de `CLAUDE.md`.
No cambies remotos ni publiques en `main` o `upstream`.

## Comandos de validación

```bash
# Cobertura del inventario; los hallazgos todavía pendientes no son un fallo.
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/context.py --audit

# Suite rápida: comparar nodeids con la baseline documentada.
.venv/bin/python -m pytest -c tests/pytest.ini -m 'not qgis_runtime'

# Usar las rutas exactas runtime_tests de la etapa como argumentos separados.
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/run_qgis_tests.py tests/integration/test_dock_sizing_qgis.py

# Ratchet existente: no aumentar la deuda ni dejar una baseline sobredimensionada.
.venv/bin/python -m pytest -c tests/pytest.ini tests/integration/test_flake8_compliance.py

# Solo al cierre; las pruebas runtime y la revisión manual siguen siendo necesarias.
.venv/bin/python .agents/skills/qpansopy-qt6-migration/scripts/context.py --audit --require-clean
```

El runner descubre rutas comunes de bindings del sistema; acepta
`--extra-pythonpath RUTA` y `QGIS_PYTHON_PATH` para otras instalaciones.
Comprueba QGIS 4/Qt6/PyQt6 antes de ejecutar. Guarda logs y JUnit en `/tmp`
(o `--log-dir`) y devuelve fallo para crashes, timeout, cero casos ejecutados
o una tanda completamente omitida. No instala paquetes ni modifica el sistema.

Al agregar, mover o retirar archivos, actualiza su dueño en el inventario. Para
una eliminación aprobada, registra `deleted_files` en la etapa que la completa.
No elimines scripts antiguos por no tener imports entrantes.
