## LapHUD 0.2.0

🇫🇷 **Nouveautés**

- **Compatible RaceChrono** : glisse les exports **CSV v3** de RaceChrono à côté de tes vidéos GoPro, exactement comme les CSV RaceBox. Les tours officiels de RaceChrono sont repris au millième.
- **Signature en option** : une petite mention « made with LAPHUD » en bas de la vidéo (case *Signature*, décochée par défaut).
- **GoPro sans satellites** : certaines GoPro écrivent une fausse heure GPS (mars 2021) tant qu'elles n'ont pas capté les satellites. LapHUD l'écarte et retrouve la bonne session grâce aux accéléromètres.
- Les vidéos qui ne sont pas des GoPro (ex. vidéos exportées par RaceChrono) sont ignorées sans message d'erreur.
- Fin d'export plus robuste : si un antivirus ou OneDrive bloque le fichier un instant, LapHUD patiente au lieu d'échouer, et ne supprime jamais une vidéo terminée.

🇬🇧 **What's new**

- **RaceChrono support**: drop RaceChrono **CSV v3** exports next to your GoPro videos, just like RaceBox CSV files. RaceChrono's official lap times are kept to the millisecond.
- **Optional signature**: a small “made with LAPHUD” mark at the bottom of the video (*Signature* checkbox, off by default).
- **GoPros without satellite lock**: some GoPros write a fake GPS time (March 2021) until they find satellites. LapHUD now ignores it and finds the right session from the accelerometers.
- Videos that aren't GoPro recordings (e.g. RaceChrono's own exported videos) are skipped quietly.
- Sturdier export finish: if an antivirus or OneDrive briefly locks the file, LapHUD waits instead of failing, and never deletes a finished video.

### Téléchargements / Downloads

| | |
|---|---|
| **Windows** 10/11 | `LapHUD-windows.zip` — tout inclus / everything included (ffmpeg too) |
| **macOS** (Apple Silicon) | `LapHUD-macos.zip` — `brew install ffmpeg` |
| **Linux** x86-64 | `LapHUD-linux.tar.gz` — `sudo apt install ffmpeg` |

Site : https://shdroudlepoup.github.io/LapHUD/
