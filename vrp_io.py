from __future__ import annotations
import csv
import math
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Instance:
    name: str
    n: int
    capacity: int
    vehicles: int
    coords: list
    demand: list
    dist: list
    bks: float | None = None


def _nint(x):
    return int(math.floor(x + 0.5))


def _matrix_from_weights(fmt, weights, dim):
    fmt = fmt.strip().upper()
    dist = [[0] * dim for _ in range(dim)]
    it = iter(weights)
    if fmt == "LOWER_ROW":
        for i in range(1, dim):
            for j in range(i):
                dist[i][j] = dist[j][i] = next(it)
    elif fmt == "FULL_MATRIX":
        for i in range(dim):
            for j in range(dim):
                dist[i][j] = next(it)
    else:
        raise ValueError(f"unsupported EDGE_WEIGHT_FORMAT {fmt!r}")
    return dist


def read_instance(path, bks=None):
    path = Path(path)
    header = {}
    coords = []
    demand = {}
    weights = []
    section = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line == "EOF":
            continue
        upper = line.upper()
        if upper.endswith("_SECTION"):
            section = upper
            continue
        if ":" in line and section is None:
            key, value = line.split(":", 1)
            header[key.strip().upper()] = value.strip()
            continue
        parts = line.split()
        if section == "NODE_COORD_SECTION":
            coords.append((float(parts[1]), float(parts[2])))
        elif section == "EDGE_WEIGHT_SECTION":
            weights.extend(int(float(x)) for x in parts)
        elif section == "DEMAND_SECTION":
            demand[int(parts[0])] = int(float(parts[1]))
        elif section == "DEPOT_SECTION":
            break
    dim = int(header["DIMENSION"])
    capacity = int(header["CAPACITY"])
    name = header.get("NAME", path.stem)
    dem = [demand[i] for i in range(1, dim + 1)]
    match = re.search(r"-k(\d+)", name)
    if "VEHICLES" in header:
        vehicles = int(header["VEHICLES"])
    elif match:
        vehicles = int(match.group(1))
    else:
        vehicles = math.ceil(sum(dem) / capacity) + 1
    if name.startswith("X-n"):
        vehicles = math.ceil(1.25 * vehicles) + 1
    if coords:
        exact = header.get("EDGE_WEIGHT_TYPE", "").upper() == "EXACT_2D"
        rnd = (lambda x: x) if exact else _nint
        dist = [
            [rnd(math.hypot(a[0] - b[0], a[1] - b[1])) for b in coords]
            for a in coords
        ]
    else:
        dist = _matrix_from_weights(header.get("EDGE_WEIGHT_FORMAT", ""), weights, dim)
    return Instance(name, dim - 1, capacity, vehicles, coords, dem, dist, bks)


def load_bks(directory):
    table = {}
    with open(Path(directory) / "bks.csv") as fh:
        for row in csv.DictReader(fh):
            table[row["name"]] = float(row["bks"])
    return table


def route_cost(inst, route):
    if not route:
        return 0
    d = inst.dist
    total = d[0][route[0]] + d[route[-1]][0]
    for a, b in zip(route, route[1:]):
        total += d[a][b]
    return total


def validate(inst, routes):
    seen = [c for r in routes for c in r]
    if sorted(seen) != list(range(1, inst.n + 1)):
        return False, "customer coverage"
    for r in routes:
        if sum(inst.demand[c] for c in r) > inst.capacity:
            return False, "capacity"
    if sum(1 for r in routes if r) > inst.vehicles:
        return False, "fleet size"
    return True, sum(route_cost(inst, r) for r in routes)
