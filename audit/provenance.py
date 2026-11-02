"""Verify current research artifacts and immutable archived Git objects.

Historical hashes were recorded on Windows. Git normalizes text line endings,
so archived text is checked in both its Git and CRLF working-tree forms.
"""
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = '9584308c16d6bae49561f2865bcdb90a978b5da1'


def normalized_path(name):
    name = name.replace('\\', '/')
    path = PurePosixPath(name)
    assert not path.is_absolute() and '..' not in path.parts
    return path.as_posix()


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_archived(entries, revision):
    subprocess.run(['git', 'merge-base', '--is-ancestor', revision, 'HEAD'], cwd=ROOT, check=True)
    for name, expected in entries.items():
        name = normalized_path(name)
        content = subprocess.check_output(['git', 'show', f'{revision}:{name}'], cwd=ROOT)
        candidates = {sha256(content)}
        if b'\x00' not in content:
            candidates.add(sha256(content.replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')))
        assert expected in candidates, f'Archived provenance mismatch: {name}'
    return True


def verify_original_provenance():
    manifest = json.loads((ROOT / 'replications/rng_independent/original_manifest.json').read_text(encoding='utf-8'))
    files = {normalized_path(k): v for k, v in manifest['files'].items()}
    required = {'experiment_protocol.json', 'run_experiment.py', 'requirements.txt',
                'audit/prerun.json', 'src/__init__.py', 'src/dataset.py', 'src/encoding.py',
                'src/evaluation.py', 'src/training.py', 'src/variational_classifier.py'}
    historical = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', ORIGINAL], cwd=ROOT, text=True).splitlines()
    required.update(p for p in historical if p.startswith(('results/', 'figures/')))
    assert set(files) == required, 'Research manifest coverage changed'
    for name, expected in files.items():
        assert sha256((ROOT / name).read_bytes()) == expected, name
    verify_archived(manifest['archived_files'], manifest['original_results_commit'])
    return True


def verify_prerun():
    record = json.loads((ROOT / 'audit/prerun.json').read_text(encoding='utf-8'))
    assert sha256((ROOT / 'experiment_protocol.json').read_bytes()) == record['protocol_sha256']
    removed = {'src/data.py', 'src/encodings.py', 'src/model.py', 'src/train.py', 'src/evaluate.py'}
    archived = {}
    for name, expected in record['code_sha256'].items():
        name = normalized_path(name)
        if name in removed:
            assert not (ROOT / name).exists()
            archived[name] = expected
        else:
            assert sha256((ROOT / name).read_bytes()) == expected, name
    verify_archived(archived, ORIGINAL)
    return True
