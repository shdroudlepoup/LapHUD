## LapHUD 0.2.4

🇫🇷 **Synchro RaceChrono corrigée (HUD ~0,6 s en avance)** : sans capteur d'accélération, RaceChrono fournit des G « calculées » à partir du GPS, lissées avec une demi-seconde de retard. LapHUD s'y calait, et tout le HUD arrivait un peu trop tôt (il freinait avant la voiture). Les G sont maintenant recalculées sans retard à partir de la trajectoire. Si tu as exporté des vidéos RaceChrono avec une version précédente, refais-les. Les logs RaceBox ne sont pas concernés.

🇬🇧 **RaceChrono sync fixed (HUD ~0.6 s early)**: without an acceleration sensor, RaceChrono writes GPS-derived “calc” G values smoothed with half a second of lag. LapHUD synced to them, so the whole HUD ran slightly early (braking before the car did). G are now recomputed from the trajectory with no lag. If you exported RaceChrono videos with an earlier version, redo them. RaceBox logs are not affected.

Aussi dans la 0.2.3 / Also in 0.2.3: aperçu 10 s corrigé / 10 s preview fixed.

### Téléchargements / Downloads

| | |
|---|---|
| **Windows** 10/11 | `LapHUD-windows.zip` — tout inclus / everything included (ffmpeg too) |
| **macOS** (Apple Silicon) | `LapHUD-macos.zip` — `brew install ffmpeg` |
| **Linux** x86-64 | `LapHUD-linux.tar.gz` — `sudo apt install ffmpeg` |

Site : https://shdroudlepoup.github.io/LapHUD/
