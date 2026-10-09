"""Thème visuel de l'application (sombre, esprit F1)."""
import os

_CHECK = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "check.svg").replace("\\", "/")

BG = "#0b0c10"
PANEL = "#14161c"
PANEL2 = "#1b1e26"
LINE = "#262a34"
TEXT = "#eceef2"
DIM = "#8c929e"
ACCENT = "#e42a2e"
ACCENT_HI = "#ff3b3f"
OK = "#22c55e"
WARN = "#f5a524"
BAD = "#ef4444"
PURPLE = "#a855f7"

QSS = f"""
* {{ font-family: "Titillium Web"; color: {TEXT}; }}
QMainWindow, QWidget#root {{ background: {BG}; }}
QWidget {{ font-size: 10.5pt; }}
QLabel#logo {{ font-size: 22pt; font-weight: 900; font-style: italic; }}
QLabel#tagline {{ color: {DIM}; font-size: 10pt; }}
QLabel#section {{ color: {DIM}; font-size: 8.5pt; font-weight: 700; letter-spacing: 1.5px; }}
QLabel#dim {{ color: {DIM}; }}
QLabel#big {{ font-size: 13pt; font-weight: 700; }}
QFrame#panel {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; }}
QFrame#topline {{ background: {ACCENT}; max-height: 3px; min-height: 3px; border: none; }}
QFrame#drop {{ background: {PANEL}; border: 2px dashed {LINE}; border-radius: 12px; }}
QFrame#drop[hover="true"] {{ border-color: {ACCENT}; background: #1a1215; }}

QPushButton {{ background: {PANEL2}; border: 1px solid {LINE}; border-radius: 7px;
              padding: 7px 14px; font-weight: 600; }}
QPushButton:hover {{ background: #232731; border-color: #343946; }}
QPushButton:pressed {{ background: #191c23; }}
QPushButton:disabled {{ color: #555b66; background: #15171c; border-color: #1d2027; }}
QPushButton#primary {{ background: {ACCENT}; border: none; color: white; font-size: 12pt;
                      font-weight: 800; padding: 10px 26px; letter-spacing: 1px; }}
QPushButton#primary:hover {{ background: {ACCENT_HI}; }}
QPushButton#primary:disabled {{ background: #3a1d1f; color: #8f6f71; }}
QPushButton#nudge {{ padding: 5px 9px; min-width: 46px; font-family: "Titillium Web"; }}
QFrame#lang {{ border: 1px solid {LINE}; border-radius: 7px; background: {PANEL}; }}
QPushButton#langbtn {{ background: transparent; border: none; border-radius: 6px; padding: 6px 10px;
                      color: {DIM}; font-weight: 700; min-width: 34px; }}
QPushButton#langbtn:hover {{ color: {TEXT}; }}
QPushButton#langbtn:checked {{ background: {ACCENT}; color: white; }}
QPushButton#ghost {{ background: transparent; border: none; color: {DIM}; padding: 4px 8px; }}
QPushButton#ghost:hover {{ color: {TEXT}; }}

QComboBox {{ background: {PANEL2}; border: 1px solid {LINE}; border-radius: 7px; padding: 6px 10px; min-width: 110px; }}
QComboBox:hover {{ border-color: #343946; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{ background: {PANEL2}; border: 1px solid {LINE}; selection-background-color: {ACCENT};
                               outline: none; padding: 4px; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 18px; height: 18px; border-radius: 5px; border: 1px solid #3a3f4b; background: {PANEL2}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; image: url({_CHECK}); }}
QCheckBox:disabled {{ color: #555b66; }}

QSlider::groove:horizontal {{ height: 6px; background: {PANEL2}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: white; width: 16px; height: 16px; margin: -5px 0; border-radius: 8px; }}

QProgressBar {{ background: {PANEL2}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 4px; }}

QListWidget {{ background: transparent; border: none; outline: none; }}
QListWidget::item {{ border: none; margin: 0 0 8px 0; }}
QListWidget::item:selected {{ background: transparent; }}
QFrame#card {{ background: {PANEL}; border: 1px solid {LINE}; border-radius: 10px; }}
QFrame#card[selected="true"] {{ border: 1px solid {ACCENT}; background: #181419; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #2a2e38; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{ background: {PANEL2}; color: {TEXT}; border: 1px solid {LINE}; padding: 6px; }}
QPlainTextEdit {{ background: #08090c; border: 1px solid {LINE}; border-radius: 8px; color: {DIM};
                  font-family: Consolas; font-size: 9pt; }}
"""
