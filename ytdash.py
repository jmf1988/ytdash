#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import active_count as active_threads
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET
from urllib.parse import parse_qs, urlparse, urlencode
from io import BytesIO
import pycurl
import certifi
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
    import gi
    gi.require_version('Gdk', '3.0')
    from gi.repository import Gdk
    w = Gdk.get_default_root_window()
    maxwidth, maxheight = w.get_geometry()[2:4]
    del gi
except ImportError:
    maxwidth, maxheight = 1360, 768
    pass


class Writer:
    def __init__(self, file):
        self.file = file
        
    def write(self, data):
        # sys.stderr.write(data)
        if player.poll() is not None:
            # fd.close()
            return 0
        try:
            self.file.write(data)
        except BrokenPipeError:
            return 0
  

class Ended(Exception):
    pass      


def time_type(string):
    #  timepattern=re.compile(r"^[0-9]+[h,s,m]{0,1}$")
    if not re.match(r"^[0-9]+[HhMmSs]$|^$", string):
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
    curlobj.setopt(pycurl.CONNECTTIMEOUT, 10)
    curlobj.setopt(pycurl.TIMEOUT, 30)
    # curlobj.setopt(pycurl.TRANSFER_ENCODING, 1)
    # curlobj.setopt_string(CURLOPT_TCP_FASTOPEN, "1L")
    # curlobj.setopt(pycurl.RETURN_TRANSFER, True)
    curlobj.setopt(pycurl.TCP_KEEPALIVE, 1)
    curlobj.setopt(pycurl.PIPEWAIT, 1)
    curlobj.setopt(pycurl.BUFFERSIZE, 524288)
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
                 SPEED: %s
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
    videoquery = curlobj.perform_rs()
    # logging.debug('Video Query: %s ' % videoquery)
    status = curlobj.getinfo(pycurl.RESPONSE_CODE)
    if status != 200:
        logging.fatal('Http Error %s trying to get video info.' % status)
        return 2
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
        logging.debug('Could not get main dictionary...')
        return 2
    ytpresp = json.loads(ytdict.get('player_response', [0])[0])
    if ytpresp:
        playable = ytpresp.get('playabilityStatus')
        pstatus = playable.get('status')
        reason = playable.get('reason')
        metadata['reason'] = reason
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
        logging.debug('Could not extract player response data...')
        return 2
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
            logging.debug('MaxBitrate: ' + maxbitrate)
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
        logging.debug('No streaming data found...')
        return 2
    if not latencyclass:
        latencyclass = videodetails.get('latencyClass')
        if latencyclass:
            latencyclass = re.findall('(?<=LATENCY_).+', latencyclass)
            metadata['latencyClass'] = latencyclass[0]
    if not livecontent or not manifesturl:
        audiodata = nomanaudiodata
        videodata = nomanvideodata
        cipher = 0
        nourls = 0
        if not audiodata[-1].get('url') or not videodata[-1].get('url'):
            logging.debug('Media Urls could not be found.')
            nourls = 1
            if audiodata[-1].get('cipher') or videodata[-1].get('cipher'):
                logging.debug('Ciphered url/s.')
                cipher = 1
        if nourls or cipher:
            return 2
    # logging Details:
    logging.info('Views count: ' + viewcount)
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
        curlobj.setopt(pycurl.ACCEPT_ENCODING, 'gzip, deflate')
        rawmanifest = curlobj.perform_rs()
        curlobj.setopt(pycurl.ACCEPT_ENCODING, None)
        status = curlobj.getinfo(pycurl.RESPONSE_CODE)
        if status != 200:
            logging.info("Error getting manifest content...")
            return 2
        # if reason:
        if postlivedvr and not args.offset:
            return 1
        MPD = ET.fromstring(rawmanifest)
        Period = MPD[0]
        SegmentList = MPD[0][0]
        startnumber = int(SegmentList.attrib.get('startNumber', 0))
        presentationTimeOffset = int(SegmentList.attrib.get(
                                                   'presentationTimeOffset', 0))
        periodstarttime = Period.get('start')
        if periodstarttime:
            periodstarttime = int(float(periodstarttime[2:-1]))
            metadata['start'] = periodstarttime
        earliestseqnum = int(MPD.get('{http://youtube.com/yt/2012/10/10}' +
                                     'earliestMediaSequence', 0))
        timescale = float(SegmentList.get('timescale', 0))
        buffersecs = MPD.get('timeShiftBufferDepth')
        if buffersecs:
            buffersecs = float(buffersecs[2:-1])
        minuperiod = Period.get('minimumUpdatePeriod')
        if minuperiod:
            segsecs = int(minuperiod[2:-1])
        elif timescale:
            segsecs = round(float(SegmentList[0][0].get('d')) / timescale)
        metadata['segmentsnumber'] = len(SegmentList[0])
        # Media Metadata:
        if otf:
            if not lowlatency:
                segsecs = 5
            ida = 0
            idv = 1
        else:
            ida = 1
            idv = 2
        audiodata = Period[ida].findall("[@mimeType='audio/mp4']/")
        videodata = Period[idv].findall("[@mimeType='video/mp4']/")
        # Sort by bandwidth needed:
        for mtype in audiodata, videodata:
            mtype.sort(key=lambda mid: int(mid.attrib.get('bandwidth', 0)))
        fps_string = 'frameRate'
    else:
        logging.debug('Dash Manifest URL not available.')
        logging.info('Bandwidth adaptative mode not available.')
        if adaptivefmts:
            logging.debug('Manifestless adaptative formats available.')
            fps_string = 'fps'
            segsecs = 5
            buffersecs, earliestseqnum, startnumber = 0, 0, 0
        else:
            logging.debug('No adaptative video formats found.')
            return 2
    logging.info("VIDEO IS LIVE: %s" % live)
    totvqua = len(videodata)
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
    if len(videodata) <= 1:
        logging.info('No video found with the requested properties.')
        return 2
    logging.info("Video qualities requested/available: %s/%s " %
                 (len(videodata), totvqua))
    return (latencyclass, audiodata, videodata, buffersecs, earliestseqnum,
            startnumber, metadata, segsecs)


def ffmuxer(ffmpegbin, ffmuxerstdout, apipe, vpipe):
    ffmpegargs = '%s -y -v %s -nostdin ' % (ffmpegbin, ffloglevel)
    ffmpegargsinputs = '-blocksize 512 -thread_queue_size 512 -flags +low_delay '
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
    errxxxr = err4xxr = 3  # Max retries when http errors.
    interruptretries = -1  # Infinite retry
    curlerr18retries = 3  # Happens sometimes when streaming ends
    twbytes = 0
    totallength = 0
    newurl = None
    initbyte = 0
    interrupted = 0
    reason = None
    if not livecontent or not manifesturl:
        curlobj.setopt(pycurl.TIMEOUT, 120)
        maxbytes = 524288
        curlobj.setopt(pycurl.RANGE, '%s-%s' % (initbyte, initbyte + maxbytes))
    else:
        maxbytes = 0
    while True:
        url = baseurl + segmenturl
        columns = os.get_terminal_size().columns
        rawheaders = BytesIO()
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
            curlobj.setopt(pycurl.URL, url)
            curlobj.setopt(curlobj.HEADERFUNCTION, rawheaders.write)
            if init != 1:
                # Write media content to ffmpeg or player pipes:
                if otf and not twbytes and init:
                    iwbytes = fd.write(init)
                curlobj.setopt(pycurl.NOBODY, 0)
                curlobj.setopt(pycurl.HEADER, 0)
                # curlobj.setopt(pycurl.WRITEDATA, fd)
                curlobj.setopt(pycurl.WRITEFUNCTION, Writer(fd).write)
            else:
                curlobj.setopt(pycurl.NOBODY, 1)
            logging.debug("Getting Media Content.....")
            # curlobj.setopt(pycurl.WRITEFUNCTION,
            #                   lambda data:  onrecv(fd, data) )
            if player.poll() is not None:
                return 1
            curlobj.perform()
            if interrupted:
                curlobj.setopt(pycurl.RANGE, None)
                interrupted = 0
            logging.debug("Saving content to: " + str(fd))
            # fd.write(content)
        except (BrokenPipeError, OSError) as oserr:
            logging.debug("Exception Ocurred: %s %s" % (oserr, str(oserr.args)))
            return 1
        except pycurl.error as err:
            logging.debug("Pycurl Exception Ocurred: %s Args: %s" %
                          (err, str(err.args)))
            curlerrnum = err.args[0]
            rawheaders.close()
            print(' ' * columns, end='\r')
            if curlerrnum == 18:
                logging.debug("Server closed connection with unknown data remaining...")
                if not curlerr18retries:
                    logging.debug("Curl error 18 retries exhausted, aborting...")
                    fd.close()
                    return 1
                curlerr18retries -= 1
                interrupted = 1
                time.sleep(1)
            elif curlerrnum == 23:
                logging.debug("Write error and player closed, quitting...")
                fd.close()
                return 1
            elif (curlerrnum == 7 or curlerrnum == 56):
                print('Download interrupted.', end='\r')
                if not interruptretries:
                    logging.info("Retries after interruption exhausted, " +
                                 "aborting...")
                    fd.close()
                    return 1
                interruptretries -= 1
                interrupted = 1
                time.sleep(1)
            elif curlerrnum == 6 or curlerrnum == 28:
                print('Could not resolve host or connection timed out,' +
                      'Internet connection issues?, retrying in 1 second...',
                      end='\r')
                time.sleep(1)
                continue
            else:
                logging.info("No handled pycurl error number, please report" +
                             " it, aborting...")
                fd.close()
                return 1
        twbytes += int(curlobj.getinfo(pycurl.SIZE_DOWNLOAD))
        if interrupted:
            if twbytes:
                logging.debug("Partial download, size: " + str(twbytes))
            continue
        basedelay = curlobj.getinfo(pycurl.APPCONNECT_TIME)
        # Getting metadata from headers:
        headers = dict_from_bytes(rawheaders)
        headnumber = int(headers.get('X-Head-Seqnum', 0))
        sequencenum = int(headers.get('X-Sequence-Num', 0))
        headtime = int(headers.get('X-Head-Time-Sec', 0))
        walltimems = int(headers.get('X-Walltime-Ms', 0))
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
        speed = curlobj.getinfo(pycurl.SPEED_DOWNLOAD)
        totaltime = curlobj.getinfo(pycurl.TOTAL_TIME)
        conntime = curlobj.getinfo(pycurl.CONNECT_TIME)
        logging.debug('Connect Delay: %s ' % conntime)
        print(' ' * columns, end='\r')
        ptext = ('\rDownload Speed AVG: %s kB/s' % int(speed / 1024) +
                 ' - Download duration: %s' % totaltime)
        print(ptext[0:columns], end='\r')
        logging.debug('Curl speed AVG: -> %s <-' % int(speed / 1024))
        if contenttype == 'video/mp4':
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
            logging.debug('Head Number: %s' % headnumber)
            logging.debug('Sequence Number: %s' % sequencenum)
            # logging.debug("WALLTIMEMS  : %s" % (walltimems))
            # logging.debug("SEGMENT LMT: %s" % (segmentlmt))
            # logging.debug('ACCEPT-RANGES: %s' % acceptranges)
        logging.debug("Content Length: %s" % contentlength)
        logging.debug("Total Length: %s" % totallength)
        # Check status codes:
        if status == 200 or status == 206:
            errxxxr = err4xxr = 3
            # redirurl = curlobj.getinfo(pycurl.REDIRECT_URL)
            lasturl = curlobj.getinfo(pycurl.EFFECTIVE_URL)
            if not url == lasturl:
                rurl = lasturl + "/"
                if segmenturl:
                    baseurl = newurl = rurl.replace(segmenturl + "/", '')
                elif not livecontent:
                    baseurl = rurl[0:-1]
                if newurl:
                    logging.debug('Saving new url: %s' % newurl)
            if totallength and twbytes < totallength:
                continue
            else:
                # All live and non-live non-otf close fds:
                if not (otf and contenttype == 'audio/mp4'):
                    rawheaders.close()
                    fd.close()
                # Non-live manifestless directly end it:
                if not manifesturl:
                    return 1
            info = (status, basedelay, headnumber, headtimems,
                    sequencenum, walltimems, segmentlmt, contentlength,
                    cachecontrol, bandwidthavg, bandwidthest,
                    bandwidthest2, bandwidthest3, speed,
                    contenttype, newurl, twbytes)
            logging.debug('Bytes written: %s' % twbytes)
            return info
        else:
            logging.debug('HTTP error status code: %s' % status)
            logging.debug("Request's URL: " + url)
            # If retries exhausted or Youtube give a reason of failure, quit:
            if not err4xxr or not errxxxr or reason:
                rawheaders.close()
                fd.close()
                return 2
            # In Normal latency live videos a segment may not be available yet:
            if live and status == 404 and int(segmenturl[3:]) > headnumber:
                logging.debug('Segment not available yet.')
                logging.debug('Retrying in 1 second')
                err4xxr -= 1
            else:
                # For all http errors refresh data and retry errxxxr times:
                if live:
                    logging.info('Http error: ' + str(status) +
                                 ', refreshing video metadata...')
                    curlobj.setopt(pycurl.WRITEDATA, sys.stdout)
                    metadata = get_mediadata(curlobj, videoid)
                    ended = False
                    if type(metadata) is int and metadata == 1:
                        ended = True
                    if type(metadata) is tuple:
                        islive = metadata[6].get('isLive')
                        reason = metadata[6].get('reason')
                        if not islive:
                            ended = True
                        elif reason:
                            logging.info("Youtube's reason: " + reason)
                        else:
                            logging.debug("Live event still live...")
                    del metadata
                    if ended:
                        logging.info("Live event ended...")
                        rawheaders.close()
                        fd.close()
                        return 1
                errxxxr -= 1
            # Wait 1 seconds to retry the request/s:
            time.sleep(1)


def closepipes(totalpipes):
    pipes = []
    t = type(totalpipes)
    if t is list or t is tuple:
        for segmenttuples in totalpipes:
            t = type(segmenttuples)
            if t is list or t is tuple:
                for pipetuple in segmenttuples:
                    t = type(pipetuple)
                    if t is list or t is tuple:
                        for fd in pipetuple:
                            if type(fd) is int:
                                pipes.append(fd)
                            else:
                                logging.debug('closepipes limit reached.')
                    elif t is int:
                        pipes.append(pipetuple)
            elif t is int:
                pipes.append(segmenttuples)
    elif t is int:
        pipes.append(totalpipes)
    for pipe in pipes:
        try:
            if pipe > 2:
                logging.debug('Closing pipe: %s' % pipe)
                os.close(pipe)
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
    parser.add_argument('--version', action='version', version='%(prog)s 0.15-alpha')
    parser.add_argument('-quiet', '-q', action='store_true',
                        help='enable quiet mode (default: %(default)s)')
    parser.add_argument('-search', '-s', action='store_true',
                        help='search mode, cached results enabled ' +
                        ' if searched less than 24hs ago, which saves ' +
                        'YouTube daily quota, recommended) (default: %(default)s)')
    parser.add_argument('-research', '-rs', action='store_true',
                        help='Search with cached results disabled. (default: %(default)s)')
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
    parser.add_argument('-playlist', action='store_true',
                        help=' Play urls found in file ' +
                        '(default: %(default)s)')
    parser.add_argument('-fullscreen', '-fs', action='store_true',
                        help=' Play urls found in file ' +
                        '(default: %(default)s)')
    parser.add_argument('-maxresults', '-mr', type=int, default=5,
                        help='search max results (default: %(default)s)')
    parser.add_argument('-debug', '-d', action='store_true',
                        help='enable debug mode  (default: %(default)s)')
    parser.add_argument('-player', '-p', type=str, default='mpv',
                        help='player bin name, (default: %(default)s)')
    parser.add_argument('-novolnor', '-nv', action='store_true',
                        help='disable volume normalization ' +
                        ' for all videos (mpv). (default: %(default)s)')
    parser.add_argument('-maxfps', '-mf', type=int, default=60,
                        help='max video fps to allow (default: %(default)s)')
    parser.add_argument('-maxband', '-mb', type=int, default=700,
                        help='max video bandwidth in kB/s to allow when ' +
                        ' possible (default: %(default)s)')
    parser.add_argument('-maxheight', '-mh', type=int, default=maxheight,
                        choices=[144, 240, 360, 480, 720, 1080, 1440, 2160,
                                 4320],
                        help='max video heigth to allow (default: %(default)s)')
    parser.add_argument('-maxwidth', '-mw', type=int, default=maxwidth,
                        choices=[256, 426, 640, 854, 1280, 1920, 2560, 3840,
                                 7680],
                        help='max video width to allow (default: %(default)s)')
    parser.add_argument('-ffmpeg', '-ff', type=str, default='ffmpeg',
                        help='ffmpeg location route (default: %(default)s)')
    parser.add_argument('-autoplay', action='store_true',
                        help='Autoplay all results returned by search mode ' +
                        '(default: %(default)s)')
    parser.add_argument('-reallive', '-r', action='store_true',
                        help='Enables lowest latency possible with ' +
                        'all types of live streams. ' +
                        '(default: %(default)s)')
    parser.add_argument('-fixed', '-f', action='store_true',
                        help='Play a fixed video quality instead of doing' +
                        ' bandwidth adaptive quality change, This is the max' +
                        ' set from options (default: %(default)s)')
    parser.add_argument('-offset', '-o', type=time_type, default='',
                        help='Time offset from where the playback start,' +
                        '(i.e: -o 2h, -o 210m, -offset 3000s, for hours,' +
                        ' minutes and seconds respectively.) ' +
                        '(default: 3 segments)')
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
    # Files:
    homedir = os.environ['HOME']
    logfile = homedir + '/.ytdash.log'
    logging.basicConfig(
        level=loglevel, filename=logfile, filemode="w+",
        format="%(asctime)-15s %(levelname)-8s %(message)s")
    console = logging.StreamHandler()
    console.setLevel(loglevel)
    # add the handler to the root logger
    logging.getLogger('').addHandler(console)
    logging.debug('Resolution detected: %s x %s' % (maxwidth, maxheight))
    # Check pid file:
    if os.path.isfile('/tmp/ytdash/ytdash.pid'):
        with open('/tmp/ytdash/ytdash.pid', 'r') as fd:
            prevpid = fd.read()
            if prevpid:
                try:
                    os.killpg(int(prevpid), signal.SIGTERM)
                    logging.info("Killed existing ytdash instance...")
                except ProcessLookupError:
                    logging.debug("Process does not exist...")
    else:
        if not os.path.isdir('/tmp/ytdash'):
            os.mkdir('/tmp/ytdash')
    os.setpgrp()
    with open('/tmp/ytdash/ytdash.pid', 'w') as fd:
        fd.write(str(os.getpgrp()))
    # Check cache dir exist:
    cachedir = homedir + '/.cache/ytdash/'
    if not os.path.isdir(cachedir):
        os.makedirs(cachedir)
    if (args.search or args.research) and args.playlist:
        logging.info('Search mode cannot be used together with playlist mode' +
                     ' please choose one')
        quit()
    if args.player == 'mpv':
        playerbaseargs = ' --input-terminal=no ' 
        #              ' --rebase-start-time=yes'
        #              '--profile=low-latency'
        if not args.novolnor:
            playerbaseargs += ' --af lavfi="[alimiter=limit=0.1:level=enabled]"'
        if args.fullscreen:
            playerbaseargs += ' --fullscreen '
        if not args.debug:
            playerbaseargs += ' --really-quiet=yes '
    elif args.player == 'vlc':
        playerbaseargs = ' --file-caching=5000 '
    else:
        playerbaseargs = ' - '
    logging.debug('PLAYER CMD: ' + args.player + playerbaseargs)
    # CURL Session:
    session = pycurl.Curl()
    session.setopt(pycurl.HTTPHEADER, ['User-Agent: ytdash/0.15'])
    defsegoffset = 3  # youtube's default segments offset.
    init = None
    ffmpegbase = None
    player = None
    videodata = None
    vid = 0
    aid = 0
    ffmpegmuxer = None
    BandwidthsAvgs = [0, 1, 2, 3]
    # (X11; Linux x86_64)
    if args.playlist:
        toturls = list()
        for playlist in args.urls:
            try:
                with open(playlist, 'r') as fd:
                    fileurls = fd.read().splitlines()
                    logging.debug("fileurls " + str(fileurls))
            except UnicodeDecodeError:
                logging.info('Invalid content on given file, skipping...')
            except FileNotFoundError as ferror:
                logging.info('No such file or directory: ' + playlist)
            else:
                if fileurls:
                    toturls += fileurls
        if not toturls:
            logging.info('No urls found in given file/s.')
            quit()
        else:
            urls = toturls
    else:
        urls = args.urls
    # for urlid in range(len(urls)):
    while len(urls):
        playerargs = playerbaseargs
        url = urlparse(urls[0])
        urlquery = url.query
        if url.fragment and args.playlist:
            print('Playlist track title:' + url.fragment)
            del urls[0]
            continue
        urlstartime = parse_qs(url.query).get('t', [''])[0]
        if urlstartime and urlstartime[-1:] != 's':
            urlstartime += 's'
        urlhost = url.hostname
        urlfolders = url.path.split('/')
        idre = re.compile('^[A-z0-9_-]{11}$')
        videoid = None
        channelid = None
        userid = None
        # If given string is not a video id, check if search mode is enabled:
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
                    if not args.search and not args.research:
                        logging.info('Channel URL given but search ' +
                                     'disabled, enable search mode to' +
                                     ' list videos found in it or use '
                                     ' directly a video url or id instead.')
                        del urls[0]
                        continue
        # Open directly if video id given with search enabled
        elif url.path and re.match(idre, url.path):
            videoid = url.path
        elif not args.search and not args.research:
            logging.info('Could not find a video or channel id' +
                         ' in the given string')
            del urls[0]
            continue
        # If the url given is not a youtube ID is a search query:
        if videoid:
            apitype = 'videos'
        else:
            apibaseurl = 'https://www.googleapis.com/youtube/v3/'
            apipar = {}
            apipar['part'] = 'snippet'
            apipar['key'] = 'AIzaSyAWOONC01ILGs4dh8vnCJDO4trYbFTH4zQ'
            apiurlchecklive = apibaseurl + 'videos?' + urlencode(apipar)
            if userid:
                apitype = 'channels'
                apipar['forUsername'] = userid
                apiurl = apibaseurl + apitype + '?' + urlencode(apipar)
                session.setopt(pycurl.URL, apiurl)
                r = session.perform_rb()
                channelitems = json.loads(r).get('items')
                if channelitems:
                    channelid = channelitems[0].get('id')
                else:
                    logging.info('Could not get user channel id')
                    quit()
                del apipar['forUsername']
            apitype = 'search'
            apipar['type'] = 'video'
            apipar['order'] = args.sortby
            if not args.nonlive:
                apipar['eventType'] = args.eventtype
            apipar['videoDimension'] = '2d'
            apipar['regionCode'] = 'AR'
            apipar['safeSearch'] = args.safesearch
            apipar['videoDuration'] = args.duration
            apipar['videoType'] = args.videotype
            apipar['type'] = args.type
            apipar['videoLicense'] = args.license
            apipar['videoDefinition'] = args.definition  # high|any
            apipar['maxResults'] = args.maxresults
            apipar['videoEmbeddable'] = 'true'
            apipar['videoSyndicated'] = 'true'
            searchcachefile = (cachedir + apipar['type'] + '+' +
                    apipar['videoType'] + '+' + apipar['eventType']  + '+' +
                    str(apipar['maxResults']) + '+' + apipar['videoDuration'] +
                    '+' + apipar['videoDefinition'] + '+' +
                    apipar['safeSearch'] + '+' + apipar['videoLicense'] + '+' +
                    str(apipar['order']) + '+')
            if channelid:
                apipar['channelId'] = channelid
                searchcachefile += channelid
            else:
                apipar['q'] = urls[0]
                searchcachefile += apipar['q']
            searchcachefile += '.cache'
            apipar['fields'] = ('items(id,snippet/title,snippet/' +
                                'channelTitle,snippet/description,' +
                                'snippet/liveBroadcastContent)')
            apiurl = apibaseurl + apitype + '?' + urlencode(apipar)
            # searchcachefile = ('/tmp/ytdash/' + re.sub('&.*?=', '+',
            #                   urlencode(apiparams)[5:250]) + '.cache')
            # Check if cached search query version if less than 1 day old:
            rjson = None
            if not os.path.isfile(searchcachefile):
                research = 1
            else:
                modtime = os.path.getmtime(searchcachefile)
                lifetime = (time.time() - modtime) / 3600
                with open(searchcachefile, 'r') as fd:
                    rjson = eval(str(fd.read()))
                if (lifetime > 24 or args.research or not rjson or
                    type(rjson) is not dict):
                        research = 1
                else:
                    research = 0
                    logging.info('Search query is cached, using it.')
            if research:
                try:
                    session.setopt(pycurl.URL, apiurl)
                    r = eval(session.perform_rs())
                    logging.debug("API URL: " + apiurl)
                    status = session.getinfo(pycurl.RESPONSE_CODE)
                    if status != 200:
                        logging.info('API error code: ' + str(status))
                        reason = r['error']['errors'][0]['reason']
                        message = r['error']['errors'][0]['message']
                        logging.info('API reason: ' + reason)
                        logging.info('API message: ' + message)
                        if ((reason == 'quotaExceeded' or
                             reason == 'dailyLimitExceeded') and rjson):
                                research = 0
                                logging.info('Using old cached version.')
                        elif len(args.urls) < 2:
                            quit()
                        else:
                            del urls[0]
                            continue
                    elif status == 200:
                        rjson = r
                    if rjson.get('items'):
                        with open(searchcachefile, 'w') as fd:
                            fd.write(str(rjson))
                except pycurl.error as err:
                    err = tuple(err.args)
                    if err[0] == 6 or err[0] == 7:
                        logging.warning("Connection Error, Internet connection down?")
                    else:
                        logging.warning("Pycurl Error: %s" % str(err))
                    quit()
            items = rjson.get('items')
            if items:
                print("Videos found:")
            else:
                print("No videos found.")
                del urls[0]
                continue
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
            if (args.search or args.research) and len(items) > 1:
                print('Enter nº of video to play, press '
                      'Enter to play all in order, "n" to search next ' +
                      'query if given or "q" to exit.')
                nextquery = 0
                while True:
                    if not args.autoplay:
                        answer = input()
                    else:
                        answer = ''
                    if(re.match(r'^[0-9]+$', answer) and
                       0 < int(answer) <= len(items)):
                        answer = int(answer)
                    if type(answer) is int:
                        item = items[answer - 1]
                        break
                    elif answer == 'n' or answer == 'N':
                        nextquery = 1
                        break
                    elif answer == 'q' or answer == 'Q':
                        quit()
                    elif answer == '':
                        del urls[0]
                        urls = videoids + urls
                        videoid = urls[0]
                        break
                    else:
                        print('Invalid input, only integers from 1 to' +
                              ' %s are accepted...' % len(items))
                if nextquery:
                    del urls[0]
                    continue
            else:
                item = items[0]
            # title += ' - ' + channeltitle
            if not videoid:
                videoid = item['id']['videoId']
        logging.info('#######################################')
        logging.info('Fetching data for video id: %s' % videoid)
        # Get video metada:
        mediadata = get_mediadata(session, videoid)
        if type(mediadata) is int:
            if mediadata == 1:
                logging.info('Live stream recently ended, retry with a ' +
                             'timeoffset to play it from.')
            elif mediadata == 2:
                logging.info('Unable to get all the video metadata needed.')
            del urls[0]
            if urls:
                logging.info('Skipping.')
            continue
        else:
            latencyclass = mediadata[0]
            audiodata = mediadata[1]
            videodata = mediadata[2]
            buffersecs = mediadata[3]
            earliestseqnum = mediadata[4]
            startnumber = mediadata[5]
            metadata = mediadata[6]
            segsecs = mediadata[7]
            periodstarttime = metadata.get('start')
            segmentsnumber = metadata.get('segmentsnumber')
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
        asegoffset = vsegoffset = remainsegms = defsegoffset
        maxaid = len(audiodata) - 1
        maxvid = len(videodata) - 1
        minsegms = 1
        maxsegms = 1
        analyzedur = 1000000
        #Player max cache in secs
        cachesecs = 120
        # max player backbuffer to conserve, in Mb
        backcachesize = 50 * 1048576
        # max player backbuffer to conserve, in Mb
        cachesize = 50 * 1048576
        if live:
            if latencyclass[0] == 'ULTRA LOW':
                logging.info('--Live mode: ULTRA LOW LATENCY--')
                segsecs = 1
            elif latencyclass[0] == 'LOW':
                logging.info('--Live mode: LOW LATENCY--')
                segsecs = 2
            elif latencyclass[0] == 'NORMAL':
                logging.info('--Live mode: NORMAL LATENCY--')
                minsegms = 1
                maxsegms = 1
                segsecs = 5
            if args.reallive:
                remainsegms = vsegoffset = 0
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
            # Limit backbuffer to youtube's max default in seconds (12h):
            if not periodstarttime:
                maxbackbuffersecs = segmentsnumber*segsecs
            else:
                maxbackbuffersecs = min(periodstarttime+buffersecs, 43200)
            # Limit of segment number to force resync :
            segmresynclimit = 43200/segsecs
            headnumber = len(audiodata[1][2]) + earliestseqnum
            fromzero = 0
            if startnumber > earliestseqnum:
                # This are forced live streams (without pause button, no offset)
                logging.info('Live stream type: Forced live')
                logging.info('Time offsets are disabled for this stream.')
                segmresynclimit = startnumber - earliestseqnum
                cachesecs = segmresynclimit * segsecs
                backcachesize = 0
                maxbackbuffersecs = segsecs * defsegoffset
            elif args.offset:
                # This is for live streams with backbuffer available:
                offsetnum = int(args.offset[0:-1])
                offsetunit = args.offset[-1]
                if offsetunit == "h":
                    secs = 3600
                elif offsetunit == "m":
                    secs = 60
                elif offsetunit == "s":
                    secs = 1
                # Filter time to the max allowed:
                offsetsecs = min(maxbackbuffersecs, offsetnum*secs)
                vsegoffset = asegoffset = int(offsetsecs/segsecs)
                if offsetsecs < offsetnum*secs:
                    if not startnumber:
                        fromzero = 1
                    logging.info('Maximum time offset available is ' +
                                 str(int(maxbackbuffersecs/secs)) +
                                 ', playing from there...')
                # vsegoffset = min(segmresynclimit, vsegoffset, headnumber)
            arraydelayslim = min(max(vsegoffset, 1), defsegoffset)
            seqnumber = int(headnumber - vsegoffset)
            logging.debug("Back buffer depth in secs: " + str(buffersecs))
            logging.debug("Earliest seq number: " + str(earliestseqnum))
            logging.debug('HEADNUMBER: %s, ' % headnumber +
                          'START NUMBER: %s, ' % startnumber +
                          'SEQNUMBER: %s, ' % seqnumber)

            logging.debug("AUDIOMAINURL %s" % audiodata[aid][1].text)
            logging.debug("VIDEOMAINURL %s" % videodata[vid][0].text)
        else:
            apipe = 0
            vid = int(len(videodata) / 1) - 1
            aidu = 1
            aid = -1
            minvid = 2
            headnumber = 999
            seqnumber = 0
            remainsegms = 0
            segmresynclimit = 99999
            arraydelayslim = 1
            selectedbandwidth = [0, 0]
            nextbandwidth = [0, 0]
            minbandavg = [0, 0]
            minbandlast = [0, 0]
            bandslastavg = [0, 0]
            bandwidthdown = 1
            bandwidthup = 1
            if otf:
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
            ffbaseargs = args.ffmpeg + ' -v %s ' % ffloglevel
            ffbaseinputs = ' -thread_queue_size 500 -flags +low_delay '
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
                playerargs += ' --audio-file=fd://%s ' % apipe[0]
            elif args.player == 'vlc':
                # playerargs += '--input-slave="%s"' % audiodata[aid]['url']
                playerargs += ' --input-slave=fd://%s ' % apipe[0]
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
        logging.info('Title: "%s"' % title )
        logging.info('Description: "%s"' % description )
        if args.player == 'mpv':
            playerargs += (' --title="%s" ' % (title + " - " + author) +
                           '--osd-playing-msg="%s" ' % description +
                           '--osd-font-size=%s ' % 25 +
                           '--osd-duration=%s ' % 
                           min(len(description) * 25, 10000) +
                           '--osd-align-x=center ' +
                           '--demuxer-max-bytes=%s ' % cachesize +
                           '--demuxer-seekable-cache=yes ' +
                           '--keep-open ')
            if urlstartime:
                offsetnum, offsetunit = urlstartime[0:-1], urlstartime[-1]
                offsetsecs = int(offsetnum)
                if offsetunit == 'm':
                    offsetsecs *= 60
                elif offsetunit == 'h':
                    offsetsecs *= 3600
                playerargs += ' --start=%s ' % offsetsecs
            if manifesturl:
                playerargs += ('--cache-secs=%s ' % cachesecs +
                               '--demuxer-max-back-bytes=%s ' % backcachesize +
                               '--demuxer-max-bytes=%s ' % cachesize )
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
        speeds = []
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
                if firstrun:
                    numbsegms = 1
                else:
                    numbsegms = min(max(remainsegms, minsegms), maxsegms)
                for sid in range(numbsegms):
                    if not manifesturl:
                        pipebuffer = 524288  # Same or less than maxbytes
                        segsecs = 5
                        # print("Audiodata: " + str(audiodata))
                        amainurl = audiodata[aid]['url']
                        vmainurl = videodata[vid]['url']
                        vsegurl = asegurl = ''
                        rpipes = (apipe, vpipe)
                        fda = os.fdopen(apipe[1], 'wb', pipebuffer)
                        initv = 0
                        inita = 0
                    else:
                        pipebuffer = 1024
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
                                ffmpegmuxer.communicate(timeout=1)
                                break
                            except subprocess.TimeoutExpired:
                                logging.debug('Checking player...')
                                if player.poll() is not None:
                                    end = 1
                                    break
                    ffmuxerdelay = round(time.time() - ffmuxerstarttimer, 4)
                    if not end and manifesturl and not inita == initv == 1:
                        logging.debug('FFmpeg read pipes: %s, %s' %
                                      (rpipes[pid][0], rpipes[pid][1]))
                        ffmpegmuxer = ffmuxer(args.ffmpeg, ffmuxerstdout,
                                              rpipes[pid][0],
                                              rpipes[pid][1])
                    for mediares in segmresult:
                        while True:
                            try:
                                result = mediares.result(timeout=1)
                                break
                            except TimeoutError:
                                logging.debug('Waiting download to complete...')
                                if player.poll() is not None:
                                    mediares.cancel()
                                    result = 1
                                    break
                        if type(result) is tuple:
                            (status, basedelay, headnumber,
                             headtimems, sequencenum, walltimems,
                             segmentlmt, contentlength, cachecontrol,
                             bandwidthavg, bandwidthest, bandwidthest2,
                             bandwidthest3, speed, contenttype,
                             newurl, wbytes) = result
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
                                speeds.append(speed)
                                # if sequencenum:
                                #    sequencenums.append(sequencenum)
                        elif result == 1:
                            end = True
                        elif result == 2:
                            http_errors = True
                    if otf or manifesturl:
                        closepipes(rpipes[pid])
                        pid += 1
                if http_errors:
                    print(' ' * columns, end='\r')
                    logging.info('Too many http errors, YouTube '
                                 'server issues?, quitting.')
                if end or http_errors:
                    raise Ended
                # Limit Arrays
                headtimes = headtimes[-arrayheaderslim:]
                walltimemss = walltimemss[-arrayheaderslim:]
                headnumbers = headnumbers[-arrayheaderslim:]
                if headnumbers:
                    headnumber = max(headnumbers)
                    if not firstrun:
                        remainsegms = max(headnumber - seqnumber, 0)
                    elif fromzero:
                        seqnumber = 0
                        fromzero = 0
                    else:
                        seqnumber = headnumber - vsegoffset
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
                firstrun = 0
                basedelays = basedelays[-arraydelayslim * 2:]
                if len(basedelays) > 0:
                    basedelayavg = round(sum(basedelays) / (
                                         2 * len(basedelays)), 4)
                    mindelay = min(min(basedelays) / 2, mindelay)
                    truedelay = round(delays[-1] - (max(basedelays[-2:])/2), 3)
                    truedelays.append(truedelay)
                    truedelays = truedelays[-arraydelayslim:]
                    truedelayavg = round(sum(truedelays) / len(truedelays), 3)
                if live or postlivedvr:
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
                speeds = speeds[-arraydelayslim:]
                speed = max(speeds)
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
                           ((speed * 8) + minbandavg[0]) / 2 > nextbandwidth[0] * sensup and
                           minbandlast[0] > nextbandwidth[0] * sensup):
                            bandwidthup = 1
                        logging.debug("Bandwidth UP: %s" % bandwidthup)
                    logging.debug("Bandwidth DOWN: %s" % bandwidthdown)
                else:
                    bandwidthup = 1
                    bandwidthdown = 1
                bandwidthdown = 1
                if inita and initv:
                    inita = 0
                    initv = 0
                    if not args.fixed:
                        aid, vid = get_quality_ids((audiodata, videodata),
                                                   Bandwidths)
                # CHECK TO GO DOWN: -------------------------------------------#
                if(not args.fixed and vid > minvid and ffmuxerdelay < 1 and
                   bandwidthdown and delays[-1] <= segsecs * len(videodata) and
                   ((segsecs <= 2 and delayavg > segsecs * 1.2 and
                     delays[-1] > segsecs * 1.2) or
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
                         minbandlast[1], bandslastavg[1], speed,
                         videodata[vid][0].text))
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
                        if lowlatency and not args.offset:
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
                             minbandlast[1], bandslastavg[1], speed,
                             videodata[vid][0].text))
                if remainsegms <= 0 and not lowlatency and live:
                    sleepsecs = max(round((segsecs) - delays[-1] + 0.100, 4), 0)
                    logging.debug("Sleeping %s seconds..." % sleepsecs)
                    while sleepsecs > 0:
                        if player.poll() is not None:
                            raise Ended
                        partialsecs = min(1,max(round(sleepsecs, 4),0))
                        sleepsecs -= 1
                        if partialsecs:
                            logging.debug("Waiting %s sec..." % partialsecs )
                            time.sleep(partialsecs)
            # EXCEPTIONS: -------------------------------------------------#
            except Ended:
                if player.poll() is not None:
                    print(' ' * columns, end='\r')
                    playclosemess = 'Player closed'
                    if len(urls) > 1:
                        playclosemess += ', playing next video...'
                    else:
                        playclosemess += ', no more videos to play.'
                    logging.info(playclosemess)
                else:
                    print(' ' * columns, end='\r')
                    logging.info('Streaming completed, waiting player...')
                    player.communicate()
                    player.wait()
                if playerfds:
                    closepipes(playerfds)
                # This has to be after closing players pipes or it hangs:
                pool.shutdown(wait=True)
                if ffmpegbase:
                    ffmpegbase.kill()
                    ffmpegbase.wait()
                if ffmpegmuxer:
                    ffmpegmuxer.kill()
                    ffmpegmuxer.wait()
                break
        # End While -
        del urls[0]
    sys.stdout.flush()
    os.closerange(3, 100)
    os.remove('/tmp/ytdash/ytdash.pid')
