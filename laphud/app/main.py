"""Point d'entrée de l'application LapHUD."""
from __future__ import annotations

import glob
import multiprocessing as mp
import os
import sys


def main():
    mp.freeze_support()          # indispensable pour le rendu parallèle dans l'exe
    from PySide6.QtGui import QFontDatabase, QFont, QIcon
    from PySide6.QtWidgets import QApplication

    from ..hud.theme import FONT_DIR
    from .style import QSS
    from .window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("LapHUD")
    for f in glob.glob(os.path.join(FONT_DIR, "*.ttf")):
        QFontDatabase.addApplicationFont(f)
    app.setFont(QFont("Titillium Web", 10))
    icon = os.path.join(os.path.dirname(FONT_DIR), "icon.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    app.setStyleSheet(QSS)
    # langue : choix enregistré, sinon celle de l'ordinateur (LAPHUD_LANG pour forcer, ex. captures)
    from PySide6.QtCore import QSettings
    from .. import i18n
    i18n.set_lang(os.environ.get("LAPHUD_LANG") or QSettings("LapHUD", "LapHUD").value("lang")
                  or i18n.system_lang())
    w = MainWindow()
    w.show()
    if len(sys.argv) > 1:
        w._add_paths(sys.argv[1:])
    snap = os.environ.get("LAPHUD_SELFTEST")
    if snap:
        _selftest(app, w, snap)
    sys.exit(app.exec())


def _selftest(app, w, out):
    """Test de fumée (CI / build) : attend l'analyse et l'aperçu, capture la fenêtre, quitte."""
    import time
    from PySide6.QtCore import QTimer
    t0 = time.time()

    def poll():
        ready = not w.paths or (w.jobs and w._frame is not None and not w._is_busy)
        if ready or time.time() - t0 > 120:
            QTimer.singleShot(800, lambda: (w.grab().save(out), app.quit()))
        else:
            QTimer.singleShot(300, poll)
    QTimer.singleShot(500, poll)


if __name__ == "__main__":
    main()
