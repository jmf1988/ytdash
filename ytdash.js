#!/usr/bin/env node
/*jshint esversion: 8 */
"use strict";
const {performance} = require('perf_hooks'),
      http = require('https'),
      net = require('net'),
      fs = require('fs'),
      child_process = require('child_process'),
      parseString = require('xml2js').parseString,
      zlib = require('zlib'),
      keepAliveAgent = new http.Agent({ keepAlive: true, scheduling: 'fifo', keepAliveMsecs:0,  timeout:12000  }),
      apiKey='AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
      metadataUrl = 'https://www.youtube.com/youtubei/v1/player?key=' + apiKey,
      args = process.argv.slice(2),
      ffmpegURI = '/usr/bin/ffmpeg',
      cacheDir = process.env.HOME + '/.cache/ytdashjs',
      configDir = process.env.HOME + '/.config/ytdashjs',
      // Flags:
      live = !args.includes('-n'),
      debug = args.includes('-debug'),
      fixed = args.includes('-fixed')||args.includes('-f'),
      fullscreen = args.includes('-fullscreen')||args.includes('-F'),
      extraInfo = args.includes('-e')||args.includes('-extra'),
      help = args.includes('-help')||args.includes('-h'),
      noDiskCache = args.includes('-nc'),
      noVolNor = args.includes('-nv'),
      order = args.includes('-order'),
      orderType = args.slice(args.indexOf('-order'))[1],
      onlyAudio = args.includes('-oa'),
      searchMode = args.includes('-s'),
      searchTerm = args.slice(args.indexOf('-s'))[1],
      videoCodecsPriorities = args.slice(args.indexOf('-vc'))[1]||'vp9,avc1,av01',
      audioCodecsPriorities = args.slice(args.indexOf('-ac'))[1]||'opus,mp4a',
      maxWidth = Math.round(Number(args.slice(args.indexOf('-mw'))[1]))||4096,
      maxFps = Math.round(Number(args.slice(args.indexOf('-mf'))[1]))||60,
      maxHeight = Math.round(Number(args.slice(args.indexOf('-mh'))[1]))||720,
      maxResults = Math.round(Number(args.slice(args.indexOf('-mr'))[1])),
      urlPassthrough = 1,
      ffmuxinargs = ' -thread_queue_size 100512 -flags +low_delay -i ',
      ffmuxoutargs = ' -c copy -copyts -flags +low_delay -f mpegts ',
      //-tune zerolatency -write_index 0 -f_strict experimental -syncpoints timestamped
      ffmuxbaseargs = '-v fatal -nostdin -xerror',
      metaPostdata = {"context":
                        {"client":
                            {"hl": "en", "clientName": "WEB",
                             "clientVersion": "2.20210721.00.00",
                             "mainAppWebInfo": {"graftUrl": 0}
                            }
                        },"videoId": 0
                    },
      metaPostHeaders = {
             'Accept': 'application/json',
             'Authorization': 'AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
             'Content-Type': 'application/json'
           };

if (help){
    console.info('Usage: ytdash [(URLs|Video Ids)|-s search term] [Options]');
    console.info('  -s [term]           Search mode, uses Youtube Api to search for videos.');
    console.info('  -nc                 Disable cache to disk of results found with search mode.');
    console.info('  -order [date,rating,...]   Sort search results found by this order.');
    console.info('  -n                  Enable streaming of non-live videos found. (Partial support)');
    console.info('  -oa                 Open only audio sources from all streams.');
    console.info('  -mh [number]        Maximum video height allowed.');
    console.info('  -mw [number]        Maximum video width allowed.');
    console.info('  -mf [number]        Maximum video fps allowed.');
    console.info('  -nv                 Disable Mpv player volume normalization.');
    console.info('  -f, -fixed          Don\'t switch video qualities in live streams.');
    console.info('  -fullscreen, -F     Start Mpv player playback fullscreen.');
    console.info('  -e, -extra          Show more information about each video properties.');
    console.info('  -vc [vp9,avc1,av01] Video codecs priorities for non-live streams, comma separated.');
    console.info('  -ac [opus,mp4a]     Audio codecs priorities for non-live streams, comma separated.');
    console.info('  -debug              Show debugging console output.');
    process.exit();
}
if (order) {
    let choices=['relevance', 'viewCount', 'videoCount', 'date', 'rating', 'title'];
    if (!choices.includes(orderType)){
        console.info('Invalid order type input. Choices are: %s', choices);
        process.exit();
    }
}
let videoCodecsPrio;
if (videoCodecsPriorities) {
    videoCodecsPrio = videoCodecsPriorities.split(',');
    let choices=['vp9', 'avc1', 'av01'];
    if (!videoCodecsPrio.every(codec=>choices.includes(codec))){
        console.info('Invalid video codecs input. Options separated by commas are: %s ', choices);
        process.exit();
    }
}
let audioCodecsPrio;
if (audioCodecsPriorities) {
    audioCodecsPrio = audioCodecsPriorities.split(',');
    let choices=['opus', 'mp4a'];
    if (!audioCodecsPrio.every(codec=>choices.includes(codec))){
        console.info('Invalid audio codecs input. Options separated by commas are: %s ', choices);
        process.exit();
    }
}
// Variables:
let next=0,
    mpvargs =   '--idle ' +
                  //'--input-ipc-server=/tmp/mpvsocket ' +
                  '--player-operation-mode=pseudo-gui ' +
                  //'--demuxer-lavf-linearize-timestamps=yes ' +
                  '--demuxer-seekable-cache=yes ' +
                  '--cache=yes ' +
                  '--osd-playing-msg-duration=4000 ' +
                  '--osd-align-x=center ' +
                  //'--loop-playlist ' +
                  //'--loop-playlist=force ' +
                  '--prefetch-playlist=yes ' +
                  //'--playlist=fd://0 ' +
                  //'--reset-on-next-file=all ' +
                  //'--video-latency-hacks=yes ' +
                  //'--af=lavfi="[alimiter=limit=0.9:level=enabled]" ' +
                  //'--audio-normalize-downmix=yes ' +
                  //'--merge-files ' +
                  //'--demuxer-lavf-o-add=fflags=+nobuffer ' +
                  //'--no-correct-pts ' + // a/v desync on seeking
                  //'--untimed ' +
                  //'--fps=60 ' +
                  //'--demuxer-lavf-probe-info=nostreams ' +
                  //'--demuxer-lavf-analyzeduration=0.4 ' +
                  //'--framedrop=no ' +
                  '--input-ipc-client=fd://3 ' +
                 //'--really-quiet'+
                 //' - ' +
                 '--keep-open'
                 ;
if (fullscreen){mpvargs += ' --fullscreen';}
if (!noVolNor){mpvargs += ' --af=lavfi=[loudnorm=I=-22:TP=-1.5:LRA=2]';}
if (live){
    //mpvargs += ' --profile=low-latency';
    mpvargs += ' --cache-secs=300 ' +
	       ' --demuxer-max-bytes=' + 50 * 1048576 + 
               ' --demuxer-max-back-bytes=' + 50 * 1048576;
}

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
    //console.dir(videoDetails);
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
    //console.dir(formats);
    adaptiveFormats = streamingData.adaptiveFormats;
    //.sort((a,b)=>{return a.height-b.height;});
    // Get and log video Details:
    mediaMetadata.status = playabilityStatus.status;
    mediaMetadata.isLive = (videoDetails.isLive||false);
    mediaMetadata.isPostLiveDvr = (videoDetails.isPostLiveDvr||false);
    mediaMetadata.title = videoDetails.title.replace(/,/g,';');
    mediaMetadata.author = videoDetails.author.replace(/,/g,';');
    mediaMetadata.channelId = videoDetails.channelId;
    mediaMetadata.viewCount = Number(videoDetails.viewCount);
    mediaMetadata.shortDescription = videoDetails.shortDescription;
    mediaMetadata.latencyClass = videoDetails.latencyClass && videoDetails.latencyClass.slice(42).replace('_',' ');
    if (!videoDetails.isLive) {
        console.warn('\x1b[31m%s\x1b[0m', 'By Youtube rules, non-live videos have slow external download, bandwidth adaptive mode is disabled.');
    }

    if (mediaMetadata.isLive || mediaMetadata.isPostLiveDvr){
        dashManifestURL = streamingData.dashManifestUrl;
        if(debug){console.debug('DASH Manifest URL:'+ dashManifestURL);}
        // Request manifest compressed 'cause too big:
        dashManifestRawBody = await request(dashManifestURL, 'GET',
                                         {'Accept-Encoding' : 'gzip'}, 0
                                        );
        if (!dashManifestRawBody[1]){return 1;}
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
                                            v=>Number(v.$.height) <= maxHeight);
        mediaMetadata.video = mediaMetadata.video.filter(
                                            v=>Number(v.$.width) <= maxWidth);
        mediaMetadata.video = mediaMetadata.video.filter(
                                            v=>Number(v.$.frameRate) <= maxFps);
        //Sort video qualities by bandwidth;
        mediaMetadata.video.sort((a,b)=>{return a.$.bandwidth-b.$.bandwidth;});
        mediaMetadata.audio.sort((a,b)=>{return a.$.bandwidth-b.$.bandwidth;});
    }else {
        adaptiveFormats.sort((a,b)=>{return a.bitrate-b.bitrate;});
        // Filter and create registers by type, container and codec:
        let maxWidthFound = 0, maxHeightFound=0,  maxFpsFound=0;
        for (let format of adaptiveFormats){
            if (format.width > maxWidth) continue;
            if (format.height > maxHeight) continue;
            if (format.fps > maxFps) continue;
            // Filter prefering video properties over codec type:
            /*if(format.width < maxWidthFound) continue;
            if(format.height < maxHeightFound) continue;
            if(format.fps < maxFpsFound) continue;
            maxWidthFound = format.width;
            maxHeightFound = format.height;
            maxFpsFound = format.fps;*/
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
            if(extraInfo){console.info(printStr);}
        }
    }
    // Change url to redirectors:
    //u.protocol + '//redirector.' + 'googlevideo.com' + u.pathname + u.search
    //console.info(mediaMetadata.video);
    if (!mediaMetadata.video || !Object.keys(mediaMetadata.video).length) {
        console.info('===>>> No video/s format found with requested properties.');
        return 1;
    }
    return mediaMetadata;
}

async function request(url, type='GET', headers={}, ffmpeg, fd, playlistEntryId) {
    if(debug){console.debug("REQUEST TYPE: " + type);}
    url = new URL(url);
    headers.Accept = '*/*';
    headers['User-Agent'] = 'YTdash/0.19';
    //headers['Connection'] = 'keep-alive';
    //headers['Range'] = 'bytes=0-1024000';
    //headers['Accept-Encoding'] = 'gzip';
    headers['Access-Control-Expose-Headers'] = 'Content-Length';
    let httpRetries = 5,
        retrySecs = 5,
        bytesWritten = 0,
        body = '',
        newURL = '',
        options = { host: url.host,
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
            r = http.request(options, async function(res) {
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
                    //        headers, ffmpeg.stdio[fd], 1);
                } else if (statcode === 200||statcode === 204||statcode === 206){
                    // data no se llama with a HEAD request:
                    /*res.on('readable', () => {
                        let chunk;
                        let canWrite;
                        while (null !== (chunk = res.read(10240))) {
                            //console.log(`Received ${chunk.length} bytes of data.`);
                            if (type==='GET'){
                                //body.push(chunk);
                                if (ffmpeg.stdio[fd]){
                                    //ffmpeg.stdio[fd].cork();
                                    if (httpRetries){
                                            if(next !== playlistEntryId){
                                                //ffmpeg.stdio[fd].cork();
                                                canWrite = !ffmpeg.stdio[fd].write(chunk);
                                                //ffmpeg.stdio[fd].uncork();
                                            } else{
                                                //res.pause();
                                                //ffmpeg.stdio[fd].uncork();
                                                r.end();
                                                ffmpeg.stdio[fd].end();
                                                //ffmpeg.stdio[fd].uncork();
                                                //r.emit('end', '');
                                                ffmpeg.kill('SIGKILL');
                                                res.destroy(new Error('Next item requested '));
                                                //res.destroySoon()
                                                //r.destroy( new Error('Next item requested '));
                                            }
                                        } else{
                                            console.log('Http error on the other media content, cancelling ');
                                            ffmpeg.stdio[fd].end();
                                            r.end();
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
                            } else{
                                // For POST requests:
                                body+=chunk;
                            }
                        }
                    });*/
                    res.on("data", async function(chunk) {
                        bytesWritten += chunk.length;
                        let canWrite;
                        //console.log(`Received ${chunk.length} bytes of data.`);
                        //console.log(`Total bytes written:  ${bytesWritten}`);
                        if (type==='GET'){
                            if (ffmpeg){
                                if (httpRetries){
                                    //if((!next && live) || (!live && next!==playlistEntryId)){
                                    if(!next){
                                        canWrite = !ffmpeg.stdio[fd].write(chunk);
                                        //ffmpeg.stdio[fd].cork();
                                        //ffmpeg.stdio[fd].uncork();
                                    } else{
                                        if(debug){
                                            console.debug("Stopping Playlist Entry Id: " +
                                                          playlistEntryId);
                                        }
                                        await res.pause();
                                        //ffmpeg.stdio[fd].uncork();

                                        //mpv.send({'command':['playlist-remove', playlistEntryId]})
                                        //mpv.send({'command':['playlist-remove', 'current']})
                                        await ffmpeg.stdio[fd].end();
                                        await ffmpeg.kill('SIGKILL');
                                        await res.destroy(new Error('Next item requested.'));
                                        //r.destroy( new Error('Next item requested '));
                                    }
                                } else{
                                    res.destroy(new Error('Http error in the other request...'));
                                    ffmpeg.kill('SIGKILL');
                                    //r.destroy(new Error('Http error on the other media content, cancelling '));

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
                            if (ffmpeg){ffmpeg.stdio[fd].end();}
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
                //} else if(statcode === 403||statcode === 404||statcode === 503){
                } else {
                    if (httpRetries>0) {
                            httpRetries--;
                            if(debug){console.debug("Retrying, remaining tries: " + httpRetries);}
                            await new Promise((r)=>{setTimeout(r, retrySecs*1000);});
                            retriableRequest();
                    } else{
                        //if(debug){console.debug('HTTP error ' + res.statusCode)};
                        let errorMsg = 'HTTP Error ' + res.statusCode +
                                              ' retries exhuasted.';
                        res.destroy(new Error(errorMsg));
                        //resolve(null);
                    }
                }
                /*} else{
                    res.destroy(new Error('HTTP error code: ' + statcode));

                }*/
            });
            //r.on('socket', so=>{console.log('socket'+so)});
            r.on('error', async function(err) {
                hadError = true;
                if ( err.message !== 'Next item requested.'){
                    console.info("Got error on request: " + err.message);
                    if ( err.code ) {
                        console.info("Error code: " + err.code);//if (r.reusedSocket && err.code === 'ECONNRESET') {
                    }
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
                    //ffmpeg.stdio[fd].end();
                    if(!ffmpeg && type==='GET' ){body = '';}
                    console.info("Trying to resume stream from byte=" + bytesWritten);
                    options.headers.Range = 'bytes=' + bytesWritten + '-';
                    await new Promise((r)=>{setTimeout(r, retrySecs*1000);});
                    //onErrorDuration += (performance.now() - onErrorStartTime)/1000;
                    return retriableRequest();

                }else{
                    if (ffmpeg){
                        if(debug){console.debug("Destroying ffmpeg...");}
                        //ffmpeg.stdio[fd].end();
                        //ffmpeg.stdio[fd].destroy();
                        ffmpeg.kill('SIGKILL');
                        r.destroy();
                    }
                    if(debug){console.debug("Resolving...");}
                    resolve([0,0,0,0,0]);
                    if(debug){console.debug("Resolved...");}
                    //return;
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

function segmentCreator(murls, fd, mpv, isLive, playlistEntryId){

    let segmenter = new Promise((resolve, reject) => {
        let ffmpeg,
            audioRequest,
            videoRequest,
            stdios = { stdio: ['ignore', mpv.stdio[fd], process.stderr]},
            ffMuxAllArgs;
        ffMuxAllArgs = ffmuxbaseargs + ffmuxinargs  + 'async:pipe:3';
        stdios.stdio.push('pipe');
        if (!onlyAudio){
            stdios.stdio.push('pipe');
            ffMuxAllArgs += ffmuxinargs + 'async:pipe:4';
        }
        ffMuxAllArgs += ffmuxoutargs + 'pipe:1'
        //console.log('FFMUXALL: ' + ffMuxAllArgs);
        //console.log('STDIOS: ' + stdios);
        ffmpeg = child_process.spawn(ffmpegURI, ffMuxAllArgs.split(' '),
                                     stdios);
            //let audioRequest=request(murls[0],'GET',{},mpv.stdio[3]);
            //let videoRequest=request(murls[1],'GET',{},mpv.stdio[4]);
        ffmpeg.on('error', (err)=>{
            console.info('FFmpeg Muxer error: ' + err);
            resolve(1);
        });
        ffmpeg.on('spawn',()=>{
            //let videoResponse, audioResponse;
            //httpRetries=5;
            //beforeRequest = performance.now();
            try {
                audioRequest = request(murls[0],
                                         'GET',
                                         {},
                                         ffmpeg,
                                         3,
                                         playlistEntryId);
                if (!onlyAudio){
                    videoRequest=request(murls[1],'GET',{},ffmpeg,4,
                                         playlistEntryId);
                }
                } catch (error) {
                console.info('Error on Media requests: ' + error);
            }
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


async function openURL(url,fd, mpv, sq, onlyMetadata, refreshMetadata){
        //metadata={},
        let segmentDurationSecs,
        segmentsDurationsSecs = [],
        segmentsDurationsSecsAvg,
        videoId,
        //aid,
        //vid,
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
        manifestSequencePath,
        playlistStartId = 1,
        playlistEntryId = fd - playlistStartId,
        videoMetadata, audioMetadata;
    //await new Promise(r => setTimeout(r, 20000));
    // for what?:
    //if(!url){ console.info("No URL detected"); return;}
    //
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
            if(!onlyMetadata){
                //console.info('VideoId: --->>> %o <<<---', url);
            } else{
                console.info('Pre-caching VideoId: --->>> %o <<<---', url);
            }
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
    //if (!metadata[videoId]){
        metadata[videoId] = await getMetadata(metadataUrl,
                                              metaPostHeaders, onlyMetadata);
        if(debug){console.debug("DATE CREATION ADDED: " );}
        //console.dir(metadata[videoId]);
    //} else{
     //   console.info("ººº Using cached video details. ººº" );
    //}
    // If a video Id gives metadata errors it's skipped next time:
    if (metadata[videoId]===1){
            //console.log('Removing %s from playlist', videoId);
            //urls = urls.filter(item=>item!==videoId);
            console.info('Skipping Video Id: %s.', videoId);
            //mpv.send({ command: [ 'playlist-next'] })
            /*if (args.includes('-n')){
                //mpv.send({ "command": ["playlist-remove", playlistEntryId - 1 ] });
            }*/
            //next=false;
            return 1;
    } else{
        metadata[videoId].dateTime = dateTime;

    }
    // If only metadata requested return with non error code:
    if (onlyMetadata){
        return 2;
    }
    let status = metadata[videoId].status,
        title = metadata[videoId].title,
        author = metadata[videoId].author,
        isLive = metadata[videoId].isLive,
        isPostLiveDvr = metadata[videoId].isPostLiveDvr,
        latencyClass = metadata[videoId].latencyClass,
        channelId = metadata[videoId].channelId,
        viewCount = metadata[videoId].viewCount,
        shortDescription = metadata[videoId].shortDescription
        ;
    if(!refreshMetadata){
		// Print Video Details;
		console.info('VideoId: --->>> %o <<<---', videoId);
		console.info("Status: %o", status);
		console.info('Title: %o', title);
		console.info('Author: %o', author);
		console.info('Channel Id: %o', channelId);
		console.info('Views: ', viewCount);
		console.info('Is Live: ', isLive);
		console.info('Is PostLive: ', isPostLiveDvr);
		if (latencyClass) {
			console.info('Latency Class: %o', latencyClass);
		}
		if (extraInfo && shortDescription) {
			console.info('Short Description:');
			console.info(shortDescription);
			//console.dir(console.dir(videoDetails.shortDescription.replace('\n\' \+', '')));
		}
	}
    //
    /*if (metadata[videoId]['downloadFinished']){
        console.info('VIDEOID; ' + videoId + 'ALready DOWNLOADED');
        return 3;
    }    */
    //console.dir(Object.entries(metadata))
    //console.dir(metadata[videoId]);
    // if live or post live use DASH manifest as URLs source:
    //mpv.send({ command: [ 'loadfile', 'fd://' + fd , 'append-play'] })
    //
    //
    /*if(args.includes('-n')){
        videoMetadata = metadata[videoId].video;
    }else{videoMetadata = metadata[videoId].video;
    }*/
    //console.dir(videoMetadata)
    audioMetadata = metadata[videoId].audio;
    videoMetadata = metadata[videoId].video;
    // Diferentiate live|postlive from non-live:
    if (isLive || (isPostLiveDvr && !live)){
        if(!refreshMetadata){aid = audioMetadata.length - 1;}
        if (fixed){
            if(!refreshMetadata){vid = videoMetadata.length - 1;}
        }else{
            if(!refreshMetadata){vid = Math.min(videoMetadata.length - 1, 3);}
        }
        //ffmuxargs = ffmuxargs.replace('-f nut','-f mpegts');
        aurl = audioMetadata[aid].BaseURL;
        vurl = videoMetadata[vid].BaseURL;
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
        let headSeqNum = headRes[0]['x-head-seqnum'] - 3;
        if(!sq){ sq = headSeqNum;}
        if (metadata[videoId].isPostLiveDvr){
            let backbufferTotalSeqNum = (12*60*60)/segmentDurationSecs;
            if(!sq){ sq = Math.max(0, headSeqNum - backbufferTotalSeqNum);}
        }
        //metadata[videoId]['x-head-time-sec'] = headRes[0]['x-head-time-sec'];
        saurl = aurl + manifestSequencePath + sq;
        svurl = vurl + manifestSequencePath + sq; //+ '&range=0-1024000';
    }else{
        // console.dir(metadata[videoId])
        if(live){
            console.info('\x1b[31m%s\x1b[0m', 'This item is not a live stream, ' +
                         'pass -n option to play non-live ' +
                         'videos (Partial support).');
            return 0;
        }
        let prefAudioFormat,prefVideoFormat,prefAudioCodecs,prefVideoCodecs,audioFormat, videoFormat;
        //ffmuxargs = ffmuxargs.replace('-f mpegts','-f nut');
        // Select audio and video media url sources:
        for (let pacodec of audioCodecsPrio){
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
        for (let pvcodec of videoCodecsPrio){
            for (let videoContainer in await videoMetadata){
                for (let videoCodec in videoMetadata[videoContainer]){
                    if (videoCodec === pvcodec){
                        vcodec = videoMetadata[videoContainer][videoCodec];
                        break;
                    }
                }
                if (vcodec){break;}
            }
            if (vcodec){break;}
        }
        if (!vcodec){
            console.warn('===>>> No video codec found. (requested %s)', videoCodecsPrio);
            metadata[videoId]=1;
            return 1;
        }
        if (!acodec){
            console.warn('===>>> No audio codec found. (requested %s)', audioCodecsPrio);
            metadata[videoId]=1;
            return 1;
        }
        aid = acodec.length - 1; // Defaulting to highest audio quality by sort.order:
        //aid=0
        //if(vcodec.length < vid + 1){ vid = vcodec.length - 1; }; // Pick highest available-
        //console.dir(metadata[videoId].video);
        //vid=0
        vid = vcodec.length - 1;// Defaulting to highest video quality
        if (await vcodec.every(elem=>elem.signatureCipher)){
            //vcodec[0].signatureCipher
            console.warn('\x1b[31m%s\x1b[0m', '===>>> Ciphered videos are not supported.');
            //mpv.send({ command: [ 'playlist-next'] })
            //mpv.send({ "command": ["playlist-remove", playlistEntryId - 1] });
            //fd--
            //delete metadata[videoId];
            metadata[videoId]=1;
            return 1;
            //return 1;
            //process.exit();
        }
        if(debug){console.dir(acodec[acodec.length-1]);}
        // console.dir(vcodec.at(vid));
        saurl = acodec[aid].url;
        svurl = vcodec[vid].url;
        //fd++;
        /*if (next) {
            if(debug){console.debug('NEXT NON LIVE ITEM REQUESTED!!!!');}
            mpv.send({ command: [ 'playlist-play-index', next ] })
        }*/
    }
    if (!fullscreen && !refreshMetadata){
        child_process.execFile('notify-send', ['Ytdash: ' + metadata[videoId].title,
                                           metadata[videoId].author, '-t', 3000]);
    }
    if(debug){console.debug("AURL: " + saurl);}
    if(debug){console.debug("VURL: " + svurl);}
    //client.write('{ "command": ["drop-buffers"] }\n');
    //let ipcString = { "command": ["loadfile", "fd://" + fd, ["playlist-play-index", fd - 3]] }
    /*if (args.includes('-n')){
        mpv.send({ "command": ["loadfile", "fd://" + fd, 'append-play'] });
    }*/
    //console.debug(ipcString);
    let loadfileMode, ipcCommand;
    let mpvTitle = `${metadata[videoId].title.replace(':',';') + ' - ' + metadata[videoId].author}`;
    mpv.send({ "command": ["set",  "osd-playing-msg", '${media-title}']});
    if (live){
        ipcCommand = { "command": ["set",  "force-media-title", mpvTitle]};
        if(debug){console.debug(ipcCommand);}
        mpv.send(ipcCommand);
        //mpv.send({ "command": ["set",  "osd-italic", "yes"]});
        //mpv.send({ "command": ["set",  "osd-align-x", "center"]});
        //mpv.send({ "command": ["set",  "osd-playing-msg-duration", '4000']});

    }else {
        if (isLive){
            console.warn('\x1b[31m%s\x1b[0m', 'This is a live stream but non-live mode enabled, skipping...');
            return 1;
        }
        if (urlPassthrough){
            // Non-live streams are opened directly by the player:
            ipcCommand = { "command": ["loadfile", `${svurl}`, 'append-play']};
            //ipcCommand = { "command": ["loadfile", `ytdl://${url}`, 'append-play']};
            if (!onlyAudio ){
                ipcCommand.command.push( "audio-file=" + `${saurl}`+
                                          ",force-media-title=" + mpvTitle);
                //ipcCommand.command.push("force-media-title=" + mpvTitle);
            }else{
                ipcCommand.command.splice(1,1, `${saurl}`);
                ipcCommand.command.push("force-media-title=" + mpvTitle);
            }
            mpv.send(ipcCommand);
            return 2;
        }
    }
    //console.log(ipcCommand);
    //mpv.send({ command: [ 'playlist-play-index', next - 1 ] })
    videoQualitiesQuantity = metadata[videoId].video.length;
    murls = [saurl, svurl];
    //if(next){mpv.send({ command: [ 'playlist-next'] })}
    next=false;
    let timeUrlOpen,audioResults,videoResults,startMiliSecsTime,segmenterDurationSecs,
        requestDurationSecs,goUp=false,goDown=false,bandEstAvg,bandEstAvgs=[];
    // Main loop:
    while(resp = await segmentCreator(murls, fd, mpv, isLive, playlistEntryId)){
        if(debug){console.debug('NEXT ITEM REQUESTED?: ' + next);}
        //if (!onlyAudio ){
            videoResults = await resp[1];
            if (videoResults){headers = await videoResults[0];}

        //}
        timeUrlOpen = (new Date() - metadata[videoId].dateTime)/1000;
        if(debug){
            console.debug('URL Expire in Seconds: ' + metadata[videoId].expiresInSeconds);
            console.debug('URL Open Time: ' + timeUrlOpen);
        }
        // Refresh stream metadata after 6hrs URLs lifetime - 1hr:
        //if ( timeUrlOpen >= metadata[videoId].expiresInSeconds - 3600){
        if ( timeUrlOpen >= 25){
            if(debug){console.debug('URLS Expired. Refreshing.' );}
            //console.debug('URLs Expired. Refreshing stream metadata...');
            //metadata[videoId] = 0;
            metadata = {};
            //console.info('METADATAAAAA: ');
            //console.info(metadata);
            return openURL(url,fd, mpv, sq + 1, false, true);
        }
        if (next) {
            if(debug){console.debug('NEXT ITEM REQUESTED!!!!' + next);}
            /*await resp[1];
            await resp[0];
            next=false;*/
            next=false;
            if (isLive){
                //mpv.send({ command: [ 'playlist-next'] });
                //mpv.send({ command: [ 'playlist-play-index', 'current' ] })
            } else{
                await resp[1];
                await resp[0];
                //mpv.send({ command: [ 'playlist-play-index', next] })
            }
            return 2;
            //break;
        }
        audioResults = await resp[0];
        await audioResults[0];
        if (!audioResults || (!videoResults && !onlyAudio)){
            let errorMsg = 'Unable to stream media content, giving up.';
            if(!fullscreen){
                child_process.execFile('notify-send', ['YTdash: ' +
                        metadata[videoId].title, errorMsg, '-t', 3000]);
            }
            console.info(errorMsg);
            //mpv.send({ "command": ["playlist-next"] });
            return 1;
        }
        //console.dir(headers)
        if (isLive || isPostLiveDvr){
            sq++;
            if(!onlyAudio){
                bandEst = headers['x-bandwidth-est']/8/1024;
                bandEst2 = headers['x-bandwidth-est2']/8/1024;
                bandEst3 = headers['x-bandwidth-est3']/8/1024;
                bandEstComp = headers['x-bandwidth-est-comp']/8/1024;
                bandEstAvg = (bandEst + bandEst2 + bandEst3)/3;
                bandEstAvgs.push(bandEstAvg);
                if (bandEstAvgs.length > 5 ){bandEstAvgs.shift();}
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
                if ( !fixed && !goDown && vid < videoQualitiesQuantity - 1){
                    if (bandEstAvg>1.3*(minBandwidthRequired/8/1024) &&
                        metadata[videoId].video[vid+1].$.height<=maxHeight){
                        goUp=true;
                        if(debug){console.debug('====>> GOING UP');}
                        vid++;
                        vurl = metadata[videoId].video[vid].BaseURL;
                        minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
                    }
                // Check to go down:
                }
                goDown=false;
                if ( !fixed && !goUp && vid > 0 && segmentsDurationsSecsAvg > segmentDurationSecs * 1.2 &&
                    segmentsDurationsSecs[2] > segmentDurationSecs * 1.2 ){
                    //if (bandEstAvg<1.5*(minBandwidthRequired/8/1024)){
                        if(debug){console.debug('====>> GOING DOWN');}
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
                murls[1] = vurl + manifestSequencePath + sq;
            }
            if(audioResults[2]){
                //aurl = audioResults[2].slice(0,audioResults[2].indexOf(manifestSequencePath))
                aurl = audioResults[2] + '/';
                if(debug){console.debug('----------->> NEW AURL HREF: ' + aurl);}
            }
            //murls = [audioResults[2], videoResults[2]];
            //console.dir(murls);
            murls[0] = aurl + manifestSequencePath + sq;
        } else {
            console.info("Video ended.");
            //metadata[videoId]['downloadFinished'] = 1;
            return 3;
        }

    }
}
    /*}else{
    console.info("Video NON LIVE.");
        client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl} ,force-media-title=${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
    }*/
//}
//main()
async function apiSearch(query){
    let items,apiBaseURL,apiParameters = {},midURL,apiUrlCheckLive,apiType,
    urlEnd,apiURL,jsonResponse,videoIds = [], cacheFilename = cacheDir + '/';

    apiBaseURL = 'https://www.googleapis.com/youtube/v3/';
    midURL = new URLSearchParams(apiParameters).toString();
    apiUrlCheckLive = apiBaseURL + 'videos?' + midURL;
    apiType = 'search';
    apiParameters.q = query;
    apiParameters.type = 'video';
    apiParameters.order = 'relevance';
    apiParameters.videoDimension = '2d';
    //apiParameters['regionCode'] = 'AR';
    apiParameters.safeSearch = 'none';
    apiParameters.videoDuration = 'any';
    apiParameters.videoType = 'any';
    apiParameters.type = 'video';
    apiParameters.videoLicense = 'any';
    apiParameters.videoDefinition = 'any';  // high|any
    apiParameters.maxResults = 5;
    apiParameters.videoEmbeddable = 'any';
    apiParameters.videoSyndicated = 'true';
    if (order){apiParameters.order = orderType;}
    if (live){apiParameters.eventType = 'live';}
    if (args.includes('-c')){apiParameters.eventType ='completed';}
    if (args.includes('-u')){apiParameters.eventType ='upcoming';}
    if (maxResults > 0 && maxResults <= 50){
        apiParameters.maxResults = maxResults;
    }
    for (let parameter in apiParameters) {
        cacheFilename += parameter + '=' + apiParameters[parameter] + '+';
    }
    cacheFilename = cacheFilename.slice(0,249);
    cacheFilename += '.cache';
    if( !noDiskCache && fs.existsSync(cacheFilename)) {
        let stats,cachedResponse;
        stats = fs.statSync(cacheFilename);
        if (((new Date() - stats.birthtime)/1000)/60 < 24*60 ){
            cachedResponse = fs.readFileSync(cacheFilename);
            if(cachedResponse){
                try {
                    items = JSON.parse(cachedResponse);
                } catch {
                    console.info("Cannot parse JSON from cached file.");
                }
            } else {
                if(debug){console.debug("Cannot get JSON from cache file.");}
            }
        } else{ fs.unlinkSync(cacheFilename); }
    }
    if (!items) {
        apiParameters.part = 'snippet';
        apiParameters.key = 'AIzaSyBSnNQ7qOmLPxC5CaHH9BWHqAgrecwzCVA';

        apiParameters.fields = 'items(id,snippet/title,snippet/' +
                                  'channelTitle,snippet/description,' +
                                  'snippet/liveBroadcastContent,' +
                                  'snippet/publishedAt)';
        urlEnd = new URLSearchParams(apiParameters).toString();
        apiURL = apiBaseURL + apiType + '?' + urlEnd;
        if(debug){console.debug("API URL: " + apiURL);}
        jsonResponse = await request(apiURL, "GET",
                                    {'Referer':'www.youtube.com/test'});
        if (jsonResponse[1]){
            jsonResponse = JSON.parse(jsonResponse[1]);
            items = jsonResponse.items;
            if(debug){console.dir(items);}
            fs.writeFileSync(cacheFilename, JSON.stringify(items));

        }
    } else { console.info('ºº Using cached search results. ºº');}
    console.dir(items);
    items.forEach(item=>videoIds.push(item.id.videoId));
    if(debug){console.dir("videoIds" + videoIds);}
    return videoIds;
}

let results=[0];
var metadata={},aid,vid;
// MAIN ULTRA_ASYNC_GENERIC_LOOP_2000:
async function  main() {
    fs.mkdirSync(cacheDir, {recursive:true});
    fs.mkdirSync(configDir, {recursive:true});
    let mpvStdio = {stdio: ['ignore', process.stdout, process.stderr, 'ipc']},
        parameter,urls;
    if(debug){console.debug('ARGS: %o', args);}
    urls = args.filter(e=>e!=='-s' && e!=='-n'&& e!=='-u'&& e!=='-f' &&
                       e!=='-debug' &&  e!=='-mw' &&  e!=='-mh' &&
                       e!=='-mf' && (e.startsWith('http') ||
                       e.length === 11 ) && e!=='-F' && e!=='-fixed' &&
                       e!=='-fullscreen' && e!=='-e' && e!=='-extra' &&
                       e!=='-h' && e!=='-help' && e!=='-order' &&  e!=='-vc' &&
                       e!==orderType &&  e!=='-ac' &&  e!=='-nc' &&
                       e!=='-nv' && e!=maxWidth && e!=maxHeight && e!=maxFps &&
                       e!=maxResults
                       );
    if(searchMode){
        if (searchTerm){
            urls = await apiSearch(searchTerm);
            if(debug){console.dir(urls);}
            if (!urls.length){
                console.info("0 videos found.");
                process.exit();
            }
        }else{
            console.info('No search string given.');
            process.exit();
        }
    }
    
    if(!urls.length){ console.info("No URLs given."); process.exit();}
    if(debug){console.debug('URLS: %o', urls);}
    /*for (let times=0; times < urls.length;times++){
                mpvStdio.stdio.push('pipe');
                //console.log('Mpv STDIO: %o', mpvStdio.stdio)
            }*/
    let initialFd = 4;
    await urls.forEach((e)=>{
        mpvStdio.stdio.push('pipe');
        /*if(args.includes('-n')){
            mpvargs += ' fd://' + initialFd;
            initialFd++;
        }*/
    });
    //if(debug){console.debug('Mpv STDIO: %o', mpvStdio.stdio)}
    const mpv = child_process.spawn('mpv', mpvargs.split(' '),mpvStdio);
    //mpv.stdin._writableState.highWaterMark=1024;

    mpv.on('exit', ()=>{
        console.info('Player closed, exit...');
        process.exit();
    });

    mpv.on('message', message=>{
        let event, itemEntryId, reason;
        if(debug){console.log(message);}
        //console.log(message)
        event = message.event;
        itemEntryId = message.playlist_entry_id;
        reason = message.reason;
        /*if ( message.event === 'end-file' && reason==='stop' &&  !args.includes('-n') ){
            // Interrupt download and get next only if not already download
            //if (results.filter(result=>result>1).length > itemEntryId){
            //    next=itemEntryId;
            //}
            next=itemEntryId
            //console.log('THIS IS THE NEXT SHIT' + next)
        }*/
        if ( message.event === 'end-file' && reason==='stop' && live){
            //next=itemEntryId;
            next=1;
        }
        /*if ( message.event === 'start-file' ){
            console.log('Starting Playlist ID:' + itemEntryId);
            next=itemEntryId;

        }*/
    });
    //mpv.send({ "command": ["observe_property", 1, "playback-abort"] });
    //mpv.send({ "command": ["observe_property", 1, "cache-buffering-state"] });
    //mpv.send({ "command": ["observe_property", 1, "playlist-pos"] });
    //mpv.send({ "command": ["observe_property", 1, "playlist-next"] });
    if(live){
        mpv.send({ "command": ["loadfile", "fd://4", 'append-play']});
        mpv.send({ "command": ["set", "loop-playlist", "inf"]});
    }
    let result,
        results=[],
        eid=0,
        init=1,
        fd=4;
    while(true){

        if(!live){
            result = await openURL(urls[eid], fd, mpv);
            results.splice(eid, 1, result);
            fd++;
            eid++;
            if(eid > urls.length - 1){
                /*eid=0;
                fd=4;
                for (let result of results){
                    if (result !== 1){
                        mpv.send({ "command": ["loadfile", "fd://" + fd, 'append-play'] });
                        fd++
                    }
                }*/
                break;
            }
            //if (result !==2){break;}
        }else{
            /*if (init){
                //Pre-cache next URL metadata informations:
                if (urls[eid+1]){
                    result = openURL(urls[eid + 1], fd, mpv, 0, 1);
                    results.splice(eid + 1, 1, result);
                }
            }*/
            if (results[eid]!==1){
                result = await openURL(urls[eid], fd, mpv, 0, 0);
                results.splice(eid, 1, result);
            }
            // if all results are different from '2' (next item requested) quit:
            if (results.length === urls.length && results.every(result=>result!==2)){
                mpv.kill();
                break;
            }
            eid++;
            if(urls.length < eid + 1){eid=0;init=0;}
        }
    }
    if(results.every(result=>result!==2)){
        console.info('No more videos to play.');
        mpv.kill();
    }
}
main();
if(debug){console.debug('OUT');}
