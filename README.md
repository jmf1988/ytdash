# ytlivedash
The aim of this project is to have native performance when playing youtube videos without losing adaptative video playback, which similar projects lacks, for this latency is a priority, so with a combination of parallelized download and manifestless DASH  this can be achieved.

Recommended dependencies: mpv (>=0.28 recommended and default), ffmpeg(>=4.0), python3(>=3.5)

Python dependencies: requests 

Dependencies instalation: 
Debian based:
-- apt-get install python3-requests ffmpeg mpv
requests:
-- pip3 install requests --user

Usage:

ytldash.py [Channel or video URL|Search query] [max number of videos found to play in sequence] [Time offset if available]

Example:

To play only the first live result of all results found for "sky":

ytldash.py sky 1 

To play all live streams found in a Youtube channel url: (close the player to play next live video)

ytldash.py "https://www.youtube.com/user/fozzium"

To play first five videos found for the term "livetv" and with 2h ago offset:

ytldash.py "livetv" 5 2h  (also can be 120m or 7200s, for minutes and seconds repectively)   

Recommended and default player is mpv >=0.28 but any player that can play from pipe should work, configured correctly.

Mpv player tips: Shift + I to see video and audio live details.

Recommended ffmpeg >=4.0 ( or better the tiny specific ffmpeg x86_64 build from this repo.)


