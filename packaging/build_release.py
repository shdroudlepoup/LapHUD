"""
Construit le zip de release Windows : dist/LapHUD (PyInstaller) + ffmpeg + licences.

    pyinstaller LapHUD.spec
    python packaging/build_release.py  [dossier contenant ffmpeg.exe et ffprobe.exe]

Sans argument, ffmpeg est cherché comme le fait l'application (PATH, WinGet…).
"""
import os
import shutil
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from laphud import __version__, tools  # noqa: E402


def main():
    dist = os.path.join(ROOT, "dist", "LapHUD")
    if not os.path.isfile(os.path.join(dist, "LapHUD.exe")):
        sys.exit("Lance d'abord : pyinstaller LapHUD.spec")
    ffbin = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(tools.find_tool("ffmpeg") or "")
    if not os.path.isfile(os.path.join(ffbin, "ffmpeg.exe")):
        sys.exit("ffmpeg.exe introuvable")
    name = f"LapHUD-{__version__}-windows"
    out_dir = os.path.join(ROOT, "_release")
    stage = os.path.join(out_dir, name)
    if os.path.isdir(stage):
        shutil.rmtree(stage)
    shutil.copytree(dist, stage)
    os.makedirs(os.path.join(stage, "ffmpeg"))
    for exe in ("ffmpeg.exe", "ffprobe.exe"):
        shutil.copy2(os.path.join(ffbin, exe), os.path.join(stage, "ffmpeg", exe))
    ffroot = os.path.dirname(ffbin)
    for src, dst in (("LICENSE", "LICENSE.txt"), ("README.txt", "README.txt")):
        p = os.path.join(ffroot, src)
        if os.path.isfile(p):
            shutil.copy2(p, os.path.join(stage, "ffmpeg", dst))
    shutil.copy2(os.path.join(ROOT, "LICENSE"), os.path.join(stage, "LICENSE.txt"))
    shutil.copy2(os.path.join(ROOT, "packaging", "LISEZMOI.txt"), os.path.join(stage, "LISEZMOI.txt"))
    zpath = os.path.join(out_dir, name + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for dirpath, _, files in os.walk(stage):
            for f in files:
                full = os.path.join(dirpath, f)
                z.write(full, os.path.relpath(full, out_dir))
    print(f"{zpath}  ({os.path.getsize(zpath) / 1e6:.0f} Mo)")


if __name__ == "__main__":
    main()
