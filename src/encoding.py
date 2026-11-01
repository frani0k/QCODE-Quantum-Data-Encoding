"""Preregistered two-feature encodings; input angles are already scaled."""
import numpy as np
from qiskit import QuantumCircuit


def scale_features(raw):
    raw = np.asarray(raw, dtype=float)
    if not np.isfinite(raw).all() or np.any(abs(raw) > 1):
        raise ValueError("Raw features must be finite and in [-1, 1]")
    return (raw + 1) * np.pi / 2


def encoding_circuit(x, variant):
    x = np.asarray(x, dtype=float)
    if x.shape != (2,) or not np.isfinite(x).all():
        raise ValueError("Expected two finite angles")
    qc = QuantumCircuit(2)
    if variant == "RY":
        qc.ry(x[0], 0)
        qc.ry(x[1], 1)
    elif variant == "ZZ":
        qc.h([0, 1])
        qc.rz(-2 * x[0], 0)
        qc.rz(-2 * x[1], 1)
        qc.rzz(-2 * (np.pi - x[0]) * (np.pi - x[1]), 0, 1)
    else:
        raise ValueError("variant must be RY or ZZ")
    return qc
