"""Build the report from saved measurements; preserve preregistered sections."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from run_experiment import read_rows
from src.evaluation import load_json
ROOT=Path(__file__).resolve().parents[1]


def build_report(prefix):
    rows=read_rows(ROOT/'results'); s=load_json(ROOT/'results/summary.json')
    table='| Seed | RY train (%) | RY test (%) | ZZ train (%) | ZZ test (%) | ZZ - RY (pp) |\n| --- | ---: | ---: | ---: | ---: | ---: |\n'
    for seed in s['seeds']:
        ry=next(r for r in rows if r['seed']==seed and r['variant']=='RY')
        zz=next(r for r in rows if r['seed']==seed and r['variant']=='ZZ')
        table+=f"| {seed} | {100*ry['train_accuracy']:.3f} | {100*ry['test_accuracy']:.3f} | {100*zz['train_accuracy']:.3f} | {100*zz['test_accuracy']:.3f} | {100*(zz['test_accuracy']-ry['test_accuracy']):.2f} |\n"
    aggregate='| Miara | RY | ZZ |\n| --- | ---: | ---: |\n'
    for label,key,scale,digits in [('Test accuracy (%)','test',100,2),('Train accuracy (%)','train_accuracy',100,3),('Końcowa train BCE','final_loss',1,4),('Czas treningu (s)','training_seconds',1,3)]:
        vals=[f"{scale*s[v][key+'_mean']:.{digits}f} ± {scale*s[v][key+'_std']:.{digits}f}" for v in ['RY','ZZ']]
        aggregate+=f"| {label}: średnia ± SD | {vals[0]} | {vals[1]} |\n"
    aggregate+='| Głębokość obwodu | 5 | 9 |\n| Bramki dwukubitowe CX | 2 | 4 |\n| Parametry trenowalne (nominalnie) | 4 | 4 |\n'
    circuits=''
    for v in ['RY','ZZ']:
        circuits+=f"\n### {v}\n\nPrzykładowe kąty wejściowe: 0.3 i 0.7 rad.\n\n```text\n{(ROOT/f'results/circuit_{v}.txt').read_text(encoding='utf-8')}\n```\n"
    text=r'''## Implementacja i zamrożony protokół

Eksperyment wykonano lokalnie 2026-11-02 po prerejestracji. Commit hipotezy: `73994d8d863ad04dfb5d80a8ed004c5c67165b68`. W tym commicie znajdowały się README i puste pliki, bez wyników. Powyższa hipoteza, plan i kryterium obalenia zachowują pierwotną treść.

Pełny protokół: [experiment_protocol.json](experiment_protocol.json). Hash protokołu i kodu sprzed uruchomienia: [audit/prerun.json](audit/prerun.json). Kopia konfiguracji i hash przy wynikach: [results/configuration.json](results/configuration.json). Nie zmieniano protokołu po obejrzeniu wyników.

Użyto Python 3.14.0, Qiskit 2.6.1, NumPy 2.5.4, Matplotlib 3.11.2 i pytest 9.2.0. W requirements.txt przypięto też zależności pośrednie (m.in. SciPy wykorzystywane przez Qiskit). Pełne środowisko: [results/environment.json](results/environment.json).

Dla każdego seeda generuje się 1000 punktów o dwóch niezależnych cechach Uniform[-1,1). Etykieta to `int(x0*x1 < 0)`, bez szumu. Skalowanie `(x+1)*pi/2` korzysta ze znanych granic, bez dopasowywania na teście. Stratyfikacja przydziela klasom zaokrąglone w dół kwoty testowe, a pozostałe miejsca według największej części ułamkowej, z remisem na rzecz klasy 0. Jest dokładnie 800 obserwacji treningowych i 200 testowych. Dane, indeksy oraz etykiety zapisano w `results/dataset_seed_*.npz`.

Generowanie, podział i inicjalizacja używają niezależnych instancji `default_rng(seed)`. W parze RY/ZZ dane, podział i cztery parametry początkowe są identyczne. Nie wybiera się najlepszego seeda ani najlepszego kroku.

### Konwencje bramek i trening

Cecha j trafia na kubit j. Kolejność bazy Qiskit to `|q1 q0>`; tensorowy zapis RY w prerejestracji oznacza lokalne przypisanie cech, a w porządku macierzy Qiskit operator kubitu 1 stoi po lewej. Stan początkowy to `|00>`. Macierz RY:

$$
R_Y(a)=\begin{pmatrix}\cos(a/2)&-\sin(a/2)\\\sin(a/2)&\cos(a/2)\end{pmatrix}.
$$

Konwencja Qiskit:

$$
R_Z(a)=e^{-iaZ/2},\qquad R_{ZZ}(a)=e^{-ia(Z\otimes Z)/2}.
$$

Dlatego dodatnie wykładniki z prerejestracji realizuje `rz(-2*x[j], j)` oraz `rzz(-2*(pi-x[0])*(pi-x[1]),0,1)` po H na obu kubitach. Nie użyto gotowej mapy o potencjalnie innej konwencji.

Ansatz ma dwie warstwy RY na obu kubitach i CX(0,1). Obserwabla to `IZ`, czyli Z0. Prawdopodobieństwo klasy 1 wynosi `(1-<IZ>)/2`, a próg to `>=0.5`. Accuracy jest odsetkiem poprawnych predykcji.

Qiskit `Statevector.from_instruction` tworzy stany po encodingu. NumPy wykonuje identyczne macierze RY i permutacje CX na całym batchu. Zgodność z pełnym obwodem Qiskit sprawdzono testami oraz w audycie wytrenowanych modeli. Symulacja jest dokładna complex128, bez szumu i shots; nie korzysta ze sprzętu kwantowego.

Adam wykonuje 100 pełnych kroków: learning rate 0.05, beta1=0.9, beta2=0.999, epsilon=1e-8, z korekcją obciążenia momentów. Funkcja straty to średnia binarna entropia krzyżowa z clippingiem do [1e-12,1-1e-12]. Parameter shift daje pochodne prawdopodobieństw, a reguła łańcuchowa gradient straty. Pochodna clippingu jest zerowa poza tym przedziałem. Historia obejmuje stratę początkową i po każdym kroku (101 wartości). Test ocenia parametry po setnym kroku.

Zasoby mierzy się w bazie `ry,rz,h,cx`, z optimization_level=0 i seed_transpiler=0, przy symbolicznych parametrach ansatzu. To koszt określonej dekompozycji, nie zoptymalizowany koszt sprzętowy. Czas `perf_counter` obejmuje przygotowanie stanów treningowych, optymalizację i historię, bez importów, ewaluacji i wykresów. Kolejność jest szeregowa: RY, potem ZZ w każdym seedzie. Czasy są opisowe i zależne od obciążenia komputera.

### Reprezentacje obwodów

@@CIRCUITS@@
## Wyniki 10 powtórzeń

Accuracy podano w procentach, różnice w punktach procentowych. SD oznacza odchylenie standardowe próby (`ddof=1`). Każdy seed zmienia zbiór, podział i inicjalizację: zmienności nie można przypisać wyłącznie inicjalizacji.

@@TABLE@@
@@AGGREGATE@@
Średnia sparowana różnica ZZ minus RY wynosi **-38.65 pp**, SD różnicy **3.32 pp**. ZZ przegrywa we wszystkich 10 parach; różnice wynoszą od -45.50 do -35.00 pp.

**Przewidywanie zostało obalone w tym eksperymencie:** średnia różnica jest mniejsza niż wymagane +5 pp. To kryterium opisowe z prerejestracji, bez testu istotności i bez twierdzenia o wszystkich zadaniach kwantowego uczenia maszynowego.

Źródła: [CSV](results/metrics.csv), [podsumowanie JSON](results/summary.json), [parametry i historie](results/histories.json), [zasoby](results/resources.json).

## Wykresy

Punkty pokazują powtórzenia, kwadraty średnie, a kreski i pasma SD. Accuracy ma skalę 0-100%; słupki czasu i zasobów zaczynają się od zera. Dla różnic zaznaczono zero i próg hipotezy.

![Test accuracy](figures/test_accuracy.png)

![Train loss](figures/train_loss.png)

![Sparowane różnice](figures/paired_differences.png)

![Głębokość i CX](figures/circuit_resources.png)

![Czas treningu](figures/training_time.png)

Dane wykresów: [figures/plot_data.json](figures/plot_data.json). Hashe PNG: [figures/manifest.json](figures/manifest.json). Audyt porównuje serie z CSV i historiami oraz sprawdza pliki PNG i hashe. Wszystkie pięć wykresów obejrzano wizualnie lokalnie.

## Obserwacje, interpretacja i ograniczenia

**Obserwacje:** RY ma wyższą accuracy dla każdego seeda i niższą końcową stratę. ZZ ma większą zmienność test accuracy. Średnia luka train minus test to 0.5875 pp dla RY i 1.1250 pp dla ZZ. Nie widać dużego overfittingu mierzonego tą luką, ale nie jest to dowód jego całkowitego braku. Niska accuracy ZZ już na treningu sugeruje ograniczenie dopasowania lub optymalizacji; nie rozdzielono tych przyczyn.

ZZ ma 4 zamiast 2 CX i głębokość 9 zamiast 5. Jego średni czas treningu był większy o 24.0%. Nie jest to uniwersalny benchmark ani czas wykonania na sprzęcie kwantowym.

**Interpretacja analityczna:** interakcja w ZZ nie gwarantuje dopasowania do granicy klas. RY z tym ansatzem już może reprezentować XOR. Parametry `(pi/2, pi/2, -pi/2, dowolny)` dają:

$$
\langle Z_0\rangle=\cos(x_0)\cos(x_1).
$$

Po skalowaniu znak tego iloczynu odtwarza regułę etykiet poza granicą o zerowym prawdopodobieństwie w ciągłym generatorze. To wniosek matematyczny, sprawdzony testem, nie dodatkowe dostrajanie. Fazy ZZ są okresowe i mogą gorzej pasować do tej granicy przy ograniczonym ansatzu i odczycie; porównanie accuracy nie dowodzi jednak tej przyczyny. Nie izolowano wpływu splątania od osi obrotów i innych różnic map.

Ostatni obrót kubitu 1 nie wpływa na Z0: działa na innym kubicie, a końcowy CX(0,1) komutuje z Z0. Oba modele mają cztery nominalne parametry, ale jeden jest obojętny dla predykcji. Zachowano tę strukturę zgodnie z prerejestracją.

Ograniczenia: jeden generator danych, dwa kubity, jedna warstwa kodowania i dwie warstwy ansatzu. Nie badano innych skalowań, obserwabli, optimizerów, budżetów, szumu ani skończonych shots. Nie wykazano przewagi kwantowej nad klasycznym modelem. Wynik obala przewidywaną przewagę ZZ w tej konfiguracji, nie sam fakt obecności interakcji w reprezentacji.

## Co by się zmieniło, gdybyśmy zwiększyli liczbę warstw ansatzu?

**Nie sprawdzono tego eksperymentalnie.** Każda warstwa dodaje dwa nominalne parametry i jeden CX, może powiększyć rodzinę funkcji i umożliwić lepsze wykorzystanie faz ZZ. Przy zerowych nowych obrotach odczyt poprzedniego modelu pozostaje osiągalny, bo dodatkowy końcowy CX nie zmienia Z0. Nie oznacza to, że Adam znajdzie lepsze rozwiązanie przy tym samym budżecie.

RY już dobrze pasuje do tego XOR, więc jego możliwy zysk accuracy ogranicza sufit 100%. ZZ ma większy margines poprawy, ale nie wiadomo, czy dodatkowe warstwy wystarczą. Wzrasta koszt i może wzrosnąć trudność optymalizacji oraz ryzyko overfittingu. Zaniki gradientów w głębszych i większych obwodach są możliwe, ale nie wykazano ich tutaj. Ostatni obrót kubitu 1 nadal byłby niewidoczny dla odczytu. Porównanie głębokości wymaga osobnego protokołu ustalonego przed wynikami.

## Instalacja i uruchomienie

Polecenia PowerShell uruchamiaj w katalogu projektu. Referencyjne środowisko: Python 3.14.0 na Windows. Innych platform i wersji Pythona nie przetestowano.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONUTF8 = '1'
.\.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
.\.venv\Scripts\python.exe run_experiment.py --audit
.\.venv\Scripts\python.exe run_experiment.py --reproduce .venv/reproduction-check
```

Odtwarzanie wymaga nowej, pustej ścieżki wyjściowej. Wykonuje wszystkie 20 treningów, porównuje dokładnie parametry, historie i metryki, z wyjątkiem niedeterministycznego czasu ściennego. Potwierdzenie zapisuje do `results/reproduction.json`. Pierwsze uruchomienie w kopii z pustym results:

```powershell
.\.venv\Scripts\python.exe run_experiment.py
```

Program odmawia nadpisywania wyników. Nie usuwaj zapisanych pomiarów do kontroli odtwarzalności; użyj `--reproduce`.

## Struktura po implementacji

```text
quantum-data-encoding/
├── README.md
├── requirements.txt
├── .gitignore
├── experiment_protocol.json
├── run_experiment.py
├── src/
│   ├── encoding.py
│   ├── dataset.py
│   ├── variational_classifier.py
│   ├── training.py
│   ├── evaluation.py
│   └── __init__.py, data.py, encodings.py, model.py, train.py, evaluate.py
├── tests/
│   ├── test_qcode.py
│   └── test_data.py, test_encodings.py, test_model.py
├── audit/
├── results/
├── figures/
└── data/
```

Stare pliki szkieletu i `__init__.py` pozostają puste. Nowe moduły realizują nazwy wymagane przez zadanie. Data pozostaje pusty, dane odtwarzalne są przy wynikach. `.venv`, cache i pyc są ignorowane przez Git.

## Testy, audyt i źródła

Przeszło 20 testów: analityczne RY i ZZ, zależność członu ZZ od cech, normalizacja, zerowa interakcja, generowanie etykiet, podział bez przecieku, pomiar i klasyfikacja, liczba parametrów, batch kontra Qiskit, gradienty, odtwarzalność treningu, punkty procentowe, zapis/odczyt i przepływ wyników. Dodatkowe kontrole opisują obojętny parametr i reprezentację XOR. Testy nie są dowodem hipotezy.

Pełne odtworzenie 20 modeli sprawdza parametry, historie i metryki; czasu nie porównuje na równość. Dzienniki są w audit. Audyt obejmuje zachowanie prerejestracji i hash protokołu, kod, CSV/JSON/README, źródła wykresów, PNG i historię Git.

LaTeX używa bloków `$$` i standardowych makr, bez problematycznego `operatorname`. Nie sprawdzono renderowania nowego README na GitHubie, ponieważ zmian nie publikowano.

Dokumentacja IBM sprawdzona 2026-11-02: [RZZGate](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.circuit.library.RZZGate), [Statevector](https://quantum.cloud.ibm.com/docs/en/api/qiskit/qiskit.quantum_info.Statevector). Krótszy adres Statevector w metadanych zamrożonego protokołu jest niedostępny; poprawny podano tutaj bez zmiany protokołu. API zweryfikowano też testami z Qiskit 2.6.1.

**Wszystkie nowe zmiany i wyniki pozostają lokalnie. W tym zadaniu nie wykonano push ani żadnej zmiany zdalnego repozytorium.**
'''
    return '\n'.join(line.rstrip() for line in (prefix+text.replace('@@CIRCUITS@@',circuits).replace('@@TABLE@@',table).replace('@@AGGREGATE@@',aggregate)).splitlines())+'\n'


if __name__=='__main__':
    p=ROOT/'README.md'
    prefix=p.read_text(encoding='utf-8').split('## Struktura projektu')[0].split('## Implementacja i zamrożony protokół')[0]
    p.write_text(build_report(prefix),encoding='utf-8')
