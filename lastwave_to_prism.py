#!/usr/bin/env python3
"""Convert a LastWave backup into a Prism (YouTube Music) backup zip.
Looks up every song on YouTube Music to get real video IDs.

Setup:   pip install ytmusicapi
Run:     python lastwave_to_prism.py LastWave_All_Playlists_Updated.json
Test:    python lastwave_to_prism.py LastWave_All_Playlists_Updated.json --only "Damn..."
Re-running resumes from cache (yt_cache.json), so it's safe to stop and restart.
"""
import argparse, json, secrets, time, zipfile, os, sys
from ytmusicapi import YTMusic

ap = argparse.ArgumentParser()
ap.add_argument("src")
ap.add_argument("--only", help="only convert the playlist with this exact title")
ap.add_argument("--out", default="Prism_backup_LastWave_matched.zip")
a = ap.parse_args()

CACHE = "yt_cache.json"
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
yt = YTMusic()

def thumb(r):
    th = r.get("thumbnails") or []
    if not th:
        return None
    u = th[0]["url"]
    return u.replace("w60-h60", "w120-h120")

def lookup(name, artist, album):
    key = f"{name}|||{artist}".lower()
    if key in cache:
        return cache[key]
    res = None
    for attempt in range(3):
        try:
            hits = yt.search(f"{name} {artist}", filter="songs", limit=3)
            break
        except Exception as e:
            time.sleep(2 * (attempt + 1)); hits = []
    if hits:
        r = hits[0]
        s = {"id": r["videoId"], "title": r["title"],
             "artists": [{"name": x["name"], **({"id": x["id"]} if x.get("id") else {})} for x in r.get("artists", [])]}
        al = r.get("album")
        if al:
            s["album"] = {"title": al["name"], **({"id": al["id"]} if al.get("id") else {})}
        t = thumb(r)
        if t: s["thumbnail"] = t
        if r.get("isExplicit"): s["explicit"] = True
        res = s
    cache[key] = res
    return res

d = json.load(open(a.src, encoding="utf-8"))
pls = [p for p in d["playlists"] if not a.only or p["title"].strip() == a.only]
now = int(time.time() * 1000)
lists, missed = [], []
total = sum(len(json.loads(p["tracksJson"])) for p in pls)
done = 0
for i, p in enumerate(pls):
    songs = []
    for t in json.loads(p["tracksJson"]):
        done += 1
        s = lookup(t["name"], t.get("artist") or "", t.get("album"))
        if s: songs.append(s)
        else: missed.append(f'{p["title"]}: {t["name"]} - {t.get("artist")}')
        if done % 25 == 0:
            print(f"{done}/{total}", flush=True)
            json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)
        time.sleep(0.25)
    lists.append({"id": "prism:" + secrets.token_hex(6), "title": p["title"].strip(),
                  "songs": songs, "createdAt": now - i, "updatedAt": now - i})
json.dump(cache, open(CACHE, "w", encoding="utf-8"), ensure_ascii=False)

hdr = {"format": 2, "app": "com.prism.music", "versionCode": 67, "versionName": "1.8.7.6",
       "createdAt": now, "parts": ["LIBRARY"]}
prefs = ("<?xml version='1.0' encoding='utf-8' standalone='yes' ?>\n<map>\n"
         '    <boolean name="stars_repaired_182" value="true" />\n</map>\n')
with zipfile.ZipFile(a.out, "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("prism-backup.json", json.dumps(hdr, separators=(",", ":")))
    z.writestr("files/library/tags.json", "{}")
    z.writestr("shared_prefs/artist_prefs.xml", prefs)
    z.writestr("files/library/prism.json", json.dumps({"lists": lists}, ensure_ascii=False, separators=(",", ":")))
open("unmatched.txt", "w", encoding="utf-8").write("\n".join(missed))
print(f"Done. {a.out} written. {len(missed)} songs not found (see unmatched.txt).")
