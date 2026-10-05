import argparse
import json
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
INV = {e["file"].split("/")[-1]: e for e in json.loads((PROJECT / "inventaire.json").read_text())}
INTER = PROJECT / "rendu" / "intermediaires"
FILM = PROJECT / "rendu" / "film"
INTER.mkdir(parents=True, exist_ok=True)
FILM.mkdir(parents=True, exist_ok=True)

FORMATS = {"16x9": (1920, 1080), "9x16": (1080, 1920)}

FONT_CANDIDATS = [
    "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
    "/usr/share/fonts/truetype/lato/Lato-Medium.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]
FONT = next((f for f in FONT_CANDIDATS if Path(f).exists()), None)
if FONT is None:
    sys.exit("no font found")

NOMS_SORTIES = {"edl": "vacances_montagne", "edl_voix": "vacances_voix", "edl_long": "vacances_long"}
ARGS = None
EDL = None
SEGMENTS = None
STEM = None


def run(cmd, label=""):
    if ARGS.dry_run:
        print(f"[dry-run] {label}: {' '.join(str(c) for c in cmd)[:200]}")
        return
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"FAILED {label}\n{r.stderr[-1500:]}", file=sys.stderr)
        sys.exit(1)
    if r.stderr.strip():
        print(f"  (stderr) {r.stderr.strip()[-400:]}", flush=True)
    print(f"ok {label}", flush=True)


def seg_id(seg, suffixe=""):
    return f"seg{seg['ordre']:03d}{suffixe}_{STEM}"


def encadrer(W, H):
    return (f"split[bg][fg];"
            f"[bg]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
            f"boxblur=16:2,eq=brightness=-0.08[bgb];"
            f"[fg]scale={W}:{H}:force_original_aspect_ratio=decrease[fgs];"
            f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2")


def traitements_filtres(seg):
    chaine = []
    for t in seg.get("traitements", []):
        if t == "etalonnage_chaud":
            chaine += ["eq=contrast=1.04:saturation=1.08",
                       "colorbalance=rm=0.03:gm=0.01:bm=-0.03"]
        elif t == "etalonnage_nuit":
            chaine += ["hqdn3d=4:3:6:4", "eq=brightness=0.05:saturation=0.9:gamma=1.04"]
        elif t == "denoise":
            chaine.append("hqdn3d=2:1.5:3:2")
    return chaine


def drawtext_titre_jour(seg, W, H):
    items = []
    if seg.get("titre_jour"):
        items.append(seg["titre_jour"])
    if seg.get("texte_overlay"):
        items.append(seg["texte_overlay"])
    resultats = []
    for k, item in enumerate(items):
        fichier_texte = INTER / f"txt_{seg_id(seg)}_{k}.txt"
        fichier_texte.write_text(item["texte"])
        app, dur = item["apparition_s"], item["duree_s"]
        alpha = (f"if(lt(t,{app}),0,if(lt(t,{app + 0.4}),(t-{app})/0.4,"
                 f"if(lt(t,{app + dur - 0.4}),1,if(lt(t,{app + dur}),({app + dur}-t)/0.4,0))))")
        resultats.append(f"drawtext=fontfile={FONT}:textfile={fichier_texte}:"
                         f"fontsize={max(28, W // 34)}:fontcolor=white:box=1:boxcolor=black@0.45:"
                         f"boxborderw=12:x=(w-text_w)/2:y={int(H * 0.82)}:alpha='{alpha}'")
    return resultats


def kenburns(seg, W, H):
    D = max(2, round(seg["duree"] * 30))
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    table = {
        "zoom_in_lent": (f"1+0.14*on/{D}", cx, cy),
        "zoom_out_lent": (f"1.14-0.14*on/{D}", cx, cy),
        "zoom_in_tres_lent": (f"1+0.07*on/{D}", cx, cy),
        "zoom_in_rapide_sur_baigneur": (f"1+0.22*on/{D}", cx, cy),
        "pan_haut_bas": ("1.10", cx, f"(ih-ih/zoom)*on/{D}"),
        "pan_bas_haut": ("1.10", cx, f"(ih-ih/zoom)*(1-on/{D})"),
        "pan_gauche_droite": ("1.10", f"(iw-iw/zoom)*on/{D}", cy),
        "pan_droite_gauche": ("1.10", f"(iw-iw/zoom)*(1-on/{D})", cy),
    }
    z, x, y = table.get(seg.get("kenburns", "zoom_in_lent"), table["zoom_in_lent"])
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={D}:s={W}x{H}:fps=30"


def encodage(sortie, duree):
    return ["-t", str(duree), "-c:v", "libx264", "-crf", "14", "-preset", "medium", str(sortie)]


def segment_video(seg, W, H):
    sortie = INTER / f"{seg_id(seg)}_{W}x{H}.mp4"
    if sortie.exists() and not ARGS.force:
        return sortie
    rush = PROJECT / seg["fichier"]
    duree_extrait = seg["out"] - seg["in"]
    vidstab = "vidstab" in seg.get("traitements", [])
    trf = INTER / f"{seg_id(seg)}.trf"
    if vidstab:
        run(["ffmpeg", "-v", "error", "-ss", str(seg["in"]), "-i", str(rush),
             "-t", str(duree_extrait),
             "-vf", f"vidstabdetect=shakiness=6:accuracy=12:result={trf}",
             "-an", "-f", "null", "-"], f"vidstab detect {seg_id(seg)}")
    etapes = []
    if vidstab:
        etapes.append(f"vidstabtransform=input={trf}:smoothing=20")
    etapes += [encadrer(W, H), *traitements_filtres(seg), "fps=30", "setsar=1",
               "format=yuv420p", *drawtext_titre_jour(seg, W, H)]
    fc = f"[0:v]{','.join(e for e in etapes if e)}[v]"
    cmd = ["ffmpeg", "-v", "error", "-ss", str(seg["in"]), "-i", str(rush),
           "-t", str(duree_extrait), "-an",
           "-filter_complex", fc, "-map", "[v]", *encodage(sortie, seg["duree"])]
    run(cmd, f"vidéo {seg_id(seg)}")
    return sortie


def segment_photo(seg, W, H):
    sortie = INTER / f"{seg_id(seg)}_{W}x{H}.mp4"
    if sortie.exists() and not ARGS.force:
        return sortie
    photo = PROJECT / seg["fichier"]
    etapes = [encadrer(W, H), f"scale={2 * W}:{2 * H}:flags=lanczos",
              kenburns(seg, W, H), "format=yuv420p", *drawtext_titre_jour(seg, W, H)]
    etapes = [e for e in etapes if e] or ["null"]
    fc = f"[0:v]{','.join(etapes)}[v]"
    cmd = ["ffmpeg", "-v", "error", "-i", str(photo),
           "-filter_complex", fc, "-map", "[v]", *encodage(sortie, seg["duree"])]
    run(cmd, f"photo {seg_id(seg)}")
    return sortie


def segment_titre(seg, W, H):
    sortie = INTER / f"{seg_id(seg)}_{W}x{H}.mp4"
    if sortie.exists() and not ARGS.force:
        return sortie
    fichier_texte = INTER / f"txt_{seg_id(seg)}.txt"
    fichier_texte.write_text(seg["texte"])
    d = seg["duree"]
    fade = min(0.8, d / 3)
    alpha = f"if(lt(t,{fade}),t/{fade},if(lt(t,{d - fade}),1,({d}-t)/{fade}))"
    vf = (f"drawtext=fontfile={FONT}:textfile={fichier_texte}:"
          f"fontsize={max(34, W // 22)}:fontcolor=white:"
          f"x=(w-text_w)/2:y=(h-text_h)/2:alpha='{alpha}',format=yuv420p,setsar=1")
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi",
           "-i", f"color=black:s={W}x{H}:d={d}:r=30",
           "-vf", vf, *encodage(sortie, d)]
    run(cmd, f"titre {seg_id(seg)} ({seg['texte'][:28]})")
    return sortie


def segment_noir(seg, W, H):
    sortie = INTER / f"{seg_id(seg)}_{W}x{H}.mp4"
    if sortie.exists() and not ARGS.force:
        return sortie
    cmd = ["ffmpeg", "-v", "error", "-f", "lavfi",
           "-i", f"color=black:s={W}x{H}:d={seg['duree']}:r=30",
           *encodage(sortie, seg["duree"])]
    run(cmd, f"noir {seg_id(seg)}")
    return sortie


RENDERERS = {"video": segment_video, "photo": segment_photo,
             "titre": segment_titre, "noir": segment_noir}


def assembler(fmt):
    W, H = FORMATS[fmt]
    fichiers = [RENDERERS[seg["type"]](seg, W, H) for seg in SEGMENTS]

    morceaux = []
    bloc = [0]
    for i in range(1, len(SEGMENTS)):
        chev = SEGMENTS[i].get("transition_entree", {}).get("chevauchement", 0.0)
        if chev <= 0.01:
            morceaux.append(bloc)
            bloc = [i]
        else:
            bloc.append(i)
    morceaux.append(bloc)

    chunks = []
    for num, bloc in enumerate(morceaux):
        sortie = INTER / f"chunk_{STEM}_{fmt}_{num:02d}.mp4"
        if sortie.exists() and not ARGS.force:
            chunks.append(sortie)
            continue
        if len(bloc) == 1:
            run(["cp", str(fichiers[bloc[0]]), str(sortie)], f"chunk {STEM} {fmt} #{num} (copie)")
        else:
            cmd = ["ffmpeg", "-v", "error"]
            for i in bloc:
                cmd += ["-i", str(fichiers[i])]
            parties = []
            cur = SEGMENTS[bloc[0]]["duree"]
            for k in range(1, len(bloc)):
                i = bloc[k]
                chev = SEGMENTS[i].get("transition_entree", {}).get("chevauchement", 0.4)
                offset = cur - chev
                entree_a = "[0:v]" if k == 1 else f"[x{k - 1}]"
                parties.append(f"{entree_a}[{k}:v]xfade=transition=fade:"
                               f"duration={chev}:offset={offset:.3f}[x{k}]")
                cur = offset + SEGMENTS[i]["duree"]
            cmd += ["-filter_complex", ";".join(parties), "-map", f"[x{len(bloc) - 1}]",
                    "-t", f"{cur:.3f}", "-c:v", "libx264", "-crf", "16",
                    "-preset", "medium", str(sortie)]
            run(cmd, f"chunk {STEM} {fmt} #{num} ({len(bloc)} segs, {cur:.1f}s)")
        chunks.append(sortie)

    video_finale = FILM / f"video_{STEM}_{fmt}.mp4"
    liste = FILM / f"concat_{STEM}_{fmt}.txt"
    liste.write_text("".join(f"file '{c}'\n" for c in chunks))
    if not ARGS.dry_run:
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
                        "-i", str(liste), "-c", "copy", str(video_finale)], check=True)
        print(f"video {STEM} {fmt} : {video_finale} ({video_finale.stat().st_size / 1e6:.1f} Mo)")
    return video_finale


def lin(a, b, v1, v2):
    return f"({v1}+({v2}-({v1}))*(t-{a})/({b}-{a}))"


ORIG_DB = (f"if(lt(t,212.8),0,if(lt(t,224.7),{lin(212.8, 224.7, 0, -2)},"
           f"if(lt(t,229.0),{lin(224.7, 229.0, -2, -7)},"
           f"if(lt(t,235.0),-7,if(lt(t,235.8),{lin(235.0, 235.8, -7, -2)},-2)))))")
CHANT_DB_LOCAL = (f"if(lt(t,3.2),{lin(0, 3.2, -30, -11)},"
                  f"if(lt(t,11.9),{lin(3.2, 11.9, -11, -3)},"
                  f"if(lt(t,16.2),{lin(11.9, 16.2, -3, -2)},"
                  f"if(lt(t,22.2),-2,if(lt(t,23.5),{lin(22.2, 23.5, -2, -9)},"
                  f"if(lt(t,25.25),{lin(23.5, 25.25, -9, -40)},-90))))))")


def preparer_parole(seg):
    rush = PROJECT / seg["fichier"]
    wav = INTER / f"parole_{seg_id(seg)}.wav"
    if wav.exists() and not ARGS.force:
        return wav
    gain = seg.get("gain_parole_dB", 0)
    pre = seg.get("preroll_parole_s", 0)
    af = "highpass=f=80,loudnorm=I=-17:TP=-2:LRA=9,aresample=48000"
    if gain:
        af += f",volume={gain}dB"
    run(["ffmpeg", "-v", "error", "-ss", str(max(0, seg["in"] - pre)), "-i", str(rush),
         "-t", f"{seg['out'] - seg['in'] + pre:.2f}", "-vn", "-ac", "2", "-ar", "48000",
         "-af", af,
         "-c:a", "pcm_s16le", str(wav)], f"speech {seg_id(seg)}")
    return wav


def preparer_ambiance(seg):
    rush = PROJECT / seg["fichier"]
    wav = INTER / f"amb_{seg_id(seg)}.wav"
    if wav.exists() and not ARGS.force:
        return wav
    run(["ffmpeg", "-v", "error", "-ss", str(seg["in"]), "-i", str(rush),
         "-t", f"{seg['out'] - seg['in']:.2f}", "-vn", "-ac", "2", "-ar", "48000",
         "-c:a", "pcm_s16le", str(wav)], f"ambience {seg_id(seg)}")
    return wav


def construire_audio():
    film = EDL["film"]
    FIN = film["fin_video_s"]
    musiques = film.get("musiques") or [{"fichier": film["musique"],
                                         "debut_piste": 0.0, "fin_piste": 238.5,
                                         "debut_film": 0.0}]
    chant_cfg = EDL.get("audio", {})
    entre_chant = (film.get("chant", {}) or {}).get("entre_film_s",
                   chant_cfg.get("chant_entree_s", 212.8))
    fichier_chant = chant_cfg.get("chant") or "rendu/recon/chant_voiture.m4a"

    paroles = [s for s in SEGMENTS if s.get("audio_rush") == "parole"]
    ambiances = [s for s in SEGMENTS if str(s.get("audio_rush", "")).startswith("ambiance")]

    parties = []
    cmd = ["ffmpeg", "-v", "error"]
    branches_musique = []
    for i, m in enumerate(musiques):
        cmd += ["-i", str(PROJECT / m["fichier"])]
        dp, fp, df = m["debut_piste"], m["fin_piste"], m["debut_film"]
        longueur = fp - dp
        etapes = ["asetpts=N/SR/TB"]
        if "copains" in m["fichier"]:
            etapes += [f"volume='pow(10,({ORIG_DB})/20)':eval=frame"]
        etapes += [f"atrim={dp}:{fp}", "asetpts=PTS-STARTPTS"]
        fondu = m.get("fondu_entree_avec_precedente", 0)
        if fondu > 0 and i > 0:
            etapes += [f"afade=t=in:st=0:d={fondu}"]
            duree_prec = musiques[i - 1]["fin_piste"] - musiques[i - 1]["debut_piste"]
            idx_prec = branches_musique[i - 1]
            parties[idx_prec] = parties[idx_prec].replace(
                "adelay=",
                f"afade=t=out:st={duree_prec - fondu:.2f}:d={fondu},adelay=")
        etapes += [f"adelay=delays={int(df * 1000)}:all=1"]
        label = f"mus{i}"
        chaine = ",".join(etapes)
        parties.append(f"[{i}:a]{chaine}[{label}]")
        branches_musique.append(len(parties) - 1)

    cmd += ["-i", str(PROJECT / fichier_chant)]
    idx_chant = len(musiques)
    parties.append(f"[{idx_chant}:a]asetpts=N/SR/TB,atrim=start=168.0871:end=193.337,"
                   f"asetpts=PTS-STARTPTS,highpass=f=280,highpass=f=280,"
                   f"volume='pow(10,({CHANT_DB_LOCAL})/20)':eval=frame,"
                   f"adelay=delays={int(entre_chant * 1000)}:all=1[c]")

    branches_bruit = []
    index_entree = idx_chant + 1
    for seg in paroles:
        wav = preparer_parole(seg)
        cmd += ["-i", str(wav)]
        n = index_entree
        index_entree += 1
        debut_audio = seg["debut"] - seg.get("preroll_parole_s", 0)
        parties.append(f"[{n}:a]adelay=delays={int(debut_audio * 1000)}:all=1[p{seg['ordre']}]")
        branches_bruit.append(f"[p{seg['ordre']}]")
    for seg in ambiances:
        wav = preparer_ambiance(seg)
        cmd += ["-i", str(wav)]
        n = index_entree
        index_entree += 1
        parties.append(f"[{n}:a]atrim=0:{seg['duree']:.3f},asetpts=PTS-STARTPTS,volume=-15dB,"
                       f"highpass=f=120,adelay=delays={int(seg['debut'] * 1000)}:all=1[a{seg['ordre']}]")
        branches_bruit.append(f"[a{seg['ordre']}]")

    labels_musique = "".join(f"[mus{i}]" for i in range(len(musiques)))
    a_des_bruits = bool(branches_bruit)
    suffixe_asplit = f"[mussc]" if a_des_bruits else f"[mus][mussc]"
    if len(musiques) == 1:
        parties.append(f"[mus0]apad=whole_dur={FIN}{suffixe_asplit}")
    else:
        parties.append(f"{labels_musique}amix=inputs={len(musiques)}:normalize=0,"
                       f"apad=whole_dur={FIN}{suffixe_asplit}")

    if branches_bruit:
        nb = len(branches_bruit)
        parties.append(f"{''.join(branches_bruit)}amix=inputs={nb}:normalize=0,"
                       f"apad=whole_dur={FIN},asplit=2[bruit][bruitsc]")
        parties.append(f"[mussc][bruitsc]sidechaincompress="
                       f"threshold=0.015:ratio=9:attack=40:release=350[musd]")
        continu = [s for s in SEGMENTS if s.get("duck_continu")]
        if continu:
            def fenetre(s):
                f = round(10 ** (s.get("duck_continu_dB", -8) / 20), 4)
                a = s["debut"] - s.get("preroll_parole_s", 0)
                b = s["debut"] + s["duree"]
                return (f"if(lt(t,{a - 0.1:.3f}),1,"
                        f"if(lt(t,{a + 0.1:.3f}),{1 + (f - 1) * 0.5:.4f},"
                        f"if(lt(t,{b + 0.1:.3f}),{f},"
                        f"if(lt(t,{b + 0.3:.3f}),{1 - (1 - f) * 0.5:.4f},1))))")
            expression = "*".join(fenetre(s) for s in continu)
            parties.append(f"[musd]volume='{expression}':eval=frame[musfin]")
            label_musique_finale = "[musfin]"
        else:
            label_musique_finale = "[musd]"
        parties.append(f"{label_musique_finale}[bruit][c]amix=inputs=3:normalize=0:duration=first,"
                       f"alimiter=limit=0.89:level=0,"
                       f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                       f"atrim=0:{FIN}[aout]")
    else:
        parties.append(f"[mus][c]amix=inputs=2:normalize=0:duration=first,"
                       f"alimiter=limit=0.89:level=0,"
                       f"loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,"
                       f"atrim=0:{FIN}[aout]")

    sortie = FILM / f"audio_{STEM}.m4a"
    cmd += ["-filter_complex", ";".join(parties), "-map", "[aout]",
            "-t", str(FIN), "-c:a", "aac", "-b:a", "192k", str(sortie)]
    if sortie.exists():
        sortie.unlink()
    run(cmd, f"final audio {STEM}")
    return sortie


def muxer(fmt, video, audio):
    sortie = FILM / f"{NOMS_SORTIES.get(STEM, STEM)}_{fmt}.mp4"
    if ARGS.dry_run:
        print(f"[dry-run] mux {STEM} {fmt} -> {sortie}")
        return sortie
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(video), "-i", str(audio),
           "-map", "0:v", "-map", "1:a", "-c", "copy",
           "-movflags", "+faststart", "-shortest"]
    date_creation = EDL.get("film", {}).get("date_creation")
    if date_creation:
        cmd += ["-metadata", f"creation_time={date_creation['utc']}",
                "-metadata:s:v:0", f"creation_time={date_creation['utc']}",
                "-metadata:s:a:0", f"creation_time={date_creation['utc']}"]
    cmd.append(str(sortie))
    subprocess.run(cmd, check=True)
    if date_creation:
        import datetime
        epoch = datetime.datetime.fromisoformat(date_creation["utc"].replace("Z", "+00:00")).timestamp()
        sortie2 = sortie.with_suffix(suffix := sortie.suffix)
        import os
        os.utime(sortie2, (epoch, epoch))
    print(f"FILM {STEM} {fmt} : {sortie} ({sortie.stat().st_size / 1e6:.1f} Mo)")
    return sortie


def main():
    global ARGS, EDL, SEGMENTS, STEM
    p = argparse.ArgumentParser()
    p.add_argument("--edl", default="rendu/edl.json")
    p.add_argument("--format", choices=["16x9", "9x16", "audio", "tout"], default="16x9")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    ARGS = p.parse_args()
    chemin = Path(ARGS.edl)
    STEM = chemin.stem
    EDL = json.loads(chemin.read_text())
    SEGMENTS = EDL["segments"]

    audio = construire_audio() if ARGS.format == "audio" else FILM / f"audio_{STEM}.m4a"
    if ARGS.format in ("16x9", "9x16", "tout"):
        for fmt in (["16x9", "9x16"] if ARGS.format == "tout" else [ARGS.format]):
            video = assembler(fmt)
            if audio.exists():
                muxer(fmt, video, audio)


main()
