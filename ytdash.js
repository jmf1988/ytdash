#!/usr/bin/env node
/*jshint esversion: 8 */
"use strict";
const http = require('https'),
      net = require('net'),
      child_process = require('child_process'),
      parseString = require('xml2js').parseString,
      zlib = require('zlib'),
      keepAliveAgent = new http.Agent({ keepAlive: true, scheduling: 'fifo' }),
      apiKey='AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
      metadataUrl = 'https://www.youtube.com/youtubei/v1/player?key=' + apiKey,
      args = process.argv.slice(2),
      ffmpegURI = '/usr/bin/ffmpeg',
      debug = args.includes('-debug');

// Variables:
let     ffbaseinputs = '',
        ffbaseargs = '',
        ffmuxinargs,
        ffmuxoutargs,
        urlPassthrough=1,
        ffmuxargs,
        playlist_entry_id=1,
        ffmpegbase,
        next=0,
        Id,
        maxWidth = 1360,
        maxFps = 60,
        maxHeight = 720;
var httpRetries = 5,
        client;
// ffmpeg base Args (all single spaces or ffmpeg fails 'cause split()):
ffbaseargs += ffbaseinputs + '-y -v 0 -flags +low_delay -thread_queue_size 512 -i -';
ffbaseargs += ' -c copy -f nut -bsf:v h264_mp4toannexb';
ffbaseargs += ' -flags +low_delay -';
// ffmpeg muxer:
ffmuxinargs = ' -thread_queue_size 100512 -flags +low_delay -i ';
ffmuxoutargs = ' -c copy -copyts -flags +low_delay -f mpegts ';
ffmuxargs = '-v warning -nostdin -xerror' +
            ffmuxinargs + 'async:pipe:3' +
            ffmuxinargs + 'async:pipe:4' +
            ffmuxoutargs + 'pipe:1';
//-tune zerolatency -write_index 0 -f_strict experimental -syncpoints timestamped
const mpvargs =   '--idle ' +
                  '--input-ipc-server=/tmp/mpvsocket ' +
                  '--player-operation-mode=pseudo-gui ' +
                  '--profile=low-latency ' +
                  //'--demuxer-lavf-linearize-timestamps=yes ' +
                  //'--demuxer-seekable-cache=yes ' +
                  '--demuxer-max-bytes=' + 50 * 1048576 + ' ' +
                  '--demuxer-max-back-bytes=' + 50 * 1048576 + ' ' +
                  '--cache=yes ' +
                  '--cache-secs=300 ' +
                  '--loop-playlist=force ' +
                  '--prefetch-playlist=yes ' +
                  //'--playlist=fd://0 ' +
                  //'--audio-file=fd://3' +
                  //' fd://3 ' +
                  //'--reset-on-next-file=all ' +
                  '--video-latency-hacks=yes ' +
                  //'--af=lavfi="[alimiter=limit=0.9:level=enabled]" ' +
                  '--audio-normalize-downmix=yes ' +
                  '--af=lavfi=[loudnorm=I=-22:TP=-1.5:LRA=2] ' +
                  //'--demuxer-lavf-o-add=fflags=+nobuffer ' +
                  //'--no-correct-pts ' + // a/v desync on seeking
                  //'--untimed ' +
                  //'--fps=60 ' +
                  //'--demuxer-lavf-probe-info=nostreams ' +
                  //'--demuxer-lavf-analyzeduration=0.1 ' +
                  //'--framedrop=no ' +
                  //'--input-ipc-client=fd://3 ' +
                 //'--really-quiet'+
                 //' - ' +
                 '--keep-open';

const metaPostdata = {"context":
                        {"client":
                            {"hl": "en", "clientName": "WEB",
                             "clientVersion": "2.20210721.00.00",
                             "mainAppWebInfo": {"graftUrl": 0}
                            }
                        },"videoId": 0
                    };

const metaPostHeaders = {
             'Accept': 'application/json',
             'Authorization': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
             'Content-Type': 'application/json'
           };

async function getMetadata(url, headers={}) {
    let mediaMetadata = {},
        adaptiveMediaFormats = {},
        postRes,
        jsonResponse,
        videoDetails,
        playabilityStatus,
        streamingData,
        formats,
        adaptiveFormats,
        latencyClass,
        dashManifestURL,
        dashManifestRawBody,
        dashManifest,
        audioMetadata,
        videoMetadata,
        audioFormatMetadata,
        videoFormatMetadata;
    if(debug){console.debug('PRE POST.');}
    postRes = await request(url, 'POST', headers);
    //await new Promise((r)=>{setTimeout(r, 5000)});
    if(debug){console.debug('POST POST.');}
    jsonResponse = JSON.parse(postRes[1]);
    //console.dir(jsonResponse.microformat);
    videoDetails = jsonResponse.videoDetails;
    playabilityStatus = jsonResponse.playabilityStatus;
    if (playabilityStatus.status !== 'OK'){
        console.info('Stream status: %o', playabilityStatus.status);
        console.info('Reason: %o', playabilityStatus.reason);
        return 1;
    }
    streamingData = jsonResponse.streamingData;
    //console.dir(streamingData);
    mediaMetadata.expiresInSeconds = streamingData.expiresInSeconds;
    formats = streamingData.formats;
    adaptiveFormats = streamingData.adaptiveFormats;
    //.sort((a,b)=>{return a.height-b.height;});
    // Get and log video Details:
    mediaMetadata.isLive = videoDetails.isLive;
    mediaMetadata.title = videoDetails.title.replace(/,/g,';');
    mediaMetadata.author = videoDetails.author.replace(/,/g,';');
    latencyClass = videoDetails.latencyClass;
    if (!videoDetails.isLive) {
        console.warn('Non-live videos have slow download because of Youtube rules so video bandwidth adaptive mode is disabled.');
    }
    //console.log("VideoID: %o", videoId);
    console.info("Status: %o", playabilityStatus.status);
    console.info('Title: %o', videoDetails.title);
    console.info('Author: %o', videoDetails.author);
    console.info('Is Live: ', (videoDetails.isLive||false));
    if (latencyClass) {
        mediaMetadata.latencyClass = latencyClass.slice(42).replace('_',' ');
        console.info('Latency Class: %o', mediaMetadata.latencyClass);
    }
    console.info('Channel Id: %o', videoDetails.channelId);
    console.info('Views: ', Number(videoDetails.viewCount));
    if (videoDetails.shortDescription) {
        console.info('Short Description:');
        console.info(videoDetails.shortDescription);
        //console.dir(console.dir(videoDetails.shortDescription.replace('\n\' \+', '')));
    }
    if (videoDetails.isLive){
        dashManifestURL = streamingData.dashManifestUrl;
        if(debug){console.debug('DASH Manifest URL:'+ dashManifestURL);}
        // Request manifest compressed 'cause too big:
        dashManifestRawBody = await request(dashManifestURL, 'GET',
                                         {'Accept-Encoding' : 'gzip'}
                                        );
        parseString(zlib.gunzipSync(
                    dashManifestRawBody[1]),
                    function (err, result) {
                            dashManifest = result;
        });
        audioMetadata = dashManifest.MPD.Period[0].AdaptationSet[0];
        videoMetadata = dashManifest.MPD.Period[0].AdaptationSet[1];
        mediaMetadata.audio = audioMetadata.Representation;
        // filter video by metadata:
        mediaMetadata.video = videoMetadata.Representation.filter(
                                            v=>v.$.height <= maxHeight);
        mediaMetadata.video = mediaMetadata.video.filter(
                                            v=>v.$.width <= maxWidth);
        mediaMetadata.video = mediaMetadata.video.filter(
                                            v=>v.$.frameRate <= maxFps);
        //Sort video qualities by bandwidth;
        mediaMetadata.video.sort((a,b)=>{return a.$.bandwidth-b.$.bandwidth;});
        mediaMetadata.audio.sort((a,b)=>{return a.$.bandwidth-b.$.bandwidth;});
    }else {
        adaptiveFormats.sort((a,b)=>{return a.bitrate-b.bitrate;});
        // Filter and create registers by type, container and codec:
        for (let format of adaptiveFormats){
            if (format.width > maxWidth) continue;
            if (format.height > maxHeight) continue;
            if (format.fps > maxFps) continue;
            let mimeType = format.mimeType.split('; ');
            let typeContainer = mimeType[0].split('/');
            let codecs = mimeType[1].split('=')[1];
            let type = typeContainer[0];
            let container = typeContainer[1];
            let codec = codecs.slice(1,-1).split('.')[0];
            let formatType = format.type;
            if (!mediaMetadata[type]) {
                    mediaMetadata[type]={};
            }
            if (!mediaMetadata[type][container]){
                    mediaMetadata[type][container]={};
            }
            if (!mediaMetadata[type][container][codec]){
                    mediaMetadata[type][container][codec]=[];
            }
            // filter out OTF streams url give 503 Error :
            if (formatType !== 'FORMAT_STREAM_TYPE_OTF'){
                mediaMetadata[type][container][codec].push(format);
                //mediaMetadata[type][container][codec].filter
            }
            let printStr='Found mimeType: ' + typeContainer +
                         " Codec: " + codecs + ' ';
            if (type==='audio') {
                printStr += format.audioQuality;
            } else {
                printStr += format.qualityLabel + ' Fps: ' +
                format.fps + ' Duration: ' +
                (format.approxDurationMs/1000/60).toFixed(2) + ' Min';
                if (formatType){
                    printStr += ' Stream Type: ' + formatType.split('_').at(-1);
                }
            }
            if(debug){console.debug(printStr);}
        }
    }
    // Change url to redirectors:
    //u.protocol + '//redirector.' + 'googlevideo.com' + u.pathname + u.search
    return mediaMetadata;
}

async function request(url, type='GET', headers={}, ioo=0, ffmpeg) {
    if(debug){console.debug("REQUEST TYPE: " + type);}
    url = new URL(url);
    headers.Accept = '*/*';
    headers['User-Agent'] = 'YTdash/0.19';
    //headers['Connection'] = 'keep-alive';
    //headers['Range'] = 'bytes=0-1024000';
    //headers['Accept-Encoding'] = 'gzip';
    headers['Access-Control-Expose-Headers'] = 'Content-Length';
    //var httpRetries = 5;
    var retrySecs = 5,
        bytesWritten = 0,
        body = '',
        newURL = '';
    let options = { host: url.host,
                port: 443,
                path: url.pathname + url.search,
                headers: headers,
                method: type },
        hadError=false,
        requestStartTime = performance.now(),
        requestDuration;
    options.agent = keepAliveAgent;
    let Ans = new Promise((resolve, reject) => {
        function retriableRequest(){
            let r;
            //onErrorStartTime = performance.now();

            r = http.request(options, function(res) {
                let responseHeaders = res.headers;
                var statcode = res.statusCode;
                if(debug){console.debug("REUSED SOCKET: " + r.reusedSocket);}
                if(debug){console.debug("HTTP Response Code: " + res.statusCode);}
                //console.log("HTTP Version: " + res.httpVersion);
                if( type==='POST' ){
                    res.setEncoding('utf8');
                } else if (type==='GET'){
                    body = [];
                } else{
                    if(debug){console.debug("HEADERS: " + res.rawHeaders);}
                }
                if(statcode === 301 || statcode === 302) {
                    newURL = res.headers.location;
                    if(debug){console.debug("-----> Redirecting to New URL: " + newURL);}
                    url = new URL(newURL);
                    options.host = url.host;
                    options.path = url.pathname + url.search;
                    return retriableRequest();
                    //return request(res.headers.location, type='GET',
                    //        headers, ioo, 1);
                } else if (statcode === 200||statcode === 204||statcode === 206){
                    // data no se llama with a HEAD request:
                    /*res.on('readable', async() => {
                            let chunk;
                            let canWrite;
                            while (null !== (chunk = res.read(102400))) {
                                console.log(`Received ${chunk.length} bytes of data.`);
                                if (type==='GET'){
                                    //body.push(chunk);
                                    if (ioo){
                                        ioo.cork();
                                        if (httpRetries){
                                                if(!next){
                                                    //ioo.cork();
                                                    canWrite = !ioo.write(chunk);
                                                    ioo.uncork();
                                                } else{
                                                    //res.pause();
                                                    ioo.uncork();
                                                    ioo.end();
                                                    //ioo.uncork();
                                                    //r.emit('end', '');
                                                    r.end();
                                                    ffmpeg.kill('SIGKILL');
                                                    await res.destroy(new Error('Next item requested '));
                                                    //res.destroySoon()
                                                    //r.destroy( new Error('Next item requested '));
                                                }
                                            } else{
                                                console.log('Http error on the other media content, cancelling ');
                                                ioo.end();
                                                r.end();
                                                await res.destroy(new Error('Http error on the other media content, cancelling '));
                                                //r.destroy(new Error('Http error on the other media content, cancelling '));
                                                //res.emit('end', null);
                                                //return

                                            }
                                        //  }
                                    } else {
                                        // For getting Manifest URL:
                                        body.push(chunk);
                                    }
                                } else{
                                    // For POST requests:
                                    body+=chunk;
                                }
                            }
                    });*/
                    res.on("data", function(chunk) {
                        bytesWritten += chunk.length;
                        let canWrite;
                        //console.log(`Received ${chunk.length} bytes of data.`);
                        //console.log(`Total bytes written:  ${bytesWritten}`);
                        if (type==='GET'){
                            if (ioo){
                                if (httpRetries){
                                        if(!next){
                                            //ioo.cork();
                                            canWrite = !ioo.write(chunk);
                                            //ioo.uncork();
                                        } else{
                                            //res.pause();
                                            ioo.end();
                                            //ioo.uncork();
                                            //ioo.uncork();
                                            //r.emit('end', '');
                                            //res.end()
                                            ffmpeg.kill('SIGKILL');
                                            res.destroy(new Error('Next item requested.'));
                                            //res.destroySoon()
                                            //r.destroy( new Error('Next item requested '));
                                        }
                                    } else{
                                        console.info('Http error on the other media content, cancelling ');
                                        res.destroy(new Error('Http error on the other media content, cancelling '));
                                        //r.destroy(new Error('Http error on the other media content, cancelling '));
                                        //res.emit('end', null);
                                        //return

                                    }
                                //  }
                            } else {
                                // For getting Manifest URL:
                                body.push(chunk);
                            }
                        } else {
                            // For POST requests:
                            body+=chunk;
                        }
                    });
                    res.on("end",()=>{
                        requestDuration = (performance.now() - requestStartTime)/1000;
                        if(debug){console.debug("==>>> RUNNiNG REQUEST END EVENT ");}
                        // Close fds or ffmpeg don't close:
                        if(type==='GET'){
                            if (ioo!==0 ){ioo.end();}
                            if (next){
                                if(debug){console.debug('Next item requested. ');}
                                //res.destroy();
                            }
                            body = Buffer.concat(body);
                        }
                        if(debug){console.debug("==>>> PRE RESOLVE ");}
                        //if(!next){
                        newURL = newURL.replace(/\/sq\/[0-9]*/, '');
                        resolve([responseHeaders, body, newURL, requestDuration, hadError]);
                        //}else{resolve(1);}
                    });
                    /*res.on('error',(err)=>{
                        if(debug){console.debug("Error on response, cancelling: " + err);}
                        //ffmpeg.kill('SIGKILL');
                    });*/
                } else if(statcode === 403||statcode === 404||statcode === 503){
                    if (httpRetries>0) {
                            (function loop() {
                            setTimeout(function() {
                                // Escriba su lógica aquí
                                retriableRequest();
                                httpRetries--;
                                loop();
                            }, retrySecs*2000);
                            })();
                            httpRetries--;
                        console.info("Retrying, remaining tries: " + httpRetries);
                        //res.emit('end', null);
                        //retriableRequest();

                    } else{
                        console.info('HTTP error code: ' + res.statusCode);
                        res.destroy(new Error('Http error on the other media content, cancelling '));
                        //resolve(null);
                    }
                } else{
                    res.destroy(new Error('HTTP error code: ' + statcode));

                }
            });
            r.on('error', async function(err) {
                hadError = true;
                if ( err.message !== 'Next item requested.'){
                    console.info("Got error: " + err.message);
                    console.info("Error code: " + err.code);//if (r.reusedSocket && err.code === 'ECONNRESET') {
                }
                /*if (httpRetries>1) {
                    /*(function loop() {
                        setTimeout(function() {
                        // Escriba su lógica aquí
                        retriableRequest();
                        loop();
                    }, retrySecs*1000);
                    })();
                    httpRetries--;
                    console.log("Retrying, remaining tries: " + httpRetries);
                    retriableRequest();
                }else{
                    resolve(1);
                    //reject('HTTP retries 0');
                }*/
                // if retriable error:
                if (err.code === 'ENETUNREACH' || err.code === 'EAI_AGAIN' || err.code === 'ECONNRESET' || err.code === 'ETIMEDOUT' ){
                    //ioo.end();
                    console.info("Trying to resume stream from byte=" + bytesWritten);
                    options.headers['Range'] = 'bytes=' + bytesWritten + '-';
                    await new Promise((r)=>{setTimeout(r, 2000)});
                    //onErrorDuration += (performance.now() - onErrorStartTime)/1000;
                    return retriableRequest();

                }else{
                    if (ioo!==0 ){ioo.end();
                        //ioo.destroy();
                        //r.destroy();
                    }
                    //
                    if(debug){console.debug("Resolving...");}
                    resolve(1);
                    if(debug){console.debug("Resolved...");}
                }
            });
            if (type==='POST'){
                r.write(JSON.stringify(metaPostdata));
            }
            r.end();
        }
        retriableRequest();
    });
    if(debug){console.debug("PRE Return");}
    return Ans;
}

function segmentCreator(sq, murls, fd, mpv, isLive){
    var ffmpeg;
    let audioRequest,beforeRequest,requestsLapse,
        videoRequest;
    let segmenter = new Promise((resolve, reject) => {
        ffmpeg = child_process.spawn(ffmpegURI, ffmuxargs.split(' '),
                { stdio: ['ignore', mpv.stdio[fd], process.stderr,
                          'pipe', 'pipe']
                });
            //let audioRequest=request(murls[0],'GET',{},mpv.stdio[3]);
            //let videoRequest=request(murls[1],'GET',{},mpv.stdio[4]);
        ffmpeg.on('error', (err)=>{
            console.info('FFmpeg Muxer error: ' + err);
            resolve(1);
        });
        ffmpeg.on('spawn',()=>{
            //let videoResponse, audioResponse;
            httpRetries=5;
            //beforeRequest = performance.now();
            audioRequest=request(murls[0],'GET',{},ffmpeg.stdio[3],ffmpeg);
            videoRequest=request(murls[1],'GET',{},ffmpeg.stdio[4],ffmpeg);
            if(debug){console.debug('Audio PREresolved: ');}
            if (isLive){
                ffmpeg.on('close',()=>{
                    resolve([audioRequest, videoRequest]);
                });
            }else{
                resolve([audioRequest, videoRequest]);}
            //videoResponse = await videoRequest;
            //audioResponse = await audioRequest;
            //console.info(' Error Lapso ' + videoResponse[3]);
            //console.info(' Error Lapso ' + audioResponse[3]);
            //requestsLapse = (performance.now() - beforeRequest)/1000;
            //audioResponse.push(requestsLapse);
            //videoResponse.push(requestsLapse);
           // console.info(' Lapso ' + requestsLapse);

            /*audioRequest.then((ar)=>{
                    //console.log('Audio Resolved: %o', ar);
                    videoRequest.then((vr)=>{
                        //console.log('Video Resolved: %o', vr);
                        resolve(vr);
                        //audioRequest.then((ar)=>{resolve(vr)})
                    });
            });*/
            /*ffmpeg.on('close', (res)=>{
                console.dir('FFMPEG RES;' + res);
                if (httpRetries){
                    if(next) {
                        resolve(null);
                    }else{
                        resolve(videoRequest);
                    }
                }else{
                    console.log('FFmpeg exited with http errors: ');
                    resolve(null);
                }*/


                        /*if(vr !== 1){
                            if(httpRetries){
                                mpv.stdio[3].on('close', (res)=>{resolve(1)});
                                //ffmpeg.on('close', (res)=>{resolve(1)});
                            }else{
                                resolve(null);
                            }
                        }else{
                            console.log('Video Http errored, cancelling.');
                            //ffmpeg.kill()
                            resolve(null);
                        }*/

                    //ffmpeg.on('close', (res)=>{resolve(1)});
                    /*if(ar !== 1) {
                        console.log('Audio Resolved: ' + ar);
                        if(httpRetries){
                            //mpv.stdio[4].on('close', (res)=>{resolve(1)});
                            ffmpeg.on('close', (res)=>{resolve(1)});
                        }else{
                            resolve(null);
                        }
                    }else{
                        console.log('Audio Http errored, cancelling.');
                        //ffmpeg.kill()
                        resolve(null);
                    }
                    console.log('Audio Resolved: ' + ar);

                });

            });*/
        });

    });
    if(debug){console.debug('RETURNING...');}
    return segmenter;
}


async function openURL(url,fd, mpv){
        let sq,
        //metadata={},
        segmentDurationSecs,
        segmentsDurationsSecs = [],
        segmentsDurationsSecsAvg,
        videoId,
        aid,
        vid,
        bandEst,
        bandEst2,
        bandEst3,
        bandEstComp,
        acodec,
        vcodec,
        aurl,
        vurl,
        svurl,
        saurl,
        murls,
        resp,
        headers,
        dateTime,
        videoQualitiesQuantity,
        minBandwidthRequired,
        manifestSequencePath;
    //await new Promise(r => setTimeout(r, 20000));
    if(!url){ console.info("No URL detected"); return;}
    if (!url.startsWith('#')){
        if (url.length !== 11) {
            let urlp;
            try {
                urlp = new URL(url);
            }
            catch(error){
                console.info('URL Error: %o with Input: %o ',
                            error.code,
                            error.input);
                //deadVideoIds++;
                return 1;
            }
            if (urlp.host === 'youtu.be') {
                videoId = urlp.pathname.slice(1);
            } else {
                videoId = urlp.searchParams.get('v');
                //console.log('Incorrect Video Id lenght.');
                //process.exit();
            }
        } else {
            console.info('VideoId: --->>> %o <<<---', url);
            videoId = url;
        }
    }else {
        console.info('Playlist Item Info: ' + url);
        //deadVideoIds++;
        return 1;
    }
    metaPostdata.context.client.mainAppWebInfo.graftUrl = "/watch?v=" + videoId;
    metaPostdata.videoId = videoId;
    metaPostHeaders['Content-Length'] = Buffer.byteLength(JSON.stringify(metaPostdata));
    //console.dir(metaPostdata.context.client.mainAppWebInfo);
    // if metadata wasn't previously stored get it;
    //||(metadata[videoId].expireInSeconds - metadata[videoId]['x-head-time-sec'])
    dateTime = new Date();
    //URLs expire in 6hrs:
    //if(debug){console.debug("MMMMEEETTAADDDDAAATTAEEEEEE!!: " + metadata[videoId])}
    if (!metadata[videoId]){
        metadata[videoId] = await getMetadata(metadataUrl,
                                              metaPostHeaders);
        if(debug){console.debug("DATE CREATION ADDED: " );}
        //console.dir(metadata[videoId]);
    } else{
        console.info("Using cached video details." );
    }
    // If a video Id gives metadata errors it's skipped next time:
    if (metadata[videoId]===1){
            //console.log('Removing %s from playlist', videoId);
            //urls = urls.filter(item=>item!==videoId);
            //deadVideoIds++;
            console.info('Skipping Video Id: %s.', videoId);
            return 1;
        } else{
            metadata[videoId].dateTime = dateTime;
        }
    //console.dir(metadata[videoId]);
    // Live or not?:
    if (metadata[videoId].isLive){
        aid=-1;
        vid=3;
        ffmuxargs = ffmuxargs.replace('-f nut','-f mpegts');
        aurl = metadata[videoId].audio.at(aid).BaseURL;
        vurl = metadata[videoId].video.at(vid).BaseURL;
        minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
        switch (metadata[videoId].latencyClass) {
            case 'NORMAL':
                segmentDurationSecs = 5;
                break;
            case 'LOW':
                segmentDurationSecs = 2;
                break;
            case 'ULTRA LOW':
                segmentDurationSecs = 1;
                break;
        }
        manifestSequencePath = 'sq/';
        let manLessSequencePath = '&sq='; // bandwidth limited by YouTube;
        // Get Live HEADers metadata:
        let headRes = await request(aurl, 'HEAD');
        sq = headRes[0]['x-head-seqnum'] - 3;
        //metadata[videoId]['x-head-time-sec'] = headRes[0]['x-head-time-sec'];
        saurl = aurl + manifestSequencePath + sq;
        svurl = vurl + manifestSequencePath + sq; //+ '&range=0-1024000';
    }else{
        let prefAudioFormat,prefVideoFormat,prefAudioCodecs,prefVideoCodecs,videoMetadata, audioMetadata, audioFormat, videoFormat;
        ffmuxargs = ffmuxargs.replace('-f mpegts','-f nut');
        vid = 2; // Defaulting to low/medium video quality by sort.order:
        audioMetadata = metadata[videoId].audio;
        videoMetadata = await metadata[videoId].video;
        prefAudioCodecs = ['opus', 'mp4a'];
        prefVideoCodecs = ['vp9', 'avc1','av01'];
        for (let pacodec of prefAudioCodecs){
            for (let audioFormat in audioMetadata){
                for (let audioCodec in audioMetadata[audioFormat]){
                    if (audioCodec === pacodec){
                        acodec = audioMetadata[audioFormat][audioCodec];
                        break;
                    }
                }
                if (acodec){break;}
            }
            if (acodec){break;}
        }
        for (let pvcodec of prefVideoCodecs){
            for (let videoFormat in videoMetadata){
                for (let videoCodec in videoMetadata[videoFormat]){
                    if (videoCodec === pvcodec){
                        vcodec = videoMetadata[videoFormat][videoCodec];
                        break;
                    }
                }
                if (vcodec){break;}
            }
            if (vcodec){break;}
        }
        /*prefAudioCodecs.forEach(codec=>{
            console.log('CODECCCCCCCCCCCC:' + codec)
            if (codec === 'opus') {
                prefAudioFormat = 'webm';
            } else {
                prefAudioFormat = 'mp4';
            }
            audioFormat = audioMetadata[prefAudioFormat];
            if (audioFormat){
                acodec = audioFormat[codec];
                if (acodec){return;}
                console.dir(audioFormat)
            }
        });
        prefVideoCodecs.forEach(codec=>{
            if (codec === 'av01' || codec === 'avc1') {
                prefVideoFormat = 'mp4';
            } else {
                prefVideoFormat = 'webm';

            }
            videoFormat = videoMetadata[prefVideoFormat];
            if (videoFormat){
                vcodec = videoFormat[codec];
                if (vcodec){return;}
                console.dir(videoFormat)
            }
        });*/
        aid=acodec.length - 1; // Defaulting to highest audio quality by sort.order:
        if(vcodec.length < vid + 1){ vid = vcodec.length - 1; }; // Pick highest available-
        //console.dir(metadata[videoId].video.mp4);
        if (vcodec.every(elem=>elem.signatureCipher)){
            //vcodec[0].signatureCipher
            console.warn('===>>> Ciphered videos are not supported.');
            metadata[videoId]===1;
            return 1;
            //return 1;
            //process.exit();
        }
        if(debug){console.dir(acodec[acodec.length-1]);}
        // console.dir(vcodec.at(vid));
        saurl = acodec[aid].url;
        svurl = vcodec[vid].url;
    }
    if(debug){console.debug("AURL: " + saurl);}
    if(debug){console.debug("VURL: " + svurl);}
    //client.write('{ "command": ["drop-buffers"] }\n');
    //if (!fd){fd=3;}else{fd=0;}
    /*if (result[0] === 2 && result[1] !== fd) {
        nextAvailable=1;
    }else{
        nextAvailable=0;
    }*/
    let ipcString = `{ "command": ["loadfile", "fd://${fd}", "append-play", "force-media-title=${metadata[videoId].title.replace(':',';') + ' - ' + metadata[videoId].author}"] }\n`
    if(debug){console.debug(ipcString);}
    client.write(ipcString)
    //if (client){client.write(ipcString)};
    //client.write('{ "command": ["set", "idle", "no"] }\n');
    //client.write(`{ "command": ["force-media-title", "${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
    videoQualitiesQuantity = metadata[videoId].video.length;
    murls = [saurl, svurl];
    next=0;
    // Main loop:
    //client.write('{ "command": ["set", "pause", "no"] }\n')
    //if (metadata[videoId].isLive){
    let audioResults,videoResults,startMiliSecsTime,segmenterDurationSecs,requestDurationSecs,goUp=false,goDown=false,bandEstAvg,bandEstAvgs=[];
    while(resp = await segmentCreator(sq, murls, fd, mpv, metadata[videoId].isLive)){
        if(debug){console.debug('NEXT ITEM REQUESTED?: ' + next);}
        videoResults = await resp[1];
        headers = await videoResults[0];
        if (next) {
            if(debug){console.debug('NEXT ITEM REQUESTED!!!!');}
            return 2;
            //break;
        }
        //console.dir(headers)
        if (metadata[videoId].isLive){
            bandEst = headers['x-bandwidth-est']/8/1024;
            bandEst2 = headers['x-bandwidth-est2']/8/1024;
            bandEst3 = headers['x-bandwidth-est3']/8/1024;
            bandEstComp = headers['x-bandwidth-est-comp']/8/1024;
            bandEstAvg = (bandEst + bandEst2 + bandEst3)/3;
            bandEstAvgs.push(bandEstAvg);
            if (bandEstAvgs.length > 5 ){bandEstAvgs.shift()};
            bandEstAvg = 0;
            bandEstAvgs.forEach(e=>bandEstAvg+=e);
            bandEstAvg /= 5;
            if(debug){console.debug('SEQUENCE NUMBER: ' + sq);}
            if(debug){console.debug("VID: " + vid);}
            if(debug){console.debug('BAND EST: ' + bandEst + ' Kb/s');}
            if(debug){console.debug('BAND EST2: ' + bandEst2 + ' Kb/s');}
            if(debug){console.debug('BAND EST3: ' + bandEst3 + ' Kb/s');}
            if(debug){console.debug('BAND Avg: ' + bandEstAvg + ' Kb/s');}
            if(debug){console.debug('BAND AvgS: ' + bandEstAvgs);}
            if(debug){console.debug('MIN BAND REQ: ' + minBandwidthRequired/8/1024);}
            if(debug){console.debug('BAND EST COMP: ' + bandEstComp + ' Kb/s');}
            audioResults = await resp[0];
            await audioResults[0];
            //if(startMiliSecsTime) {
            // if any request had error do not save segment stream duration:
            if(!audioResults[4] || !videoResults[4]) {
                // Use highest media type duration as segment duration:
                if(videoResults[3] >= audioResults[3]){
                    requestDurationSecs = videoResults[3];
                } else {
                    requestDurationSecs = audioResults[3];
                }
                // segmenterDurationSecs = Math.round((performance.now() - startMiliSecsTime))/1000;
                segmentsDurationsSecs.push(requestDurationSecs);
                if (segmentsDurationsSecs.length > 3) {
                    segmentsDurationsSecs.shift();
                }
                segmentsDurationsSecsAvg = 0;
                segmentsDurationsSecs.forEach(e=>segmentsDurationsSecsAvg+=e);
                segmentsDurationsSecsAvg /= segmentsDurationsSecs.length;
                if(debug){console.debug('-----------> Segments Durs: ' + segmentsDurationsSecs);}
                if(debug){console.debug('-----------------------> DOWNLOADs Avg DURATION: ' + segmentsDurationsSecsAvg + ' secs');}
            }
            // startMiliSecsTime = performance.now();
            // Check to go up in media quality:
            if ( !goDown && vid < videoQualitiesQuantity - 1){
                if (bandEstAvg>1.3*(minBandwidthRequired/8/1024) &&
                    metadata[videoId].video[vid+1].$.height<=maxHeight){
                    goUp=true;
                    if(debug){console.debug('====>> GOING UP')}
                    vid++;
                    vurl = metadata[videoId].video[vid].BaseURL;
                    minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
                }
            // Check to go down:
            }
            goDown=false;
            if (!goUp && vid > 0 && segmentsDurationsSecsAvg > segmentDurationSecs * 1.2 &&
                segmentsDurationsSecs[2] > segmentDurationSecs * 1.2 ){
                //if (bandEstAvg<1.5*(minBandwidthRequired/8/1024)){
                    if(debug){console.debug('====>> GOING DOWN')}
                    goDown=true;
                    vid--;
                    vurl = metadata[videoId].video[vid].BaseURL;
                    minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
                //}
            }
            goUp=false;
            if(videoResults[2]){
                //vurl = videoResults[2].slice(0,videoResults[2].indexOf(manifestSequencePath))
                vurl = videoResults[2] + '/';
                if(debug){console.debug('----------->> NEW VURL HREF: ' + vurl);}
            }
            if(audioResults[2]){
                //aurl = audioResults[2].slice(0,audioResults[2].indexOf(manifestSequencePath))
                aurl = audioResults[2] + '/';
                if(debug){console.debug('----------->> NEW AURL HREF: ' + aurl);}
            }
            //murls = [audioResults[2], videoResults[2]];
            //console.dir(murls);
            sq++;
            murls[0] = aurl + manifestSequencePath + sq;
            murls[1] = vurl + manifestSequencePath + sq;

        } else {
            console.info("Video ended.");
            return 3;
        }

    }
}
    /*}else{
    console.info("Video NON LIVE.");
        // client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl}"] }\n`);
        // client.read().toString()
        client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl} ,force-media-title=${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
    }*/

//}
//main()
/*main().then((returnCode)=>{
    if(returnCode===1 && !mpv.exitCode){
        mpv.kill();
    }
});*/
async function apiSearch(query){
    let parms,items,apiBaseURL,apiParameters,midURL,apiUrlCheckLive,apiType,
    urlEnd,apiURL,jsonResponse,videoIds = [];
    parms = {
    'eventType':'completed',
    'sortBy':'relevance',
    'safeSearch':'moderate',
    'type':'video',
    'videoDuration':'any',
    'videoType':'any',
    'videoLicense':'any',
    'videoDefinition':'any',
    'maxResults':'5',
    'videoEmbeddable':'any',
    'videoSyndicated':'true',
    'videoDimension':'2d'

    }
    apiBaseURL = 'https://www.googleapis.com/youtube/v3/';
    apiParameters = {};
    apiParameters['part'] = 'snippet';
    apiParameters['key'] = 'AIzaSyBSnNQ7qOmLPxC5CaHH9BWHqAgrecwzCVA';
    midURL = new URLSearchParams(apiParameters).toString();
    apiUrlCheckLive = apiBaseURL + 'videos?' + midURL;
    apiType = 'search'
    apiParameters['type'] = 'video'
    apiParameters['order'] = 'relevance'
    apiParameters['eventType'] = 'live'
    apiParameters['videoDimension'] = '2d'
    //apipar['regionCode'] = 'AR'
    apiParameters['safeSearch'] = 'moderate'
    apiParameters['videoDuration'] = 'any'
    apiParameters['videoType'] = 'any'
    apiParameters['type'] = 'video'
    apiParameters['videoLicense'] = 'any'
    apiParameters['videoDefinition'] = 'any'  // high|any
    apiParameters['maxResults'] = 5
    apiParameters['videoEmbeddable'] = 'any'
    apiParameters['videoSyndicated'] = 'true'
    apiParameters['fields'] = 'items(id,snippet/title,snippet/' +
                              'channelTitle,snippet/description,' +
                              'snippet/liveBroadcastContent,' +
                              'snippet/publishedAt)'
    apiParameters['q'] = query;
    if (args.includes('-n')){apiParameters['eventType']='completed'}
    if (args.includes('-u')){apiParameters['eventType']='upcoming'}
    if (args.includes('-mr')){
        apiParameters['maxResults'] = args.slice(args.indexOf('-mr'))[1];
    }
    urlEnd = new URLSearchParams(apiParameters).toString();
    apiURL = apiBaseURL + apiType + '?' + urlEnd;
    if(debug){console.debug("API URL: " + apiURL);}
    jsonResponse = await request(apiURL, "GET", {'Referer':'www.youtube.com/test'});
    jsonResponse = JSON.parse(jsonResponse[1]);
    if(debug){console.dir(jsonResponse['items']);}
    items = jsonResponse.items;
    if (items){
        items.forEach(item=>videoIds.push(item.id.videoId));
        if(debug){console.dir("item " + videoIds);}
    }
    return videoIds;
}
//if(debug){console.debug('URLS' + urls);}
let results=[0],
    nextAvailable;
var metadata={},videoId;
// MAIN ULTRA_ASYNC_GENERIC_LOOP_2000:
async function  main() {
    let mpvStdio = {stdio: ['ignore', process.stdout, process.stderr]},
        parameter,urls;
    if(debug){console.debug('ARGS: %o', args)}
    if (args.includes('-s')){
        parameter = args.slice(args.indexOf('-s'))[1];
        if (parameter){
            urls = await apiSearch(parameter);
            if(debug){console.dir(urls);}
            if (!urls.length){
                console.info("0 videos found.");
                process.exit();
            }
        }else{
            console.info('No search string given.');
            process.exit();
        }

    } else {
        urls = args.filter(e=>e!=='-s' && e!=='-n'&& e!=='-u'&& e!=='-debug')
    }
    if(debug){console.debug('URLS: %o', urls)}
    /*for (let times=0; times < urls.length;times++){
                mpvStdio.stdio.push('pipe');
                //console.log('Mpv STDIO: %o', mpvStdio.stdio)
            }*/
    await urls.forEach(e=>mpvStdio.stdio.push('pipe'));
    //if(debug){console.debug('Mpv STDIO: %o', mpvStdio.stdio)}
    const mpv = child_process.spawn('mpv', mpvargs.split(' '),mpvStdio);
    //mpv.stdin._writableState.highWaterMark=1024;

    //mpv.connected
    mpv.on('exit', ()=>{
        console.info('Player closed, exit...');
        process.exit();
    });
    //function setMpvIPC(){
    mpv.on('spawn', ()=>{
        // connect to IPC socket :
        Id=setInterval(function(){
            client=net.createConnection("/tmp/mpvsocket", ()=>{
                //client.write('{ "command": ["loadfile", "-"] }\n');
                //client.write('{ "command": ["loadfile", "fd://0", "append-play"] }\n');
                //client.write('{ "command": ["loadfile", "fd://3", "append-play"] }\r\n');
                client.write('{ "command": ["observe_property", 1, "playback-abort"] }\r\n');
                client.write('{ "command": ["observe_property", 1, "cache-buffering-state"] }\n');
                client.write('{ "command": ["observe_property", 1, "playlist-pos"] }\n');
                client.write('{ "command": ["observe_property", 1, "playlist-next"] }\n');
                client.write('{ "command": ["observe_property", 1, "playlist-playing-pos"] }\n');
                /*ffmpegbase = child_process.spawn('ffmpeg',
                             ffbaseargs.split(' '),
                             {stdio: ['pipe',mpv.stdin, process.stderr]});
                             //*/
                clearInterval(Id);
            }).on('error', (err)=>{
                //console.log('MPV Exit Code: ' + mpv.exitCode)
                //console.log('MPV Error Code: ' + err);
                if(debug){console.debug('Mpv IPC Channel Unavailable yet.' + err);}
                //process.exit();
            }).on('data', async (rawEvents)=>{
                // Multiline events  can come so:
                const eventsList = rawEvents.toString().split('\n').slice(0,-1);
                for (let strEvent of eventsList) {
                    let event = JSON.parse(strEvent);
                    if(debug){console.debug('IPC Event: ');}
                    if(debug){console.dir(event);}
                    // console.dir(JSON.parse(event));
                    if ( event && event.event === "seek" ){
                        if(debug){console.debug('Seek ');}
                    } else if ( event.event === 'end-file' && event.reason!=='quit' ){
                        //client.write('{ "command": ["drop-buffers"] }\n');
                        //client.write('{ "command": ["set", "idle", "yes"] }\n');
                        /*if(urls.length - 1 > eid){
                            eid++;
                        }else{
                            eid=0;
                        }*/
                        //playlist_entry_id = event.playlist_entry_id;
                        //client.write('{ "command": ["set", "audio-reload", "0"] }\n');
                        //client.write('{ "command": ["set", "video-reload", "0"] }\n');
                        /*if (!nextAvailable){
                            console.log('OPENNING NEXT FILE ');
                            next = 1;
                            //playlist_entry_id = event.playlist_entry_id;
                        }*/
                        let cid = event.playlist_entry_id;
                        if(debug){console.dir(results);}
                        if(debug){console.dir(results.slice(cid-1));}
                        if(!results.slice(cid-1).some(e=>e>=2)){
                            if(debug){console.debug('OPENNING NEXT FILE ');}
                            //client.write('{ "command": ["stop", "keep-playlist"] }\n');
                            client.write('{ "command": ["stop"] }\n');
                            next=1
                       }
                        client.write('{ "command": ["stop"] }\n');
                        next=1
                        //console.log('PLAYING NEXT FILE ' + client.write('{ "command": ["playlist-next"] }\n'));
                        //await new Promise((r)=>{setTimeout(r, 2000)})
                        /*while (await openURL(urls[eid])){
                            console.log('Error opening this, Skipping');
                            if(urls.length - 1 > eid){
                                eid++;
                            }else {
                                break;
                            }

                        }
                        if (playlist_entry_id === event.playlist_entry_id) {
                            playlist_entry_id = event.playlist_entry_id;
                            next = 1;
                    }else if ( event.event === 'tracks-changed'){*/
                        //client.write('{ "command": ["loadfile", "-"] }\n');
                    }
                }
            });
        }, 100);
    });
    let result,
        eid=0,
        fd=3;
    //do {
    while (true){
        if (eid > urls.length - 1){
            //client.write('{ "command": ["playlist-clear"] }\n');
            //client.write('{ "command": ["stop"] }\n');
            if (results.length == urls.length && results.length == 1){
                break;
            };
            if (results.every(r=>r<2)){
                console.info('All videos had errors...');
                break;
            }else if (results.filter(e=>e>1).every(r=>r>=2)){
                if (!Object.entries(metadata).every(([l,e])=>{return e.isLive})){
                    console.info('ALl urls are non live.');
                    console.info('All videos already downloaded...');
                    break;
                }
            };
            eid=0;
            fd=3;
        };
        if ( !results[eid] || results[eid] < 4 ){
            result = await openURL(urls[eid], fd, mpv);
            results.splice(eid, 1, result);
        }
        eid++;
        if(result>=2){
            fd++;
        }
        if(debug){console.debug('Trying to open input URL: ' + urls[eid]);}
        if(debug){console.debug('Results ' + results);}
    };
    console.info('No more videos to play.');
    //mpv.kill();
}
main();
if(debug){console.debug('OUT');}
