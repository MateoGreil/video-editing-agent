import json
import re
import subprocess
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
RUSHES = PROJECT / "rushes"
OUTPUT = PROJECT / "inventaire.json"

NAME = re.compile(r"PXL_(\d{8})_(\d{9})((?:\.[A-Za-z0-9-]+)*)\.(\w+)$")
VIDEO_EXT = {"mp4", "mov"}
PHOTO_EXT = {"jpg", "jpeg", "png", "heic"}


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def rotation(stream):
    for side in stream.get("side_data_list", []):
        if "rotation" in side:
            return int(side["rotation"])
    return int(stream.get("tags", {}).get("rotate", 0))


def describe_video(path):
    data = probe(path)
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    has_audio = any(s["codec_type"] == "audio" for s in data["streams"])
    width, height = video["width"], video["height"]
    if abs(rotation(video)) in (90, 270):
        width, height = height, width
    return {
        "duration": round(float(data["format"]["duration"]), 2),
        "codec": video["codec_name"],
        "width": width,
        "height": height,
        "fps": round(float(Fraction(video["r_frame_rate"])), 2),
        "audio": has_audio,
        "size_mb": round(int(data["format"]["size"]) / 1e6, 1),
    }


def scan():
    entries = []
    for path in sorted(RUSHES.iterdir()):
        match = NAME.match(path.name)
        if not match:
            entries.append({"file": path.name, "kind": "inconnu"})
            continue
        day, clock, tag, ext = match.groups()
        ext = ext.lower()
        entry = {"file": path.name, "day": day, "time": clock[:6], "tag": tag.lstrip(".")}
        if ext in VIDEO_EXT:
            entry["kind"] = "video"
            entry.update(describe_video(path))
        elif ext in PHOTO_EXT:
            entry["kind"] = "photo"
        else:
            entry["kind"] = "autre"
        entries.append(entry)
    return entries


def mmss(seconds):
    return f"{int(seconds // 60)}:{int(seconds % 60):02d}"


def report(entries):
    videos = [e for e in entries if e["kind"] == "video"]
    photos = [e for e in entries if e["kind"] == "photo"]
    print(f"{len(entries)} fichiers : {len(photos)} photos, {len(videos)} vidéos, "
          f"{len(entries) - len(photos) - len(videos)} autres")
    print(f"Durée vidéo totale : {mmss(sum(v['duration'] for v in videos))}\n")

    print("Tags de nom :", dict(Counter(e.get("tag", "") or "(aucun)" for e in entries)))
    print("Codecs      :", dict(Counter(v["codec"] for v in videos)))
    print("Résolutions :", dict(Counter(f"{v['width']}x{v['height']}" for v in videos)))
    print("FPS         :", dict(Counter(v["fps"] for v in videos)))
    print("Sans audio  :", sum(1 for v in videos if not v["audio"]), "\n")

    by_day = defaultdict(lambda: {"photos": 0, "videos": 0, "secondes": 0.0})
    for e in entries:
        if "day" not in e:
            continue
        stats = by_day[e["day"]]
        if e["kind"] == "photo":
            stats["photos"] += 1
        elif e["kind"] == "video":
            stats["videos"] += 1
            stats["secondes"] += e["duration"]
    print("Jour       photos  vidéos  durée vidéo")
    for day in sorted(by_day):
        s = by_day[day]
        print(f"{day}  {s['photos']:>6}  {s['videos']:>6}  {mmss(s['secondes']):>10}")

    print("\nVidéos (jour heure durée résolution fps tag):")
    for v in sorted(videos, key=lambda e: (e["day"], e["time"])):
        print(f"{v['day']} {v['time']}  {mmss(v['duration']):>6}  {v['width']}x{v['height']}  "
              f"{v['fps']:>5}  {v['tag'] or '-'}")


def main():
    entries = scan()
    OUTPUT.write_text(json.dumps(entries, indent=2, ensure_ascii=False))
    report(entries)


main()
