import random
import time

from vrp_io import route_cost

def clarke_wright(inst):
    n, d, q, cap = inst.n, inst.dist, inst.demand, inst.capacity
    routes = {i: [i] for i in range(1, n + 1)}
    owner = list(range(n + 1))
    load = {i: q[i] for i in range(1, n + 1)}
    savings = []
    for i in range(1, n + 1):
        for j in range(i + 1, n + 1):
            savings.append((d[0][i] + d[0][j] - d[i][j], i, j))
    savings.sort(reverse=True)
    for s, i, j in savings:
        if s <= 0:
            break
        ri, rj = owner[i], owner[j]
        if ri == rj or load[ri] + load[rj] > cap:
            continue
        a, b = routes[ri], routes[rj]
        if a[-1] == i and b[0] == j:
            new = a + b
        elif a[0] == i and b[-1] == j:
            new = b + a
        elif a[0] == i and b[0] == j:
            new = a[::-1] + b
        elif a[-1] == i and b[-1] == j:
            new = a + b[::-1]
        else:
            continue
        routes[ri] = new
        load[ri] += load[rj]
        del routes[rj]
        del load[rj]
        for c in b:
            owner[c] = ri
    return list(routes.values())


def cheapest_position(inst, routes, loads, c):
    d, q, cap = inst.dist, inst.demand, inst.capacity
    best = None
    for r, route in enumerate(routes):
        fits = loads[r] + q[c] <= cap
        excess = 0 if fits else loads[r] + q[c] - cap
        prev = 0
        for p in range(len(route) + 1):
            nxt = route[p] if p < len(route) else 0
            delta = d[prev][c] + d[c][nxt] - d[prev][nxt]
            key = (not fits, excess, delta)
            if best is None or key < best[0]:
                best = (key, r, p)
            prev = nxt
    return best[1], best[2]


def reduce_fleet(inst, routes):
    routes = [list(r) for r in routes]
    while len(routes) > inst.vehicles:
        loads = [sum(inst.demand[c] for c in r) for r in routes]
        victim = min(range(len(routes)), key=lambda r: loads[r])
        customers = routes.pop(victim)
        loads.pop(victim)
        for c in sorted(customers, key=lambda c: -inst.demand[c]):
            r, p = cheapest_position(inst, routes, loads, c)
            routes[r].insert(p, c)
            loads[r] += inst.demand[c]
    return routes


def route_arcs(route):
    seq = [0] + route + [0]
    return {(a, b) if a < b else (b, a) for a, b in zip(seq, seq[1:]) if a != b}


class TabuSearch:
    def __init__(self, inst, seed=0, granularity=15, tenure=(8, 20),
                 stagnation=300, time_limit=30.0, max_iter=10**9):
        self.inst = inst
        self.n = inst.n
        self.d = inst.dist
        self.q = inst.demand
        self.cap = inst.capacity
        self.K = inst.vehicles
        self.rng = random.Random(seed)
        self.tenure = tenure
        self.stagnation = stagnation
        self.time_limit = time_limit
        self.max_iter = max_iter
        self.history = []
        g = min(granularity, self.n - 1)
        self.nbr = [[]]
        for i in range(1, self.n + 1):
            others = [j for j in range(1, self.n + 1) if j != i]
            others.sort(key=lambda j: self.d[i][j])
            self.nbr.append(others[:g])

    def _set_solution(self, routes):
        self.routes = [list(r) for r in routes]
        self.routes += [[] for _ in range(self.K - len(self.routes))]
        self.rid = [0] * (self.n + 1)
        self.pos = [0] * (self.n + 1)
        self.load = [0] * len(self.routes)
        self.rcost = [0] * len(self.routes)
        self.arcs = [set() for _ in self.routes]
        for r in range(len(self.routes)):
            self._refresh(r)

    def _refresh(self, r):
        route = self.routes[r]
        for p, c in enumerate(route):
            self.rid[c] = r
            self.pos[c] = p
        self.load[r] = sum(self.q[c] for c in route)
        self.rcost[r] = route_cost(self.inst, route)
        self.arcs[r] = route_arcs(route)

    def _excess(self, load):
        return max(0, load - self.cap)

    def _relocate(self, i, j, after):
        ri, rj = self.rid[i], self.rid[j]
        if ri == rj:
            r = [c for c in self.routes[ri] if c != i]
            r.insert(r.index(j) + (1 if after else 0), i)
            if r == self.routes[ri]:
                return None
            return [(ri, r)]
        a = [c for c in self.routes[ri] if c != i]
        b = list(self.routes[rj])
        b.insert(b.index(j) + (1 if after else 0), i)
        return [(ri, a), (rj, b)]

    def _swap(self, i, j):
        ri, rj = self.rid[i], self.rid[j]
        pi, pj = self.pos[i], self.pos[j]
        if ri == rj:
            r = list(self.routes[ri])
            r[pi], r[pj] = j, i
            return [(ri, r)]
        a = list(self.routes[ri])
        b = list(self.routes[rj])
        a[pi], b[pj] = j, i
        return [(ri, a), (rj, b)]

    def _reverse(self, i, j, first):
        r = self.rid[i]
        p, q = self.pos[i], self.pos[j]
        if q > p + 1:
            lo, hi = (p + 1, q) if first else (p, q - 1)
        elif p > q + 1:
            lo, hi = (q + 1, p) if first else (q, p - 1)
        else:
            return None
        route = list(self.routes[r])
        route[lo:hi + 1] = route[lo:hi + 1][::-1]
        return [(r, route)]

    def _two_opt_star(self, i, j, first):
        ri, rj = self.rid[i], self.rid[j]
        R, S = self.routes[ri], self.routes[rj]
        p, q = self.pos[i], self.pos[j]
        if first:
            return [(ri, R[:p + 1] + S[q:]), (rj, S[:q] + R[p + 1:])]
        return [(ri, R[:p + 1] + S[:q + 1][::-1]), (rj, R[p + 1:][::-1] + S[q + 1:])]

    def _evaluate(self, change):
        d_dist = 0
        d_exc = 0
        for r, route in change:
            d_dist += route_cost(self.inst, route) - self.rcost[r]
            load = sum(self.q[c] for c in route)
            d_exc += self._excess(load) - self._excess(self.load[r])
        return d_dist, d_exc

    def _changed_arcs(self, change):
        old_arcs = set()
        new_arcs = set()
        for r, route in change:
            old_arcs |= self.arcs[r]
            new_arcs |= route_arcs(route)
        return old_arcs - new_arcs, new_arcs - old_arcs

    def _best_move(self, it, best_dist):
        best_f = float("inf")
        best = None
        cur_exc = sum(self._excess(L) for L in self.load)
        cur_dist = sum(self.rcost)
        empty = next((r for r in range(len(self.routes)) if not self.routes[r]), None)
        for i in range(1, self.n + 1):
            candidates = []
            if empty is not None and len(self.routes[self.rid[i]]) > 1:
                src = self.rid[i]
                candidates.append([(src, [c for c in self.routes[src] if c != i]), (empty, [i])])
            for j in self.nbr[i]:
                candidates.append(self._relocate(i, j, True))
                candidates.append(self._relocate(i, j, False))
                candidates.append(self._swap(i, j))
                if self.rid[i] == self.rid[j]:
                    for first in (True, False):
                        candidates.append(self._reverse(i, j, first))
                else:
                    candidates.append(self._two_opt_star(i, j, True))
                    candidates.append(self._two_opt_star(i, j, False))
            for change in candidates:
                if change is None:
                    continue
                d_dist, d_exc = self._evaluate(change)
                f = d_dist + self.alpha * d_exc
                if f >= best_f:
                    continue
                removed, added = self._changed_arcs(change)
                if not removed and not added:
                    continue
                is_tabu = any(self.tabu.get(a, 0) > it for a in added)
                aspirated = cur_exc + d_exc == 0 and cur_dist + d_dist < best_dist - 1e-7
                if is_tabu and not aspirated:
                    continue
                best_f = f
                best = (change, removed)
        return best

    def _apply(self, move, it):
        change, removed = move
        for r, route in change:
            self.routes[r] = route
        for r, route in change:
            self._refresh(r)
        for a in removed:
            self.tabu[a] = it + self.rng.randint(*self.tenure)

    def _perturb(self, base):
        routes = [list(r) for r in base]
        count = max(2, self.n // 8)
        victims = self.rng.sample(range(1, self.n + 1), count)
        chosen = set(victims)
        routes = [[c for c in r if c not in chosen] for r in routes]
        routes += [[] for _ in range(self.K - len(routes))]
        loads = [sum(self.q[c] for c in r) for r in routes]
        self.rng.shuffle(victims)
        for c in victims:
            r, p = cheapest_position(self.inst, routes, loads, c)
            routes[r].insert(p, c)
            loads[r] += self.q[c]
        return routes

    def run(self):
        start = time.perf_counter()
        self._set_solution(reduce_fleet(self.inst, clarke_wright(self.inst)))
        self.tabu = {}
        n1 = self.n + 1
        mean_d = sum(sum(row) for row in self.d) / (n1 * n1)
        mean_q = sum(self.q) / n1
        self.alpha = max(mean_d / max(mean_q, 1), 1e-3)
        best_dist = float("inf")
        best_routes = None
        best_time = 0.0
        if sum(self._excess(L) for L in self.load) == 0:
            best_dist = sum(self.rcost)
            best_routes = [list(r) for r in self.routes if r]
            self.history.append((0.0, best_dist))
        last_improve = 0
        window = []
        it = 0
        while it < self.max_iter:
            it += 1
            if time.perf_counter() - start >= self.time_limit:
                break
            move = self._best_move(it, best_dist)
            if move is None:
                self.tabu = {}
                continue
            self._apply(move, it)
            cur_dist = sum(self.rcost)
            cur_exc = sum(self._excess(L) for L in self.load)
            window.append(cur_exc == 0)
            if len(window) == 10:
                if all(window):
                    self.alpha = max(self.alpha / 1.5, 1e-3)
                elif not any(window):
                    self.alpha = min(self.alpha * 1.5, 1e6)
                window = []
            if cur_exc == 0 and cur_dist < best_dist - 1e-7:
                best_dist = cur_dist
                best_routes = [list(r) for r in self.routes if r]
                best_time = time.perf_counter() - start
                last_improve = it
                self.history.append((best_time, best_dist))
            if it - last_improve > self.stagnation:
                base = best_routes if best_routes is not None else self.routes
                self._set_solution(self._perturb(base))
                self.tabu = {}
                last_improve = it
        self.iterations = it
        self.elapsed = time.perf_counter() - start
        self.best_time = best_time
        return best_routes, best_dist