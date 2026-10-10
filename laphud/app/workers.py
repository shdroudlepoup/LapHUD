"""Tâches de fond (analyse, aperçu, export) pour ne jamais figer l'interface."""
from __future__ import annotations

import ctypes
import sys
import traceback

from PySide6.QtCore import QThread, Signal


class Task(QThread):
    progressed = Signal(float, str)
    logged = Signal(str)
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn, *args, **kw):
        super().__init__()
        self.fn, self.args, self.kw = fn, args, kw
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def run(self):
        try:
            res = self.fn(*self.args, task=self, **self.kw)
            self.succeeded.emit(res)
        except Exception as e:          # noqa: BLE001 — remonté à l'interface
            traceback.print_exc()
            self.failed.emit(str(e) or e.__class__.__name__)


# ---------------------------------------------------------------- Windows : veille / priorité
ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
BELOW_NORMAL, NORMAL = 0x4000, 0x20


def keep_awake(on):
    """Empêche la mise en veille pendant un export (sinon tout s'arrête la nuit)."""
    if sys.platform == "win32":
        flags = ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0)
        ctypes.windll.kernel32.SetThreadExecutionState(flags)


def low_priority(on):
    """Priorité basse pendant l'export : le PC reste utilisable (jeux, navigation).
    ffmpeg et les processus de rendu héritent de cette priorité."""
    if sys.platform == "win32":
        from ctypes import wintypes
        k = ctypes.windll.kernel32
        # types explicites : sans eux, le pseudo-handle 64 bits est tronqué et l'appel échoue en silence
        k.GetCurrentProcess.restype = wintypes.HANDLE
        k.SetPriorityClass.argtypes = (wintypes.HANDLE, wintypes.DWORD)
        k.SetPriorityClass.restype = wintypes.BOOL
        k.SetPriorityClass(k.GetCurrentProcess(), BELOW_NORMAL if on else NORMAL)
