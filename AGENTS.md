# Video Editing Agents

Agents working in this repository edit videos end-to-end from raw footage, in CLI on a Linux headless machine. All shared assets are English; project working dirs may be in any language.

## Layout

```
tools/               reusable pipeline scripts (see "The pipeline" below) — COPY them, do not run them from here
docs/                reference: ffmpeg gotchas, EDL schema
editing/             one subdirectory per editing project (NEVER committed, only .gitkeep is)
editing/<projet>/    a project: rushes/, musique/, rendu/, scripts/, plan + EDL + reports
```

## Hard rules

- **Open source only** (OSI licenses) for every tool. ffmpeg/ffprobe (GPL build), faster-whisper (MIT), yt-dlp. Rejected on principle: Remotion, vex, DaVinci Resolve, Diffusion Studio (reasons in the research report of the reference project).
- **Raw footage is read-only.** Everything produced goes under the project's `rendu/` directory.
- **Every render must be replayable**: the project's `scripts/` + EDL files fully determine the output. Never hand-edit a rendered file.
- Media metadata matters: set `creation_time` on final exports (see `date_creation` in the EDL schema) so the film sorts next to the trip's media in the user's library.
- Music: user-provided or user-approved files; ripping (yt-dlp) is for private use — remind the user about Content ID if they ever publish.

## The pipeline (how to edit a project)

1. **Intake.** Unzip/copy footage into `<projet>/rushes/` (untouched afterwards). Copy `tools/*.py` into `<projet>/scripts/` — scripts resolve paths relative to their own location (`project = scripts/..`).
2. **Inventory.** `python3 scripts/inventory.py` → `inventaire.json` (per-file kind, duration, resolution, fps, orientation). Read it before anything else.
3. **Vision recon.** You cannot see images — dispatch sub-agents that can (any vision model; Sonnet-class is enough for describing, use the strongest model for editorial arbitration).
   - `scripts/filmstrips.py` generates one strip per video (6 thumbnails) into `rendu/recon/`; `scripts/contact_sheets.py` generates verified 4×4 photo sheets + manifest into `rendu/recon3/`.
   - Have describer agents report per-clip: content, technical flaws, memorable moments as *fractions of duration*, keep/cut verdict. Then have one strong "editor-in-chief" agent produce the cut.
4. **Audio recon.** `scripts/audio_analysis.py` (RMS envelopes, silences, tempo, spectrograms). For speech: `scripts/find_speech.py` (audio-active windows) then `scripts/transcribe.py` (faster-whisper, word timestamps — install in a project venv: `pip install faster-whisper "av<15"`; if PyAV breaks, decode to 16 kHz WAV with ffmpeg and pass the numpy array). Whisper mishears names: re-run suspicious clips with `initial_prompt` biasing, escalate small→medium model.
5. **Plan.** Write `plan-montage.md` (structure, selection, music, what is excluded and why) and **get user sign-off before any long render**.
6. **EDL.** The film is one JSON timeline: `rendu/edl*.json` (schema in `docs/edl-schema.md`). Have the editor-in-chief agent write it, then run `python3 scripts/verify_edl.py rendu/edl.json` — it must exit OK (timeline math, file bounds, chant/finale coverage).
7. **Render.** `python3 scripts/montage.py --edl rendu/edl.json --format 16x9|9x16|audio|tout`. Intermediates are cached (delete the ones you changed); every EDL gets its own namespace. Both aspect masters come from the same EDL: vertical clips sit on a blurred fill in 16:9, landscape clips likewise in 9:16.
8. **QC — never skip.** (a) measured probes: per-timestamp luminance, per-window audio levels; (b) `scripts/qc_sheets.py <film> <name> <nb_frames> <step>` overview sheet + a vision agent with a checklist (titles, unexpected blacks, duplicates, deformation). Sheet generation has bitten us twice — always verify sheets cell-by-cell (see docs/ffmpeg-gotchas.md).
9. **Retouches.** Apply user feedback by editing the EDL (deterministic scripts if complex), re-verify, re-render. Single-segment changes only rebuild that segment + its chunk.
10. **Delivery.** Masters stay in `rendu/film/` (archive quality). For messaging apps run `scripts/export_whatsapp.py` (two-pass ~2 Mb/s, ~75 MB — high-bitrate masters make WhatsApp's transcoder fail).

## Editing conventions that worked

- Film duration locked to the music; lay sections of the film onto musical structure (intro, verses, bridge, final verse) — get the music analyzed (silences, sections, spectrograms) and lock any live-recording overlay to measured anchors.
- Day/chapter titles as drawtext overlays on footage (not title cards), except opening/closing cards.
- Speech segments: `audio_rush: "parole"`, loudnorm to a uniform level, + optional `gain_parole_dB`, `preroll_parole_s` (start the voice slightly before its picture so the first syllable is never clipped by the cut), and `duck_continu` (hold the music down through the whole clip, not just under words).
- Ken Burns on photos via zoompan; motion types and durations live in the EDL.
- Coupes franches (hard cuts) also serve as chunk boundaries in assembly — the renderer splits xfade chains there automatically.
