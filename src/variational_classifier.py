"""Qiskit circuit and equivalent batched exact statevector evolution."""
import numpy as np
from qiskit.circuit import ParameterVector
from qiskit.quantum_info import Statevector
from .encoding import encoding_circuit


def circuit(x, theta, variant):
    qc = encoding_circuit(x, variant)
    if theta is None:
        theta = ParameterVector("theta", 4)
    if len(theta) != 4:
        raise ValueError("Expected four trainable parameters")
    for layer in range(2):
        qc.ry(theta[2 * layer], 0)
        qc.ry(theta[2 * layer + 1], 1)
        qc.cx(0, 1)
    return qc


def encoded_states(x, variant):
    return np.array([Statevector.from_instruction(encoding_circuit(row, variant)).data for row in x])


def probabilities(states, theta):
    theta = np.asarray(theta, dtype=float)
    if theta.shape != (4,):
        raise ValueError("Expected four trainable parameters")
    s = np.array(states, dtype=complex, copy=True)
    # Basis order: |q1 q0>. Each RY acts on pairs differing in its bit.
    for layer in range(2):
        for qubit in range(2):
            c, sn = np.cos(theta[2 * layer + qubit] / 2), np.sin(theta[2 * layer + qubit] / 2)
            low = np.array([i for i in range(4) if not i & (1 << qubit)])
            high = low + (1 << qubit)
            a, b = s[:, low].copy(), s[:, high].copy()
            s[:, low], s[:, high] = c * a - sn * b, sn * a + c * b
        s = s[:, [0, 3, 2, 1]]  # CX(0,1)
    return np.sum(abs(s[:, [1, 3]]) ** 2, axis=1)


def predict(p):
    return (np.asarray(p) >= 0.5).astype(int)
