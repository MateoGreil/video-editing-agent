# EDL schema (rendu/edl*.json)

One JSON describes one film. `montage.py --edl <file>` renders it; `verify_edl.py <file>` must exit OK.

```jsonc
{
  "film": {
    "titre": "…",                       // opening card text
    "fin_video_s": 290.4,               // total duration — timeline math must land exactly here
    "date_creation": {                   // optional: written to container creation_time + file mtime
      "utc": "2023-11-01T10:20:09Z", "local": "2023-11-01 11:20:09 +01:00", "raison": "…"
    },
    "musiques": [                        // music blocks; single-block films may omit the array
      { "fichier": "musique/track1.webm", "debut_piste": 0, "fin_piste": 220.26, "debut_film": 0 },
      { "fichier": "musique/track2.webm", "debut_piste": 165.5, "fin_piste": 238.5,
        "debut_film": 217.4, "fondu_entree_avec_precedente": 1.2 }
    ],
    "chant": { "entre_film_s": 264.7 }   // optional live-recording overlay entry point (film time)
  },
  "audio": { "chant": "rendu/recon/…m4a" },   // overlay source; envelope constants live in montage.py
  "segments": [
    {
      "ordre": 1, "debut": 0.0, "duree": 4.0, "type": "titre",   // titre | video | photo | noir
      "texte": "…", "fond": "noir",
      "transition_entree": { "type": "aucune|fondu|fondu_jour|…", "chevauchement": 0.0 }
    },
    {
      "ordre": 2, "debut": 3.6, "duree": 3.4, "type": "video",
      "fichier": "rushes/PXL_….mp4", "in": 10.6, "out": 14.2,   // source bounds (videos only)
      "orientation": "vertical|paysage",
      "traitements": ["vidstab", "etalonnage_chaud", "etalonnage_nuit", "denoise"],
      "audio_rush": "muet|ambiance_-15dB|parole",
      "gain_parole_dB": 9, "preroll_parole_s": 0.3,              // speech niceties (optional)
      "duck_continu": true, "duck_continu_dB": -12,              // hold music down through the clip
      "titre_jour":  { "texte": "Jour 2 · …", "apparition_s": 0.5, "duree_s": 2.6 },
      "texte_overlay": { "texte": "…", "apparition_s": 0.9, "duree_s": 3.5 },
      "kenburns": "zoom_in_lent|zoom_out_lent|zoom_in_tres_lent|zoom_in_rapide_sur_baigneur|pan_haut_bas|pan_bas_haut|pan_gauche_droite|pan_droite_gauche",  // photos only
      "note": "…"
    }
  ]
}
```

## Invariants (checked by verify_edl.py)

- `ordre` consecutive from 1; `debut_1 = 0`; `debut_i = fin_{i-1} − chevauchement_i` (±0.05); `fin = debut + duree`.
- Video files exist and `0 ≤ in < out ≤ inventory duration`; speech segment durations equal `out − in` exactly.
- The last music block covers the film end; any overlay entry point (`chant`) falls on a photo/video segment.
- Cuts with `chevauchement ≤ 0.01` are hard cuts (assembly chunk boundaries).

Editing rule: apply user retouches by deterministic scripts (e.g. `retouches_*.py` in the project), re-verify, re-render — never by hand-patching rendered files.
