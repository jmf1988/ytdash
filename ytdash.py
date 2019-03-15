#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from threading import active_count as active_threads
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse, urlencode
import pycurl
import certifi
from io import BytesIO
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
# import chardet
try:
    import gtk
    maxwidth = gtk.gdk.screen_width()
    maxheight = gtk.gdk.screen_height()
except ImportError:
    pass


def time_type(string):
    #  timepattern=re.compile(r"^[0-9]+[h,s,m]{0,1}$")
    if not re.match(r"^[+,-]{0,1}[0-9]+[HhMmSs]+$|^$", string):
        raise argparse.ArgumentTypeError
    return string


def request(url=None, mode='body'):
    # HEADERS = ['Connection: Keep-Alive', 'Keep-Alive: 300']
    # rawheaders = BytesIO()
    # content = BytesIO()
    headers = 0
    curlobj = pycurl.Curl()
    curlobj.setopt(pycurl.VERBOSE, 0)
    # curlobj.setopt(pycurl.HEADER, 1)
    # curlobj.setopt(pycurl.ACCEPT_ENCODING, 'gzip, deflate')
    curlobj.setopt(pycurl.CONNECTTIMEOUT, 15)
    curlobj.setopt(pycurl.TIMEOUT, 30)
    curlobj.setopt(pycurl.TRANSFER_ENCODING, 1)
    # curlobj.setopt_string(CURLOPT_TCP_FASTOPEN, "1L")
    # curlobj.setopt(pycurl.RETURN_TRANSFER, True)
    curlobj.setopt(pycurl.TCP_KEEPALIVE, 1)
    curlobj.setopt(pycurl.PIPEWAIT, 1)
    # curlobj.setopt(pycurl.BUFFERSIZE, 1024)
    curlobj.setopt(pycurl.NOSIGNAL, 1)
    curlobj.setopt(pycurl.HEADER, 0)
    # curlobj.setopt(pycurl.KEEP_SENDING_ON_ERROR, 1)
    # curlobj.setopt(pycurl.HTTPHEADER, HEADERS)
    curlobj.setopt(pycurl.FOLLOWLOCATION, 1)
    curlobj.setopt(pycurl.CAINFO, certifi.where())
    # curlobj.setopt(pycurl.NOBODY, 0)
    if mode == 'head':
        curlobj.setopt(pycurl.NOBODY, 1)
    # elif mode == 'body':
        # content = BytesIO()
        # curlobj.setopt(curlobj.WRITEDATA, content)
    # curlobj.setopt(pycurl.HEADERFUNCTION, rawheaders.write)
    if url:
        curlobj.set_url(url)
        body = curlobj.get()
        status = curlobj.getinfo(pycurl.RESPONSE_CODE)
        headers = dict_from_bytes(body)
    return curlobj, headers


def dict_from_bytes(byteheaders):
    headers = {}
    byteheaders.seek(0)
    listheaders = byteheaders.read().decode('iso-8859-1').split('\r\n')
    for header in listheaders:
        if re.match(r'.*: .*', header):
            header = header.split(': ')
            headers[header[0]] = header[1]
    return headers


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


def get_mediadata(curlobj, videoid):
    # https://www.youtube.com/oembed?url=[Youtubewatchurl]&format=json
    url = 'https://www.youtube.com/get_video_info?video_id=' + videoid
    logging.debug('Opening URL: %s ' % url)
    curlobj.setopt(pycurl.URL, url)
    videoquery = curlobj.perform_rb().decode('iso-8859-1')
    # logging.debug('Video Query: %s ' % videoquery)
    status = curlobj.getinfo(pycurl.RESPONSE_CODE)
    if status != 200:
        logging.fatal('Http Error %s trying to get video info.' % status)
        return 1
    ytdict = parse_qs(videoquery, strict_parsing=False)
    if ytdict:
        metadata = {}
        otf = False
        streamtype = ytdict.get('qoe_cat')
        if streamtype:
            otf = True
        metadata['Otf'] = otf
        logging.debug('stream type: ' + str(streamtype))
    else:
        logging.info('Could not get main dictionary...')
        return 1
    ytpresp = json.loads(ytdict.get('player_response', [0])[0])
    if ytpresp:
        playable = ytpresp.get('playabilityStatus')
        pstatus = playable.get('status')
        reason = playable.get('reason')
        if pstatus and pstatus == 'UNPLAYABLE':
            logging.info('Video status: UNPLAYABLE')
            if reason:
                href = re.findall(r'(?<=href=").*?(?=")', reason)
                if href:
                    reco = re.findall(r'(?<=>).*?(?=<)', reason)
                    if reco:
                        reco = reco[0] + ' --> ' + href[0]
                        realreason = re.findall(r'(?<=\n).*$', reason)
                        if realreason:
                            reason = realreason[0] + '\n' + reco
                logging.info("Reason: %s" % reason)
            return 2
    else:
        logging.info('Could not extract player response data...')
        return 1
    logging.info("Video id: %s" % videoid)
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
        metadata.update(videodetails)
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
        if adaptivefmts:
            # logging.debug('ADAPTIVEFMTS: ' + str(adaptivefmts))
            adaptivefmts.sort(key=lambda fmt: fmt.get('bitrate', 0))
            nomanaudiodata = []
            nomanvideodata = []
            for fid in range(len(adaptivefmts)):
                mtype = adaptivefmts[fid]['mimeType'].split('; ')
                if mtype[0] == 'audio/mp4' and mtype[1][8:11] == 'mp4':
                    nomanaudiodata.append(adaptivefmts[fid])
                elif mtype[0] == 'video/mp4' and mtype[1][8:11] == 'avc':
                    if not streamtype:
                        streamtype = adaptivefmts[fid].get('type')
                    nomanvideodata.append(adaptivefmts[fid])
            # logging.debug('Videodata: %s' % nomanvideodata)
            if streamtype == 'FORMAT_STREAM_TYPE_OTF':
                otf = True
            metadata['Otf'] = otf
        logging.debug('OTF: ' + str(otf))
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
        audiodata = nomanaudiodata
        videodata = nomanvideodata
    # logging Details:
    logging.info('View count: ' + viewcount)
    logging.debug('postLiveDVR: ' + str(postlivedvr))
    logging.debug('reason: ' + str(reason))
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
    if manifesturl:
        manifesturl += '/keepalive/yes'
        logging.debug("Manifest URL: %s" % manifesturl)
        curlobj.setopt(pycurl.URL, manifesturl)
        rawmanifest = curlobj.perform_rb().decode('iso-8859-1')
        status = curlobj.getinfo(pycurl.RESPONSE_CODE)
        if status != 200:
            logging.info("Error getting manifest...")
            return 1
        # if reason:
        if postlivedvr and not args.offset:
            return 1
        tree = ET.fromstring(rawmanifest)
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
            return 2
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
           or videowidth > args.maxwidth or
           videoband / 8 > args.maxband * 1024):
            del videodata[idx]
        else:
            idx += 1
    logging.info("Total video Qualitys Choosen: %s" % len(videodata))
    return (segsecs, audiodata, videodata, buffersecs, earliestseqnum,
            startnumber, metadata)


def ffmuxer(ffmpegbin, ffmuxerstdout, apipe, vpipe):
    ffmpegargs = '%s -y -v %s -nostdin ' % (ffmpegbin, ffloglevel)
    ffmpegargsinputs = '-thread_queue_size 2000000 -flags +low_delay '
    if apipe:
        ffmpegargs += ffmpegargsinputs + '-i async:pipe:%s ' % apipe
        fds = (apipe, vpipe)
    else:
        fds = (vpipe,)
    ffmpegargs += ffmpegargsinputs + ' -i async:pipe:%s ' % vpipe
    ffmpegargs += '-f mpegts -bsf:v h264_mp4toannexb -c copy -copyts '
    ffmpegargs += '-flags +low_delay -'
    ffmpegmuxer = subprocess.Popen(shlex.split(ffmpegargs),
                                   bufsize=-1,
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
    return ffmpegmuxer


def get_media(data):
    baseurl, segmenturl, fd, curlobj, init = data
    retries503 = 5
    retries40x = 2
    conerr = 0
    twbytes = 0
    acceptranges = None
    headnumber = 0
    timeouts = (3.05, 0)
    headers = 0
    status = 0
    response = 0
    contentlength = totallength = 0
    end = 0
    walltimems = 0
    headtime = 0
    newurl = None
    rheaders = []
    initbyte = 0
    playerclosed = 0
    rawheaders = BytesIO()
    if not livecontent or not manifesturl:
        maxbytes = 524288
        # maxbytes = 30000
        curlobj.setopt(pycurl.RANGE, '%s-%s' % (initbyte, initbyte + maxbytes))
    else:
        maxbytes = 0
    while True:
        columns = os.get_terminal_size().columns
        try:
            if twbytes:
                sbyte = initbyte + int(twbytes)
                if maxbytes:
                    ebyte = sbyte + maxbytes
                    if totallength and ebyte > totallength:
                        ebyte = totallength
                else:
                    ebyte = ''
                curlobj.setopt(pycurl.RANGE, '%s-%s' % (sbyte, ebyte))
                logging.debug("Trying to resume from byte: %s to %s" % (sbyte,
                                                                        ebyte))
            gettime = time.time()
            url = baseurl + segmenturl
            curlobj.setopt(pycurl.URL, url)
            curlobj.setopt(curlobj.HEADERFUNCTION, rawheaders.write)

            if init != 1:
                # Write media content to ffmpeg or player pipes:
                if otf and not twbytes and init:
                    iwbytes = fd.write(init)
                curlobj.setopt(pycurl.NOBODY, 0)
                curlobj.setopt(pycurl.HEADER, 0)
                curlobj.setopt(pycurl.WRITEDATA, fd)

            else:
                curlobj.setopt(pycurl.NOBODY, 1)
            # curlobj.setopt(CURLOPT_CONNECTTIMEOUT, timeouts[0])
            # curlobj.setopt(pycurl.TIMEOUT, timeouts[1])
            # curlobj.setopt(pycurl.HTTPHEADER, rheaders)
            # curlobj.setopt(pycurl.NOSIGNAL, 0)
            try:
                logging.debug("Getting Media Content.....")
                # curlobj.setopt(pycurl.WRITEDATA, fd.write)
                # curlobj.setopt(pycurl.WRITEFUNCTION,
                #                   lambda data:  onrecv(fd, data) )
                curlobj.perform()
                # content = curlobj.get(url)
                if player.poll() is not None:
                    return 1
                logging.debug("WRITING TO PIPE: " + str(fd))
                # fd.write(content)
                fd.flush()
            except pycurl.error as err:
                logging.debug("Pycurl Exception Ocurred: %s Args: %s" %
                              (err, str(err.args)))
                curlerrnum = err.args[0]
                if curlerrnum == 18:
                    logging.debug("Partial content, Transmision ended...")
                    fd.close()
                    return 1
                if curlerrnum != 28:
                    time.sleep(segsecs)
            twbytes += int(curlobj.getinfo(pycurl.SIZE_DOWNLOAD))
            # basedelay = round((time.time() - gettime), 4)
            basedelay = curlobj.getinfo(pycurl.APPCONNECT_TIME)
            # Getting metadata from headers:
            headers = dict_from_bytes(rawheaders)
            # reqheaders = response.request.headers
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
                    end = 1
            if not totallength:
                totallength = headers.get('Content-Range', '').split('/')[-1]
                if totallength:
                    if totallength != '*':
                        totallength = int(totallength)
                    else:
                        totallength = ''
            contentlength = int(headers.get('Content-Length', 0))
            acceptranges = headers.get('Accept-Ranges', 0)
            cachecontrol = headers.get('Cache-Control', 0)
            headtimems = int(headers.get('X-Head-Time-Millis', 0))
            segmentlmt = int(headers.get('X-Segment-Lmt', 0))
            contenttype = headers.get('Content-Type', 0)
            if contenttype == 'video/mp4':
                speed = curlobj.getinfo(pycurl.SPEED_DOWNLOAD)
                totaltime = curlobj.getinfo(pycurl.TOTAL_TIME)

                print(' ' * columns, end='\r')
                ptext = ('\rDownload Speed AVG: %s kB/s' % int(speed / 1024) +
                         ' - Download duration: %s' % totaltime)
                print(ptext[0:columns], end='\r')
                logging.debug('SPEED AVG: -> %s <-' % int(speed / 1024))
                bandwidthavg = int(headers.get('X-Bandwidth-Avg', 0))
                bandwidthest = int(headers.get('X-Bandwidth-Est', 0))
                bandwidthest2 = int(headers.get('X-Bandwidth-Est2', 0))
                bandwidthest3 = int(headers.get('X-Bandwidth-Est3', 0))
            else:
                bandwidthavg = 0
                bandwidthest = 0
                bandwidthest2 = 0
                bandwidthest3 = 0

            status = curlobj.getinfo(pycurl.RESPONSE_CODE)
            if live or postlivedvr:
                # logging.debug('HEADERS: %s' % headers)
                # logging.debug('REQ HEADERS: %s' % reqheaders)
                # logging.debug("HEADTIMES : %s s %s ms" %
                #               (headtime, headtimems))
                logging.debug('HEADNUMBER: %s' % headnumber)
                logging.debug('SEQUENCENUMBER: %s' % sequencenum)
                # logging.debug("WALLTIMEMS  : %s" % (walltimems))
                # logging.debug("SEGMENT LMT: %s" % (segmentlmt))
                # logging.debug('ACCEPT-RANGES: %s' % acceptranges)
            logging.debug("CONTENT LENGTH: %s" % contentlength)
            logging.debug("TOTAL LENGTH: %s" % totallength)
            # Check status codes:
            if status == 200 or status == 206:
                retries503 = retries40x = 5
                # redirurl = curlobj.getinfo(pycurl.REDIRECT_URL)
                lasturl = curlobj.getinfo(pycurl.EFFECTIVE_URL)
                if not url == lasturl:
                    rurl = lasturl + "/"
                    if segmenturl:
                        baseurl = newurl = rurl.replace(segmenturl + "/", '')
                    elif not livecontent:
                        baseurl = rurl[0:-1]
                    logging.debug('SAVING NEW URL: %s' % newurl)
                if totallength and twbytes < totallength:
                    continue
                elif not manifesturl:
                    end = 1
                if not (otf and contenttype == 'audio/mp4'):
                    rawheaders.close()
                    fd.close()
                conntime = curlobj.getinfo(pycurl.CONNECT_TIME)

                # print('APPCONN TIME: %s ' % (conntime, totaltime))
                logging.debug('CONN TIME: %s ' % conntime)

                info = (status, basedelay, headnumber, headtimems,
                        sequencenum, walltimems, segmentlmt, contentlength,
                        cachecontrol, bandwidthavg, bandwidthest,
                        bandwidthest2, bandwidthest3,
                        contenttype, newurl, twbytes, end)
                logging.debug('Bytes written: %s' % twbytes)
                return info
            else:
                logging.debug('Status Code: %s' % status)
                # logging.debug('REQUEST HEADERS: %s' %
                #              response.request.headers)
                # logging.debug('HEADERS: %s' % response.headers)
                logging.debug("REQUEST URL: " + url)
                if status == 204:
                    logging.debug('Retrying in %s secs' % segsecs)
                if status == 503:
                    # curlobj.close()
                    if retries503:
                        logging.debug("Trying redirection...")
                        gvideohost = url.split('/')[2].split('.')[0]
                        url = url.replace(gvideohost, "redirector")
                        # retries503 -= 1
                elif(status == 404 or status == 400 or status == 403 or
                     not retries503):
                    if retries40x:
                        logging.debug('Refreshing video metadata...')
                        curlobj.setopt(pycurl.WRITEDATA, sys.stdout)
                        metadata = get_mediadata(curlobj, videoid)
                        if((type(metadata) is tuple and not
                           metadata[6].get('isLive')) or
                           type(metadata) is int and metadata == 1):
                            rawheaders.close()
                            logging.debug("Live event ended..")
                            fd.close()
                            return 1
                        else:
                            logging.debug("Live event still live..")
                        retries40x -= 1
                    else:
                        rawheaders.close()

                        fd.close()
                        return 2
                time.sleep(segsecs)
                continue
        except (BrokenPipeError) as oserr:
            logging.debug("Exception Ocurred: %s %s" % (oserr, str(oserr.args)))
            break


def closefds(totalpipes):
    fds = []
    if type(totalpipes) is list:
        for segmenttuples in totalpipes:
            if type(segmenttuples) is list:
                for pipetuple in segmenttuples:
                    if type(pipetuple) is tuple:
                        for fd in pipetuple:
                            if type(fd) is int:
                                fds.append(fd)
                    elif type(pipetuple) is int:
                        fds.append(fd)
            elif type(segmenttuples) is int:
                fds.append(segmenttuples)
    elif type(totalpipes) is int:
        fds.append(totalpipes)
    for fd in fds:
        try:
            if fd > 2:
                logging.debug('Closing fd: %s' % fd)
                os.close(fd)
        except OSError:
            pass


if __name__ == '__main__':
    global ffmpegmuxer, args, livecontent, live, otf, lowlatency, manifesturl
    global segsecs, videoid, minvid
    assert ('linux' in sys.platform), "This code runs on Linux only."
    parser = argparse.ArgumentParser(prog='ytdash',
                                     description='Youtube DASH video playback.')
    parser.add_argument('urls', metavar='URL|QUERY', type=str, nargs='+',
                        help='URLs or search queries of videos to play')
    parser.add_argument('--version', action='version', version='%(prog)s 0.12-alpha')
    parser.add_argument('-quiet', '-q', action='store_true',
                        help='enable quiet mode (default: %(default)s)')
    parser.add_argument('-search', '-s', action='store_true',
                        help='search mode (default: %(default)s)')
    parser.add_argument('-nonlive', '-nl', action='store_true',
                        help='search also non-live videos ' +
                        '(default: %(default)s)')
    parser.add_argument('-sortby', '-sb', type=str, default='relevance',
                        choices=['relevance', 'viewCount', 'videoCount', 'date',
                                 'rating', 'title', 'rating'],
                        help='sorting order for the search results ' +
                        '(default: %(default)s)')
    parser.add_argument('-eventtype', '-et', type=str, default='live',
                        choices=['live', 'upcoming', 'completed'],
                        help='filter results by live event type' +
                        '(default: %(default)s)')
    parser.add_argument('-safesearch', '-ss', type=str, default='moderate',
                        choices=['moderate', 'none', 'strict'],
                        help='Safe search mode to use if any' +
                        '(default: %(default)s)')
    parser.add_argument('-duration', '-dur', type=str, default='any',
                        choices=['any', 'long', 'medium', 'short'],
                        help='filter results by video duration' +
                        '(default: %(default)s)')
    parser.add_argument('-videotype', '-vt', type=str, default='any',
                        choices=['any', 'episode', 'movie'],
                        help='filter results by video type ' +
                        '(default: %(default)s)')
    parser.add_argument('-type', type=str, default='video',
                        choices=['video', 'channel', 'playlist'],
                        help='filter results by type of resource ' +
                        '(default: %(default)s)')
    parser.add_argument('-definition', '-vd', type=str, default='any',
                        choices=['hd', 'sd', 'any'],
                        help='filter results by video definition ' +
                        '(default: %(default)s)')
    parser.add_argument('-license', type=str, default='any',
                        choices=['creativeCommon', 'youtube', 'any'],
                        help='filter results by video livense type ' +
                        '(default: %(default)s)')
    parser.add_argument('-playlist', type=str, default='',
                        help=' Play urls found om filename playlist ' +
                        '(default: %(default)s)')
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
                        choices=[144, 240, 360, 480, 720, 1080, 1440, 2160,
                                 4320],
                        help='max video heigth to allow (default: %(default)s)')
    parser.add_argument('-maxwidth', '-mw', type=int, default=1280,
                        choices=[256, 426, 640, 854, 1280, 1920, 2560, 3840,
                                 7680],
                        help='max video width to allow (default: %(default)s)')
    parser.add_argument('-ffmpeg', '-ff', type=str, default='ffmpeg',
                        help='ffmpeg location route (default: %(default)s)')
    parser.add_argument('-fixed', '-f', action='store_true',
                        help='Play a fixed video quality instead of doing' +
                        ' bandwidth adaptive quality change, This is the max' +
                        ' set from options (default: %(default)s)')
    parser.add_argument('--offset', '-o', type=time_type, default='',
                        help='Time offset from where to start ' +
                        ' to play. can be negative or ' +
                        ' positive  (i.e: -o 2h, -o 210m, --offset 3000s or' +
                        ' --offset=-3h, -o=-5m, -o=-300s, for hours, minutes,' +
                        ' seconds respectively.) (default: %(default)s)')
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
        backcachesize = 5  # max back RAM cached media played/skipped to keep,Mb
        totalcachesize = backcachesize + cachesize
        playerbaseargs = (' --input-terminal=no ')
        #              ' --rebase-start-time=yes'
        #              '--profile=low-latency'
        if not args.debug:
            playerbaseargs += ' --really-quiet=yes '
    elif args.player == 'vlc':
        playerbaseargs = ' --file-caching=5000 '
    else:
        playerbaseargs = ' - '
    logging.debug('PLAYER CMD: ' + args.player + playerbaseargs)
    autoresync = 1  # Drop segments on high delays to keep live
    # CURL Session:
    session = pycurl.Curl()
    # session.setopt(pycurl.NOSIGNAL, 1)
    # session.headers['User-Agent'] += ' ytdash/0.1 (gzip)'
    session.setopt(pycurl.ACCEPT_ENCODING, 'gzip, deflate')
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
    # (X11; Linux x86_64)
    if args.playlist:
        with open(args.playlist, 'r') as fd:
            urls = fd.readlines()
        if not urls:
            logging.info('No urls found on given file.')
            quit()
    else:
        urls = args.urls
    # for urlid in range(len(urls)):
    while len(urls):
        playerargs = playerbaseargs
        url = urlparse(urls[0])
        urlquery = url.query
        if not args.offset:
            args.offset = parse_qs(url.query).get('t', [''])[0]
            if args.offset and args.offset[-1:] != 's':
                args.offset += 's'
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
                        logging.info('Channel URL given but search ' +
                                     'disabled, enable search mode to' +
                                     ' list videos found in it or use '
                                     ' directly a video url or id instead.')
                        quit()
        elif not args.search:
            if url.path and re.match(idre, url.path):
                videoid = url.path
            else:
                logging.info('Could not find a video or channel id' +
                             ' in the given string')
                quit()
        if videoid:
            apitype = 'videos'
        else:
            apibaseurl = 'https://www.googleapis.com/youtube/v3/'
            apiparams = {}
            apiparams['part'] = 'snippet'
            apiparams['key'] = 'AIzaSyAWOONC01ILGs4dh8vnCJDO4trYbFTH4zQ'
            apiurlchecklive = apibaseurl + 'videos?' + urlencode(apiparams)
            if userid:
                apitype = 'channels'
                apiparams['forUsername'] = userid
                apiurl = apibaseurl + apitype + '?' + urlencode(apiparams)
                session.setopt(pycurl.URL, apiurl)
                r = session.perform_rb()
                channelitems = json.loads(r).get('items')
                if channelitems:
                    channelid = channelitems[0].get('id')
                else:
                    logging.info('Could not get user channel id')
                    quit()
                del apiparams['forUsername']
            apitype = 'search'
            apiparams['type'] = 'video'
            apiparams['order'] = args.sortby
            if not args.nonlive:
                apiparams['eventType'] = args.eventtype
            apiparams['videoDimension'] = '2d'
            apiparams['regionCode'] = 'AR'
            apiparams['safeSearch'] = args.safesearch
            apiparams['videoDuration'] = args.duration
            apiparams['videoType'] = args.videotype
            apiparams['type'] = args.type
            apiparams['videoLicense'] = args.license
            apiparams['videoDefinition'] = args.definition  # high|any
            apiparams['maxResults'] = args.maxresults
            apiparams['videoEmbeddable'] = 'true'
            apiparams['videoSyndicated'] = 'true'
            if channelid:
                apiparams['channelId'] = channelid
            else:
                apiparams['q'] = args.urls[0]
            apiparams['fields'] = ('items(id,snippet/title,snippet/' +
                                   'channelTitle,snippet/description,' +
                                   'snippet/liveBroadcastContent)')
            apiurl = apibaseurl + apitype + '?' + urlencode(apiparams)
            try:
                session.setopt(pycurl.URL, apiurl)
                r = session.perform_rb().decode('UTF-8')
                logging.debug("API URL: " + apiurl)
                status = session.getinfo(pycurl.RESPONSE_CODE)
                if status != 200:
                    if status == 400:
                        reason = r['error']['message']
                        logging.info('Bad API request: ' + reason)
                    else:
                        logging.info('Error code %s API request ' + status)
                    quit()
            except pycurl.error as err:
                err = tuple(err.args)
                if err[0] == 6 or err[0] == 7:
                    logging.warn("Connection Error, Internet connection down?")
                else:
                    logging.warn("Pycurl Error: %s" % str(err))
                quit()
            # chardet.detect(r)['encoding']
            # input()
            items = json.loads(r).get('items')
            if items:
                print("Videos found:")
            else:
                print("No videos found.")
                quit()
            # while True:
            answer = None
            itemnum = 1
            videoids = []
            for item in items:
                columns = os.get_terminal_size().columns
                snippet = item['snippet']
                title = snippet['title'].replace('"', "\'")[:columns - 4:]
                videoids.append(item['id']['videoId'])
                # logging.debug('Title: %s' % title)
                channeltitle = snippet["channelTitle"]
                description = snippet['description'][:columns - 24:] + '...'
                # description = description.replace('"', "\'").replace('\\n', "")
                # logging.debug('Description: %s' % description)
                livebroad = snippet['liveBroadcastContent']
                if livebroad == 'none':
                    livebroad = False
                else:
                    livebroad = True
                print('%s) %s\n' % (itemnum, title) +
                      '    * Description: {}\n'.format(repr(description)) +
                      '    * Channel: %s\n' % channeltitle +
                      '    * Live: %s' % livebroad)
                itemnum += 1
            if args.search and len(items) > 1:
                print('Enter nº of video to play, press '
                      'Enter to play all from the first or "q" to exit.')
                while True:
                    answer = input()
                    if(re.match(r'^[0-9]+$', answer) and
                       0 < int(answer) <= len(items)):
                        answer = int(answer)
                    if type(answer) is int:
                        item = items[answer - 1]
                        break
                    elif answer == 'q' or answer == 'Q':
                        quit()
                    elif answer == '':
                        urls += videoids[1:]
                        videoid = videoids[0]
                        args.search = 0
                        break
                    else:
                        print('Invalid input, only integers from 1 to' +
                              ' %s are accepted...' % len(items))
            else:
                item = items[0]
            # title += ' - ' + channeltitle
            if not videoid:
                videoid = item['id']['videoId']
        # Get the manifest and all its Infos
        mediadata = get_mediadata(session, videoid)
        # print(metadata)
        if type(mediadata) is int:
            if mediadata == 1:
                print('Live Stream recently ended, retry with a timeoffset ' +
                      'to play from.')
            elif mediadata == 2:
                print('Live Stream not available.')
            del urls[0]
            continue
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
            livecontent = metadata.get('isLiveContent')  # media is/was live
            live = metadata.get('isLive')
            lowlatency = metadata.get('isLowLatencyLiveStream')
            livedvr = metadata.get('isLiveDvrEnabled')
            otf = metadata.get('Otf')
            manifesturl = metadata.get('ManifestUrl')
            # otf = 0
            # manifesturl = 0
        logging.debug("Start number: " + str(startnumber))
        # Check the Url and Get info from Headers:
        maxaid = len(audiodata) - 1
        maxvid = len(videodata) - 1
        minsegms = 3
        maxsegms = 3
        if live:
            if segsecs == 1:
                logging.info('--Live mode: ULTRA LOW LATENCY--')
            elif segsecs == 2:
                logging.info('--Live mode: LOW LATENCY--')
            elif segsecs == 5:
                logging.info('--Live mode: NORMAL LATENCY--')
                maxsegms = 3
                minsegms = 1
        else:
            maxsegms = 1
        logging.debug("Segment duration in secs: " + str(segsecs))
        if live or postlivedvr:
            if args.fixed:
                aid = maxaid
                vid = maxvid
            else:
                aid = 1
                vid = 1
            inita = 1
            initv = 1
            aidu = 1
            minvid = 1
            Bandwidths = [[0], [0], [0], [0]]
            logging.debug("Back buffer depth in secs: " + str(buffersecs))
            logging.debug("Earliest seq number: " + str(earliestseqnum))
            # max Nº of pending segments allowed before forcing resync:
            segmresynclimit = buffersecs/segsecs
            headnumber = len(audiodata[1][2]) + earliestseqnum - 1
            if startnumber > earliestseqnum:
                segmresynclimit = startnumber - earliestseqnum
                if vsegoffset > segmresynclimit:
                    vsegoffset = segmresynclimit - 1
            # elif starttime:
            #    seqnumber = startnumber +
            elif args.offset:
                offsetnum = args.offset[0:-1]
                offsetunit = args.offset[-1]
                if re.match('^[0-9]+$', offsetnum):
                    floffset = float(args.offset[0:-1])
                else:
                    print('Invalid time offset format...')
                    quit()
                if offsetunit == "h":
                    vsegoffset = int((floffset*3600)/segsecs)
                    if floffset > 4:
                        logging.debug('''The max back buffer hours is %s,
                                        playing
                                        from oldest segment available'''
                                      % str(buffersecs/3600))
                elif offsetunit == "m":
                    vsegoffset = int((floffset*60)/segsecs)
                    if floffset > 240:
                        logging.debug('''The max back buffer minutes is %s,
                                     playing from oldest segment available
                                     ''' % str(buffersecs/60))
                elif offsetunit == "s":
                    vsegoffset = int(int(floffset)/segsecs)
                    if floffset > buffersecs:
                        logging.debug('The max backbuffer seconds ' +
                                      'is %s, playing ' % buffersecs +
                                      'from there')
                elif re.match('^[0-9]+$', args.offset):
                    if headnumber - int(args.offset) >= earliestseqnum:
                        vsegoffset = int(args.offset)
                    else:
                        logging.debug("The oldest segment to " +
                                      "play is %s, playing " % buffersecs +
                                      "from there")
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
                logging.debug('ASEGOFFSET: %s' % asegoffset)
                initaurl = audiodata[aid][1].text
                initaurl += audiodata[aid][2][0].get('sourceURL')
                initvurl = videodata[vid][0].text
                initvurl += videodata[vid][1][0].get('sourceURL')
                session.setopt(pycurl.URL, initvurl)
                initv = session.perform_rb()
                session.setopt(pycurl.URL, initaurl)
                inita = session.perform_rb()
                logging.debug("IDS MEDIADATA %s %s" % (aid, vid))
                logging.debug("AUDIOMAINURL %s" % initaurl)
                logging.debug("VIDEOMAINURL %s" % initvurl)
            '''
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
            '''

            logging.debug('VSEGOFFSET: %s' % vsegoffset)

        # While End ---
        if manifesturl:
            analyzedur = int(segsecs * 1000000 * 2)
            ffbaseargs = args.ffmpeg + ' -v %s ' % ffloglevel
            ffbaseinputs = ' -thread_queue_size 150000 -flags +low_delay '
            ffbaseargs += ' -analyzeduration ' + str(analyzedur)
            if otf:
                apipe = os.pipe()
                fda = os.fdopen(apipe[1], 'wb', 1048576)
                ffbaseargs += ffbaseinputs + ' -i pipe:%s ' % apipe[0]
                fffds = (apipe[0],)
            else:
                fffds = ()
            ffbaseargs += ffbaseinputs + ' -i pipe:0 '
            ffbaseargs += ' -c copy -f nut '
            ffbaseargs += ' -bsf:v h264_mp4toannexb '
            ffbaseargs += ' -flags +low_delay pipe:1'
            ffmpegbase = subprocess.Popen(shlex.split(ffbaseargs),
                                          stdin=subprocess.PIPE,
                                          stdout=subprocess.PIPE,
                                          bufsize=-1,
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
            if args.player == 'mpv':
                # playerargs += '--audio-file=%s ' % audiodata[aid]['url']
                playerargs += '--audio-file=fd://%s' % apipe[0]
            elif args.player == 'vlc':
                # playerargs += '--input-slave="%s"' % audiodata[aid]['url']
                playerargs += '--input-slave=fd://%s ' % apipe[0]
            # playerargs += ' "%s" ' % videodata[vid]['url']
            playerargs += ' fd://%s ' % vpipe[0]
            playerstdin = None
            playerfds = (apipe[0], vpipe[0])
            # playerfds = ()
            ffmpegbase = None
            ffmpegmuxer = None
            ffmuxerstdout = None
        # fd2 = os.pipe()
        # fd3 = os.pipe()
        # fd4 = os.pipe()
        title = title.replace('"', "\'")
        description = description.replace('"', "\'")
        if args.player == 'mpv':
            playerargs += (' --title="%s" ' % (title + " - " + author) +
                           '--osd-playing-msg="%s" ' % description +
                           '--osd-font-size=%s ' % 25 +
                           '--osd-duration=%s ' % 20000 +
                           '--osd-align-x=center ' +
                           '--demuxer-max-bytes=%s ' %
                           (cachesize * 1048576) +
                           '--demuxer-seekable-cache=yes ' +
                           '--keep-open ')
            if args.offset:
                offsetnum, offsetunit = args.offset[0:-1], args.offset[-1]
                offsetsecs = int(offsetnum)
                if offsetunit == 'm':
                    offsetsecs *= 60
                elif offsetunit == 'h':
                    offsetsecs *= 3600
                playerargs += ' --start=%s ' % offsetsecs
            if manifesturl:
                playerargs += ('--demuxer-lavf-analyzeduration=%s ' %
                               int(segsecs * 3) +
                               '--cache-backbuffer=%s ' %
                               (backcachesize * 1024) +
                               '--force-seekable=no ' +
                               '--demuxer-max-back-bytes=%s ' %
                               (backcachesize * 1048576) +
                               '--cache=%s ' % (cachesize * 256))
            '''else:
                playerargs += ('--cache-initial=%s ' % 0 +
                               '--cache-pause-initial=no ')'''
        elif args.player == 'vlc':
            playerargs += (' --input-title-format "%s" ' % (title + " - " +
                                                            author) +
                           '--no-video-title-show '
                           )
        playercmd = args.player + playerargs
        logging.debug('PLAYER COMMANDS' + playercmd)
        player = subprocess.Popen(shlex.split(playercmd),
                                  # env=env,
                                  bufsize=-1,
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
        '''if not manifesturl:
            player.wait()
            continue'''
        if ffmuxerstdout == "player":
            ffmuxerstdout = player.stdin
        elif ffmpegbase and ffmpegbase.poll() is None:
            ffmpegbase.stdout.close()
        # MAIN LOOP: ------------------------------------------------------#
        delays = [0]
        truedelays = []
        mindelay = 3600
        totaldelay = 0.0
        lastbands = []
        headnumbers = []
        basedelays = []
        headtimes = []
        walltimemss = []
        firstrun = 1
        avgsecs = 20
        arrayheaderslim = int(avgsecs / segsecs) * 2
        basedelayavg = 0
        end = 0
        # abytes = 1025400
        # vbytes = 0
        bandwidthup = 0
        bandwidthdown = 0
        ffmuxerdelay = 0
        bandwidthavg = 0
        cachecontrol = 0
        if live or postlivedvr:
            remainsegms = 1
            # maxsegms = 3
        else:
            remainsegms = 1
            maxsegms = 1
        arraydelayslim = 3
        ssegms = 1
        aend = vend = 0
        # initv = inita = 1
        # maxsegms = 1
        twbytes = 0
        http_errors = False
        pool = ThreadPoolExecutor(max_workers=2 * maxsegms)
        segcurlobjs = []
        for sid in range(maxsegms):
            acurlobj = request()[0]
            vcurlobj = request()[0]
            segcurlobjs.append((vcurlobj, acurlobj))
        while True:
            starttime = time.time()
            columns = os.get_terminal_size().columns
            try:
                sequencenums = []
                logging.debug('SEQNUMBER: %s, ' % seqnumber +
                              'REMAIN SEGMS: %s' % remainsegms)
                # Media downloads imapping:
                segmsresults = []
                reqs = []
                rpipes = []
                numbsegms = min(max(remainsegms, minsegms), maxsegms)
                for sid in range(numbsegms):
                    if not manifesturl:
                        pipebuffer = 1048576
                        segsecs = 5
                        amainurl = audiodata[aid]['url']
                        vmainurl = videodata[vid]['url']
                        vsegurl = asegurl = ''
                        rpipes = (apipe, vpipe)
                        fda = os.fdopen(apipe[1], 'wb', pipebuffer)
                        initv = 0
                        inita = 0
                    else:
                        pipebuffer = 1048576
                        if initv and inita:
                            if live:
                                asegurl = vsegurl = ''
                        if not otf:
                            apipe = os.pipe()
                            rpipes.append([apipe[0]])
                            fda = os.fdopen(apipe[1], 'wb', pipebuffer)
                        else:
                            rpipes.append([0])
                        vpipe = os.pipe()
                        rpipes[sid].append(vpipe[0])
                        amainurl = audiodata[aid][aidu].text
                        vmainurl = videodata[vid][0].text
                        if postlivedvr or otf:
                            if asegoffset:
                                asegurl = audiodata[aid][2][-asegoffset]
                                asegurl = asegurl.get('media')
                            else:
                                aend = 1
                            if vsegoffset:
                                vsegurl = videodata[vid][1][-vsegoffset]
                                vsegurl = vsegurl.get('media')
                            else:
                                vend = 1
                            if otf or not initv == 1 == inita:
                                if not vend:
                                    vsegoffset -= 1
                                if not aend:
                                    asegoffset -= 1
                            if aend and vend:
                                raise Ended
                        elif live and initv == 0 == inita:
                            asegurl = vsegurl = "sq/%s" % seqnumber
                            seqnumber += 1
                    logging.debug('ASEGMENTURL: %s' % str(asegurl))
                    logging.debug('VSEGMENTURL: %s' % str(vsegurl))
                    # gargs = [[amainurl, asegurl, fda, inita],
                    #         [vmainurl, vsegurl, fdv, initv]]
                    fdv = os.fdopen(vpipe[1], 'wb', pipebuffer)
                    '''acurlobj = segcurlobjs[sid][0][0]
                    vcurlobj = segcurlobjs[sid][1][0]
                    aurl = amainurl + asegurl
                    vurl = vmainurl + vsegurl
                    acurlobj.setopt(pycurl.URL, aurl)
                    vcurlobj.setopt(pycurl.URL, vurl)
                    req = (aurl, segcurlobjs[sid][0][2],
                           segcurlobjs[sid][0][0])
                    curlmulti.add_handle(req[2])
                    reqs.append(req)
                    req = (vurl, segcurlobjs[sid][1][2],
                           segcurlobjs[sid][1][0])
                    curlmulti.add_handle(req[2])
                    reqs.append(req)
                    #acurlobj.setopt(pycurl.WRITEDATA, fda)
                    #vcurlobj.setopt(pycurl.WRITEDATA, fdv)
                    acurlobj.setopt(pycurl.WRITEFUNCTION,
                                    segcurlobjs[sid][0][2].write)
                    vcurlobj.setopt(pycurl.WRITEFUNCTION,
                                    segcurlobjs[sid][1][2].write)'''
                    # curlmulti.add_handle(segcurlobjs[sid][1][0])
                    ares = pool.submit(get_media, [amainurl, asegurl,
                                       fda, segcurlobjs[sid][0],
                                       inita])
                    vres = pool.submit(get_media, [vmainurl, vsegurl,
                                       fdv, segcurlobjs[sid][1],
                                       initv])
                    # athread = Thread(target=, args=('rout',)).start()
                    # vthread = Thread(target=get_media,
                    #                  args=('rout',)).start()
                    segmsresults.append((ares, vres))
                pid = 0
                for segmresult in segmsresults:
                    ffmuxerstarttimer = time.time()
                    if ffmpegmuxer is not None:
                        logging.debug('Waiting ffmpeg muxer...')
                        # Check if player was closed while waiting muxer:
                        while True:
                            try:
                                ffmpegmuxer.communicate(timeout=segsecs)
                                break
                            except subprocess.TimeoutExpired:
                                logging.debug('Checking player...')
                                if player.poll() is not None:
                                    raise Ended
                    ffmuxerdelay = round(time.time() - ffmuxerstarttimer, 4)
                    if manifesturl and not inita == initv == 1:
                        logging.debug('FFmpeg read pipes: %s, %s' %
                                      (rpipes[pid][0], rpipes[pid][1]))
                        ffmpegmuxer = ffmuxer(args.ffmpeg, ffmuxerstdout,
                                              rpipes[pid][0],
                                              rpipes[pid][1])
                    for media in segmresult:
                        if type(media.result()) is tuple:
                            (status, basedelay, headnumber,
                             headtimems, sequencenum, walltimems,
                             segmentlmt, contentlength, cachecontrol,
                             bandwidthavg, bandwidthest, bandwidthest2,
                             bandwidthest3, contenttype,
                             newurl, wbytes, end) = media.result()
                            if headnumber:
                                headnumbers.append(int(headnumber))
                            if headtimems:
                                headtimes.append(int(headtimems))
                            if walltimems:
                                walltimemss.append(int(walltimems))
                            if status == 200 or status == 206:
                                if contenttype == "video/mp4":
                                    # vbytes += wbytes
                                    if newurl is not None:
                                        if not manifesturl:
                                            videodata[vid]['url'] = newurl
                                        else:
                                            videodata[vid][0].text = newurl
                                elif contenttype == "audio/mp4":
                                    # abytes += wbytes
                                    if newurl is not None:
                                        if not manifesturl:
                                            audiodata[aid]['url'] = newurl
                                        else:
                                            audiodata[aid][1].text = newurl
                                if basedelay:
                                    basedelays.append(basedelay)
                                # if sequencenum:
                                #    sequencenums.append(sequencenum)
                        elif media.result() == 1:
                            end = True
                        elif media.result() == 2:
                            http_errors = True
                    if (otf or not inita == initv == 1) and manifesturl:
                        closefds(rpipes[pid])
                        pid += 1
                if end:
                    raise Ended
                if http_errors:
                    print(' ' * columns, end='\r')
                    logging.info('Too many http errors, quitting.')
                    break
                # Limit Arrays
                headtimes = headtimes[-arrayheaderslim:]
                walltimemss = walltimemss[-arrayheaderslim:]
                headnumbers = headnumbers[-arrayheaderslim:]
                if headnumbers:
                    headnumber = max(headnumbers)
                    if not seqnumber:
                        seqnumber = headnumber
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
                        metadata = get_mediadata(session, videoid)
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
            except (Ended):
                for curlobjs in segcurlobjs:
                    for curlobj in curlobjs:
                        curlobj = None
                if player.poll() is not None:
                    print(' ' * columns, end='\r')
                    logging.info("Player Closed... ")
                else:
                    print(' ' * columns, end='\r')
                    logging.info('Streaming completed, waiting player...')
                    player.communicate()
                    player.wait()
                for segmresult in segmsresults:
                    for media in segmresult:
                        media.cancel()
                pool.shutdown(wait=True)
                if ffmpegbase:
                    ffmpegbase.kill()
                    ffmpegbase.wait()
                if ffmpegmuxer:
                    ffmpegmuxer.kill()
                    ffmpegmuxer.wait()
                break
            # finally:
            #    closefds(rpipes)

            # Resyncing:
            if remainsegms > segmresynclimit:
                seqnumber = headnumber - vsegoffset
                print(' ' * columns, end='\r')
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
            delay = round((time.time() - starttime - ffmuxerdelay) / ssegms, 4)
            delays.append(round(delay, 4))
            delays = delays[-arraydelayslim:]
            delayavg = round(sum(delays) / len(delays), 2)
            delaytogoup = max(round(segsecs / 3, 3), 1)
            threadsc = active_threads()
            logging.debug("--> DELAY TO UP: %s seconds\n" % delaytogoup +
                          "--> BASEDELAYS: %s seconds\n" % basedelays +
                          "--> BASEDELAY AVG: %s seconds\n" % basedelayavg +
                          "--> MIN DELAY: %s seconds\n" % mindelay +
                          "--> DELAYS: %s" % delays +
                          "--> DELAY AVG: %s seconds\n" % delayavg +
                          "--> FFMPEG DELAYS: %s\n" % ffmuxerdelay +
                          "--> Threads Count: %s\n" % threadsc)
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
                print(' ' * columns, end='\r')
                ptext = ('\rBandwidth Last Avg/Min: %skB/s' % bandslastavg[1] +
                         ' / %skB/s ' % minbandlast[1] +
                         ' - Delay Avg/Last %ss / %ss' % (delayavg, delays[-1]))
                print(ptext[0:columns], end='\r', flush=True)
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
                logging.debug("Bandwidth DOWN: %s" % bandwidthdown)
                if inita and initv:
                    inita = 0
                    initv = 0
                    aid, vid = get_quality_ids((audiodata, videodata),
                                               Bandwidths)
            else:
                bandwidthup = 1
                bandwidthdown = 1
            bandwidthdown = 1
            # CHECK TO GO DOWN: -------------------------------------------#
            if(not args.fixed and vid > minvid and ffmuxerdelay < 1 and
               bandwidthdown and delays[-1] <= segsecs * len(videodata) and
               ((segsecs <= 2 and delayavg > segsecs * 1.3 and
                 delays[-1] > segsecs * 1.3) or
                (segsecs > 2 and delayavg > segsecs and
                 delays[-1] > segsecs))):
                print(' ' * columns, end='\r')
                print('\rDelays detected, switching to lower video quality...'
                      [0:columns], end='\r')
                inertia = int(max(round(delayavg / segsecs, 4), 1))
                vid = int(max(minvid, vid - inertia))
                if otf:
                    initvurl = videodata[vid][0].text
                    initvurl += videodata[vid][1][0].get(
                                                        'sourceURL')
                    session.setopt(pycurl.URL, initvurl)
                    initv = session.perform_rb()
                    logging.debug('Initurl' + initvurl)
                log_(("DOWN", vid, remainsegms, mindelay,
                     ffmuxerdelay, delaytogoup, truedelays,
                     truedelayavg, basedelays, basedelayavg, delays,
                     delayavg, selectedbandwidth[1],
                     nextbandwidth[1], minbandavg[1],
                     minbandlast[1], bandslastavg[1],
                     videodata[vid][0].text))
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
                    if goup:
                        print(' ' * columns, end='\r')
                        print('\rSwitching to higher video quality...'
                              [0:columns], end='\r')
                        vid += 1
                        if otf:
                            initvurl = videodata[vid][0].text
                            initvurl += videodata[vid][1][0].get('sourceURL')
                            session.setopt(pycurl.URL, initvurl)
                            initv = session.perform_rb()
                            logging.debug('Initurl' + initvurl)

                        log_(("UP", vid, remainsegms, mindelay,
                             ffmuxerdelay, delaytogoup, truedelays,
                             truedelayavg, basedelays, basedelayavg, delays,
                             delayavg, selectedbandwidth[1],
                             nextbandwidth[1], minbandavg[1],
                             minbandlast[1], bandslastavg[1],
                             videodata[vid][0].text))
                if not lowlatency and live:
                    sleepsecs = max(round((segsecs) - delays[-1], 4), 0)
                    logging.debug("Sleeping %s seconds..." % sleepsecs)
                    time.sleep(sleepsecs)
        # End While -
        del urls[0]
    sys.stdout.flush()
    os.closerange(3, 100)
    os.remove('/tmp/dash2.0.pid')
