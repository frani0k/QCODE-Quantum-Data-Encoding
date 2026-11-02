"""POST-HOC REPLICATION: three reproducible, separately spawned RNG roles.

The legacy dataset module is intentionally unchanged for historical reproduction.
"""
import numpy as np
from .dataset import labels
from .encoding import scale_features

ROLES = ('data', 'split', 'initialization')


def spawn_streams(seed):
    children = np.random.SeedSequence(seed).spawn(len(ROLES))
    return {role: np.random.default_rng(child) for role, child in zip(ROLES, children)}


def from_streams(streams):
    raw = streams['data'].uniform(-1, 1, (1000, 2))
    y = labels(raw)
    groups = [streams['split'].permutation(np.flatnonzero(y == c)) for c in (0, 1)]
    quotas = np.array([len(g) * 0.2 for g in groups])
    counts = np.floor(quotas).astype(int)
    order = np.argsort(-(quotas - counts), kind='stable')
    counts[order[:200 - counts.sum()]] += 1
    test = streams['split'].permutation(np.concatenate([g[:n] for g, n in zip(groups, counts)]))
    train = streams['split'].permutation(np.concatenate([g[n:] for g, n in zip(groups, counts)]))
    data = {'raw': raw, 'train_idx': train, 'test_idx': test,
            'X_train': scale_features(raw[train]), 'X_test': scale_features(raw[test]),
            'y_train': y[train], 'y_test': y[test]}
    initial = streams['initialization'].uniform(-0.1, 0.1, 4)
    return data, initial


def make_pair(seed):
    return from_streams(spawn_streams(seed))
