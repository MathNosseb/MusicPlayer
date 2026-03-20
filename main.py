import requests
import json
import base64
import os
from pathlib import Path
import re
from urllib.parse import quote
from typing import List, Dict, Optional

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────

SAVE_ROOT = Path.home() / "Music" / "Téléchargements_monochrome"
QUALITY = "LOSSLESS"
CHUNK_SIZE = 1024 * 1024  # 1 Mo

headers = {"User-Agent": "MusicBatchDownloader/1.0"}

# ────────────────────────────────────────────────
def sanitize_filename(s: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '', s).strip()[:180]

def parse_tracks(data) -> List[Dict]:
    tracks = []

    if isinstance(data, list):
        for item in data:
            if isinstance(item, str):
                if " - " in item:
                    artist, title = item.split(" - ", 1)
                    tracks.append({"artist": artist.strip(), "title": title.strip()})
                else:
                    tracks.append({"artist": "", "title": item.strip()})

            elif isinstance(item, dict):
                artist = item.get("artist") or item.get("artiste") or ""
                title = item.get("title") or item.get("titre") or item.get("name") or ""
                if title:
                    tracks.append({"artist": str(artist).strip(), "title": str(title).strip()})

    elif isinstance(data, dict):
        for key in ("tracks", "musiques", "songs", "liste"):
            if key in data:
                return parse_tracks(data[key])  # ici OK

    return tracks

def load_tracks_from_json(filepath: str) -> List[Dict]:
    path = Path(filepath)
    if not path.is_file():
        raise FileNotFoundError(f"Fichier non trouvé : {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    tracks = parse_tracks(data)

    if not tracks:
        raise ValueError("Aucune piste valide trouvée dans le JSON")

    print(f"{len(tracks)} pistes chargées depuis {filepath}")
    return tracks


def search_track(artist: str, title: str) -> Optional[Dict]:
    query = f"{artist} {title}".strip()
    if not query:
        return None

    url = f"https://monochrome-api.samidy.com/search?s={quote(query)}"

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"  Recherche échouée : {e}")
        return None

    items = data.get("data", {}).get("items", [])

    if items:
        return items[0]  # 👉 premier résultat direct

    return None


def get_download_url(track_id: str) -> Optional[str]:
    url = f"https://triton.squid.wtf/track/?id={track_id}&quality={QUALITY}"
    try:
        r = requests.get(url, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()

        manifest_b64 = data.get("data", {}).get("manifest")
        if not manifest_b64:
            return None

        decoded = base64.b64decode(manifest_b64).decode("utf-8", errors="ignore")
        manifest = json.loads(decoded)

        urls = manifest.get("urls", [])
        if urls:
            return urls[0]
    except:
        pass
    return None


def download(url: str, filepath: Path):
    try:
        with requests.get(url, stream=True, timeout=30) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0

            with open(filepath, "wb") as f:
                for chunk in r.iter_content(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total:
                            pct = downloaded / total * 100
                            print(f"\r  {pct:5.1f}%  {downloaded//(1024*1024):3} Mo   ", end="")
                        else:
                            print(f"\r  {downloaded//(1024*1024):3} Mo   ", end="")

        print(f"\r  ✓ {filepath.name}")
    except Exception as e:
        print(f"\r  ✗ Échec : {e}")


# ──────────────────────────────────────────────── MAIN ────────────────────────────────────────────────

if __name__ == "__main__":
    json_path = "/home/matheo/programmation/python/spotify/data.json"
    if not json_path:
        exit(1)

    try:
        tracks_list = load_tracks_from_json(json_path)
    except Exception as e:
        print(f"Erreur lecture JSON : {e}")
        exit(1)

    print("\n" + "═" * 70)
    print("Analyse et recherche des pistes...")
    print("═" * 70 + "\n")

    to_download = []
    not_found = []

    for i, track in enumerate(tracks_list, 1):
        artist = track["artist"]
        title = track["title"]
        print(f"[{i:3d}/{len(tracks_list)}]  {artist} – {title}")

        result = search_track(artist, title)

        if result:
            found_title = result["title"]
            found_artist = result["artist"]["name"]
            track_id = result["id"]
            duration_min = round(result.get("duration", 0) / 60, 1)

            print(f"   → Trouvé : {found_artist} – {found_title} ({duration_min} min)  id={track_id}")

            to_download.append({
                "original_artist": artist,
                "original_title": title,
                "found_artist": found_artist,
                "found_title": found_title,
                "id": track_id,
                "duration_min": duration_min
            })
        else:
            print("   → NON TROUVÉ")
            not_found.append(track)

        print()

    print("\n" + "═" * 70)
    print(f"Résumé : {len(to_download)} pistes trouvées  |  {len(not_found)} non trouvées")
    print("═" * 70 + "\n")

    if not to_download:
        print("Aucune piste trouvée → fin.")
        exit(0)

    # Affichage récapitulatif clair
    print("Pistes qui seront téléchargées :")
    for i, item in enumerate(to_download, 1):
        print(f"  {i:3d} | {item['found_artist']} – {item['found_title']}   ({item['duration_min']} min)")

    if not_found:
        print("\nNon trouvées (ignorées) :")
        for item in not_found:
            print(f"  • {item['artist']} – {item['title']}")

    print("\n" + "═" * 70)
    rep = input("\nTout est bon ? Télécharger maintenant ? (o / oui / y) ").strip().lower()

    if rep not in ("o", "oui", "y", "yes"):
        print("Annulé.")
        exit(0)

    # ─── Téléchargement ───────────────────────────────────────

    SAVE_ROOT.mkdir(parents=True, exist_ok=True)

    for item in to_download:
        print(f"\nTéléchargement : {item['found_artist']} – {item['found_title']}")

        dl_url = get_download_url(item["id"])
        if not dl_url:
            print("  ✗ Impossible de récupérer l'URL")
            continue

        filename = sanitize_filename(f"{item['found_artist']} - {item['found_title']}.flac")
        filepath = SAVE_ROOT / filename

        if filepath.exists():
            print("  (déjà présent → ignoré)")
            continue

        download(dl_url, filepath)

    print("\n" + "═" * 70)
    print("Téléchargement terminé.")
    print("═" * 70)