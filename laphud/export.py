"""
Export : vidéo GoPro + HUD -> MP4.

Le HUD est dessiné en parallèle sur plusieurs cœurs. Pour chaque image, les
panneaux sont rangés dans un petit « atlas » envoyé à ffmpeg, qui les découpe et
les pose à leur place. On n'envoie ainsi que ~15 % des pixels d'une image 4K.

Le fichier est écrit sous un nom temporaire puis renommé à la toute fin : un export
interrompu (plantage, coupure) ne peut jamais passer pour une vidéo terminée.
"""
from __future__ import annotations

import collections
import multiprocessing as mp
import os
import re
import subprocess
import threading
import time
from dataclasses import dataclass

import numpy as np

from . import tools, voices
from .hud.render import HudRenderer


@dataclass
class ExportOptions:
    out_size: tuple | None = None       # (L, H) ; None = résolution de la vidéo
    hud_fps: float = 30.0
    theme: str = "broadcast"
    lang: str = "fr"
    remove_voices: bool = False
    nudge: float = 0.0                  # réglage manuel de la synchro (s), + = HUD plus tard
    start: float | None = None          # extrait : début (s)
    duration: float | None = None       # extrait : durée (s)
    workers: int = 0                    # 0 = auto


class Cancelled(Exception):
    pass


# ---------------------------------------------------------------- atlas
def atlas_layout(panels):
    """Rangement simple en étagères. Renvoie (L, H, {nom: (x, y)})."""
    maxw = max(p.sw for p in panels) * 2
    x = y = row_h = 0
    pos = {}
    for p in sorted(panels, key=lambda p: -p.sh):
        if x + p.sw > maxw:
            x, y, row_h = 0, y + row_h, 0
        pos[p.name] = (x, y)
        x += p.sw
        row_h = max(row_h, p.sh)
    w = max(pos[p.name][0] + p.sw for p in panels)
    h = y + row_h
    return w + (w & 1), h + (h & 1), pos


# ---------------------------------------------------------------- rendu parallèle
_W = {}


def _worker_init(session, size, theme, lang, offset, start, fps):
    r = HudRenderer(session, size[0], size[1], theme=theme, lang=lang)
    aw, ah, pos = atlas_layout(r.panels)
    _W.update(session=session, r=r, aw=aw, ah=ah, pos=pos, offset=offset, start=start, fps=fps)


def _render_atlas(k):
    """Image k du HUD -> octets RGBA prémultipliés de l'atlas (None = pas de HUD)."""
    import skia
    W = _W
    t_video = W["start"] + k / W["fps"]
    st = W["session"].state_at(t_video - W["offset"])
    if not st.active:
        return None
    if "surf" not in W:
        # Skia dessine directement dans ce tableau : aucune copie ni conversion.
        # Les fonds fixes des panneaux sont posés une fois dans un atlas de base, recopié
        # à chaque image (une copie mémoire est ~200× plus rapide qu'un collage Skia).
        W["arr"] = np.zeros((W["ah"], W["aw"], 4), np.uint8)
        W["base"] = np.zeros_like(W["arr"])
        for p in W["r"].panels:
            x, y = W["pos"][p.name]
            W["base"][y:y + p.sh, x:x + p.sw] = W["r"].static_array(p)
        W["surf"] = skia.Surface(W["arr"], colorType=skia.kRGBA_8888_ColorType,
                                 alphaType=skia.kPremul_AlphaType)
    np.copyto(W["arr"], W["base"])
    c = W["surf"].getCanvas()
    for p in W["r"].panels:
        x, y = W["pos"][p.name]
        W["r"].draw_into(c, p, st, x, y, with_static=False)
    return W["arr"].tobytes()


# ---------------------------------------------------------------- export
def export(video, clip, session, offset, out, opts=None, log=print, progress=None, cancel=None):
    """
    video   : chemin du MP4 GoPro
    clip    : GoProClip (résolution, durée)
    session : Session RaceBox
    offset  : synchro (temps_session = temps_vidéo - offset)
    progress(fraction, texte) ; cancel() -> True pour arrêter.
    Renvoie le chemin de la vidéo créée.
    """
    opts = opts or ExportOptions()
    ff = tools.ffmpeg()
    enc, enc_label, enc_opts = tools.pick_encoder()
    OW, OH = opts.out_size or (clip.width, clip.height)
    OW, OH = OW - OW % 2, OH - OH % 2
    start = opts.start or 0.0
    dur = opts.duration or max(0.0, clip.duration - start)
    fps = opts.hud_fps
    nfr = int(dur * fps)
    offset = offset + opts.nudge
    work = os.path.join(os.path.dirname(os.path.abspath(out)), ".laphud_tmp")
    os.makedirs(work, exist_ok=True)
    part = os.path.splitext(out)[0] + ".part.mp4"

    def prog(f, txt):
        if progress:
            progress(max(0.0, min(1.0, f)), txt)

    def check():
        if cancel and cancel():
            raise Cancelled()

    # --- son : la suppression des voix tourne EN MÊME TEMPS que l'encodage vidéo ;
    # la vidéo est d'abord encodée avec le son d'origine, puis on remplace la piste son.
    voice = {}
    vthread = None
    if opts.remove_voices:
        def sep():
            voice["wav"] = voices.remove_voices(video, work, log=log)
        vthread = threading.Thread(target=sep, daemon=True)
        vthread.start()

    # --- ffmpeg
    probe = HudRenderer(session, OW, OH, theme=opts.theme, lang=opts.lang)
    aw, ah, pos = atlas_layout(probe.panels)
    trim = (["-ss", f"{start:.3f}"] if start else []) + ["-t", f"{dur:.3f}"]
    cmd = [ff, "-y", "-hide_banner", "-v", "error", "-nostats", "-progress", "pipe:2",
           *tools.decoder_args(enc), *trim, "-i", video,
           "-f", "rawvideo", "-pix_fmt", "rgba", "-s", f"{aw}x{ah}", "-r", f"{fps:g}", "-i", "pipe:0"]
    audio = None
    n = len(probe.panels)
    fc = [f"[1:v]unpremultiply=inplace=1,split={n}" + "".join(f"[a{i}]" for i in range(n))]
    base = "[0:v]"
    if (OW, OH) != (clip.width, clip.height):
        fc.append(f"[0:v]scale={OW}:{OH}:flags=lanczos[b0]")
        base = "[b0]"
    for i, p in enumerate(probe.panels):
        x, y = pos[p.name]
        fc.append(f"[a{i}]crop={p.sw}:{p.sh}:{x}:{y}[p{i}]")
        nxt = "[vo]" if i == n - 1 else f"[v{i}]"
        fc.append(f"{base}[p{i}]overlay={p.sx}:{p.sy}:format=auto:eof_action=pass:repeatlast=0{nxt}")
        base = f"[v{i}]"
    cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "2:a:0" if audio else "0:a:0?",
            "-c:v", enc, *enc_opts, "-pix_fmt", "yuv420p",
            "-tag:v", "hvc1" if enc.startswith(("hevc", "libx265")) else "avc1",
            "-c:a", "aac", "-b:a", "256k", *([] if opts.remove_voices else ["-movflags", "+faststart"]), part]
    log(f"Encodage {OW}×{OH} avec {enc_label}, HUD {fps:g} i/s, {nfr} images")

    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE,
                            creationflags=tools.NO_WINDOW)
    errlines = []
    enc_time = [0.0]

    def read_err():
        rx = re.compile(rb"out_time_us=(\d+)")
        for line in proc.stderr:
            m = rx.match(line)
            if m:
                enc_time[0] = int(m.group(1)) / 1e6
            elif not line.startswith((b"frame=", b"fps=", b"stream_", b"bitrate=", b"total_size=",
                                      b"out_time", b"dup_frames=", b"drop_frames=", b"speed=",
                                      b"progress=")):
                errlines.append(line.decode("utf-8", "replace").strip())
    th = threading.Thread(target=read_err, daemon=True)
    th.start()

    empty = bytes(aw * ah * 4)
    # le rendu est léger (~10 ms/image en 4K) : on laisse l'essentiel du processeur à ffmpeg
    workers = opts.workers or max(2, min(6, (os.cpu_count() or 4) // 3))
    ctx = mp.get_context("spawn")
    t0 = time.time()
    ok = False
    try:
        with ctx.Pool(workers, initializer=_worker_init,
                      initargs=(session, (OW, OH), opts.theme, opts.lang, offset, start, fps)) as pool:
            # nombre d'images en vol limité : si ffmpeg est plus lent que le rendu, les
            # processus de rendu attendent au lieu d'empiler des images en mémoire
            inflight = collections.deque()
            nxt = 0
            for k in range(nfr):
                while nxt < nfr and len(inflight) < workers * 3:
                    inflight.append(pool.apply_async(_render_atlas, (nxt,)))
                    nxt += 1
                buf = inflight.popleft().get()
                proc.stdin.write(buf if buf is not None else empty)
                if k % 15 == 0:
                    check()
                    el = time.time() - t0
                    rate = (k + 1) / el if el > 0 else 0
                    eta = (nfr - k) / rate if rate else 0
                    prog(k / max(nfr, 1), f"{k / max(nfr, 1) * 100:4.1f} % · {rate / fps:.2f}× temps réel · "
                                          f"reste {int(eta // 60)} min {int(eta % 60):02d} s")
        proc.stdin.close()
        proc.wait()
        th.join(timeout=5)
        if proc.returncode != 0:
            raise RuntimeError("ffmpeg a échoué : " + " | ".join(errlines[-3:]))
        got = tools.media_duration(part) or 0
        if got < dur - 2.0:
            raise RuntimeError(f"vidéo incomplète ({got:.0f} s sur {dur:.0f} s)")
        if vthread is not None:
            if vthread.is_alive():
                prog(1.0, "Suppression des voix (fin)…")
            while vthread.is_alive():
                vthread.join(timeout=0.5)
                check()
            audio = voice.get("wav")
            if audio:
                prog(1.0, "Pose du son sans voix…")
                mixed = os.path.splitext(out)[0] + ".mix.part.mp4"
                atrim = (["-ss", f"{start:.3f}"] if start else []) + ["-t", f"{dur:.3f}"]
                r = tools.run([ff, "-y", "-v", "error", "-i", part, *atrim, "-i", audio,
                               "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                               "-c:a", "aac", "-b:a", "256k", "-shortest", "-movflags", "+faststart", mixed])
                if r.returncode == 0 and (tools.media_duration(mixed) or 0) >= dur - 2.0:
                    os.replace(mixed, part)
                else:
                    log("Pose du son sans voix impossible : son d'origine conservé.")
                    try:
                        os.remove(mixed)
                    except OSError:
                        pass
        os.replace(part, out)
        ok = True
        prog(1.0, f"Terminé en {int((time.time() - t0) // 60)} min {int((time.time() - t0) % 60):02d} s")
        return out
    except (BrokenPipeError, OSError) as e:
        proc.kill()
        raise RuntimeError("ffmpeg s'est arrêté : " + (" | ".join(errlines[-3:]) or str(e)))
    finally:
        if not ok:
            try:
                proc.kill()
            except OSError:
                pass
            try:
                os.remove(part)
            except OSError:
                pass
        for p in ((audio, os.path.dirname(audio)) if audio else ()) + (work,):
            try:
                os.remove(p) if os.path.isfile(p) else os.rmdir(p)
            except OSError:
                pass
