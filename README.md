# CVRP ar Tabu Search

Palaišana (Python 3.9+, bez ārējām bibliotēkām):

    python3 main.py                # visi testa piemēri
    python3 main.py CMT1 A-n32-k5  # tikai izvēlētie (skat testa piemēri)

## Faili

- `vrp_io.py` – TSPLIB/CVRPLIB formāta datu ielase, risinājumu validācija.
- `tabu.py` – Clarke-Wright sākuma risinājums un Tabu Search.
- `main.py` – algortima palaišana un paralēls salīdzinājums ar BKS.
- `testa_piemeri/` – testa piemeri veiktspējas analīzei, `.sol` fails un `bks.csv`.