# -*- mode: python -*-
# Construction de l'exécutable Windows :  pyinstaller RaceSync.spec
# Résultat : dist/RaceSync/RaceSync.exe (dossier à zipper pour une release).
# Pour une release autonome, ajouter ffmpeg.exe et ffprobe.exe dans dist/RaceSync/ffmpeg/.

a = Analysis(
    ["racesync/__main__.py"],
    pathex=["."],
    datas=[("racesync/assets", "racesync/assets")],
    hiddenimports=["racesync.app.main"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest",
              "matplotlib", "scipy", "torch", "PIL"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="RaceSync",
    icon="racesync/assets/icon.ico",
    console=False,
    version=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="RaceSync")
