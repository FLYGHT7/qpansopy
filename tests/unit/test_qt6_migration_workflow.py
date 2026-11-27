"""Safety and navigation checks for the resumable Qt6 migration tooling."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


SCRIPTS = (Path(__file__).resolve().parents[2] / '.agents' / 'skills'
           / 'qpansopy-qt6-migration' / 'scripts')


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def context_tool():
    return _load('context')


@pytest.fixture
def runner():
    return _load('run_qgis_tests')


@pytest.fixture
def project(tmp_path):
    package = tmp_path / 'Q_Pansopy'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / 'helper.py').write_text('VALUE = 1\n')
    (package / 'dock.py').write_text(
        'from .helper import VALUE\n'
        'from qgis.PyQt.QtCore import QVariant as Variant\n'
        'from .qt_compat import Qt_AlignTop\n'
        'field_type = Variant.String\n')
    (package / 'dock.ui').write_text('<ui/>')
    plan = tmp_path / 'plans' / 'qt6-only'
    plan.mkdir(parents=True)
    rows = [
        dict(id='00', slug='workflow', title='Workflow', status='pending',
             branch='refactor/qt6-00-workflow', parent_branch='origin/main',
             depends_on=[], source_files=['Q_Pansopy/__init__.py',
                                         'Q_Pansopy/helper.py'],
             support_files=[], unit_tests=[], runtime_tests=[], evidence=[]),
        dict(id='01', slug='dock', title='Dock', status='pending',
             branch='refactor/qt6-01-dock',
             parent_branch='refactor/qt6-00-workflow', depends_on=['00'],
             source_files=['Q_Pansopy/dock.py', 'Q_Pansopy/dock.ui'],
             support_files=[], unit_tests=[], runtime_tests=[], evidence=[]),
    ]
    ledger = dict(schema_version=1, batches=rows)
    (plan / 'batches.json').write_text(json.dumps(ledger))
    return tmp_path, ledger


def test_inventory_detects_unassigned_missing_and_duplicate_files(context_tool,
                                                                project):
    root, ledger = project
    assert context_tool.inventory(root, ledger)['unassigned'] == []
    (root / 'Q_Pansopy/new.py').write_text('')
    ledger['batches'][1]['source_files'] += ['Q_Pansopy/helper.py',
                                           'Q_Pansopy/missing.py']
    report = context_tool.inventory(root, ledger)
    assert report['unassigned'] == ['Q_Pansopy/new.py']
    assert report['missing'] == ['Q_Pansopy/missing.py']
    assert report['duplicates'] == ['Q_Pansopy/helper.py']


def test_next_batch_resumes_blocked_work_instead_of_skipping(context_tool,
                                                          project):
    _, ledger = project
    ledger['batches'][0]['status'] = 'blocked'
    assert context_tool.choose_batch(ledger, 'next')['id'] == '00'
    with pytest.raises(ValueError, match='depend'):
        context_tool.choose_batch(ledger, '01')


@pytest.mark.parametrize('bad_path', ['../secret.py', '/etc/passwd'])
def test_ledger_rejects_paths_outside_project(context_tool, project, bad_path):
    root, ledger = project
    ledger['batches'][0]['source_files'] = [bad_path]
    (root / 'plans/qt6-only/batches.json').write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match='ruta'):
        context_tool.load_ledger(root)


def test_ledger_rejects_duplicate_ids_and_unknown_dependencies(context_tool,
                                                             project):
    root, ledger = project
    path = root / 'plans/qt6-only/batches.json'
    ledger['batches'][1]['id'] = '00'
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match='identificador'):
        context_tool.load_ledger(root)
    ledger['batches'][1]['id'] = '01'
    ledger['batches'][1]['depends_on'] = ['99']
    path.write_text(json.dumps(ledger))
    with pytest.raises(ValueError, match='depend'):
        context_tool.load_ledger(root)


def test_context_uses_source_imports_without_graphify(context_tool, project):
    root, ledger = project
    report = context_tool.build_context(root, ledger, ledger['batches'][1])
    assert 'Q_Pansopy/helper.py' in report['imports']['outgoing']
    assert report['graph']['warnings']
    findings = report['findings']
    assert any(f['kind'] == 'legacy_field_type' for f in findings)
    assert any(f['kind'] == 'shim_import' for f in findings)


def test_graph_neighborhood_reports_stale_data_and_never_invents_direction(
        context_tool, project):
    root, ledger = project
    graph = root / 'graphify-out'
    graph.mkdir()
    (graph / 'graph.json').write_text(json.dumps(dict(
        directed=False,
        nodes=[dict(id='dock', label='Dock', source_file='dock.py'),
               dict(id='helper', label='Helper', source_file='helper.py')],
        links=[dict(source='helper', target='dock', relation='uses')],
    )))
    (graph / 'manifest.json').write_text(json.dumps({
        'dock.py': {'ast_hash': 'old'}, 'helper.py': {'ast_hash': 'old'},
    }))
    report = context_tool.build_context(root, ledger, ledger['batches'][1])
    assert report['graph']['stale'] == ['Q_Pansopy/dock.py']
    assert report['graph']['neighbors'][0]['source_file'] == 'Q_Pansopy/helper.py'
    assert report['graph']['directed'] is False
    assert any('direcci' in w for w in report['graph']['warnings'])


def test_corrupt_graph_falls_back_to_current_source(context_tool, project):
    root, ledger = project
    graph = root / 'graphify-out'
    graph.mkdir()
    (graph / 'graph.json').write_text('{broken')
    report = context_tool.build_context(root, ledger, ledger['batches'][1])
    assert 'Q_Pansopy/helper.py' in report['imports']['outgoing']
    assert report['graph']['warnings']


def test_finished_batch_requires_a_commit_reachable_from_head(context_tool,
                                                            project):
    root, ledger = project
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test',
                    '-c', 'user.email=test@example.invalid', 'commit',
                    '--allow-empty', '-qm', 'Initial'], check=True)
    ledger['batches'][0]['status'] = 'done'
    with pytest.raises(ValueError, match='commit'):
        context_tool.verify_history(root, ledger)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test',
                    '-c', 'user.email=test@example.invalid', 'commit',
                    '--allow-empty', '-qm', 'Workflow\n\nQt6-Batch: 00'],
                   check=True)
    context_tool.verify_history(root, ledger)


def test_context_cli_is_bounded_and_returns_nonzero_for_incomplete_inventory(
        project):
    root, _ = project
    command = [sys.executable, str(SCRIPTS / 'context.py'), '--root', str(root)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.split()) <= 1500
    (root / 'Q_Pansopy/forgotten.py').write_text('')
    result = subprocess.run(command + ['--audit', '--json'],
                            capture_output=True, text=True)
    assert result.returncode != 0
    assert 'Q_Pansopy/forgotten.py' in result.stdout


@pytest.fixture
def fake_pytest(tmp_path):
    """A child process simulates pytest without loading Qt in this test suite."""
    root = tmp_path / 'runtime-project'
    (root / 'tests').mkdir(parents=True)
    (root / 'tests/pytest.ini').write_text('[pytest]\n')
    for name in ('pass', 'fail', 'skip'):
        (root / f'tests/test_{name}.py').write_text('')
    package = root / 'pytest'
    package.mkdir()
    (package / '__init__.py').write_text('')
    (package / '__main__.py').write_text(
        'import os, sys\n'
        'from pathlib import Path\n'
        'path = next(a.split("=", 1)[1] for a in sys.argv '
        'if a.startswith("--junitxml="))\n'
        'skip = "skip" in sys.argv[-1]\n'
        'fail = "fail" in sys.argv[-1]\n'
        'Path(path).write_text(f\'<testsuites><testsuite tests="1" '
        'skipped="{int(skip)}" failures="{int(fail)}" errors="0"/>'
        '</testsuites>\')\n'
        'print("pid", os.getpid())\n'
        'print("1 failed" if fail else "1 skipped" if skip else "1 passed")\n'
        'sys.exit(int(fail))\n')
    env = dict(os.environ, PYTHONPATH=str(root))
    return root, env


def test_runtime_runner_isolates_files_and_keeps_failures_visible(runner,
                                                               fake_pytest):
    root, env = fake_pytest
    files = ['tests/test_fail.py', 'tests/test_pass.py']
    runs = runner.run_files(root, files, env, sys.executable, root / 'logs', 10)
    assert [r.returncode for r in runs] == [1, 0]
    assert not runs[0].verified and runs[1].verified
    logs = [r.log.read_text() for r in runs]
    assert logs[0].splitlines()[0] != logs[1].splitlines()[0]


def test_runtime_runner_never_treats_all_skipped_as_verified(runner, fake_pytest):
    root, env = fake_pytest
    run = runner.run_files(root, ['tests/test_skip.py'], env,
                           sys.executable, root / 'logs', 10)[0]
    assert run.returncode == 0
    assert not run.verified


def test_runtime_runner_rejects_directories_and_outside_files(runner,
                                                           fake_pytest):
    root, env = fake_pytest
    for path in ['tests', '../outside.py']:
        with pytest.raises(ValueError, match='archivo'):
            runner.run_files(root, [path], env, sys.executable, root / 'logs', 10)


def test_runtime_runner_does_not_reuse_a_previous_success_report(runner,
                                                               fake_pytest):
    root, env = fake_pytest
    log_dir = root / 'logs'
    log_dir.mkdir()
    (log_dir / '00-test_pass.xml').write_text(
        '<testsuites><testsuite tests="1" skipped="0"/></testsuites>')
    (root / 'pytest/__main__.py').write_text('print("No report produced")\n')
    run = runner.run_files(root, ['tests/test_pass.py'], env,
                           sys.executable, log_dir, 10)[0]
    assert run.returncode == 0
    assert not run.verified


def test_runtime_runner_records_timeout(runner, fake_pytest):
    root, env = fake_pytest
    (root / 'pytest/__main__.py').write_text('import time\ntime.sleep(10)\n')
    run = runner.run_files(root, ['tests/test_pass.py'], env,
                           sys.executable, root / 'logs', 0.1)[0]
    assert run.returncode == 124
    assert not run.verified
    assert 'TIMEOUT' in run.log.read_text()


def test_real_catalog_assigns_every_python_and_ui_once(context_tool):
    root = SCRIPTS.parents[3]
    ledger = context_tool.load_ledger(root)
    report = context_tool.inventory(root, ledger)
    assert not report['unassigned']
    assert not report['duplicates']
    assert not report['missing']
