"""Read-only audit of the preregistered experiment and its Git provenance."""
import subprocess
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
from qiskit.quantum_info import Statevector
from run_experiment import audit_results, audit_figures, read_rows
from src.evaluation import load_json
from src.variational_classifier import circuit
from audit.provenance import verify_original_provenance, verify_prerun
from audit.readme import validate_readme

ROOT = Path(__file__).resolve().parents[1]


def check():
    hypothesis = '73994d8d863ad04dfb5d80a8ed004c5c67165b68'
    assert subprocess.check_output(['git', 'rev-list', '--max-parents=0', 'HEAD'], cwd=ROOT, text=True).strip() == hypothesis
    tree = subprocess.check_output(['git', 'ls-tree', '-rl', hypothesis], cwd=ROOT, text=True)
    assert 'results/' not in tree and 'figures/' not in tree
    verify_original_provenance()
    verify_prerun()
    validate_readme()
    audit_results(ROOT / 'results')
    audit_figures(ROOT / 'results', ROOT / 'figures')
    assert load_json(ROOT / 'results/reproduction.json')['passed']
    rows = read_rows(ROOT / 'results')
    histories = load_json(ROOT / 'results/histories.json')
    for row in rows:
        with np.load(ROOT / 'results' / f"dataset_seed_{row['seed']}.npz") as data:
            probabilities = [Statevector.from_instruction(circuit(x, histories[f"{row['seed']}_{row['variant']}"]['theta'], row['variant'])).probabilities([0])[1] for x in data['X_test']]
            assert float(np.mean((np.array(probabilities) >= 0.5) == data['y_test'])) == row['test_accuracy']
    print('ORIGINAL EXPERIMENT AUDIT PASS: provenance, recorded data, README, figures and 4000 Qiskit predictions')
    return True


if __name__ == '__main__':
    check()
