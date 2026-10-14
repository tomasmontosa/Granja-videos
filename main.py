import os
import json
import re
import subprocess
import pathlib
import html
import requests

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "YouTubeShortPilot/1.0 (personal educational project; contact via repository owner)"

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)

def safe_path(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

def clean_html(value):
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", "", value)
    return " ".join(value.split()).strip()

def get_stock_video(query, target):
    # Commons files have individual licenses. Accept only clearly identified CC0,
    # Public Domain, or CC BY 4.0 files; skip ambiguous and ShareAlike licenses.
    params = {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrnamespace": 6,
        "gsrsearch": f"{query} filetype:video",
        "gsrlimit": 20,
        "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata",
    }
    r = requests.get(COMMONS_API, params=params,
                     headers={"User-Agent": USER_AGENT}, timeout=30)
    r.raise_for_status()
    pages = r.json().get("query", {}).get("pages", {})
    candidates = []

    for page in pages.values():
        info_list = page.get("imageinfo", [])
        if not info_list:
            continue
        info = info_list[0]
        mime = (info.get("mime") or "").lower()
        if not mime.startswith("video/"):
            continue
        size = info.get("size") or 0
        if size and size > 150 * 1024 * 1024:
            continue

        meta = info.get("extmetadata", {})
        license_short = clean_html(meta.get("LicenseShortName", {}).get("value", ""))
        license_url = clean_html(meta.get("LicenseUrl", {}).get("value", ""))
        creator = clean_html(meta.get("Artist", {}).get("value", "")) or clean_html(
            meta.get("Credit", {}).get("value", "")) or "Autor no indicado"
        title = page.get("title", "Archivo de Wikimedia Commons")
        source_page = info.get("descriptionurl", "")
        download_url = info.get("url", "")

        normalized = license_short.lower()
        allowed = (
            normalized in {"cc0 1.0", "cc0", "public domain", "public domain mark"}
            or normalized.startswith("cc by 4.0")
        )
        if not allowed or not download_url or not source_page:
            continue

        candidates.append({
            "title": title,
            "creator": creator,
            "license": license_short,
            "license_url": license_url,
            "source_page": source_page,
            "download_url": download_url,
            "size": size,
        })

    if not candidates:
        raise RuntimeError(
            f"No encontré videos con licencia CC0, Dominio Público o CC BY 4.0 para: {query}. "
            "Probá con una búsqueda visual más general."
        )

    # Use the first suitable result. Keep the file page and license for attribution.
    chosen = candidates[0]
    with requests.get(chosen["download_url"], stream=True,
                      headers={"User-Agent": USER_AGENT}, timeout=90) as resp:
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(1024 * 1024):
                if chunk:
                    f.write(chunk)

    attribution = (
        f"Material visual: {chosen['title']}\n"
        f"Autor/crédito: {chosen['creator']}\n"
        f"Fuente: {chosen['source_page']}\n"
        f"Licencia: {chosen['license']}"
        + (f" ({chosen['license_url']})" if chosen["license_url"] else "")
        + "\nDescargado desde Wikimedia Commons; se aplican los términos de la licencia indicada."
    )
    return attribution

def make_video(script):
    slug = re.sub(r"[^a-z0-9]+", "-", script["id"].lower()).strip("-")
    audio = OUT / f"{slug}.mp3"
    srt = OUT / f"{slug}.srt"
    stock = OUT / f"{slug}-stock"
    video = OUT / f"{slug}.mp4"

    run([
        "edge-tts", "--voice", script.get("voice", "es-AR-ElenaNeural"),
        "--text", script["narration"], "--write-media", str(audio),
        "--write-subtitles", str(srt)
    ])

    attribution = get_stock_video(script["visual_search"], stock)

    subtitle_path = safe_path(srt.resolve())
    duration_probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(audio)],
        capture_output=True, text=True, check=True
    )
    duration = max(1, float(duration_probe.stdout.strip()))
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        f"subtitles='{subtitle_path}':force_style='FontName=DejaVu Sans,FontSize=16,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=3,"
        "Shadow=1,Alignment=2,MarginV=170'"
    )
    run([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(stock), "-i", str(audio),
        "-t", f"{duration:.2f}", "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
        "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(video)
    ])

    description = script["description"].strip()
    description += "\n\n" + attribution
    description += "\n\nNarración original generada para este video. Revisa la licencia indicada arriba antes de reutilizar el material."
    return video, description

def upload(video_path, script, description):
    client_id = os.environ["YT_CLIENT_ID"]
    client_secret = os.environ["YT_CLIENT_SECRET"]
    refresh_token = os.environ["YT_REFRESH_TOKEN"]
    creds = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=["https://www.googleapis.com/auth/youtube.upload"],
    )
    creds.refresh(Request())
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
    body = {
        "snippet": {
            "title": script["title"][:100],
            "description": description[:5000],
            "tags": script.get("tags", [])[:20],
            "categoryId": script.get("category_id", "27"),
            "defaultLanguage": "es",
            "defaultAudioLanguage": "es"
        },
        "status": {
            "privacyStatus": "private",
            "selfDeclaredMadeForKids": False
        }
    }
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(str(video_path), chunksize=-1, resumable=True)
    )
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    print("Uploaded video ID:", response["id"])
    print("URL: https://www.youtube.com/watch?v=" + response["id"])

def main():
    script_file = os.environ.get("SCRIPT_FILE", "scripts/sol_desaparece.json")
    with open(ROOT / script_file, encoding="utf-8") as f:
        script = json.load(f)
    video, description = make_video(script)
    upload(video, script, description)

if __name__ == "__main__":
    main()
 
