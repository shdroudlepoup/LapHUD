"""Tests sur données simulées (aucun fichier vidéo nécessaire) : python -m unittest"""
import math
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np

from racesync.gopro import GoProClip
from racesync.racebox import RaceBoxLog
from racesync.session import Session
from racesync import sync

T0 = datetime(2026, 5, 31, 12, 0, 0, tzinfo=timezone.utc)
R, V, FS = 100.0, 20.0, 25.0          # circuit circulaire de 100 m, 20 m/s, RaceBox 25 Hz
LAP = 2 * math.pi * R / V             # 31.4159 s


def circle_log(n_laps=4, start_angle=-0.3, phase_noise=0.0):
    """Voiture sur un cercle (sens horaire), départ un peu avant la ligne (angle 0, au nord)."""
    t = np.arange(0, (n_laps + 0.6) * LAP, 1 / FS)
    ang = start_angle + V / R * t               # radians parcourus
    lat0, lon0 = 47.86, -1.90
    x, y = R * np.sin(ang), R * np.cos(ang)     # horaire vu du dessus, nord = +y
    lat = lat0 + np.degrees(y / 6371000.0)
    lon = lon0 + np.degrees(x / (6371000.0 * math.cos(math.radians(lat0))))
    laps_done = np.floor(ang / (2 * math.pi)).astype(int)    # passages de la ligne (angle 2kπ)
    lap = np.where(laps_done < 0, 0, laps_done + 1)
    lap[lap > n_laps] = 0                                     # in-lap
    g_lat = np.full_like(t, V * V / R / 9.80665)              # virage à droite permanent
    return RaceBoxLog("sim.csv", T0, t, lat, lon, np.zeros_like(t), np.full_like(t, V),
                      np.zeros_like(t), -g_lat, lap, True)   # axe latéral volontairement inversé


class SessionTests(unittest.TestCase):
    def test_lap_times_exact(self):
        s = Session(circle_log())
        self.assertEqual(len(s.timed), 4)
        for L in s.timed:
            self.assertAlmostEqual(L.duration, LAP, delta=0.005)

    def test_delta_zero_on_identical_laps(self):
        s = Session(circle_log())
        st = s.state_at(s.timed[2].t_start + LAP / 2)
        self.assertIsNotNone(st.delta)
        self.assertAlmostEqual(st.delta, 0.0, delta=0.03)

    def test_best_is_progressive(self):
        s = Session(circle_log())
        st = s.state_at(s.timed[0].t_start + 5)
        self.assertIsNone(st.best)           # premier tour : pas encore de meilleur tour
        st = s.state_at(s.timed[1].t_start + 5)
        self.assertAlmostEqual(st.best, LAP, delta=0.005)

    def test_lateral_axis_auto_flip(self):
        s = Session(circle_log())
        # virage à droite permanent -> G latéral positif malgré l'axe inversé dans le CSV
        self.assertGreater(float(np.median(s.g_lat)), 0.3)


class SyncTests(unittest.TestCase):
    def _signals(self, true_offset, anchor_error):
        rng = np.random.default_rng(1)
        n = int(600 * FS)
        t = np.arange(n) / FS
        # manœuvres aléatoires lissées (freinages / virages)
        def maneuvers():
            x = rng.normal(size=n)
            k = np.ones(int(FS)) / FS
            return np.convolve(x, k, mode="same") * 0.6
        g_lon, g_lat = maneuvers(), maneuvers()
        log = RaceBoxLog("sim.csv", T0, t, np.zeros(n), np.zeros(n), np.zeros(n), np.full(n, 30.0),
                         g_lon, g_lat, np.zeros(n, int), True)
        # GoPro : 200 Hz, axes mélangés (caméra tournée), bruit + gravité
        ta = np.arange(0, 560, 1 / 200)
        ts = ta - true_offset
        lon_v = np.interp(ts, t, g_lon) * 9.81
        lat_v = np.interp(ts, t, g_lat) * 9.81
        accl = np.column_stack([9.81 + 0.3 * lon_v, -lat_v, 0.8 * lon_v]) + rng.normal(0, 1.5, (len(ta), 3))
        anchor = T0 + timedelta(seconds=-true_offset + anchor_error)
        clip = GoProClip("sim.mp4", 560, 3840, 2160, 59.94, None, ta, accl,
                         np.zeros(0), np.zeros((0, 4)), anchor)
        return clip, log

    def test_imu_sync_with_gps(self):
        clip, log = self._signals(true_offset=-6.68, anchor_error=1.1)
        r = sync.synchronize(clip, log)
        self.assertEqual(r.method, "imu")
        self.assertAlmostEqual(r.offset, -6.68, delta=0.03)

    def test_imu_sync_without_gps(self):
        clip, log = self._signals(true_offset=-23.4, anchor_error=0)
        clip.gps_anchor = None
        r = sync.synchronize(clip, log)
        self.assertAlmostEqual(r.offset, -23.4, delta=0.03)


if __name__ == "__main__":
    unittest.main()
