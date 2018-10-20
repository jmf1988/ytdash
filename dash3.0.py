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
# import socket
# problematic server https://r3---sn-j5c5nx-5x2e.googlevideo.com
# REdirector: https://redirector.googlevideo.com/videoplayback?live=1&aitags=133%2C134%2C135%2C136%2C160%2C298&ipbits=0&cmbypass=yes&compress=yes&noclen=1&mime=video%2Fmp4&itag=160&id=IdpLV9vsWho.0&signature=C7BC51C59DD7BB41721053DBCCE64F8B4C71F7B6.0468CF83C66F16A525E6A01968383799C4C5A19F&key=yt6&ip=190.114.233.229&expire=1532343596&mv=m&cmpl=1&mt=1532321955&ms=lv&ei=zGBVW46pFMOtwwTkn4n4CQ&mn=sn-j5c5nx-5x2e&mm=32&keepalive=yes&requiressl=yes&c=WEB&gcr=ar&sparams=aitags%2Ccmbypass%2Ccompress%2Cei%2Cgcr%2Cgir%2Chang%2Cid%2Cinitcwndbps%2Cip%2Cipbits%2Citag%2Ckeepalive%2Clive%2Cmime%2Cmm%2Cmn%2Cms%2Cmv%2Cnoclen%2Cpl%2Crequiressl%2Csource%2Cexpire&hang=1&pl=24&source=yt_live_broadcast&initcwndbps=232500&gir=yes&alr=yes&cpn=iL53FIKa687Ci00q&cver=2.20180719&cmo=pf=1&range=0-4095&rn=2&rbuf=0 # noqa
# redirector2: https://redirector.googlevideo.com/videoplayback?source=yt_live_broadcast&live=1&mm=32&expire=1532391235&ei=4xpWW5eLC8SGxwTpt6zYDQ&gcr=ar&keepalive=yes&noclen=1&signature=66CAC6A1B0C2AFB907E096154DD5CA056BE48185.2348B91500684A5F925A5923114AC7ADA92F1E76&requiressl=yes&ms=lv&sparams=aitags%2Ccmbypass%2Cei%2Cgcr%2Cgir%2Chang%2Cid%2Cip%2Cipbits%2Citag%2Ckeepalive%2Clive%2Cmime%2Cmm%2Cmn%2Cms%2Cmv%2Cnoclen%2Cpl%2Crequiressl%2Csource%2Cexpire&mt=1532368960&mv=u&mime=video%2Fmp4&id=Cp4L7wRT3Sw.0&pl=24&aitags=133%2C134%2C135%2C136%2C137%2C160%2C298%2C299&gir=yes&cmbypass=yes&ip=190.114.233.229&mn=sn-uxax4vopj55gb-x1xs&ipbits=0&itag=133&c=WEB&key=yt6&hang=1&alr=yes&cpn=Tp-3t-AhPOj5c0Gd&cver=2.20180719&cmo=pf=1&sq=7215&rn=378&rbuf=2087 # noqa
"""
A24:
https://www.youtube.com/watch?v=LrHM-kZ39Cc
tren:
https://www.youtube.com/channel/UCUPn5IEQugMf_JeNJOV9p2A
tn:
https://www.youtube.com/channel/UCj6PcyLvpnIRT_2W_mwa9Aw
            """
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
'''
import tkinter
root = tkinter.Tk()
swidth = root.winfo_screenwidth()
sheight = root.winfo_screenheight()
try:
    from BeautifulSoup import BeautifulSoup
except ImportError:
    from bs4 import BeautifulSoup
'''

ffmpegbin = "ffmpeg-nohttp"
playercmd = """mpv7 -"""
# --demuxer-max-back-bytes=10485760 --really-quiet=yes --demuxer-max-bytes=10485760
# playercmd = 'mpv -'
maxfps = 30
segmentsoffset = 3
twosegmentsdownload = 0
audiofilename = "/dev/shm/audio"

logging.basicConfig(
    level=logging.INFO, filename="logfile", filemode="w+",
    format="%(asctime)-15s %(levelname)-8s %(message)s")
rheaders = None
"""
rheaders = {
    'Connection': 'close',
    'User-Agent': '''Mozilla/5.0 (X11; Linux i686 (x86_64)) AppleWebKit/537.36
    (KHTML, like Gecko) Chrome/67.0.3396.87 Safari/537.36'''
        }
"""
rheaders = {
    # 'Connection': 'close',
    'Origin': 'https://www.youtube.com',
    'Referer': 'https://www.youtube.com/',
    # 'Keep-Alive': 'timeout=5'
    }
# host = "localhost"
# aport = 5560
# vport = 5561
# udpa = "udp://" + host + ":" + str(aport)
# udpv = "udp://" + host + ":" + str(vport)
# tcpa = "tcp://" + host + ":" + str(aport)
# tcpv = "tcp://" + host + ":" + str(vport)
# s = socket.socket(
#    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
# s.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_LOOP, 1)
# s = socket.socket(
#    socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
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


"""
def bg_cb(sess, resp):
    # parse the json storing the result on the response object
    resp.data = resp.content
"""


def get_metadata(manifestsearch, aid, vid):
    manifesturl = manifestsearch.group(1)
    offline = re.search('force_finished|playback_host', str(manifesturl))
    tries = 10
    refreshman = True
    while tries > 0:
        if not offline and refreshman:
            # rheaders['Referer'] = videourl
            rawmanifest = session.get(manifesturl.replace('\\', "").replace(
                    'ip/', 'keepalive/yes/ip/'), headers=rheaders)
            if not rawmanifest.result().ok:
                print("Error getting manifest, skipping...")
                return 1
            # rheaders['Referer'] = "https://www.youtube.com/"
            '''
            rawmanifest = session.get(
            manifesturl.replace('\\', ""), headers=rheaders)
            '''
        else:
            print("Live recently ended, skipping..." + manifesturl)
            return 1
        soup3 = BeautifulSoup(rawmanifest.result().content, 'xml')
        segmentsecs = float(soup3.MPD['minimumUpdatePeriod'][2:7])
        print("Segmento segundos: " + str(segmentsecs))
        if segmentsecs == 1.000:
            print('Live mode: ULTRA LOW LATENCY')
            logging.info('Live mode: ULTRA LOW LATENCY')
            twosegmentsdownload = 0
        elif segmentsecs == 2.000:
            print('Live mode: LOW LATENCY')
            logging.info('Live mode: LOW LATENCY')
        elif segmentsecs == 5.000:
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
        audiomainurl = audiourls[aid].text
        videomainurl = videodata[vid].text
        ha = session.get(audiomainurl, allow_redirects=True)
        status = ha.result().status_code
        if status == 503 or status == 403:
            tries -= 1
            print(
                "Error Status: %s, trying redirection..."
                % status)
            currenthost = re.search(
                'https://(.*?)\.', videomainurl).group(1)
            redirvideourl = videomainurl.replace(currenthost, "redirector")
            rediraudiourl = audiomainurl.replace(currenthost, "redirector")
            videomainurl = session.head(
                redirvideourl, allow_redirects=True).result().url + "/"
            audiomainurl = session.head(
                rediraudiourl, allow_redirects=True).result().url + "/"
            break
            '''
            tries -= 1
            # Get new host with redirector
            currenthost = re.search(
                'https://(.*?)\.', videomainurl).group(1)
            while not requests.head(videomainurl, allow_redirects=True).ok:
                if re.search(currenthost, videomainurl):
                    vredirurl = videomainurl.replace(currenthost, "redirector")
                    aredirurl = audiomainurl.replace(currenthost, "redirector")
                    getnewaurl = requests.get(
                        aredirurl, allow_redirects=False,
                        headers={'Host': 'redirector.googlevideo.com'})
                    getnewvurl = requests.get(
                        vredirurl, allow_redirects=False,
                        headers={'Host': 'redirector.googlevideo.com'})
                    videomainurl = getnewvurl.headers.get('Location')
                    audiomainurl = getnewaurl.headers.get('Location')
                    print("NEW Video URL: %s" % videomainurl)
                else:
                    break
                print('Sleeping 5 seconds...')
                time.sleep(5)
            hv = requests.head(videomainurl, allow_redirects=False)
            ha = requests.head(audiomainurl, allow_redirects=False)
            status = hv.status_code
            if status == 302:
                videomainurl = hv.headers['Location']
                audiomainurl = ha.headers['Location']
                break
            if status == 200:
                break
            '''
        else:
            break
        if tries == 0:
            print("No more tries, skipping...")
            return 1
    ha = session.head(audiomainurl)
    '''
    headnum = ha.result().headers.get('X-Head-Seqnum')
    if headnum:
        seqnumber = int(headnum) - segmentsoffset
        print('HEADNUM: %s, SEQNUMBER: %s' % (headnum, seqnumber))
    else:
        print('Could not get Head number, skipping...')
        return 1
    '''
    # checkavg = h.headers.get('X-Bandwidth-Avg')
    # Array with all speeds in bps:
    checkavg = ha.result().headers.get('X-Bandwidth-Avg')
    if checkavg:
        Bandwidths = [[int(checkavg) * 8]]
    else:
        Bandwidths = [[0]]
    for Type in 'Est', 'Est2', 'Est3':
        bpstype = ha.result().headers.get('X-Bandwidth-%s' % Type)
        if bpstype is not None:
            Bandwidths.append([int(bpstype)*8])
    print("Bandwidths " + str(Bandwidths))
    return (
        segmentsecs, audiourls, videodata, aid, vid, Bandwidths,
        audiomainurl, videomainurl)


def get_headseqnum(url):
    h = session.head(url, headers={'Connection': 'close'}, allow_redirects=True)
    if h.result().status_code == 504:
        headnum = 0
    else:
        headnum = int(h.result().headers.get('X-Head-Seqnum'))
    h.result().close()
    return headnum
    # audiomainurl.replace('keepalive/yes/ip/', 'ip/'),
    # headers={'Connection': 'close'}, allow_redirects=True
    # )


def main():
    # a = requests.adapters.HTTPAdapter(max_retries=13)
    # session.mount('https://', a)
    arg2 = None
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        if len(sys.argv) > 2:
            arg2 = sys.argv[2]
        yth = "http[s]?://(w{3}\.)?youtube.com"
        yths = "http[s]?://youtu.be"
        urlpattern1 = yths + '/[A-z0-9_-]{11}$'
        urlpattern2 = yth + '/watch\?v=([A0-z9_-]{11}$|[A0-z9_-]{11}&.*$)'
        urlpattern3 = yth + '/(channel/|user/|playlist\?list\=)[A-z0-9_-]+'
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
    # print(str(links))
    # Main for loop:
    # session = requests.Session()
    # session.verify = True
    print("%s ITEMS FOUND." % len(videourls))
    # global session
    # session = requests.Session()
    # session = FuturesSession(max_workers=10)
    # session.mount('https://', requests.adapters.HTTPAdapter(
    # pool_connections=1000, pool_maxsize=1000, max_retries=50))
    item = 1
    for videourl in videourls:
        # print('Args: %s' % sys.argv[2])
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
        # session = FuturesSession(max_workers=10)

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
            # print(metadata)
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
                # seqnumber = metadata[5] + 2
                Bandwidths = metadata[5]
                BandwidthsAvgs = [0, 1, 2, 3]
                audiomainurl = metadata[6]
                videomainurl = metadata[7]
        else:
            print('Couldn\'t get Manifest or Video isn\'t Live, skipping...')
            continue

        '''
        videourls = soup3.MPD.find("AdaptationSet", mimeType="video/mp4").findAll('BaseURL')
        # Sort bandwidths:
        vurls[0], vurls[1], vurls[2], vurls[3] = vurls[3], vurls[0], vurls[1], vurls[2]
        urls = soup3.MPD.findAll('BaseURL')
        audiomainurl = str(urls[0]).replace('<BaseURL>', "").replace('</BaseURL>', "")
        videomainurl = str(urls[2]).replace('<BaseURL>', "").replace('</BaseURL>', "")
        while soup.findAll('a')[i]['href']:
        for i in range(50):
            if str(soup.findAll('a')[i]['href'])[:6] == "/watch":soup.findAll('a')[i]['href']  # noqa
        rawmanifest = requests.get(manifest)
        rawxml=BeautifulSoup(rawmanifest.text, 'xml')
        rawxml.MPD.Representation
        pipenin, pipeout = os.pipe()
        pipenin2, pipeout2 = os.pipe()
        os.spawnl(os.P_NOWAIT, '/home/jmf/ffmpeg13 -v 0 -follow 1 -i /home/jmf/fifo -c copy -f nut -|/home/jmf/mpv4 - >&/dev/null')  # noqa
        ffm = os.system(
            '( %s -v 0 -follow 1 -i %s -c copy -f nut -|%s 1>/dev/null ) &'
            % (ffmpegbin, fifofile, playercmd))
        if ffm > 0:
            print("Error openning player, Error: " + ffm + " ,quitting...")
            quit()
        '''

        """
        udpa = "udp://" + host + ":" + str(aport)
        udpv = "udp://" + host + ":" + str(vport)
        ffmpegbaseargs = shlex.split(
             '''%s -y -v 255 -thread_queue_size 1024 -flags +low_delay
             -overrun_nonfatal 1 -i %s
             -thread_queue_size 1024 -flags +low_delay -overrun_nonfatal 1
             -i %s -c copy -f mpegts ->>out.ts''' %
             (ffmpegbin, udpa, udpv)
             )
        """
        # Opening main FFmpeg and player:
        ffmpegbaseargs = shlex.split(
            '''%s -v 0 -analyzeduration %s -thread_queue_size 1024
            -flags +low_delay -i pipe:0
            -c copy -f nut -bsf:v h264_mp4toannexb pipe:1''' %
            (ffmpegbin, (1000000*segmentsecs))
            )
        playerargs = shlex.split(playercmd)
        ffmpegbase = subprocess.Popen(
            ffmpegbaseargs, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        player = subprocess.Popen(
                playerargs, stdin=ffmpegbase.stdout, stdout=None, stderr=None)
        # player = None
        ffmpegbase.stdout.close()
        if ffmpegbase.poll() is not None:
            print('Error openning main ffmpeg, quitting...')
            session.close()
            quit()
        print("Total video Qualitys: " + str(len(videodata)))
        headnumber = get_headseqnum(audiomainurl)
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
            if player is not None:
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
            # audiourl = audiomainurl
            # videourl = videomainurl
            audiourl = audiomainurl + "sq/" + str(seqnumber)
            videourl = videomainurl + "sq/" + str(seqnumber)
            # +str(seqnumber)
            # for Type in audiomainurl, videomainurl:

            try:
                # socka = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                # sockv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                starttime = time.time()
                ra = session.get(
                     audiourl, stream=False, timeout=(
                        3.05, 6),
                     allow_redirects=True, headers=rheaders)
                '''
                if init is None:
                    time.sleep(5)
                    init = 1
                '''
                rv = session.get(
                     videourl, stream=True, timeout=(
                        3.05, 6),
                     allow_redirects=True, headers=rheaders)
                '''
                if init is None:
                    time.sleep(5)
                    init = 1
                '''
                if twosegmentsdownload == 1:
                    audiourl2 = audiomainurl + "sq/" + str(seqnumber + 1)
                    videourl2 = videomainurl + "sq/" + str(seqnumber + 1)
                    ra2 = session.get(
                        audiourl2, stream=False, timeout=(3.05, 6),
                        allow_redirects=True, headers=rheaders)
                    rv2 = session.get(
                        videourl2, stream=True, timeout=(3.05, 6),
                        allow_redirects=True, headers=rheaders)
                    # rm = grequests.map(murls, size=2)
                    print("VID: " + str(vid) + " Selected ")
                    rm = [[
                        ra.result(), rv.result()], [ra2.result(), rv2.result()]]
                else:
                    rm = [[ra.result(), rv.result()]]

                basedelays.append(round((time.time() - starttime)/len(rm), 4))
                if len(basedelays) > segmentsoffset:
                    del basedelays[0]
                basedelayavg = sum(basedelays) / len(basedelays)
                mindelay = min(min(basedelays), mindelay)
                # starttimec = time.clock()
                print("---> DELAY1: " + str(basedelays) + " Seconds ")
                print("---> MIN DELAY: " + str(mindelay) + " Seconds ")
                # print('HEADERS' + str(rm[1][1].headers))
                # print('REQUESTHEADERS' + str(rm[1][1].request.headers))
                # lanza player if no error:
                """
                if init is None:
                    player = subprocess.Popen(playerargs,
                    stdin=ffmpegbase.stdout, stdout=None, stderr=None)
                    init = 2
                """
                cont = False
                wallclocks = []
                headnumbers = []
                headtimes = []
                totaldelay = 0.0
                tries = 0
                for segment in rm:
                    for Mtype in range(2):
                        headnumber = segment[Mtype].headers.get('X-Head-Seqnum')
                        if headnumber:
                            headnumbers.append(int(headnumber))
                        headtimes.append(segment[Mtype].headers.get(
                                'X-Head-Time-Sec'))
                        sequencenum = segment[Mtype].headers.get(
                                'X-Sequence-Num')
                        wallclocks.append(float(
                            segment[Mtype].headers.get('X-Walltime-Ms')
                            ))
                        # Check status codes:
                        status = segment[Mtype].status_code
                        if status == 200:
                            print("STATUS URL OK: %s" % (status))
                            '''
                            history = segment[Mtype].history
                            if history == 302:
                                audiomainurl = segment[0].url
                                videomainurl = segment[1].url
                            '''
                        elif status == 404 or status == 204:
                                    segment[Mtype].close()
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
                        elif status > 400 or status >= 302:
                                print(
                                    "Error status: %s, refreshing metadata..."
                                    % status)
                                # Get new host with redirector
                                metadata = get_metadata(
                                    manifestsearch, aid, vid)
                                audiourls = metadata[1]
                                videodata = metadata[2]
                                audiomainurl = metadata[7]
                                videomainurl = metadata[8]
                                cont = True
                                break
                    # starttime2 = time.time()
                    # print('Segment' + str(segment))
                    # socka = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    # sockv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    ffmpegargs = shlex.split(
                        '''%s -v 1 -thread_queue_size 1024 -i %s
                         -thread_queue_size 1024 -i pipe:0 -map 0:0 -map 1:0
                         -c copy -f mpegts pipe:1'''
                        % (ffmpegbin, audiofilename)
                         )
                    # print('PLAYER ARGS:' + str(ffmpegargs))

                    # for chunk in segment[0].iter_content(chunk_size=None):
                    #    fd.write(chunk)

                    # ffmpegmuxer.kill()
                    # ffmpegmuxer.communicate()
                    # ffmpegmuxer.wait()
                    with open(audiofilename, 'wb') as fd:
                        '''for chunk in segment[0].iter_content(
                                chunk_size=512):
                                    fd.write(chunk)
                        '''
                        fd.write(segment[0].content)
                    # segment[0].close()
                    if ffmpegmuxer is not None:
                        print("Waiting previous process...")
                        ffmpegmuxer.communicate()
                        ffmpegmuxer.wait()
                    '''
                    while player.poll()is not None:
                        print('Waiting player...')
                        time.sleep(1)
                    '''
                    ffmpegmuxer = subprocess.Popen(
                            ffmpegargs, bufsize=-1, stdin=subprocess.PIPE,
                            stdout=ffmpegbase.stdin)
                    while ffmpegmuxer.poll() is not None:
                        print("WAITING FFMPEG OPEN...")
                        time.sleep(1)
                    # stderr=subprocess.PIP
                    print("Writing....")
                    # with open(videofilename, 'w+', 0) as fd:
                    print("PRECHUNKS")
                    # chunk_size=512
                    for chunk in segment[1].iter_content(
                            chunk_size=512):
                                ffmpegmuxer.stdin.write(chunk)
                    # segment[1].close()
                    print("PRECOMMUNICATE")
                    ffstatus = ffmpegmuxer.communicate()
                    # Next segment:
                    seqnumber += 1

                    # ffmpegmuxer.stdin.write(segment[1].content)
                    # time.sleep(1)
                    # while True:
                    '''
                    try:
                        socka.connect((host, aport))
                    except:
                        print("Waiting localserver...")
                        time.sleep(0.5)
                    #   else:
                    #        break
                    #try:
                    for chunk in segment[0].iter_content(chunk_size=128):
                        socka.send(chunk)
                    socka.close()
                    # data = s.recv(1024)
                    sockv.connect((host, vport))
                    for chunk in segment[1].iter_content(chunk_size=128):
                        sockv.send(chunk)
                    sockv.close()
                    #except:
                    #    print("Exception ocurred")
                    #sockv.close()
                    '''
                # if twosegmentsdownload == 1:
                    # ra2.result().close()
                    # rv2.result().close()
                if cont:
                    cont = False
                    continue
                """
                #socka.connect('/dev/shm/audio')
                for chunk in rm[0].iter_content(chunk_size=128):
                    socka.sendall(chunk)
                #sockv.connect('/dev/shm/video')
                for chunk in rm[1].iter_content(chunk_size=128):
                    sockv.sendall(chunk)
                for chunk in rm[2].iter_content(chunk_size=128):
                    socka.sendall(chunk)
                for chunk in rm[3].iter_content(chunk_size=128):
                    sockv.sendall(chunk)
                #socka.close()
                #sockv.close()
                """
                """
                for line in rm[0].iter_lines():
                    s.sendto(line, (host, aport))
                for line in rm[1].iter_lines():
                    s.sendto(line, (host, vport))
                for line in rm[2].iter_lines():
                    s.sendto(line, (host, vport))
                for line in rm[3].iter_lines():
                    s.sendto(line, (host, aport))
                """
                """
                for chunk in rm[0].iter_content(chunk_size=128):
                    s.sendto(chunk, (host, aport))
                for chunk in rm[1].iter_content(chunk_size=128):
                    s.sendto(chunk, (host, vport))
                for chunk in rm[2].iter_content(chunk_size=128):
                    s.sendto(chunk, (host, aport))
                for chunk in rm[3].iter_content(chunk_size=128):
                    s.sendto(chunk, (host, vport))
                """
                '''
                # for filename in audiofilename, videofilename:
                # for i in range(2*2):
                with open(audiofilename, 'wb') as fd:
                        # for chunk in rm[0].iter_content(chunk_size=None):
                        #    fd.write(chunk)
                        fd.write(rm[0].content)
                with open(videofilename, 'wb') as fd:
                        # for chunk in rm[1].iter_content(chunk_size=None):
                        #   fd.write(chunk)
                        fd.write(rm[1].content)
                ffmpegargs = shlex.split(
                    '%s -v 0 -nostdin -y -flags +low_delay
                    -thread_queue_size 1024 -i %s
                    -flags +low_delay -thread_queue_size 1024 -i %s
                    -c copy -f mpegts %s'
                    % (ffmpegbin, audiofilename, videofilename, fifofile)
                     )
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
                ffmpegreturncode = subprocess.call(ffmpegargs)
                with open(audiofilename2, 'wb') as fd:
                        # for chunk in rm[2].iter_content(chunk_size=None):
                        #   fd.write(chunk)
                        fd.write(rm[2].content)
                with open(videofilename2, 'wb') as fd:
                        # for chunk in rm[3].iter_content(chunk_size=None):
                        #   fd.write(chunk)
                        fd.write(rm[3].content)
                # FFMpeg Muxing:
                ffmpegargs = shlex.split(
                     '%s -v 0 -nostdin -y -flags +low_delay
                     -thread_queue_size 1024 -i %s
                     -flags +low_delay -thread_queue_size 1024 -i %s
                     -c copy -f mpegts %s'
                     % (ffmpegbin, audiofilename2, videofilename2, fifofile)
                     )
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
                ffmpegreturncode = subprocess.call(ffmpegargs)
                '''

                """
                if ffmpegreturncode > 0:
                    print("Ffmpeg error, reintentando...")
                    time.sleep(1)
                    continue
                """
                # Next segment:
                # seqnumber += 2
            # print("STATUS CODE: " + str(rm[0].status_code))
            #    print("Retrying in %s secs..." % segmentsecs)
            #   time.sleep(segmentsecs)
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
            """finally:
                ##os.remove(audiofilename)
                #os.remove(videofilename)
                print("Retrying in %s secs..." % segmentsecs)
                time.sleep(segmentsecs)
            """
            # Download delays:
            # Delays:
            totaldelay = round((time.time() - starttime) / len(rm), 4)
            # totaldelay = (time.time() - basedelays[-1]) / len(rm)
            print("---> DELAY2: " + str(totaldelay) + " Seconds ")
            delays.append(round(totaldelay, 4))
            if len(delays) > segmentsoffset:
                del delays[0]
            delayavg = round(sum(delays) / segmentsoffset, 2)
            print("---> Delays " + str(delays))
            print("---> Delay Avg: " + str(delayavg))

            # Get bandwidth speeds:
            # if Bandwidths[0][0] == 0:
            #    Bandwidths[0][0] = int(rv.headers['X-Bandwidth-Avg']) * 8
            # .get returns empty if not found:
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
                BandwidthsAvgs[i] = sum(Bandwidths[i]) / len(Bandwidths[i])
            # Print Bandwidths values:
            # print("BANDWIDTHS: " + str(Bandwidths))
            # print("BANDWIDTHSAVG: " + str(BandwidthsAvgs))
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
            #  + (basedelays[-1]/2)
            selectedbandwidth = int(videodata[vid]['bandwidth']) + 124000
            if(vid > 0 and delayavg > segmentsecs and
                round(basedelays[-1], 1) < segmentsecs*0.7 and
                round(delays[-1], 1) > segmentsecs + 0.2 and
                    delays[-1] < segmentsecs * segmentsoffset * 3):
                        bandwidth_ok = False
                        '''
                        bandwidth_ok = True
                        for bandidx in range(len(BandwidthsAvgs)):
                            if BandwidthsAvgs[bandidx] < selectedbandwidth:
                                bandwidth_ok = False
                                break
                        '''
                        if not bandwidth_ok:
                            rest = int(delays[-1] / segmentsecs)
                            if rest > vid:
                                rest = vid
                            vid -= rest
                            logging.info('Going DOWN, to VID: %s' % vid)
                            logging.info("BASE DELAYS: %s" % str(basedelays))
                            logging.info(
                                "BASE DELAY AVG: %s" % str(basedelayavg))
                            logging.info('DELAYS: %s' % str(delays))
                            logging.info('DELAY AVG: %s' % str(delayavg))
                            logging.info("MIN DELAY: %s" % str(mindelay))
                            videomainurl = videodata[vid].text
                            logging.info('NEW VIDEO URL: %s' % videomainurl)
            # Check remaining segments:
            if headnumbers:
                headnumber = max(headnumbers)
            '''if not headnumber:
                headnumber = get_headseqnum(audiomainurl)
            '''
            remainsegms = headnumber - (seqnumber - 1)
            if remainsegms < 0:
                remainsegms = 0
            elif remainsegms > segmentsoffset*2:
                print('Resyncing...')
                logging.info('Resyncing...')
                seqnumber = headnumber
                ReleaseConn(rm)
                metadata = get_metadata(manifestsearch, aid, vid)
                audiourls = metadata[1]
                videodata = metadata[2]
                audiomainurl = metadata[6]
                videomainurl = metadata[7]
                #time.sleep(segmentsecs)
            print('HEAD TIMES: %s' % headtimes)
            print(
                "HEAD NUMBER: %s, SEQNUMBER: %s, REMAINING SEGMENTS:%s"
                % (headnumber, seqnumber, remainsegms))
            if mindelay > segmentsecs * 0.75:
                # videomainurl = videodata[0].text
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
                # time.sleep(segmentsecs-elapsed3)
                # delaytogoup = (segmentsecs + ( mindelay / 2 )) / 2
                # delaytogoup = (segmentsecs / 2) + (mindelay / 2)
                delaytogoup = max(mindelay * 2, segmentsecs/2)
                elapsed3 = round(time.time() - starttime, 4)
                print("---> DELAY3 (2 segments + ffmpeg): " + str(elapsed3))
                # Local wallclock timing:
                timesincedown = totaldelay - basedelays[-1]
                # - (segmentsecs/10)
                # CPU time wallclock timing:
                # timesincedownc = (time.clock() - starttimec ) * 100
                # Wallclock Milisecs from headers:
                timesincedownh = round(
                    (time.time() - (max(wallclocks)/1000)), 4)
                print('WALLCLOCK LOCAL : %s' % timesincedown)
                # print('CLOCK CPU TIME  : %s' % timesincedownc)
                print('WALLCLOCK SERVER: %s' % timesincedownh)
                # Check to get more video quality :
                if (
                    vid < len(videodata) - 1 and
                    delayavg < delaytogoup and
                    delays[-1] < delaytogoup and
                        basedelayavg < segmentsecs/2):
                        for bandidx in range(len(BandwidthsAvgs)):
                            bandwidth_ok = False
                            if BandwidthsAvgs[bandidx] > selectedbandwidth * 2:
                                bandwidth_ok = True
                            else:
                                break
                        if bandwidth_ok:
                            print("Getting more video quality...")
                            vid += 1
                            logging.info('Going UP, to VID: %s' % vid)
                            logging.info("BASE DELAYS: %s" % str(basedelays))
                            logging.info('DELAYS: %s' % str(delays))
                            logging.info('DELAY AVG: %s' % str(delayavg))
                            logging.info("MIN DELAY: %s" % str(mindelay))
                            logging.info('WALLCLOCK LOCAL : %s' % timesincedown)
                            logging.info('WALLCLOCK SERVER:%s' % timesincedownh)
                            videomainurl = videodata[vid].text
                            logging.info('NEW VIDEO URL: %s' % videomainurl)
                # remainsegms = 0
                sleepsecs = ((len(rm) * segmentsecs) - (
                            (remainsegms * segmentsecs) + timesincedown))
                # + ( segmentsecs/3) + prevsleepsecs
                if sleepsecs < 0:
                    # prevsleepsecs = sleepsecs
                    sleepsecs = 0
                else:
                    prevsleepsecs = 0
                # time.sleep(sleepsecs)
                # for times in range(times):
                if player.poll() is not None:
                    print("Player Closed, quitting...")
                    break
                print("Sleeping %s seconds..." % str(round(sleepsecs, 3)))
                logging.info(
                    "Sleeping %s seconds..." % str(round(sleepsecs, 3)))
                time.sleep(round(sleepsecs, 3))
                '''
                tries = 0
                headnumber = get_headseqnum(audiomainurl)
                while headnumber < seqnumber + (len(rm) - 1):
                    time.sleep(segmentsecs/2)
                    headnumber = get_headseqnum(audiomainurl)
                    print("HEAD UPDATED: %s" % headnumber)
                    print("Waiting next segment generation...")
                    tries += 1
                    if tries == 3:
                        print('Transmission finished, waiting player close...')
                        player.wait()
                        break
                '''
        # After for:
        ReleaseConn(rm)
        item += 1
    # session.close()


with FuturesSession(max_workers=10) as session:
    session.mount(
        'https://', requests.adapters.HTTPAdapter(
            pool_connections=1000, pool_maxsize=1000, max_retries=50))
    main()
#os.remove('/tmp/dash2.0.pid')
#os.killpg(int(os.getpgrp()), signal.SIGTERM)
#os.wait()
