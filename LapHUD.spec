# -*- mode: python -*-
# Construction de l'exécutable Windows :  pyinstaller LapHUD.spec
# Résultat : dist/LapHUD/LapHUD.exe (dossier à zipper pour une release).
# Pour une release autonome, ajouter ffmpeg.exe et ffprobe.exe dans dist/LapHUD/ffmpeg/.

a = Analysis(
    ["laphud/__main__.py"],
    pathex=["."],
    datas=[("laphud/assets", "laphud/assets")],
    hiddenimports=["laphud.app.main"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest",
              "matplotlib", "scipy", "torch", "PIL"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="LapHUD",
    icon="laphud/assets/icon.ico",
    console=False,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="LapHUD")
