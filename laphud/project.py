"""
Analyse d'un lot : on donne des fichiers ou des dossiers, LapHUD trouve les
vidéos GoPro et les CSV RaceBox ou RaceChrono, associe chaque vidéo à sa session et la synchronise.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from . import gopro, racebox, racechrono, sync
from .session import Session
from .i18n import Msg

VIDEO_EXT = (".mp4",)
SKIP_DIRS = {".laphud_tmp", "$recycle.bin", "system volume information"}


@dataclass
class Job:
    video: str
    clip: gopro.GoProClip | None = None
    log: racebox.RaceBoxLog | None = None
    session: Session | None = None
    sync: sync.SyncResult | None = None
    nudge: float = 0.0                 # réglage manuel (s)
    include: bool = True
    status: str = "pending"            # pending, ready, error, running, done
    message: object = ""     # texte, Msg ou liste de Msg (traduit à l'affichage)
    output: str | None = None

    @property
    def name(self):
        return os.path.basename(self.video)

    @property
    def offset(self):
        return (self.sync.offset if self.sync else 0.0) + self.nudge

    @property
    def ready(self):
        return self.status in ("ready", "done") and self.session is not None


def scan(paths):
    """-> (vidéos, csv) trouvés dans les fichiers / dossiers donnés."""
    vids, csvs = [], []

    def add(p):
        low = p.lower()
        if low.endswith(VIDEO_EXT) and not os.path.basename(low).startswith("._"):
            if not low.endswith((".part.mp4", "_laphud.mp4")):
                vids.append(os.path.abspath(p))
        elif low.endswith(".csv") and (racebox.is_racebox_csv(p) or racechrono.is_racechrono_csv(p)):
            csvs.append(os.path.abspath(p))

    for p in paths:
        if os.path.isdir(p):
            for root, dirs, files in os.walk(p):
                dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
                for f in files:
                    add(os.path.join(root, f))
        elif os.path.isfile(p):
            add(p)
    return sorted(set(vids)), sorted(set(csvs))


def analyze(paths, log=print, progress=None, extra_csvs=()):
    """Analyse complète. Renvoie la liste de Job (un par vidéo)."""
    vids, csvs = scan(paths)
    csvs = sorted(set(csvs) | set(extra_csvs))
    logs = []
    for c in csvs:
        try:
            logs.append(racechrono.load(c) if racechrono.is_racechrono_csv(c) else racebox.load(c))
        except (OSError, ValueError) as e:
            log(f"CSV ignoré ({os.path.basename(c)}) : {e}")
    sessions = {}
    jobs = []
    for i, v in enumerate(vids):
        if progress:
            progress(i / max(len(vids), 1), os.path.basename(v))
        j = Job(v)
        try:
            j.clip = gopro.read_clip(v)
        except (OSError, ValueError) as e:
            reason = e.args[0] if e.args else str(e)
            if isinstance(reason, Msg) and reason.key == "err_no_gpmf":
                continue           # pas une vidéo GoPro (ex. vidéo RaceChrono) : on l'ignore
            j.status, j.message, j.include = "error", reason, False
        jobs.append(j)
        if j.status == "error":
            continue
        L, res = sync.best_match(j.clip, logs)
        if L is None:
            j.status, j.message, j.include = "error", Msg("no_match"), False
            continue
        j.log, j.sync = L, res
        if L.path not in sessions:
            sessions[L.path] = Session(L)
        j.session = sessions[L.path]
        j.status = "ready"
        j.message = [Msg("sync_" + res.quality), *res.note]
    if progress:
        progress(1.0, "")
    return jobs


# ---------------------------------------------------------------- reprise après coupure
def save_queue(path, jobs, settings):
    data = {"settings": settings,
            "jobs": [{"video": j.video, "csv": j.log.path if j.log else None, "nudge": j.nudge,
                      "include": j.include, "done": j.status == "done"} for j in jobs]}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, path)


def load_queue(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None
