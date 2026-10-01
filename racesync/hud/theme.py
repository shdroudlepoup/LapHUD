"""Thèmes du HUD : couleurs, polices et style des panneaux."""
from __future__ import annotations

import os
from dataclasses import dataclass, field

FONT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "fonts")


def rgba(hexstr, a=255):
    h = hexstr.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)


@dataclass
class Theme:
    key: str
    name: str
    style: str                          # "glass", "broadcast", "minimal"
    font_num: str                       # chiffres
    font_num_heavy: str                 # gros chiffres (vitesse)
    font_label: str                     # libellés
    accent: tuple = rgba("#e42a2e")
    text: tuple = rgba("#ffffff")
    dim: tuple = rgba("#a9b0bc")
    faster: tuple = rgba("#22c55e")
    slower: tuple = rgba("#ef4444")
    best: tuple = rgba("#a855f7")       # violet = meilleur tour (convention F1)
    panel: tuple = rgba("#0d0f14", 200)
    panel2: tuple = rgba("#161922", 215)
    border: tuple = rgba("#ffffff", 22)
    shadow: tuple = rgba("#000000", 130)
    track: tuple = rgba("#eef1f6", 235)
    track_edge: tuple = rgba("#000000", 150)
    extra: dict = field(default_factory=dict)

    def font(self, which):
        return os.path.join(FONT_DIR, getattr(self, which))


THEMES = {
    "glass": Theme(
        key="glass", name="Carbone", style="glass",
        font_num="BarlowSemiCondensed-SemiBold.ttf",
        font_num_heavy="BarlowSemiCondensed-ExtraBold.ttf",
        font_label="BarlowSemiCondensed-SemiBold.ttf",
    ),
    "broadcast": Theme(
        key="broadcast", name="Broadcast", style="broadcast",
        font_num="TitilliumWeb-Bold.ttf",
        font_num_heavy="TitilliumWeb-Black.ttf",
        font_label="TitilliumWeb-Bold.ttf",
        panel=rgba("#0a0b0e", 235), panel2=rgba("#1b1d24", 240),
        border=rgba("#ffffff", 0),
    ),
    "minimal": Theme(
        key="minimal", name="Épuré", style="minimal",
        font_num="ChakraPetch-SemiBold.ttf",
        font_num_heavy="ChakraPetch-Bold.ttf",
        font_label="ChakraPetch-Medium.ttf",
        panel=rgba("#000000", 0), panel2=rgba("#000000", 0),
        shadow=rgba("#000000", 190),
    ),
}

LABELS = {
    "fr": {"unit": "KM/H", "lap": "TOUR", "out": "OUT LAP", "in": "IN LAP",
           "best": "MEILLEUR", "last": "DERNIER", "best_lap": "MEILLEUR TOUR"},
    "en": {"unit": "KM/H", "lap": "LAP", "out": "OUT LAP", "in": "IN LAP",
           "best": "BEST", "last": "LAST", "best_lap": "BEST LAP"},
}
