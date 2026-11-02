"""POST-HOC REPLICATION: RNG repair only; immutable legacy experiment."""
import argparse
import csv
import hashlib
from pathlib import Path
import numpy as np
from qiskit.quantum_info import Statevector
from run_experiment import ROOT, digest, environment
from src.replication_rng import make_pair
from src.training import train, loss_gradient
from src.variational_classifier import circuit, encoded_states, probabilities
from src.evaluation import accuracy, summarize, resources, save_json, load_json

STUDY = 'POST-HOC REPLICATION'
BASE = ROOT / 'replications' / 'rng_independent'


def original_unchanged():
    manifest = load_json(BASE / 'original_manifest.json')
    for name, sha in manifest['files'].items():
        if digest(ROOT / name) != sha:
            raise AssertionError(f'Protected original changed: {name}')
    return True


def array_hash(*arrays):
    h = hashlib.sha256()
    for a in arrays:
        a = np.ascontiguousarray(a)
        h.update(str(a.shape).encode())
        h.update(a.dtype.str.encode())
        h.update(a.tobytes())
    return h.hexdigest()


def read_rows(output):
    with (Path(output) / 'metrics.csv').open(encoding='utf-8', newline='') as f:
        return [{k: int(v) if k == 'seed' else v if k in ('variant', 'study') else float(v)
                 for k, v in row.items()} for row in csv.DictReader(f)]


def run(output, seeds=None, steps=None, validation_only=False):
    original_unchanged()
    output = Path(output).resolve()
    if output == (ROOT / 'results').resolve() or (ROOT / 'results').resolve() in output.parents:
        raise ValueError('Original results are protected')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Output must be empty; no overwriting')
    if not validation_only and (seeds is not None or steps is not None):
        raise ValueError('Cannot override production seeds or training budget')
    protocol = load_json(BASE / 'protocol.json')
    seeds = protocol['seeds'] if seeds is None else seeds
    steps = protocol['base_protocol']['training']['steps'] if steps is None else steps
    output.mkdir(parents=True, exist_ok=True)
    save_json(output / 'configuration.json', {'study': STUDY, 'protocol': protocol,
              'protocol_sha256': digest(BASE / 'protocol.json'), 'validation_only': validation_only,
              'actual_seeds': seeds, 'actual_steps': steps})
    save_json(output / 'environment.json', {'study': STUDY, **environment()})
    rows, histories = [], {}
    for seed in seeds:
        data, initial = make_pair(seed)
        np.savez_compressed(output / f'dataset_seed_{seed}.npz', **data)
        dataset_sha = array_hash(data['raw'])
        split_sha = array_hash(data['train_idx'], data['test_idx'])
        for variant in ('RY', 'ZZ'):
            trained = train(data['X_train'], data['y_train'], variant, initial.copy(), steps)
            row = {'study': STUDY, 'seed': seed, 'variant': variant}
            for split in ('train', 'test'):
                p = probabilities(encoded_states(data[f'X_{split}'], variant), trained['theta'])
                row[f'{split}_accuracy'] = accuracy(data[f'y_{split}'], p)
            row.update(training_seconds=trained['training_seconds'], final_loss=trained['history'][-1])
            rows.append(row)
            histories[f'{seed}_{variant}'] = {'study': STUDY, 'initial': initial.tolist(),
                'dataset_sha256': dataset_sha, 'split_sha256': split_sha, **trained}
            print(f"{STUDY}: seed={seed} {variant} train={row['train_accuracy']:.4f} test={row['test_accuracy']:.4f}", flush=True)
    with (output / 'metrics.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary = summarize(rows)
    summary['study'] = STUDY
    for variant in ('RY', 'ZZ'):
        group = [r for r in rows if r['variant'] == variant]
        for metric in ('train_accuracy', 'training_seconds', 'final_loss'):
            a = np.array([r[metric] for r in group])
            summary[variant][metric + '_mean'] = float(a.mean())
            summary[variant][metric + '_std'] = float(a.std(ddof=1)) if len(a) > 1 else None
        summary[variant]['generalization_gap_mean'] = float(np.mean([r['train_accuracy'] - r['test_accuracy'] for r in group]))
    save_json(output / 'histories.json', histories)
    save_json(output / 'summary.json', summary)
    save_json(output / 'resources.json', {'study': STUDY, **{v: resources(v) for v in ('RY', 'ZZ')}})
    audit_results(output)
    original_unchanged()
    return rows, summary


def audit_results(output, full_qiskit=False):
    output = Path(output)
    original_unchanged()
    cfg = load_json(output / 'configuration.json')
    assert cfg['study'] == STUDY
    assert cfg['protocol_sha256'] == digest(BASE / 'protocol.json')
    assert cfg['protocol'] == load_json(BASE / 'protocol.json')
    if not cfg['validation_only']:
        assert cfg['actual_seeds'] == list(range(10)) and cfg['actual_steps'] == 100
    rows = read_rows(output)
    assert len(rows) == 2 * len(cfg['actual_seeds'])
    assert all(r['study'] == STUDY for r in rows)
    assert sorted({r['seed'] for r in rows}) == cfg['actual_seeds']
    summary = load_json(output / 'summary.json')
    recomputed = summarize(rows)
    for key in ('seeds', 'paired_delta_pp', 'delta_pp', 'delta_std_pp', 'prediction_met'):
        assert summary[key] == recomputed[key]
    for variant in ('RY', 'ZZ'):
        for key in ('test_mean', 'test_std'):
            assert summary[variant][key] == recomputed[variant][key]
        group = [r for r in rows if r['variant'] == variant]
        for metric in ('train_accuracy', 'training_seconds', 'final_loss'):
            a = np.array([r[metric] for r in group])
            assert summary[variant][metric + '_mean'] == float(a.mean())
            assert summary[variant][metric + '_std'] == (float(a.std(ddof=1)) if len(a)>1 else None)
        assert load_json(output / 'resources.json')[variant] == resources(variant)
    histories = load_json(output / 'histories.json')
    for seed in cfg['actual_seeds']:
        data, initial = make_pair(seed)
        with np.load(output / f'dataset_seed_{seed}.npz') as stored:
            for k in data: np.testing.assert_array_equal(data[k], stored[k])
        assert not set(data['train_idx']) & set(data['test_idx'])
        assert len(data['train_idx']) == 800 and len(data['test_idx']) == 200
        for variant in ('RY', 'ZZ'):
            h = histories[f'{seed}_{variant}']
            np.testing.assert_array_equal(h['initial'], initial)
            assert h['study'] == STUDY
            assert h['dataset_sha256'] == array_hash(data['raw'])
            assert h['split_sha256'] == array_hash(data['train_idx'], data['test_idx'])
            assert len(h['history']) == cfg['actual_steps'] + 1
            assert np.isfinite(h['history']).all()
            final_loss = loss_gradient(encoded_states(data['X_train'], variant), data['y_train'], np.array(h['theta']))[0]
            np.testing.assert_allclose(final_loss, h['history'][-1], atol=1e-14)
            row = next(r for r in rows if r['seed'] == seed and r['variant'] == variant)
            assert row['final_loss'] == h['history'][-1]
            assert row['training_seconds'] == h['training_seconds']
            for split in ('train', 'test'):
                p = probabilities(encoded_states(data[f'X_{split}'], variant), h['theta'])
                assert accuracy(data[f'y_{split}'], p) == row[f'{split}_accuracy']
                x = data[f'X_{split}'] if full_qiskit and split == 'test' else data[f'X_{split}'][:3]
                oracle = [Statevector.from_instruction(circuit(r, h['theta'], variant)).probabilities([0])[1] for r in x]
                np.testing.assert_allclose(p[:len(x)], oracle, atol=1e-13)
    return True


def reproduce(output, destination):
    run(destination)
    a, b = read_rows(output), read_rows(destination)
    for ra, rb in zip(a, b):
        for key in ra:
            if key != 'training_seconds': assert ra[key] == rb[key]
    ha, hb = load_json(Path(output) / 'histories.json'), load_json(Path(destination) / 'histories.json')
    for key in ha:
        for field in ('initial', 'theta', 'history', 'dataset_sha256', 'split_sha256'):
            assert ha[key][field] == hb[key][field]
    save_json(BASE / 'reproduction.json', {'study': STUDY, 'passed': True, 'models': len(a),
              'excluded': 'wall-clock training_seconds', 'compared': ['parameters', 'histories', 'metrics', 'data and split hashes']})


def main():
    parser = argparse.ArgumentParser(description=STUDY)
    parser.add_argument('--audit', action='store_true')
    parser.add_argument('--reproduce', type=Path)
    args = parser.parse_args()
    if args.audit:
        audit_results(BASE / 'results', full_qiskit=True)
        print(STUDY + ': AUDIT PASS')
    elif args.reproduce:
        reproduce(BASE / 'results', args.reproduce)
        print(STUDY + ': REPRODUCTION PASS')
    else:
        run(BASE / 'results')
        print(STUDY + ': EXPERIMENT PASS')


if __name__ == '__main__':
    main()
