#!/usr/bin/env python3
"""Read-only, source-first context for one QPANSOPY Qt6 migration batch."""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, TypedDict


DONE = {'done', 'verified_unchanged'}
STATUSES = DONE | {'pending', 'in_progress', 'blocked'}
PLAN = Path('plans/qt6-only/batches.json')


class Batch(TypedDict):
    id: str
    slug: str
    title: str
    status: str
    branch: str
    parent_branch: str
    depends_on: list[str]
    source_files: list[str]
    support_files: list[str]
    unit_tests: list[str]
    runtime_tests: list[str]
    evidence: list[str]


class Ledger(TypedDict):
    schema_version: int
    batches: list[Batch]


def safe_path(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts:
        raise ValueError(f'ruta fuera del repositorio: {relative}')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'ruta fuera del repositorio: {relative}')
    return resolved


def load_ledger(root: Path) -> Ledger:
    data = json.loads((root / PLAN).read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('schema_version debe ser 1')
    if not isinstance(data.get('batches'), list) or not data['batches']:
        raise ValueError('batches debe contener etapas')
    previous: set[str] = set()
    for batch in data['batches']:
        if not isinstance(batch, dict):
            raise ValueError('etapa inválida')
        identifier = batch.get('id', '')
        if not isinstance(identifier, str) or not re.fullmatch(r'\d{2}', identifier):
            raise ValueError('identificador inválido')
        if identifier in previous:
            raise ValueError(f'identificador duplicado: {identifier}')
        if batch.get('status') not in STATUSES:
            raise ValueError(f'estado inválido: {identifier}')
        for key in ('slug', 'title', 'branch', 'parent_branch'):
            if not isinstance(batch.get(key), str) or not batch[key]:
                raise ValueError(f'{identifier}: falta {key}')
        for key in ('depends_on', 'source_files', 'support_files',
                    'unit_tests', 'runtime_tests', 'evidence'):
            values = batch.get(key)
            if not isinstance(values, list) or any(not isinstance(v, str) for v in values):
                raise ValueError(f'{identifier}: lista inválida {key}')
            if key in ('source_files', 'support_files', 'unit_tests', 'runtime_tests'):
                for value in values:
                    safe_path(root, value)
        if not set(batch['depends_on']) <= previous:
            raise ValueError(f'{identifier}: dependencia desconocida o posterior')
        previous.add(identifier)
    return data


def choose_batch(ledger: Ledger, requested: str) -> Batch | None:
    rows = ledger['batches']
    if requested == 'next':
        batch = next((b for b in rows if b['status'] not in DONE), None)
    else:
        batch = next((b for b in rows if b['id'] == requested), None)
        if batch is None:
            raise ValueError(f'etapa desconocida: {requested}')
    if batch is not None:
        statuses = {b['id']: b['status'] for b in rows}
        if any(statuses[d] not in DONE for d in batch['depends_on']):
            raise ValueError(f'{batch["id"]}: dependencias pendientes')
    return batch


def verify_history(root: Path, ledger: Ledger) -> None:
    finished = {b['id'] for b in ledger['batches'] if b['status'] in DONE}
    if not finished:
        return
    result = subprocess.run(
        ['git', '-C', str(root), 'log', '--format=%B',
         '--grep=^Qt6-Batch: ', 'HEAD'], capture_output=True, text=True,
        check=False,
    )
    committed = set(re.findall(r'^Qt6-Batch: (\d{2})$', result.stdout, re.MULTILINE))
    if result.returncode or not finished <= committed:
        missing = ', '.join(sorted(finished - committed))
        raise ValueError(f'etapas terminadas sin commit alcanzable desde HEAD: {missing}')


def inventory(root: Path, ledger: Ledger) -> dict[str, Any]:
    actual = {str(p.relative_to(root)) for p in (root / 'Q_Pansopy').rglob('*')
              if p.is_file() and p.suffix in ('.py', '.ui')}
    counts = Counter(p for b in ledger['batches'] for p in b['source_files'])
    # A deletion must be recorded on the completed cleanup batch, not hidden.
    removed = {p for b in ledger['batches'] if b['status'] in DONE
               for p in b.get('deleted_files', [])}
    return dict(python_files=sum(p.endswith('.py') for p in actual),
                ui_files=sum(p.endswith('.ui') for p in actual),
                unassigned=sorted(actual - counts.keys()),
                missing=sorted(counts.keys() - actual - removed),
                duplicates=sorted(p for p, count in counts.items() if count > 1))


def parse_source(root: Path, relative: str) -> ast.Module:
    return ast.parse(safe_path(root, relative).read_text(encoding='utf-8-sig'),
                     filename=relative)


def import_edges(root: Path) -> set[tuple[str, str]]:
    """Static Python imports only; dynamic calls and XML need source inspection."""
    paths = sorted((root / 'Q_Pansopy').rglob('*.py'))
    modules = {'.'.join(p.relative_to(root).with_suffix('').parts)
               .removesuffix('.__init__'): str(p.relative_to(root)) for p in paths}
    edges: set[tuple[str, str]] = set()
    for path in paths:
        relative = str(path.relative_to(root))
        package = path.relative_to(root).parts[:-1]
        for node in ast.walk(parse_source(root, relative)):
            candidates: list[str] = []
            if isinstance(node, ast.Import):
                candidates = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                prefix = package[:len(package) - node.level + 1] if node.level else ()
                base = '.'.join((*prefix, *((node.module or '').split('.')))).strip('.')
                candidates = [base] + [f'{base}.{a.name}' for a in node.names]
            for module in candidates:
                if module in modules and modules[module] != relative:
                    edges.add((relative, modules[module]))
    return edges


FLAT = {
    'Qt': {'RightDockWidgetArea', 'LeftDockWidgetArea', 'AlignTop', 'AlignBottom',
           'AlignLeft', 'AlignRight', 'AlignCenter', 'AlignVCenter', 'AlignHCenter',
           'ScrollBarAsNeeded', 'ScrollBarAlwaysOff', 'ScrollBarAlwaysOn',
           'SizeVerCursor', 'SizeHorCursor', 'ArrowCursor', 'PointingHandCursor',
           'WaitCursor', 'LeftButton', 'RightButton', 'MiddleButton',
           'Vertical', 'Horizontal', 'NoPen', 'TopDockWidgetArea', 'BottomDockWidgetArea'},
    'Qgis': {'Info', 'Success', 'Warning', 'Critical'},
    'QgsWkbTypes': {'PointGeometry', 'LineGeometry', 'PolygonGeometry',
                    'UnknownGeometry', 'NullGeometry'},
    'QgsMapLayer': {'VectorLayer', 'RasterLayer', 'AllVisualStyleCategories'},
    'QgsMapLayerProxyModel': {'PointLayer', 'LineLayer', 'PolygonLayer', 'VectorLayer',
                            'RasterLayer', 'All', 'NoGeometry'},
    'QgsAction': {'GenericPython'},
    'QMessageBox': {'Ok', 'Cancel', 'Yes', 'No'},
    'QDialogButtonBox': {'Ok', 'Cancel'},
    'QDockWidget': {'DockWidgetMovable', 'DockWidgetFloatable',
                    'DockWidgetClosable', 'DockWidgetVerticalTitleBar'},
    'QFormLayout': {'LabelRole', 'FieldRole', 'SpanningRole', 'AllNonFixedFieldsGrow',
                    'FieldsStayAtSizeHint', 'ExpandingFieldsGrow'},
    'QSizePolicy': {'Fixed', 'Minimum', 'Maximum', 'Preferred', 'Expanding',
                    'MinimumExpanding', 'Ignored'},
    'QFrame': {'NoFrame', 'StyledPanel', 'HLine', 'VLine'},
    'QLayout': {'SetDefaultConstraint', 'SetMinimumSize', 'SetFixedSize',
                'SetMaximumSize', 'SetMinAndMaxSize', 'SetNoConstraint'},
    'QTextEdit': {'WidgetWidth', 'NoWrap', 'FixedPixelWidth', 'FixedColumnWidth'},
    'QEvent': {'MouseButtonPress', 'MouseMove', 'MouseButtonRelease', 'Resize',
               'Close', 'Show', 'Hide'},
}


def scan_source(root: Path, relative: str) -> list[dict[str, Any]]:
    if not relative.endswith('.py') or not safe_path(root, relative).exists():
        return []
    tree = parse_source(root, relative)
    aliases = {a.asname or a.name: a.name for n in ast.walk(tree)
               if isinstance(n, ast.ImportFrom) for a in n.names}
    findings = []
    for node in ast.walk(tree):
        kind = None
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module or ''])
            if any(n.split('.')[0] in ('PyQt5', 'PyQt6') for n in names):
                kind = 'binding_import'
            elif any(n.split('.')[-1] == 'qt_compat' for n in names):
                kind = 'shim_import'
            elif isinstance(node, ast.ImportFrom) and node.module == 'qgis.PyQt.QtWidgets':
                if any(a.name == 'QAction' for a in node.names):
                    kind = 'moved_qaction'
        elif isinstance(node, ast.Attribute):
            if node.attr == 'exec_':
                kind = 'legacy_exec'
            elif isinstance(node.value, ast.Name):
                owner = aliases.get(node.value.id, node.value.id)
                if owner == 'QVariant' and node.attr in {'String', 'Double', 'Int', 'LongLong', 'Bool'}:
                    kind = 'legacy_field_type'
                elif node.attr in FLAT.get(owner, set()):
                    kind = 'flat_enum'
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == 'exec_':
            kind = 'legacy_exec'
        elif isinstance(node, ast.ExceptHandler) and isinstance(node.type, ast.Name):
            if node.type.id == 'AttributeError':
                kind = 'review_fallback'
        if kind:
            findings.append(dict(path=relative, line=node.lineno, kind=kind,
                                 code=ast.unparse(node).splitlines()[0][:160]))
    return sorted(findings, key=lambda f: f['line'])


def graph_context(root: Path, scope: set[str]) -> dict[str, Any]:
    report: dict[str, Any] = dict(warnings=[], missing=[], stale=[], neighbors=[])
    folder = root / 'graphify-out'
    try:
        data = json.loads((folder / 'graph.json').read_text(encoding='utf-8'))
        nodes = data['nodes']
        links = data.get('links', data.get('edges', []))
        if not isinstance(nodes, list) or not isinstance(links, list):
            raise ValueError('nodes/links inválidos')
        by_id = {n['id']: n for n in nodes}
        files = {n['id']: 'Q_Pansopy/' + n.get('source_file', '').removeprefix('Q_Pansopy/')
                 for n in nodes}
        selected = {nid for nid, source in files.items() if source in scope}
        report['directed'] = bool(data.get('directed', False))
        if not report['directed']:
            report['warnings'].append('Grafo no dirigido: no inferir dirección de llamadas.')
        report['missing'] = sorted(p for p in scope if p.endswith('.py') and p not in files.values())
        seen = set()
        for link in links:
            left, right = link['source'], link['target']
            for own, neighbor in ((left, right), (right, left)):
                if own in selected and neighbor in by_id and neighbor not in selected:
                    key = (files[neighbor], by_id[neighbor].get('label', ''))
                    if key not in seen:
                        seen.add(key)
                        report['neighbors'].append(dict(source_file=key[0], label=key[1],
                            source_location=by_id[neighbor].get('source_location', ''),
                            relation=link.get('relation', ''),
                            confidence=link.get('confidence', 'unverified')))
        manifest = json.loads((folder / 'manifest.json').read_text(encoding='utf-8'))
        for path in scope:
            if path.endswith('.py') and safe_path(root, path).is_file():
                entry = manifest.get(path.removeprefix('Q_Pansopy/'), {})
                digest = hashlib.md5(safe_path(root, path).read_bytes()).hexdigest()
                if not isinstance(entry, dict) or entry.get('ast_hash') != digest:
                    report['stale'].append(path)
        report['stale'].sort()
        if (folder / 'health.json').exists():
            health = json.loads((folder / 'health.json').read_text(encoding='utf-8'))
            for key in ('dangling_endpoint_edges', 'missing_endpoint_edges',
                        'undirected_same_endpoint_collapsed_edges'):
                if health.get(key, 0):
                    report['warnings'].append(f'{key}: {health[key]}')
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        report['warnings'].append(f'Graphify incompleto/no disponible: {error}')
    report['warnings'].append('Verificar el código actual; XML y llamadas dinámicas no están cubiertos.')
    return report


def build_context(root: Path, ledger: Ledger, batch: Batch) -> dict[str, Any]:
    scope = set(batch['source_files'])
    edges = import_edges(root)
    return dict(batch=batch, inventory=inventory(root, ledger),
                imports=dict(outgoing=sorted({b for a, b in edges if a in scope and b not in scope}),
                             incoming=sorted({a for a, b in edges if b in scope and a not in scope})),
                graph=graph_context(root, scope),
                findings=[f for p in sorted(scope) for f in scan_source(root, p)])


def readable(report: dict[str, Any], max_words: int) -> str:
    batch = report.get('batch')
    lines = [f'Etapa {batch["id"]}: {batch["title"]} ({batch["status"]})' if batch else 'Auditoría Qt6']
    if batch:
        lines += [f'Rama: {batch["branch"]}; base: {batch["parent_branch"]}',
                  'Alcance: ' + ', '.join(batch['source_files'] + batch['support_files']),
                  'Pruebas: ' + ', '.join(batch['unit_tests'] + batch['runtime_tests']),
                  'Evidencia: ' + '; '.join(batch['evidence']),
                  'Instrucciones: ' + '; '.join(batch.get('notes', []))]
    for key in ('inventory', 'imports', 'graph'):
        if key in report:
            lines.append(f'{key}: {json.dumps(report[key], ensure_ascii=False)}')
    findings = report.get('findings', [])
    lines.append(f'Hallazgos: {len(findings)}; ' + str(dict(Counter(f['kind'] for f in findings))))
    for finding in findings:
        lines.append(f'{finding["path"]}:{finding["line"]} [{finding["kind"]}] {finding["code"]}')
    words = '\n'.join(lines).split()
    if len(words) > max_words:
        return ' '.join(words[:max_words - 7]) + '\nSalida truncada; usar --json para detalle completo.'
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--batch', default='next')
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--require-clean', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--max-words', type=int, default=1500)
    args = parser.parse_args()
    try:
        if args.max_words < 100:
            raise ValueError('--max-words debe ser al menos 100')
        root = args.root.resolve()
        ledger = load_ledger(root)
        verify_history(root, ledger)
        if args.audit:
            report = dict(inventory=inventory(root, ledger), findings=[
                finding for p in sorted((root / 'Q_Pansopy').rglob('*.py'))
                for finding in scan_source(root, str(p.relative_to(root)))])
        else:
            batch = choose_batch(ledger, args.batch)
            if batch is None:
                print('Todas las etapas están terminadas y tienen commit alcanzable.')
                return 0
            report = build_context(root, ledger, batch)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.json
              else readable(report, args.max_words))
        coverage = report['inventory']
        incomplete = any(coverage[k] for k in ('unassigned', 'missing', 'duplicates'))
        blockers = [f for f in report['findings'] if f['kind'] != 'review_fallback']
        return int(incomplete or (args.require_clean and bool(blockers)))
    except (OSError, ValueError, SyntaxError) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
