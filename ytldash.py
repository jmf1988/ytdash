#!/usr/bin/env python
# -*- coding: utf-8 -*-
# pip[2|3] install bs4 lxml pyopenssl requests-futures requests
from bs4 import BeautifulSoup
from requests_futures.sessions import FuturesSession
# from concurrent.futures import ProcessPoolExecutor
import requests
import logging
import os
import signal
import sys
import time
import subprocess
import re
import shlex

try:
    import gtk
    swidth = gtk.gdk.screen_width()
    sheight = gtk.gdk.screen_height()
except ImportError:
    sheight = 720
try:
    with open('/tmp/dash2.0.pid', 'r') as fd:
        prevpid = fd.read()
        try:
            os.killpg(int(prevpid), signal.SIGTERM)
            print("Killed previous instance...")
        except Exception:
            print("Cannot kill process or it does not exist")
except Exception:
    print("No previous process found")
os.setpgrp()
with open('/tmp/dash2.0.pid', 'w') as fd:
    fd.write(str(os.getpgrp()))

ffmpegbin = "/home/jmf/bin/ffmpeg"
audiofilename = "/dev/shm/audio"
ffmpegargs = shlex.split('''%s -v 1 -thread_queue_size 1024 -i %s
    -thread_queue_size 1024 -i pipe:0 -map 0:0 -map 1:0
    -c copy -f mpegts pipe:1''' % (ffmpegbin, audiofilename))

playercmd = """mpv --demuxer-max-back-bytes=10485760 --really-quiet=yes
    --demuxer-max-bytes=10485760 - """
# playercmd = 'mpv -'
maxfps = 60
segmentsoffset = 3
twosegmentsdownload = 0
autoresync = 1  # Drop segments on high delays to keep live

logging.basicConfig(
    level=logging.INFO, filename="logfile", filemode="w+",
    format="%(asctime)-15s %(levelname)-8s %(message)s")

rheaders = {
    # 'Connection': 'close',
    # 'User-Agent': '''Mozilla/5.0 (X11; Linux i686 (x86_64)) AppleWebKit/537.36
    # (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36''',
    # 'Keep-Alive': 'timeout=5'
    }


def ReleaseConn(rm):
    for segment in rm:
        for mediatype in segment:
            mediatype.close()


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
        head = session.head(url, allow_redirects=False)
        status = head.result().status_code
        print("STATUS %s" % status)
        if status == 302:
            url = head.result().headers.get('Location') + "/"
        elif status == 200:
            return (url, status)
        else:
            logging.info("Error checking URL, STATUS: %s" % str(status))
            return (url, status)


def get_metadata(manifestsearch, aid, vid):
    manifesturl = manifestsearch.group(1)
    offline = re.search('force_finished|playback_host', str(manifesturl))
    tries = 10
    refreshman = True
    while tries > 0:
        if not offline and refreshman:
            rawmanifest = session.get(manifesturl.replace('\\', "").replace(
                    'ip/', 'keepalive/yes/ip/'), headers=rheaders)
            if not rawmanifest.result().ok:
                print("Error getting manifest, skipping...")
                return 1
        else:
            print("Live recently ended, skipping..." + manifesturl)
            return 1
        soup3 = BeautifulSoup(rawmanifest.result().content, 'xml')
        segmentsecs = float(soup3.MPD['minimumUpdatePeriod'][2:7])
        print("Segmento segundos: " + str(segmentsecs))
        global sens
        if segmentsecs == 1.000:
            sens = 1
            print('Live mode: ULTRA LOW LATENCY')
            logging.info('Live mode: ULTRA LOW LATENCY')
            twosegmentsdownload = 1
        elif segmentsecs == 2.000:
            sens = 1
            print('Live mode: LOW LATENCY')
            logging.info('Live mode: LOW LATENCY')
        elif segmentsecs == 5.000:
            sens = 0.8
            print('Live mode: NORMAL LATENCY')
            logging.info('Live mode: NORMAL LATENCY')

        audiourls = soup3.MPD.find(
            "AdaptationSet", mimeType="audio/mp4").findAll('BaseURL')
        videodata = soup3.MPD.find(
            "AdaptationSet", mimeType="video/mp4").findAll(
            'Representation',
            frameRate=re.compile("^[0-" + str(maxfps)[:1] + "][0-9]$"),
            bandwidth=True
            )
        # print("VIDEODATA: %s" % videodata)
        videodata.sort(key=Bandwidth)
        idx = 0
        while idx < len(videodata):
            videofps = int(videodata[idx]['frameRate'])
            videoheight = int(videodata[idx]['height'])
            if videofps > maxfps or videoheight > sheight:
                del videodata[idx]
            idx += 1
        aid = aid
        vid = vid
        audiomainurl, astatus = check_url(audiourls[aid].text)
        videomainurl, vstatus = check_url(videodata[vid].text)
        logging.info("AUDIOMAINURL %s" % audiomainurl)
        logging.info("VIDEOMAINURL %s" % videomainurl)
        if (vstatus == 503 or vstatus == 403 or
           astatus == 503 or astatus == 403):
                tries -= 1
                print(
                    "Error Status: %s, trying redirection..."
                    % str(astatus))
                currenthost = re.search(
                    r'https://(.*?)\.', videomainurl).group(1)
                redirvideourl = videomainurl.replace(currenthost, "redirector")
                rediraudiourl = audiomainurl.replace(currenthost, "redirector")
                videomainurl = session.head(
                    redirvideourl, allow_redirects=True).result().url + "/"
                audiomainurl = session.head(
                    rediraudiourl, allow_redirects=True).result().url + "/"
                audiomainurl, astatus = check_url(audiomainurl)
                videomainurl, vstatus = check_url(videomainurl)
                break
        else:
                break
        if tries == 0:
            print("No more tries, skipping...")
            return 1
    # Array with all speeds in bps:
    checkavg = head.result().headers.get('X-Bandwidth-Avg')
    if checkavg:
        Bandwidths = [[int(checkavg) * 8]]
    else:
        Bandwidths = [[0]]
    for Type in 'Est', 'Est2', 'Est3':
        bpstype = head.result().headers.get('X-Bandwidth-%s' % Type)
        if bpstype is not None:
            Bandwidths.append([int(bpstype)*8])
        else:
            Bandwidths.append([0])
    print("Bandwidths " + str(Bandwidths))
    return (
        segmentsecs, audiourls, videodata, aid, vid, Bandwidths,
        audiomainurl, videomainurl)


def get_headseqnum(url):
    h = session.head(url, headers={'Connection': 'close'}, allow_redirects=True)
    if h.result().status_code == 504:
        headnum = 0
    else:
        hd = h.result().headers.get('X-Head-Seqnum')
        if hd is not None:
            headnum = int(hd)
        else:
            hd = head.result().headers.get('X-Head-Seqnum')
            if hd is not None:
                headnum = int(hd)
    h.result().close()
    return headnum


def main():
    arg2 = None
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if len(sys.argv) > 2:
            arg2 = sys.argv[2]
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
                    # print(link)
                    # videourl += link
                    links.append("https://www.youtube.com" + link)
                    # print(videourl)
        videourls = links
    print("%s ITEMS FOUND." % len(videourls))
    item = 1
    for videourl in videourls:
        if arg2 is not None and item > int(arg2):
            print('All items opened, quitting...')
            return
        print("OPENING ITEM n° %s..." % str(item))
        init = None
        ffmpegbase = None
        player = None
        videodata = None
        vid = None
        delays = [0]
        ffmpegmuxer = None
        basedelays = []
        mindelay = 100
        if videourl:
            r = session.get(videourl)
        else:
            print('Could not get video URL, skipping...')
            continue
        soup2 = BeautifulSoup(r.result().text, "lxml")
        manifestsearch = re.search(
            'dashmpd":"(.+?)"', str(soup2.findAll('script')))
        if manifestsearch:
            metadata = get_metadata(manifestsearch, 0, 2)
            if metadata == 1:
                item += 1
                continue
            elif metadata == 2:
                break
            else:
                segmentsecs = metadata[0]
                audiourls = metadata[1]
                videodata = metadata[2]
                aid = metadata[3]
                vid = metadata[4]
                Bandwidths = metadata[5]
                BandwidthsAvgs = [0, 1, 2, 3]
                audiomainurl = metadata[6]
                videomainurl = metadata[7]
                audiomainurls = []
                videomainurls = []
                for ida in range(len(audiourls)):
                    audiomainurls.append(0)
                for idv in range(len(videodata)):
                    videomainurls.append(0)
                audiomainurls[aid] = audiomainurl
                videomainurls[vid] = videomainurl

        else:
            print('Couldn\'t get Manifest or Video isn\'t Live, skipping...')
            continue
        # Opening main FFmpeg and player:
        ffmpegbaseargs = shlex.split(
            '''%s -v 0 -analyzeduration %s -thread_queue_size 1024
            -flags +low_delay -i pipe:0
            -c copy -f nut -bsf:v h264_mp4toannexb pipe:1''' %
            (ffmpegbin, (1000000*segmentsecs))
            )
        playerargs = shlex.split(playercmd)
        ffmpegbase = subprocess.Popen(ffmpegbaseargs,
                                      stdin=subprocess.PIPE,
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE)
        player = subprocess.Popen(playerargs,
                                  stdin=ffmpegbase.stdout,
                                  stdout=None,
                                  stderr=None)
        ffmpegbase.stdout.close()
        if ffmpegbase.poll() is not None:
            print('Error openning main ffmpeg, quitting...')
            session.close()
            quit()
        print("Total video Qualitys: " + str(len(videodata)))
        logging.info("Total video Qualitys: " + str(len(videodata)))
        headnumber = head.result().headers.get('X-Sequence-Num')
        # get_headseqnum(audiomainurl)
        if headnumber:
            seqnumber = int(headnumber) - segmentsoffset + 1
            logging.info(
                'HEADNUM: %s, SEQNUMBER: %s' %
                (headnumber, seqnumber))
        else:
            print('Could not get Head number, skipping...')
            continue
        # Main loop:
        while True:
            print("TWO SEGMENTS: %s" % twosegmentsdownload)

            if player is not None:
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
            audiourl = audiomainurl + "sq/" + str(seqnumber)
            videourl = videomainurl + "sq/" + str(seqnumber)
            try:
                starttime = time.time()
                ra = session.get(
                     audiourl, stream=True, timeout=(
                        3.05, 6),
                     allow_redirects=False, headers=rheaders)
                rv = session.get(
                     videourl, stream=True, timeout=(
                        3.05, 6),
                     allow_redirects=False, headers=rheaders)
                if twosegmentsdownload == 1:
                    audiourl2 = audiomainurl + "sq/" + str(seqnumber + 1)
                    videourl2 = videomainurl + "sq/" + str(seqnumber + 1)
                    ra2 = session.get(
                        audiourl2, stream=True, timeout=(3.05, 6),
                        allow_redirects=True, headers=rheaders)
                    rv2 = session.get(
                        videourl2, stream=True, timeout=(3.05, 6),
                        allow_redirects=True, headers=rheaders)
                    print("VID: " + str(vid) + " Selected ")
                    rm = [[
                        ra.result(), rv.result()], [ra2.result(), rv2.result()]]
                else:
                    rm = [[ra.result(), rv.result()]]

                basedelays.append(round((time.time() - starttime)/len(rm), 4))
                if len(basedelays) > segmentsoffset:
                    del basedelays[0]
                basedelayavg = round(sum(basedelays) / len(basedelays), 4)
                mindelay = min(min(basedelays), mindelay)
                print("---> BASEDELAYS: " + str(basedelays) + " Seconds ")
                print("---> MIN DELAY: " + str(mindelay) + " Seconds ")
                cont = False
                wallclocks = []
                headnumbers = []
                headtimes = []
                totaldelay = 0.0
                tries = 0
                for segment in rm:
                    for mtype in range(2):
                        headnumber = segment[mtype].headers.get('X-Head-Seqnum')
                        if headnumber:
                            headnumbers.append(int(headnumber))
                        headtimes.append(segment[mtype].headers.get(
                                'X-Head-Time-Sec'))
                        sequencenum = segment[mtype].headers.get(
                                'X-Sequence-Num')
                        wallclocks.append(float(
                            segment[mtype].headers.get('X-Walltime-Ms')
                            ))
                        # Check status codes:
                        status = segment[mtype].status_code
                        if status == 200:
                            print("STATUS URL OK: %s" % (status))
                        elif status == 404 or status == 204:
                                    segment[mtype].close()
                                    if ffmpegmuxer.poll() is None:
                                        ffmpegmuxer.kill()
                                    print('Error 404,retrying in 1 second...')
                                    logging.info(
                                        'Error 404,retrying in 1 second...')
                                    tries += 1
                                    time.sleep(1)
                                    if tries >= 3:
                                        tries = 0
                                        print(
                                            '''Transmission ended, waiting
                                            player...''')
                                        if player is not None:
                                            player.wait()
                                            cont = True
                                    break
                        elif status > 400 or status == 302:
                                print(
                                    "Error status: %s, refreshing metadata..."
                                    % status)
                                # Get new host with redirector
                                metadata = get_metadata(
                                    manifestsearch, aid, vid)
                                audiourls = metadata[1]
                                videodata = metadata[2]
                                audiomainurl = metadata[6]
                                videomainurl = metadata[7]
                                cont = True
                                break
                    with open(audiofilename, 'wb') as fd:
                        '''for chunk in segment[0].iter_content(
                                chunk_size=512):
                                    fd.write(chunk)
                        '''
                        fd.write(segment[0].content)
                    if ffmpegmuxer is not None:
                        print("Waiting previous process...")
                        ffmpegmuxer.communicate()
                        ffmpegmuxer.wait()
                    '''
                    while player.poll()is not None:
                        print('Waiting player...')
                        time.sleep(1)
                    '''
                    tries = 0
                    # Open ffmpeg to mux to pipe from pipe:
                    ffmpegmuxer = subprocess.Popen(ffmpegargs,
                                                   bufsize=-1,
                                                   stdin=subprocess.PIPE,
                                                   stdout=ffmpegbase.stdin)
                    while ffmpegmuxer.poll() is not None:
                        print("WAITING FFMPEG TO OPEN...")
                        if tries < 5:
                            time.sleep(1)
                        else:
                            cont = True
                            break
                        tries += 1
                    print("Writing....")
                    print("PRECHUNKS")
                    ffmpegmuxer.stdin.write(segment[1].content)
                    print("PRECOMMUNICATE")
                    # Next segment:
                    seqnumber += 1
                if cont:
                    cont = False
                    continue
            except requests.exceptions.ConnectionError:
                print("Connection Error Exception")
                logging.info("Connection Error Exception")
                ReleaseConn(rm)
                time.sleep(segmentsecs)
                continue
            except requests.exceptions.ChunkedEncodingError as exception:
                print("Chunked Encoding Error Exception, %s" % exception)
                logging.info("Chunked Encoding Error Exception, %s" % exception)
                ReleaseConn(rm)
            except requests.exceptions.ReadTimeout:
                print("Connection ReadTimeout Exception")
                logging.info("Connection ReadTimeout Exception")
                ReleaseConn(rm)
            except IOError:
                print("IOError Exception")
                logging.info("IOError Exception")
                ReleaseConn(rm)
            # Delays:
            totaldelay = round((time.time() - starttime) / len(rm), 4)
            print("---> TOTAL DELAY: " + str(totaldelay) + " Seconds ")
            delays.append(round(totaldelay, 4))
            if len(delays) > segmentsoffset:
                del delays[0]
            delayavg = round(sum(delays) / segmentsoffset, 2)
            print("---> Delays " + str(delays))
            print("---> Delay Avg: " + str(delayavg))
            BandwidthAvg = rm[-1][1].headers.get('X-Bandwidth-Avg')
            if BandwidthAvg:
                Bandwidths[0].append(int(BandwidthAvg) * 8)
            print("Avg Bandwidth: " + str(Bandwidths[0][-1]) + " bps " +
                  str(int((Bandwidths[0][-1] / 8) / 1024)) + " kB/s")
            # Update bandwidths:
            bid = 1
            for Type in 'Est', 'Est2', 'Est3':
                BandwidthE = rm[-1][1].headers.get(
                    'X-Bandwidth-%s' % (Type))
                if BandwidthE:
                    Bandwidths[bid].append(int(BandwidthE) * 8)
                bid += 1
            # Limit subarrays to segments offset length:
            for i in range(len(Bandwidths)):
                while len(Bandwidths[i]) > segmentsoffset:
                    del Bandwidths[i][0]
                BandwidthsAvgs[i] = int(sum(Bandwidths[i]) / len(Bandwidths[i]))
            print(
                  "Bandwidth Est Avg: " + str(BandwidthsAvgs[1]) + " bps "
                  + str(int((BandwidthsAvgs[1] / 8) / 1024)) + " kB/s")
            print(
                  "Bandwidth Est2 Avg: " + str(BandwidthsAvgs[2]) + " bps "
                  + str(int((BandwidthsAvgs[2] / 8) / 1024)) + " kB/s")
            print(
                  "Bandwidth Est3 Avg: " + str(BandwidthsAvgs[3]) + " bps "
                  + str(int((BandwidthsAvgs[3] / 8) / 1024)) + " kB/s")
            # Check to go down:
            selectedbandwidth = int(videodata[vid]['bandwidth']) + 124000
            if(vid > 0 and delayavg > segmentsecs + basedelays[-1] and
                round(basedelays[-1], 1) < segmentsecs*0.7 and
                round(delays[-1], 1) > segmentsecs + 0.2 and
                    delays[-1] < segmentsecs * segmentsoffset * 3):
                        bandwidth_ok = False
                        print("Bandwidth to Down OK: %s" % bandwidth_ok)
                        logging.info("Bandwidth to Down OK: %s" % bandwidth_ok)
                        if not bandwidth_ok:
                            rest = int(delays[-1] / segmentsecs)
                            if rest > vid:
                                rest = vid
                            vid -= rest
                            if videomainurls[vid] != 0:
                                videomainurl = videomainurls[vid]
                            else:
                                videomainurl, vstatus = check_url(
                                    videodata[vid].text)
                                if vstatus == 200:
                                    videomainurls[vid] = videomainurl
                            logging.info('Going DOWN, to VID: %s' % vid)
                            logging.info("BASE DELAYS: %s" % str(basedelays))
                            logging.info(
                                "BASE DELAY AVG: %s" % str(basedelayavg))
                            logging.info('DELAYS: %s' % str(delays))
                            logging.info('DELAY AVG: %s' % str(delayavg))
                            logging.info("MIN DELAY: %s" % str(mindelay))
                            logging.info('NEW VIDEO URL: %s' % videomainurl)
            # Check remaining segments:
            if headnumbers:
                headnumber = max(headnumbers)
            remainsegms = headnumber - (seqnumber - 1)
            if remainsegms < 0:
                remainsegms = 0
            elif remainsegms > segmentsoffset and autoresync == 1:
                seqnumber = get_headseqnum(videomainurl)
                print('Resyncing...')
                logging.info('Resyncing...')
                ReleaseConn(rm)
            print(
                "HEAD NUMBER: %s, SEQNUMBER: %s, REMAINING SEGMENTS:%s"
                % (headnumber, seqnumber, remainsegms))
            if mindelay > segmentsecs * 0.75:
                logging.info(
                    'Min delay to high: %s seconds, playback not realistic' %
                    mindelay)
                print(
                    'Min delay to high: %s seconds, playback not realistic' %
                    mindelay)
            if remainsegms <= len(rm) - 1:
                # Check links expiring (secs remaining)
                cachecontrol = rm[-1][1].headers.get('Cache-Control')
                if cachecontrol:
                    expiresecs = re.search(
                        'private, max-age=(.*)', cachecontrol)
                    if expiresecs:
                        expiresecs = int(expiresecs.group(1))
                        print('EXPIRING IN %s SECS' % expiresecs)
                    if expiresecs is not None and expiresecs <= 20:
                        logging.info(
                            'URL Expired %s, refreshing metadata.' % expiresecs)
                        metadata = get_metadata(manifestsearch, aid, vid)
                        audiourls = metadata[1]
                        videodata = metadata[2]
                        audiomainurl = metadata[6]
                        videomainurl = metadata[7]
                sen = (6 - vid)
                if sen < 2:
                    sen = 2
                delaytogoup = max(mindelay * sen, segmentsecs/2)
                elapsed3 = round(time.time() - starttime, 4)
                print("---> DELAY3 (2 segments + ffmpeg): " + str(elapsed3))
                # Local wallclock timing:
                timesincedown = round(elapsed3 - basedelays[-1], 4)
                # Wallclock Milisecs from headers:
                timesincedownh = round(
                    (time.time() - (max(wallclocks)/1000)), 4)
                print('WALLCLOCK LOCAL : %s' % timesincedown)
                print('WALLCLOCK SERVER: %s' % timesincedownh)
                # Check to get more video quality :
                delaytogoup = segmentsecs * 0.7
                if (vid < len(videodata) - 1 and
                    delayavg < delaytogoup and
                    delays[-1] < delaytogoup and
                        basedelayavg < segmentsecs/2):
                        bandidx = int((2 + vid) / 2)
                        bandidxN = bandidx + 1
                        if bandidxN >= len(BandwidthsAvgs):
                            bandidxN = len(BandwidthsAvgs) - 1
                        if ((BandwidthsAvgs[bandidx] >
                           selectedbandwidth * 2.5 and
                           BandwidthsAvgs[bandidxN] >
                           selectedbandwidth * 2.5) and
                           (BandwidthsAvgs[0] > selectedbandwidth * 2 or
                           BandwidthsAvgs[0] == 0)):
                                bandwidth_ok = True
                        else:
                            bandwidth_ok = False
                        print("Bandwidth to Up OK: %s" % bandwidth_ok)
                        logging.info("Bandwidth to Up OK: %s" % bandwidth_ok)
                        if bandwidth_ok:
                            print("Getting more video quality...")
                            vid += 1
                            if videomainurls[vid] != 0:
                                videomainurl = videomainurls[vid]
                            else:
                                videomainurl, vstatus = check_url(
                                    videodata[vid].text)
                                if vstatus == 200:
                                    videomainurls[vid] = videomainurl
                            logging.info('Going UP, to VID: %s' % vid)
                            logging.info("BASE DELAYS: %s" % str(basedelays))
                            logging.info('DELAYS: %s' % str(delays))
                            logging.info('DELAY AVG: %s' % str(delayavg))
                            logging.info('SELECTED BAND: %s' % str(
                                selectedbandwidth))
                            logging.info('BANDWIDTH AVG: %s' % str(
                                BandwidthsAvgs[bandidx]))
                            logging.info('BANDWIDTHNext AVG: %s' % str(
                                BandwidthsAvgs[bandidxN]))
                            logging.info("MIN DELAY: %s" % str(mindelay))
                            logging.info('WALLCLOCK LOCAL : %s' % timesincedown)
                            logging.info('WALLCLOCK SERVER:%s' % timesincedownh)
                            logging.info('NEW VIDEO URL: %s' % videomainurl)
                if twosegmentsdownload == 1:
                    sleepsecs = ((len(rm) * segmentsecs) - (
                                    (remainsegms * segmentsecs) +
                                    (elapsed3 * sens)))
                else:
                    if remainsegms == 0:
                        sleepsecs = segmentsecs - elapsed3
                    else:
                        sleepsecs = 0
                if sleepsecs < 0:
                    sleepsecs = 0
                else:
                    prevsleepsecs = 0
                # for times in range(times):
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
                print("Sleeping %s seconds..." % str(round(sleepsecs, 3)))
                logging.info(
                    "Sleeping %s seconds..." % str(round(sleepsecs, 3)))
                time.sleep(round(sleepsecs, 3))
        # After for:
        ReleaseConn(rm)
        item += 1


with FuturesSession(max_workers=10) as session:
    session.mount(
        'https://', requests.adapters.HTTPAdapter(
            pool_connections=1000, pool_maxsize=1000, max_retries=50))
    main()

