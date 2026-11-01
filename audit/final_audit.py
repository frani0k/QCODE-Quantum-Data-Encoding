"""Independent checks of scientific artifacts and local Git provenance."""
import hashlib
import re
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from qiskit.quantum_info import Statevector
from run_experiment import audit_results,audit_figures,read_rows,digest
from src.evaluation import load_json,save_json
from src.variational_classifier import circuit
from audit.write_report import build_report
ROOT=Path(__file__).resolve().parents[1]


def check():
    hypothesis='73994d8d863ad04dfb5d80a8ed004c5c67165b68'
    def git(*args):
        return subprocess.check_output(['git',*args],cwd=ROOT,encoding='utf-8').strip()
    assert git('rev-list','--max-parents=0','HEAD')==hypothesis
    subprocess.run(['git','merge-base','--is-ancestor',hypothesis,'HEAD'],cwd=ROOT,check=True)
    tree=git('ls-tree','-rl',hypothesis)
    assert 'results/' not in tree and 'figures/' not in tree
    original=git('show',hypothesis+':README.md')
    current=(ROOT/'README.md').read_text(encoding='utf-8')
    expected_prefix=original.split('## Struktura projektu')[0].replace(r'\operatorname{acc}',r'\mathrm{acc}')
    assert current.startswith(expected_prefix)
    assert current==build_report(expected_prefix)
    assert len(re.findall(r'(?m)^\$\$$',current))%2==0
    assert len(re.findall(r'(?m)^```',current))%2==0
    assert r'\operatorname' not in current and '\ufffd' not in current
    for target in re.findall(r'\]\(([^)]+)\)',current):
        if not target.startswith(('https://','http://')):
            assert (ROOT/target).exists(),target
    prerecord=load_json(ROOT/'audit/prerun.json')
    assert digest(ROOT/'experiment_protocol.json')==prerecord['protocol_sha256']
    for name,sha in prerecord['code_sha256'].items():
        assert digest(ROOT/name)==sha,name
    audit_results(ROOT/'results'); audit_figures(ROOT/'results',ROOT/'figures')
    assert load_json(ROOT/'results/reproduction.json')['passed']
    rows=read_rows(ROOT/'results'); histories=load_json(ROOT/'results/histories.json')
    for row in rows:
        with np.load(ROOT/'results'/f"dataset_seed_{row['seed']}.npz") as data:
            p=[Statevector.from_instruction(circuit(x,histories[f"{row['seed']}_{row['variant']}"]['theta'],row['variant'])).probabilities([0])[1] for x in data['X_test']]
            assert float(np.mean((np.array(p)>=0.5)==data['y_test']))==row['test_accuracy']
    ry=np.array([r['test_accuracy'] for r in rows if r['variant']=='RY'])
    zz=np.array([r['test_accuracy'] for r in rows if r['variant']=='ZZ'])
    assert round(100*ry.mean(),2)==97.10
    assert round(100*zz.mean(),2)==58.45
    assert round(100*(zz-ry).mean(),2)==-38.65
    old=['src/__init__.py','src/data.py','src/encodings.py','src/model.py','src/train.py','src/evaluate.py','tests/test_data.py','tests/test_encodings.py','tests/test_model.py']
    assert all((ROOT/p).stat().st_size==0 for p in old)
    for p in [ROOT/'README.md',*list((ROOT/'src').glob('*.py')),*list((ROOT/'audit').glob('*.py'))]:
        assert '\ufffd' not in p.read_text(encoding='utf-8')
    # Check textual deliverables for common credential formats, without printing matches.
    patterns=[r'gh[pousr]_[A-Za-z0-9]{30,}',r'github_pat_[A-Za-z0-9_]{30,}',r'-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----',r'AKIA[A-Z0-9]{16}']
    for folder in ['src','tests','audit','results','figures']:
        for p in (ROOT/folder).rglob('*'):
            if p.is_file() and p.suffix in ['.py','.json','.csv','.log','.txt']:
                text=p.read_text(encoding='utf-8')
                assert not any(re.search(pattern,text) for pattern in patterns),p
    report={'passed':True,'independent_qiskit_test_predictions':4000,'preregistration_preserved':True,'protocol_and_training_code_unchanged_since_prerun':True,'csv_json_readme_consistent':True,'figures_data_and_hashes_valid':True,'full_reproduction':True,'visual_figures_reviewed':5,'unverified':['GitHub rendering of new README (no publishing)','other platforms and Python versions','quantum hardware, finite shots and noise','additional ansatz depths'],'no_push_in_this_task':True}
    save_json(ROOT/'audit/final_checks.json',report)
    print('FINAL AUDIT PASS: all 4000 held-out predictions independently checked with Qiskit')


if __name__=='__main__':
    check()
