from yt_dlp import YoutubeDL

def probe_video(url: str) -> dict:
    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
        return info

info = probe_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
print(info)