import json
import re
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RUSHES = PROJECT / "rushes"
SORTIE = PROJECT / "rendu" / "paroles"
SORTIE.mkdir(parents=True, exist_ok=True)
INV = [e for e in json.loads((PROJECT / "inventaire.json").read_text()) if e["kind"] == "video"]
EDL = json.loads((PROJECT / "rendu" / "edl.json").read_text())
DANS_FILM = {}
for s in EDL["segments"]:
    if s["type"] == "video":
        DANS_FILM.setdefault(s["fichier"].split("/")[-1], []).append(
            (s["in"], s["out"], s.get("audio_rush", "muet")))

EXCLU = {"PXL_20231028_202851902.TS.mp4"}


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def fenetres_actives(chemin, bruit=-32, dmin=0.6):
    r = run(["ffmpeg", "-i", str(chemin), "-af",
             f"silencedetect=noise={bruit}dB:d={dmin}", "-vn", "-f", "null", "-"])
    evenements = re.findall(r"silence_(start|end): ([\d.]+)", r.stderr)
    duree = float(re.search(r"Duration: ([\d:.]+)", r.stderr).group(1).split(":")[-1]) if "Duration:" in r.stderr else None
    silences = [(float(v), e) for e, v in evenements]
    actifs = []
    curseur = 0.0
    for debut_silence, _ in [s for s in silences if True]:
        if debut_silence - curseur >= 1.5:
            actifs.append((curseur, min(debut_silence, duree or debut_silence)))
        m = re.search
        curseur = debut_silence
    fin_dernier = None
    for e, v in evenements:
        if e == "end":
            fin_dernier = float(v)
    if fin_dernier is not None and duree and duree - fin_dernier >= 1.5:
        actifs.append((fin_dernier, duree))
    if not silences and duree and duree >= 1.5:
        actifs = [(0.0, duree)]
    return [(a, b) for a, b in actifs if b - a >= 1.5][:4]


def niveau(chemin, debut, fin):
    r = run(["ffmpeg", "-ss", str(debut), "-t", f"{fin - debut:.2f}", "-i", str(chemin),
             "-vn", "-af", "volumedetect", "-f", "null", "-"])
    m = re.search(r"mean_volume: ([-\d.]+) dB", r.stderr)
    return float(m.group(1)) if m else None


lignes_index = ["# Moments avec audio actif (paroles probables) — à écouter et sélectionner",
                "",
                "Chaque fichier .mp4 est un extrait vidéo+son. La colonne « film » indique si le rush est déjà dans le montage (et si son audio y est).",
                ""]


def mmss(s):
    return f"{int(s // 60)}:{s % 60:04.1f}"


total = 0
for e in sorted(INV, key=lambda x: (x["day"], x["time"])):
    nom = e["file"]
    if nom in EXCLU:
        continue
    chemin = RUSHES / nom
    for a, b in fenetres_actives(chemin):
        moy = niveau(chemin, a, b)
        if moy is None or moy < -30:
            continue
        tag_film = ""
        if nom in DANS_FILM:
            couples = DANS_FILM[nom]
            chevauche = any(a < out and b > inp for inp, out, _ in couples)
            audio = couples[0][2] if couples else "muet"
            tag_film = "✓ au film" + (f" ({audio})" if chevauche else " (autre extrait)")
        sortie = SORTIE / f"{e['day']}_{e['time']}_{nom.replace('.mp4', '').replace('.TS', '')}__{int(a)}-{int(b)}s.mp4"
        if not sortie.exists():
            run(["ffmpeg", "-v", "error", "-ss", f"{a:.2f}", "-t", f"{b - a:.2f}",
                 "-i", str(chemin), "-vf", "scale=480:-2", "-c:v", "libx264", "-crf", "23",
                 "-preset", "fast", "-c:a", "aac", "-b:a", "96k", str(sortie)])
        lignes_index.append(f"- `{sortie.name}` — {mmss(b - a)} | niveau {moy} dB | {tag_film or '—'}")
        total += 1

(SORTIE / "index.md").write_text("\n".join(lignes_index) + "\n")
print(f"{total} extraits dans {SORTIE}")
