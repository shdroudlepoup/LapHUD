# -*- mode: python -*-
# Construction de l'application :  pyinstaller LapHUD.spec
#   Windows : dist/LapHUD/LapHUD.exe   (packaging/build_release.py ajoute ffmpeg et fait le zip)
#   macOS   : dist/LapHUD.app
#   Linux   : dist/LapHUD/LapHUD
import sys

ICON = "laphud/assets/icon.ico" if sys.platform == "win32" else "laphud/assets/icon.png"

a = Analysis(
    ["laphud/__main__.py"],
    pathex=["."],
    datas=[("laphud/assets", "laphud/assets")],
    hiddenimports=["laphud.app.main"],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
              "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtPdf", "PySide6.QtCharts",
              "PySide6.QtDataVisualization", "PySide6.QtBluetooth", "PySide6.QtSql", "PySide6.QtTest",
              "matplotlib", "scipy", "torch"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="LapHUD",
    icon=ICON,
    console=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="LapHUD")

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="LapHUD.app",
        icon=ICON,
        bundle_identifier="io.github.shdroudlepoup.laphud",
        info_plist={"NSHighResolutionCapable": True, "CFBundleShortVersionString": "0.2.0"},
    )
