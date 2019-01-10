#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# pip[2|3] install bs4 lxml pyopenssl requests
from bs4 import BeautifulSoup
from multiprocessing.dummy import Pool as ThreadPool
import requests
import logging
import os
import signal
import sys
import time
import subprocess
import re
import shlex
import readline
import threading
try:
    import gtk
    swidth = gtk.gdk.screen_width()
    sheight = gtk.gdk.screen_height()
except ImportError:
    sheight = 720  # Max video height resolution, equal or less than native res

if os.path.isfile('/tmp/dash2.0.pid'):
    with open('/tmp/dash2.0.pid', 'r') as fd:
        prevpid = fd.read()
        try:
            os.killpg(int(prevpid), signal.SIGTERM)
            print("Killed previous instance...")
        except ProcessLookupError:
            print("Process does not exist...")
os.setpgrp()
with open('/tmp/dash2.0.pid', 'w') as fd:
    fd.write(str(os.getpgrp()))
ffmpegbin = "/home/jmf/bin/ffmpeg"
audiofilename = "/dev/shm/audio"
ffmpegargs = shlex.split('''%s -v 0 -thread_queue_size 100000 -i -
    -thread_queue_size 100000 -i - -c copy -f mpegts pipe:1''' % (ffmpegbin))
pid = os.getpid()
# max RAM cached media size downloaded after pause in Mb:
mpvcachesize = 10*1024
mpvbackcachesize = 5  # max back RAM cached media played/skipped to keep, Mb.

playercmd = """mpv --force-seekable=yes --demuxer-max-back-bytes=%s
            --cache-backbuffer=%s --really-quiet=yes --demuxer-max-bytes=%s
            --demuxer-seekable-cache=yes --cache=%s
            --cache-file-size=%s --cache-seek-min=%s - """ % (
                 mpvbackcachesize * 1048576,
                 mpvbackcachesize * 1024,
                 mpvcachesize * 1024,
                 mpvcachesize * 1,
                 mpvcachesize * 1024,
                 mpvcachesize * 1024)
# playercmd = 'mpv -'
maxfps = 60
autoresync = 1  # Drop segments on high delays to keep live

logging.basicConfig(
    level=logging.INFO, filename="logfile", filemode="w+",
    format="%(asctime)-15s %(levelname)-8s %(message)s")
console = logging.StreamHandler()
console.setLevel(logging.INFO)
# add the handler to the root logger
logging.getLogger('').addHandler(console)
rheaders = None

def Bandwidth(elem):
    return int(elem['bandwidth'])


def SetVideoQuality():
    for i in range(len(videodata)):
        qband = int(videodata[i]['bandwidth'])
        if (
            qband > int(Bandwidths[1]) or
            qband > int(Bandwidths[2]) or
            qband > int(Bandwidths[3])
           ):
            break
        else:
            idx = i
    return int(idx)


def check_url(url):
    status = 0
    while True:
        global head
        head = requests.head(url, allow_redirects=False)
        status = head.status_code
        print("STATUS %s" % status)
        if status == 302:
            # head.connection.close()
            url = head.headers.get('Location') + "/"
        elif status == 200:
            return (url, status)
        else:
            logging.info("Error checking URL, STATUS: %s" % str(status))
            return (url, status)


def get_metadata(videourl, aid, vid):
    logging.info("Youtube URL: %s" % videourl)
    r = session.get(videourl)
    manifestsurl = None
    manifesturlsearch = re.findall('(dashmpd|dashManifestUrl)":"(.+?)"' + '|' +
                               '"(https://manifest.googlevideo.com/' +
                               'api/manifest/dash.+?)"',
                               r.text.replace('\\', ""))
    if manifesturlsearch:
        if manifesturlsearch[0][1]:
            manifesturl = manifesturlsearch[0][1]
        else:
            manifesturl = manifesturlsearch[0][2]
    else:
        logging.info('Couldn\'t extract Manifest URL, skipping item...')
        return 1
    logging.info("Manifest URL: %s" % manifesturl)
    offline = re.search('force_finished|playback_host', str(manifesturl))
    tries = 5
    refreshman = True
    while True:
        if not offline and refreshman:
            rawmanifest = session.get(manifesturl.replace(
                    'ip/', 'keepalive/yes/ip/'), headers=rheaders)
            if not rawmanifest.ok:
                logging.info("Error getting manifest, skipping...")
                return 1
            
        else:
            print("Live recently ended, skipping..." + manifesturl)
            return 1
        soup3 = BeautifulSoup(rawmanifest.content, 'xml')
        segmentsecs = float(soup3.MPD['minimumUpdatePeriod'][2:-1])
        buffersecs = float(soup3.MPD['timeShiftBufferDepth'][2:-1])
        earliestseqnum = int(soup3.MPD['yt:earliestMediaSequence'])
        startnumber = int(soup3.MPD.Period.SegmentList['startNumber'])
        logging.info("Segment duration in secs: " + str(segmentsecs))
        logging.info("Back buffer depth in secs: " + str(buffersecs))
        logging.info("Earliest sequence number: " + str(earliestseqnum))
        logging.info("Start number: " + str(startnumber))
        global sens, twosegmentsdownload, maxparalelsemgs
        twosegmentsdownload = 0
        maxparalelsemgs = 1
        if segmentsecs == 1.000:
            sens = 1
            logging.info('--Live mode: ULTRA LOW LATENCY--')
            maxparalelsemgs = 2
            twosegmentsdownload = 2
        elif segmentsecs == 2.000:
            sens = 1
            logging.info('--Live mode: LOW LATENCY--')
            twosegmentsdownload = 1
        elif segmentsecs == 5.000:
            sens = 1
            logging.info('--Live mode: NORMAL LATENCY--')

        audiourls = soup3.MPD.find(
            "AdaptationSet", mimeType="audio/mp4").findAll('BaseURL')
        videodata = soup3.MPD.find(
            "AdaptationSet", mimeType="video/mp4").findAll(
            'Representation', bandwidth=True)
        videodata.sort(key=Bandwidth)
        logging.info("Total video Qualitys Available: " + str(len(videodata)))
        idx = 0
        while idx < len(videodata):
            videofps = int(videodata[idx]['frameRate'])
            videoheight = int(videodata[idx]['height'])
            if videofps > maxfps or videoheight > sheight:
                del videodata[idx]
            else:
                idx += 1
        aid = aid
        vid = vid
        murls = [audiourls[aid].text, videodata[vid].text]
        pool = ThreadPool(2)
        results = pool.imap(check_url, murls)
        is_video = 0
        for res in results:
            if is_video == 0:
                audiomainurl, astatus = res
                is_video += 1
            else:
                videomainurl, vstatus = res
                is_video = 0
        pool.terminate()
        logging.info("AUDIOMAINURL %s" % audiomainurl)
        logging.info("VIDEOMAINURL %s" % videomainurl)
        if (vstatus == 503 or vstatus == 403 or
           astatus == 503 or astatus == 403):
                tries -= 1
                logging.info("Error Status: %s, trying redirection..." %
                             str(astatus))
                currenthost = re.search(
                    r'https://(.*?)\.', videomainurl).group(1)
                redirvideourl = videomainurl.replace(currenthost, "redirector")
                rediraudiourl = audiomainurl.replace(currenthost, "redirector")
                videomainurl = session.head(
                    redirvideourl, allow_redirects=True).url + "/"
                audiomainurl = session.head(
                    rediraudiourl, allow_redirects=True).url + "/"
                audiomainurl, astatus = check_url(audiomainurl)
                videomainurl, vstatus = check_url(videomainurl)
        else:
                break
        if tries <= 0:
            print("No more tries, skipping...")
            return 1
    # While End ---
    # Array with all speeds in bps:
    checkavg = head.headers.get('X-Bandwidth-Avg')
    if checkavg:
        Bandwidths = [[int(checkavg) * 8]]
    else:
        Bandwidths = [[0]]
    for Type in 'Est', 'Est2', 'Est3':
        bpstype = head.headers.get('X-Bandwidth-%s' % Type)
        if bpstype is not None:
            Bandwidths.append([int(bpstype)*8])
        else:
            Bandwidths.append([0])
    print("Bandwidths " + str(Bandwidths))
    return (segmentsecs, audiourls, videodata, aid, vid, Bandwidths,
            audiomainurl, videomainurl, buffersecs, earliestseqnum, startnumber)


def get_headseqnum(url):
    h = session.head(url, headers={'Connection': 'close'}, allow_redirects=True)
    if h.status_code == 504:
        headnum = 0
    else:
        hd = h.headers.get('X-Head-Seqnum')
        if hd is not None:
            headnum = int(hd)
        else:
            hd = head.headers.get('X-Head-Seqnum')
            if hd is not None:
                headnum = int(hd)
    h.close()
    return headnum

def cnv(x):
    converted = x
    if x is not None:
        converted = int(x)
    return converted


def get_media(url):
    gettries = 5
    err404tries = 3
    end = 0
    seqnumber = re.search(r'/([0-9]+)', url).group(1)
    while gettries > 0:
        try:
            gettime = time.time()
            timeout = segmentsecs * 3.05
            response = session.get(url, stream=True, timeout=(3.05, timeout),
                                   allow_redirects=False,
                                   headers=rheaders)
            basedelay = round((time.time() - gettime), 4)
            headnumber = cnv(response.headers.get('X-Head-Seqnum'))
            headtime = cnv(response.headers.get('X-Head-Time-Sec'))
            sequencenum = cnv(response.headers.get('X-Sequence-Num'))
            wallclock = cnv(response.headers.get('X-Walltime-Ms'))
            contentlength = cnv(response.headers.get('Content-Length'))
            cachecontrol = response.headers.get('Cache-Control')
            bandwidthavg = cnv(response.headers.get('X-Bandwidth-Avg'))
            bandwidthest = cnv(response.headers.get('X-Bandwidth-Est'))
            bandwidthest2 = cnv(response.headers.get('X-Bandwidth-Est2'))
            bandwidthest3 = cnv(response.headers.get('X-Bandwidth-Est3'))
            # Check status codes:
            status = response.status_code
            contents = 0
            if status == 200:
                print("STATUS URL OK: %s" % (status))
                print("Getting Media Content.....")
                connection = response.connection
                contents = response.content
                response.close()
                return (status, contents, basedelay, headnumber, headtime,
                        sequencenum, wallclock, contentlength, cachecontrol,
                        bandwidthavg, bandwidthest, bandwidthest2,
                        bandwidthest3, connection)
            else:
                response.close()
                gettries -= 1
                if status == 404 or status == 204:
                        logging.info('Error %s, retrying...' % status)
                        time.sleep(segmentsecs)
                        if err404tries <= 0:
                            return 2
                        err404tries -= 1
                elif status == 400:
                    logging.info('Error status: %s, Resyncing...' % status)
                    return 1

                else:
                    print("Error status: %s, refreshing metadata..." % status)
                    return 3
        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ConnectionError) as exception:
            logging.info("Exception: %s retrying..." % exception)
            gettries -= 1
            if gettries <= 0:
                return 1

            time.sleep(segmentsecs*1.1)
        except (requests.exceptions.ReadTimeout, IncompleteRead,
                http.client.IncompleteRead,
                ProtocolError, Exception) as exception:
            if end == 0:
                end += 1
                logging.info("Trassmission maybe ended, retrying...")
                time.sleep(segmentsecs*1.1)
            elif end == 1:
                logging.info("This trassmission has ended...")
                response.connection.close()
                return 2
            if gettries <= 0:
                return 1
            logging.info("Exception: %s retrying..." % exception)
            gettries -= 1


def main():
    arg2 = None
    arg3 = None
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if len(sys.argv) == 3:
            arg2 = sys.argv[2]
        if len(sys.argv) == 4:
            arg3 = sys.argv[3]

        yth = r"http[s]?://(w{3}\.)?youtube.com"
        yths = "http[s]?://youtu.be"
        urlpattern1 = yths + '/[A-z0-9_-]{11}$'
        urlpattern2 = yth + r'/watch\?v=([A0-z9_-]{11}$|[A0-z9_-]{11}&.*$)'
        urlpattern3 = yth + r'/(channel/|user/|playlist\?list\=)[A-z0-9_-]+'
        if re.search(urlpattern1 + "|" + urlpattern2, arg1):
            videourls = [arg1]
            searchurl = None
        elif re.search(urlpattern3, arg1):
            searchurl = arg1
        else:
            searchurl = (
                'https://www.youtube.com/' +
                'results?sp=EgJAAQ%253D%253D&search_query=' + arg1 + "&page=1")
            print("Openning Search URL: " + searchurl)
    else:
        print("No url nor query to open")
        raise NoArgs
    if searchurl is not None:
        try:
            r = requests.get(searchurl)
        except requests.exceptions.ConnectionError:
            print("Connection Error opening Main URL...")
            raise
        soup = BeautifulSoup(r.text, "lxml")
        atags = soup.findAll('a')
        links = []
        for tag in atags:
            link = tag.get('href', None)
            if link is not None:
                if (link[:6] == "/watch" and
                   not re.search(link[-11:], str(links))):
                    links.append("https://www.youtube.com" + link)
        videourls = links
    print("%s ITEMS FOUND." % len(videourls))
    item = 1
    for videourl in videourls:
        if arg2 is not None and item > int(arg2):
            print('All items opened, quitting...')
            return
        print("OPENING ITEM n° %s..." % str(item))
        segmentsoffset = 3
        init = None
        ffmpegbase = None
        player = None
        videodata = None
        vid = None
        ffmpegmuxer = None
        metadata = get_metadata(videourl, 0, 2)
        if metadata == 1:
            item += 1
            continue
        elif metadata == 2:
            break
        else:
            global segmentsecs
            segmentsecs = metadata[0]
            audiourls = metadata[1]
            videodata = metadata[2]
            aid = metadata[3]
            vid = metadata[4]
            Bandwidths = metadata[5]
            BandwidthsAvgs = [0, 1, 2, 3]
            audiomainurl = metadata[6]
            videomainurl = metadata[7]
            buffersecs = metadata[8]
            earliestseqnum = metadata[9]
            startnumber = metadata[10]
            audiomainurls = []
            videomainurls = []
            for ida in range(len(audiourls)):
                audiomainurls.append(0)
            for idv in range(len(videodata)):
                videomainurls.append(0)
            audiomainurls[aid] = audiomainurl
            videomainurls[vid] = videomainurl
        # Opening main FFmpeg and player:
        if segmentsecs >= 5:
            ffmpegbaseargs = shlex.split(
                '''%s -v 0 -analyzeduration %s -thread_queue_size 6500
                -flags +low_delay -i -
                -c copy -f nut -bsf:v h264_mp4toannexb pipe:1''' %
                (ffmpegbin, (int(1000000*segmentsecs))))
            ffmpegbase = subprocess.Popen(ffmpegbaseargs,
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
            playerstdin = ffmpegbase.stdout
            ffmuxerstdout = ffmpegbase.stdin
        else:
            playerstdin = subprocess.PIPE
            ffmuxerstdout = "player.stdin"
        playerargs = shlex.split(playercmd + "--cache-secs=%s" %
                                 int(segmentsecs*3600))

        player = subprocess.Popen(playerargs,
                                  stdin=playerstdin,
                                  stdout=None,
                                  stderr=None)
        logging.info("Total video Qualitys Choosen: " + str(len(videodata)))
        segmresynclimit = buffersecs/segmentsecs
        headnumber = int(head.headers.get('X-Head-Seqnum'))
        if startnumber - earliestseqnum > 0:
            segmresynclimit = startnumber - earliestseqnum
            if segmentsoffset > segmresynclimit:
                segmentsoffset = segmresynclimit - 1
            oldestsegment = earliestseqnum
        elif arg3 is not None:
            if arg3[-1] == "h":
                segmentsoffset = int((float(arg3[0:-1])*3600)/segmentsecs)
                if float(arg3[0:-1]) > 4:
                    logging.info('''The max back buffer hours is %s, playing
                                    from oldest segment available'''
                                 % str(buffersecs/3600))
            elif arg3[-1] == "m":
                segmentsoffset = int((float(arg3[0:-1])*60)/segmentsecs)
                if float(arg3[0:-1]) > 240:
                    logging.info('''The max back buffer minutes is %s, playing
                                 from oldest segment available'''
                                 % str(buffersecs/60))
            elif arg3[-1] == "s":
                segmentsoffset = int(int(arg3[0:-1])/segmentsecs)
                if int(arg3[0:-1]) > buffersecs:
                    logging.info(
                        "The max backbuffer seconds is %s, playing from there" %
                        str(buffersecs))

            elif arg3[-1] <= 9 and arg3[-1] >= 0:
                if int(arg3) >= oldestsegment:
                    segmentsoffset = int(arg3)
                else:
                    logging.info(
                        "The oldest segment to play is %s, playing from there" %
                        str(buffersecs))
            else:
                logging.info('''No valid value entered for third argument,
                                acepted values are, i.e: 2h, 210m or 3000s or
                                152456 for hours, minutes, seconds and number of
                                 segment respectively please retry.''')
            # max Nº of pending segments allowed before forcing resync to oldest
            segmentsoffset = min(segmresynclimit, segmentsoffset, headnumber)
        seqnumber = int(headnumber - segmentsoffset)
        logging.info('HEADNUMBER: %s, SEQNUMBER: %s' % (headnumber, seqnumber))
        # MAIN LOOP: ----------------------------------------------------------#
        delays = [0]
        truedelays = []
        mindelay = 100
        excetries = 5
        totaldelay = 0.0
        global headtimes, headnumbers, wallclocks, basedelays, pool
        # global pheadnumber, headnumber
        pheadnumber = headnumber
        pool = None
        basedelays = []

        remainsegms = int(headnumber - seqnumber)
        retryerrormsg = 'Retries exhausted, transmission probably ended'

        while True:
            print("HEAD NUMBER: %s, SEQNUMBER: %s, REMAINING SEGMENTS:%s" %
                  (headnumber, seqnumber, remainsegms))
            starttime = time.time()
            print("TWO SEGMENTS: %s" % str(twosegmentsdownload))
            if player is not None:
                if player.poll() is not None:
                    print("Player Closed, playing next...")
                    vconn.close()
                    aconn.close()
                    break
            try:
                wallclocks = []
                headnumbers = []
                headtimes = []
                murls = []
                for sid in range(min(remainsegms, maxparalelsemgs)):
                    audiototalurl = audiomainurl + "sq/" + str(
                                                           int(seqnumber + sid))
                    murls.append(audiototalurl)
                    videototalurl = videomainurl + "sq/" + str(
                                                           int(seqnumber + sid))
                    murls.append(videototalurl)
                pool = ThreadPool(len(murls))
                results = pool.imap(get_media, murls)
                pipe1 = os.pipe()
                pipe2 = os.pipe()
                with os.fdopen(pipe1[1], 'wb') as fda:
                    with os.fdopen(pipe2[1], 'wb') as fdv:
                        is_video = 0
                        ffmuxerdelay = 0
                        ffmuxerstarttimer = time.time()
                        if ffmpegmuxer is not None:
                            print("Waiting previous process...")
                            ffmpegmuxer.communicate()
                            ffmpegmuxer.wait()
                        ffmuxerdelay = round(time.time() - ffmuxerstarttimer, 4)
                        ffmpegargs = shlex.split('''%s -thread_queue_size 1024
                                                 -flags +low_delay
                                                 -vsync 0 -i pipe:%s
                                                 -thread_queue_size 1024
                                                 -flags +low_delay
                                                 -fflags +genpts -vsync 0
                                                 -i pipe:%s -c copy
                                                 -f mpegts -copyts
                                                 -bsf:v h264_mp4toannexb
                                                 -flags +low_delay
                                                 -fflags +genpts
                                                 - -y -v 1''' %
                                                 (ffmpegbin, pipe1[0],
                                                  pipe2[0]))
                        if ffmuxerstdout == "player.stdin":
                            ffmuxerstdout = player.stdin
                        ffmpegmuxer = subprocess.Popen(ffmpegargs,
                                                       bufsize=-1,
                                                       stdout=ffmuxerstdout,
                                                       pass_fds=(pipe1[0],
                                                                 pipe2[0]))
                        while ffmpegmuxer.poll() is not None:
                                        print("WAITING FFMPEG TO OPEN...")
                                        if fftries < 5:
                                            time.sleep(1)
                                        else:
                                            raise Exception
                                        fftries += 1
                        for result in results:
                            if result == 1:
                                raise Exception
                            elif result == 2:
                                logging.info(retryerrormsg)
                                reply = str(input("Retry or play Next/Quit?"))
                                if (reply == 'N' or reply == 'n' or
                                   reply == 'q' or reply == 'Q'):
                                        logging.info('Choosen %s' % reply)
                                        if player is not None:
                                            logging.info('Forcing player close')
                                            player.kill()
                                        if reply == 'q' or reply == 'Q':
                                            raise KeyboardInterrupt
                                raise Exception
                            elif result == 3:
                                # Get new host with redirector
                                metadata = get_metadata(videourl, aid, vid)
                                if not metadata == 1:
                                    audiourls = metadata[1]
                                    videodata = metadata[2]
                                    audiomainurl = metadata[6]
                                    videomainurl = metadata[7]
                                break
                            (status, contents, basedelay, headnumber, headtime,
                                sequencenum, wallclock, contentlength,
                                cachecontrol, bandwidthavg, bandwidthest,
                                bandwidthest2, bandwidthest3,
                                connection) = result
                            if headnumber:
                                headnumbers.append(int(headnumber))
                            if headtime:
                                headtimes.append(int(headtime))
                            if wallclock:
                                wallclocks.append(int(wallclock))
                            if status == 200:
                                if basedelay:
                                    basedelays.append(basedelay)
                                if is_video == 1:
                                    vconn = connection
                                    vbytes = fdv.write(contents)
                                    is_video = 0
                                    seqnumber += 1
                                elif is_video == 0:
                                    aconn = connection
                                    is_video = 1
                                    fftries = 0
                                    abytes = fda.write(contents)
                excetries = 5
            # EXCEPTIONS: -----------------------------------------------------#
            except KeyboardInterrupt:
                logging.info("KeyboardInterrupt, cleaning... ")
                ffmpegmuxer.terminate()
                player.kill()
                ffmpegmuxer.wait()
                player.wait()
                raise KeyboardInterrupt
            except (IOError) as exception:
                logging.info("Exception: %s" % exception)
                if excetries <= 0:
                    logging.info('Exception retries exhausted, quitting...')
                    res = str(input("Press Enter to play next item or Quit"))
                    if res is '':
                        vconn.close()
                        aconn.close()
                        logging.info('Trying to play next item if available...')
                        player.kill()
                        break
                    elif res is 'q' or res is 'Q':
                        quit()
                time.sleep(1)
                excetries -= 1
                continue
            finally:
                # fda.close()
                # fdv.close()
                os.close(pipe1[0])
                os.close(pipe2[0])
                # ffmpegmuxer.communicate()
                if pool is not None:
                    print("Killing Threads")
                    pool.terminate()
                    pool.join()
                    print("Threads killed")

            # DELAYS: ---------------------------------------------------------#
            while len(basedelays) > min(segmentsoffset*2, 3*2):
                    del basedelays[0]
            basedelayavg = round(sum(basedelays) / (2 * len(basedelays)), 4)
            mindelay = min(min(basedelays), mindelay)
            totaldelay = round((time.time() - starttime - ffmuxerdelay)*2
                               / len(murls), 4)
            delays.append(round(totaldelay, 4))
            while len(delays) > min(segmentsoffset, 3):
                del delays[0]
            delayavg = round(sum(delays) / min(segmentsoffset, 3), 2)
            truedelay = round(delays[-1] - basedelays[-1], 3)
            truedelayavg = round(delayavg - basedelayavg, 3)
            truedelays.append(truedelay)
            while len(truedelays) > min(segmentsoffset, 3):
                del truedelays[0]
            print("--> BASEDELAYS: " + str(basedelays) + " Seconds ")
            print("--> MIN DELAY: " + str(mindelay) + " Seconds ")
            print("--> DELAYS: " + str(delays) + " Seconds ")
            print("--> LAST DELAYS:: " + str(totaldelay) + " Seconds ")
            print("--> DELAY AVG: " + str(delayavg) + " Seconds ")
            print("--> TRUE DELAYS: %s" % str(truedelays))
            print("--> TRUE DELAY AVG: %s" % str(truedelayavg))
            print("--> FFMPEG DELAYS: %s" % str(ffmuxerdelay))
            threadsc = threading.active_count()
            print("--> Threads Count: %s" % str(threadsc))
            # -----------------------------------------------------------------#

            # BANDWIDTHS: -----------------------------------------------------#
            if bandwidthavg:
                Bandwidths[0].append(int(bandwidthavg) * 8)
            if bandwidthest:
                Bandwidths[1].append(int(bandwidthest) * 8)
            if bandwidthest2:
                Bandwidths[2].append(int(bandwidthest2) * 8)
            if bandwidthest3:
                Bandwidths[3].append(int(bandwidthest3) * 8)
            # Limit subarrays to min segments offset length:
            for i in range(len(Bandwidths)):
                while len(Bandwidths[i]) > min(segmentsoffset, 3):
                    del Bandwidths[i][0]
                BandwidthsAvgs[i] = int(sum(Bandwidths[i]) / len(Bandwidths[i]))
            print("Bandwidth Avg: " + str(Bandwidths[0][-1]) + " bps " +
                  str(int((Bandwidths[0][-1] / 8) / 1024)) + " kB/s")
            print("Bandwidth Est Avg: " +
                  str(int((BandwidthsAvgs[1] / 8) / 1024)) + " kB/s " +
                  "Bandwidth Est Last: " +
                  str(int((Bandwidths[1][-1] / 8) / 1024)) + " kB/s ")
            print("Bandwidth Est2 Avg: " +
                  str(int((BandwidthsAvgs[2] / 8) / 1024)) + " kB/s " +
                  "Bandwidth Est2 Last: " +
                  str(int((Bandwidths[2][-1] / 8) / 1024)) + " kB/s ")
            print("Bandwidth Est3 Avg: " +
                  str(int((BandwidthsAvgs[3] / 8) / 1024)) + " kB/s " +
                  "Bandwidth Est3 Last: " +
                  str(int((Bandwidths[3][-1] / 8) / 1024)) + " kB/s ")
            selectedbandwidth = int(videodata[vid]['bandwidth']) + 124000
            # CHECK TO GO DOWN: -----------------------------------------------#
            if(vid > 0 and ffmuxerdelay < segmentsecs/4 and
               truedelayavg > segmentsecs and truedelays[-1] > segmentsecs):
                        rest = min(int(truedelays[-1] / segmentsecs), vid)
                        if rest > 0:
                            vid -= rest
                        elif rest == 0 or segmentsecs < 5:
                            vid -= 1
                        if videomainurls[vid] != 0:
                            videomainurl = videomainurls[vid]
                        else:
                            videomainurl, vstatus = check_url(
                                videodata[vid].text)
                            if vstatus == 200:
                                videomainurls[vid] = videomainurl
                        logging.info('---> Going DOWN, to VID: %s' % vid)
                        logging.info("BASE DELAYS: %s" % str(basedelays))
                        logging.info("TRUE DELAYS: %s" % truedelays)
                        logging.info("TRUE DELAY AVG: %s" % truedelayavg)
                        logging.info("BASE DELAY AVG: %s" % str(basedelayavg))
                        logging.info('DELAYS: %s' % str(delays))
                        logging.info('DELAY AVG: %s' % str(delayavg))
                        logging.info("MIN DELAY: %s" % str(mindelay))
                        logging.info("FFMUX DELAY: %s" % str(ffmuxerdelay))
                        logging.info('NEW VIDEO URL: %s' % videomainurl)
            # Check remaining segments:
            if headnumbers:
                headnumber = max(headnumbers)
            remainsegms = int(headnumber) - (seqnumber - 1)
            if remainsegms < 0:
                remainsegms = 0
            elif remainsegms > segmresynclimit:
                    seqnumber = get_headseqnum(videomainurl) - segmentsoffset
                    seqnumber += 2
                    logging.info('Resyncing...')
            if mindelay > segmentsecs * 0.75:
                logging.info(
                    'Min delay to high: %s seconds, playback not realistic' %
                    mindelay)
            if remainsegms <= 1 + twosegmentsdownload or remainsegms > 10:
                # Check links expiring (secs remaining)
                if cachecontrol:
                    expiresecs = re.search(
                        'private, max-age=(.*)', cachecontrol)
                    if expiresecs:
                        expiresecs = int(expiresecs.group(1))
                        print('EXPIRING IN %s SECS' % expiresecs)
                    if expiresecs is not None and expiresecs <= 20:
                        logging.info(
                            'URL Expired %s, refreshing metadata.' % expiresecs)
                        metadata = get_metadata(videourl, aid, vid)
                        if metadata == 1:
                            break
                        audiourls = metadata[1]
                        videodata = metadata[2]
                        audiomainurl = metadata[6]
                        videomainurl = metadata[7]
                delaytogoup = max(basedelayavg * 2, mindelay * 3,
                                  segmentsecs / 3)
                elapsed3 = round(time.time() - starttime, 4)
                print("---> TOTAL LOCAL DELAY: " + str(elapsed3))
                # Local wallclock timing:
                timesincedown = round(elapsed3 - basedelays[-1], 4)
                # Wallclock Milisecs from headers:
                timesincedownh = round(
                    (time.time() - (max(wallclocks)/1000)), 4)
                print('WALLCLOCK LOCAL : %s' % timesincedown)
                # CHECK TO GO UP: ---------------------------------------------#
                bandidxC = 2
                bandidxN = 1
                sensup = 3
                if((BandwidthsAvgs[bandidxC] > selectedbandwidth * sensup and
                    Bandwidths[bandidxC][-1] > selectedbandwidth * sensup and
                    BandwidthsAvgs[bandidxN] > selectedbandwidth * sensup and
                    Bandwidths[bandidxN][-1] > selectedbandwidth * sensup) or
                    BandwidthsAvgs[bandidxC] == 0 or
                        BandwidthsAvgs[bandidxN] == 0):
                            bandwidth_ok = True
                else:
                    bandwidth_ok = False
                if (vid < len(videodata) - 1 and ((segmentsecs >= 5 and
                   delayavg < delaytogoup and delays[-1] < delaytogoup and
                   basedelayavg < segmentsecs/2) or
                   (segmentsecs < 5 and bandwidth_ok))):
                        logging.info("Bandwidth to next quality OK: %s" %
                                     bandwidth_ok)
                        if bandwidth_ok:
                            vid += 1
                            if videomainurls[vid] != 0:
                                videomainurl = videomainurls[vid]
                            else:
                                videomainurl, vstatus = check_url(
                                    videodata[vid].text)
                                if vstatus == 200:
                                    videomainurls[vid] = videomainurl
                            logging.info('---> Going UP, to VID: %s' % vid)
                            logging.info("TRUE DELAY: %s" % truedelay)
                            logging.info("BASE DELAYS: %s" % str(basedelays))
                            logging.info('DELAYS: %s' % str(delays))
                            logging.info('DELAY AVG: %s' % str(delayavg))
                            logging.info('SELECTED BAND: %s' % str(
                                selectedbandwidth))
                            logging.info('BANDWIDTH AVG: %s' % str(
                                BandwidthsAvgs[bandidxC]))
                            logging.info('BANDWIDTHNext AVG: %s' % str(
                                BandwidthsAvgs[bandidxN]))
                            logging.info("MIN DELAY: %s" % str(mindelay))
                            logging.info("FFMUX DELAY: %s" % str(ffmuxerdelay))
                            logging.info('WALLCLOCK LOCAL : %s' % timesincedown)
                            logging.info('WALLCLOCK SERVER:%s' % timesincedownh)
                            logging.info('NEW VIDEO URL: %s' % videomainurl)
                if remainsegms == 0:
                    sleepsecs = round(max(segmentsecs - elapsed3, 0), 4)
                    remainsegms += 1 + twosegmentsdownload
                else:
                    sleepsecs = 0
                if sleepsecs:
                    logging.info("Sleeping %s seconds..." % sleepsecs)
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
                time.sleep(sleepsecs)
        item += 1

try:
    with requests.Session() as session:
        session.verify = True
        session.mount('https://', requests.adapters.HTTPAdapter(
                        pool_connections=1000,
                        pool_maxsize=10,
                        max_retries=3))
        main()

except KeyboardInterrupt:
    logging.info("Exit requested by keyboard....")
finally:
    os.closerange(3, 100)
    os.remove('/tmp/dash2.0.pid')
