"""
Lecture de la télémétrie GoPro (GPMF) directement dans le fichier MP4.

On lit la table d'échantillons de la piste « gpmd » (quelques Mo) au lieu de faire
passer tout le fichier (souvent 4 à 8 Go) dans ffmpeg : l'analyse prend une
fraction de seconde.

Extrait :
  - l'accéléromètre (ACCL, ~200 Hz) et le gyroscope (GYRO) — sert à la synchro ;
  - le GPS (GPS5 ou GPS9) et l'heure GPS (GPSU) — sert à la synchro grossière ;
  - la durée, la résolution et la cadence de la vidéo.
"""
from __future__ import annotations

import os
import struct
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import numpy as np

from .i18n import Msg

# ---------------------------------------------------------------------------
# MP4 : lecture minimale des boîtes nécessaires
# ---------------------------------------------------------------------------
_CONTAINERS = {b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf"}
_MAC_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)


def _iter_boxes(f, start, end):
    pos = start
    while pos + 8 <= end:
        f.seek(pos)
        hdr = f.read(8)
        if len(hdr) < 8:
            return
        size, typ = struct.unpack(">I4s", hdr)
        hlen = 8
        if size == 1:
            size = struct.unpack(">Q", f.read(8))[0]
            hlen = 16
        elif size == 0:
            size = end - pos
        if size < hlen:
            return
        yield typ, pos + hlen, pos + size
        pos += size


def _read(f, start, end):
    f.seek(start)
    return f.read(end - start)


@dataclass
class _Track:
    handler: bytes = b""
    fmt: bytes = b""
    timescale: int = 1
    duration: int = 0
    width: int = 0
    height: int = 0
    stts: list = field(default_factory=list)
    stsz: list = field(default_factory=list)
    stsc: list = field(default_factory=list)
    chunks: list = field(default_factory=list)


def _parse_trak(f, start, end):
    tr = _Track()

    def walk(s, e):
        for typ, a, b in _iter_boxes(f, s, e):
            if typ in _CONTAINERS:
                walk(a, b)
            elif typ == b"mdhd":
                d = _read(f, a, b)
                if d[0] == 1:
                    tr.timescale, tr.duration = struct.unpack(">IQ", d[20:32])
                else:
                    tr.timescale, tr.duration = struct.unpack(">II", d[12:20])
            elif typ == b"hdlr":
                tr.handler = _read(f, a, b)[8:12]
            elif typ == b"tkhd":
                d = _read(f, a, b)
                tr.width = struct.unpack(">I", d[-8:-4])[0] >> 16
                tr.height = struct.unpack(">I", d[-4:])[0] >> 16
            elif typ == b"stsd":
                d = _read(f, a, b)
                if len(d) >= 16:
                    tr.fmt = d[12:16]
            elif typ == b"stts":
                d = _read(f, a, b)
                n = struct.unpack(">I", d[4:8])[0]
                tr.stts = list(struct.iter_unpack(">II", d[8:8 + 8 * n]))
            elif typ == b"stsz":
                d = _read(f, a, b)
                size, n = struct.unpack(">II", d[4:12])
                tr.stsz = [size] * n if size else list(struct.unpack(f">{n}I", d[12:12 + 4 * n]))
            elif typ == b"stsc":
                d = _read(f, a, b)
                n = struct.unpack(">I", d[4:8])[0]
                tr.stsc = list(struct.iter_unpack(">III", d[8:8 + 12 * n]))
            elif typ == b"stco":
                d = _read(f, a, b)
                n = struct.unpack(">I", d[4:8])[0]
                tr.chunks = list(struct.unpack(f">{n}I", d[8:8 + 4 * n]))
            elif typ == b"co64":
                d = _read(f, a, b)
                n = struct.unpack(">I", d[4:8])[0]
                tr.chunks = list(struct.unpack(f">{n}Q", d[8:8 + 8 * n]))

    walk(start, end)
    return tr


def _sample_table(tr):
    """Liste (offset, taille, pts_s, durée_s) de chaque échantillon d'une piste."""
    # temps
    times, durs, t = [], [], 0
    for count, delta in tr.stts:
        for _ in range(count):
            times.append(t / tr.timescale)
            durs.append(delta / tr.timescale)
            t += delta
    # offsets (sample-to-chunk)
    offsets = []
    si = 0
    stsc = tr.stsc + [(len(tr.chunks) + 1, 0, 0)]
    for k in range(len(stsc) - 1):
        first, per_chunk, _ = stsc[k]
        nxt = stsc[k + 1][0]
        for c in range(first, nxt):
            if c - 1 >= len(tr.chunks):
                break
            off = tr.chunks[c - 1]
            for _ in range(per_chunk):
                if si >= len(tr.stsz):
                    break
                offsets.append(off)
                off += tr.stsz[si]
                si += 1
    n = min(len(offsets), len(times), len(tr.stsz))
    return [(offsets[i], tr.stsz[i], times[i], durs[i]) for i in range(n)]


# ---------------------------------------------------------------------------
# GPMF (KLV)
# ---------------------------------------------------------------------------
_NUM = {
    "b": ("b", 1), "B": ("B", 1), "s": ("h", 2), "S": ("H", 2),
    "l": ("i", 4), "L": ("I", 4), "f": ("f", 4), "d": ("d", 8),
    "j": ("q", 8), "J": ("Q", 8),
}


def _klv(buf):
    pos, end = 0, len(buf)
    while pos + 8 <= end:
        key = buf[pos:pos + 4]
        typ = chr(buf[pos + 4])
        ssize = buf[pos + 5]
        rep = struct.unpack(">H", buf[pos + 6:pos + 8])[0]
        dlen = ssize * rep
        yield key, typ, ssize, rep, buf[pos + 8:pos + 8 + dlen]
        pos += 8 + ((dlen + 3) & ~3)


def _values(typ, ssize, rep, data, complex_type=None):
    """Décode un tableau numérique GPMF -> np.ndarray (rep, n)."""
    if typ == "?" and complex_type:
        fmt = ">" + "".join(_NUM[c][0] for c in complex_type)
        step = struct.calcsize(fmt)
        rows = [struct.unpack(fmt, data[i * step:(i + 1) * step]) for i in range(rep)
                if (i + 1) * step <= len(data)]
        return np.array(rows, dtype=float)
    if typ not in _NUM:
        return None
    ch, sz = _NUM[typ]
    n = ssize // sz
    if n == 0:
        return None
    arr = np.frombuffer(data[:rep * n * sz], dtype=">" + ch).astype(float)
    return arr.reshape(rep, n)


def _parse_gpsu(data):
    try:
        s = data[:16].decode("ascii")
        return datetime.strptime(s, "%y%m%d%H%M%S.%f").replace(tzinfo=timezone.utc)
    except (UnicodeDecodeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
@dataclass
class GoProClip:
    path: str
    duration: float            # s
    width: int
    height: int
    fps: float
    creation_time: datetime | None   # horloge caméra (pas fiable à la seconde)
    accl_t: np.ndarray          # temps vidéo (s)
    accl: np.ndarray            # (n, 3) m/s², ordre caméra
    gps_t: np.ndarray           # temps vidéo (s)
    gps: np.ndarray             # (n, 4) lat, lon, alt, vitesse m/s
    gps_anchor: datetime | None  # heure UTC à t_vidéo = 0, d'après GPSU (±1 s)

    @property
    def has_imu(self):
        return len(self.accl_t) > 100

    @property
    def start_utc_guess(self):
        """Meilleure estimation de l'heure UTC du début de la vidéo."""
        return self.gps_anchor or self.creation_time


def read_clip(path):
    """Lit un fichier GoPro et renvoie un GoProClip. Lève ValueError si pas de télémétrie."""
    with open(path, "rb") as f:
        fsize = os.fstat(f.fileno()).st_size
        moov = next(((a, b) for t, a, b in _iter_boxes(f, 0, fsize) if t == b"moov"), None)
        if not moov:
            raise ValueError(Msg("err_moov"))
        creation = None
        tracks = []
        for typ, a, b in _iter_boxes(f, *moov):
            if typ == b"mvhd":
                d = _read(f, a, min(b, a + 32))
                secs = struct.unpack(">Q", d[4:12])[0] if d[0] == 1 else struct.unpack(">I", d[4:8])[0]
                if secs:
                    # les GoPro écrivent l'heure LOCALE de la caméra : simple indice
                    creation = _MAC_EPOCH + timedelta(seconds=secs)
            elif typ == b"trak":
                tracks.append(_parse_trak(f, a, b))

        vid = next((t for t in tracks if t.handler == b"vide"), None)
        meta = next((t for t in tracks if t.fmt == b"gpmd"), None)
        if vid is None:
            raise ValueError(Msg("err_no_video"))
        duration = vid.duration / vid.timescale
        nfr = sum(c for c, _ in vid.stts)
        fps = nfr / duration if duration else 30.0
        if meta is None:
            raise ValueError(Msg("err_no_gpmf"))

        acc_t, acc_v, gps_t, gps_v, anchors = [], [], [], [], []
        for off, size, pts, dur in _sample_table(meta):
            payload = _read(f, off, off + size)
            _parse_payload(payload, pts, dur, acc_t, acc_v, gps_t, gps_v, anchors)

    accl_t = np.concatenate(acc_t) if acc_t else np.zeros(0)
    accl = np.vstack(acc_v) if acc_v else np.zeros((0, 3))
    g_t = np.concatenate(gps_t) if gps_t else np.zeros(0)
    g_v = np.vstack(gps_v) if gps_v else np.zeros((0, 4))
    return GoProClip(path, duration, vid.width, vid.height, fps, creation,
                     accl_t, accl, g_t, g_v, _best_anchor(anchors))


def _best_anchor(anchors):
    """Heure UTC du début de la vidéo d'après les GPSU.

    Les ancres prises avec un fix GPS sont fiables. Sans fix, le récepteur donne souvent
    quand même la bonne heure (elle vient des satellites), mais avant cela il émet des
    valeurs bidon (ex. 2021-03-07) : on garde le plus gros groupe d'ancres cohérentes."""
    good = [a for a, fix in anchors if fix]
    pool = good or [a for a, fix in anchors if a.year >= 2016]
    if not pool:
        return None
    base = pool[0]
    rel = np.array([(a - base).total_seconds() for a in pool])
    best = max(range(len(rel)), key=lambda i: int((np.abs(rel - rel[i]) < 1.5).sum()))
    grp = rel[np.abs(rel - rel[best]) < 1.5]
    if not good and len(grp) < 5:
        return None
    return base + timedelta(seconds=float(np.median(grp)))


def _parse_payload(buf, pts, dur, acc_t, acc_v, gps_t, gps_v, anchors):
    for key, typ, ss, rep, data in _klv(buf):
        if key != b"DEVC":
            continue
        for k2, t2, s2, r2, d2 in _klv(data):
            if k2 == b"STRM":
                _parse_strm(d2, pts, dur, acc_t, acc_v, gps_t, gps_v, anchors)


def _parse_strm(buf, pts, dur, acc_t, acc_v, gps_t, gps_v, anchors):
    # on collecte d'abord tous les champs : leur ordre varie selon les modèles
    fld = {}
    for key, typ, ss, rep, data in _klv(buf):
        fld[key] = (typ, ss, rep, data)

    def num(key, ctype=None):
        if key not in fld:
            return None
        return _values(*fld[key], ctype) if ctype else _values(*fld[key])

    scal = num(b"SCAL")
    scal = scal.ravel() if scal is not None else None

    def scaled(v):
        if scal is None:
            return v
        if len(scal) == v.shape[1]:
            return v / scal
        return v / scal[0]

    def spread(n):
        return pts + np.arange(n) * dur / n

    if b"ACCL" in fld:
        v = num(b"ACCL")
        if v is not None and len(v) and v.shape[1] >= 3:
            v = scaled(v)[:, :3]
            acc_t.append(spread(len(v)))
            acc_v.append(v)

    if b"GPS5" in fld:
        v = num(b"GPS5")
        f = num(b"GPSF")
        fix = int(f[0, 0]) if f is not None and len(f) else 0
        gpsu = _parse_gpsu(fld[b"GPSU"][3]) if b"GPSU" in fld else None
        if gpsu is not None:
            anchors.append((gpsu - timedelta(seconds=pts), fix >= 2))
        if v is not None and len(v) and v.shape[1] >= 4 and fix >= 2:
            v = scaled(v)
            gps_t.append(spread(len(v)))
            gps_v.append(v[:, :4])

    if b"GPS9" in fld and b"TYPE" in fld:
        t_, ss_, rep_, d_ = fld[b"TYPE"]
        ctype = d_[:ss_ * rep_].decode("ascii", "ignore").rstrip("\0")
        try:
            v = num(b"GPS9", ctype)
        except (KeyError, struct.error):
            v = None
        if v is not None and len(v) and v.shape[1] >= 9:
            v = scaled(v)
            ok = v[:, 8] >= 2
            if ok.any():
                tt = spread(len(v))
                gps_t.append(tt[ok])
                gps_v.append(v[ok][:, :4])
                # GPS9 : jours depuis 2000 + secondes depuis minuit, par échantillon
                k = int(np.argmax(ok))
                utc = (datetime(2000, 1, 1, tzinfo=timezone.utc)
                       + timedelta(days=float(v[k, 5]), seconds=float(v[k, 6])))
                anchors.append((utc - timedelta(seconds=float(tt[k])), True))
