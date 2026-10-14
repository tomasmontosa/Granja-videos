import os, json, re, subprocess, tempfile, pathlib, requests
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / "output"
OUT.mkdir(exist_ok=True)

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)

def safe_path(p):
    return str(p).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

def get_stock_video(query, api_key, target):
    r = requests.get(
        "https://api.pexels.com/v1/videos/search",
        headers={"Authorization": api_key},
        params={"query": query, "orientation": "portrait", "per_page": 10},
        timeout=30
    )
    r.raise_for_status()
    videos = r.json().get("videos", [])
    if not videos:
        raise RuntimeError(f"No Pexels videos found for query: {query}")
    # Prefer a medium-sized file to reduce render time.
    files = []
    for video in videos:
        for f in video.get("video_files", []):
            if f.get("file_type") == "video/mp4" and f.get("link"):
                w, h = f.get("width") or 0, f.get("height") or 0
                if w and h:
                    files.append((abs((w/h) - (9/16)), f.get("width", 99999), f["link"], video.get("url",""), video.get("user",{}).get("name","Pexels contributor")))
    if not files:
        raise RuntimeError("Pexels returned no usable MP4 files.")
    files.sort(key=lambda x: (x[0], x[1]))
    _, _, link, page_url, creator = files[0]
    with requests.get(link, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(target, "wb") as f:
            for chunk in resp.iter_content(1024*1024):
                if chunk:
                    f.write(chunk)
    return page_url, creator

def make_video(script, pexels_key):
    slug = re.sub(r"[^a-z0-9]+", "-", script["id"].lower()).strip("-")
    audio = OUT / f"{slug}.mp3"
    srt = OUT / f"{slug}.srt"
    stock = OUT / f"{slug}-stock.mp4"
    video = OUT / f"{slug}.mp4"

    # Use Edge's online TTS service via the open-source edge-tts package.
    run(["edge-tts", "--voice", script.get("voice", "es-AR-ElenaNeural"),
         "--text", script["narration"], "--write-media", str(audio),
         "--write-subtitles", str(srt)])

    source_url, creator = get_stock_video(script["visual_search"], pexels_key, stock)

    # Render a vertical 1080x1920 short. The stock video is looped to match narration.
    # Captions are burned in from the generated SRT. Upload is private by default.
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
    run(["ffmpeg", "-y", "-stream_loop", "-1", "-i", str(stock), "-i", str(audio),
         "-t", f"{duration:.2f}", "-vf", vf, "-map", "0:v:0", "-map", "1:a:0",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "24",
         "-c:a", "aac", "-b:a", "128k", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(video)])

    description = script["description"].strip()
    description += f"\n\nVisual footage: {source_url} (Pexels; contributor: {creator})."
    description += "\nThis Short uses original narration and licensed stock footage."
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
    pexels_key = os.environ["PEXELS_API_KEY"]
    with open(ROOT / script_file, encoding="utf-8") as f:
        script = json.load(f)
    video, description = make_video(script, pexels_key)
    upload(video, script, description)

if __name__ == "__main__":
    main()
