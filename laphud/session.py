"""
Session de roulage : tout ce que le HUD affiche, calculé une fois pour toutes.

- G recalées (sens des axes vérifié sur la physique, biais retiré, vibrations lissées) ;
- tours chronométrés au millième grâce à l'intersection exacte avec la ligne ;
- meilleur tour et delta PROGRESSIFS (jamais de « spoiler » sur un tour pas encore fait) ;
- delta par projection sur la trajectoire du meilleur tour (insensible aux écarts de ligne).

state_at(t) renvoie l'état du HUD à n'importe quel instant (interpolé, donc fluide
à 30 ou 60 images/s).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

G = 9.80665
LAP_FLASH_S = 5.0           # durée d'affichage du temps du tour qui vient de se terminer
G_TRAIL_S = 0.8             # traînée du point de G


def _smooth(a, w):
    w = int(w)
    if w <= 1 or len(a) < w:
        return a
    pad = w // 2
    ap = np.pad(a, (pad, w - 1 - pad), mode="edge")
    return np.convolve(ap, np.ones(w) / w, mode="valid")


@dataclass
class Lap:
    number: int             # 0 = tour de sortie / rentrée
    kind: str               # "out", "timed", "in"
    t_start: float
    t_end: float
    i0: int                 # premier échantillon
    i1: int                 # dernier échantillon (exclu)

    @property
    def duration(self):
        return self.t_end - self.t_start


@dataclass
class HudState:
    active: bool = False
    speed_kmh: float = 0.0
    lap_kind: str = "out"
    lap_number: int = 0
    lap_elapsed: float | None = None
    last: float | None = None
    best: float | None = None
    delta: float | None = None
    flash: dict | None = None           # tour qui vient de se terminer
    map_xy: tuple = (0.5, 0.5)
    g_lat: float = 0.0                  # + = virage à droite (force ressentie vers la gauche)
    g_lon: float = 0.0                  # + = accélération
    g_trail: list = field(default_factory=list)


class Session:
    def __init__(self, log):
        self.log = log
        self.t = log.t
        n = len(self.t)
        self.fs = (n - 1) / max(self.t[-1], 1e-6)

        # projection locale en mètres
        lat0 = math.radians(float(np.median(log.lat)))
        self.x = np.radians(log.lon - np.median(log.lon)) * math.cos(lat0) * 6371000.0
        self.y = np.radians(log.lat - np.median(log.lat)) * 6371000.0
        self.dist = np.concatenate([[0], np.cumsum(np.hypot(np.diff(self.x), np.diff(self.y)))])
        self.speed = _smooth(log.speed, max(1, round(self.fs * 0.12)))

        self._fix_g()
        self._build_laps()
        self._build_delta()
        self._build_map()

    # ------------------------------------------------------------------ G
    def _physics_g(self):
        """G déduites de la vitesse et de la trajectoire (référence de sens)."""
        # trajectoire lissée d'abord : le GPS « tremble » de quelques dizaines de cm, ce qui
        # suffit à fausser le cap (et donc les G latérales) si on le dérive directement
        t = self.t
        w = max(1, round(self.fs * 0.5))
        xs, ys = _smooth(self.x, w), _smooth(self.y, w)
        hdg = _smooth(np.unwrap(np.arctan2(np.gradient(xs, t), np.gradient(ys, t))), w)
        yaw = np.gradient(hdg, t)                          # rad/s, + = vers la droite
        moving = (self.speed > 5.0).astype(float)          # à l'arrêt, le cap ne veut rien dire
        lat = _smooth(self.speed * yaw / G * moving, round(self.fs * 0.4))
        lon = _smooth(np.gradient(_smooth(self.speed, w), t) / G, round(self.fs * 0.4))
        # une voiture de route dépasse rarement 1,5 G : au-delà c'est du bruit GPS
        return np.clip(lat, -1.6, 1.6), np.clip(lon, -1.6, 1.6)

    def _fix_g(self):
        lat_d, lon_d = self._physics_g()
        raw = {"x": self.log.g_lon, "y": self.log.g_lat}
        moving = self.speed > 8.0
        self.g_flags = {}
        if moving.sum() < self.fs * 20:
            lat, lon = lat_d, lon_d
            self.g_flags["source"] = "gps"
        else:
            # pour chaque axe attendu, on choisit l'axe et le signe du capteur qui collent
            # à la physique (le RaceBox se trompe parfois de sens à la calibration)
            def score(sig, target):
                a, b = sig[moving], target[moving]
                if a.std() > 1e-6 and b.std() > 1e-6:
                    return float(np.corrcoef(a, b)[0, 1])
                # signal constant (virage permanent, axe vide…) : on compare les signes moyens
                den = math.sqrt(float(np.mean(a * a) * np.mean(b * b)))
                return float(np.mean(a * b)) / den if den > 1e-9 else 0.0

            def pick(target, avoid=None):
                best = (None, None, 0.0)
                for name, sig in raw.items():
                    if name != avoid:
                        c = score(sig, target)
                        if abs(c) > abs(best[2]):
                            best = (name, sig, c)
                return best

            nl, slon, clon = pick(lon_d)
            na, slat, clat = pick(lat_d, avoid=nl)

            def fixed(sig, c, phys):
                if sig is None or abs(c) < 0.2:      # capteur inexploitable : G calculées par GPS
                    return phys
                out = sig * np.sign(c)
                # biais (capteur pas parfaitement à plat) : écart médian à la physique
                return out - np.median((out - phys)[moving])

            lon = fixed(slon, clon, lon_d)
            lat = fixed(slat, clat, lat_d)
            self.g_flags.update(source="racebox", lon_axis=nl, lat_axis=na,
                                lon_corr=round(abs(clon), 2), lat_corr=round(abs(clat), 2))
        w = max(1, round(self.fs * 0.2))                   # anti-vibrations
        self.g_lon = np.clip(_smooth(lon, w), -2.5, 2.5)
        self.g_lat = np.clip(_smooth(lat, w), -2.5, 2.5)

    # ------------------------------------------------------------------ tours
    def _build_laps(self):
        lc = self.log.lap
        n = len(lc)
        cuts = [i for i in range(1, n) if lc[i] != lc[i - 1]]
        self.finish = None
        tcut = {}
        if cuts:
            # ligne d'arrivée = position médiane des changements de tour, normale au sens de marche
            px = float(np.median([self.x[i] for i in cuts]))
            py = float(np.median([self.y[i] for i in cuts]))
            hx = float(np.median([self.x[min(i + 2, n - 1)] - self.x[max(i - 2, 0)] for i in cuts]))
            hy = float(np.median([self.y[min(i + 2, n - 1)] - self.y[max(i - 2, 0)] for i in cuts]))
            hn = math.hypot(hx, hy) or 1.0
            hx, hy = hx / hn, hy / hn
            self.finish = (px, py, hx, hy)
            for i in cuts:
                tcut[i] = self._crossing_time(i, px, py, hx, hy)

        bounds = [0] + cuts + [n]
        laps = []
        seen_timed = False
        for a, b in zip(bounds[:-1], bounds[1:]):
            num = int(lc[a])
            ts = tcut.get(a, float(self.t[a]))
            te = tcut.get(b, float(self.t[b - 1]))
            if num >= 1:
                kind = "timed" if b < n else "partial"   # dernier tour pas fini = pas de temps
                seen_timed = True
            else:
                kind = "in" if seen_timed else "out"
            laps.append(Lap(num, kind, ts, te, a, b))
        self.laps = laps
        self.timed = [L for L in laps if L.kind == "timed"]

    def _crossing_time(self, i, px, py, hx, hy):
        """Instant exact du franchissement de la ligne autour de l'échantillon i."""
        d = lambda k: (self.x[k] - px) * hx + (self.y[k] - py) * hy
        for k in range(max(i - 3, 1), min(i + 3, len(self.t))):
            d0, d1 = d(k - 1), d(k)
            if d0 < 0 <= d1:
                f = -d0 / (d1 - d0)
                return float(self.t[k - 1] + f * (self.t[k] - self.t[k - 1]))
        return float(self.t[i] - 0.5 / self.fs)

    # ------------------------------------------------------------------ delta
    def _build_delta(self):
        n = len(self.t)
        self.delta = np.full(n, np.nan)
        self.best_before = {}          # n° d'index de tour -> (meilleur tour fini avant)
        best = None
        for k, L in enumerate(self.laps):
            self.best_before[k] = best
            if L.kind in ("timed", "partial") and best is not None:
                self.delta[L.i0:L.i1] = self._delta_vs(L, best)
            if L.kind == "timed" and (best is None or L.duration < best.duration):
                best = L

    def _delta_vs(self, cur, ref):
        rx, ry = self.x[ref.i0:ref.i1], self.y[ref.i0:ref.i1]
        rt = self.t[ref.i0:ref.i1] - ref.t_start
        cx, cy = self.x[cur.i0:cur.i1], self.y[cur.i0:cur.i1]
        ct = self.t[cur.i0:cur.i1] - cur.t_start
        m = len(rx)
        out = np.empty(len(cx))
        j = 0
        back, ahead = int(self.fs * 0.5), int(self.fs * 3)
        for k in range(len(cx)):
            lo, hi = max(0, j - back), min(m - 1, j + ahead)
            seg = slice(lo, hi + 1)
            dd = (rx[seg] - cx[k]) ** 2 + (ry[seg] - cy[k]) ** 2
            j = lo + int(np.argmin(dd))
            # affinage sur le segment voisin (projection orthogonale)
            j2 = min(j + 1, m - 1)
            ex, ey = rx[j2] - rx[j], ry[j2] - ry[j]
            el = ex * ex + ey * ey
            f = 0.0 if el == 0 else max(0.0, min(1.0, ((cx[k] - rx[j]) * ex + (cy[k] - ry[j]) * ey) / el))
            out[k] = ct[k] - (rt[j] + f * (rt[j2] - rt[j]))
        return _smooth(out, max(1, round(self.fs * 0.3)))

    # ------------------------------------------------------------------ carte
    def _build_map(self):
        ref = min(self.timed, key=lambda L: L.duration) if self.timed else None
        sl = slice(ref.i0, ref.i1) if ref else slice(0, len(self.t))
        x, y = self.x[sl], self.y[sl]
        cx, cy = (x.min() + x.max()) / 2, (y.min() + y.max()) / 2
        self.map_scale = max(x.max() - x.min(), y.max() - y.min(), 1.0)
        self.map_center = (cx, cy)
        self.map_outline = np.column_stack([(x - cx) / self.map_scale + 0.5,
                                            0.5 - (y - cy) / self.map_scale])
        self.map_finish = None
        if self.finish:
            px, py, hx, hy = self.finish
            self.map_finish = ((px - cx) / self.map_scale + 0.5, 0.5 - (py - cy) / self.map_scale,
                               hx, -hy)

    # ------------------------------------------------------------------ état HUD
    def _lap_index(self, t):
        for k, L in enumerate(self.laps):
            if t < L.t_end or k == len(self.laps) - 1:
                return k
        return len(self.laps) - 1

    def state_at(self, t):
        """État du HUD au temps de session t (secondes depuis le début du CSV)."""
        if t < self.t[0] or t > self.t[-1]:
            return HudState(active=False)
        s = HudState(active=True)
        s.speed_kmh = float(np.interp(t, self.t, self.speed)) * 3.6
        s.g_lat = float(np.interp(t, self.t, self.g_lat))
        s.g_lon = float(np.interp(t, self.t, self.g_lon))
        tt = t - np.linspace(0, G_TRAIL_S, 12)
        s.g_trail = list(zip(np.interp(tt, self.t, self.g_lat), np.interp(tt, self.t, self.g_lon)))
        x = float(np.interp(t, self.t, self.x)); y = float(np.interp(t, self.t, self.y))
        s.map_xy = ((x - self.map_center[0]) / self.map_scale + 0.5,
                    0.5 - (y - self.map_center[1]) / self.map_scale)

        k = self._lap_index(t)
        L = self.laps[k]
        s.lap_kind = "timed" if L.kind == "partial" else L.kind
        s.lap_number = L.number
        if s.lap_kind == "timed":
            s.lap_elapsed = max(0.0, t - L.t_start)
        done = [P for P in self.laps[:k] if P.kind == "timed"]
        if done:
            s.last = done[-1].duration
            s.best = min(P.duration for P in done)
        if s.lap_kind == "timed":
            d = float(np.interp(t, self.t, self.delta))
            s.delta = None if math.isnan(d) else d
        # flash du tour qui vient de se terminer
        if done and t - done[-1].t_end < LAP_FLASH_S:
            P = done[-1]
            prev = [Q.duration for Q in done[:-1]]
            s.flash = {"number": P.number, "time": P.duration,
                       "is_best": not prev or P.duration < min(prev),
                       "vs_best": (P.duration - min(prev)) if prev else None,
                       "age": t - P.t_end}
        return s

    # ------------------------------------------------------------------ résumé
    def summary(self):
        return {
            "laps": [(L.number, round(L.duration, 3)) for L in self.timed],
            "best": round(min((L.duration for L in self.timed), default=float("nan")), 3),
            "vmax": round(float(self.speed.max() * 3.6), 1),
            "g": self.g_flags,
        }
