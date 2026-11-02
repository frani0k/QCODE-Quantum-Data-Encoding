"""Read-only checks of scientific claims and tables against recorded results."""
import csv
import json
import re
import subprocess
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESIS = '73994d8d863ad04dfb5d80a8ed004c5c67165b68'


def validate_readme(text=None):
    if text is None:
        text = (ROOT / 'README.md').read_text(encoding='utf-8')
    original = subprocess.check_output(['git', 'show', HYPOTHESIS + ':README.md'], cwd=ROOT).decode('utf-8')
    # Preserve the full preregistered question, hypothesis, plan and rejection rule.
    prefix = original.split('## Struktura projektu')[0].replace(r'\operatorname{acc}', r'\mathrm{acc}')
    assert text.startswith(prefix), 'Preregistered scientific content changed'
    assert '\ufffd' not in text and r'\operatorname' not in text
    assert len(re.findall(r'(?m)^\$\$$', text)) % 2 == 0
    assert len(re.findall(r'(?m)^```', text)) % 2 == 0
    for target in re.findall(r'\]\(([^)]+)\)', text):
        if not target.startswith(('http://', 'https://')):
            assert (ROOT / target).exists(), target
    lines = [[v.strip() for v in line.strip('|').split('|')] for line in text.splitlines() if line.startswith('|')]
    summaries = []
    for folder in (ROOT / 'results', ROOT / 'replications/rng_independent/results'):
        with (folder / 'metrics.csv').open(encoding='utf-8', newline='') as f:
            rows = list(csv.DictReader(f))
        summary = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        summaries.append(summary)
        assert len(rows) == 20
        for seed in range(10):
            ry = next(r for r in rows if int(r['seed']) == seed and r['variant'] == 'RY')
            zz = next(r for r in rows if int(r['seed']) == seed and r['variant'] == 'ZZ')
            expected = [str(seed)] + [f'{100*float(r[k]):.3f}' for r,k in [(ry,'train_accuracy'),(ry,'test_accuracy'),(zz,'train_accuracy'),(zz,'test_accuracy')]]
            candidates = [r for r in lines if len(r) == 6 and r[:5] == expected]
            delta = 100 * (float(zz['test_accuracy']) - float(ry['test_accuracy']))
            assert any(abs(float(r[5]) - delta) < 1e-10 for r in candidates), (folder, seed)
        for variant in ('RY', 'ZZ'):
            values = np.array([float(r['test_accuracy']) for r in rows if r['variant'] == variant])
            np.testing.assert_allclose(values.mean(), summary[variant]['test_mean'], atol=1e-15)
            np.testing.assert_allclose(values.std(ddof=1), summary[variant]['test_std'], atol=1e-15)
            expected = f"{100*values.mean():.2f} ± {100*values.std(ddof=1):.2f}"
            assert expected in text, expected
        assert f"{summary['delta_pp']:.2f} pp" in text
    def accuracy_cell(summary, variant):
        values = summary[variant]
        return f"{100*values['test_mean']:.2f} ± {100*values['test_std']:.2f}"
    assert ['Test accuracy (%): średnia ± SD'] + [accuracy_cell(summaries[0], v) for v in ('RY', 'ZZ')] in lines
    for variant in ('RY', 'ZZ'):
        change = 100 * (summaries[1][variant]['test_mean'] - summaries[0][variant]['test_mean'])
        assert [variant, accuracy_cell(summaries[0], variant), accuracy_cell(summaries[1], variant), f'{change:+.2f}'] in lines
    assert 'POST-HOC REPLICATION' in text
    assert 'Nie sprawdzono tego eksperymentalnie' in text
    assert 'nie uzasadniają ogólnej wyższości RY' in text
    assert 'wizualnie' in text
    return True
