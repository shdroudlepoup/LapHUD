"""
Lecture d'un export CSV de RaceChrono (format v3 : « Export → CSV (v3) » dans l'app).

Colonnes utilisées : timestamp (heure Unix UTC), lap_number, latitude, longitude,
altitude, speed (m/s), lateral_acc et longitudinal_acc (G).

Les données sont converties au même format qu'un log RaceBox : tout le reste de
LapHUD (tours, delta, HUD, synchro) fonctionne pareil.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone

import numpy as np

from .i18n import Msg
from .racebox import RaceBoxLog


def is_racechrono_csv(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace") as fh:
            head = [fh.readline() for _ in range(3)]
        return "RaceChrono" in head[0] and head[1].strip().startswith("Format,3")
    except OSError:
        return False


def load(path):
    with open(path, encoding="utf-8-sig", newline="", errors="replace") as fh:
        rows = csv.reader(fh)
        header = None
        for r in rows:
            if r and r[0] == "timestamp":
                header = r
                break
        if header is None:
            raise ValueError(Msg("err_csv_columns"))
        next(rows, None)              # ligne des unités
        next(rows, None)              # ligne des sources
        col = {}
        for i, name in enumerate(header):
            col.setdefault(name, i)   # certaines colonnes (speed…) apparaissent deux fois
        need = ("timestamp", "latitude", "longitude", "speed")
        if any(n not in col for n in need):
            raise ValueError(Msg("err_csv_columns"))

        def val(r, name, default=np.nan):
            i = col.get(name)
            if i is None or i >= len(r) or r[i] == "":
                return default
            try:
                return float(r[i])
            except ValueError:
                return default

        data = []
        for r in rows:
            ts, la, lo = val(r, "timestamp"), val(r, "latitude"), val(r, "longitude")
            if np.isnan(ts) or np.isnan(la) or np.isnan(lo):
                continue
            data.append((ts, la, lo, val(r, "altitude", 0.0), val(r, "speed", 0.0),
                         val(r, "longitudinal_acc", 0.0), val(r, "lateral_acc", 0.0),
                         val(r, "lap_number", 0.0)))
    if len(data) < 10:
        raise ValueError(Msg("err_csv_empty"))
    a = np.array(data, dtype=float)
    a = a[np.argsort(a[:, 0], kind="stable")]
    keep = np.concatenate([[True], np.diff(a[:, 0]) > 0])
    a = a[keep]
    a[:, 5:7] = np.nan_to_num(a[:, 5:7])
    lap = np.nan_to_num(a[:, 7]).astype(int)
    t0 = datetime.fromtimestamp(a[0, 0], tz=timezone.utc)
    return RaceBoxLog(path, t0, a[:, 0] - a[0, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4],
                      a[:, 5], a[:, 6], lap, True)
