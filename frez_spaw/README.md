# Frez: start 3 mm od osi, krok średnicy I073, koniec D120

Ta wersja zastępuje wcześniejszy wariant 15 obiegów ze startem 3 mm od ścianki. Użytkownik potwierdził nowy start: **oś freza ma znaleźć się 3 mm od osi otworu**, po czym pełne obiegi mają zwiększać średnicę szlifu o `I073` do granicy wyliczonej w `D120`.

Potrzebne są **oba** pliki:

- `OBLICZ_SZLIF_TROJNIKA.JBI` — inicjalizacja wymiarów i wyliczanie punktów;
- `SZLIF_SPAWU_TROJNIKA.JBI` — dojazd promieniowy, pełne obiegi i zakończenie przy granicy.

## Zmienne

| Zmienna | Znaczenie i skala |
|---|---|
| `I070` | Średnica fizycznego freza, 0,1 mm. Dla freza Ø12 mm ustawić **120**. Program nie nadpisuje tej zmiennej. |
| `I071` | Średnica zewnętrzna detalu, 0,1 mm. |
| `I074` | Grubość jednej ścianki, 0,1 mm. |
| `I073` | Ustawiany przez operatora **przyrost średnicy na pełny obieg**, 0,001 mm. Przykład: **100 = 0,10 mm średnicy**, czyli 0,05 mm promienia. |
| `D120` | Docelowy **promień toru osi freza**, 0,001 mm. Jest wyliczany z geometrii na początku każdej sztuki, zgodnie z kodem operatora. |
| `D074` | Aktualny promień toru osi freza, 0,001 mm. Zaczyna od **3000**, czyli 3 mm. |
| `D121` | Nowa robocza zmienna D: zapamiętany na sztukę krok promienia, czyli `I073 / 2`. W archiwalnych 97 jobach nie znaleziono jej użycia; należy zarezerwować ją również w bieżącym PLC/HMI. |
| `I120` | Licznik wykonanych/wykonywanych obiegów, zaczyna od 1. Nie jest limitem wymiaru. `I120` i `D120` to osobne zmienne. |
| `D103–D105` | Dotychczasowe korekty położenia z `TROJNIK_TEST`. |

Krok `I073` musi być dodatni i parzysty, co najmniej 2. Punkty mają rozdzielczość 0,001 mm na promieniu; podział nieparzystego kroku średnicy przez dwa wymagałby połowy tej jednostki. Wersja zatrzymuje się na `PAUSE` dla takiego kroku, zamiast zaokrąglać go lub ryzykować brak postępu.

`I073` nie jest już wyliczane z `I072`. `I072` i `I075` nie sterują obróbką i nie są modyfikowane. Kompensacja zużycia freza została usunięta.

## Geometria i przebieg

W jednostkach 0,001 mm:

```text
D120 = (I071*100 - 2*I074*100 - I070*100) / 2
D121 = I073 / 2
D074(n) = MIN(3000 + (n-1)*D121, D120)
```

`D120` zachowuje znaczenie promienia z wklejonego kodu operatora, gdzie występuje `DIV D120 2`. Nie porównujemy do niego średnicy. Średnica obrabianego otworu na danym obiegu wynika z dwukrotnego promienia toru osi i średnicy freza.

1. Program ruchowy ustawia `I120=1` i wywołuje obliczenia. Wymiary i krok są pobierane na nowo, bez uzależnienia od przycisku resetu `B030`.
2. Oś freza dojeżdża ruchem `MOVL` do `P010` na promieniu 3 mm od skorygowanej osi otworu. Punkt ma również zachowaną wysokość obróbki.
3. Wykonywany jest pełny obieg: `P010 → P013 → P012 → P011 → P010`.
4. Jeżeli promień jest mniejszy niż `D120`, licznik `I120` rośnie, obliczany jest kolejny promień i wykonywany dojazd promieniowy do nowego `P010`.
5. Promień ostatniego obiegu jest ograniczany do `D120`. Po wykonaniu **jednego pełnego obiegu na tym promieniu** program kończy się. Ostatni przyrost może być mniejszy od nominalnego kroku.

Promień wyliczamy z numeru obiegu, a nie przez ślepe dodawanie do poprzedniego `D074`. Powtórzenie samych obliczeń dla tego samego `I120` nie powoduje kolejnego zwiększenia promienia.

Wymiary i krok są zapamiętywane na początku sztuki. Zmiana `I073` w trakcie pracy obowiązuje od następnej sztuki, zgodnie z wcześniej ustaloną zasadą. Nie nadpisywać roboczych `D074`, `D120`, `D121`, `I120` ani punktów P z PLC/HMI w trakcie cyklu.

## Przykład dla obecnej receptury

`I071=269` (Ø26,9 mm), `I074=16` (ścianka 1,6 mm), `I070=120` (frez Ø12 mm):

- otwór nominalny: Ø23,7 mm;
- docelowy promień osi freza `D120=5850`, czyli 5,85 mm;
- pierwszy promień osi freza: 3,00 mm, a zewnętrzna obwiednia freza ma wtedy Ø18,00 mm;
- przy `I073=100` promienie wynoszą 3,00; 3,05; 3,10; …; 5,85 mm — **58 obiegów**;
- przy `I073=200` ostatni krok jest skrócony: 3,00; 3,10; …; 5,80; 5,85 mm — **30 obiegów**;
- jeśli `D120=3000`, wykonywany jest jeden obieg na promieniu startowym;
- jeśli `D120<3000`, program zatrzymuje się przed ruchem, ponieważ frez nie mieści się na wymaganym torze początkowym.

## Zastosowanie i integracja

Zachować bieżące joby z kontrolera i wprowadzić oba pliki tej wersji po sprawdzeniu ich nagłówków. `BLOK_DO_PODMIANY.txt` zawiera część obliczeniową od `NOP` do komentarza `TABELA PARAMETROW DLA SREDNIC`. Sama podmiana obliczeń nie wystarczy, jeśli program ruchowy nadal ma pętlę `FOR ... TO 15`.

Dotychczasowe wywołanie z `WYBOR_SZLIFU` pozostaje:

```text
CALL JOB:SZLIF_SPAWU_TROJNIKA UF#(18)
```

W programie ruchowym zachowano `SET I020 200` oraz pięć punktów każdego obiegu `MOVC`. Dodano `MOVL P010` przed pierwszym obiegiem i między obiegami. Dojazdy oraz końcowy punkt obiegu mają `PL=0`, aby rozdzielić promieniowy dosuw i zamknięty obieg. Wpływ tych zmian na interpolację, obciążenie i czas wymaga sprawdzenia na kontrolerze.

Ustawianie orientacji, wysokość `D032=19000` i korekty XYZ pochodzą z podanego kodu. TOOL 17 jest używany dla P010–P013. Archiwalne dojazdy i odjazdy P000–P009 korzystają z TOOL 18, którego TCP ma inne wartości; bieżący tor dojazdu/odjazdu trzeba zweryfikować dla freza i TCP 17. Nowe pliki dotyczą trybu spawu i nie zmieniają innych programów szlifu całego trójnika.

Kontrola parametrów wykonuje `PAUSE` przed pierwszym ruchem dla błędnej receptury, kroku lub wymiarów. Pauza nie wyłącza wrzeciona; zachowanie przy przerwaniu i wznowieniu musi odpowiadać konfiguracji stanowiska. Nie dobierano obrotów ani technologicznego posuwu dla freza.

## Sprawdzenie wykonane offline

Uruchomienie z katalogu repozytorium:

```text
python frez_spaw/test_promieni.py
```

Model wykonuje instrukcje obu plików i sprawdza pierwszy dojazd na promień 3 mm, kolejność pięciu ruchów kołowych, przyrost średnicy, ograniczenie końcowego kroku, pełny obieg końcowy, brak obiegów ponad granicę, różne kroki i geometrie, restart na nową sztukę, zapamiętanie ustawień i powtórzenie obliczeń. Wynik: **133 poprawne scenariusze oraz 10 przypadków błędnych danych zakończonych pauzą przed ruchem**. Szczegóły w `wyniki_sprawdzenia.json`.

To model arytmetyki i sterowania, nie kompilator INFORM ani symulator DX200. Nie potwierdza importu, kinematyki, rzeczywistej interpolacji MOVC, kolizji, działania PLC ani jakości obróbki. Wersja jest przeznaczona do przeglądu i prób na docelowym kontrolerze/MotoSim.
