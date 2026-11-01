"""Full-batch Adam with exact parameter-shift probability derivatives."""
from time import perf_counter
import numpy as np
from .variational_classifier import encoded_states, probabilities


def loss_gradient(states, y, theta):
    p = probabilities(states, theta)
    clipped = np.clip(p, 1e-12, 1 - 1e-12)
    loss = -np.mean(y * np.log(clipped) + (1 - y) * np.log1p(-clipped))
    factor = (clipped - y) / (clipped * (1 - clipped))
    factor = np.where((p > 1e-12) & (p < 1 - 1e-12), factor, 0)
    gradient = np.empty(4)
    for j in range(4):
        shift = np.zeros(4)
        shift[j] = np.pi / 2
        derivative = (probabilities(states, theta + shift) - probabilities(states, theta - shift)) / 2
        gradient[j] = np.mean(factor * derivative)
    return float(loss), gradient


def train(x, y, variant, initial, steps=100):
    start = perf_counter()
    states = encoded_states(x, variant)
    theta = np.array(initial, dtype=float, copy=True)
    m, v = np.zeros(4), np.zeros(4)
    history = [loss_gradient(states, y, theta)[0]]
    for t in range(1, steps + 1):
        _, g = loss_gradient(states, y, theta)
        m = 0.9 * m + 0.1 * g
        v = 0.999 * v + 0.001 * g * g
        theta -= 0.05 * (m / (1 - 0.9 ** t)) / (np.sqrt(v / (1 - 0.999 ** t)) + 1e-8)
        history.append(loss_gradient(states, y, theta)[0])
    return {"theta": theta.tolist(), "history": history, "training_seconds": perf_counter() - start}
