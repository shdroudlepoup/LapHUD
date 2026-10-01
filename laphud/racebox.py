"""
Lecture d'un export CSV RaceBox (Mini / Mini S / Micro).

Export conseillé dans l'app RaceBox : « Custom », « Full Date/Time » en UTC.
Colonnes utilisées : Time, Latitude, Longitude, Altitude, Speed (km/h),
GForceX (longitudinal), GForceY (latéral), Lap.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone

import numpy as np


@dataclass
class RaceBoxLog:
    path: str
    t0: datetime            # heure UTC du premier échantillon
    t: np.ndarray           # secondes depuis t0
    lat: np.ndarray
    lon: np.ndarray
    alt: np.ndarray
    speed: np.ndarray       # m/s
    g_lon: np.ndarray       # G, + = accélération (avant recalage)
    g_lat: np.ndarray       # G latéral brut
    lap: np.ndarray         # n° de tour officiel (0 = tour de sortie / rentrée)
    utc: bool               # False si l'heure exportée était locale

    @property
    def duration(self):
        return float(self.t[-1]) if len(self.t) else 0.0

    @property
    def has_laps(self):
        return bool((self.lap > 0).any())


def _parse_time(s):
    s = s.strip()
    utc = s.endswith("Z")
    s = s.rstrip("Z")
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc), utc
        except ValueError:
            pass
    raise ValueError(f"date illisible : {s!r}")


def _col(row, *names, default=None):
    for n in names:
        if n in row and row[n] not in (None, ""):
            return row[n]
    return default


def _is_header(line):
    return "Time" in line and "Latitude" in line and "Speed" in line


def _skip_to_header(fh, max_lines=60):
    """Avance jusqu'à la ligne des colonnes. L'option « Include session description
    header » de l'export ajoute quelques lignes de description avant."""
    for _ in range(max_lines):
        pos = fh.tell()
        line = fh.readline()
        if not line:
            return False
        if _is_header(line):
            fh.seek(pos)
            return True
    return False


def is_racebox_csv(path):
    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return _skip_to_header(fh)
    except (OSError, UnicodeDecodeError):
        return False


def load(path):
    times, rows, utc_flag = [], [], True
    with open(path, encoding="utf-8-sig", newline="") as fh:
        if not _skip_to_header(fh):
            raise ValueError("ce n'est pas un export CSV RaceBox (colonnes introuvables)")
        for r in csv.DictReader(fh):
            try:
                ts, utc = _parse_time(r["Time"])
                rows.append((
                    float(r["Latitude"]), float(r["Longitude"]),
                    float(_col(r, "Altitude", default=0)),
                    float(r["Speed"]) / 3.6,
                    float(_col(r, "GForceX", default=0)),
                    float(_col(r, "GForceY", default=0)),
                    int(float(_col(r, "Lap", default=0))),
                ))
                times.append(ts)
                utc_flag = utc_flag and utc
            except (KeyError, ValueError):
                continue
    if len(rows) < 10:
        raise ValueError("CSV RaceBox vide ou illisible")
    a = np.array(rows, dtype=float)
    t0 = times[0]
    t = np.array([(x - t0).total_seconds() for x in times])
    # échantillons dupliqués / désordonnés -> on garde une série strictement croissante
    keep = np.concatenate([[True], np.diff(t) > 0])
    a, t = a[keep], t[keep]
    return RaceBoxLog(path, t0, t, a[:, 0], a[:, 1], a[:, 2], a[:, 3],
                      a[:, 4], a[:, 5], a[:, 6].astype(int), utc_flag)
