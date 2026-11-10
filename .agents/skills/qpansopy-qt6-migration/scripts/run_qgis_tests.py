#!/usr/bin/env python3
"""Run each QGIS test file in a fresh process; never count skips as validation."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class TestRun:
    file: str
    returncode: int
    verified: bool
    log: Path


def runtime_env(root: Path, extra_paths: list[str]) -> dict[str, str]:
    env = dict(os.environ)
    candidates = [*extra_paths, env.get('QGIS_PYTHON_PATH', ''),
                  str(Path(env.get('QGIS_PREFIX_PATH', '/usr')) / 'share/qgis/python')]
    version = f'python{sys.version_info.major}.{sys.version_info.minor}'
    candidates += [str(Path(sys.base_prefix) / 'lib' / version / 'site-packages'),
                   str(Path(sys.base_prefix) / 'lib' / version / 'dist-packages'),
                   str(Path(sys.base_prefix) / 'lib/python3/dist-packages')]
    paths = [str(root), *[p for p in candidates if p and Path(p).is_dir()],
             *env.get('PYTHONPATH', '').split(os.pathsep)]
    env['PYTHONPATH'] = os.pathsep.join(dict.fromkeys(p for p in paths if p))
    env.update(QT_QPA_PLATFORM='offscreen', QT_QPA_PLATFORMTHEME='',
               QT_STYLE_OVERRIDE='Fusion')
    return env


def probe_runtime(root: Path, env: dict[str, str]) -> dict[str, str]:
    code = (
        'import json\n'
        'from qgis.core import Qgis\n'
        'from qgis.PyQt.QtCore import QT_VERSION_STR, PYQT_VERSION_STR\n'
        'assert 40000 <= Qgis.QGIS_VERSION_INT < 50000, "Requiere QGIS 4"\n'
        'assert QT_VERSION_STR.split(".")[0] == "6", "Requiere Qt6"\n'
        'assert PYQT_VERSION_STR.split(".")[0] == "6", "Requiere PyQt6"\n'
        'print(json.dumps(dict(qgis=Qgis.QGIS_VERSION, qt=QT_VERSION_STR, '
        'pyqt=PYQT_VERSION_STR)))\n'
    )
    result = subprocess.run([sys.executable, '-c', code], cwd=root, env=env,
                            capture_output=True, text=True, timeout=30, check=False)
    if result.returncode:
        raise ValueError(f'Runtime no válido: {result.stdout}{result.stderr}')
    return json.loads(result.stdout)


def run_files(root: Path, files: list[str], env: dict[str, str], python: str,
              log_dir: Path, timeout: float) -> list[TestRun]:
    resolved: list[Path] = []
    for file in files:
        path = (root / file).resolve()
        if (not path.is_relative_to((root / 'tests').resolve())
                or not path.is_file() or path.suffix != '.py'):
            raise ValueError(f'No es un archivo de pruebas dentro de tests/: {file}')
        resolved.append(path)
    if not files:
        raise ValueError('Seleccionar al menos un archivo de pruebas')
    log_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for index, path in enumerate(resolved):
        log = log_dir / f'{index:02d}-{path.stem}.log'
        junit = log.with_suffix('.xml')
        junit.unlink(missing_ok=True)
        command = [python, '-m', 'pytest', '-c', str(root / 'tests/pytest.ini'),
                   '-m', 'qgis_runtime', f'--junitxml={junit}', str(path)]
        try:
            result = subprocess.run(command, cwd=root, env=env, capture_output=True,
                                    text=True, timeout=timeout, check=False)
            output = result.stdout + result.stderr
            returncode = result.returncode
        except subprocess.TimeoutExpired as error:
            def text(value: str | bytes | None) -> str:
                return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
            output = text(error.stdout) + text(error.stderr) + '\nTIMEOUT\n'
            returncode = 124
        log.write_text(output, encoding='utf-8')
        verified = False
        if returncode == 0 and junit.exists():
            try:
                suites = list(ET.parse(junit).getroot().iter('testsuite'))
                executed = sum(int(s.get('tests', 0)) - int(s.get('skipped', 0)) for s in suites)
                errors = sum(int(s.get('failures', 0)) + int(s.get('errors', 0)) for s in suites)
                verified = executed > 0 and errors == 0
            except (OSError, ET.ParseError, ValueError):
                verified = False
        runs.append(TestRun(str(path.relative_to(root)), returncode, verified, log))
    return runs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', help='Exact test files, not directories')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--extra-pythonpath', action='append', default=[])
    parser.add_argument('--timeout', type=float, default=60)
    parser.add_argument('--log-dir', type=Path)
    args = parser.parse_args()
    try:
        if args.timeout <= 0:
            raise ValueError('--timeout debe ser positivo')
        root = args.root.resolve()
        env = runtime_env(root, args.extra_pythonpath)
        print('Runtime:', json.dumps(probe_runtime(root, env), ensure_ascii=False))
        log_dir = (args.log_dir or Path(tempfile.mkdtemp(prefix='qpansopy-qt6-tests-'))).resolve()
        runs = run_files(root, args.files, env, sys.executable, log_dir, args.timeout)
        for run in runs:
            status = 'PASS' if run.verified else 'NOT VERIFIED'
            print(f'{status} {run.file} (exit {run.returncode}); log: {run.log}')
        return int(any(not run.verified for run in runs))
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print(f'Error: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
