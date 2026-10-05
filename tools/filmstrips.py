import json
import math
import subprocess
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RUSHES = PROJECT / "rushes"
RECON = PROJECT / "rendu" / "recon2"
INVENTAIRE = json.loads((PROJECT / "inventaire.json").read_text())
RECON.mkdir(parents=True, exist_ok=True)

DEJA_VUS = {
    "PXL_20231028_111644038.TS.mp4",
    "PXL_20231028_202851902.TS.mp4",
    "PXL_20231029_104358099.TS.mp4",
    "PXL_20231029_133157436.TS.mp4",
    "PXL_20231029_153055688.TS.mp4",
    "PXL_20231029_182439792.mp4",
    "PXL_20231030_100100844.mp4",
    "PXL_20231030_221940464.mp4",
    "PXL_20231030_222221190.mp4",
    "PXL_20231031_144612224.mp4",
    "PXL_20231031_145139286.mp4",
}


def filmstrip(entry):
    name = entry["file"]
    duree = entry["duration"]
    fps = 1.0 if duree <= 6 else 6.0 / duree
    nb = max(1, math.ceil(duree * fps))
    cols = 6
    rows = math.ceil(nb / cols)
    sortie = RECON / f"fs_{name.replace('.mp4', '')}.jpg"
    subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(RUSHES / name),
         "-vf", f"fps={fps},scale=-2:120,tile={cols}x{rows}",
         "-frames:v", "1", str(sortie)],
        check=True, capture_output=True)
    print(f"{entry['day']} {entry['time']} {duree:>6.1f}s {name}")


videos = [e for e in INVENTAIRE if e["kind"] == "video" and e["file"] not in DEJA_VUS]
for entry in sorted(videos, key=lambda e: (e["day"], e["time"])):
    filmstrip(entry)
print(f"\n{len(videos)} filmstrips dans {RECON}")
