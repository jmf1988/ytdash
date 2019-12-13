
# YTlivedash
YTlivedash is a linux command line tool written in python 3 that enables media playing with native performance by using a local player to play youtube live DASH videos without having to lose adaptative video playback, which is more important when streaming live content because there is less buffer available to pull from, to do all this latency improvements are approached with a combination of parallelized https requests, DASH protocol and keep alive connections.

Recommended dependencies: mpv (>=0.28 recommended and default), ffmpeg(>=4.0), python3(>=3.5), pycurl(>=7.43.0.2)

Python dependencies: pycurl and certifi

Dependencies installation: 
- Debian based:
apt-get install python3 python3-pycurl python3-certifi ffmpeg mpv 

Optional: for terminal/player titles/descriptions emojis support also install package fonts-symbola.

Note: The above installs distro version of pycurl that can be outdated and come with gnutls backend enabled by default, which may use more memory and cause some issues. To install pycurl with openssl backend that uses less memory and is more realiable do the following:

- Install dependecies on debian to compile libcurl to use openssl backend (better performance):

apt-get install python3-dev libssl-dev libcurl4-openssl-dev python3-pip

PYCURL_SSL_LIBRARY=openssl pip3 install pycurl certifi --user

That's all.

Usage: 
<pre>
usage: ytdash [-h] [--version] [-quiet] [-search] [-research] [-nonlive]
              [-sortby {relevance,viewCount,videoCount,date,rating,title,rating}]
              [-eventtype {live,upcoming,completed}]
              [-safesearch {moderate,none,strict}]
              [-duration {any,long,medium,short}]
              [-videotype {any,episode,movie}]
              [-type {video,channel,playlist}] [-definition {hd,sd,any}]
              [-license {creativeCommon,youtube,any}] [-playlist]
              [-fullscreen] [-maxresults MAXRESULTS] [-debug] [-player PLAYER]
              [-nodescription] [-novolnor] [-maxfps MAXFPS] [-maxband MAXBAND]
              [-maxheight {144,240,360,480,720,1080,1440,2160,4320}]
              [-maxwidth {256,426,640,854,1280,1920,2560,3840,7680}]
              [-ffmpeg FFMPEG] [-autoplay] [-reallive] [-fixed]
              [-offset OFFSET]
              URL|QUERY [URL|QUERY ...]

Youtube DASH video playback.

positional arguments:
  URL|QUERY             URLs or search queries of videos to play

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -quiet, -q            enable quiet mode (default: False)
  -onlyone, -oo         Only one instance of ytdash can be running. (default:
                        False)
  -kill, -k             First terminate all other running instances of ytdash.
                        (default: False)
  -search, -s           search mode, results cache enabled if searched less
                        than 24hs ago, which saves YouTube daily quota,
                        recommended) (default: False)
  -research, -rs        Search with cached results disabled. (default: False)
  -nonlive, -nl         search also for non-live videos (default: False)
  -sortby {relevance,viewCount,videoCount,date,rating,title,rating}, -sb {relevance,viewCount,videoCount,date,rating,title,rating}
                        sorting order for the search results (default:
                        relevance)
  -eventtype {live,upcoming,completed}, -et {live,upcoming,completed}
                        filter results by live event type(default: live)
  -safesearch {moderate,none,strict}, -ss {moderate,none,strict}
                        Safe search mode to use if any(default: moderate)
  -duration {any,long,medium,short}, -dur {any,long,medium,short}
                        filter results by video duration(default: any)
  -videotype {any,episode,movie}, -vt {any,episode,movie}
                        filter results by video type (default: any)
  -type {video,channel,playlist}
                        filter results by type of resource (default: video)
  -definition {hd,sd,any}, -vd {hd,sd,any}
                        filter results by video definition (default: any)
  -license {creativeCommon,youtube,any}
                        filter results by video livense type (default: any)
  -playlist             Play urls found in file (default: False)
  -fullscreen, -fs      Start all videos in fullscreen mode (default: False)
  -maxresults MAXRESULTS, -mr MAXRESULTS
                        search max results (default: 5)
  -debug, -d            enable debug mode (default: False)
  -player PLAYER, -p PLAYER
                        player bin name, (default: mpv)
  -nodescription, -nd   Do not show video descriptions on the terminal/player
                        (default: False)
  -novolnor, -nv        disable volume normalization for all videos (mpv).
                        (default: False)
  -maxfps MAXFPS, -mf MAXFPS
                        max video fps to allow (default: 60)
  -maxband MAXBAND, -mb MAXBAND
                        max video bandwidth in kB/s to allow when possible
                        (default: 700)
  -maxheight {144,240,360,480,720,1080,1440,2160,4320}, -mh {144,240,360,480,720,1080,1440,2160,4320}
                        max video heigth to allow (default: 768)
  -maxwidth {256,426,640,854,1280,1920,2560,3840,7680}, -mw {256,426,640,854,1280,1920,2560,3840,7680}
                        max video width to allow (default: 1360)
  -ffmpeg FFMPEG, -ff FFMPEG
                        ffmpeg location route (default: ffmpeg)
  -autoplay             Autoplay all results returned by search mode (default:
                        False)
  -reallive, -r         Enables lowest latency possible with all types of live
                        streams. (default: False)
  -fixed, -f            Play a fixed video quality instead of doing bandwidth
                        adaptive quality change, This is the max set from
                        options (default: False)
  -offset OFFSET, -o OFFSET
                        Time offset from where the playback start,(i.e: -o 2h,
                        -o 210m, -offset 3000s, for hours, minutes and seconds
                        respectively.) (default: 3 segments)

</pre>
Examples:

To play a single video with id lrX6ktLg8WQ:
- ytdash "https://www.youtube.com/watch?v=lrX6ktLg8WQ" or
- ytdash "//youtube.com/watch?v=lrX6ktLg8WQ" or
- ytdash "https://youtu.be/lrX6ktLg8WQ" or
- ytdash "lrX6ktLg8WQ"

To search a live video in a channel listing the first 10 results to choose or playing if only one live video found:

- ytdash "https://www.youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash "//youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash "https://www.youtube.com/user/skynews" -s -maxresults 10

are all equivalent.

Extreme example:

To play first 5 videos in a channel one by one with a max height of 720, max FPS of 30, using a max bandwidth of 400 kB/s, with an offset, of -30 minutes and with bandwidth adaptative mode disabled:

- ytdash "https://www.youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -f -maxresults 5 -offset 30m -maxfps 30 -maxheight 720 -maxband 400

That will ignore all qualities of the video/s above the first lowest limit reached and play the maximum quality left in fixed mode (the selected quality will be not switched to a lower one even if delays or bandwidth drops are detected.)

Non-live videos:
It is possible to play some non-live non-restricted public videos but that is not a priority for this project and there are many others, more complete and mature tools to do it, however, the connection errors handling and reconnecting (infinite retry)  development needed for the live streams can be an advantage for long videos, these may be better handled than playing them  with a player that uses ffmpeg, with it is more difficult to pass/have complex http options/errors, like long reconnect tries, because the C Curl library used here has more polished and mature code to deal specifically with http/s, and ffmpeg is used just as a muxer/demuxer.

Recommended and default player is mpv >=0.28 but any player that can play from pipe should work, configured correctly.

MPV player tips: Shift + I to see video and audio live details.

Recommended ffmpeg >=4.0 ( or better the tiny specific ffmpeg x86_64 build from this repo.)


