import json
import os
import subprocess
import datetime
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
SORTIE = PROJECT / "rendu" / "film" / "whatsapp"
SORTIE.mkdir(parents=True, exist_ok=True)
DATE = json.loads((PROJECT / "rendu" / "edl_long.json").read_text())["film"]["date_creation"]

CIBLES = {
    "16x9": (PROJECT / "rendu/film/vacances_long_16x9.mp4", 2000),
    "9x16": (PROJECT / "rendu/film/vacances_long_9x16.mp4", 2000),
}


def duree(fichier):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(fichier)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def encoder(entree, sortie, debit_video_kbps):
    commun = ["-c:v", "libx264", "-b:v", f"{debit_video_kbps}k",
              "-maxrate", f"{int(debit_video_kbps * 1.45)}k",
              "-bufsize", f"{debit_video_kbps * 2}k", "-profile:v", "high", "-level", "4.0",
              "-pix_fmt", "yuv420p", "-preset", "medium",
              "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
              "-movflags", "+faststart",
              "-metadata", f"creation_time={DATE['utc']}",
              "-metadata:s:v:0", f"creation_time={DATE['utc']}"]
    r1 = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(entree),
                         *commun, "-pass", "1", "-passlogfile", str(SORTIE / "passe"),
                         "-an", "-f", "null", "-"], capture_output=True, text=True)
    if r1.returncode != 0:
        raise RuntimeError(r1.stderr[-800:])
    r2 = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(entree),
                         *commun, "-pass", "2", "-passlogfile", str(SORTIE / "passe"),
                         str(sortie)], capture_output=True, text=True)
    if r2.returncode != 0:
        raise RuntimeError(r2.stderr[-800:])
    for f in SORTIE.glob("passe-*"):
        f.unlink()
    epoch = datetime.datetime.fromisoformat(DATE["utc"].replace("Z", "+00:00")).timestamp()
    os.utime(sortie, (epoch, epoch))


for fmt, (entree, debit) in CIBLES.items():
    sortie = SORTIE / f"vacances_long_{fmt}_whatsapp.mp4"
    d = duree(entree)
    taille_estimee = (debit + 128) * d / 8 / 1000
    encoder(entree, sortie, debit)
    print(f"{sortie.name} : {sortie.stat().st_size / 1e6:.1f} Mo "
          f"(estimé {taille_estimee:.0f} Mo, {d:.0f} s, {debit} kb/s)")
