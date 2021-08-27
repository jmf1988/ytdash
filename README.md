
# YTdash
YTdash is a linux command line tool written in python 3 that allows you to search online and play mainly live videos from Youtube with native performance by using a local player without having to lose bandwidth-adaptative capabilities, which is more important when streaming live content because there is less buffer available to pull from. To do all this, latency improvements are approached with a combination of parallelized https requests, DASH protocol, and keep alive connections, using the more reliable third party programs known in each function needed; the Mpv player for low latency playback and minimal interface, ffmpeg for muxing/demuxing and cURL to download the content.

Required dependencies: mpv (>=0.28 recommended and default), ffmpeg(>=4.0), python3(>=3.5), pycurl(>=7.43.0.2)

Python dependencies: pycurl and certifi

Quick installation of dependencies: 
- Debian based:
apt-get install python3 python3-pycurl python3-certifi ffmpeg mpv 

- Optional dependencies: "fonts-symbola" and "libnotify-bin" packages for terminal/player titles/descriptions emojis and symbols support and native desktop notifications respectively.

That's all.

Optional installation of pycurl with openssl backend:

The above installs OS version of pycurl that can be outdated and/or come with gnutls backend enabled by default, depending on the distro used, which may use more memory and cause some issues. To install pycurl with openssl backend that uses less memory and is more realiable using pip tool do the following:

- Install the required dependecies in debian/ubuntu to build pycurl with openssl backend instead 

  - apt-get install python3-dev gcc libssl-dev libcurl4-openssl-dev [python3-pip]

- Remove possible already installed packages with other methods:

  - apt-get remove libcurl4-gnutls-dev && apt-get remove python3-pycurl python3-certifi && pip3 uninstall pycurl certifi
  
- Build and install pycurl with openssl backend:

  - PYCURL_SSL_LIBRARY=openssl pip3 install --no-cache-dir pycurl certifi [--user]

Ytdash command line usage: 
<pre>
usage: ytdash [-h] [--version] [-quiet] [-onlyone] [-kill] [-search] [-research] [-nonlive]
              [-sortby {relevance,viewCount,videoCount,date,rating,title,rating}] [-eventtype {live,upcoming,completed}]
              [-safesearch {moderate,none,strict}] [-duration {any,long,medium,short}] [-videotype {any,episode,movie}]
              [-type {video,channel,playlist}] [-definition {hd,sd,any}] [-license {creativeCommon,youtube,any}] [-playlist]
              [-fullscreen] [-maxresults MAXRESULTS] [-debug] [-player PLAYER] [-nodescription] [-volnor] [-maxfps MAXFPS]
              [-keeplowfps] [-maxband MAXBAND] [-maxheight MAXHEIGHT] [-maxwidth MAXWIDTH] [-audioquality AUDIOQUALITY]
              [-preferaudiocodec {opus,mp4a,none}] [-prefervideocodec {avc1,vp9,av01}] [-ffmpeg FFMPEG] [-autoplay]
              [-reallive] [-preferquality] [-fixed] [-offset OFFSET]
              URL|QUERY [URL|QUERY ...]

Youtube DASH video playback.

positional arguments:
  URL|QUERY             URLs or search queries of videos to play

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  -quiet, -q            enable quiet mode (default: False)
  -onlyone, -oo         Only one instance of ytdash can be running. (default: False)
  -kill, -k             First terminate all other running instances of ytdash. (default: False)
  -search, -s           search mode, results cache enabled if searched less than 24hs ago, which saves YouTube daily quota,
                        recommended) (default: False)
  -research, -rs        Search with cached results disabled. (default: False)
  -nonlive, -nl         search also for non-live videos (default: False)
  -sortby {relevance,viewCount,videoCount,date,rating,title,rating}, -sb {relevance,viewCount,videoCount,date,rating,title,rating}
                        sorting order for the search results (default: relevance)
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
  -playlist, -pl        Play all urls/ids found in file(s) (default: False)
  -fullscreen, -fs      Start all videos in fullscreen mode (default: False)
  -maxresults MAXRESULTS, -mr MAXRESULTS
                        search max results (default: 5)
  -debug, -d            enable debug mode (default: False)
  -player PLAYER, -p PLAYER
                        player bin name, (default: mpv)
  -httppassthrough, -hp
                        Only for non-live video streams, media URL are passed directly to the player so it handles http
                        connections. (this allows seeking without cache but may be more prone to playback failures under
                        connection errors) (default: False)
  -nodescription, -nd   Do not show video descriptions on the terminal/player (default: False)
  -volnor, -vn          enable volume normalization for all videos (mpv). (default: False)
  -maxfps MAXFPS, -mf MAXFPS
                        max video fps to allow (default: 60)
  -keeplowfps, -klf     Do not not discard lower fps sources for each video resolution if many available. (default: False)
  -maxband MAXBAND, -mb MAXBAND
                        max video bandwidth in kB/s to allow when available (default: 100000000)
  -maxheight MAXHEIGHT, -mh MAXHEIGHT
                        maximum video height to allow
  -maxwidth MAXWIDTH, -mw MAXWIDTH
                        maximum video width to allow
  -audioquality AUDIOQUALITY, -aq AUDIOQUALITY
                        Audio quality to enable if available, 0=lowest, 1-int=medium, -1=highest. (default: -1)
  -preferaudiocodec {opus,mp4a,none}, -pac {opus,mp4a,none}
                        Audio codec to priorize for non-live streams, if a similar quality is available. (default: none)
  -prefervideocodec {avc1,vp9,av01}, -pvc {avc1,vp9,av01}
                        Video codec to priorize for non-live streams, if available. (default: avc1)
  -ffmpeg FFMPEG, -ff FFMPEG
                        ffmpeg location route (default: ffmpeg)
  -autoplay, -a         Autoplay all results returned by search mode (default: False)
  -reallive, -r         Enables lowest latency possible with all types of live streams. (default: False)
  -preferquality, -pq   Prioritize quality over latency in bandwidth-adaptive enabled video streams (default: False)
  -fixed, -f            Play a fixed video quality instead of doing bandwidth adaptive quality change, This is the max set
                        from options (default: False)
  -offset OFFSET, -o OFFSET
                        Time offset from where the playback start,(i.e: -o 2h, -o 210m, -offset 3000s, for hours, minutes
                        and seconds respectively.) (default: 3 segments)
</pre>
Examples:

To play a single video with id lrX6ktLg8WQ, these are all equivalent:
- ytdash "https://www.youtube.com/watch?v=lrX6ktLg8WQ" or
- ytdash "//youtube.com/watch?v=lrX6ktLg8WQ" or
- ytdash "https://youtu.be/lrX6ktLg8WQ" or
- ytdash "lrX6ktLg8WQ"

To search for live videos that match the term "live+news" and return a max of 5 results to choose from:

- ytdash -s live+news

To search for live videos in a particular channel URL and return a max of 10 results to choose from, these are all equivalent:

- ytdash "https://www.youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash "//youtube.com/channel/UCqUowrZdd95X_L7prqCd22Q" -s -maxresults 10
- ytdash "https://www.youtube.com/user/skynews" -s -maxresults 10

Extreme example:

To play first 5 live videos if found in a particular channel one by one with a max height of 720, max FPS of 30, using a max bandwidth of 400 kB/s, with a time offset of 30 minutes ago and with bandwidth adaptative mode disabled:

- ytdash "https://www.youtube.com/channel/UCSyg9cb3Iq-NtlbxqNB9wGw" -s -f -maxresults 5 -offset 30m -maxfps 30 -maxheight 720 -maxband 400

That will ignore all qualities of the video/s above the first lowest limit reached and play the maximum quality left in fixed mode (the selected quality will be not switched to a lower one even if delays or bandwidth drops are detected.)

More examples and tips in the wiki: https://github.com/jmf1988/ytdash/wiki

Non-live videos:

It is possible to play some non-live non-restricted public videos but that is not a priority for this project and there are many others, more complete and mature tools to do it, however, the connection errors handling and reconnecting (infinite retry)  development needed for the live streams can be an advantage for long videos, these may be better handled than playing them  with a player that uses ffmpeg, with it is more difficult to pass/have complex http options/errors, like long reconnect tries, because the C Curl library used here has more polished and mature code to deal specifically with http/s, and ffmpeg is used just as a muxer/demuxer.

Recommended and default player is mpv >=0.28 but any player that can play from pipe should work, configured correctly.

MPV player tips: Shift + I keys to see video and audio live details, "q" to close the player, "m" to mute, "/" and "*" for volume control.

Recommended ffmpeg >=4.0 ( or better the tiny specific ffmpeg x86_64 build from this repo.)


