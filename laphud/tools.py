"""Outils externes : localisation de ffmpeg et choix de l'encodeur vidéo."""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
from functools import lru_cache

NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # pas de console qui clignote


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW, **kw)


def _app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@lru_cache(maxsize=None)
def find_tool(name):
    """ffmpeg / ffprobe : variable d'env, dossier de l'appli, PATH, puis installs courantes."""
    exe = name + (".exe" if sys.platform == "win32" else "")
    env = os.environ.get("LAPHUD_" + name.upper())
    if env and os.path.isfile(env):
        return env
    for d in (os.path.join(_app_dir(), "ffmpeg"), os.path.join(_app_dir(), "ffmpeg", "bin"), _app_dir()):
        p = os.path.join(d, exe)
        if os.path.isfile(p):
            return p
    p = shutil.which(name)
    if p:
        return p
    if sys.platform == "win32":
        pats = [os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\*FFmpeg*\*\bin\\" + exe),
                r"C:\ffmpeg\bin\\" + exe,
                os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin\\" + exe)]
        for pat in pats:
            hits = sorted(glob.glob(pat))
            if hits:
                return hits[-1]
    return None


def ffmpeg():
    p = find_tool("ffmpeg")
    if not p:
        raise RuntimeError("ffmpeg introuvable. Installe-le (https://ffmpeg.org) ou place ffmpeg.exe "
                           "dans le dossier « ffmpeg » à côté de LapHUD.")
    return p


# Encodeurs HEVC par ordre de préférence. Les options visent une qualité « YouTube 4K ».
ENCODERS = [
    ("hevc_nvenc", "NVIDIA", ["-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", "21", "-b:v", "0"]),
    ("hevc_amf", "AMD", ["-quality", "quality", "-rc", "cqp", "-qp_i", "20", "-qp_p", "22"]),
    ("hevc_qsv", "Intel", ["-preset", "slow", "-global_quality", "22"]),
    ("libx265", "processeur", ["-preset", "medium", "-crf", "21"]),
]


@lru_cache(maxsize=None)
def pick_encoder():
    """Premier encodeur qui fonctionne VRAIMENT (un encodeur listé peut manquer de matériel)."""
    ff = ffmpeg()
    listed = run([ff, "-hide_banner", "-encoders"], text=True).stdout
    for name, label, opts in ENCODERS:
        if name not in listed:
            continue
        test = run([ff, "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "color=black:s=256x256:d=0.2",
                    "-c:v", name, *opts, "-f", "null", "-"])
        if test.returncode == 0:
            return name, label, opts
    return "libx264", "processeur (H.264)", ["-preset", "medium", "-crf", "20"]


def decoder_args(encoder):
    """Décodage matériel de la source quand c'est sans risque."""
    if encoder == "hevc_nvenc":
        return ["-hwaccel", "nvdec"]
    if encoder in ("hevc_amf", "hevc_qsv"):
        return ["-hwaccel", "auto"]
    return []


def media_duration(path):
    ffprobe = find_tool("ffprobe")
    if not ffprobe or not os.path.exists(path):
        return None
    p = run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", path],
            text=True)
    try:
        return float(p.stdout.strip())
    except ValueError:
        return None
