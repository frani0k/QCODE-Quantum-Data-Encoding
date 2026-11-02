"""POST-HOC REPLICATION: figures, descriptive comparison, and audit.

Only README and the separate replication directory may be written.
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

HEADER = '## Audyt metodologiczny i replikacja post hoc'
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


def section():
    c=comparison(); s=load_json(BASE/'results/summary.json')
    table='| Encoding | Oryginał: test mean ± SD (%) | POST-HOC REPLICATION: test mean ± SD (%) | Zmiana średniej (pp) |\n| --- | ---: | ---: | ---: |\n'
    for v in ('RY','ZZ'):
        a=c['variants'][v]
        table+=f"| {v} | {100*a['original_test_mean']:.2f} ± {100*a['original_test_std']:.2f} | {100*a['replication_test_mean']:.2f} ± {100*a['replication_test_std']:.2f} | {a['change_pp']:+.2f} |\n"
    rows=read_rows(BASE/'results')
    seeds='| Seed | RY train (%) | RY test (%) | ZZ train (%) | ZZ test (%) | ZZ - RY (pp) |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
    for seed in s['seeds']:
        a=next(r for r in rows if r['seed']==seed and r['variant']=='RY'); b=next(r for r in rows if r['seed']==seed and r['variant']=='ZZ')
        seeds+=f"| {seed} | {100*a['train_accuracy']:.3f} | {100*a['test_accuracy']:.3f} | {100*b['train_accuracy']:.3f} | {100*b['test_accuracy']:.3f} | {100*(b['test_accuracy']-a['test_accuracy']):+.2f} |\n"
    conclusion=('RY wygrywa we wszystkich 10 parach; kierunek przewagi pozostaje stabilny.' if c['RY_wins_all_replication_pairs'] else 'Nie wszystkie pary zachowują przewagę RY; stabilność należy ocenić z tabeli.')
    text=r'''
## Audyt metodologiczny i replikacja post hoc

**POST-HOC REPLICATION — kontrola metodologiczna z 2026-11-02.** To osobne badanie po poznaniu wyników, a nie nowa prerejestracja ani zastąpienie pierwszego eksperymentu. Oryginalna hipoteza, protocol, wyniki i commit `9584308c16d6bae49561f2865bcdb90a978b5da1` pozostają zachowane. Ich niezmienność jest kontrolowana bajtowo przez [manifest oryginałów](replications/rng_independent/original_manifest.json).

### Wada i jej matematyczna weryfikacja

Osobne wywołania `default_rng(seed)` nie dają niezależnych strumieni: rozpoczynają tę samą sekwencję. Dla tych samych pierwszych liczb jednostajnych u dane wynosiły `r=2*u-1`, a inicjalizacja `theta=0.2*u-0.1`. Zatem:

$$
\theta_{\mathrm{init}}=\frac{1}{10}(r_{0,0},r_{0,1},r_{1,0},r_{1,1}).
$$

Relację potwierdzono dla wszystkich seedów 0-9 z błędem poniżej 2e-17. Pierwsze dwie obserwacje nie zawsze były treningowe: próbka 1 trafiała na test przy seedzie 2, a próbka 0 przy seedach 5, 7 i 9. To pośrednia zależność inicjalizacji od cech testowych, choć kod nie odczytywał jawnie testowych etykiet w treningu. Także generator podziału ponownie startował z tego samego seeda.

### Naprawa i niezmienione warunki

Nowy moduł `src/replication_rng.py` tworzy dokładnie trzy dzieci `SeedSequence(seed).spawn(3)`, w ustalonej kolejności: data (spawn_key 0), split (1), initialization (2). Każde dziecko inicjalizuje osobny `default_rng` z PCG64. Zużycie jednego strumienia nie przesuwa pozostałych. Daje to zalecaną przez NumPy separację strumieni pseudolosowych z bardzo wysokim prawdopodobieństwem; skończone testy nie są dowodem absolutnej niezależności statystycznej. Dokumentacja: [NumPy SeedSequence spawning](https://numpy.org/doc/stable/reference/random/parallel.html), sprawdzona 2026-11-02, zainstalowane NumPy 2.5.4.

Każda para RY/ZZ otrzymuje ten sam dataset i podział oraz kopie tej samej inicjalizacji. Pozostają 2 kubity, 1000 obserwacji, 800/200 train/test, XOR, skalowanie, stratyfikacja, obie definicje encodingów, dwie warstwy ansatzu, Z0, BCE, Adam 0.05 i 100 kroków oraz seedy 0-9. Kod modelu i treningu jest używany bez zmian. Oryginalna ścieżka RNG pozostaje zamrożona wyłącznie do historycznego odtworzenia; replikację uruchamia osobny skrypt.

Plan replikacji zapisano przed pełnym uruchomieniem w [osobnym protokole](replications/rng_independent/protocol.json); hashe kodu i protokołu zapisano w [prerun.json](replications/rng_independent/prerun.json). Nie dobierano seedów ani ustawień po wynikach. Wszystkie nowe artefakty są w `replications/rng_independent/`, a wiersze CSV, konfiguracje, historie i wykresy mają oznaczenie POST-HOC REPLICATION.

### Wyniki kontrolne

@@TABLE@@
@@SEEDS@@

Średnia sparowana różnica ZZ minus RY w replikacji wynosi **@@DELTA@@ pp**, SD różnicy **@@DELTA_SD@@ pp**, wobec **-38.65 pp** w oryginale. @@CONCLUSION@@ Przewidywanie +5 pp dla ZZ @@PREDICTION@@ w tej kontroli; ta ocena post hoc nie zmienia historycznego wyniku hipotezy.

Źródła: [CSV](replications/rng_independent/results/metrics.csv), [summary JSON](replications/rng_independent/results/summary.json), [historie i hashe par](replications/rng_independent/results/histories.json), [porównanie badań](replications/rng_independent/comparison.json).

### Nieaktywny parametr i interpretacja

Nie zmieniono architektury. Dla C=CX(0,1) i końcowego obrotu RY na kubicie 1 zachodzi:

$$
C^{\dagger} Z_0 C=Z_0,\qquad [R_{Y,1}(\theta_3),Z_0]=0.
$$

Dlatego odczyt i loss są niezależne od theta3; jego gradient jest analitycznie zerowy. Modele nadal mają cztery nominalne parametry, ale co najwyżej trzy aktywne w predykcji. To własność odczytu, nie dowód barren plateau. Usunięcie parametru zmieniłoby prerejestrowaną architekturę i nie jest częścią tej kontroli.

Replikacja ocenia stabilność wyniku po rozdzieleniu RNG. Zmienia realizacje danych, podziałów i inicjalizacji jednocześnie; różnic między badaniami nie można przypisać wyłącznie usunięciu sprzężenia inicjalizacji. Ten sam numer seeda nie oznacza tej samej próbki między badaniami. Nie stosujemy więc interpretacji sparowanego efektu przyczynowego między oryginałem a kontrolą.

Nadal nie rozdzielono ograniczeń reprezentacji ZZ, odczytu i optymalizacji. Mały ansatz, jeden generator XOR, brak szumu i jeden budżet nie uzasadniają ogólnej wyższości RY. SD obejmuje zmienność danych, podziałów i inicjalizacji; nie jest samą zmiennością inicjalizacji. Wynik nie dowodzi mechanizmu przyczynowego ani przewagi kwantowej.

### Wykresy i walidacja

Wszystkie nowe wykresy mają nagłówek POST-HOC REPLICATION. Accuracy ma skalę 0-100%, zasoby i czasy zaczynają się od zera. Źródła serii i hashe PNG są zapisane obok wykresów.

![POST-HOC REPLICATION: accuracy](replications/rng_independent/figures/test_accuracy_comparison.png)

![POST-HOC REPLICATION: loss](replications/rng_independent/figures/train_loss.png)

![POST-HOC REPLICATION: różnice](replications/rng_independent/figures/paired_differences.png)

![POST-HOC REPLICATION: zasoby](replications/rng_independent/figures/circuit_resources.png)

![POST-HOC REPLICATION: czas](replications/rng_independent/figures/training_time.png)

Testy regresyjne sprawdzają odtwarzalność, przypisanie dzieci SeedSequence, separację zużycia strumieni, zerwanie dawnego sprzężenia, wspólne dane/podział/inicjalizację par oraz zachowanie oryginalnych plików i odtwarzanie dawnych datasetów. Pełne odtworzenie replikacji porównuje parametry, historie, dane i metryki; wyłącza niedeterministyczny czas. Audyt porównuje zapisane predykcje z Qiskit i sprawdza zgodność CSV, JSON, README oraz danych wykresów.

```powershell
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe -B run_rng_replication.py --audit
.\.venv\Scripts\python.exe -B run_rng_replication.py --reproduce .venv/posthoc-reproduction-check
.\.venv\Scripts\python.exe -B audit_rng_replication.py --check
```

Pierwsze uruchomienie nowej replikacji, wyłącznie gdy osobny katalog wyników jeszcze nie istnieje: `python run_rng_replication.py`. Program odmawia nadpisania wcześniejszych pomiarów. Nie uruchamiaj ponownie starego generatora raportu `audit/write_report.py` do aktualizacji tego dodatku — dotyczy on wyłącznie pierwszego badania. Żadna kontrola nie wymaga nadpisywania oryginalnych wyników.

Testów niezależności RNG nie należy interpretować jako matematycznego dowodu niezależności wszystkich strumieni. Nie sprawdzono innego środowiska, alternatywnego ansatzu ani renderowania tej lokalnej sekcji na GitHubie. **Nie wykonano push.**
'''
    return text.replace('@@TABLE@@',table).replace('@@SEEDS@@',seeds).replace('@@DELTA@@',f"{s['delta_pp']:.2f}").replace('@@DELTA_SD@@',f"{s['delta_std_pp']:.2f}").replace('@@CONCLUSION@@',conclusion).replace('@@PREDICTION@@','zostało spełnione' if s['prediction_met'] else 'nie zostało spełnione')


def generate():
    original_unchanged()
    save_json(BASE/'comparison.json',comparison())
    figures()
    readme=ROOT/'README.md'
    original=subprocess.check_output(['git','show',ORIGINAL_COMMIT+':README.md'],cwd=ROOT).decode('utf-8')
    assert readme.read_text(encoding='utf-8')==original
    readme.write_text(original+section(),encoding='utf-8')


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
    original=subprocess.check_output(['git','show',ORIGINAL_COMMIT+':README.md'],cwd=ROOT).decode('utf-8')
    readme=(ROOT/'README.md').read_text(encoding='utf-8')
    assert readme==original+section()
    assert len(re.findall(r'(?m)^\$\$$',readme))%2==0
    assert len(re.findall(r'(?m)^```',readme))%2==0
    for target in re.findall(r'\]\(([^)]+)\)',readme):
        if not target.startswith(('http://','https://')): assert (ROOT/target).exists(),target
    subprocess.run(['git','merge-base','--is-ancestor',ORIGINAL_COMMIT,'HEAD'],cwd=ROOT,check=True)
    print(STUDY+': FINAL AUDIT PASS; original files unchanged; 4000 test predictions checked')


def main():
    parser=argparse.ArgumentParser(description=STUDY)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    if args.check: check()
    else: generate()


if __name__=='__main__': main()
