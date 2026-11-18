# TOFIC — programy robota YASKAWA DX200

Bieżąca wersja na tej gałęzi: frez Ø12 mm, start osi freza na promieniu 3 mm od osi otworu, następnie zwiększanie średnicy o `I073` po pełnym obiegu do promienia `D120`.

- [Opis ustawień i integracji](frez_spaw/README.md)
- [Obliczanie punktów: OBLICZ_SZLIF_TROJNIKA.JBI](frez_spaw/OBLICZ_SZLIF_TROJNIKA.JBI)
- [Wykonanie obiegów: SZLIF_SPAWU_TROJNIKA.JBI](frez_spaw/SZLIF_SPAWU_TROJNIKA.JBI)
- [Paczka bieżącej wersji](frez_spaw_i073_d120.zip)

Potrzebne są oba pliki JBI. Wersja wymaga sprawdzenia na DX200/MotoSim i potwierdzenia dojazdów dla TCP 17 przed użyciem na stanowisku.

`TOFIC_komplet.zip` zawiera wcześniejszy zrzut robota i starsze wyniki optymalizacji. Aktualne zmiany freza znajdują się w katalogu `frez_spaw` oraz w paczce `frez_spaw_i073_d120.zip`.
