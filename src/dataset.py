"""Independent RNG streams and a stratified, disjoint 800/200 split."""
import numpy as np
from .encoding import scale_features


def labels(raw):
    raw = np.asarray(raw)
    return (raw[:, 0] * raw[:, 1] < 0).astype(int)


def make_dataset(seed):
    raw = np.random.default_rng(seed).uniform(-1, 1, (1000, 2))
    y = labels(raw)
    rng = np.random.default_rng(seed)
    groups = [rng.permutation(np.flatnonzero(y == c)) for c in (0, 1)]
    quotas = np.array([len(g) * 0.2 for g in groups])
    counts = np.floor(quotas).astype(int)
    order = np.argsort(-(quotas - counts), kind="stable")
    counts[order[:200 - counts.sum()]] += 1
    test = rng.permutation(np.concatenate([g[:n] for g, n in zip(groups, counts)]))
    train = rng.permutation(np.concatenate([g[n:] for g, n in zip(groups, counts)]))
    return {"raw": raw, "train_idx": train, "test_idx": test,
            "X_train": scale_features(raw[train]), "X_test": scale_features(raw[test]),
            "y_train": y[train], "y_test": y[test]}
