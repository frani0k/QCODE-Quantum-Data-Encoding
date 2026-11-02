"""Regression tests for POST-HOC REPLICATION; original experiment stays frozen."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pytest
from src.replication_rng import spawn_streams, make_pair, from_streams
from src.dataset import make_dataset
from run_rng_replication import run, audit_results

ROOT=Path(__file__).resolve().parents[1]


def test_original_rng_coupling_is_reproduced_not_erased():
    for seed in range(10):
        data=make_dataset(seed)
        initial=np.random.default_rng(seed).uniform(-0.1,0.1,4)
        np.testing.assert_allclose(initial,data['raw'][:2].reshape(-1)/10,atol=2e-17,rtol=0)


def test_spawn_roles_match_independent_child_sequences():
    streams=spawn_streams(7)
    assert set(streams)=={'data','split','initialization'}
    children=np.random.SeedSequence(7).spawn(3)
    values=[]
    for role,child in zip(['data','split','initialization'],children):
        a=streams[role].random(10)
        np.testing.assert_array_equal(a,np.random.default_rng(child).random(10))
        values.append(a)
    assert all(not np.array_equal(values[i],values[j]) for i in range(3) for j in range(i))


def test_consuming_one_stream_does_not_advance_others():
    a,b=spawn_streams(2),spawn_streams(2)
    a['data'].random(5000)
    for role in ['split','initialization']:
        np.testing.assert_array_equal(a[role].random(100),b[role].random(100))


def test_pair_reproducible_without_legacy_coupling():
    for seed in range(10):
        a,ia=make_pair(seed); b,ib=make_pair(seed)
        for k in a: np.testing.assert_array_equal(a[k],b[k])
        np.testing.assert_array_equal(ia,ib)
        assert not np.allclose(ia,a['raw'][:2].reshape(-1)/10)
        assert len(a['train_idx'])==800 and len(a['test_idx'])==200
        assert not set(a['train_idx'])&set(a['test_idx'])
        np.testing.assert_array_equal(a['y_test'],(a['raw'][a['test_idx'],0]*a['raw'][a['test_idx'],1]<0).astype(int))


def test_data_consumption_does_not_change_initialization():
    streams=spawn_streams(9)
    streams['data'].random(4000)
    _,initial=from_streams(streams)
    _,expected=make_pair(9)
    np.testing.assert_array_equal(initial,expected)


def test_original_artifacts_and_code_unchanged():
    manifest=json.loads((ROOT/'replications/rng_independent/original_manifest.json').read_text())
    for name,sha in manifest['files'].items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    for seed in range(10):
        regenerated=make_dataset(seed)
        with np.load(ROOT/f'results/dataset_seed_{seed}.npz') as saved:
            for key in regenerated: np.testing.assert_array_equal(regenerated[key],saved[key])


def test_small_replication_is_paired_and_reproducible(tmp_path):
    a,b=tmp_path/'a',tmp_path/'b'
    run(a,seeds=[0],steps=2,validation_only=True)
    run(b,seeds=[0],steps=2,validation_only=True)
    for path in [a,b]: assert audit_results(path)
    ha=json.loads((a/'histories.json').read_text()); hb=json.loads((b/'histories.json').read_text())
    for variant in ['RY','ZZ']:
        for field in ['initial','theta','history','dataset_sha256','split_sha256']:
            assert ha['0_'+variant][field]==hb['0_'+variant][field]
    for field in ['initial','dataset_sha256','split_sha256']:
        assert ha['0_RY'][field]==ha['0_ZZ'][field]
    cfg=json.loads((a/'configuration.json').read_text())
    assert cfg['study']=='POST-HOC REPLICATION' and cfg['validation_only']
    with pytest.raises(ValueError): run(a,seeds=[0],steps=2,validation_only=True)
