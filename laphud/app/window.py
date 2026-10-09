"""Fenêtre principale de LapHUD."""
from __future__ import annotations

import os
import tempfile

import numpy as np
import skia
from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QSettings
from PySide6.QtGui import QImage, QPixmap, QPainter
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QFrame, QLabel, QPushButton, QComboBox, QCheckBox, QSlider,
    QProgressBar, QListWidget, QListWidgetItem, QHBoxLayout, QVBoxLayout,
    QFileDialog, QStackedWidget, QSizePolicy, QMessageBox,
)

from .. import tools, voices, export, project, i18n
from ..i18n import tr
from ..hud.render import HudRenderer, fmt_time
from . import style
from .workers import Task, keep_awake, low_priority

RESOLUTIONS = [("res_original", None), ("4K", (3840, 2160)), ("1440p", (2560, 1440)), ("1080p", (1920, 1080))]
THEME_KEYS = ["broadcast", "glass", "minimal"]
OUT_SUFFIX = "_LapHUD.mp4"


def _fmt_dur(s):
    return f"{int(s // 60)} min {int(s % 60):02d}"


def grab_frame(video, t, width):
    """Une image de la vidéo au temps t, redimensionnée -> np.ndarray RGB."""
    ff = tools.ffmpeg()
    p = tools.run([ff, "-v", "error", "-ss", f"{max(0.0, t):.3f}", "-i", video, "-frames:v", "1",
                   "-vf", f"scale={width}:-2", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"])
    data = p.stdout
    if not data:
        return None
    h = len(data) // (width * 3)
    return np.frombuffer(data[:h * width * 3], np.uint8).reshape(h, width, 3)


class Dot(QLabel):
    """Petite pastille de couleur (état)."""
    def __init__(self, color=style.DIM):
        super().__init__()
        self.setFixedSize(9, 9)
        self.set_color(color)

    def set_color(self, color):
        self.setStyleSheet(f"background:{color}; border-radius:4px;")


# ====================================================================== carte de session
class JobCard(QFrame):
    def __init__(self, job, on_toggle):
        super().__init__()
        self.setObjectName("card")
        self.job = job
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(10)
        self.chk = QCheckBox()
        self.chk.setChecked(job.include)
        self.chk.setEnabled(job.ready and job.status != "done")
        self.chk.toggled.connect(lambda v: on_toggle(job, v))
        lay.addWidget(self.chk, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        self.title = QLabel(job.name)
        self.title.setObjectName("big")
        self.sub = QLabel()
        self.sub.setObjectName("dim")
        self.state = QLabel()
        self.state.setWordWrap(True)
        self.bar = QProgressBar()
        self.bar.setMaximumHeight(6)
        self.bar.hide()
        col.addWidget(self.title)
        col.addWidget(self.sub)
        srow = QHBoxLayout()
        srow.setSpacing(7)
        self.dot = Dot()
        srow.addWidget(self.dot, 0, Qt.AlignVCenter)
        srow.addWidget(self.state, 1)
        col.addLayout(srow)
        col.addWidget(self.bar)
        lay.addLayout(col, 1)
        self.refresh()

    def refresh(self, text=None):
        j = self.job
        bits = []
        if j.clip:
            bits.append(_fmt_dur(j.clip.duration))
        if j.session:
            n = len(j.session.timed)
            bits.append(tr("laps_1") if n == 1 else tr("laps_n", n=n))
            if n:
                bits.append(tr("card_best", t=fmt_time(min(L.duration for L in j.session.timed))))
        self.sub.setText("  ·  ".join(bits) or "—")
        col = {"ready": style.OK, "error": style.BAD, "done": style.PURPLE, "running": style.ACCENT}.get(j.status, style.DIM)
        if j.status == "ready" and j.sync and j.sync.quality in ("faible", "approx"):
            col = style.WARN
        msg = text or {"done": tr("card_done"), "running": tr("card_running")}.get(j.status) \
            or i18n.text(j.message)
        self.dot.set_color(col)
        self.state.setText(f'<span style="color:{style.DIM}">{msg}</span>')
        self.chk.setEnabled(j.ready and j.status not in ("done", "running"))
        self.chk.setChecked(j.include)

    def set_selected(self, on):
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)


# ====================================================================== fenêtre
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LapHUD")
        self.resize(1360, 860)
        self.setMinimumSize(1100, 700)
        self.setAcceptDrops(True)
        self.settings = QSettings("LapHUD", "LapHUD")
        self.paths = []
        self.jobs = []
        self.cards = []
        self.current = None
        self.task = None
        self.preview_task = None
        self._renderers = {}
        self._frame = None
        self._frame_key = None
        self._pending_t = None
        self._is_busy = False
        self.tmp = tempfile.mkdtemp(prefix="laphud_")
        self._clip_n = 0
        self._build()
        self._set_empty(True)

    # ------------------------------------------------------------------ UI
    def _build(self):
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        v = QVBoxLayout(root)
        v.setContentsMargins(22, 16, 22, 16)
        v.setSpacing(14)

        # en-tête
        head = QHBoxLayout()
        logo = QLabel(f'<span style="color:{style.TEXT}">LAP</span><span style="color:{style.ACCENT}">HUD</span>')
        logo.setObjectName("logo")
        tag = QLabel(tr("tagline"))
        tag.setObjectName("tagline")
        head.addWidget(logo)
        head.addSpacing(14)
        head.addWidget(tag, 0, Qt.AlignBottom)
        head.addStretch(1)
        b_files = QPushButton(tr("btn_files"))
        b_dir = QPushButton(tr("btn_dir"))
        self.b_clear = QPushButton(tr("btn_clear"))
        self.b_clear.setObjectName("ghost")
        b_files.clicked.connect(self._pick_files)
        b_dir.clicked.connect(self._pick_dir)
        self.b_clear.clicked.connect(self._clear)
        for b in (self.b_clear, b_files, b_dir):
            head.addWidget(b)
        head.addSpacing(10)
        head.addWidget(self._build_lang())
        v.addLayout(head)

        # zone centrale
        self.center = QStackedWidget()
        v.addWidget(self.center, 1)

        # -- état vide : zone de dépôt
        self.drop = QFrame()
        self.drop.setObjectName("drop")
        dl = QVBoxLayout(self.drop)
        dl.addStretch(1)
        t1 = QLabel(tr("drop_title"))
        t1.setStyleSheet("font-size: 18pt; font-weight: 700;")
        t2 = QLabel(tr("drop_sub"))
        t2.setObjectName("dim")
        t2.setAlignment(Qt.AlignCenter)
        t3 = QLabel(tr("drop_hint"))
        t3.setObjectName("dim")
        t3.setStyleSheet("font-size: 9pt;")
        for w in (t1, t2, t3):
            dl.addWidget(w, 0, Qt.AlignHCenter)
        dl.addSpacing(6)
        dl.addStretch(1)
        self.center.addWidget(self.drop)

        # -- état travail
        work = QWidget()
        h = QHBoxLayout(work)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)
        lab = QLabel(tr("sessions"))
        lab.setObjectName("section")
        left.addWidget(lab)
        self.list = QListWidget()
        self.list.setVerticalScrollMode(QListWidget.ScrollPerPixel)
        self.list.currentRowChanged.connect(self._select)
        left.addWidget(self.list, 1)
        lw = QWidget()
        lw.setLayout(left)
        lw.setFixedWidth(400)
        h.addWidget(lw)
        h.addWidget(self._build_preview(), 1)
        self.center.addWidget(work)

        # barre du bas
        v.addWidget(self._build_bottom())

    def _build_lang(self):
        """Sélecteur FR | EN : change la langue de l'interface et du HUD, en direct."""
        box = QFrame()
        box.setObjectName("lang")
        box.setToolTip(tr("lang_tip"))
        lay = QHBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        self.lang_btns = {}
        for code in i18n.LANGS:
            b = QPushButton(code.upper())
            b.setObjectName("langbtn")
            b.setCheckable(True)
            b.setChecked(code == i18n.get_lang())
            b.clicked.connect(lambda _=False, c=code: self._set_lang(c))
            lay.addWidget(b)
            self.lang_btns[code] = b
        return box

    def _set_lang(self, code):
        for c, b in self.lang_btns.items():
            b.setChecked(c == (code if not self._is_busy else i18n.get_lang()))
        if self._is_busy or code == i18n.get_lang():
            return
        i18n.set_lang(code)
        self.settings.setValue("lang", code)
        self._rebuild()

    def _rebuild(self):
        """Reconstruit la fenêtre dans la nouvelle langue en gardant les vidéos chargées."""
        row = self.list.currentRow()
        slider = self.slider.value()
        self._stop_player()
        self._build()
        if self.jobs:
            self._populate()
            self._set_empty(False)
            ok = sum(j.ready for j in self.jobs)
            self.lbl_status.setText(tr("ready_count", ok=ok))
            if row >= 0:
                self.list.setCurrentRow(row)
                self.slider.setValue(slider)
                self._frame = None
                self._load_frame()
        else:
            self._set_empty(True)

    def _build_preview(self):
        panel = QFrame()
        panel.setObjectName("panel")
        g = QVBoxLayout(panel)
        g.setContentsMargins(14, 12, 14, 14)
        g.setSpacing(10)
        top = QHBoxLayout()
        lab = QLabel(tr("preview"))
        lab.setObjectName("section")
        self.lbl_title = QLabel("")
        self.lbl_title.setObjectName("dim")
        top.addWidget(lab)
        top.addSpacing(10)
        top.addWidget(self.lbl_title, 1)
        self.cmb_lap = QComboBox()
        self.cmb_lap.setToolTip(tr("goto_lap_tip"))
        self.cmb_lap.activated.connect(self._goto_lap)
        top.addWidget(self.cmb_lap)
        g.addLayout(top)

        self.view_stack = QStackedWidget()
        self.view = QLabel()
        self.view.setAlignment(Qt.AlignCenter)
        self.view.setMinimumSize(480, 270)
        self.view.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.view.setStyleSheet("background:#000; border-radius:8px;")
        self.video = QVideoWidget()
        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)
        self.player.setVideoOutput(self.video)
        self.player.mediaStatusChanged.connect(self._media_status)
        self.view_stack.addWidget(self.view)
        self.view_stack.addWidget(self.video)
        g.addWidget(self.view_stack, 1)

        row = QHBoxLayout()
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, 10000)
        self.slider.valueChanged.connect(self._scrub)
        self.lbl_time = QLabel("0:00")
        self.lbl_time.setObjectName("dim")
        self.lbl_time.setMinimumWidth(110)
        row.addWidget(self.slider, 1)
        row.addWidget(self.lbl_time)
        g.addLayout(row)

        sync = QHBoxLayout()
        sync.setSpacing(6)
        self.sync_dot = Dot()
        self.lbl_sync = QLabel("")
        self.lbl_sync.setTextFormat(Qt.RichText)
        sync.addWidget(self.sync_dot, 0, Qt.AlignVCenter)
        sync.addSpacing(4)
        sync.addWidget(self.lbl_sync, 1)
        hint = QLabel(tr("nudge_label"))
        hint.setObjectName("dim")
        hint.setToolTip(tr("nudge_hint"))
        sync.addWidget(hint)
        for d in (-0.1, -0.02, 0.02, 0.1):
            b = QPushButton(f"{d:+.2f}".replace("-", "−"))
            b.setObjectName("nudge")
            b.setToolTip(tr("nudge_tip", d=f"{d:+.2f}"))
            b.clicked.connect(lambda _=False, d=d: self._nudge(d))
            sync.addWidget(b)
        self.b_reset = QPushButton(tr("auto"))
        self.b_reset.setObjectName("nudge")
        self.b_reset.setToolTip(tr("auto_tip"))
        self.b_reset.clicked.connect(lambda: self._nudge(None))
        sync.addWidget(self.b_reset)
        sync.addSpacing(10)
        self.b_play = QPushButton(tr("preview_btn"))
        self.b_play.setToolTip(tr("preview_tip"))
        self.b_play.clicked.connect(self._preview_clip)
        sync.addWidget(self.b_play)
        g.addLayout(sync)
        self._scrub_timer = QTimer(self)
        self._scrub_timer.setSingleShot(True)
        self._scrub_timer.timeout.connect(self._load_frame)
        return panel

    def _build_bottom(self):
        bar = QFrame()
        bar.setObjectName("panel")
        h = QHBoxLayout(bar)
        h.setContentsMargins(16, 12, 16, 12)
        h.setSpacing(14)

        def labeled(text, w):
            box = QVBoxLayout()
            box.setSpacing(3)
            l = QLabel(text)
            l.setObjectName("section")
            box.addWidget(l)
            box.addWidget(w)
            return box

        self.cmb_theme = QComboBox()
        for k in THEME_KEYS:
            self.cmb_theme.addItem(tr("theme_" + k), k)
        self.cmb_theme.setCurrentIndex(max(0, THEME_KEYS.index(self.settings.value("theme", "broadcast"))))
        self.cmb_theme.currentIndexChanged.connect(self._theme_changed)
        h.addLayout(labeled(tr("style"), self.cmb_theme))

        self.cmb_res = QComboBox()
        for name, _ in RESOLUTIONS:
            self.cmb_res.addItem(tr(name) if name.startswith("res_") else name)
        self.cmb_res.setCurrentIndex(int(self.settings.value("res", 0)))
        h.addLayout(labeled(tr("resolution"), self.cmb_res))

        self.cmb_fps = QComboBox()
        self.cmb_fps.addItem(tr("fps30"), 30.0)
        self.cmb_fps.addItem(tr("fps60"), 60.0)
        self.cmb_fps.setCurrentIndex(int(self.settings.value("fps", 0)))
        h.addLayout(labeled(tr("hud"), self.cmb_fps))

        self.chk_voices = QCheckBox(tr("voices"))
        if voices.available():
            self.chk_voices.setChecked(self.settings.value("voices", "true") == "true")
            self.chk_voices.setToolTip(tr("voices_tip"))
        else:
            self.chk_voices.setEnabled(False)
            self.chk_voices.setToolTip(tr("voices_missing"))
        h.addLayout(labeled(tr("sound"), self.chk_voices))

        self.b_out = QPushButton()
        self.b_out.setMinimumWidth(220)
        self.b_out.clicked.connect(self._pick_out)
        self.out_dir = self.settings.value("out_dir", "") or ""
        self._update_out()
        h.addLayout(labeled(tr("out_dir"), self.b_out))

        h.addStretch(1)
        st = QVBoxLayout()
        st.setSpacing(4)
        self.lbl_status = QLabel("")
        self.lbl_status.setObjectName("dim")
        self.lbl_status.setMinimumWidth(320)
        self.pbar = QProgressBar()
        self.pbar.setRange(0, 1000)
        self.pbar.hide()
        st.addWidget(self.lbl_status)
        st.addWidget(self.pbar)
        h.addLayout(st)
        self.b_cancel = QPushButton(tr("cancel"))
        self.b_cancel.clicked.connect(self._cancel)
        self.b_cancel.hide()
        h.addWidget(self.b_cancel)
        self.b_export = QPushButton(tr("export_btn"))
        self.b_export.setObjectName("primary")
        self.b_export.clicked.connect(self._export)
        h.addWidget(self.b_export)
        return bar

    # ------------------------------------------------------------------ fichiers
    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
            self.drop.setProperty("hover", "true")
            self.drop.style().polish(self.drop)

    def dragLeaveEvent(self, e):
        self.drop.setProperty("hover", "false")
        self.drop.style().polish(self.drop)

    def dropEvent(self, e):
        self.dragLeaveEvent(e)
        self._add_paths([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, tr("dlg_files"), self.settings.value("last_dir", ""),
                                                tr("dlg_filter"))
        if files:
            self.settings.setValue("last_dir", os.path.dirname(files[0]))
            self._add_paths(files)

    def _pick_dir(self):
        d = QFileDialog.getExistingDirectory(self, tr("dlg_dir"), self.settings.value("last_dir", ""))
        if d:
            self.settings.setValue("last_dir", d)
            self._add_paths([d])

    def _pick_out(self):
        d = QFileDialog.getExistingDirectory(self, tr("dlg_out"), self.out_dir or "")
        if d:
            self.out_dir = d
            self.settings.setValue("out_dir", d)
            self._update_out()
            self._mark_done()

    def _update_out(self):
        txt = self.out_dir or tr("next_to_videos")
        if len(txt) > 34:
            txt = "…" + txt[-33:]
        self.b_out.setText(txt)

    def _out_path(self, job):
        d = self.out_dir or os.path.dirname(job.video)
        return os.path.join(d, os.path.splitext(job.name)[0] + OUT_SUFFIX)

    def _clear(self):
        if self._is_busy:
            return
        self.paths, self.jobs = [], []
        self.list.clear()
        self.cards = []
        self.current = None
        self._set_empty(True)

    def _set_empty(self, empty):
        self.center.setCurrentIndex(0 if empty else 1)
        self.b_clear.setVisible(not empty)
        self._update_export_btn()

    # ------------------------------------------------------------------ analyse
    def _add_paths(self, paths):
        if self._is_busy:
            return
        new = [p for p in paths if p and p not in self.paths]
        if not new:
            return
        self.paths += new
        self._busy(True, tr("analyzing"))
        t = Task(lambda task: project.analyze(self.paths, progress=lambda f, s: task.progressed.emit(f, s)))
        t.progressed.connect(lambda f, s: self._progress(f, tr("analyzing_file", name=s)))
        t.succeeded.connect(self._analyzed)
        t.failed.connect(lambda m: (self._busy(False), QMessageBox.warning(self, "LapHUD", m)))
        self.task = t
        t.start()

    def _analyzed(self, jobs):
        self._busy(False)
        keep = {j.video: j for j in self.jobs}
        for j in jobs:                      # on garde les réglages déjà faits
            old = keep.get(j.video)
            if old:
                j.nudge, j.include = old.nudge, old.include
        self.jobs = jobs
        self._mark_done()
        self._populate()
        first = next((i for i, j in enumerate(jobs) if j.ready), 0 if jobs else -1)
        if first >= 0:
            self.list.setCurrentRow(first)
        self._update_export_btn()

    def _populate(self):
        """(Re)crée les cartes des sessions à partir de self.jobs."""
        jobs = self.jobs
        self.list.clear()
        self.cards = []
        for j in jobs:
            card = JobCard(j, self._toggle)
            it = QListWidgetItem()
            it.setSizeHint(QSize(360, card.sizeHint().height() + 4))
            self.list.addItem(it)
            self.list.setItemWidget(it, card)
            self.cards.append(card)
        self._set_empty(not jobs)
        ok = sum(j.ready for j in jobs)
        err = [j for j in jobs if j.status == "error"]
        self.lbl_status.setText(tr("ready_count", ok=ok) + (tr("ignored", n=len(err)) if err else ""))

    def _mark_done(self):
        for j in self.jobs:
            if j.ready and os.path.exists(self._out_path(j)):
                j.status, j.include, j.output = "done", False, self._out_path(j)
            elif j.status == "done" and not os.path.exists(self._out_path(j)):
                j.status, j.include = "ready", True
        for c in self.cards:
            c.refresh()
        self._update_export_btn()

    def _toggle(self, job, on):
        job.include = on
        self._update_export_btn()

    def _update_export_btn(self):
        n = sum(1 for j in self.jobs if j.include and j.ready and j.status != "done")
        running = self._is_busy
        self.b_export.setEnabled(n > 0 and not running)
        self.b_export.setText(tr("export_btn_n", n=n) if n else tr("export_btn"))

    # ------------------------------------------------------------------ aperçu
    def _select(self, row):
        for i, c in enumerate(self.cards):
            c.set_selected(i == row)
        if not (0 <= row < len(self.jobs)):
            return
        j = self.jobs[row]
        self.current = j
        self._stop_player()
        self.lbl_title.setText(j.name + (f"  ←  {os.path.basename(j.log.path)}" if j.log else ""))
        self.cmb_lap.clear()
        if j.session:
            self.cmb_lap.addItem(tr("goto_lap"), None)
            for L in j.session.timed:
                self.cmb_lap.addItem(tr("lap_item", n=L.number, time=fmt_time(L.duration)), L.t_start)
        self._update_sync_label()
        # position de départ : début du meilleur tour + 5 s (ou milieu de la vidéo)
        t = j.clip.duration / 2 if j.clip else 0
        if j.session and j.session.timed:
            best = min(j.session.timed, key=lambda L: L.duration)
            t = best.t_start + 5 + j.offset
        self._set_slider_time(t)
        self._load_frame()

    def _set_slider_time(self, t):
        j = self.current
        if not j or not j.clip:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(int(10000 * max(0, min(1, t / j.clip.duration))))
        self.slider.blockSignals(False)
        self._update_time_label()

    def _slider_time(self):
        j = self.current
        return (self.slider.value() / 10000) * j.clip.duration if j and j.clip else 0.0

    def _update_time_label(self):
        t = self._slider_time()
        self.lbl_time.setText(f"{int(t // 60)}:{t % 60:04.1f}")

    def _goto_lap(self, idx):
        ts = self.cmb_lap.itemData(idx)
        if ts is None or not self.current:
            return
        self._set_slider_time(ts + self.current.offset + 3)
        self._load_frame()

    def _scrub(self, _):
        self._update_time_label()
        self._stop_player()
        self._scrub_timer.start(120)

    def _load_frame(self):
        j = self.current
        if not j or not j.clip:
            return
        t = self._slider_time()
        if self.preview_task and self.preview_task.isRunning():
            self._pending_t = t
            return
        key = (j.video, round(t, 2))
        if key == self._frame_key and self._frame is not None:
            self._draw_preview()
            return
        w = 1280
        t_task = Task(lambda task: (key, grab_frame(j.video, t, w)))
        t_task.succeeded.connect(self._frame_ready)
        t_task.failed.connect(lambda m: self.lbl_status.setText(tr("preview_failed", err=m)))
        t_task.finished.connect(self._frame_task_finished)
        self.preview_task = t_task
        t_task.start()

    def _frame_ready(self, res):
        key, frame = res
        self._frame_key, self._frame = key, frame
        self._draw_preview()

    def _frame_task_finished(self):
        # l'utilisateur a bougé le curseur pendant le chargement : on charge la dernière position
        if self._pending_t is not None:
            self._pending_t = None
            self._load_frame()

    def _renderer(self, job, w, h):
        k = (id(job.session), w, h, self.cmb_theme.currentData(), i18n.get_lang())
        r = self._renderers.get(k)
        if r is None:
            r = self._renderers[k] = HudRenderer(job.session, w, h, theme=self.cmb_theme.currentData(),
                                                 lang=i18n.get_lang(), signature=True)
        return r

    def _draw_preview(self):
        j = self.current
        f = self._frame
        if j is None or f is None:
            return
        h, w = f.shape[:2]
        img = QImage(f.data, w, h, 3 * w, QImage.Format_RGB888).copy()
        if j.session:
            t = self._frame_key[1]
            st = j.session.state_at(t - j.offset)
            hud = self._renderer(j, w, h).render_frame(st)
            arr = hud.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
            himg = QImage(arr.data, w, h, 4 * w, QImage.Format_RGBA8888).copy()
            p = QPainter(img)
            p.drawImage(0, 0, himg)
            p.end()
        pm = QPixmap.fromImage(img).scaled(self.view.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.view.setPixmap(pm)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if self._frame is not None:
            QTimer.singleShot(0, self._draw_preview)

    def _theme_changed(self):
        self.settings.setValue("theme", self.cmb_theme.currentData())
        self._draw_preview()

    def _update_sync_label(self):
        j = self.current
        if not j or not j.sync:
            self.lbl_sync.setText("")
            return
        q = j.sync.quality
        col = {"excellent": style.OK, "ok": style.OK, "faible": style.WARN, "approx": style.WARN}[q]
        conf = f"{j.sync.confidence * 100:.0f}"
        txt = {"excellent": tr("sync_label_auto", c=conf), "ok": tr("sync_label_auto", c=conf),
               "faible": tr("sync_label_faible"), "approx": tr("sync_label_approx")}[q]
        man = f'  <span style="color:{style.TEXT}">{tr("manual", d=f"{j.nudge:+.2f}")}</span>' if j.nudge else ""
        self.sync_dot.set_color(col)
        self.lbl_sync.setText(f'<span style="color:{style.DIM}">{txt}</span>{man}')

    def _nudge(self, d):
        j = self.current
        if not j:
            return
        j.nudge = 0.0 if d is None else round(j.nudge + d, 3)
        self._update_sync_label()
        self._stop_player()
        self._draw_preview()

    # -- extrait vidéo
    def _preview_clip(self):
        j = self.current
        if not j or not j.ready or self._is_busy:
            return
        start = max(0.0, self._slider_time() - 1.0)
        # Le lecteur garde l'extrait précédent ouvert : on le libère, on nettoie, et chaque
        # extrait a un nom unique (sinon réécrire un fichier encore ouvert échoue sous Windows).
        self._stop_player()
        for f in os.listdir(self.tmp):
            if f.startswith("apercu_"):
                try:
                    os.remove(os.path.join(self.tmp, f))
                except OSError:
                    pass
        self._clip_n += 1
        out = os.path.join(self.tmp, f"apercu_{self._clip_n}.mp4")
        opts = export.ExportOptions(out_size=(1280, 720), hud_fps=30, theme=self.cmb_theme.currentData(),
                                    lang=i18n.get_lang(), signature=True,
                                    start=start, duration=10, workers=4)
        self._busy(True, tr("preparing_preview"))

        def job_fn(task):
            try:
                return export.export(j.video, j.clip, j.session, j.sync.offset + j.nudge, out, opts,
                                     progress=lambda f, s: task.progressed.emit(f, tr("preview_prefix", s=s)),
                                     cancel=lambda: task.cancelled)
            except RuntimeError:
                part = os.path.splitext(out)[0] + ".part.mp4"
                if os.path.isfile(part) and not task.cancelled:
                    return part          # extrait complet mais pas renommé : on le lit tel quel
                raise
        t = Task(job_fn)
        t.progressed.connect(self._progress)
        t.succeeded.connect(self._play)
        t.failed.connect(lambda m: (self._busy(False), QMessageBox.warning(self, "LapHUD", m)))
        self.task = t
        t.start()

    def _play(self, path):
        self._busy(False)
        self.view_stack.setCurrentIndex(1)
        self.player.setSource(QUrl.fromLocalFile(path))
        self.player.play()

    def _media_status(self, st):
        if st == QMediaPlayer.EndOfMedia:
            self._stop_player()

    def _stop_player(self):
        if self.player.playbackState() != QMediaPlayer.StoppedState:
            self.player.stop()
        self.player.setSource(QUrl())       # rend la main sur le fichier
        self.view_stack.setCurrentIndex(0)

    # ------------------------------------------------------------------ export
    def _export(self):
        todo = [j for j in self.jobs if j.include and j.ready and j.status != "done"]
        if not todo:
            return
        out_size = RESOLUTIONS[self.cmb_res.currentIndex()][1]
        fps = self.cmb_fps.currentData()
        theme = self.cmb_theme.currentData()
        kill = self.chk_voices.isChecked() and self.chk_voices.isEnabled()
        self.settings.setValue("res", self.cmb_res.currentIndex())
        self.settings.setValue("fps", self.cmb_fps.currentIndex())
        self.settings.setValue("voices", "true" if kill else "false")
        self._stop_player()
        keep_awake(True)
        low_priority(True)
        self._busy(True, tr("exporting"), cancellable=True)
        lang = i18n.get_lang()

        def run(task):
            done = 0
            for k, j in enumerate(todo, 1):
                if task.cancelled:
                    break
                out = self._out_path(j)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                task.logged.emit(f"start:{self.jobs.index(j)}")
                opts = export.ExportOptions(out_size=out_size, hud_fps=fps, theme=theme, lang=lang,
                                            remove_voices=kill, signature=True)
                try:
                    export.export(j.video, j.clip, j.session, j.sync.offset + j.nudge, out, opts,
                                  progress=lambda f, s, k=k: task.progressed.emit(
                                      f, tr("video_k", k=k, n=len(todo), s=s)),
                                  cancel=lambda: task.cancelled)
                    j.output = out
                    task.logged.emit(f"done:{self.jobs.index(j)}")
                    done += 1
                except export.Cancelled:
                    task.logged.emit(f"cancel:{self.jobs.index(j)}")
                    break
                except Exception as e:      # noqa: BLE001 — on passe à la vidéo suivante
                    task.logged.emit(f"error:{self.jobs.index(j)}:{e}")
            return done, len(todo)

        t = Task(run)
        t.progressed.connect(self._progress)
        t.logged.connect(self._export_event)
        t.succeeded.connect(self._exported)
        t.failed.connect(lambda m: (self._exported((0, len(todo))), QMessageBox.warning(self, "LapHUD", m)))
        self.task = t
        t.start()

    def _export_event(self, ev):
        kind, idx, *rest = ev.split(":", 2)
        j = self.jobs[int(idx)]
        card = self.cards[int(idx)]
        if kind == "start":
            j.status = "running"
            self.list.setCurrentRow(int(idx))
        elif kind == "done":
            j.status, j.include = "done", False
        elif kind == "cancel":
            j.status = "ready"
        elif kind == "error":
            j.status, j.message = "ready", tr("export_failed", err=rest[0] if rest else "?")
        card.refresh()

    def _exported(self, res):
        done, total = res
        keep_awake(False)
        low_priority(False)
        self._busy(False)
        self.lbl_status.setText(tr("finished", done=done, total=total))
        self._update_export_btn()
        if done:
            QMessageBox.information(self, "LapHUD",
                                    tr("exported_dlg", done=done, where=self.out_dir or tr("video_folders")))

    def _cancel(self):
        if self.task:
            self.task.cancel()
            self.lbl_status.setText(tr("stopping"))

    # ------------------------------------------------------------------ état
    def _busy(self, on, text="", cancellable=False):
        self._is_busy = on
        self.pbar.setVisible(on)
        self.pbar.setValue(0)
        self.b_cancel.setVisible(on and cancellable)
        self.b_play.setEnabled(not on)
        if text:
            self.lbl_status.setText(text)
        self._update_export_btn()

    def _progress(self, f, text):
        self.pbar.setValue(int(f * 1000))
        self.lbl_status.setText(text)

    def closeEvent(self, e):
        if self.task and self.task.isRunning():
            r = QMessageBox.question(self, "LapHUD", tr("quit_q"))
            if r != QMessageBox.Yes:
                e.ignore()
                return
            self.task.cancel()
            self.task.wait(15000)
        keep_awake(False)
        super().closeEvent(e)
