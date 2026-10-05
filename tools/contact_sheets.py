import json
import math
import shutil
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RUSHES = PROJECT / "rushes"
RECON = PROJECT / "rendu" / "recon3"
INV = json.loads((PROJECT / "inventaire.json").read_text())
RECON.mkdir(parents=True, exist_ok=True)

JOURS = ["20231028", "20231029", "20231030", "20231031", "20231101"]

NOIRE = RECON / "noire.png"
if not NOIRE.exists():
    subprocess.run(
        ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=266x200:d=1",
         "-frames:v", "1", str(NOIRE)], check=True, capture_output=True)

CELLULE = "scale=266:200:force_original_aspect_ratio=decrease,pad=266:200:(ow-iw)/2:(oh-ih)/2:black"

for jour in JOURS:
    photos = sorted(e["file"] for e in INV
                    if e.get("day") == jour and e["kind"] in ("photo", "inconnu")
                    and e["file"].lower().endswith((".jpg", ".jpeg")))
    if not photos:
        continue
    manifest = []
    for g in range(0, len(photos), 16):
        lot = photos[g:g + 16]
        nb_vrais = len(lot)
        lot = lot + ["__NOIRE__"] * (16 - nb_vrais)
        tmp = RECON / f"tmp_{jour}_{g // 16}"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir()
        for i, p in enumerate(lot):
            cible_png = tmp / f"{i:03d}.png"
            if p == "__NOIRE__":
                cible_png.symlink_to(NOIRE)
            else:
                subprocess.run(
                    ["ffmpeg", "-v", "error", "-i", str(RUSHES / p), "-vf", CELLULE,
                     "-frames:v", "1", str(cible_png)], check=True, capture_output=True)
        sortie = RECON / f"photos_{jour}_{g // 16:02d}.jpg"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-framerate", "1", "-i", str(tmp / "%03d.png"),
             "-vf", "tile=4x4", "-frames:v", "1", str(sortie)],
            check=True, capture_output=True)
        shutil.rmtree(tmp)
        for i, p in enumerate(lot[:nb_vrais]):
            r, c = divmod(i, 4)
            manifest.append(f"photos_{jour}_{g // 16:02d}.jpg  Ligne{r + 1} Col{c + 1}  =  {p}")
    (RECON / f"manifest_{jour}.txt").write_text("\n".join(manifest))
    print(f"{jour}: {len(photos)} photos, {math.ceil(len(photos) / 16)} planche(s)")
