# Video Editing Agent

AI-agent pipeline for editing videos end-to-end from raw footage — headless Linux, CLI only, open-source tools only (ffmpeg, faster-whisper, yt-dlp).

## Layout

- `tools/` — reusable pipeline scripts (copied into each project, never run from here)
- `docs/` — reference: EDL schema, ffmpeg gotchas
- `editing/` — one subdirectory per project (never committed)

## Pipeline

1. **Intake** — copy footage into `editing/<project>/rushes/` (read-only from then on)
2. **Inventory** — `inventory.py` → `inventaire.json` (durations, resolutions, fps)
3. **Recon** — vision sub-agents on filmstrips/contact sheets; `audio_analysis.py`, `find_speech.py`, `transcribe.py`
4. **Plan** — `plan-montage.md`, signed off by the user before any long render
5. **EDL** — the film as one JSON timeline (`docs/edl-schema.md`), validated by `verify_edl.py`
6. **Render** — `montage.py` builds 16:9, 9:16, and audio masters from the same EDL
7. **QC** — measured probes + vision-agent review of QC sheets
8. **Deliver** — masters in `rendu/film/`, `export_whatsapp.py` for messaging apps

Every render is fully replayable from the project's scripts + EDL. Full conventions in `AGENTS.md`.
