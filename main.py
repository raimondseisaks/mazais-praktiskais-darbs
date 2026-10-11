import statistics
import sys
import time
from multiprocessing import Pool
from pathlib import Path

from tabu import TabuSearch, clarke_wright, reduce_fleet
from vrp_io import load_bks, read_instance, validate

ROOT = Path(__file__).parent
TESTS = ROOT / "testa_piemeri"
ORDER = ["E-n13-k4", "P-n16-k8", "E-n22-k4", "A-n32-k5",
         "CMT1", "F-n72-k4", "M-n101-k10", "X-n101-k25"]
SEEDS = [1, 2, 3, 4, 5]


def time_budget(n):
    return min(60.0, max(5.0, 0.4 * n))


def run_one(args):
    name, seed = args
    inst = read_instance(TESTS / f"{name}.vrp")
    ts = TabuSearch(inst, seed=seed, time_limit=time_budget(inst.n))
    routes, _ = ts.run()
    if routes is None:
        return name, None, None
    ok, value = validate(inst, routes)
    if not ok:
        return name, None, None
    return name, value, ts.best_time


def main():
    names = sys.argv[1:] or ORDER
    jobs = [(name, seed) for name in names for seed in SEEDS]
    start = time.perf_counter()
    with Pool(2) as pool:
        results = pool.map(run_one, jobs, chunksize=1)
    bks = load_bks(TESTS)

    lines = ["| Testa Piemērs | Klienti | BKS | CW sākuma | Labākais | Vidējais | Gap labākais % | "
             "Gap vidējais % | BKS sasniegts | Laiks līdz labākajam, s | Laika limits, s |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]

    for name in names:
        inst = read_instance(TESTS / f"{name}.vrp")
        good = [r for r in results if r[0] == name and r[1] is not None]
        if not good:
            lines.append(f"| {name} | {inst.n} | {bks[name]:.2f} | – | nav derīga | – | – | – | 0/{len(SEEDS)} | – | – |")
            continue

        dists = [r[1] for r in good]
        best = min(dists)
        avg = statistics.mean(dists)
        cw_ok, cw = validate(inst, reduce_fleet(inst, clarke_wright(inst)))
        cw = f"{cw:.2f}" if cw_ok else "nederīgs"
        hits = sum(1 for x in dists if x <= bks[name] + 0.01)
        t_best = statistics.mean(r[2] for r in good)

        lines.append(
            f"| {name} | {inst.n} | {bks[name]:.2f} | {cw} | {best:.2f} | {avg:.2f} | "
            f"{100 * (best - bks[name]) / bks[name]:.2f} | "
            f"{100 * (avg - bks[name]) / bks[name]:.2f} | "
            f"{hits}/{len(SEEDS)} | {t_best:.2f} | {time_budget(inst.n):.0f} |"
        )

    table = "\n".join(lines)
    (ROOT / "results.md").write_text(table + "\n")
    print(table)
    print(f"\nwall time {time.perf_counter() - start:.0f}s")


if __name__ == "__main__":
    main()