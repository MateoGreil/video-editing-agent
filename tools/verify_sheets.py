import subprocess
from pathlib import Path

RECON = Path(__file__).resolve().parent.parent / "rendu" / "recon3"

ATTENDUS = {
    "photos_20231028_00.jpg": 13,
    "photos_20231029_00.jpg": 16, "photos_20231029_01.jpg": 16, "photos_20231029_02.jpg": 16,
    "photos_20231029_03.jpg": 16, "photos_20231029_04.jpg": 16, "photos_20231029_05.jpg": 16,
    "photos_20231029_06.jpg": 4,
    "photos_20231030_00.jpg": 16, "photos_20231030_01.jpg": 16, "photos_20231030_02.jpg": 16,
    "photos_20231030_03.jpg": 8,
    "photos_20231031_00.jpg": 16, "photos_20231031_01.jpg": 16, "photos_20231031_02.jpg": 16,
    "photos_20231031_03.jpg": 16, "photos_20231031_04.jpg": 3,
    "photos_20231101_00.jpg": 2,
}


def luminance_cellule(planche, ligne, col):
    x = col * 266
    y = ligne * 200
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(planche),
         "-vf", f"crop=266:200:{x}:{y},signalstats,metadata=print:key=lavfi.signalstats.YAVG:file=-",
         "-frames:v", "1", "-f", "null", "-"],
        capture_output=True, text=True, check=True)
    valeur = r.stdout.strip().split("=")[-1]
    return float(valeur)


tout_ok = True
for nom, attendu in ATTENDUS.items():
    planche = RECON / nom
    visibles = sum(
        1 for l in range(4) for c in range(4)
        if luminance_cellule(planche, l, c) > 1.0)
    statut = "OK" if visibles == attendu else "ECART"
    if visibles != attendu:
        tout_ok = False
    print(f"{nom}  visibles={visibles:>2}  attendus={attendu:>2}  {statut}")
print("\nALL OK" if tout_ok else "\nMISMATCHES FOUND")
