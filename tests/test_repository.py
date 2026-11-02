"""Repository-level checks of scientific provenance and public documentation."""
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_readme_has_no_obsolete_publication_claims():
    text=(ROOT/'README.md').read_text(encoding='utf-8')
    for phrase in ['Nie wykonano push','Wszystkie nowe zmiany i wyniki pozostają lokalnie','ponieważ zmian nie publikowano','PREPUBLICATION_AUDIT','verification/prepublication']:
        assert phrase not in text
    assert 'https://github.com/frani0k/QCODE-Quantum-Data-Encoding' in text
    assert 'wizualnie' in text and 'post hoc' in text


def test_unused_legacy_skeletons_are_absent():
    for name in ['src/data.py','src/encodings.py','src/model.py','src/train.py','src/evaluate.py','tests/test_data.py','tests/test_encodings.py','tests/test_model.py']:
        assert not (ROOT/name).exists()
    assert (ROOT/'src/__init__.py').exists()


def test_archived_and_current_provenance_are_both_verified():
    from audit.provenance import verify_original_provenance, verify_prerun
    assert verify_original_provenance()
    assert verify_prerun()


def test_publication_readme_is_validated_from_actual_data():
    from audit.readme import validate_readme
    assert validate_readme()


def test_readme_validator_rejects_changed_accuracy():
    from audit.readme import validate_readme
    original=(ROOT/'README.md').read_text(encoding='utf-8')
    with pytest.raises(AssertionError):
        validate_readme(original.replace('97.10 ± 1.70','99.99 ± 1.70',1))


def test_readme_validator_rejects_changed_hypothesis():
    from audit.readme import validate_readme
    original=(ROOT/'README.md').read_text(encoding='utf-8')
    with pytest.raises(AssertionError):
        validate_readme(original.replace('co najmniej 5 punktów procentowych','co najmniej 1 punkt procentowy',1))


def test_provenance_rejects_tampered_archive_digest():
    import json
    from audit.provenance import verify_archived
    manifest=json.loads((ROOT/'replications/rng_independent/original_manifest.json').read_text())
    name=next(iter(manifest['archived_files']))
    with pytest.raises(AssertionError):
        verify_archived({name:'0'*64},manifest['original_results_commit'])
