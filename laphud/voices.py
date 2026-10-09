"""
Suppression des voix (option) avec le modèle BS-Roformer via « audio-separator ».
On garde le son du moteur et de la route.

Installation (facultative, ~3 Go avec PyTorch) :
    pip install "audio-separator[gpu]"
"""
from __future__ import annotations

import glob
import os
import shutil
import sys

from . import tools

MODEL = "model_bs_roformer_ep_368_sdr_12.9628.ckpt"


def _cli():
    p = shutil.which("audio-separator")
    if p:
        return p
    sub, exe = ("Scripts", "audio-separator.exe") if sys.platform == "win32" else ("bin", "audio-separator")
    cand = os.path.join(os.path.dirname(sys.executable), sub, exe)
    if os.path.isfile(cand):
        return cand
    for pat in (os.path.expandvars(r"%LOCALAPPDATA%\Programs\Python\Python3*\Scripts\audio-separator.exe"),):
        hits = sorted(glob.glob(pat))
        if hits:
            return hits[-1]
    return None


def available():
    return _cli() is not None


def remove_voices(video, work_dir, log=print):
    """Renvoie le chemin d'un WAV sans voix, ou None si échec (on garde alors le son d'origine)."""
    cli = _cli()
    if not cli:
        log("Suppression des voix indisponible (audio-separator non installé).")
        return None
    os.makedirs(work_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video))[0]
    wav = os.path.join(work_dir, base + "_audio.wav")
    p = tools.run([tools.ffmpeg(), "-y", "-v", "error", "-i", video, "-vn", "-ac", "2", "-ar", "48000", wav])
    if p.returncode != 0 or not os.path.exists(wav):
        log("Extraction audio impossible : son d'origine conservé.")
        return None
    out_dir = os.path.join(work_dir, base + "_sep")
    p = tools.run([cli, wav, "--model_filename", MODEL, "--output_dir", out_dir,
                   "--output_format", "WAV", "--single_stem", "Instrumental", "--use_autocast"])
    try:
        os.remove(wav)
    except OSError:
        pass
    hits = glob.glob(os.path.join(out_dir, "*Instrumental*.wav"))
    if p.returncode != 0 or not hits:
        err = (p.stderr or b"").decode("utf-8", "replace").strip().splitlines()[-1:] or ["?"]
        log(f"Suppression des voix échouée ({err[0][:120]}) : son d'origine conservé.")
        return None
    return hits[0]
