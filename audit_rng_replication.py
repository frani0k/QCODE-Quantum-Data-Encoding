"""POST-HOC REPLICATION: figures, descriptive comparison, and audit.

Read-only result verification and optional generation of missing figures.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path
import numpy as np
from run_rng_replication import BASE, STUDY, ROOT, read_rows, original_unchanged, audit_results
from run_experiment import digest
from src.evaluation import load_json, save_json
from audit.provenance import verify_original_provenance, verify_prerun
from audit.readme import validate_readme

ORIGINAL_COMMIT = '9584308c16d6bae49561f2865bcdb90a978b5da1'


def comparison():
    old=load_json(ROOT/'results/summary.json'); new=load_json(BASE/'results/summary.json')
    return {'study':STUDY,'comparison':'Descriptive across studies, not paired causal changes',
            'variants':{v:{'original_test_mean':old[v]['test_mean'],'replication_test_mean':new[v]['test_mean'],
            'original_test_std':old[v]['test_std'],'replication_test_std':new[v]['test_std'],
            'change_pp':100*(new[v]['test_mean']-old[v]['test_mean'])} for v in ('RY','ZZ')},
            'original_delta_pp':old['delta_pp'],'replication_delta_pp':new['delta_pp'],
            'RY_wins_all_replication_pairs':all(d<0 for d in new['paired_delta_pp'])}


def plot_data():
    rows=read_rows(BASE/'results'); s=load_json(BASE/'results/summary.json'); h=load_json(BASE/'results/histories.json')
    return {'study':STUDY,'comparison':comparison(),'seeds':s['seeds'],
        'test_accuracy_percent':{v:[100*next(r for r in rows if r['seed']==seed and r['variant']==v)['test_accuracy'] for seed in s['seeds']] for v in ('RY','ZZ')},
        'loss':{v:[h[f'{seed}_{v}']['history'] for seed in s['seeds']] for v in ('RY','ZZ')},
        'paired_delta_pp':s['paired_delta_pp'],
        'resources':load_json(BASE/'results/resources.json'),
        'training_seconds':{v:[next(r for r in rows if r['seed']==seed and r['variant']==v)['training_seconds'] for seed in s['seeds']] for v in ('RY','ZZ')}}


def figures(refresh=False):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    folder=BASE/'figures'
    if folder.exists() and any(folder.iterdir()) and not refresh:
        raise ValueError('Replication figures already exist; refusing overwrite')
    folder.mkdir(parents=True,exist_ok=True)
    d=plot_data(); save_json(folder/'plot_data.json',d)
    def finish(fig,name):
        if len(fig.axes) == 1:
            fig.axes[0].set_title(STUDY, fontsize=13, pad=12)
        else:
            fig.suptitle(STUDY, fontsize=13)
        fig.tight_layout(); fig.savefig(folder/name,dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.5))
    for j,v in enumerate(('RY','ZZ')):
        c=d['comparison']['variants'][v]
        ax.errorbar(j-.13,100*c['original_test_mean'],yerr=100*c['original_test_std'],fmt='o',capsize=5,color='gray',label='Original mean +/- SD' if j==0 else None)
        ax.errorbar(j+.13,100*c['replication_test_mean'],yerr=100*c['replication_test_std'],fmt='s',capsize=5,color='tab:blue',label='Replication mean +/- SD' if j==0 else None)
        ax.scatter(np.full(10,j+.13),d['test_accuracy_percent'][v],alpha=.35,color='tab:blue')
    ax.set(xticks=[0,1],xticklabels=['RY','ZZ'],ylabel='Test accuracy (%)',ylim=(0,100)); ax.legend(loc='lower left')
    finish(fig,'test_accuracy_comparison.png')
    fig,ax=plt.subplots(figsize=(8,4.5))
    for v in ('RY','ZZ'):
        a=np.array(d['loss'][v]); line,=ax.plot(a.mean(axis=0),label=v)
        ax.fill_between(np.arange(a.shape[1]),a.mean(axis=0)-a.std(axis=0,ddof=1),a.mean(axis=0)+a.std(axis=0,ddof=1),color=line.get_color(),alpha=.2)
    ax.set(xlabel='Adam updates',ylabel='Train BCE (mean +/- SD)',ylim=(0,None)); ax.legend()
    finish(fig,'train_loss.png')
    fig,ax=plt.subplots(figsize=(8,4.5))
    ax.bar(d['seeds'],d['paired_delta_pp']); ax.axhline(0,color='black'); ax.axhline(5,color='red',linestyle='--',label='Original prediction: +5 pp')
    ax.set(xlabel='Seed',ylabel='ZZ - RY test accuracy (pp)',xticks=d['seeds']); ax.legend()
    finish(fig,'paired_differences.png')
    fig,axes=plt.subplots(1,2,figsize=(8,4.5))
    for ax,key,label in zip(axes,['depth','two_qubit_gates'],['Circuit depth','Two-qubit gates (CX)']):
        ax.bar(['RY','ZZ'],[d['resources'][v][key] for v in ('RY','ZZ')]); ax.set(ylabel=label,ylim=(0,None))
    finish(fig,'circuit_resources.png')
    fig,ax=plt.subplots(figsize=(8,4.5))
    for j,v in enumerate(('RY','ZZ')):
        a=d['training_seconds'][v]; ax.scatter(np.full(10,j),a,alpha=.5)
        ax.errorbar(j,np.mean(a),yerr=np.std(a,ddof=1),fmt='ks',capsize=5)
    ax.set(xticks=[0,1],xticklabels=['RY','ZZ'],ylabel='Training time (s)',ylim=(0,None))
    finish(fig,'training_time.png')
    save_json(folder/'manifest.json',{'study':STUDY,'sha256':{p.name:digest(p) for p in folder.glob('*.png')}})


def check():
    import matplotlib.image as mpimg
    original_unchanged()
    for name,sha in load_json(BASE/'prerun.json')['sha256'].items(): assert digest(ROOT/name)==sha,name
    audit_results(BASE/'results',full_qiskit=True)
    assert load_json(BASE/'reproduction.json')['passed']
    assert load_json(BASE/'comparison.json')==comparison()
    assert load_json(BASE/'figures/plot_data.json')==plot_data()
    manifest=load_json(BASE/'figures/manifest.json')
    assert manifest['study']==STUDY and len(manifest['sha256'])==5
    for name,sha in manifest['sha256'].items():
        assert digest(BASE/'figures'/name)==sha
        pixels=mpimg.imread(BASE/'figures'/name)
        assert pixels.shape[0]>=400 and pixels.shape[1]>=800 and np.isfinite(pixels).all()
    verify_original_provenance()
    verify_prerun()
    validate_readme()
    subprocess.run(['git','merge-base','--is-ancestor',ORIGINAL_COMMIT,'HEAD'],cwd=ROOT,check=True)
    print(STUDY+': FINAL AUDIT PASS; original files unchanged; 4000 test predictions checked')


def main():
    parser=argparse.ArgumentParser(description=STUDY)
    parser.add_argument('--check',action='store_true')
    parser.add_argument('--plots',action='store_true',help='Generate missing figures; never overwrite recorded figures')
    args=parser.parse_args()
    if args.plots: figures()
    else: check()


if __name__=='__main__': main()
