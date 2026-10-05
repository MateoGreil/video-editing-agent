import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
QC = PROJECT / "rendu" / "qc"
QC.mkdir(parents=True, exist_ok=True)
CELLULE = "scale=266:150:force_original_aspect_ratio=decrease,pad=266:150:(ow-iw)/2:(oh-ih)/2:black"


def frame(film, t, sortie):
    subprocess.run(["ffmpeg", "-v", "error", "-ss", str(t), "-i", str(film),
                    "-frames:v", "1", "-vf", CELLULE, str(sortie)],
                   check=True, capture_output=True)


def planche(film, nom, nb=60, pas=4):
    tmp = QC / f"tmp_{nom}"
    if tmp.exists():
        import shutil
        shutil.rmtree(tmp)
    tmp.mkdir()
    for i in range(nb):
        frame(film, i * pas, tmp / f"{i:03d}.png")
    lignes = (nb + 7) // 8
    subprocess.run(["ffmpeg", "-v", "error", "-framerate", "1",
                    "-i", str(tmp / "%03d.png"), "-vf", f"tile=8x{lignes}",
                    "-frames:v", "1", str(QC / f"{nom}.jpg")],
                   check=True, capture_output=True)
    import shutil
    shutil.rmtree(tmp)
    print(f"{nom}.jpg : {nb} vignettes (1/{pas}s, grille 8x{lignes})")


def titres(film, prefix):
    moments = {"titre_ouverture": 2.0, "gag": 161.0, "carton_fin": 234.0}
    for nom, t in moments.items():
        frame(film, t, QC / f"{prefix}_{nom}_t{t}s.png")
        print(f"{prefix}_{nom} (t={t}s)")


import sys
if len(sys.argv) > 2:
    film_cible = Path(sys.argv[1])
    nom_cible = sys.argv[2]
    nb = int(sys.argv[3]) if len(sys.argv) > 3 else 60
    pas = float(sys.argv[4]) if len(sys.argv) > 4 else 4
    planche(film_cible, nom_cible, nb, pas)
    sys.exit(0)

film169 = PROJECT / "rendu" / "film" / "vacances_montagne_16x9.mp4"
planche(film169, "apercu_film_16x9_v2")
titres(film169, "169")
