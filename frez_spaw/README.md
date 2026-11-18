# Szlif spawu frezem Ø12 — start 3 mm od ścianki

Zmiana dotyczy wklejonego `OBLICZ_SZLIF_TROJNIKA`, czyli trybu szlifu spawu, dla `I035=30` i TCP 17 na osi freza. Frez nie ma modelowanej kompensacji zużycia. Inne tryby obróbki w starej paczce nie są tą zmianą dostosowywane do freza.

## Ustalenia i parametry

- Frez Ø12 mm: program ustawia `I070=120` (jednostka zmiennej: 0,1 mm).
- Średnica zewnętrzna: `I071` w 0,1 mm; grubość jednej ścianki: `I074` w 0,1 mm.
- Przesunięcie początkowe 3 mm jest promieniowe: odległość krawędzi freza od nominalnej wewnętrznej ścianki, w stronę osi otworu.
- Zachowano 15 obiegów istniejącego `SZLIF_SPAWU_TROJNIKA`: licznik `I120` od 1 do 15. Między pierwszym i ostatnim obiegiem są 14 przyrostów, po około 0,214 mm.
- `D103`, `D104`, `D105` to dotychczasowe korekty X/Y/Z z `TROJNIK_TEST`.
- Wynik `D074` jest promieniem toru osi freza w 0,001 mm. Nie jest średnicą ani pozostałym zużyciem.

Wzór dla obiegu n, w mm:

`R(n) = (średnica_zewnętrzna - 2 × ścianka - średnica_freza) / 2 - 3 + (n - 1) × 3 / 14`

Dla `I071=269`, `I074=16`: otwór Ø23,7 mm, promień końcowy osi freza 5,85 mm. Obieg 1: 2,85 mm (3 mm od ścianki), obieg 8: 4,35 mm (1,5 mm od ścianki), obieg 15: 5,85 mm (nominalna ścianka).

Program oblicza promień od nowa na każdym obiegu. `I072`, `I073` i `I075` nie są używane ani zmieniane. Nie nalicza się zużycia, a stary `D074` nie wpływa na wynik. Zachowano potwierdzenie dawnego resetu `B030=0` i `OT#(6)=OFF`.

`D066` służy chwilowo jako obliczenie postępu, a następnie — jak wcześniej — do współrzędnej X. Nie zajęto nowych zmiennych roboczych. Przelicznik `DIV` na D daje rozdzielczość 0,001 mm; możliwe zaokrąglenie kroku trzeba potwierdzić na DX200. Początek i koniec mają dokładne wartości całkowite w tej skali.

## Zastosowanie

1. Zachować aktualną kopię programu z kontrolera.
2. Podmienić podprogram na `OBLICZ_SZLIF_TROJNIKA.JBI` z tego katalogu, po sprawdzeniu zgodności nagłówka i bieżących układów. Plik jest oparty na archiwalnym nagłówku; korpus uwzględnia podany TOOL 17.
3. W aktualnym `SZLIF_SPAWU_TROJNIKA` zachować:

```text
FOR I120 START= 1 TO 15 STEP= 1
    CALL JOB:OBLICZ_SZLIF_TROJNIKA
    ... istniejące ruchy MOVC ...
NEXT I120
```

`I120` musi być numerem aktualnego obiegu. Przed samodzielnym wywołaniem obliczeń należy ustawić go w zakresie 1–15. Nie ustawiać go na 1 wewnątrz podprogramu, bo zablokuje to przyrost promienia. Zmiana liczby obiegów wymaga również zmiany dzielnika 14 i kontroli zakresu w obliczeniach.

Jeśli modyfikujesz tylko kod wklejony w rozmowie, `BLOK_DO_PODMIANY.txt` zastępuje fragment od `NOP` do linii przed komentarzem `TABELA PARAMETROW DLA SREDNIC`. Dalsza część ustawiania punktów pozostaje zgodna z podanym kodem. `zmiany.diff` pokazuje pełne porównanie względem wersji z TOOL 17.

Program wykonuje `PAUSE`, gdy `I120` jest poza zakresem 1–15 albo nie ma dodatniego promienia początkowego przy odsunięciu 3 mm. Po wznowieniu wraca do kontroli parametrów. To pauza programu i nie zmienia stanu wyjścia wrzeciona.

## Integracja z robotem

Archiwalne `OBLICZENIA_KROKOW_TROJNIKI` ustawia TOOL 18 dla punktów dojazdu P000–P009; dotyczy to również odjazdu. TOOL 17 i TOOL 18 mają różne definicje TCP w archiwum. Bieżący dojazd i odjazd należy zweryfikować dla freza i TCP 17. Nie przeliczano automatycznie tych trajektorii z nieaktualnego zrzutu.

Dodatkowo trzeba sprawdzić wejście na pierwszy obieg, przejścia pomiędzy obiegami MOVC oraz wysokość obróbki. Nominalny promień punktów nie dowodzi, że interpolacja i PL dadzą dokładnie tę samą powierzchnię. Dotychczasowe korekty i wysokość `D032=19000` pozostają w kodzie; wymagają potwierdzenia dla nowego narzędzia.

## Sprawdzenie offline

Uruchom: `python frez_spaw/test_promieni.py` z katalogu repozytorium.

Model wykonuje instrukcje obliczeniowe z wygenerowanego JBI i sprawdza geometrię, korekty, TOOL 17, wszystkie 15 obiegów, niezależność od dawnych parametrów zużycia oraz odrzucenie błędnych danych. Wynik: 1260 scenariuszy obliczeniowych i 5 przypadków odrzucenia. Szczegóły są w `wyniki_sprawdzenia.json`.

To model arytmetyki i fragmentu sterowania, nie kompilator ani symulator DX200. Nie sprawdza importu na kontroler, PLC, kinematyki, kolizji, posuwu, obrotów ani jakości obróbki. Wersja wymaga prób offline/na stanowisku przed użyciem produkcyjnym.
