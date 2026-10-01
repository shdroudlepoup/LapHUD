# RaceSync

**Le HUD tÃ©lÃ©mÃ©trie style F1 pour tes vidÃ©os embarquÃ©es.**
Tu donnes tes vidÃ©os GoPro et tes sessions RaceBox, RaceSync s'occupe du reste :
il retrouve quelle vidÃ©o va avec quelle session, les synchronise au centiÃ¨me prÃ¨s
et incruste un HUD propre â€” vitesse, chrono, delta, meilleur tour, tracÃ© du circuit, G.

Gratuit et libre (GPL-3.0), sans filigrane, sans compte, tout tourne sur ton PC.

![HUD RaceSync sur une vidÃ©o embarquÃ©e](docs/hud.jpg)

![L'application RaceSync](docs/app.png)

---

## Ce que fait RaceSync

- **Synchro automatique au centiÃ¨me.** L'heure GPS de la GoPro ne suffit pas (elle peut
  Ãªtre fausse d'une seconde, ou absente). RaceSync compare l'accÃ©lÃ©romÃ¨tre de la GoPro
  Ã  celui du RaceBox : freinages et virages laissent la mÃªme signature dans les deux
  capteurs, et le dÃ©calage qui les superpose est le bon. Ã‡a marche mÃªme si la camÃ©ra
  est sur le casque, et mÃªme si elle n'a jamais captÃ© le GPS.
- **Association automatique.** Glisse un dossier entier : chaque vidÃ©o est rattachÃ©e Ã  la
  bonne session RaceBox.
- **Chronos exacts.** Les temps au tour sont calculÃ©s Ã  l'instant prÃ©cis du passage de la
  ligne, pas arrondis Ã  l'image prÃ¨s.
- **Meilleur tour et delta Â« en direct Â».** Le HUD n'affiche que ce qui s'est dÃ©jÃ  passÃ© :
  pas de spoiler du meilleur tour dÃ¨s le dÃ©but de la vidÃ©o. Le delta compare ta position
  sur la trajectoire de ton meilleur tour, pas juste la distance parcourue.
- **HUD net en 4K**, fluide en 30 ou 60 images/s, trois styles : Broadcast (F1), Carbone, Ã‰purÃ©.
- **AperÃ§u avant export**, avec rÃ©glage fin de la synchro si tu veux chipoter.
- **Suppression des voix (option)** : garde le son du moteur et de la route.
- **Robuste** : un export interrompu ne laisse jamais de fichier Ã  moitiÃ© Ã©crit, le PC ne se
  met pas en veille pendant l'export, et la prioritÃ© est basse pour que tu puisses jouer
  ou naviguer en mÃªme temps.

## MatÃ©riel compatible

- **CamÃ©ras** : GoPro HERO5 et plus rÃ©centes (tÃ©lÃ©mÃ©trie GPMF).
- **DonnÃ©es** : RaceBox Mini / Mini S / Micro, export **CSV**.
- **Encodage** : carte NVIDIA, AMD ou Intel (accÃ©lÃ©ration matÃ©rielle), sinon le processeur.

### Exporter ta session depuis l'app RaceBox

Format **CSV**, prÃ©rÃ©glage **Custom**, **Full Date/Time** en **UTC**.
(L'heure locale marche aussi : RaceSync corrige le fuseau.)

## Utilisation

1. Lance RaceSync.
2. Glisse tes vidÃ©os GoPro et tes CSV RaceBox (ou un dossier) dans la fenÃªtre.
3. VÃ©rifie l'aperÃ§u â€” la pastille verte indique une synchro sÃ»re.
4. Choisis le style, la rÃ©solution, puis **Exporter**.

Les vidÃ©os sont crÃ©Ã©es Ã  cÃ´tÃ© des originales (`GX010166_RaceSync.mp4`) ou dans le
dossier de ton choix. Les vidÃ©os dÃ©jÃ  exportÃ©es sont reconnues et sautÃ©es.

## Installation

### Depuis les sources

Il faut [Python 3.10+](https://www.python.org/) et [ffmpeg](https://ffmpeg.org/download.html)
(dans le PATH, ou `ffmpeg.exe` dans un dossier `ffmpeg` Ã  cÃ´tÃ© de RaceSync).

```bash
git clone https://github.com/shdroudlepoup/RaceSync.git
cd RaceSync
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python -m racesync
```

Sous Windows, `RaceSync.bat` fait tout Ã§a pour toi.

Suppression des voix (facultatif, ~3 Go avec PyTorch, carte NVIDIA conseillÃ©e) :

```bash
.venv\Scripts\pip install "audio-separator[gpu]"
```

## Comment Ã§a marche (pour les curieux)

| Module | RÃ´le |
|---|---|
| `racesync/gopro.py` | Lit la tÃ©lÃ©mÃ©trie GoPro directement dans le MP4 (accÃ©lÃ©romÃ¨tre 200 Hz, GPS, heure GPS) en quelques millisecondes |
| `racesync/racebox.py` | Lit l'export CSV RaceBox |
| `racesync/sync.py` | Synchro par corrÃ©lation croisÃ©e des accÃ©lÃ©romÃ¨tres (FFT), toutes orientations de camÃ©ra |
| `racesync/session.py` | Tours, chronos au passage de ligne, delta, recalage des G (sens, biais, vibrations) |
| `racesync/hud/` | Rendu du HUD avec Skia, indÃ©pendant de la rÃ©solution |
| `racesync/export.py` | Rendu parallÃ¨le + incrustation et encodage par ffmpeg |
| `racesync/app/` | Interface (Qt) |

Convention des G : le point montre la **force ressentie** â€” virage Ã  droite â†’ point Ã  gauche,
freinage â†’ point en haut, accÃ©lÃ©ration â†’ point en bas.

## Contribuer

Les retours, idÃ©es et corrections sont les bienvenus : ouvre une *issue* ou une *pull request*.
Envie d'ajouter un autre boÃ®tier (AiM, VBOX, RaceChronoâ€¦) ? Il suffit d'Ã©crire un lecteur
qui produit les mÃªmes donnÃ©es que `racebox.py`.

## Licence

RaceSync est un logiciel libre sous licence **GNU GPL v3.0 ou ultÃ©rieure** â€” voir [LICENSE](LICENSE).
Tu peux l'utiliser, le modifier et le partager librement ; toute version redistribuÃ©e doit
rester libre et fournie avec son code source.

Polices incluses : Titillium Web, Barlow Semi Condensed, Chakra Petch â€” SIL Open Font License
(voir `racesync/assets/fonts`). RaceSync utilise [Skia](https://skia.org/),
[Qt / PySide6](https://www.qt.io/), [FFmpeg](https://ffmpeg.org/) et, en option,
[audio-separator](https://github.com/nomadkaraoke/python-audio-separator) (modÃ¨le BS-Roformer).

RaceSync n'est affiliÃ© ni Ã  GoPro, ni Ã  RaceBox.

---

## English

**RaceSync** burns a clean, F1-style telemetry HUD (speed, lap timer, live delta, best/last lap,
track map, G-meter) onto GoPro onboard videos using RaceBox CSV data. It pairs each video with
its session and syncs them to a few hundredths of a second by cross-correlating the GoPro's
accelerometer with the RaceBox's â€” no manual offset, even without GPS time in the video.
Free software under GPL-3.0-or-later. Run from source with `python -m racesync`.
