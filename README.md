# ytlivedash
The aim of this project is to have native performance when playing youtube videos without losing adaptative video playback, which similar projects lacks, for this latency is a priority, so with a combination of parallelized download and manifestless DASH  this can be achieved.

Recommended dependencies: mpv (>=0.28 recommended and default), ffmpeg(>=4.0), python3(>=3.5)

Python dependencies: requests 

Dependencies instalation: 
- Debian based:
apt-get install python3-requests ffmpeg mpv

Pip:
- pip3 install requests --user

Usage: 

ytdash.py [-h] [--version] [-quiet] [-search] [-maxresults MAXRESULTS]\
	      [-debug] [-player PLAYER] [-maxfps MAXFPS] [-maxband MAXBAND]\
          [-maxheight MAXHEIGHT] [-maxwidth MAXWIDTH] [-ffmpeg FFMPEG]\
          [-fixed] [-offset OFFSET]  URL|QUERY [URL|QUERY ...]

Youtube DASH video playback.

positional arguments:
  URL|QUERY             URLs or search queries of videos to play

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -quiet, -q            enable quiet mode (default: False)
  -search, -s           search mode (default: False)
  -maxresults MAXRESULTS, -mr MAXRESULTS
                        search max results (default: 5)
  -debug, -d            enable debug mode (default: False)
  -player PLAYER, -p PLAYER
                        player bin name, (default: mpv)
  -maxfps MAXFPS, -mf MAXFPS
                        max video fps to allow (default: 60)
  -maxband MAXBAND, -mb MAXBAND
                        max video bandwidth in kB/s to allow when possible
                        (default: 700)
  -maxheight MAXHEIGHT, -mh MAXHEIGHT
                        max video heigth to allow (default: 720)
  -maxwidth MAXWIDTH, -mw MAXWIDTH
                        max video width to allow (default: 1360)
  -ffmpeg FFMPEG, -ff FFMPEG
                        ffmpeg location route (default: ffmpeg)
  -fixed, -f            Play a fixed video quality instead of doing bandwidth
                        adaptive quality change, This is the max set from
                        options (default: False)
  -offset OFFSET, -o OFFSET
                        Time or segments offset from where start to play,
                        (i.e: 2h, 210m, 3000s or 152456, for hours, minutes,
                        seconds and nº of segment respectively.)

Examples:

To play a single video are all equivalent:
- ytldash.py "https://www.youtube.com/watch?v=lrX6ktLg8WQ"
- ytldash.py "//youtube.com/watch?v=lrX6ktLg8WQ"
- ytldash.py "https://youtu.be.com/lrX6ktLg8WQ"
- ytldash.py "lrX6ktLg8WQ"

To search a live video in a channel listing the first 10 results to choose or playing if only one live video found:

- ytdash.py "https://www.youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash.py "//youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash.py "https://www.youtube.com/user/skynews" -s -maxresults 10

are all equivalent.

Extreme example:

To play first 5 videos in a channel one by one with a max height of 720, max FPS of 30, using a max bandwidth of 400 kB/s, with an offset, if live, of 30 minutes and with bandwidth adaptative mode disabled:

- ytdash.py "https://www.youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -f -maxresults 5 -offset 30m -maxfps 30 -maxheight 720 -maxband 400

That will discard all videos above the first limit reached and play the maximun quality left in fixed mode (the selected quality will be not switched to a lower one even if delays or bandwidth drops are detected.)

Is also possible to play some non-live public videos but that is not a priority for the project.

Recommended and default player is mpv >=0.28 but any player that can play from pipe should work, configured correctly.

Mpv player tips: Shift + I to see video and audio live details.

Recommended ffmpeg >=4.0 ( or better the tiny specific ffmpeg x86_64 build from this repo.)


