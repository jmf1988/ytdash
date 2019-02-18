#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from threading import active_count as active_threads
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse
import requests
import logging
import os
import signal
import sys
import time
import subprocess
import re
import shlex
import json
import argparse
try:
    import gtk
    maxwidth = gtk.gdk.screen_width()
    maxheight = gtk.gdk.screen_height()
except ImportError:
    pass


class Ended(Exception):
    pass


def log_(infos):
    logging.debug('''---> Going %s, to VID: %s
                 REMAINING SEGMENTS: %s
                 MIN DELAY: %s
                 FFMUX DELAY: %s
                 DELAY TO UP: %s
                 TRUE DELAYS: %s
                 TRUE DELAY AVG: %s
                 BASE DELAYS: %s
                 BASE DELAY AVG: %s
                 DELAYS: %s
                 DELAY AVG: %s
                 CURRENT BAND: %s
                 NEXT BAND: %s
                 MIN BANDWIDTH AVGS: %s
                 MIN BANDWIDTH LASTS: %s
                 BANDWIDTH LASTS AVG: %s
                 NEW VIDEO URL: %s''' % infos)


def get_quality_ids(mediadata, Bandwidths):
    minband = min(Bandwidths[1:])[-1]
    logging.debug("MINBANDS: %s" % Bandwidths[1:])
    mid = len(mediadata) - 1
    aid = 1
    audioband = 144000
    logging.debug('Videodata Attribs: %s' % mediadata[mid][minvid].attrib)
    for idv in range(len(mediadata[mid])):
        manband = mediadata[mid][idv].attrib.get('bandwidth', 0)
        manband = int(manband) + audioband
        vid = idv
        if manband > minband:
            #  or manband / 8 > maxband * 1024
            break
    vid = max(idv - 1, minvid)
    logging.debug('VID SELECTED: %s' % vid)
    return (aid, vid)


def get_mediadata(videoid):
    # https://www.youtube.com/oembed?url=[Youtubewatchurl]&format=json
    url = 'https://www.youtube.com/get_video_info?video_id=' + videoid
    r = session.get(url)
    ytdict = parse_qs(r.text, strict_parsing=True)
    ytpresp = json.loads(ytdict.get('player_response', [0])[0])
    if ytpresp:
        playable = ytpresp.get('playabilityStatus')
        pstatus = playable.get('status')
        if pstatus and pstatus == 'UNPLAYABLE':
            logging.info('Video status: UNPLAYABLE')
            reason = playable.get('reason')
            if reason:
                href = re.findall(r'(?<=href=").*?(?=")', reason)
                if href:
                    reco = re.findall(r'(?<=>).*?(?=<)', reason)
                    if reco:
                        reco = reco[0] + ' --> ' + href[0]
                        realreason =  re.findall(r'(?<=\n).*$', reason)
                        if realreason:
                            reason = realreason[0] + '\n' + reco
                logging.info("Reason: %s" % reason)
            return 1
    else:
        logging.info('Could not extract player response data...')
        return 1
    # videourl = videourl.replace('watch?v=','embed/' )
    logging.info("Video id: %s" % videoid)
    # r = session.get(videourl, stream=True)
    # Player configs json:
    # ytpjs = re.findall(r'ytplayer.config = ({.*?});', r.text)
    # if not ytpjs:
    #    return 1
    # ytpjson = json.loads(ytpjs[0])
    # ytpargs = ytpjson['args']
    liveaheadsecs = ytdict.get('live_readahead_seconds')
    liveaheadchunk = ytdict.get('live_chunk_readahead')
    latencyclass = ytdict.get('latency_class')
    livestream = ytdict.get('livestream')
    liveplayback = ytdict.get('live_playback')
    # lengthsecs = ytpjson['args']['length_seconds']
    # ytpresp = json.loads(ytpjson['args']['player_response'])
    ytpconfig = ytpresp.get('playerConfig')
    if ytpconfig:
        audioconfig = ytpconfig.get('audioConfig')
        streamconfig = ytpconfig.get('streamSelectionConfig')
        if streamconfig:
            maxbitrate = streamconfig.get('maxBitrate')
            logging.info('MaxBitrate: ' + maxbitrate)
    # Get Video Details:
    videodetails = ytpresp.get('videoDetails')
    if videodetails:
        metadata = videodetails
        title = videodetails.get('title')
        description = videodetails.get('shortDescription')
        author = videodetails.get('author')
        isprivate = videodetails.get('isPrivate')
        viewcount = videodetails.get('viewCount')
        lengthsecs = videodetails['lengthSeconds']
        postlivedvr = videodetails.get('isPostLiveDvr')
        livecontent = videodetails.get('isLiveContent')
        live = videodetails.get('isLive', False)
        lowlatency = videodetails.get('isLowLatencyLiveStream')
        livedvr = videodetails.get('isLiveDvrEnabled')
    # Get streaming Data:
    streamingdata = ytpresp.get('streamingData')
    if streamingdata:
        dashmanurl = streamingdata.get('dashManifestUrl')
        hlsmanurl = streamingdata.get('hlsManifestUrl')
        manifesturl = dashmanurl
        metadata['ManifestUrl'] = manifesturl
        formats = streamingdata.get('formats')
        adaptivefmts = streamingdata.get('adaptiveFormats')
        otf = False
        if adaptivefmts:
            # logging.debug('ADAPTIVEFMTS: ' + str(adaptivefmts))
            adaptivefmts.sort(key=lambda fmt: fmt.get('bitrate', 0))
            streamtype = adaptivefmts[0].get('type')
            if streamtype == 'FORMAT_STREAM_TYPE_OTF':
                otf = True
            metadata['Otf'] = otf
            logging.debug('stream type: ' + str(streamtype))
    else:
        manifesturl = None
        logging.info('No data found to play media')
        return 1
    if not latencyclass:
        latencyclass = videodetails.get('latencyClass')
        if latencyclass:
            latencyclass = re.findall('(?<=LATENCY_).+', latencyclass)
            metadata['latencyClass'] = latencyclass[0]
    if not livecontent or not manifesturl:
        audiodata = []
        videodata = []
        for i in range(len(adaptivefmts)):
            mtype = adaptivefmts[i]['mimeType'].split('; ')
            if mtype[0] == 'audio/mp4' and mtype[1][8:11] == 'mp4':
                audiodata.append(adaptivefmts[i])
            elif mtype[0] == 'video/mp4' and mtype[1][8:11] == 'avc':
                videodata.append(adaptivefmts[i])
        logging.debug('Videodata: %s' % videodata)
    # mimetype = formats[0]['mimeType']
    # logging Details:
    logging.info('View count: ' + viewcount)
    logging.debug('postLiveDVR: ' + str(postlivedvr))
    # logging.debug('reason: ' + str(reason))
    logging.debug('liveplayback: ' + str(liveplayback))
    logging.debug('livestream: ' + str(livestream))
    logging.debug('title: ' + str(title))
    logging.debug('description: ' + str(description))
    logging.debug('isprivate: ' + str(isprivate))
    logging.debug('islive: ' + str(live))
    logging.debug('islivecontent: ' + str(livecontent))
    logging.debug('islowlatency: ' + str(lowlatency))
    logging.debug('islivedvr: ' + str(livedvr))
    logging.debug('latencyclass: ' + str(latencyclass))
    logging.debug('live readahead secs: ' + str(liveaheadsecs))
    logging.debug('live readahead chunks: ' + str(liveaheadchunk))
    '''
    manifesturlsearch = re.findall('(dashmpd|dashManifestUrl)":"(.+?)"' + '|' +
                                   '"(https://manifest.googlevideo.com/' +
                                   'api/manifest/dash.+?)"',
                                   r.text.replace('\\', ""))
    '''
    if manifesturl:
        manifesturl +=  '/keepalive/yes'
        logging.debug("Manifest URL: %s" % manifesturl)
        # if live or (not live and args.offset):
        rawmanifest = session.get(manifesturl,
                                  headers=None, stream=True)
        if not rawmanifest.ok:
            logging.info("Error getting manifest...")
            return 1
        # else:
        if not live and livecontent:
            if reason:
                print(reason)
            else:
                print('Stream no longer live...')
            if postlivedvr or otf:
                print("Retry with a timeoffset to play it from.")
                return 1
        tree = ET.fromstring(rawmanifest.text)
        startnumber = int(tree[0][0].attrib.get('startNumber', 0))
        earliestseqnum = int(tree.get('{http://youtube.com/yt/2012/10/10}' +
                                      'earliestMediaSequence', 0))
        timescale = float(tree[0][0].get('timescale', 0))
        buffersecs = tree.get('timeShiftBufferDepth')
        if buffersecs:
            buffersecs = float(buffersecs[2:-1])
        minuperiod = tree[0].get('minimumUpdatePeriod')
        if minuperiod:
            segsecs = int(minuperiod[2:-1])
        elif timescale:
            segsecs = round(float(tree[0][0][0][0].get('d')) / timescale)
        # Media Metadata:
        if otf:
            if not lowlatency:
                segsecs = 5
            ida = 0
            idv = 1
        else:
            ida = 1
            idv = 2
        audiodata = tree[0][ida].findall("[@mimeType='audio/mp4']/")
        videodata = tree[0][idv].findall("[@mimeType='video/mp4']/")
        # Sort by bandwidth needed:
        for mtype in audiodata, videodata:
            mtype.sort(key=lambda mid: int(mid.attrib.get('bandwidth', 0)))
        fps_string = 'FrameRate'
    else:
        logging.info('Dash Manifest URL not available...')
        if adaptivefmts:
            logging.info('Playing manifestless video...')
            logging.info('Adaptative video disabled...')
            fps_string = 'fps'
            segsecs = 5
            buffersecs, earliestseqnum, startnumber = 0, 0, 0
        else:
            logging.info('No dynamic video to play...')
            return 1
    logging.info("VIDEO IS LIVE: %s" % live)
    logging.info("Total video Qualitys Available: %s" % len(videodata))
    # Filter video types by max height, width, fps and badnwidth:
    idx = 0
    while idx < len(videodata):
        # logging.info(videodata[idx].get('bandwidth'))
        videofps = int(videodata[idx].get(fps_string, 0))
        videoheight = int(videodata[idx].get('height', 0))
        videowidth = int(videodata[idx].get('width', 0))
        if livecontent and manifesturl:
            videoband = int(videodata[idx].attrib.get('bandwidth', 0))
        else:
            videoband = 0
        if(videofps > args.maxfps or videoheight > args.maxheight
           or videowidth > args.maxwidth or videoband / 8 > args.maxband * 1024):
                del videodata[idx]
        else:
            idx += 1
    logging.info("Total video Qualitys Choosen: %s" % len(videodata))
    return (segsecs, audiodata, videodata, buffersecs, earliestseqnum,
            startnumber, metadata)


def ffmuxer(ffmpegbin, ffmuxerstdout, apipe, vpipe):
    ffmpegargs = '%s -y -v %s -nostdin ' % (ffmpegbin, ffloglevel)
    ffmpegargsinputs = '-thread_queue_size 1512 -flags +low_delay '
    if apipe:
        ffmpegargs += ffmpegargsinputs + '-i pipe:%s ' % apipe
        fds = (apipe, vpipe)
    else:
        fds = (vpipe,)
    ffmpegargs += ffmpegargsinputs + ' -i pipe:%s ' % vpipe
    ffmpegargs += '-f mpegts -bsf:v h264_mp4toannexb -c copy -copyts '
    ffmpegargs += '-flags +low_delay -'
    ffmpegmuxer = subprocess.Popen(shlex.split(ffmpegargs),
                                   bufsize=1048576,
                                   stdout=ffmuxerstdout,
                                   stderr=None,
                                   close_fds=True,
                                   pass_fds=fds)
    fftries = 0
    while ffmpegmuxer.poll() is not None:
        print("WAITING FFMPEG TO OPEN...")
        if fftries < 5:
            time.sleep(1)
        else:
            raise Exception
        fftries += 1
    # closefd(apipe)
    return ffmpegmuxer


def get_media(data):
    baseurl, segmenturl, fd, init = data
    rtimeouttries = 2
    err404tries = 2
    conerr = 0
    twbytes = 0
    acceptranges = None
    headnumber = 0
    timeouts = (3.05, max(4, segsecs * 3))
    headers = 0
    status = 0
    response = 0
    contentlength = 0
    walltimems = 0
    headtime = 0
    newurl = None
    rheaders = {}
    initbyte = 0
    if not livecontent or not manifesturl:
        initbyte = 0
        maxbytes = 1048576
        rheaders['Range'] = 'bytes=%s-%s' % (initbyte, initbyte + maxbytes)
    else:
        maxbytes = 0
    while True:
        try:
            if twbytes:
                fd.flush()
                logging.debug("Trying to resume from byte: %s" % twbytes)
                sbyte = initbyte + twbytes
                if maxbytes:
                    ebyte = sbyte + maxbytes
                    if ebyte > contentlength:
                        ebyte = contentlength
                else:
                    ebyte = ''

                rheaders['Range'] = 'bytes=%s-%s' % (sbyte, ebyte)
            # for segment in segmenturl[1]:
            url = baseurl + segmenturl
            # logging.debug("GETTING URL: " + url)
            gettime = time.time()
            with session.get(url, stream=True, timeout=timeouts,
                             allow_redirects=True,
                             headers=rheaders) as response:
                # logging.debug('REQUESTHEADERS' + str(response.request.headers))
                basedelay = round((time.time() - gettime), 4)
                # Getting metadata from headers:
                headers = response.headers
                headnumber = int(headers.get('X-Head-Seqnum', 0))
                sequencenum = int(headers.get('X-Sequence-Num', 0))
                pheadtime = headtime
                headtime = int(headers.get('X-Head-Time-Sec', 0))
                pwalltimems = walltimems
                walltimems = int(headers.get('X-Walltime-Ms', 0))
                if live and pwalltimems and pheadtime:
                    walldiff = (walltimems - pwalltimems) / 1000
                    headdiff = (headtime - pheadtime) / 1
                    if(walldiff > segsecs * 1.5 and headdiff == 0):
                        logging.debug('Wallsdif > SegmSecs: %s' % walldiff)
                        logging.info('Transmission ended...')
                        return 1
                if not contentlength:
                    # print('HEADERS' + str(response.headers))
                    contentrange = headers.get(
                                             'Content-Range', '').split('/')[-1]
                    if contentrange and contentrange != '*':
                        contentlength = int(contentrange)
                    else:
                        contentlength = int(headers.get('Content-Length', 0))
                acceptranges = headers.get('Accept-Ranges', 0)
                cachecontrol = headers.get('Cache-Control', 0)
                headtimems = int(headers.get('X-Head-Time-Millis', 0))
                segmentlmt = int(headers.get('X-Segment-Lmt', 0))
                contenttype = headers.get('Content-Type', 0)
                if contenttype != 'audio/mp4':
                    bandwidthavg = int(headers.get('X-Bandwidth-Avg', 0))
                    bandwidthest = int(headers.get('X-Bandwidth-Est', 0))
                    bandwidthest2 = int(headers.get('X-Bandwidth-Est2', 0))
                    bandwidthest3 = int(headers.get('X-Bandwidth-Est3', 0))
                else:
                    bandwidthavg = 0
                    bandwidthest = 0
                    bandwidthest2 = 0
                    bandwidthest3 = 0

                status = response.status_code
                contents = 0
                connection = response.connection
                if live or postlivedvr:
                    logging.debug('HEADNUMBER: %s' % headnumber)
                    logging.debug('SEQUENCENUMBER: %s' % sequencenum)
                logging.debug('ACCEPT-RANGES: %s' % acceptranges)
                logging.debug("CONTENT LENGTH: %s" % contentlength)
                # Check status codes:
                if status == 200 or status == 206:
                    logging.debug("Getting Media Content.....")
                    if response.history:
                        if response.history[-1].status_code == 302:
                            rurl = response.url + "/"
                            if segmenturl:
                                newurl = rurl.replace(segmenturl + "/", '')
                            elif not livecontent:
                                baseurl = rurl[0:-1]
                            logging.debug('SAVING NEW URL: %s' % newurl)
                    if otf and not twbytes and init:
                        twbytes = fd.write(init)
                    logging.debug("WRITING TO FD: " + str(fd))

                    for chunk in response.iter_content(chunk_size=1024):
                        if player.poll() is not None:
                            fd.flush()
                            fd.close()
                            connection.close()
                            return 1
                        twbytes += fd.write(chunk)
                        fd.flush()
                    if otf:
                        if contenttype == 'video/mp4':
                            fd.close()
                    elif not livecontent or not manifesturl:
                        if twbytes < contentlength:
                            continue
                        else:
                            connection.close()
                            fd.close()
                            return 1
                    else:
                        fd.close()
                    info = (status, contents, basedelay, headnumber, headtimems,
                            sequencenum, walltimems, segmentlmt, contentlength,
                            cachecontrol, bandwidthavg, bandwidthest,
                            bandwidthest2, bandwidthest3, connection,
                            contenttype, newurl, twbytes)
                    logging.debug('Bytes written: %s' % twbytes)
                    return info
                else:
                    logging.debug('Status Code: %s' % status)
                    logging.debug('REQUEST HEADERS: %s' %
                                 response.request.headers)
                    logging.debug('HEADERS: %s' % response.headers)
                    logging.debug("REQUEST URL: " + url)
                    if status == 204:
                        return 1
                    if status == 503:
                        logging.debug("Trying redirection...")
                        gvideohost = url.split('/')[2].split('.')[0]
                        url = url.replace(gvideohost, "redirector")
                    elif status == 404 or status == 400 or status == 403:
                        logging.debug('Refreshing metadata: ' + str(segsecs))
                        metadata = get_mediadata(videoid)
                        still_live = metadata.get('isLive')
                        if metadata and not still_live:
                            logging.debug("Transmission looks ended...")
                            return 1
                    time.sleep(segsecs)
                    continue
            gettries = 5
        except BrokenPipeError as oserr:
            logging.debug("Exception Ocurred: %s %s" % (oserr, str(oserr.args)))
            return 1
        except (requests.exceptions.ConnectionError) as exception:
            logging.debug("Requests HTTP Exception Ocurred: %s" % exception)
            logging.debug("Total bytes written: %s" % twbytes)
            headtime = 0
            if headers:
                logging.debug("HEADERS: %s" % headers)
            if status:
                logging.debug("LAST STATUS CODE: %s" % status)
            connerr = 1
            time.sleep(segsecs)
            continue

        except (requests.exceptions.ChunkedEncodingError,
                requests.exceptions.ReadTimeout) as exception:
            logging.debug("Requests Exception Ocurred: %s" % exception)
            logging.debug("Total bytes written: %s" % twbytes)
            headtime = 0
            if headers:
                logging.debug("HEADERS: %s" % headers)
            if status:
                logging.debug("LAST STATUS CODE: %s" % status)
            connerr = 1
            if livecontent and manifesturl:
                metadata = get_mediadata(videoid)
                if (metadata and metadata[6] != 'live'):
                            logging.debug("Manifest upd:Transmission ended...")
                            return 2
            time.sleep(segsecs)
            continue


def closefds(fds):
    for fd in fds:
        if fd > 2:
            try:
                os.close(fd)
            except OSError:
                pass


def check_player(player, fda, fdv):
    while True:
        if player is not None:
            if player.poll() is not None:
                print("Player Closed, playing next item in list...")
                fda.flush()
                fdv.flush()
                # if pool.poll() is None:
                #    pool.terminate()
                #    pool.join()
                raise Ended
                return
        time.sleep(segsecs)


if __name__ == '__main__':
    global ffmpegmuxer, abaseurls, vbaseurls, args, livecontent, live, otf
    global segsecs, apiurllive, videoid, minvid, livedvr, lowlatency, manifesturl
    parser = argparse.ArgumentParser(prog='ytdash',
                                     description='Youtube DASH video playback.')
    parser.add_argument('urls', metavar='URL|QUERY', type=str, nargs='+',
                        help='URLs or search queries of videos to play')
    parser.add_argument('--version', action='version', version='%(prog)s 0.1')
    parser.add_argument('-quiet', '-q', action='store_true',
                        help='enable quiet mode (default: %(default)s)')
    parser.add_argument('-search', '-s', action='store_true',
                        help='search mode (default: %(default)s)')
    parser.add_argument('-maxresults', '-mr', type=int, default=5,
                        help='search max results (default: %(default)s)')
    parser.add_argument('-debug', '-d', action='store_true',
                        help='enable debug mode  (default: %(default)s)')
    parser.add_argument('-player', '-p', type=str, default='mpv',
                        help='player bin name, (default: %(default)s)')
    parser.add_argument('-maxfps', '-mf', type=int, default=60,
                        help='max video fps to allow (default: %(default)s)')
    parser.add_argument('-maxband', '-mb', type=int, default=700,
                        help='max video bandwidth in kB/s to allow when ' +
                        ' possible (default: %(default)s)')
    parser.add_argument('-maxheight', '-mh', type=int, default=720,
                        help='max video heigth to allow (default: %(default)s)')
    parser.add_argument('-maxwidth', '-mw', type=int, default=1360,
                        help='max video width to allow (default: %(default)s)')
    parser.add_argument('-ffmpeg', '-ff', type=str, default='ffmpeg',
                        help='ffmpeg location route (default: %(default)s)')
    parser.add_argument('-fixed', '-f', action='store_true',
                        help='Play a fixed video quality instead of'  +
                        ' doing bandwidth adaptive quality change, This is the max' +
                        ' set from options (default: %(default)s)')
    parser.add_argument('-offset', '-o', type=str, default='',
                        help='Time or segments offset from where start ' +
                        'to play, (i.e: 2h, 210m, 3000s or 152456, ' +
                        "for hours, minutes, seconds and " +
                        "nº of segment respectively.)")
    args = parser.parse_args()
    # Logging:
    if args.debug:
        loglevel = logging.DEBUG
        ffloglevel = 'warning'
    elif args.quiet:
        loglevel = logging.WARN
        ffloglevel = 'fatal'
    else:
        loglevel = logging.INFO
        ffloglevel = 'fatal'
    logging.basicConfig(
        level=loglevel, filename="logfile", filemode="w+",
        format="%(asctime)-15s %(levelname)-8s %(message)s")
    console = logging.StreamHandler()
    console.setLevel(loglevel)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)

    if os.path.isfile('/tmp/dash2.0.pid'):
        with open('/tmp/dash2.0.pid', 'r') as fd:
            prevpid = fd.read()
            if prevpid:
                try:
                    os.killpg(int(prevpid), signal.SIGTERM)
                    logging.debug("Killed previous instance...")
                except ProcessLookupError:
                    logging.debug("Process does not exist...")
    os.setpgrp()
    with open('/tmp/dash2.0.pid', 'w') as fd:
        fd.write(str(os.getpgrp()))

    if args.player == 'mpv':
        # max RAM cached media size downloaded after pause in Mb:
        cachesize = 7
        backcachesize = 5  # max back RAM cached media played/skipped to keep, Mb.
        totalcachesize = backcachesize + cachesize
        playerargs = ( ' --input-terminal=no ')
                      # ' --rebase-start-time=yes ' )
                      # '--profile=low-latency'
        if not args.debug:
            playerargs += ' --really-quiet=yes '
    elif args.player == 'vlc':
        playerargs = ' - --file-caching=5000'
    else:
        playerargs = ' - '
    logging.debug('PLAYER CMD: ' + args.player + playerargs)

    autoresync = 1  # Drop segments on high delays to keep live
    url = urlparse(args.urls[0])
    urlquery = url.query
    urlhost = url.hostname
    urlfolders = url.path.split('/')
    idre = re.compile('^[A-z0-9_-]{11}$')
    videoid = None
    channelid = None
    userid = None
    if urlhost:
        if url.hostname[-8:] == "youtu.be":
            videoid = urlfolders[1]
        elif url.hostname[-11:] == "youtube.com":
            if url.path == '/watch':
                videoid = parse_qs(url.query).get('v', [0])[0]
            elif url.path == '/embed':
                videoid = urlfolders[2]
            elif url.path[0:8] == '/channel':
                channelid = urlfolders[2]
            elif url.path[0:5] == '/user':
                userid = urlfolders[2]
            if channelid or userid:
                if not args.search:
                    logging.info('Channel URL given but search disabled, ' +
                                 'enable search mode to play the videos found')
                    quit()
    elif not args.search:
        if url.path and re.match(idre, url.path):
            videoid = url.path
        else:
            logging.info('Could not find a video or channel id in the given string')
            quit()
    apibaseurl = 'https://www.googleapis.com/youtube/v3/'
    apiparams = {}
    apiparams['part'] = 'snippet'
    apiparams['key'] = 'AIzaSyAWOONC01ILGs4dh8vnCJDO4trYbFTH4zQ'
    if videoid:
        apitype = 'videos'
        apiparams['id'] = videoid
    else:
        # channelid = re.search(urlpattern3, args.urls[0])
        if userid:
            apitype = 'channels'
            apiurl = apibaseurl + apitype
            apiparams['forUsername'] = userid
            r = requests.get(apiurl, params=apiparams)
            channelitems = r.json().get('items')
            if channelitems:
                channelid = channelitems[0].get('id')
            else:
                logging.info('Could not get user channel id')
                quit()
            del apiparams['forUsername']
        apitype = 'search'
        apiparams['type'] = 'video'
        apiparams['order'] = 'relevance'
        apiparams['eventType'] = 'live'
        apiparams['maxResults'] = args.maxresults
        if channelid:
            # searchid = "channelId=" + ischannelid.group(3)
            apiparams['channelId'] = channelid
        else:
            # searchid = 'q=' + args.urls[0]
            apiparams['q'] = args.urls[0]
    apiparams['fields'] = 'items(id,snippet/title,snippet/channelTitle,snippet/description)'
    apiurl = apibaseurl + apitype
    # ' +'snippet/liveBroadcastContent
    with requests.Session() as session:
        session.verify = True
        session.mount('https://', requests.adapters.HTTPAdapter(
                        pool_connections=10,
                        pool_maxsize=10,
                        max_retries=1))
        try:
            r = requests.get(apiurl, params=apiparams)
            logging.debug("API URL: " + r.url)
        except requests.exceptions.ConnectionError:
            logging.warn("Connection Error, please check Internet connection...")
            quit()
        items = r.json().get('items')
        if items:
            print("%s Videos found." % len(items))
        else:
            print("No videos found.")
            quit()
        answer = None
        if args.search and len(items) > 1:
            itemnum = 1
            for item in items:
                snippet = item['snippet']
                chantitle = snippet["channelTitle"]
                title = snippet['title']
                description = snippet['description'][:58:] + '...'
                print('%s) %s\n' % (itemnum, title) +
                      '    * Description: %s\n' % description +
                      '    * Channel: %s' %  chantitle)
                itemnum += 1
            print('Please enter the number of the video to play or press ' +
                  'Enter to play from the first one.')
            while True:
                answer = input()
                if re.match(r'^[0-9]+$', answer) and int(answer) <= len(items):
                    answer = int(answer)
                if not answer or type(answer) is int:
                    break
                else:
                    print('Invalid input, only integers minor or equal to' +
                          ' %s accepted...' % len(items))
        if answer:
            items = [items[answer - 1]]
        for item in items:
            channeltitle = item['snippet']["channelTitle"]
            title = item['snippet']['title'] + ' - ' + channeltitle
            description = str(item['snippet']['description'])
            if not videoid:
                videoid = item['id']['videoId']
            apiurllive = 'https://www.googleapis.com/youtube/v3/videos?' +\
                         'part=snippet' +\
                         '&fields=items(snippet/liveBroadcastContent)' +\
                         '&key=AIzaSyAWOONC01ILGs4dh8vnCJDO4trYbFTH4zQ' +\
                         '&id=%s' % videoid
            logging.debug('APICHECKLIVE: ' + apiurllive)
            vsegoffset = 3
            init = None
            ffmpegbase = None
            player = None
            videodata = None
            vid = 0
            aid = 0
            minsegms = 1
            ffmpegmuxer = None
            BandwidthsAvgs = [0, 1, 2, 3]
            # Get the manifest and all its Infos
            mediadata = get_mediadata(videoid)
            # print(metadata)
            if mediadata == 1:
                continue
            elif mediadata == 2:
                break
            else:
                segsecs = mediadata[0]
                audiodata = mediadata[1]
                videodata = mediadata[2]
                buffersecs = mediadata[3]
                earliestseqnum = mediadata[4]
                startnumber = mediadata[5]
                metadata = mediadata[6]
                title = metadata.get('title')
                description = metadata.get('shortDescription')
                author = metadata.get('author')
                private = metadata['isPrivate']
                lengthsecs = metadata['lengthSeconds']
                postlivedvr = metadata.get('isPostLiveDvr')
                livecontent = metadata.get('isLiveContent') # media is/was live
                live = metadata.get('isLive')
                lowlatency = metadata.get('isLowLatencyLiveStream')
                livedvr = metadata.get('isLiveDvrEnabled')
                otf = metadata.get('Otf')
                manifesturl = metadata.get('ManifestUrl')
            logging.debug("Start number: " + str(startnumber))
            # Check the Url and Get info from Headers:
            maxaid = len(audiodata) - 1
            maxvid = len(videodata) - 1
            if live:
                maxsegms = 2
                if segsecs == 1:
                    logging.info('--Live mode: ULTRA LOW LATENCY--')
                    maxsegms = 3
                    minsegms = 2
                elif segsecs == 2:
                    logging.info('--Live mode: LOW LATENCY--')
                elif segsecs == 5:
                    logging.info('--Live mode: NORMAL LATENCY--')
                    maxsegms = 2
            else:
                maxsegms = 3
            logging.debug("Segment duration in secs: " + str(segsecs))
            if live or postlivedvr:
                if args.fixed:
                    aid = maxaid
                    vid = maxvid
                else:
                    aid = 1
                    vid = 1
                inita = 0
                initv = 0
                aidu = 1
                minvid = 1
                Bandwidths = [[0], [0], [0], [0]]
                logging.debug("Back buffer depth in secs: " + str(buffersecs))
                logging.debug("Earliest sequence number: " + str(earliestseqnum))
                # max Nº of pending segments allowed before forcing resync:
                segmresynclimit = buffersecs/segsecs
                headnumber = len(audiodata[1][2]) + earliestseqnum - 1
                if startnumber > earliestseqnum:
                    segmresynclimit = startnumber - earliestseqnum
                    if vsegoffset > segmresynclimit:
                        vsegoffset = segmresynclimit - 1
                elif args.offset:
                    if args.offset[-1] == "h":
                        vsegoffset = int((float(args.offset[0:-1])*3600)/segsecs)
                        if float(args.offset[0:-1]) > 4:
                            logging.debug('''The max back buffer hours is %s,
                                            playing
                                            from oldest segment available'''
                                         % str(buffersecs/3600))
                    elif args.offset[-1] == "m":
                        vsegoffset = int((float(args.offset[0:-1])*60)/segsecs)
                        if float(args.offset[0:-1]) > 240:
                            logging.debug('''The max back buffer minutes is %s,
                                         playing from oldest segment available
                                         '''
                                         % str(buffersecs/60))
                    elif args.offset[-1] == "s":
                        vsegoffset = int(int(args.offset[0:-1])/segsecs)
                        if int(args.offset[0:-1]) > buffersecs:
                            logging.debug("The max backbuffer seconds is %s, " +
                                         "playing from there" % str(buffersecs))

                    elif args.offset[-1] <= 9 and args.offset[-1] >= 0:
                        if int(args.offset) >= earliestseqnum:
                            vsegoffset = int(args.offset)
                        else:
                            logging.debug("The oldest segment to play is %s, " +
                                         "playing from there" % str(buffersecs))
                    else:
                        logging.debug("No valid value entered for third " +
                                     "argument, acepted values are; " +
                                     " i.e: 2h, 210m or 3000s or 152456, " +
                                     "for hours, minutes, seconds and " +
                                     "nº of segment respectively.")
                    vsegoffset = min(segmresynclimit, vsegoffset, headnumber)
                    vsegoffset = asegoffset = int(vsegoffset)
                seqnumber = int(headnumber - vsegoffset)
                if lowlatency:
                    seqnumber = ''
                logging.debug('HEADNUMBER: %s, ' % headnumber +
                              'START NUMBER: %s, ' % startnumber +
                              'SEQNUMBER: %s, ' % seqnumber)
                logging.debug('VSEGOFFSET: %s' % vsegoffset)
                logging.debug("AUDIOMAINURL %s" % audiodata[aid][1].text)
                logging.debug("VIDEOMAINURL %s" % videodata[vid][0].text)
            else:
                apipe = 0
                vid = int(len(videodata) / 1) - 1
                aidu = 1
                minvid = 2
                headnumber = 999
                seqnumber = 0
                remainsegms = 0
                segmresynclimit = 99999
                selectedbandwidth = [0, 0]
                nextbandwidth = [0, 0]
                minbandavg = [0, 0]
                minbandlast = [0, 0]
                bandslastavg = [0, 0]
                bandwidthdown = 1
                bandwidthup = 1
                if otf:
                    aid = 2
                    vsegoffset = len(videodata[2][1]) - 1
                    asegoffset = len(audiodata[2][2]) - 1
                    initaurl = audiodata[aid][1].text
                    initaurl += audiodata[aid][2][0].get('sourceURL')
                    initvurl = videodata[vid][0].text
                    initvurl += videodata[vid][1][0].get('sourceURL')
                else:
                    aid = 0
                    initaurl = audiodata[aid]['url']
                    rangestart = audiodata[aid]['initRange'].get('start')
                    rangeend = audiodata[aid]['indexRange'].get('end')
                    initaurl += '&range=%s-%s' % (rangestart, rangeend)
                    initvurl = videodata[vid]['url']
                    rangestart = videodata[vid]['initRange'].get('start')
                    rangeend = videodata[vid]['indexRange'].get('end')
                    if rangestart:
                        initvurl += '&range=%s-%s' % (rangestart, rangeend)
                initv = session.get(initvurl).content
                inita = session.get(initaurl).content
                logging.debug("IDS MEDIADATA %s %s" % (aid, vid))
                logging.debug("AUDIOMAINURL %s" % initaurl)
                logging.debug("VIDEOMAINURL %s" % initvurl)
            # While End ---
            if manifesturl:
                analyzedur = int(segsecs * 1000000 * 3)
                ffbaseargs = args.ffmpeg + ' -v %s -analyzeduration ' % ffloglevel
                ffbaseinputs = ' -thread_queue_size 6500 -flags +low_delay '
                ffbaseargs += str(analyzedur)
                if otf:
                    apipe = os.pipe()
                    fda = os.fdopen(apipe[1], 'wb', 524288)
                    ffbaseargs += ffbaseinputs + '-i async:pipe:%s ' % apipe[0]
                    fffds = (apipe[0],)
                else:
                    fffds = ()
                ffbaseargs += ffbaseinputs + ' -i pipe:0 '
                ffbaseargs += ' -c copy -f nut '
                ffbaseargs += ' -bsf:v h264_mp4toannexb'
                ffbaseargs += ' -flags +low_delay pipe:1'
                ffmpegbase = subprocess.Popen(shlex.split(ffbaseargs),
                                              stdin=subprocess.PIPE,
                                              stdout=subprocess.PIPE,
                                              bufsize=1048576,
                                              pass_fds=fffds)
                playerstdin = ffmpegbase.stdout
                ffmuxerstdout = ffmpegbase.stdin
                playerargs += ' - '
                playerfds = ()
                if ffmpegbase.poll() is not None:
                    logging.info('Error openning main ffmpeg, quitting...')
                    quit()
            else:
                apipe = os.pipe()
                vpipe = os.pipe()
                fda = os.fdopen(apipe[1], 'wb', 1048576)
                fdv = os.fdopen(vpipe[1], 'wb', 1048576)
                playerfds = (apipe[0], vpipe[0])
                playerargs += '--audio-file=fd://%s ' % apipe[0]
                playerargs += 'fd://%s ' % vpipe[0]
                playerstdin = None
                # subprocess.PIPE
                ffmpegbase = None
                ffmpegmuxer = None
                ffmuxerstdout = None
            description = description.replace("'", "")
            if args.player == 'mpv':
                playerargs += (" --title='%s' " % title +
                               #'--start=%s ' % 60 +
                               "--osd-playing-msg='%s' " % description +
                               '--osd-font-size=%s ' % 25 +
                               '--osd-duration=%s ' % 20000 +
                               '--osd-align-x=center ' +
                               '--keep-open ')
                if manifesturl:
                    playerargs += ('--demuxer-lavf-analyzeduration=%s ' % int(segsecs * 3) +
                                   '--demuxer-max-back-bytes=%s ' % (backcachesize * 1048576) +
                                   '--cache-backbuffer=%s ' % (backcachesize * 1024) +
                                   '--demuxer-max-bytes=%s ' % (cachesize * 1048576) +
                                   '--demuxer-seekable-cache=yes ' +
                                   '--force-seekable=no ' +
                                   # '--cache-secs=%s ' % int(segsecs * 3) +
                                   # '--demuxer-readahead-secs=%s ' % int(segsecs * 3) +
                                   '--cache=%s ' % (cachesize * 256))
                else:
                    playerargs += ('--cache-initial=%s ' % 512 +
                                   '--cache-pause-initial=yes ')
            playercmd = args.player + playerargs
            logging.debug('PLAYER COMMANDS' + playercmd)
            player = subprocess.Popen(shlex.split(playercmd),
                                      # env=env,
                                      bufsize=1048576,
                                      shell=False,
                                      stdin=playerstdin,
                                      stdout=None,
                                      stderr=None,
                                      pass_fds=playerfds)
            playertries = 0
            while player.poll() is not None:
                logging.debug("WAITING PLAYER TO OPEN...")
                if playertries < 5:
                    time.sleep(1)
                else:
                    logging.info('Could not open the player, check args...')
                    quit()
                playertries += 1
            if ffmuxerstdout == "player":
                ffmuxerstdout = player.stdin
            # MAIN LOOP: ------------------------------------------------------#
            global headtimes, headnumbers, walltimemss, basedelays, pool
            excetries = 5
            asegmenturl = 0
            vsegmenturl = 0
            pool = None
            results = None
            cont = None
            delays = [0]
            truedelays = []
            mindelay = 100
            totaldelay = 0.0
            lastbands = []
            headnumbers = []
            basedelays = []
            headtimes = []
            walltimemss = []
            segmentlmt = 1
            firstrun = 1
            remainsegms = 0
            avgsecs = 20
            arrayheaderslim = int(avgsecs / segsecs) * 2
            basedelayavg = 0
            ended = 0
            abytes = 1025400
            vbytes = 0
            bandwidthup = 0
            bandwidthdown = 0
            ffmuxerdelay = 0
            bandwidthavg = 0
            remainsegms = 1
            skip = 0
            if not livecontent or otf:
                arraydelayslim = 3
            else:
                #apipe = 0
                arraydelayslim = 3
            ssegms = 1
            pool = ThreadPoolExecutor(max_workers=2 * maxsegms)
            while True:
                starttime = time.time()
                try:
                    sequencenums = []
                    logging.debug('SEQNUMBER: %s, ' % seqnumber +
                                  'REMAIN SEGMS: %s' % remainsegms)
                    # Media downloads imapping:
                    segmsresults = []
                    rpipes = []
                    numbsegms = min(max(remainsegms, minsegms), maxsegms)
                    for sid in range(numbsegms):
                        if not manifesturl:
                            segsecs = 5
                            amainurl = audiodata[aid]['url']
                            vmainurl = videodata[vid]['url']
                            vsegurl = asegurl = ''
                        else:
                            if not otf:
                                apipe = os.pipe()
                                rpipes.append([apipe[0]])
                                fda = os.fdopen(apipe[1], 'wb', 10485760)
                            else:
                                rpipes.append([0])
                            vpipe = os.pipe()
                            rpipes[sid].append(vpipe[0])
                            fdv = os.fdopen(vpipe[1], 'wb', 10485760)
                            amainurl = audiodata[aid][aidu].text
                            vmainurl = videodata[vid][0].text
                            if postlivedvr or otf:
                                if asegoffset:
                                    asegurl = audiodata[aid][2][-asegoffset].get(
                                                                        'media')
                                    asegoffset -= 1
                                if vsegoffset:
                                    vsegurl = videodata[vid][1][-vsegoffset].get(
                                                                       'media')
                                    vsegoffset -= 1
                                else:
                                    raise Ended
                            elif live:
                                if seqnumber:
                                    asegurl = vsegurl = "sq/" + str(seqnumber)
                                    seqnumber += 1
                                else:
                                    asegurl = vsegurl = ''

                        logging.debug('ASEGMENTURL: %s' % str(asegurl))
                        logging.debug('VSEGMENTURL: %s' % str(vsegurl))
                        gargs = [[amainurl, asegurl, fda, inita],
                                 [vmainurl, vsegurl, fdv, initv]]
                        ares = pool.submit(get_media,[amainurl, asegurl, fda,
                                            inita])
                        vres = pool.submit(get_media,[vmainurl, vsegurl, fdv,
                                            initv])
                        # athread = Thread(target=, args=('rout',)).start()
                        # vthread = Thread(target=get_media, args=('rout',)).start()
                        segmsresults.append((ares, vres))
                        # segmsresults.append(pool.imap(get_media, gargs))
                    # print('Sending pipes: %s, %s' % (apipe, vpipe))
                    playertries = 0
                    # Media Downloads results:
                    pid = 0
                    for segmresult in segmsresults:
                        ffmuxerstarttimer = time.time()
                        if ffmpegmuxer is not None:
                            logging.debug('Waiting ffmpeg muxer...')
                            ffmpegmuxer.wait()
                        ffmuxerdelay = round(time.time() - ffmuxerstarttimer, 4)
                        if manifesturl:
                            ffmpegmuxer = ffmuxer(args.ffmpeg, ffmuxerstdout,
                                                  rpipes[pid][0],
                                                  rpipes[pid][1])
                        for media in segmresult:
                            if type(media.result()) is tuple:
                                (status, contents, basedelay, headnumber,
                                 headtimems, sequencenum, walltimems,
                                 segmentlmt, contentlength, cachecontrol,
                                 bandwidthavg, bandwidthest, bandwidthest2,
                                 bandwidthest3, connection, contenttype,
                                 newurl, wbytes) = media.result()
                                if headnumber:
                                    headnumbers.append(int(headnumber))
                                if headtimems:
                                    headtimes.append(int(headtimems))
                                if walltimems:
                                    walltimemss.append(int(walltimems))
                                if status == 200 or status == 206:
                                    if contenttype == "video/mp4":
                                        vbytes += wbytes
                                        if newurl is not None:
                                            if not livecontent:
                                                videodata[vid]['url'] = newurl
                                            else:
                                                videodata[vid][0].text = newurl
                                        vconn = connection
                                    elif contenttype == "audio/mp4":
                                        abytes += wbytes
                                        if newurl is not None:
                                            if not livecontent:
                                                audiodata[aid]['url'] = newurl
                                            else:
                                                audiodata[aid][aidu].text = newurl

                                        aconn = connection
                                    if basedelay:
                                        basedelays.append(basedelay)
                                    if(not livecontent and
                                       wbytes == contentlength):
                                            ended = 1
                            elif media.result() == 1:
                                ended = 1
                        if ended:
                            raise Ended
                        closefds((rpipes[pid][0], rpipes[pid][1]))
                        pid += 1
                    # Limit Arrays
                    headtimes = headtimes[-arrayheaderslim:]
                    walltimemss = walltimemss[-arrayheaderslim:]
                    headnumbers = headnumbers[-arrayheaderslim:]
                    if headnumbers:
                        headnumber = max(headnumbers)
                        if not seqnumber:
                            seqnumber = headnumber + 1
                        remainsegms = max(headnumber - seqnumber, 0)
                    # Check links expiring time(secs remaining):
                    if cachecontrol:
                        expiresecs = re.search(
                            'private, max-age=(.*)', cachecontrol)
                        if expiresecs:
                            expiresecs = int(expiresecs.group(1))
                            logging.debug('URLS EXPIRING IN %s S' % expiresecs)
                        if expiresecs is not None and expiresecs <= 20:
                            logging.debug('URL Expired %s, refreshing metadata.'
                                         % expiresecs)
                            metadata = get_mediadata(videoid)
                            # print(metadata)
                            if metadata == 1 or metadata == 2:
                                break
                            else:
                                segsecs = metadata[0]
                                audiodata = metadata[1]
                                videodata = metadata[2]
                                buffersecs = metadata[3]
                                earliestseqnum = metadata[4]
                                startnumber = metadata[5]

                # EXCEPTIONS: -------------------------------------------------#
                except (Ended, KeyboardInterrupt, OSError):
                    if player.poll() is not None:
                        logging.info("Player Closed... ")
                    else:
                        if live:
                            aconn.close()
                            vconn.close()
                        logging.info('Streaming completed, waiting player...')
                        player.wait()
                    pool.shutdown(wait=True)
                    if ffmpegmuxer:
                        ffmpegmuxer.kill()
                        ffmpegmuxer.wait()
                    if ffmpegbase:
                        ffmpegbase.kill()
                        ffmpegbase.wait()
                    sys.stdout.flush()
                    os.closerange(3, 100)
                    break
                # Resyncing:
                if remainsegms > segmresynclimit:
                        seqnumber = headnumber - vsegoffset
                        logging.info('Resyncing...')
                # DELAYS: -----------------------------------------------------#
                # Min latency check:
                if not firstrun and mindelay > segsecs * 0.75:
                    logging.info('Min delay to high: %s seconds, ' % mindelay +
                                 'playback not realistic')
                basedelays = basedelays[-min(vsegoffset*2, 3*2):]
                if len(basedelays) > 0:
                    basedelayavg = round(sum(basedelays) / (
                                         2 * len(basedelays)), 4)
                    mindelay = min(min(basedelays) / 2, mindelay)
                    truedelay = round(delays[-1] - (max(basedelays[-2:])/2), 3)
                    truedelays.append(truedelay)
                    truedelays = truedelays[-arraydelayslim:]
                    truedelayavg = round(sum(truedelays) / len(truedelays), 3)
                if live:
                    ssegms = len(segmsresults)
                delay = round((time.time() - starttime - ffmuxerdelay) / ssegms,
                              4)
                delays.append(round(delay, 4))
                delays = delays[-arraydelayslim:]
                delayavg = round(sum(delays) / len(delays), 2)
                delaytogoup = max(round(segsecs / 3, 3), 1)
                threadsc = active_threads()
                logging.debug("--> DELAY TO UP: %s" % delaytogoup +
                      " Seconds \n" +
                      "--> BASEDELAYS: " + str(basedelays) + " Seconds \n" +
                      "--> BASEDELAY AVG: %s" % basedelayavg + " Seconds \n" +
                      "--> MIN DELAY: " + str(mindelay) + " Seconds \n" +
                      "--> DELAYS: " + str(delays) + " Seconds \n" +
                      "--> DELAY AVG: " + str(delayavg) + " Seconds \n" +
                      "--> FFMPEG DELAYS: %s \n" % str(ffmuxerdelay) +
                      "--> Threads Count: %s\n" % str(threadsc))
                # -------------------------------------------------------------#

                # BANDWIDTHS: -------------------------------------------------#
                if not args.fixed and (live or postlivedvr):
                    if bandwidthavg:
                        Bandwidths[0].append(round(bandwidthavg * 8, 1))
                    if bandwidthest:
                        Bandwidths[1].append(round(bandwidthest * 8, 1))
                    if bandwidthest2:
                        Bandwidths[2].append(round(bandwidthest2 * 8, 1))
                    if bandwidthest3:
                        Bandwidths[3].append(round(bandwidthest3 * 8, 1))
                    # Limit subarrays to min segments offset length:
                    for i in range(len(Bandwidths)):
                        Bandwidths[i] = Bandwidths[i][-arrayheaderslim:]
                        BandwidthsAvgs[i] = int(sum(Bandwidths[i]) /
                                                len(Bandwidths[i]))
                        lastbands.append(Bandwidths[i][-1])
                    lastbands = lastbands[-4:]
                    #
                    pvid = max(vid - 1, minvid)
                    prevbandwidthb = int(
                                        videodata[pvid].attrib.get('bandwidth'))
                    selectedbandwidthb = int(
                                         videodata[vid].attrib.get('bandwidth'))
                    selectedbandwidth = [selectedbandwidthb + 144000,
                                         ((selectedbandwidthb + 144000)/8)/1024]
                    selectedbandwidth[1] = round(selectedbandwidth[1], 1)
                    nvid = min(vid + 1, len(videodata) - 1)
                    nextbandwidthb = int(
                                        videodata[nvid].attrib.get('bandwidth'))
                    nextbandwidth = [nextbandwidthb + 144000,
                                     ((nextbandwidthb + 144000)/8) / 1024]
                    nextbandwidth[1] = round(nextbandwidth[1], 1)
                    # Min values:
                    if BandwidthsAvgs[0] and int(segsecs) <= 5:
                        startid = 1
                        endid = None
                    else:
                        startid = 1
                        endid = None
                    minband = min(BandwidthsAvgs[startid:endid])
                    minbandavg = (minband, round((minband/8)/1024))
                    minbandlast = min(lastbands[startid:endid])
                    minbandlast = (minbandlast, round((minbandlast/8)/1024))
                    bandslastavg = round(sum(lastbands[startid:endid]) /
                                         len(lastbands[startid:endid]))
                    bandslastavg = (bandslastavg, round((bandslastavg/8)/1024))
                    print('\t' * 10, end='\r', flush=True)
                    print("Bandwidth Last Avg/Min: %s kB/s / %s kB/s" %
                          (bandslastavg[1], minbandlast[1]),
                           end='\r', flush=True)
                    logging.debug("Bandwidth Avg: " + str(Bandwidths[0][-1]) +
                                 " bps " +
                                 str(int((Bandwidths[0][-1] / 8) / 1024)) +
                                 " kB/s ")
                    logging.debug("Bandwidth Est Avg: " +
                          str(int((BandwidthsAvgs[1] / 8) / 1024)) + " kB/s " +
                          "Last: " +
                          str(int((Bandwidths[1][-1] / 8) / 1024)) + " kB/s ")
                    logging.debug("Bandwidth Est2 Avg: " +
                          str(int((BandwidthsAvgs[2] / 8) / 1024)) + " kB/s " +
                          "Last: " +
                          str(int((Bandwidths[2][-1] / 8) / 1024)) + " kB/s ")
                    logging.debug("Bandwidth Est3 Avg: " +
                          str(int((BandwidthsAvgs[3] / 8) / 1024)) + " kB/s " +
                          "Last: " +
                          str(int((Bandwidths[3][-1] / 8) / 1024)) + " kB/s ")

                    bandwidthdown = 0
                    bandwidthup = 0
                    if(minbandlast[0] <= prevbandwidthb and
                       minbandlast[0] <= prevbandwidthb):
                            bandwidthdown = 1
                    else:
                        sensup = 1
                        if(minbandavg[0] > nextbandwidth[0] * sensup and
                           minbandlast[0] > nextbandwidth[0] * sensup):
                            bandwidthup = 1
                        logging.debug("Bandwidth UP: %s" % bandwidthup)
                    # bandwidthdown = 1
                    logging.debug("Bandwidth DOWN: %s" % bandwidthdown)
                    if firstrun:
                        firstrun = 0
                        aid, vid = get_quality_ids((audiodata, videodata),
                                                   Bandwidths)
                else:
                    bandwidthup = 1
                    bandwidthdown = 1
                # CHECK TO GO DOWN: -------------------------------------------#
                if(not args.fixed and vid > minvid and ffmuxerdelay < 1 and
                   bandwidthdown and delays[-1] <= segsecs * len(videodata) and
                   ((segsecs <= 2 and delayavg > segsecs * 1.0 and
                     delays[-1] > segsecs + 0.0) or
                        (segsecs > 2 and delayavg > segsecs and
                         delays[-1] > segsecs))):
                            bandwidthdown = 0
                            sys.stdout.write("\rDelays detected, switching to lower" +
                                  ' video quality...\r')
                            sys.stdout.flush()
                            inertia = int(max(round(delayavg / segsecs, 4), 1))
                            vid = int(max(minvid, vid - inertia))
                            if otf:
                                initvurl = videodata[vid][0].text
                                initvurl += videodata[vid][1][0].get(
                                                                    'sourceURL')
                                initv = session.get(initvurl).content
                                logging.debug('Initurl' + initvurl)
                            log_(("DOWN", vid, remainsegms, mindelay,
                                 ffmuxerdelay, delaytogoup, truedelays,
                                 truedelayavg, basedelays, basedelayavg, delays,
                                 delayavg, selectedbandwidth[1],
                                 nextbandwidth[1], minbandavg[1],
                                 minbandlast[1], bandslastavg[1],
                                 videodata[vid][0].text))
                            # delays = [0]
                            # continue
                if remainsegms <= 0 or remainsegms > 10:
                    elapsed3 = round(time.time() - starttime, 4)
                    logging.debug("---> TOTAL LOCAL DELAY: " + str(elapsed3))
                    # CHECK TO GO UP: -----------------------------------------#
                    # General check:
                    if(not args.fixed and vid < maxvid and bandwidthup and
                       basedelayavg < segsecs):
                                gcheck = True
                    else:
                        gcheck = False
                    logging.debug('GCHECK:' + str(gcheck))
                    # Check per live mode type:
                    if gcheck:
                        goup = 0
                        if live:
                            if lowlatency:
                                if(remainsegms == 0 and
                                   round(delayavg, 1) == segsecs):
                                        goup = 1
                            elif(delayavg < delaytogoup and delays[0] and
                                 delays[-1] < delaytogoup):
                                    goup = 1
                        elif(delayavg < delaytogoup and delays[0] and
                                 delays[-1] < delaytogoup):
                                    goup = 1
                        '''if not live and not lowlatency:
                            if(delayavg < delaytogoup and delays[0] and
                                 delays[-1] < delaytogoup):
                                    goup = 1'''

                        if goup:
                            sys.stdout.flush()
                            vid += 1
                            if otf:
                                initvurl = videodata[vid][0].text
                                initvurl += videodata[vid][1][0].get(
                                                                    'sourceURL')
                                # inita = session.get(initaurl).content
                                initv = session.get(initvurl).content
                                logging.debug('Initurl' + initvurl)

                            log_(("UP", vid, remainsegms, mindelay,
                                 ffmuxerdelay, delaytogoup, truedelays,
                                 truedelayavg, basedelays, basedelayavg, delays,
                                 delayavg, selectedbandwidth[1],
                                 nextbandwidth[1], minbandavg[1],
                                 minbandlast[1], bandslastavg[1],
                                 videodata[vid][0].text))
                    if player.poll() is not None:
                        print("Player Closed, quitting...")
                        break
                    if not lowlatency and live:
                        sleepsecs = max(round((segsecs) - delays[-1], 4), 0)
                        # sleepsecs = round(segsecs * 1.1, 4)
                        logging.debug("Sleeping %s seconds..." % sleepsecs)
                        time.sleep(sleepsecs)
            # After for:
            videoid = 0
    sys.stdout.flush()
    os.closerange(3, 100)
    os.remove('/tmp/dash2.0.pid')
