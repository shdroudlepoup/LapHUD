"""
Rendu du HUD avec Skia (le moteur de dessin de Chrome) : texte net, anti-crénelage,
dégradés, ombres douces. Indépendant de la résolution : tout est dessiné en
« unités 1080p » multipliées par s = hauteur / 1080.

Le HUD est découpé en panneaux. Chaque panneau a sa propre petite surface, ce qui
permet à l'export de n'envoyer à ffmpeg que les zones utiles (≈ 15 % de l'image en
4K) au lieu d'une image pleine transparente.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import skia

from .theme import THEMES, LABELS

GMAX = 1.5          # G au bord du cercle
PAD = 26            # marge autour des panneaux (ombres), en unités


def _c(t, a=None):
    """tuple RGBA -> couleur Skia (alpha optionnellement remplacé / multiplié)."""
    r, g, b, al = t
    if a is not None:
        al = int(max(0, min(255, a)))
    return skia.Color(r, g, b, al)


def new_surface(w, h):
    """Surface RGBA prémultipliée : même format partout, sinon Skia convertit chaque pixel
    à chaque collage (très lent)."""
    return skia.Surface.MakeRaster(skia.ImageInfo.Make(int(w), int(h), skia.kRGBA_8888_ColorType,
                                                       skia.kPremul_AlphaType))


def fmt_time(sec):
    if sec is None:
        return "-:--.---"
    m = int(sec // 60)
    return f"{m}:{sec - 60 * m:06.3f}"


@dataclass
class Panel:
    name: str
    x: int          # coin haut-gauche du CONTENU, en pixels écran
    y: int
    w: int
    h: int
    pad: int        # marge de la surface autour du contenu

    @property
    def sx(self):   # position de la surface à l'écran
        return self.x - self.pad

    @property
    def sy(self):
        return self.y - self.pad

    @property
    def sw(self):
        return self.w + 2 * self.pad

    @property
    def sh(self):
        return self.h + 2 * self.pad


class HudRenderer:
    def __init__(self, session, width, height, theme="broadcast", lang="fr", signature=False):
        self.session = session
        self.signature = signature      # petite mention « made with LAPHUD » en bas au centre
        self.W, self.H = width, height
        self.s = height / 1080.0
        self.th = THEMES[theme] if isinstance(theme, str) else theme
        self.lb = LABELS.get(lang, LABELS["fr"])
        self._tf = {}
        self._digit_w = {}
        self.vmax = max(120.0, float(session.speed.max() * 3.6)) if session is not None else 200.0
        self.panels = self._layout()
        self._static = {}

    # ------------------------------------------------------------------ mise en page
    def _layout(self):
        s, W, H = self.s, self.W, self.H
        M = 34
        u = lambda v: int(round(v * s))
        pad = u(PAD)
        tw = 420 if self.th.style != "minimal" else 400
        return [
            Panel("speed", u(M), u(M), u(272), u(118), pad),
            Panel("timer", (W - u(tw)) // 2, u(M), u(tw), u(140), pad),
            Panel("times", W - u(M) - u(330), u(M), u(330), u(118), pad),
            Panel("map", u(M), H - u(M) - u(224), u(224), u(224), pad),
            Panel("g", W - u(M) - u(224), H - u(M) - u(254), u(224), u(254), pad),
        ] + ([Panel("brand", (W - u(330)) // 2, H - u(M) - u(46), u(330), u(46), pad)]
             if self.signature else [])

    # ------------------------------------------------------------------ texte
    def font(self, which, size):
        path = self.th.font(which)
        tf = self._tf.get(path)
        if tf is None:
            tf = self._tf[path] = skia.Typeface.MakeFromFile(path)
        f = skia.Font(tf, size * self.s)
        f.setSubpixel(True)
        f.setEdging(skia.Font.Edging.kAntiAlias)
        return f

    def _dw(self, font):
        key = (font.getTypeface().uniqueID(), font.getSize())
        w = self._digit_w.get(key)
        if w is None:
            w = self._digit_w[key] = max(font.measureText(str(d)) for d in range(10))
        return w

    def text_width(self, txt, font, tab=True, spacing=0.0):
        dw = self._dw(font)
        w = 0.0
        for ch in txt:
            w += (dw if (tab and ch.isdigit()) else font.measureText(ch)) + spacing * self.s
        return w - (spacing * self.s if txt else 0)

    def text(self, c, txt, x, y, font, color, align="l", tab=True, spacing=0.0, shadow=False):
        """Texte à chasse fixe pour les chiffres (les nombres ne « dansent » pas)."""
        w = self.text_width(txt, font, tab, spacing)
        if align == "c":
            x -= w / 2
        elif align == "r":
            x -= w
        p = skia.Paint(AntiAlias=True, Color=color)
        if shadow or self.th.style == "minimal":
            p.setImageFilter(skia.ImageFilters.DropShadow(
                0, 2 * self.s, 3.5 * self.s, 3.5 * self.s, _c(self.th.shadow)))
        dw = self._dw(font)
        for ch in txt:
            cw = font.measureText(ch)
            if tab and ch.isdigit():
                c.drawString(ch, x + (dw - cw) / 2, y, font, p)
                x += dw
            else:
                c.drawString(ch, x, y, font, p)
                x += cw
            x += spacing * self.s
        return w

    # ------------------------------------------------------------------ fonds de panneaux
    def _panel_bg(self, c, w, h, accent_left=False):
        s, th = self.s, self.th
        if th.style == "minimal":
            return
        if th.style == "glass":
            r = 14 * s
            rect = skia.Rect.MakeWH(w, h)
            sh = skia.Paint(AntiAlias=True, Color=_c(th.shadow),
                            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 9 * s))
            c.drawRRect(skia.RRect.MakeRectXY(rect.makeOffset(0, 4 * s), r, r), sh)
            fill = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, 0), skia.Point(0, h)], [_c(th.panel2), _c(th.panel)]))
            c.drawRRect(skia.RRect.MakeRectXY(rect, r, r), fill)
            # reflet discret en haut
            hl = skia.Paint(AntiAlias=True, Shader=skia.GradientShader.MakeLinear(
                [skia.Point(0, 0), skia.Point(0, h * 0.5)],
                [skia.Color(255, 255, 255, 14), skia.Color(255, 255, 255, 0)]))
            c.drawRRect(skia.RRect.MakeRectXY(rect, r, r), hl)
            bd = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                            StrokeWidth=max(1.0, 1.0 * s), Color=_c(th.border))
            c.drawRRect(skia.RRect.MakeRectXY(rect.makeInset(0.5 * s, 0.5 * s), r, r), bd)
            if accent_left:
                c.save()
                c.clipRRect(skia.RRect.MakeRectXY(rect, r, r), doAntiAlias=True)
                c.drawRect(skia.Rect.MakeWH(5 * s, h), skia.Paint(AntiAlias=True, Color=_c(th.accent)))
                c.restore()
        elif th.style == "broadcast":
            k = min(h * 0.16, 19 * s)
            path = skia.Path()
            path.moveTo(k, 0); path.lineTo(w, 0); path.lineTo(w - k, h); path.lineTo(0, h); path.close()
            sh = skia.Paint(AntiAlias=True, Color=_c(th.shadow, 110),
                            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 7 * s))
            c.save(); c.translate(0, 3 * s); c.drawPath(path, sh); c.restore()
            c.drawPath(path, skia.Paint(AntiAlias=True, Color=_c(th.panel)))
            if accent_left:
                a = skia.Path()
                a.moveTo(k, 0); a.lineTo(k + 7 * s, 0); a.lineTo(7 * s, h); a.lineTo(0, h); a.close()
                c.drawPath(a, skia.Paint(AntiAlias=True, Color=_c(th.accent)))
            # liseré rouge en haut
            top = skia.Path()
            top.moveTo(k, 0); top.lineTo(w, 0); top.lineTo(w - 3 * s * k / h, 3 * s); top.lineTo(k - 3 * s * k / h, 3 * s); top.close()
            c.drawPath(top, skia.Paint(AntiAlias=True, Color=_c(th.accent)))

    def _pill(self, c, x, y, w, h, color):
        s, th = self.s, self.th
        if th.style == "broadcast":
            k = h * 0.25
            p = skia.Path()
            p.moveTo(x + k, y); p.lineTo(x + w, y); p.lineTo(x + w - k, y + h); p.lineTo(x, y + h); p.close()
            c.drawPath(p, skia.Paint(AntiAlias=True, Color=color))
        else:
            sh = skia.Paint(AntiAlias=True, Color=_c(th.shadow, 90),
                            MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6 * s))
            r = h / 2
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y + 2 * s, w, h), r, r), sh)
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(x, y, w, h), r, r),
                        skia.Paint(AntiAlias=True, Color=color))

    # ------------------------------------------------------------------ couches statiques
    def _static_layer(self, p):
        img = self._static.get(p.name)
        if img is not None:
            return img
        surf = new_surface(p.sw, p.sh)
        c = surf.getCanvas()
        c.clear(skia.ColorTRANSPARENT)
        c.translate(p.pad, p.pad)
        if p.name == "speed":
            self._panel_bg(c, p.w, p.h, accent_left=True)
        elif p.name == "times":
            self._panel_bg(c, p.w, p.h)
            if self.th.style != "minimal":
                c.drawLine(18 * self.s, p.h / 2, p.w - 18 * self.s, p.h / 2,
                           skia.Paint(AntiAlias=True, Color=_c(self.th.border, 40), StrokeWidth=1 * self.s))
        elif p.name == "timer":
            if self.th.style != "minimal":
                self._panel_bg(c, p.w, 86 * self.s)
        elif p.name == "map":
            self._panel_bg(c, p.w, p.h)
            self._draw_track(c, p)
        elif p.name == "g":
            self._panel_bg(c, p.w, p.h)
            self._draw_g_grid(c, p)
        elif p.name == "brand":
            self._draw_brand(c, p)
        img = self._static[p.name] = surf.makeImageSnapshot()
        return img

    # ------------------------------------------------------------------ panneaux dynamiques
    def draw_panel(self, c, p, st):
        """Dessine le panneau p (coordonnées locales au contenu)."""
        getattr(self, "_p_" + p.name)(c, p, st)

    def _p_speed(self, c, p, st):
        s, th = self.s, self.th
        x0 = (34 if th.style == "broadcast" else 24) * s
        self.text(c, f"{st.speed_kmh:.0f}", x0, 86 * s, self.font("font_num_heavy", 88), _c(th.text))
        self.text(c, self.lb["unit"], p.w - 20 * s, 38 * s, self.font("font_label", 17),
                  _c(th.accent), align="r", tab=False, spacing=1.6)
        if st.lap_kind == "timed":
            lab = f"{self.lb['lap']} {st.lap_number}"
        else:
            lab = self.lb["out"] if st.lap_kind == "out" else self.lb["in"]
        self.text(c, lab, p.w - 20 * s, 86 * s, self.font("font_label", 17), _c(th.dim),
                  align="r", tab=False, spacing=1.2)
        # jauge de vitesse
        bx, by, bw, bh = x0, p.h - 16 * s, p.w - x0 - 20 * s, 4 * s
        r = bh / 2
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, by, bw, bh), r, r),
                    skia.Paint(AntiAlias=True, Color=skia.Color(255, 255, 255, 30 if th.style != "minimal" else 60)))
        f = max(0.0, min(1.0, st.speed_kmh / self.vmax))
        if f > 0.01:
            a = th.accent
            sh = skia.GradientShader.MakeLinear([skia.Point(bx, 0), skia.Point(bx + bw, 0)],
                                                [_c(a, 150), _c(a, 255)])
            c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeXYWH(bx, by, bw * f, bh), r, r),
                        skia.Paint(AntiAlias=True, Shader=sh))

    def _p_timer(self, c, p, st):
        s, th = self.s, self.th
        cx = p.w / 2
        if st.lap_kind == "timed" and st.lap_elapsed is not None:
            self.text(c, fmt_time(st.lap_elapsed), cx, 66 * s, self.font("font_num", 68), _c(th.text), align="c")
        else:
            lab = self.lb["out"] if st.lap_kind == "out" else self.lb["in"]
            self.text(c, lab, cx, 60 * s, self.font("font_label", 40), _c(th.dim), align="c", tab=False, spacing=3)

        y = 96 * s
        fl = st.flash
        if fl:
            # bandeau du tour terminé, fondu d'entrée/sortie
            age = fl["age"]
            alpha = min(1.0, age / 0.25, max(0.0, (5.0 - age) / 0.5))
            col = th.best if fl["is_best"] else th.panel2
            title = self.lb["best_lap"] if fl["is_best"] else f"{self.lb['lap']} {fl['number']}"
            f1 = self.font("font_label", 17)
            f2 = self.font("font_num", 30)
            t2 = fmt_time(fl["time"])
            extra = "" if fl["is_best"] or fl["vs_best"] is None else f"  {fl['vs_best']:+.2f}"
            w1 = self.text_width(title, f1, False, 1.4)
            w2 = self.text_width(t2, f2)
            w3 = self.text_width(extra, f2) if extra else 0
            bw = w1 + w2 + w3 + 60 * s
            c.saveLayerAlpha(None, int(255 * alpha))
            self._pill(c, cx - bw / 2, y, bw, 40 * s, _c(col, 240))
            xx = cx - bw / 2 + 24 * s
            self.text(c, title, xx, y + 26.5 * s, f1, _c(th.text if fl["is_best"] else th.dim),
                      tab=False, spacing=1.4, shadow=False)
            xx += w1 + 12 * s
            self.text(c, t2, xx, y + 31 * s, f2, _c(th.text))
            if extra:
                self.text(c, extra, xx + w2, y + 31 * s, f2, _c(th.slower))
            c.restore()
        elif st.delta is not None:
            d = st.delta
            col = th.faster if d <= 0 else th.slower
            txt = f"{d:+.2f}".replace("-", "−")
            f = self.font("font_num", 30)
            tw = self.text_width(txt, f)
            if th.style == "minimal":
                self.text(c, txt, cx, y + 31 * s, f, _c(col), align="c")
            else:
                bw = tw + 40 * s
                self._pill(c, cx - bw / 2, y, bw, 40 * s, _c(col, 235))
                self.text(c, txt, cx, y + 31 * s, f, skia.Color(10, 12, 16, 255), align="c")

    def _p_times(self, c, p, st):
        s, th = self.s, self.th
        fl, fv = self.font("font_label", 16), self.font("font_num", 34)
        for row, (lab, val, col) in enumerate((
                (self.lb["best"], st.best, th.best),
                (self.lb["last"], st.last, th.text))):
            yb = (row * p.h / 2)
            self.text(c, lab, 20 * s, yb + 37 * s, fl, _c(th.dim), tab=False, spacing=1.6)
            self.text(c, fmt_time(val), p.w - 20 * s, yb + 44 * s, fv,
                      _c(col if val is not None else th.dim), align="r")

    def _map_tf(self, p):
        inset = 22 * self.s
        span = p.w - 2 * inset
        return lambda u, v: (inset + u * span, inset + v * span)

    def _draw_track(self, c, p):
        s, th = self.s, self.th
        sess = self.session
        if sess is None:
            return
        tf = self._map_tf(p)
        pts = sess.map_outline
        step = max(1, len(pts) // 1500)
        path = skia.Path()
        x, y = tf(*pts[0]); path.moveTo(x, y)
        for u, v in pts[::step][1:]:
            x, y = tf(u, v); path.lineTo(x, y)
        path.close()
        edge = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=7.5 * s,
                          StrokeJoin=skia.Paint.kRound_Join, StrokeCap=skia.Paint.kRound_Cap,
                          Color=_c(th.track_edge, 200 if th.style == "minimal" else 150))
        if th.style == "minimal":
            edge.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 2.5 * s))
        c.drawPath(path, edge)
        c.drawPath(path, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=3.4 * s,
                                    StrokeJoin=skia.Paint.kRound_Join, Color=_c(th.track)))
        if sess.map_finish:
            fx, fy, hx, hy = sess.map_finish
            X, Y = tf(fx, fy)
            nx, ny = -hy, hx
            L = 9 * s
            c.drawLine(X - nx * L, Y - ny * L, X + nx * L, Y + ny * L,
                       skia.Paint(AntiAlias=True, StrokeWidth=3.2 * s, Color=_c(th.accent),
                                  StrokeCap=skia.Paint.kRound_Cap))

    def _p_map(self, c, p, st):
        s, th = self.s, self.th
        x, y = self._map_tf(p)(*st.map_xy)
        glow = skia.Paint(AntiAlias=True, Color=_c(th.accent, 120),
                          MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6 * s))
        c.drawCircle(x, y, 10 * s, glow)
        c.drawCircle(x, y, 7 * s, skia.Paint(AntiAlias=True, Color=_c(th.accent)))
        c.drawCircle(x, y, 7 * s, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                             StrokeWidth=2.2 * s, Color=_c(th.text)))

    def _g_geom(self, p):
        return p.w / 2, 112 * self.s, 90 * self.s

    def _draw_g_grid(self, c, p):
        s, th = self.s, self.th
        cx, cy, R = self._g_geom(p)
        mini = th.style == "minimal"
        if mini:
            c.drawCircle(cx, cy, R, skia.Paint(AntiAlias=True, Color=skia.Color(0, 0, 0, 70),
                                               MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 12 * s)))
        for g in (0.5, 1.0, 1.5):
            rr = R * g / GMAX
            c.drawCircle(cx, cy, rr, skia.Paint(
                AntiAlias=True, Style=skia.Paint.kStroke_Style,
                StrokeWidth=(1.6 if g == 1.0 else 1.1) * s,
                Color=skia.Color(255, 255, 255, 75 if g == 1.0 else 40)))
        ln = skia.Paint(AntiAlias=True, StrokeWidth=1 * s, Color=skia.Color(255, 255, 255, 30))
        c.drawLine(cx - R, cy, cx + R, cy, ln)
        c.drawLine(cx, cy - R, cx, cy + R, ln)
        f = self.font("font_label", 12)
        self.text(c, "1G", cx + R / GMAX * 0.72 + 3 * s, cy - R / GMAX * 0.72 - 3 * s, f,
                  skia.Color(255, 255, 255, 110), tab=False)

    def _g_xy(self, p, glat, glon):
        cx, cy, R = self._g_geom(p)
        # virage à droite -> point à gauche (force ressentie) ; accélération -> bas
        dx, dy = -glat / GMAX, glon / GMAX
        n = math.hypot(dx, dy)
        if n > 1:
            dx, dy = dx / n, dy / n
        return cx + dx * R, cy + dy * R

    def _draw_brand(self, c, p):
        """« made with LAPHUD » : discret, lisible sur n'importe quel fond."""
        s = self.s
        f_small = self.font("font_label", 19)
        tf = skia.Typeface.MakeFromFile(self.th.font("font_num_heavy"))
        f_logo = skia.Font(tf, 33 * s)
        f_logo.setSkewX(-0.2)
        f_logo.setEdging(skia.Font.Edging.kAntiAlias)
        pre = "made with  "
        w_pre = self.text_width(pre, f_small, False, 0.8)
        w_lap, w_hud = f_logo.measureText("LAP"), f_logo.measureText("HUD")
        # petit panneau sombre biseauté (même famille que le HUD) : lisible sur ciel ou bitume
        tw = w_pre + w_lap + w_hud
        bw, bh = tw + 44 * s, p.h
        bx = (p.w - bw) / 2
        k = bh * 0.25
        path = skia.Path()
        path.moveTo(bx + k, 0); path.lineTo(bx + bw, 0); path.lineTo(bx + bw - k, bh); path.lineTo(bx, bh); path.close()
        c.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color(8, 9, 12, 150)))
        x = (p.w - tw) / 2
        y = p.h / 2 + 11 * s
        shadow = skia.ImageFilters.DropShadow(0, 1.5 * s, 3 * s, 3 * s, skia.Color(0, 0, 0, 200))
        self.text(c, pre, x, y - 2 * s, f_small, skia.Color(236, 238, 242, 225), tab=False, spacing=0.8, shadow=True)
        x += w_pre
        for txt, col, w in (("LAP", _c(self.th.text, 235), w_lap), ("HUD", _c(self.th.accent, 245), w_hud)):
            c.drawString(txt, x, y, f_logo, skia.Paint(AntiAlias=True, Color=col, ImageFilter=shadow))
            x += w

    def _p_brand(self, c, p, st):
        pass                     # tout est dans le fond fixe

    def _p_g(self, c, p, st):
        s, th = self.s, self.th
        pts = [self._g_xy(p, a, b) for a, b in st.g_trail]
        for k in range(len(pts) - 1, 0, -1):
            a = int(200 * (1 - k / len(pts)) ** 1.5)
            c.drawLine(*pts[k], *pts[k - 1], skia.Paint(
                AntiAlias=True, StrokeWidth=(5 - 3 * k / len(pts)) * s, Color=_c(th.accent, a),
                StrokeCap=skia.Paint.kRound_Cap))
        x, y = self._g_xy(p, st.g_lat, st.g_lon)
        c.drawCircle(x, y, 12 * s, skia.Paint(AntiAlias=True, Color=_c(th.accent, 110),
                                              MaskFilter=skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, 6 * s)))
        c.drawCircle(x, y, 8.5 * s, skia.Paint(AntiAlias=True, Color=_c(th.accent)))
        c.drawCircle(x, y, 8.5 * s, skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                               StrokeWidth=2.2 * s, Color=_c(th.text)))
        gt = math.hypot(st.g_lat, st.g_lon)
        fv, fu = self.font("font_num", 32), self.font("font_label", 17)
        w1 = self.text_width(f"{gt:.2f}", fv)
        w2 = self.text_width("G", fu, False)
        x0 = p.w / 2 - (w1 + 6 * s + w2) / 2
        self.text(c, f"{gt:.2f}", x0, p.h - 16 * s, fv, _c(th.text))
        self.text(c, "G", x0 + w1 + 6 * s, p.h - 16 * s, fu, _c(th.dim), tab=False)

    # ------------------------------------------------------------------ rendu
    def static_array(self, p):
        """Fond fixe du panneau p en tableau RGBA prémultiplié (pour copie mémoire rapide)."""
        return self._static_layer(p).toarray(colorType=skia.kRGBA_8888_ColorType,
                                             alphaType=skia.kPremul_AlphaType)

    def draw_into(self, c, p, st, x, y, with_static=True):
        """Dessine le panneau p (avec sa marge) à la position (x, y) d'un canevas existant.
        with_static=False : le fond fixe a déjà été copié à cet endroit."""
        if not st.active:
            return
        c.save()
        c.translate(x, y)
        c.clipRect(skia.Rect.MakeWH(p.sw, p.sh))
        if with_static:
            c.drawImage(self._static_layer(p), 0, 0)
        c.translate(p.pad, p.pad)
        self.draw_panel(c, p, st)
        c.restore()

    def render_array(self, st, arr):
        """Dessine le HUD complet directement dans arr (H, L, 4) uint8, RGBA prémultiplié."""
        surf = skia.Surface(arr, colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
        c = surf.getCanvas()
        c.clear(skia.ColorTRANSPARENT)
        for p in self.panels:
            self.draw_into(c, p, st, p.sx, p.sy)
        return arr

    def render_panel(self, p, st):
        """Surface du panneau p (avec sa marge) -> skia.Image."""
        surf = new_surface(p.sw, p.sh)
        c = surf.getCanvas()
        c.clear(skia.ColorTRANSPARENT)
        if st.active:
            c.drawImage(self._static_layer(p), 0, 0)
            c.translate(p.pad, p.pad)
            self.draw_panel(c, p, st)
        return surf.makeImageSnapshot()

    def render_frame(self, st, background=None):
        """Image complète (aperçu). background : skia.Image optionnelle."""
        surf = new_surface(self.W, self.H)
        c = surf.getCanvas()
        c.clear(skia.ColorTRANSPARENT)
        if background is not None:
            c.drawImageRect(background, skia.Rect.MakeWH(self.W, self.H),
                            skia.SamplingOptions(skia.FilterMode.kLinear))
        for p in self.panels:
            c.drawImage(self.render_panel(p, st), p.sx, p.sy)
        return surf.makeImageSnapshot()
