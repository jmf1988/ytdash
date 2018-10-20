# ytlivedash
Python script to play You Tube Live DASH streams using custom local player in Linux

Dependencies: mpv/mplayer/vlc, ffmpeg

Python dependencies: BeatifulSoup4, requests, futures-requests, lxml 

Dependencies instalation: pip install bs4 requests futures-requests lxml

Usage:

ytldash.py [Channel or video URL|Search query] [max number of videos found to play in sequence]

Example:

ytldash.py sky 1 (Will play only the first live result of all results found for "sky" )

ytldash.py "https://www.youtube.com/user/fozzium" (Will play all live streams found in this channel url, closing the player is needed to play next URL )

Recommended and default player is mpv >=0.28 and ffmpeg >= 4.0

Mpv player tips: Shift + I to see video and audio live details.
