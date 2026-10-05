# ffmpeg gotchas learned the hard way (all cost real debugging time)

1. **`tile` renders black cells for heterogeneous JPEG sequences** (e.g. Pixel motion photos mixed with plain JPEGs). Symptom: contact sheets mostly black, or only row 1 filled. Fix: normalize every image to an identical-size PNG first, *then* tile the PNG sequence. `tools/contact_sheets.py` does exactly this — reuse it, and verify sheets with `tools/verify_sheets.py` (per-cell luminance). Never trust a contact sheet you haven't verified cell-by-cell.
2. **`fps=1/N` + `tile` sampling** also silently truncates: extracting frames one by one with `-ss` is slower but exact (`tools/qc_sheets.py`).
3. **`amix` requires ≥ 2 inputs** — special-case single-input buses.
4. **`sidechaincompress` stops at the shorter input**: pad the sidechain bus (`apad=whole_dur=…`) or your mix ends early (we got a 31.5 s file instead of 238.5 s).
5. **Every dangling filter label is fatal** ("asplit has an unconnected output"): when a branch is used conditionally (e.g. music with/without ducking), build the graph accordingly — don't asplit "just in case".
6. **`loudnorm` outputs at 192 kHz upsampled rate**: follow it with `aresample=48000`. Single-pass loudnorm on very short clips (<4 s) settles unevenly — prefer measuring and a fixed `volume` gain.
7. **Synchronizing two recordings of the same track** (e.g. studio track + phone recording of people singing along with the record): `asetpts=N/SR/TB` first on both, or you get phasing from 10-19 ms offsets. If offsets are stable over time, a fixed `adelay` is enough — no atempo.
8. **ffmpeg creates output files even when option/filter parsing fails** — a 0-byte or stale output can make the *next* run silently "succeed". Delete outputs before rebuilding, and add `-y` on any step that may re-run.
9. **Ken Burns**: `zoompan` on an upscaled composite (2× target), `d=duration*30`, expression-based z/x/y (see `montage.py`'s `kenburns()` table). Compute frame counts from the segment duration so the motion rate is duration-relative.
10. **Mixed-orientation footage**: one generic framing chain — blurred background (`split`, `scale=…:force_original_aspect_ratio=increase,crop`, `boxblur`, dim) + fitted foreground overlay — works for both masters (1920×1080 and 1080×1920).
11. **Assembly**: chain `xfade` inside chunks; split chunks only at hard cuts (chevauchement 0) and join chunks with the concat demuxer (`-c copy`). Splitting a chunk anywhere else silently turns a crossfade into a hard cut.
12. **yt-dlp breaks monthly**: update via `pipx upgrade yt-dlp` on HTTP 403 / "page needs to be reloaded".
13. **Pixel filenames are UTC**; photo EXIF carries local `OffsetTimeOriginal`. Verify before dating exports (a 16:48 "dusk" photo made sense only after checking the DST change).
