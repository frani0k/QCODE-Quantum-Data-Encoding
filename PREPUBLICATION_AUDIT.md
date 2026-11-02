# QCODE — końcowy audyt przed publikacją

Status: **READY — do przeglądu właściciela i ręcznej publikacji**, z ograniczeniami opisanymi poniżej. Data audytu: 2026-11-02 (Europe/Warsaw).

Audytowany HEAD: `b0a93e128ae65ed21e9e570674a42edd848df33c`. Ten raport i nowe dowody w `verification/prepublication/` są dodatkiem do historii; nie zmieniają wyników badań ani ich protokołów. Nie wykonano push i nie utworzono PR.

## Historia i pochodzenie wyników

Rzeczywiście odczytano daty autora i committera oraz rodziców commitów. Sprawdzono relację przodek–potomek i zawartość commitów.

| Commit | Autor — data i czas | Committer — data i czas | Zawartość |
| --- | --- | --- | --- |
| `73994d8d863ad04dfb5d80a8ed004c5c67165b68` | 2026-11-01 15:35:46 +01:00 | 2026-11-01 15:35:46 +01:00 | Hipoteza w README, puste pliki szkieletu; brak zapisanych wyników w drzewie commita |
| `9584308c16d6bae49561f2865bcdb90a978b5da1` | 2026-11-02 00:37:04 +01:00 | 2026-11-02 00:37:04 +01:00 | Implementacja i wyniki pierwszego badania |
| `b0a93e128ae65ed21e9e570674a42edd848df33c` | 2026-11-02 16:29:33 +01:00 | 2026-11-02 16:29:33 +01:00 | Oddzielna replikacja RNG i dodatek metodologiczny |

Pomiędzy hipotezą a implementacją znajduje się oczekiwany commit `4fcc280a6fada281537dd93146e455944dddf57d` (`math_rendering-fix`), z datami autora i committera 2026-11-01 15:53:43 +01:00. Modyfikuje wyłącznie zapis makra w README. Kolejność dat i topologia są zgodne. Nie znaleziono niezamierzonych zmian w porównanych zakresach commitów.

Git potwierdza zapis hipotezy przed zatwierdzonymi wynikami. Daty Git są edytowalnymi metadanymi, a nie zewnętrznym zaufanym poświadczeniem czasu; samo drzewo commita nie dowodzi nieistnienia wcześniejszych plików nieśledzonych. Tej silniejszej tezy nie przyjmujemy.

Working tree przed audytem był czysty. Wszystkie istniejące śledzone pliki zahashowano przed kontrolami. Zostały zachowane bajtowo; nie nadpisano nawet historycznych plików potwierdzenia reprodukcji. Dowody: [baseline](verification/prepublication/baseline.json), [daty i rodzice](verification/prepublication/git_history.json).

## Świeże środowisko i wykonane kontrole

Utworzono nowe środowisko Python 3.14.0 w ignorowanym `.venv/prepublication_env` i zainstalowano `requirements.txt`. Instalacja zakończyła się kodem 0. Potwierdzono dokładną zgodność wszystkich 22 przypiętych wersji, w tym Qiskit 2.6.1 i NumPy 2.5.4. `pip check` zakończył się kodem 0, bez konfliktów.

Ponieważ polecenia `--reproduce` zapisują plik potwierdzenia reprodukcji, wykonano je w izolowanej kopii śledzonych plików `.venv/prepublication_snapshot`. W kopii użyto świeżego interpretera o tych samych przypiętych zależnościach. Zastosowano polecenia z README, zastępując jedynie ścieżkę interpretera nowym środowiskiem i wybierając nowe katalogi wyjściowe. Nie zmieniono implementacji ani konfiguracji badań.

| Kontrola | Wynik | Kod wyjścia |
| --- | --- | ---: |
| Instalacja `pip install -r requirements.txt` | PASS: świeże środowisko, 22 zgodne wersje | 0 |
| `pip check` | PASS: brak konfliktów | 0 |
| Pełne `pytest -q -p no:cacheprovider` | **27 passed in 19.32s** | 0 |
| Odtworzenie pierwszego badania | PASS: 20 modeli; identyczne parametry, historie i metryki | 0 |
| Odtworzenie POST-HOC REPLICATION | PASS: 20 modeli; identyczne parametry, historie, hashe danych i metryki | 0 |
| `run_experiment.py --audit` | PASS: CSV/JSON, dane i oryginalne wykresy | 0 |
| `audit_rng_replication.py --check` | PASS: protokół, zachowanie oryginałów, README i replikacja | 0 |
| Niezależne pełne obwody Qiskit | PASS: 8000 predykcji testowych, poprawne normy stanów | 0 |
| Gradienty, dwa kroki Adama, tożsamość XOR i nieaktywny parametr | PASS | 0 |
| `git diff --check` | PASS | 0 |

Nie wymagano równości czasów ściennych: zależą od obciążenia komputera. Porównano dokładnie wszystkie wartości numeryczne, które procedury reprodukcji deklarują jako deterministyczne w tym środowisku. Ponowne wykonania są weryfikacją istniejących badań, nie nowymi wynikami hipotezy ani doborem hiperparametrów.

Dzienniki, polecenia i kody wyjścia: [execution.json](verification/prepublication/execution.json). Wersje: [dependency_versions.json](verification/prepublication/dependency_versions.json).

## Potwierdzone metryki

Liczby przeliczono z CSV i porównano z JSON oraz README; nie przepisano ich bez kontroli.

| Badanie | RY: test mean ± SD | ZZ: test mean ± SD | Średnia ZZ−RY |
| --- | ---: | ---: | ---: |
| Pierwotne | 97,10% ± 1,70 pp | 58,45% ± 2,94 pp | −38,65 pp |
| POST-HOC REPLICATION | 97,00% ± 2,01 pp | 61,90% ± 4,29 pp | −35,10 pp |

SD obliczono z `ddof=1`. RY wygrywa w każdej z 10 par obu badań. Przewidywanie przewagi ZZ o przynajmniej +5 pp nie zostało spełnione. Replikacja nie zastępuje pierwotnego wyniku i nie jest nową prerejestracją.

## Fakty matematyczne, obserwacje i interpretacje

**Fakty matematyczne:** definicje RY, RZ i RZZ odpowiadają podanym wykładnikom. Ujemne kąty `-2*x` i `-2*phi` w Qiskit realizują dodatnie wykładniki protokołu. Kolejność bazy `|q1 q0>`, CX(0,1), pomiar Z0 i prawdopodobieństwo `(1-<Z0>)/2` są spójne. Gradient parameter shift i reguła łańcuchowa BCE są poprawne w obszarze różniczkowalnym; konwencja clippingu została jawnie ustalona.

Dla kątów wejściowych x i parametrów a=theta0, b=theta1, c=theta2:

$$
\langle Z_0\rangle_{\mathrm{RY}}=\cos c\cos(x_0+a)-\sin c\sin(x_0+a)\sin(x_1+b).
$$

Wybór a=b=pi/2, c=-pi/2 daje `cos(x0)*cos(x1)`. Po skalowaniu `x=pi*(r+1)/2` znak iloczynu jest zgodny ze znakiem `r0*r1`. Reguła klasyfikacji odtwarza XOR poza granicą o zerowym prawdopodobieństwie w ciągłym generatorze. To dowód możliwości reprezentacji, nie twierdzenie, że każdy trening znajdzie to rozwiązanie.

Końcowy CX komutuje z Z0, a poprzedzający go RY na kubicie 1 działa na innym kubicie. Stąd theta3 nie wpływa na odczyt ani stratę: modele mają cztery parametry nominalne, ale najwyżej trzy aktywne. Nie jest to dowód barren plateau.

Niezależne sprawdzenie gradientów różnicami skończonymi dało maksymalne błędy 3,62e-10 dla RY i 1,11e-10 dla ZZ. Porównanie dwóch kroków Adama z zamkniętym wzorem na momenty dało błędy poniżej 3,34e-16. Testy są kontrolami implementacji na zapisanych wejściach, nie dodatkowym badaniem skuteczności. Dowód numeryczny: [scientific_checks.json](verification/prepublication/scientific_checks.json).

**Obserwacje empiryczne:** wartości accuracy, strat i ich zmienność dotyczą tych danych, tej architektury i tego budżetu. Pełne niezależne obwody Qiskit odtworzyły accuracy każdego z 40 zapisanych modeli: [8000 predykcji](verification/prepublication/qiskit_predictions.json).

**Interpretacje niepotwierdzone przyczynowo:** okresowość faz ZZ oraz ograniczony odczyt mogą wyjaśniać gorsze dopasowanie, ale nie wyznaczono najlepszego osiągalnego wyniku ZZ ani nie rozdzielono wpływu reprezentacji i optymalizacji. Nie wykazano uniwersalnej przewagi RY, przewagi kwantowej ani skutku zwiększenia głębokości ansatzu.

## RNG i ograniczenia metodologiczne

Historyczny błąd jest zachowany i jawnie opisany. Z powtórzenia tego samego seeda wynikało `theta_init = raw[:2].reshape(-1)/10`. Część tych obserwacji trafiała na test. Nowa ścieżka używa trzech dzieci SeedSequence dla danych, podziału i inicjalizacji, z identycznymi danymi oraz inicjalizacją wewnątrz każdej pary RY/ZZ. Testy sprawdzają przypisanie dzieci, odtwarzalność, brak wspólnego przesuwania stanu i zachowanie historycznych plików. To separacja strumieni pseudolosowych, nie dowód absolutnej niezależności statystycznej na podstawie skończonej próbki.

Replikacja zmienia realizacje danych, podziałów i inicjalizacji jednocześnie. Zmiany +3,45 pp ZZ nie można przypisać wyłącznie usunięciu sprzężenia inicjalizacji. SD zawiera wszystkie te źródła zmienności.

Zamrożony protokół zasobów mówi o zerowych parametrach, natomiast implementacja używa parametrów symbolicznych. Pozostawiono oba bez zmian i jawnie odnotowano rozbieżność. Kontrola w Qiskit 2.6.1 wykazała identyczne głębokości i liczby bramek dla obu konwencji przy podanej dekompozycji i optimization_level=0. Nie wpływa to na accuracy.

## README, wykresy i zgodność wymagań

README zawiera wszystkie elementy wymienione w poleceniu: cel, pytanie, hipotezę +5 pp, mechanizm, protokół, VQC, trening, obie tabele 10 powtórzeń, wykresy, analizę, RNG, nieaktywny parametr, instalację i uruchomienie. Odpowiedź o większej głębokości wyraźnie zaznacza brak takiego eksperymentu i przedstawia możliwości oraz ryzyka, a nie wynik pomiaru.

Sprawdzono UTF-8, istniejące linki lokalne, struktury tabel, jednostki i delimitery Markdown/LaTeX. Standardowe makra nie zawierają wcześniejszego problematycznego użycia operatorname w formule. **Nie zweryfikowano rzeczywistego renderowania bieżącego README na GitHubie.** Lokalnej kontroli składni ani obrazów nie przedstawia się jako testu GitHub.

Wszystkie 10 PNG sprawdzono przez odczyt, wymiary, hashe i zgodność serii z zapisanymi CSV/JSON/historiami. Dodatkowo w tym audycie ponownie obejrzano oba wykresy accuracy. Nie nadpisywano historycznych obrazów i nie regenerowano ich pod korzystniejszy wynik.

Zgodność potwierdzono z wymaganiami Axion Challenge 3 wymienionymi przez użytkownika. Nie dostarczono osobnego oficjalnego regulaminu do niezależnego potwierdzenia wszystkich kryteriów organizatora. Audyt nie jest formalnym zatwierdzeniem przez organizatora.

## Bezpieczeństwo i organizacja

Nie wykryto typowych formatów tokenów, kluczy API ani kluczy prywatnych w skanowanych śledzonych plikach tekstowych. To kontrola wzorców, nie gwarancja wykrycia każdej możliwej postaci sekretu. `.gitignore` poprawnie wyklucza `.venv`, `__pycache__`, `.pytest_cache` i pyc. Nie znaleziono śledzonych środowisk, cache ani przypadkowych plików ponad 5 MiB. Istotne artefakty obu badań są śledzone.

Świeża instalacja i odtworzenie potwierdzają działanie udokumentowanego środowiska Python 3.14 na Windows. Innych platform i wersji Pythona nie testowano. Środowisko audytu, kopie i nowe treningi kontrolne pozostają wyłącznie w ignorowanym `.venv`.

## Wykryte problemy i wprowadzone zmiany

Nie znaleziono nowego błędu implementacji wymagającego zmiany modelu, protokołu lub wyników. Nie modyfikowano README ani żadnego z wcześniejszych śledzonych plików. Dodano wyłącznie ten raport i dowody weryfikacji; nie ma poprawki logiki wymagającej nowego cyklu TDD.

Pierwsza próba testów w kopii audytowej zakończyła się `24 passed, 3 errors`: brakowało nadrzędnego katalogu dla niestandardowego `--basetemp`. Poprawiono wyłącznie pomocnicze środowisko audytu; pełna ponowna próba dała 27/27. Zachowano [pierwszy log](verification/prepublication/attempt1_full_tests.log). Początkowe sprawdzenie polskich fraz w doraźnym skrypcie również wymagało poprawnego przekazania UTF-8 przez PowerShell; plik README był poprawny, a ostateczna kontrola przeszła.

Właściciel powinien publikować z zachowaniem obu badań, jawnej informacji o RNG i ograniczeniach. Polecenia `--reproduce` należy wykonywać w kopii, jeżeli wymagane jest nienadpisywanie nawet plików potwierdzających odtwarzalność. Nie naprawiano tego zachowania przez zmianę historycznych skryptów.

Wszystkie historyczne commity pozostały bez zmian. Raport i dowody są przeznaczone do osobnego lokalnego commita `Challenge 3: final documentation and verification fixes`; jego hash podaje końcowa odpowiedź i `git log -1`. Po commicie należy sprawdzić czystość working tree. Gotowość oznacza możliwość ręcznego przeglądu i push przez właściciela, bez twierdzenia o uniwersalnej prawdziwości hipotez.

**NIE wykonano push i NIE utworzono Pull Request.**

QCODE READY FOR OWNER REVIEW — NO PUSH PERFORMED
