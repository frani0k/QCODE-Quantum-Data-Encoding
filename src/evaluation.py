"""Paired descriptive statistics, resource accounting and strict JSON I/O."""
import json
from pathlib import Path
import numpy as np
from qiskit import transpile
from .variational_classifier import circuit, predict


def accuracy(y, p):
    return float(np.mean(predict(p) == y))


def summarize(rows):
    grouped = {}
    for row in rows:
        group = grouped.setdefault(int(row["seed"]), {})
        if row["variant"] in group:
            raise ValueError("Duplicate paired result")
        group[row["variant"]] = row
    if not grouped or any(set(g) != {"RY", "ZZ"} for g in grouped.values()):
        raise ValueError("Incomplete paired results")
    seeds = sorted(grouped)
    result = {"seeds": seeds}
    for variant in ("RY", "ZZ"):
        a = np.array([grouped[s][variant]["test_accuracy"] for s in seeds])
        result[variant] = {"test_mean": float(a.mean()), "test_std": float(a.std(ddof=1)) if len(a)>1 else None}
    delta = np.array([100 * (grouped[s]["ZZ"]["test_accuracy"] - grouped[s]["RY"]["test_accuracy"]) for s in seeds])
    result.update(delta_pp=float(delta.mean()), delta_std_pp=float(delta.std(ddof=1)) if len(delta)>1 else None,
                  paired_delta_pp=delta.tolist(), prediction_met=bool(delta.mean() >= 5))
    return result


def resources(variant):
    qc = circuit([0.3, 0.7], None, variant)
    basic = transpile(qc, basis_gates=["ry", "rz", "h", "cx"], optimization_level=0, seed_transpiler=0)
    return {"depth": basic.depth(), "two_qubit_gates": sum(i.operation.num_qubits == 2 for i in basic.data),
            "gate_counts": dict(basic.count_ops()), "trainable_parameters": qc.num_parameters}


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))
