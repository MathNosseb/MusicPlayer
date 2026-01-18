import requests
import json
import base64
titre = str(input("nom de la musique: "))
url = f"https://monochrome-api.samidy.com/search?s={titre}"
res = requests.get(url)
data = res.json()

# Vérifie le JSON

# Convertir en dictionnaire Python

# Écriture propre dans un fichier


playing = {}

for track in data["data"]["items"]:
    playing[track["id"]] = {
        "title" : track["title"],
        "artist": track["artist"]["name"],
        "duration": round(track["duration"] / 60,2)
    }

    print(track["title"])
    print(track["artist"]["name"])
    print(f"{round(track["duration"] / 60,2)} min")
    print(f"id : {track["id"]}")
    print("\n")
with open("/home/matheo/programmation/python/spotify/data.json", "w", encoding="utf-8") as f:
    json.dump(playing, f, indent=4, ensure_ascii=False)

number = int(input("id a telecharger: "))

print(f"vous avez selectionné {playing[number]["title"]} de {playing[number]["artist"]}")
url = f"https://triton.squid.wtf/track/?id={number}&quality=LOSSLESS"
res = requests.get(url)
data = res.json()

# Décodage en bytes
decoded_bytes = base64.b64decode(data["data"]["manifest"])

# Convertir en string UTF-8
decoded_string = decoded_bytes.decode("utf-8")
print(json.loads(decoded_string)["urls"][0])

url = json.loads(decoded_string)["urls"][0]
filename = f"/home/matheo/programmation/python/spotify/{playing[number]['title']}.flac"

response = requests.get(url, stream=True)  # active le streaming
total_size = int(response.headers.get('content-length', 0))  # taille totale du fichier
chunk_size = 1024 * 1024  # 1 Mo par morceau
downloaded = 0

with open(filename, "wb") as f:
    for chunk in response.iter_content(chunk_size=chunk_size):
        if chunk:
            f.write(chunk)
            downloaded += len(chunk)
            percent = downloaded / total_size * 100 if total_size else 0
            print(f"\rTéléchargé : {percent:.2f}%", end='')

print("\nTéléchargement terminé !")