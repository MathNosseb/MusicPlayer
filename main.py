import json
import re
import sys
from pathlib import Path
from urllib.parse import quote
from typing import List, Dict, Optional

import requests
import yt_dlp

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────

JSON_PATH  = Path.home() / "programmation/python/spotify/data.json"
SAVE_ROOT  = Path.home() / "Musique" / "Téléchargements"
AUDIO_FMT  = "bestaudio/best"          # yt-dlp format selector
AUDIO_EXT  = "opus"                    # codec cible (opus ≃ lossless perceptif à 160k+)
MAX_SEARCH = 1                         # nb résultats YouTube Music à évaluer

headers = {"User-Agent": "MusicBatchDownloader/1.0"}

# ────────────────────────────────────────────────
# UTILS
# ────────────────────────────────────────────────

def sanitize(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', s).strip()[:180]


def parse_tracks(data) -> List[Dict]:
    if isinstance(data, dict):
        for key in ("tracks", "musiques", "songs", "liste", "titres"):
            if key in data:
                return parse_tracks(data[key])
        return []

    tracks = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                if " - " in item:
                    a, t = item.split(" - ", 1)
                    tracks.append({"artist": a.strip(), "title": t.strip()})
                else:
                    tracks.append({"artist": "", "title": item.strip()})
            elif isinstance(item, dict):
                artist = item.get("artist") or item.get("artiste") or ""
                title  = item.get("title")  or item.get("titre")   or item.get("name") or ""
                if title:
                    tracks.append({"artist": str(artist).strip(), "title": str(title).strip()})
    return tracks


def load_tracks(path: Path) -> List[Dict]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    tracks = parse_tracks(data)
    if not tracks:
        raise ValueError("Aucune piste valide dans le JSON")
    print(f"{len(tracks)} piste(s) chargée(s) depuis {path.name}\n")
    return tracks

# ────────────────────────────────────────────────
# RECHERCHE — Deezer (métadonnées propres)
# ────────────────────────────────────────────────

def search_deezer(artist: str, title: str) -> Optional[Dict]:
    q = quote(f"{artist} {title}".strip())
    try:
        r = requests.get(
            f"https://api.deezer.com/search?q={q}&limit=1",
            headers=headers, timeout=10
        )
        r.raise_for_status()
        items = r.json().get("data", [])
        if items:
            t = items[0]
            return {
                "artist":   t["artist"]["name"],
                "title":    t["title"],
                "duration": t["duration"],          # secondes
                "isrc":     t.get("isrc", ""),
            }
    except Exception as e:
        print(f"  [deezer] {e}")
    return None

# ────────────────────────────────────────────────
# DOWNLOAD — yt-dlp via YouTube Music
# ────────────────────────────────────────────────

def build_ytdlp_opts(filepath: Path) -> dict:
    return {
        "format":            AUDIO_FMT,
        "outtmpl":           str(filepath),
        "postprocessors": [{
            "key":            "FFmpegExtractAudio",
            "preferredcodec": AUDIO_EXT,
        }],
        "quiet":             True,
        "no_warnings":       True,
        "noprogress":        True,
        # plus de default_search ici
    }


def download_track(artist: str, title: str, filepath: Path) -> bool:
    query = f"ytsearch1:{artist} {title}"   # ← changement ici
    opts  = build_ytdlp_opts(filepath)

    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([query])
        final = filepath.with_suffix(f".{AUDIO_EXT}")
        if final.exists() and final.stat().st_size > 0:
            print(f"  ✓ {final.name}")
            return True
        print("  ✗ Fichier vide ou absent")
        return False
    except Exception as e:
        print(f"  ✗ {e}")
        return False

# ────────────────────────────────────────────────
# MAIN
# ────────────────────────────────────────────────

def main():
    # ── Chargement ──────────────────────────────
    try:
        tracks = load_tracks(JSON_PATH)
    except Exception as e:
        print(f"Erreur JSON : {e}")
        sys.exit(1)

    sep = "═" * 70

    # ── Recherche Deezer ─────────────────────────
    print(sep)
    print("Recherche des métadonnées (Deezer)...")
    print(sep + "\n")

    to_dl    : List[Dict] = []
    not_found: List[Dict] = []

    for i, track in enumerate(tracks, 1):
        artist, title = track["artist"], track["title"]
        print(f"[{i:3d}/{len(tracks)}]  {artist} – {title}")

        meta = search_deezer(artist, title)
        if meta:
            dur = f"{meta['duration'] // 60}:{meta['duration'] % 60:02d}"
            print(f"   → {meta['artist']} – {meta['title']}  ({dur})")
            to_dl.append({**track, **meta})
        else:
            print("   → NON TROUVÉ (sera tenté avec le nom brut)")
            # On tente quand même avec le nom original
            to_dl.append({**track, "artist": artist, "title": title, "duration": 0})
        print()

    # ── Récap ────────────────────────────────────
    print(sep)
    print(f"Pistes à télécharger : {len(to_dl)}   |   Non trouvées sur Deezer : {len(not_found)}")
    print(sep + "\n")

    for i, t in enumerate(to_dl, 1):
        dur = t.get("duration", 0)
        tag = f"{dur // 60}:{dur % 60:02d}" if dur else "??:??"
        print(f"  {i:3d} | {t['artist']} – {t['title']}  ({tag})")

    print()
    rep = input("Télécharger maintenant ? (o/oui/y) ").strip().lower()
    if rep not in ("o", "oui", "y", "yes"):
        print("Annulé.")
        sys.exit(0)

    # ── Téléchargement ───────────────────────────
    print()
    SAVE_ROOT.mkdir(parents=True, exist_ok=True)

    ok = ko = skipped = 0

    for item in to_dl:
        artist, title = item["artist"], item["title"]
        print(f"\n↓  {artist} – {title}")

        stem     = sanitize(f"{artist} - {title}")
        filepath = SAVE_ROOT / stem          # extension ajoutée par yt-dlp

        # Vérif si déjà présent
        existing = list(SAVE_ROOT.glob(f"{re.escape(stem)}.*"))
        if existing:
            print(f"  (déjà présent → ignoré)")
            skipped += 1
            continue

        success = download_track(artist, title, filepath)
        if success:
            ok += 1
        else:
            ko += 1

    # ── Bilan ────────────────────────────────────
    print(f"\n{sep}")
    print(f"Terminé.  ✓ {ok}  ✗ {ko}  ⏭ {skipped} ignoré(s)")
    print(sep)


if __name__ == "__main__":
    main()