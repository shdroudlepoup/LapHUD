"""
Traductions (français / anglais).

    tr("clé", **valeurs)   -> texte dans la langue active
    Msg("clé", **valeurs)  -> message traduit au moment où on l'affiche (str(msg)) :
                              changer de langue met à jour les messages déjà créés.

Ajouter une langue : copier le bloc "en", traduire, et l'ajouter à LANGS.
"""
from __future__ import annotations

LANGS = {"fr": "Français", "en": "English"}
_lang = "fr"

T = {
    "fr": {
        # en-tête et zone de dépôt
        "tagline": "Le HUD télémétrie de tes vidéos embarquées · GoPro + RaceBox / RaceChrono",
        "btn_files": "+  Fichiers", "btn_dir": "+  Dossier", "btn_clear": "Vider",
        "drop_title": "Glisse ici tes vidéos GoPro et tes CSV RaceBox ou RaceChrono",
        "drop_sub": "ou un dossier entier : LapHUD retrouve tout seul quelle vidéo va avec quelle session\n"
                    "et les synchronise au centième grâce aux accéléromètres.",
        "drop_hint": "RaceBox : export CSV « Custom », date et heure en UTC  ·  RaceChrono : Exporter → CSV (v3)",
        "lang_tip": "Langue de l'application et du HUD",
        # sessions et aperçu
        "sessions": "SESSIONS", "preview": "APERÇU",
        "goto_lap": "Aller au tour…", "goto_lap_tip": "Aller directement à un tour",
        "lap_item": "Tour {n}  ·  {time}",
        "nudge_label": "Décaler le HUD", "nudge_hint": "Si le HUD est en avance ou en retard sur l'image",
        "nudge_tip": "Décale le HUD de {d} s", "auto": "Auto", "auto_tip": "Revenir à la synchro automatique",
        "preview_btn": "▶  Aperçu 10 s",
        "preview_tip": "Fabrique un extrait de 10 s avec le HUD à partir de la position actuelle",
        "preview_failed": "Aperçu impossible : {err}",
        "preparing_preview": "Préparation de l'aperçu…", "preview_prefix": "Aperçu · {s}",
        # carte de session
        "laps_1": "1 tour", "laps_n": "{n} tours", "card_best": "meilleur {t}",
        "card_done": "Exportée ✓", "card_running": "Export en cours…",
        "sync_excellent": "synchro auto excellente", "sync_ok": "synchro auto correcte",
        "sync_faible": "synchro incertaine, vérifie l'aperçu", "sync_approx": "synchro approximative (heure GPS)",
        "no_match": "aucune session RaceBox ou RaceChrono ne correspond",
        # ligne de synchro
        "sync_label_auto": "Synchro auto · confiance {c} %",
        "sync_label_faible": "Synchro incertaine · vérifie avec l'aperçu",
        "sync_label_approx": "Synchro par l'heure GPS seulement · vérifie avec l'aperçu",
        "manual": "· réglage manuel {d} s",
        # barre du bas
        "style": "STYLE", "resolution": "RÉSOLUTION", "hud": "HUD", "sound": "SON", "out_dir": "DOSSIER DE SORTIE",
        "res_original": "Originale", "fps30": "30 i/s", "fps60": "60 i/s (plus fluide)",
        "voices": "Retirer les voix",
        "signature": "made with LapHUD", "signature_lbl": "SIGNATURE",
        "signature_tip": "Ajoute une petite mention « made with LAPHUD » en bas de la vidéo",
        "voices_tip": "Garde le son du moteur et de la route (modèle BS-Roformer)",
        "voices_missing": "Installe « audio-separator » pour activer cette option",
        "next_to_videos": "À côté des vidéos", "cancel": "Annuler",
        "export_btn": "EXPORTER", "export_btn_n": "EXPORTER  ({n})",
        "theme_broadcast": "Broadcast", "theme_glass": "Carbone", "theme_minimal": "Épuré",
        # dialogues
        "dlg_files": "Vidéos GoPro et CSV RaceBox / RaceChrono",
        "dlg_filter": "Vidéos et données (*.mp4 *.MP4 *.csv);;Tous les fichiers (*)",
        "dlg_dir": "Dossier de roulage", "dlg_out": "Dossier de sortie",
        "quit_q": "Un export est en cours. Quitter quand même ?",
        # état
        "analyzing": "Analyse des fichiers…", "analyzing_file": "Analyse · {name}",
        "ready_count": "{ok} vidéo(s) prête(s)", "ignored": " · {n} ignorée(s)",
        "exporting": "Export…", "video_k": "Vidéo {k}/{n} · {s}",
        "export_failed": "Échec de l'export : {err}",
        "finished": "Terminé : {done}/{total} vidéo(s) exportée(s)",
        "exported_dlg": "{done} vidéo(s) exportée(s) dans :\n{where}", "video_folders": "les dossiers des vidéos",
        "stopping": "Arrêt en cours…",
        # synchro (notes)
        "note_local_tz": "heure du CSV en local ({h:+d} h) corrigée",
        "note_no_gps_time": "pas d'heure GPS dans la vidéo : recherche sur toute la durée",
        "note_ambiguous": "plusieurs décalages possibles",
        "note_no_imu": "pas d'accéléromètre dans la vidéo",
        "note_no_overlap": "pas assez de recouvrement entre la vidéo et les données",
        # export
        "prog": "{pct:4.1f} % · {rate:.2f}× temps réel · reste {m} min {s:02d} s",
        "voices_finishing": "Suppression des voix (fin)…", "voices_mux": "Pose du son sans voix…",
        "done_in": "Terminé en {m} min {s:02d} s",
        "err_ffmpeg": "ffmpeg a échoué : {e}", "err_ffmpeg_stopped": "ffmpeg s'est arrêté : {e}",
        "err_incomplete": "vidéo incomplète ({got:.0f} s sur {dur:.0f} s)",
        "err_rename": "vidéo terminée mais impossible de la renommer (fichier bloqué, antivirus ?). Elle est ici : {path}",
        "ffmpeg_missing": "ffmpeg introuvable. Installe-le (https://ffmpeg.org) ou place ffmpeg.exe "
                          "dans le dossier « ffmpeg » à côté de LapHUD.",
        # lecture des fichiers
        "err_moov": "fichier MP4 illisible (pas de boîte moov)", "err_no_video": "pas de piste vidéo",
        "err_no_gpmf": "pas de télémétrie GoPro (piste gpmd absente)",
        "err_csv_empty": "CSV RaceBox vide ou illisible",
        "err_csv_columns": "ce n'est pas un export CSV RaceBox (colonnes introuvables)",
    },
    "en": {
        "tagline": "Telemetry HUD for your onboard videos · GoPro + RaceBox / RaceChrono",
        "btn_files": "+  Files", "btn_dir": "+  Folder", "btn_clear": "Clear",
        "drop_title": "Drop your GoPro videos and RaceBox or RaceChrono CSV files here",
        "drop_sub": "or a whole folder: LapHUD works out which video goes with which session\n"
                    "and syncs them to the hundredth of a second using the accelerometers.",
        "drop_hint": "RaceBox: “Custom” CSV export, date and time in UTC  ·  RaceChrono: Export → CSV (v3)",
        "lang_tip": "Language of the app and the HUD",
        "sessions": "SESSIONS", "preview": "PREVIEW",
        "goto_lap": "Go to lap…", "goto_lap_tip": "Jump straight to a lap",
        "lap_item": "Lap {n}  ·  {time}",
        "nudge_label": "Shift the HUD", "nudge_hint": "If the HUD runs ahead of or behind the picture",
        "nudge_tip": "Shifts the HUD by {d} s", "auto": "Auto", "auto_tip": "Back to automatic sync",
        "preview_btn": "▶  10 s preview",
        "preview_tip": "Renders a 10-second clip with the HUD from the current position",
        "preview_failed": "Preview failed: {err}",
        "preparing_preview": "Preparing the preview…", "preview_prefix": "Preview · {s}",
        "laps_1": "1 lap", "laps_n": "{n} laps", "card_best": "best {t}",
        "card_done": "Exported ✓", "card_running": "Exporting…",
        "sync_excellent": "automatic sync: excellent", "sync_ok": "automatic sync: good",
        "sync_faible": "uncertain sync, check the preview", "sync_approx": "approximate sync (GPS time)",
        "no_match": "no matching RaceBox or RaceChrono session",
        "sync_label_auto": "Automatic sync · {c}% confidence",
        "sync_label_faible": "Uncertain sync · check with the preview",
        "sync_label_approx": "GPS-time sync only · check with the preview",
        "manual": "· manual offset {d} s",
        "style": "STYLE", "resolution": "RESOLUTION", "hud": "HUD", "sound": "SOUND", "out_dir": "OUTPUT FOLDER",
        "res_original": "Original", "fps30": "30 fps", "fps60": "60 fps (smoother)",
        "voices": "Remove voices",
        "signature": "made with LapHUD", "signature_lbl": "SIGNATURE",
        "signature_tip": "Adds a small “made with LAPHUD” mark at the bottom of the video",
        "voices_tip": "Keeps the engine and road sound (BS-Roformer model)",
        "voices_missing": "Install “audio-separator” to enable this option",
        "next_to_videos": "Next to the videos", "cancel": "Cancel",
        "export_btn": "EXPORT", "export_btn_n": "EXPORT  ({n})",
        "theme_broadcast": "Broadcast", "theme_glass": "Carbon", "theme_minimal": "Clean",
        "dlg_files": "GoPro videos and RaceBox / RaceChrono CSV files",
        "dlg_filter": "Videos and data (*.mp4 *.MP4 *.csv);;All files (*)",
        "dlg_dir": "Track day folder", "dlg_out": "Output folder",
        "quit_q": "An export is running. Quit anyway?",
        "analyzing": "Analysing files…", "analyzing_file": "Analysing · {name}",
        "ready_count": "{ok} video(s) ready", "ignored": " · {n} skipped",
        "exporting": "Exporting…", "video_k": "Video {k}/{n} · {s}",
        "export_failed": "Export failed: {err}",
        "finished": "Done: {done}/{total} video(s) exported",
        "exported_dlg": "{done} video(s) exported to:\n{where}", "video_folders": "the videos' own folders",
        "stopping": "Stopping…",
        "note_local_tz": "CSV in local time ({h:+d} h), corrected",
        "note_no_gps_time": "no GPS time in the video: searching the whole recording",
        "note_ambiguous": "several possible offsets",
        "note_no_imu": "no accelerometer data in the video",
        "note_no_overlap": "not enough overlap between the video and the data",
        "prog": "{pct:4.1f} % · {rate:.2f}× real time · {m} min {s:02d} s left",
        "voices_finishing": "Removing voices (finishing)…", "voices_mux": "Adding the voice-free audio…",
        "done_in": "Finished in {m} min {s:02d} s",
        "err_ffmpeg": "ffmpeg failed: {e}", "err_ffmpeg_stopped": "ffmpeg stopped: {e}",
        "err_incomplete": "incomplete video ({got:.0f} s of {dur:.0f} s)",
        "err_rename": "the video is finished but could not be renamed (file locked, antivirus?). It is here: {path}",
        "ffmpeg_missing": "ffmpeg not found. Install it (https://ffmpeg.org) or put ffmpeg.exe "
                          "in a folder named “ffmpeg” next to LapHUD.",
        "err_moov": "unreadable MP4 file (no moov box)", "err_no_video": "no video track",
        "err_no_gpmf": "no GoPro telemetry (gpmd track missing)",
        "err_csv_empty": "empty or unreadable RaceBox CSV",
        "err_csv_columns": "not a RaceBox CSV export (columns not found)",
    },
}


def set_lang(lang):
    global _lang
    _lang = lang if lang in T else "en"


def get_lang():
    return _lang


def system_lang():
    """Langue de l'ordinateur : français si le système est en français, sinon anglais."""
    try:
        from PySide6.QtCore import QLocale
        name = QLocale.system().name()
    except ImportError:
        import locale
        name = locale.getlocale()[0] or ""
    return "fr" if name.lower().startswith("fr") else "en"


def tr(key, **kw):
    s = T.get(_lang, {}).get(key) or T["fr"].get(key) or key
    return s.format(**kw) if kw else s


class Msg:
    """Message traduit au dernier moment (à l'affichage)."""
    def __init__(self, key, **kw):
        self.key, self.kw = key, kw

    def __str__(self):
        return tr(self.key, **{k: (str(v) if isinstance(v, Msg) else v) for k, v in self.kw.items()})

    __repr__ = __str__


def text(x, sep=" — "):
    """str d'un message, d'une liste de messages ou d'un texte."""
    if isinstance(x, (list, tuple)):
        return sep.join(text(p) for p in x if p)
    return str(x) if x is not None else ""
