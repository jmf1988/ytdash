#!/usr/bin/env node
/*jshint esversion: 8 */
"use strict";
const http = require('https'),
      net = require('net'),
      child_process = require('child_process'),
      parseString = require('xml2js').parseString,
      zlib = require('zlib'),
      keepAliveAgent = new http.Agent({ keepAlive: true }),
      urls = process.argv.slice(2),
      apiKey='AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
      metadataUrl = 'https://www.youtube.com/youtubei/v1/player?key=' + apiKey;

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
ffmuxoutargs = ' -c copy -f mpegts -bsf:v h264_mp4toannexb -copyts -flags +low_delay ';
ffmuxargs = '-v warning -nostdin -xerror' +
            ffmuxinargs + 'async:pipe:3' +
            ffmuxinargs + 'async:pipe:4' +
            ffmuxoutargs + 'pipe:1';
//-tune zerolatency -write_index 0 -f_strict experimental -syncpoints timestamped
const mpvargs =   '--idle ' +
                  '--input-ipc-server=/tmp/mpvsocket ' +
                  '--player-operation-mode=pseudo-gui ' +
                  //'--profile=low-latency ' +
                  //'--demuxer-lavf-linearize-timestamps=yes ' +
                  //'--demuxer-seekable-cache=yes ' +
                  //'--demuxer-max-bytes=' + 50 * 1048576 + ' ' +
                  //'--demuxer-max-back-bytes=' + 50 * 1048576 + ' ' +
                  '--cache=yes ' +
                  //'--cache-secs=60 ' +
                  '--loop-playlist=force ' +
                  '--prefetch-playlist=yes ' +
                  //'--playlist=fd://0 ' +
                  //'--audio-file=fd://3' +
                  //' fd://3 ' +
                  //'--reset-on-next-file=all ' +
                  //'--video-latency-hacks=yes ' +
                  //'--demuxer-lavf-o-add=fflags=+nobuffer ' +
                  //'--no-correct-pts ' +
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
    console.debug('PRE POST.');
    postRes = await request(url, 'POST', headers);
    //await new Promise((r)=>{setTimeout(r, 5000)});
    console.debug('POST POST.');
    jsonResponse = JSON.parse(postRes[1]);
    //console.dir(jsonResponse.microformat);
    videoDetails = jsonResponse.videoDetails;
    playabilityStatus = jsonResponse.playabilityStatus;
    if (playabilityStatus.status !== 'OK'){
        console.debug('Stream status: %o', playabilityStatus.status);
        console.debug('Reason: %o', playabilityStatus.reason);
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
    console.log("Status: %o", playabilityStatus.status);
    console.log('Title: %o', videoDetails.title);
    console.log('Author: %o', videoDetails.author);
    console.log('Channel Id: %o', videoDetails.channelId);
    console.log('Is Live: ', (videoDetails.isLive||false));
    console.log('Views: ', Number(videoDetails.viewCount));
    if (latencyClass) {
		mediaMetadata.latencyClass = latencyClass.slice(42).replace('_',' ');
        console.log('Latency Class: %o', mediaMetadata.latencyClass);
    }
    console.log('Short Description: \n' + videoDetails.shortDescription);
    if (videoDetails.isLive){
        dashManifestURL = streamingData.dashManifestUrl;
        console.debug('DASH Manifest URL:'+ dashManifestURL);
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
            console.log(printStr);
        }
    }
    // Change url to redirectors:
    //u.protocol + '//redirector.' + 'googlevideo.com' + u.pathname + u.search
    return mediaMetadata;
}

async function request(url, type='GET', headers={}, ioo=0, redir=0) {
    console.log("REQUEST TYPE: " + type);
    url = new URL(url);
    headers.Accept = '*/*';
    headers['User-Agent'] = 'YTdash/0.19';
    //headers['Connection'] = 'keep-alive';
    //headers['Range'] = 'bytes=0-1024000';
    //headers['Accept-Encoding'] = 'gzip';
    headers['Access-Control-Expose-Headers'] = 'Content-Length';
    //var httpRetries = 5;
    var retrySecs = 5,
        bytesWritten=0;
    var body ='';
    let options = { host: url.host,
                port: 443,
                path: url.pathname + url.search,
                headers: headers,
                method: type };
    options.agent = keepAliveAgent;
    let Ans = new Promise((resolve, reject) => {
        function retriableRequest(){
            let r;
            r = http.request(options, function(res) {
                let responseHeaders = res.headers;
                var statcode = res.statusCode;
                console.log("REUSED SOCKET: " + r.reusedSocket);
                console.log("HTTP Response Code: " + res.statusCode);
                //console.log("HTTP Version: " + res.httpVersion);
                if( type==='POST' ){
                    res.setEncoding('utf8');
                } else if (type==='GET'){
                    body = [];
                } else{
                    console.log("HEADERS: " + res.rawHeaders);
                }
                if(statcode === 301 || statcode === 302) {
                    url = new URL(res.headers.location);
                    options.host = url.host;
                    options.path = url.pathname + url.search;
                    return retriableRequest();
                    //return request(res.headers.location, type='GET',
                    //        headers, ioo, 1);
                } else if (statcode === 200||statcode === 204||statcode === 206){
                    // data no se llama with a HEAD request:
                    /*res.on('readable', () => {
                            let chunk;
                            while (null !== (chunk = res.read(102400))) {
                                console.log(`Received ${chunk.length} bytes of data.`);
                                if (type==='GET'){
                                    body.push(chunk);
                                }else{
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
                                            res.pause();
                                            ioo.end()
                                            //ioo.uncork();
                                            //ioo.uncork();
                                            //r.emit('end', '');
                                            //res.end()
                                            res.destroy(new Error('Next item requested '));
                                            //res.destroySoon()
                                            //r.destroy( new Error('Next item requested '));
                                        }
                                    } else{
                                        console.log('Http error on the other media content, cancelling ');
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
                        console.log("==>>> RUNNiNG REQUEST END EVENT ");
                        // Close fds or ffmpeg don't close:
                        if(type==='GET'){
                            if (ioo!==0 ){ioo.end();}
                            /*if (next){
                                console.log('Next item requested. ');
                                res.destroy();
                            }*/
                            body = Buffer.concat(body);
                        }
                        console.log("==>>> PRE RESOLVE ");
                        //if(!next){
                        resolve([responseHeaders, body, url.href]);
                        //}else{resolve(1);}
                    });
                    /*res.on('error',(err)=>{
                        console.log("Error on response: " + err);
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
                        console.log("Retrying, remaining tries: " + httpRetries);
                        //res.emit('end', null);
                        //retriableRequest();

                    } else{
                        console.log('HTTP error code: ' + res.statusCode);
                        res.destroy(new Error('Http error on the other media content, cancelling '));
                        //resolve(null);
                    }
                } else{
                    res.destroy(new Error('HTTP error code: ' + statcode));

                }
            });
            r.on('error', async function(err) {
                console.log("Got error: " + err.message);
                console.log("Error code: " + err.code);//if (r.reusedSocket && err.code === 'ECONNRESET') {
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
                    console.log("Trying to resume from byte=" + bytesWritten);
                    options.headers['Range'] = 'bytes=' + bytesWritten + '-';
                    await new Promise((r)=>{setTimeout(r, 2000)});
                    return retriableRequest();

                }else{
                    if (ioo!==0 ){ioo.end();
                        //ioo.destroy();
                        r.destroy();
                    }
                    //
                    console.log("Resolving...");
                    resolve(1);
                    console.log("Resolved...");
                }
            });
            if (type==='POST'){
                r.write(JSON.stringify(metaPostdata));
            }
            r.end();
        }
        retriableRequest();
        /*var id = setInterval(retriableRequest();
            if (httpRetries<1) clearInterval(Id);
        , retrySecs*1000);*/
    });
    console.log("PRE Return");
    return Ans;
}

function segmentCreator(sq, murls,fd){
    var ffmpeg;
    let audioRequest,
        videoRequest;
    let segmenter = new Promise((resolve, reject) => {
        ffmpeg = child_process.spawn('ffmpeg', ffmuxargs.split(' '),
                { stdio: ['ignore', mpv.stdio[fd], process.stderr,
                          'pipe', 'pipe']
                });
            //let audioRequest=request(murls[0],'GET',{},mpv.stdio[3]);
            //let videoRequest=request(murls[1],'GET',{},mpv.stdio[4]);
        ffmpeg.on('error', (err)=>{
            console.log('FFmpeg Muxer error: ' + err);
            resolve(1);
        });
        ffmpeg.on('spawn',()=>{
            httpRetries=5;
            audioRequest=request(murls[0],'GET',{},ffmpeg.stdio[3]);
            videoRequest=request(murls[1],'GET',{},ffmpeg.stdio[4]);
            console.log('Audio PREresolved: ');
            resolve([audioRequest, videoRequest]);
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
    console.log('RETURNING...');
    return segmenter;
}


async function openURL(url,fd){
        let sq,
        //metadata={},
        segmentDurationSecs,
        segmentsDurationsSecs = [],
        segmentsDurationsSecsPro,
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
    if(!url){ console.log("No URL detected"); return;}
    if (!url.startsWith('#')){
        if (url.length !== 11) {
            let urlp;
            try {
                urlp = new URL(url);
            }
            catch(error){
                console.log('URL Error: %o with Input: %o ',
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
            console.log('Openning VideoId: ' + url);
            videoId = url;
        }
    }else {
        console.log('Playlist Item Info: ' + url);
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
    console.log("MMMMEEETTAADDDDAAATTAEEEEEE!!: " + metadata[videoId])
    if (!metadata[videoId]){
        metadata[videoId] = await getMetadata(metadataUrl,
                                              metaPostHeaders);
        console.log("DATE CREATION ADDED: " );
        //console.dir(metadata[videoId]);
    } else{
        console.log("Using cached video details." );
    }
    // If a video Id gives metadata errors it's skipped next time:
    if (metadata[videoId]===1){
            //console.log('Removing %s from playlist', videoId);
            //urls = urls.filter(item=>item!==videoId);
            //deadVideoIds++;
            console.log('Skipping Video Id: %s.', videoId);
            return 1;
        } else{
            metadata[videoId].dateTime = dateTime;
        }
    //console.dir(metadata[videoId]);
    // Live or not?:
    if (metadata[videoId].isLive){
        aid=-1;
        vid=3;
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
        vid=2; // Defaulting to low/medium video quality by sort.order:
        acodec = metadata[videoId].audio.webm.opus;
        vcodec = await metadata[videoId].video.mp4.avc1;
        aid=acodec.length-1; // Defaulting to highest audio quality by sort.order:
        //console.dir(metadata[videoId].video.mp4);
        if (vcodec.every(elem=>elem.signatureCipher)){
            //vcodec[0].signatureCipher
            console.warn('===>>> Ciphered videos are not supported.');
            metadata[videoId]===1;
            return 1;
            //return 1;
            //process.exit();
        }
        console.dir(acodec[acodec.length-1])
        // console.dir(vcodec.at(vid));
        saurl = acodec[aid].url;
        svurl = vcodec[vid].url;
    }
    console.debug("AURL: " + saurl);
    console.debug("VURL: " + svurl);
    //client.write('{ "command": ["drop-buffers"] }\n');
    //if (!fd){fd=3;}else{fd=0;}
    /*if (result[0] === 2 && result[1] !== fd) {
        nextAvailable=1;
    }else{
        nextAvailable=0;
    }*/
    let ipcString = `{ "command": ["loadfile", "fd://${fd}", "append-play", "force-media-title=${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`
    console.log(ipcString);
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
    let audioResults,videoResults,startMiliSecsTime,segmenterDurationSecs,goUp,goDown,bandEstPro,bandEstPros=[];
	while(resp = await segmentCreator(sq, murls, fd)){
		console.log('NEXT ITEM REQUESTED?: ' + next);
		audioResults = resp[0];
        videoResults = await resp[1];
        headers = await videoResults[0];
        if (next) {
            console.log('NEXT ITEM REQUESTED!!!!');
            return 2;
            //break;
        }
        //console.dir(headers)
        if (metadata[videoId].isLive){
            bandEst = headers['x-bandwidth-est']/8/1024;
            bandEst2 = headers['x-bandwidth-est2']/8/1024;
            bandEst3 = headers['x-bandwidth-est3']/8/1024;
            bandEstComp = headers['x-bandwidth-est-comp']/8/1024;
            bandEstPro = (bandEst + bandEst2 + bandEst3)/3;
            bandEstPros.push(bandEstPro);
            if (bandEstPros.length > 5 ){bandEstPros.shift()};
            bandEstPro = 0;
            bandEstPros.forEach(e=>bandEstPro+=e);
            bandEstPro /= 5;
            console.debug('SEQUENCE NUMBER: ' + sq);
            console.debug("VID: " + vid);
            console.debug('BAND EST: ' + bandEst + ' Kb/s');
            console.debug('BAND EST2: ' + bandEst2 + ' Kb/s');
            console.debug('BAND EST3: ' + bandEst3 + ' Kb/s');
            console.debug('BAND PRO: ' + bandEstPro + ' Kb/s');
            console.debug('BAND PROS: ' + bandEstPros);
            console.debug('MIN BAND REQ: ' + minBandwidthRequired/8/1024);
            console.debug('BAND EST COMP: ' + bandEstComp + ' Kb/s');
            // Check to go up in media quality:
            if ( !goDown && vid < videoQualitiesQuantity - 1){
                if (bandEstPro>2*(minBandwidthRequired/8/1024) && metadata[videoId].video[vid+1].$.height<=maxHeight){
                    goUp=true;
                    console.log('====>> GOING UP')
                    vid++;
                    vurl = metadata[videoId].video[vid].BaseURL;
                    minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
                }
        // Check to go down:
            } 
            goDown=false;
            if (!goUp && vid > 0 && segmentsDurationsSecsPro > segmentDurationSecs * 1.2 && segmentsDurationsSecsPro[2] > segmentDurationSecs * 1.2 ){
                if (bandEstPro<1.6*(minBandwidthRequired/8/1024)){
					console.log('====>> GOING DOWN')
					goDown=true;
                    vid--;
                    vurl = metadata[videoId].video[vid].BaseURL;
                    minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
                }
            }
            goUp=false;
            sq++;
            await audioResults;
	        await audioResults[0];
	        if(audioResults[2]){ 
				aurl = audioResults[2].slice(0,audioResults[2].indexOf(manifestSequencePath)) 
				console.log('----------->> NEW AURL HREF: ' + aurl)
	        }
	        if(videoResults[2]){
				vurl = videoResults[2].slice(0,videoResults[2].indexOf(manifestSequencePath)) 
				console.log('----------->> NEW VURL HREF: ' + vurl)
	        }
	        //murls = [audioResults[2], videoResults[2]];
	        //console.dir(murls);
            murls[0] = aurl + manifestSequencePath + sq;
            murls[1] = vurl + manifestSequencePath + sq;
            
        } else {
            console.info("Video ended.");
            return 3;
        }
        if(startMiliSecsTime) {
			segmenterDurationSecs = Math.round((performance.now() - startMiliSecsTime))/1000;
			segmentsDurationsSecs.push(segmenterDurationSecs);
			if (segmentsDurationsSecs.length > 3) {
				segmentsDurationsSecs.shift();
			}
			segmentsDurationsSecsPro = 0;
			segmentsDurationsSecs.forEach(e=>segmentsDurationsSecsPro+=e);
			segmentsDurationsSecsPro /= 3;
			console.log('-----------> Segments Durs: ' + segmentsDurationsSecs);
			console.log('-----------------------> DOWNLOADs Pro DURATION: ' + segmentsDurationsSecsPro + ' secs');
		
		}
		
        startMiliSecsTime = performance.now();
    }
}
    /*}else{
    console.info("Video NON LIVE.");
        // client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl}"] }\n`);
        // client.read().toString()
        client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl} ,force-media-title=${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
    }*/
let mpvStdio = {stdio: ['ignore', process.stdout, process.stderr]}
for (let times=0; times < urls.length;times++){
            mpvStdio.stdio.push('pipe');
            console.log('Mpv STDIO: %o', mpvStdio.stdio)
        }

const mpv = child_process.spawn('mpv', mpvargs.split(' '),mpvStdio);
//mpv.stdin._writableState.highWaterMark=1024;

//mpv.connected
mpv.on('exit', ()=>{
    console.log('Player closed, exit...');
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
            console.log('Mpv IPC Channel Unavailable yet.' + err);
            //process.exit();
        }).on('data', async (rawEvents)=>{
            // Multiline events  can come so:
            const eventsList = rawEvents.toString().split('\n').slice(0,-1);
            for (let strEvent of eventsList) {
                let event = JSON.parse(strEvent);
                console.log('IPC Event: ');
                console.dir(event);
                // console.dir(JSON.parse(event));
                if ( event && event.event === "seek" ){
                    console.log('Seek ');
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
                    console.dir(results);
                    console.dir(results.slice(cid-1));
                    if(!results.slice(cid-1).some(e=>e>=2)){
                        console.log('OPENNING NEXT FILE ');
                        //client.write('{ "command": ["stop", "keep-playlist"] }\n');
                        client.write('{ "command": ["stop"] }\n');
                        next=1
                   }

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
    }, 20);
});
//}
//main()
/*main().then((returnCode)=>{
    if(returnCode===1 && !mpv.exitCode){
        mpv.kill();
    }
});*/
let results=[0],
    nextAvailable;
//let  = openURL(urls[eid]);
//async()=>{urls.filter(openURL)}
//console.log('URLS' + urls);
var metadata={};
// MAIN ULTRA_ASYNC_GENERIC_LOOP_2000:
(async()=>{
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
				console.log('All videos had errors...');
				break;
			}else if (results.filter(e=>e>1).every(r=>r>=2)){
				if (!Object.entries(metadata).every(([l,e])=>{return e.isLive})){
			        console.log('ALl urls are non live.');
			        console.log('All videos already downloaded...');
			        break;
			    }
			};
            eid=0;
            fd=3;
        };
        if ( !results[eid] || results[eid] < 4 ){
			result = await openURL(urls[eid], fd);
			results.splice(eid, 1, result);
		}
        eid++;
        if(result>=2){
			fd++;
		}
        console.log('Trying to open input URL: ' + urls[eid]);
        console.log('Results ' + results);
    };
    console.log('No more videos to play.');
    //mpv.kill();
})();
async function main() {
    let deadVideoIds=0;
    //var httpRetries = 5;
    while (1){
        console.dir(urls);
        if( deadVideoIds === urls.length) {
            console.log('All video have errors, quitting. ');
            return 1;
        }
        for (let url of urls){
            //console.log('Respppppp ' + resp);
            /*if(!resp && !next){
                metadata[videoId]=1;
            }*/
            result = await openURL(url);
            /*if(next){
                console.log('Openning next url. ' + resp);
            }else{
                console.log('There are no more urls to play.');
                return 1;
            }*/
        }
        await new Promise((r)=>{setTimeout(r, 1000)})
    /*if (Object.entries(metadata).every(([l,e])=>{return e.isLive})){
        console.log('ALl urls are non live.');
        return 3
    }*/
    //if (!metadata[videoId].isLive){return 3}
    }
}
console.log('OUT');
