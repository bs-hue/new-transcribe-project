import yt_dlp

print("=====================================================")
print("             YOUTUBE OAUTH2 LOGIN SCRIPT             ")
print("=====================================================")
print("When you run this script, yt-dlp will ask you to go  ")
print("to google.com/device and enter a code.")
print("Once you complete the login, the token will be saved ")
print("permanently in /data/yt-dlp/youtube_oauth2_tokens.json")
print("=====================================================\n")

import os
os.makedirs("/data/yt-dlp", exist_ok=True)

options = {
    "username": "oauth2",
    "password": "",
    "cache_dir": "/data/yt-dlp",
    "quiet": False,
}

print("Requesting OAuth2 login from YouTube... Please wait.\n")

with yt_dlp.YoutubeDL(options) as ydl:
    try:
        # We just fetch metadata for a tiny video to trigger the login flow
        ydl.extract_info("https://www.youtube.com/watch?v=BaW_jenozKc", download=False)
        print("\n=====================================================")
        print("SUCCESS! OAuth2 token generated and saved!")
        print("The backend will now automatically use this token.")
        print("=====================================================")
    except Exception as e:
        print(f"\nError during login: {e}")
