import re
import subprocess
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
OUT = PROJECT / "rendu" / "analyse_audio"
OUT.mkdir(parents=True, exist_ok=True)

TRACKS = {
    "original": PROJECT / "musique" / "les-copains-dabord.webm",
    "chant": PROJECT / "rendu" / "recon" / "chant_voiture.m4a",
}


def run(args):
    return subprocess.run(args, capture_output=True, text=True)


def duree(path):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)])
    return float(r.stdout.strip())


def silences(path, noise, dmin):
    r = run(["ffmpeg", "-i", str(path), "-af",
             f"silencedetect=noise={noise}dB:d={dmin}", "-vn", "-f", "null", "-"])
    events = re.findall(r"silence_(start|end): ([\d.]+)", r.stderr)
    return [(e, float(v)) for e, v in events]


def rms_100ms(path):
    r = run(["ffmpeg", "-i", str(path), "-vn", "-af",
             "asetnsamples=n=4800,astats=metadata=1:reset=1,"
             "ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-",
             "-f", "null", "-"])
    if not r.stdout.strip():
        raise RuntimeError(f"pas de sortie RMS pour {path}: {r.stderr[-300:]}")
    lignes = r.stdout.splitlines()
    series = []
    temps = None
    for ligne in lignes:
        m = re.search(r"pts_time:([\d.]+)", ligne)
        if m:
            temps = float(m.group(1))
        m = re.search(r"RMS_level=(-?[\d.]+|-inf)", ligne)
        if m and temps is not None:
            val = float(m.group(1)) if m.group(1) != "-inf" else -90.0
            series.append((temps, val))
    return series


def tempo_bpm(series):
    intensite = [max(0, v) for _, v in series]
    n = len(intensite)
    if n < 100:
        return None
    valeurs = [v for _, v in series if v > -45]
    if len(valeurs) < 100:
        return None
    meilleure = (0.0, 0)
    for lag in range(10, 100):
        num = sum(a * b for a, b in zip(valeurs, valeurs[lag:]))
        norm = sum(a * a for a in valeurs[: len(valeurs) - lag]) + 1e-9
        score = num / norm
        if score > meilleure[0]:
            meilleure = (score, lag)
    return round(600.0 / meilleure[1], 1)


def spectro(path, nom, debut=None, duree_extrait=None):
    args = ["ffmpeg", "-v", "error"]
    if debut is not None:
        args += ["-ss", str(debut)]
    if duree_extrait is not None:
        args += ["-t", str(duree_extrait)]
    args += ["-i", str(path), "-vn", "-lavfi", "showspectrumpic=s=1600x400:legend=1",
             str(OUT / f"{nom}.png")]
    run(args)


def resumer(nom, path):
    d = duree(path)
    series = rms_100ms(path)
    with open(OUT / f"{nom}_rms.txt", "w") as f:
        for t, v in series:
            f.write(f"{t:.1f}\t{v:.1f}\n")
    par_seconde = {}
    for t, v in series:
        par_seconde.setdefault(int(t), []).append(v)
    profil = [round(sum(v) / len(v), 1) for s, v in sorted(par_seconde.items())]
    resume = {
        "fichier": str(path),
        "duree": round(d, 1),
        "tempo_estime_bpm": tempo_bpm(series),
        "silences_-40dB_2s": silences(path, -40, 2.0),
        "silences_-35dB_05s": silences(path, -35, 0.5),
        "rms_moyen_par_10s": [round(sum(profil[i:i + 10]) / len(profil[i:i + 10]), 1)
                              for i in range(0, len(profil), 10)],
        "pics": sorted(
            [(round(t, 1), round(v, 1)) for t, v in series if v > -12],
            key=lambda x: -x[1])[:15],
    }
    spectro(path, f"{nom}_spectro_complet")
    spectro(path, f"{nom}_spectro_fin", max(0, d - 70), 70)
    return resume


resultats = {nom: resumer(nom, path) for nom, path in TRACKS.items()}
(OUT / "resume.json").write_text(json.dumps(resultats, indent=2, ensure_ascii=False))
for nom, r in resultats.items():
    print(f"=== {nom} : {r['duree']}s, tempo ≈ {r['tempo_estime_bpm']} bpm ===")
    print("silences -40dB≥2s :", r["silences_-40dB_2s"][:8])
    print("RMS moyen /10s    :", r["rms_moyen_par_10s"])
    print("pics > -12 dB     :", r["pics"][:8])
    print()
