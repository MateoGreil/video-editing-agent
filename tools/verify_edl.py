import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
chemin_edl = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT / "rendu" / "edl.json"
edl = json.loads(chemin_edl.read_text())
inv = {e["file"]: e for e in json.loads((PROJECT / "inventaire.json").read_text())}

erreurs = []
avertissements = []
segments = edl["segments"]

KENBURNS_VALIDES = {"zoom_in_lent", "zoom_out_lent", "pan_haut_bas", "pan_bas_haut", "pan_gauche_droite", "pan_droite_gauche"}
TRAITEMENTS_VALIDES = {"vidstab", "etalonnage_chaud", "etalonnage_nuit", "denoise", "ralenti_ok"}

attendu_debut = 0.0
precedent_fin = None
precedent_ordre = 0
for s in segments:
    n = s.get("ordre")
    if n != precedent_ordre + 1:
        erreurs.append(f"non-consecutive ordre: {precedent_ordre} -> {n}")
    precedent_ordre = n if n else precedent_ordre + 1

    if precedent_fin is not None:
        chev = s.get("transition_entree", {}).get("chevauchement", 0.0)
        attendu = precedent_fin - chev
        if abs(s["debut"] - attendu) > 0.05:
            erreurs.append(f"seg {n} : debut {s['debut']} != attendu {round(attendu, 2)} (fin préc. {precedent_fin} - chev {chev})")
    elif abs(s["debut"]) > 0.01:
        erreurs.append(f"seg {n} : first segment must start at 0 (debut={s['debut']})")
    precedent_fin = s["debut"] + s["duree"]
    if abs(s.get("fin", precedent_fin) - precedent_fin) > 0.05:
        avertissements.append(f"seg {n} : champ fin {s.get('fin')} != debut+duree {round(precedent_fin, 2)}")

    if s["duree"] <= 0:
        erreurs.append(f"seg {n} : zero or negative duration")

    if s["type"] == "video":
        fic = Path(s["fichier"])
        if not fic.is_absolute():
            fic = PROJECT / fic
        if not fic.exists():
            erreurs.append(f"seg {n} : file not found {s['fichier']}")
        else:
            e = inv.get(fic.name)
            if not e:
                erreurs.append(f"seg {n} : {fic.name} missing from inventory")
            else:
                if e["kind"] != "video":
                    erreurs.append(f"seg {n} : {fic.name} is not a video in inventory")
                if not (0 <= s["in"] < s["out"] <= e["duration"] + 0.05):
                    erreurs.append(f"seg {n} : in/out {s['in']}/{s['out']} out of bounds (duration {e['duration']})")
                vertical = e["width"] < e["height"]
                if s.get("orientation") != ("vertical" if vertical else "paysage"):
                    avertissements.append(f"seg {n} : declared orientation {s.get('orientation')} != inventaire ({'vertical' if vertical else 'paysage'})")
                if abs((s["out"] - s["in"]) - s["duree"]) > 0.15:
                    avertissements.append(f"seg {n} : duree {s['duree']} != out-in {round(s['out'] - s['in'], 2)} (OK si speed-change prévu)")
    elif s["type"] == "photo":
        fic = PROJECT / s["fichier"]
        if not fic.exists():
            erreurs.append(f"seg {n} : photo introuvable {s['fichier']}")
        if s.get("kenburns") and s["kenburns"] not in KENBURNS_VALIDES:
            avertissements.append(f"seg {n} : unknown kenburns {s['kenburns']}")

    for t in s.get("traitements", []):
        if t not in TRAITEMENTS_VALIDES:
            avertissements.append(f"seg {n} : unknown treatment {t}")

fin_film = precedent_fin
if abs(fin_film - edl["film"]["fin_video_s"]) > 0.5:
    erreurs.append(f"computed end {round(fin_film, 2)} != cible {edl['film']['fin_video_s']}")

entre_chant = (edl["film"].get("chant") or {}).get("entre_film_s",
               edl.get("audio", {}).get("chant_entree_s", 212.8))
couvrant = [s for s in segments if s["debut"] <= entre_chant < s["debut"] + s["duree"]]
if couvrant and couvrant[0]["type"] not in ("photo", "video"):
    avertissements.append(f"segment couvrant l'entrée du chant ({entre_chant} s) : type {couvrant[0]['type']}")

musiques = edl["film"].get("musiques") or [{"fichier": edl["film"].get("musique", ""),
    "debut_film": 0.0, "fin_piste": edl["film"]["fin_video_s"], "debut_piste": 0.0}]
derniere = musiques[-1]
if derniere["debut_film"] + (derniere["fin_piste"] - derniere["debut_piste"]) < fin_film - 0.6:
    erreurs.append("last music block does not cover the film end")
for m in musiques:
    if m.get("fichier") and not (PROJECT / m["fichier"]).exists():
        erreurs.append(f"music file not found:  {m['fichier']}")

paroles = [s for s in segments if s.get("audio_rush") == "parole"]
print(f"{chemin_edl.name} : {len(segments)} segments — computed end : {round(fin_film, 2)} s")
print(f"Speech segments: {len(paroles)} ({round(sum(s['duree'] for s in paroles), 1)} s)")
if couvrant:
    print(f"Chant entry ({entre_chant} s) covered by: seg {couvrant[0]['ordre']} ({couvrant[0]['type']}) {couvrant[0].get('fichier', couvrant[0].get('texte', ''))}")
for a in avertissements:
    print("WARNING:", a)
for e in erreurs:
    print("ERROR:", e)
print("\nVERDICT :", "OK — EDL USABLE" if not erreurs else f"{len(erreurs)} ERROR(S) TO FIX")
sys.exit(1 if erreurs else 0)
