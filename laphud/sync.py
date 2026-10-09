"""
Synchronisation automatique vidéo GoPro <-> données RaceBox.

1. Synchro grossière : heure GPS de la GoPro (GPSU) comparée à l'heure UTC du CSV.
   Précise à ~1 s seulement, et absente si la caméra n'a pas capté le GPS.
2. Synchro fine : on compare l'accéléromètre de la GoPro (200 Hz) aux G du RaceBox.
   Freinages et virages laissent la même « signature » dans les deux capteurs ; le
   décalage qui les superpose le mieux est le bon, à quelques centièmes près.
   La caméra peut être montée n'importe comment (casque, arceau…) : on teste toutes
   les combinaisons d'axes. Sans heure GPS, on cherche sur toute la durée.

Convention : temps_session = temps_vidéo - offset
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .i18n import Msg

FS = 25.0                    # Hz, grille commune
MIN_OVERLAP_S = 60.0


@dataclass
class SyncResult:
    offset: float            # s : temps_session = temps_vidéo - offset
    method: str              # "imu" ou "gps"
    confidence: float        # 0..1 (corrélation au pic)
    coarse: float | None     # offset d'après l'heure GPS seule
    note: list = field(default_factory=list)   # liste de Msg

    @property
    def quality(self):
        if self.method != "imu":
            return "approx"
        return "excellent" if self.confidence >= 0.6 else "ok" if self.confidence >= 0.35 else "faible"


def _band(x, lo=0.15, hi=2.5):
    """Passe-bande simple : garde les manœuvres (freinages, virages), retire
    la gravité, la dérive et les vibrations moteur. Sortie normalisée."""
    def ma(a, w):
        w = max(1, int(round(w)))
        pad = w // 2
        return np.convolve(np.pad(a, (pad, w - 1 - pad), mode="edge"), np.ones(w) / w, mode="valid")
    y = ma(x, FS / hi) - ma(x, FS / lo)
    s = y.std()
    return (y - y.mean()) / s if s > 0 else y * 0


def _xcorr(g, r):
    """c[L] = moyenne de g[j+L]·r[j] sur le recouvrement, pour tous les L possibles.
    Renvoie (lags, c, recouvrement en échantillons)."""
    ng, nr = len(g), len(r)
    m = 1 << int(np.ceil(np.log2(ng + nr)))
    cc = np.fft.irfft(np.fft.rfft(g, m) * np.conj(np.fft.rfft(r, m)), m)
    lags = np.arange(-(nr - 1), ng)
    ov = np.minimum(nr, ng - lags) - np.maximum(0, -lags)
    return lags, cc[lags % m] / np.maximum(ov, 1), ov


def synchronize(clip, log, search=8.0):
    """Offset vidéo -> session. `search` = tolérance (s) autour de la synchro GPS."""
    coarse, note = None, []
    if clip.gps_anchor is not None:
        coarse = (log.t0 - clip.gps_anchor).total_seconds()
        hours = 0 if log.utc else round(coarse / 3600.0)
        if hours:                      # CSV exporté en heure locale
            coarse -= hours * 3600.0
            note.append(Msg("note_local_tz", h=hours))
    else:
        note.append(Msg("note_no_gps_time"))

    if not clip.has_imu:
        return SyncResult(coarse or 0.0, "gps", 0.0, coarse,
                          note or [Msg("note_no_imu")])

    tg = np.arange(clip.accl_t[0], clip.accl_t[-1], 1.0 / FS)       # temps vidéo
    tr = np.arange(log.t[0], log.t[-1], 1.0 / FS)                    # temps session
    Gs = [_band(np.interp(tg, clip.accl_t, clip.accl[:, k])) for k in range(3)]
    Rs = [_band(np.interp(tr, log.t, s)) for s in (log.g_lon, log.g_lat)]

    score = peak = None
    for g in Gs:
        for r in Rs:
            lags, c, ov = _xcorr(g, r)
            score = c * c if score is None else score + c * c
            peak = np.abs(c) if peak is None else np.maximum(peak, np.abs(c))
    # offset correspondant à chaque lag : session j <-> vidéo j+L
    offs = tg[0] - tr[0] + lags / FS
    ok = ov >= MIN_OVERLAP_S * FS
    if coarse is not None:
        ok &= np.abs(offs - coarse) <= search
    if not ok.any():
        return SyncResult(coarse or 0.0, "gps", 0.0, coarse,
                          [Msg("note_no_overlap")])
    sc = np.where(ok, score, -1.0)
    k = int(np.argmax(sc))
    frac = 0.0
    if 0 < k < len(sc) - 1 and ok[k - 1] and ok[k + 1]:
        y0, y1, y2 = sc[k - 1], sc[k], sc[k + 1]
        den = y0 - 2 * y1 + y2
        if den:
            frac = 0.5 * (y0 - y2) / den
    offset = float(offs[k] + frac / FS)
    conf = float(peak[k])
    far = ok & (np.abs(offs - offs[k]) > 1.5)
    if far.any() and sc[far].max() > 0.8 * sc[k]:
        conf *= 0.5
        note.append(Msg("note_ambiguous"))
    return SyncResult(offset, "imu", conf, coarse, note)


def best_match(clip, logs):
    """Trouve le CSV qui correspond à la vidéo. Avec l'heure GPS : le plus proche dans
    le temps ; sans : celui dont les G collent le mieux à l'accéléromètre."""
    if not logs:
        return None, None
    if clip.gps_anchor is not None:
        def span(L):
            d = (L.t0 - clip.gps_anchor).total_seconds()
            if not L.utc:                  # CSV en heure locale : fuseau inconnu
                d -= round(d / 3600.0) * 3600.0
            return d, d + L.duration

        def gap(L):
            # écart entre la vidéo et l'intervalle couvert par le CSV (0 s'ils se chevauchent)
            s0, s1 = span(L)
            return max(0.0, max(0.0, s0) - min(clip.duration, s1))

        def overlap(L):
            s0, s1 = span(L)
            return max(0.0, min(clip.duration, s1) - max(0.0, s0))
        # vidéo à cheval sur deux CSV : on prend celui qui en couvre la plus grande partie
        cand = sorted(logs, key=lambda L: (gap(L), -overlap(L)))
        if gap(cand[0]) < 600:
            return cand[0], synchronize(clip, cand[0])
        return None, None          # l'heure GPS est sûre : aucun CSV n'a été enregistré à ce moment-là
    # pas d'heure GPS : on cherche le CSV dont les G collent à l'accéléromètre,
    # et on n'accepte qu'une ressemblance franche (sinon c'est une autre session)
    results = [(L, synchronize(clip, L)) for L in logs]
    results = [(L, r) for L, r in results if r.method == "imu" and r.confidence >= 0.3]
    if not results:
        return None, None
    return max(results, key=lambda x: x[1].confidence)
