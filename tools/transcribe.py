import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

PROJECT = Path(__file__).resolve().parent.parent
RUSHES = PROJECT / "rushes"


def charger_audio(chemin):
    sortie = "/tmp/whisper_in.wav"
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(chemin), "-vn",
                    "-ac", "1", "-ar", "16000", "-y", sortie], check=True)
    with wave.open(sortie) as w:
        donnees = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return donnees.astype(np.float32) / 32768.0

CIBLES = [
    ("PXL_20231028_111644038.TS.mp4", ["pyrénées", "pyrenees", "on voit"], "On voit les Pyrénées depuis la route en montagne."),
    ("PXL_20231028_115657012.TS.mp4", ["greil", "reporter"], "Greil le reporter fait un reportage."),
    ("PXL_20231028_150929889.TS.mp4", ["greil", "reporter"], "Greil le reporter fait un reportage."),
    ("PXL_20231028_175347875.TS.mp4", [], ""),
    ("PXL_20231029_075512402.TS.mp4", [], ""),
    ("PXL_20231029_081011899.TS.mp4", [], ""),
    ("PXL_20231029_102313022.TS.mp4", ["trois", "heures", "heure"], "Il y a encore trois heures de marche."),
    ("PXL_20231029_133157436.TS.mp4", [], ""),
    ("PXL_20231030_182203574.mp4", [], ""),
]

model = WhisperModel("small", device="cpu", compute_type="int8")
resultat = {}
for nom, mots_cles, biais in CIBLES:
    kwargs = dict(language="fr", word_timestamps=True, vad_filter=False)
    if biais:
        kwargs["initial_prompt"] = biais
    segments, info = model.transcribe(charger_audio(RUSHES / nom), **kwargs)
    entrees = []
    print(f"\n=== {nom} ===")
    for seg in segments:
        texte = seg.text.strip()
        entrees.append({"debut": round(seg.start, 2), "fin": round(seg.end, 2), "texte": texte,
                        "mots": [{"w": w.word.strip(), "d": round(w.start, 2), "f": round(w.end, 2)}
                                 for w in (seg.words or [])]})
        print(f"  [{seg.start:6.2f} → {seg.end:6.2f}] {texte}")
        for w in (seg.words or []):
            if mots_cles and any(k in w.word.lower() for k in mots_cles):
                print(f"      ★ mot « {w.word.strip()} » : {w.start:.2f} → {w.end:.2f}")
    resultat[nom] = {"langue": info.language, "segments": entrees}

(PROJECT / "rendu" / "paroles" / "transcription.json").write_text(
    json.dumps(resultat, ensure_ascii=False, indent=1))
print("\n→ rendu/paroles/transcription.json")
