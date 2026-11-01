# QCODE — Quantum Coding of Data

## Cel projektu i pytanie badawcze

Celem projektu jest porównanie dwóch sposobów kodowania klasycznych danych w stanach kwantowych przy kontrolowanych warunkach uczenia klasyfikatora wariacyjnego.

**Pytanie badawcze:** Czy ZZ Feature Map zapewni wyższą średnią dokładność klasyfikacji na zbiorze testowym niż RY Angle Encoding dla syntetycznych danych z interakcjami między dwiema cechami?

## Porównanie kodowań

| Właściwość | RY Angle Encoding | ZZ Feature Map |
| --- | --- | --- |
| Kodowanie dwóch cech | Osobne obroty RY na dwóch kubitach | Obroty fazowe zależne od cech oraz człon ZZ zależny od pary cech |
| Interakcje na etapie kodowania | Brak jawnego członu łączącego cechy | Jawny człon dwukubitowy łączący cechy |
| Splątanie | Samo kodowanie lokalnymi RY nie splątuje początkowego stanu produktowego | Może wytworzyć splątanie dla odpowiednich danych i parametrów mapy |

Przyjmujemy RY Angle Encoding w postaci:

$$
U_{\mathrm{RY}}(x) = R_Y(x_1) \otimes R_Y(x_2).
$$

Dla ZZ Feature Map przyjmujemy jedną warstwę mapy, z konwencją:

$$
U_{\mathrm{ZZ}}(x) = \exp\left(i\,\phi_{12}(x) Z_1 Z_2\right)\exp\left(i(x_1 Z_1 + x_2 Z_2)\right)(H \otimes H),
$$

$$
\phi_{12}(x) = (\pi - x_1)(\pi - x_2).
$$

Operatory działają od prawej do lewej, a oba kodowania rozpoczynają od stanu zerowego dwóch kubitów. Ta definicja ustala konwencję matematyczną; późniejsza implementacja powinna zachować ją przy rozkładzie na bramki.

## Hipoteza i mechanizm

**Przewidywanie:** ZZ osiągnie średnią test accuracy co najmniej 5 punktów procentowych wyższą niż RY.

Dla 10 powtórzeń definiujemy różnicę:

$$
\Delta = \frac{1}{10}\sum_{s=1}^{10}\left(\mathrm{acc}_{\mathrm{ZZ},s} - \mathrm{acc}_{\mathrm{RY},s}\right).
$$

Dokładności zapisujemy jako ułamki od 0 do 1. Hipoteza przewiduje:

$$
\Delta \geq 0.05.
$$

Człon ZZ uzależnia fazę stanu od wspólnej funkcji dwóch cech. Dzięki temu interakcje cech są obecne już w reprezentacji wejściowej. Lokalne obroty RY kodują każdą cechę osobno; interakcje musi następnie odwzorować ansatz. Przy ograniczonej głębokości ansatzu ZZ może więc ułatwić rozdzielenie klas zależnych od relacji między cechami. Nie gwarantuje to przewagi: wynik zależy także od danych, optymalizacji i dopasowania mapy do zadania.

## Plan eksperymentu

1. Użyć dokładnie **2 kubitów** oraz syntetycznego zadania binarnego z dwiema cechami i interakcją typu XOR. W każdym powtórzeniu zaplanować 1000 niezależnych obserwacji z cechami z rozkładu jednostajnego na przedziale od -1 do 1. Etykieta wynosi 1, gdy iloczyn cech jest ujemny, i 0 w przeciwnym przypadku. Nie dodawać szumu etykiet.
2. Wykonać **10 sparowanych powtórzeń**, z ziarnami losowości od 0 do 9. Dla każdej pary RY/ZZ wykorzystać identyczne dane oraz identyczny stratyfikowany podział: 80% trening i 20% test.
3. Przeskalować cechy liniowo do przedziału od 0 do pi, korzystając ze znanych granic generatora. Zastosować identyczne przekształcenie w obu wariantach, bez dopasowywania do testu.
4. Po każdym kodowaniu zastosować **identyczny ansatz**: dwie warstwy, w każdej trenowalne obroty RY na obu kubitach i CNOT z kubitu 0 do kubitu 1. Oba modele mają tyle samo parametrów i identyczną inicjalizację w danym powtórzeniu.
5. Utrzymać **identyczne warunki treningu**: bezszumowy symulator stanu, dokładne wartości oczekiwane bez próbkowania pomiarów, pełny zbiór treningowy w każdym kroku, binarna entropia krzyżowa, optymalizator Adam, learning rate 0.05 i 100 kroków. Parametry początkowe losować jednostajnie z przedziału od -0.1 do 0.1 z ziarnem danego powtórzenia.
6. Prawdopodobieństwo klasy 1 wyznaczać z wartości oczekiwanej Z na kubicie 0 jako połowę różnicy między 1 a tą wartością; klasyfikować do klasy 1 przy prawdopodobieństwie co najmniej 0.5. Oceniać końcowy stan treningu, bez wyboru modelu według wyniku testowego.
7. Zmierzyć accuracy na odłożonym teście dla każdego modelu i powtórzenia. Raportować wszystkie 10 par, średnie accuracy, odchylenia standardowe oraz średnią sparowaną różnicę. Nie dostrajać konfiguracji po obejrzeniu testu.

## Kryterium obalenia przewidywania

Przewidywanie zostaje obalone w tym zaplanowanym eksperymencie, jeśli średnia sparowana różnica test accuracy jest mniejsza niż 0.05, czyli przewaga ZZ jest mniejsza niż 5 punktów procentowych. Równość 0.05 spełnia przewidywanie. Jest to kryterium opisowe dla tej konfiguracji i tych 10 powtórzeń, a nie dowód uniwersalnej przewagi ani test istotności statystycznej.

## Struktura projektu

```text
quantum-data-encoding/
├── README.md
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── data.py
│   ├── encodings.py
│   ├── model.py
│   ├── train.py
│   └── evaluate.py
├── tests/
│   ├── test_data.py
│   ├── test_encodings.py
│   └── test_model.py
├── data/
└── results/
```

Wszystkie pliki Python, pliki testów i requirements.txt są celowo puste. Katalogi data i results również pozostają puste. Implementacja, wybór zależności, generowanie danych i uruchomienie eksperymentu są zadaniami na później.

## Przyszłe wyniki

Sekcja do uzupełnienia po samodzielnej implementacji i wykonaniu zaplanowanego eksperymentu. Obecnie nie ma danych, pomiarów ani wyników.

Docelowo należy zamieścić tabelę wyników 10 powtórzeń, podsumowanie średnich i zmienności, różnicę w punktach procentowych oraz ocenę zgodności z przewidywaniem.

## Pytanie do dalszej refleksji

Co by się zmieniło, gdybyśmy zwiększyli liczbę warstw ansatzu?
