#!/usr/bin/env node
/*jshint esversion: 8 */
"use strict";
const http = require('https'),
	  net = require('node:net'),
	  child_process = require('node:child_process'),
      parseString = require('xml2js').parseString,
      zlib = require('node:zlib'),
	  keepAliveAgent = new http.Agent({ keepAlive: true }),
	  urls = process.argv.slice(2),
	  apiKey='AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8',
	  metadataUrl = 'https://www.youtube.com/youtubei/v1/player?key=' + apiKey;

// Variables:
let		ffbaseinputs = '',
		ffbaseargs = '',
		ffmuxinargs,
		ffmuxoutargs,
		urlPassthrough=1,
		ffmuxargs,
		playlist_entry_id=1,
		ffmpegbase,
		next=0,
		client,
		Id,
		maxWidth = 1360,
		maxFps = 60,
		maxHeight = 720;
var httpRetries = 5;
// ffmpeg base Args (all single spaces or ffmpeg fails 'cause split()):
ffbaseargs += ffbaseinputs + '-y -v 0 -flags +low_delay -thread_queue_size 512 -i -';
ffbaseargs += ' -c copy -f nut -bsf:v h264_mp4toannexb';
ffbaseargs += ' -flags +low_delay -';
// ffmpeg muxer:
ffmuxinargs = ' -thread_queue_size 100512 -flags +low_delay -i async:';
ffmuxoutargs = ' -c copy -f mpegts -bsf:v h264_mp4toannexb -tune zerolatency -copyts -flags +low_delay ';
ffmuxargs = '-v warning -nostdin -xerror' +
			ffmuxinargs + 'pipe:3' +
			ffmuxinargs + 'pipe:4' +
			ffmuxoutargs + 'pipe:1';
//-write_index 0 -f_strict experimental -syncpoints timestamped 
const mpvargs =   '--idle ' +
				  '--input-ipc-server=/tmp/mpvsocket ' +
				  '--player-operation-mode=pseudo-gui ' +
				  '--profile=low-latency ' +
				  //'--demuxer-lavf-linearize-timestamps=yes ' +
				  //'--demuxer-seekable-cache=yes ' +
				  //'--demuxer-max-bytes=' + 50 * 1048576 + ' ' +
				  //'--demuxer-max-back-bytes=' + 50 * 1048576 + ' ' +
				  '--cache=yes ' +
				  //'--cache-secs=60 ' +
				  '--loop-playlist ' +
				  //'--playlist=fd://0 ' +
				  //'--audio-file=fd://3' +
				  //' fd://4 '
				  '--reset-on-next-file=all ' +
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
				 //' -'
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
	mediaMetadata.title = videoDetails.title.replaceAll(',',';');
	mediaMetadata.author = videoDetails.author.replaceAll(',',';');
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
		console.log('Latency Class: %o',
		            latencyClass.slice(42).replace('_',' '));
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
											ioo.end()
											//ioo.uncork();
											//ioo.uncork();
											//res.pause();
											//res.emit('end', null);
											res.destroy(new Error('Next item requested '));
											//r.destroy( new Error('Next item requested '));
										}
									} else{
										console.log('Http error on the other media content, cancelling ');
										res.destroy(new Error('Http error on the other media content, cancelling ')); 
										//r.destroy(new Error('Http error on the other media content, cancelling ')); 
										//res.emit('end', null);
										//return
										
									}
								//	}
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
						resolve([responseHeaders, body]);
						//}else{resolve(1);}
					});
					/*res.on('error',(err)=>{
						console.log("Error on response: " + err);
					});*/
				} else if(statcode === 403||statcode === 404||statcode === 503){
					if (httpRetries>0) {
						/*(function loop() {
						    setTimeout(function() {
						        // Escriba su lógica aquí
								retriableRequest();
						        loop();
						    }, retrySecs*1000);
							})();*/
							httpRetries--;
						console.log("Retrying, remaining tries: " + httpRetries);
						//res.emit('end', null);
						retriableRequest();
						
					} else{
						console.log('HTTP error code: ' + res.statusCode);
						res.destroy(new Error('Http error on the other media content, cancelling '));
						//resolve(null);
					}		
				} else{
					res.destroy(new Error('HTTP error code: ' + statcode));
					
				}
			});
			r.on('error', function(err) {
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
				if (err.code === 'EAI_AGAIN' || err.code === 'ECONNRESET'){
					//ioo.end();
					console.log("Trying to resume from byte=" + bytesWritten);
					options.headers['Range'] = 'bytes=' + bytesWritten + '-'
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
		ffmpeg.on('spawn',()=>{
			httpRetries=5;
			audioRequest=request(murls[0],'GET',{},ffmpeg.stdio[3]);
			videoRequest=request(murls[1],'GET',{},ffmpeg.stdio[4]);
			console.log('Audio PREresolved: ');
			audioRequest.then((ar)=>{
					console.log('Audio Resolved: %o', ar);
					videoRequest.then((vr)=>{
						console.log('Video Resolved: %o', vr);
						resolve(vr);
						//audioRequest.then((ar)=>{resolve(vr)})
					});
			});
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
		/*ffmpeg.on('error', (err)=>{
			console.log('FFmpeg Muxer error: ' + err);
			resolve(null);
		});*/
	});
	console.log('RETURNING...');
	return segmenter;
}


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
async function openURL(url,fd){
		let sq,
		metadata={},
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
	if(!url){ return;}
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
		manifestSequencePath = 'sq/';
		let manLessSequencePath = '&sq='; // bandwidth limited by YouTube;
		// Get Live HEADers metadata:
		let headRes = await request(aurl, 'HEAD');
		sq = headRes[0]['x-head-seqnum'] - 3;
		//metadata[videoId]['x-head-time-sec'] = headRes[0]['x-head-time-sec'];
		saurl = aurl + manifestSequencePath + sq; 
		svurl = vurl + manifestSequencePath + sq; //+ '&range=0-1024000';
	}else{
		aid=-1; // Defaulting to highest audio quality by sort.order:
		vid=2;
		acodec = metadata[videoId].audio.webm.opus;
		vcodec = await metadata[videoId].video.mp4.avc1;
		//console.dir(metadata[videoId].video.mp4);
		if (vcodec.every(elem=>elem.signatureCipher)){
			//vcodec[0].signatureCipher
			console.warn('===>>> Ciphered videos are not supported.');
			metadata[videoId]===1;
			return 1;
			//return 1;
			//process.exit();
		}
		if (acodec.at(aid));else{aid=-1;}
		if (vcodec.at(vid));else{vid=-1;}
		console.dir(vcodec.at(vid));
		saurl = acodec.at(aid).url;
		svurl = vcodec.at(vid).url;
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
	client.write(ipcString);
	//client.write('{ "command": ["set", "idle", "no"] }\n');
	//client.write(`{ "command": ["force-media-title", "${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
	videoQualitiesQuantity = metadata[videoId].video.length;
	murls = [saurl, svurl];
	next=0;
	// Main loop:
	//client.write('{ "command": ["set", "pause", "no"] }\n')
	//if (metadata[videoId].isLive){
	while(resp = await segmentCreator(sq, murls, fd)){
		console.log('NEXTtttttttttttt ' + next);
		if (next) {
			console.log('NEXT NEXT!!!!');
			return 2;
			//break;
		}
		headers = resp[0];
		if (metadata[videoId].isLive){
			bandEst = headers['x-bandwidth-est']/8/1024;
			bandEst2 = headers['x-bandwidth-est2']/8/1024;
			bandEst3 = headers['x-bandwidth-est3']/8/1024;
			bandEstComp = headers['x-bandwidth-est-comp']/8/1024;
			console.debug('SEQUENCE NUMBER: ' + sq);
			console.debug("VID: " + vid);
			console.debug('BAND EST: ' + bandEst + ' Kb/s');
			console.debug('BAND EST2: ' + bandEst2 + ' Kb/s');
			console.debug('BAND EST3: ' + bandEst3 + ' Kb/s');
			console.debug('BAND EST COMP: ' + bandEstComp + ' Kb/s');
			// Check to go up in media quality:
			if ( vid < videoQualitiesQuantity - 1){
				if (bandEst2>minBandwidthRequired/8/1024 && metadata[videoId].video[vid+1].$.height<=maxHeight){
					vid++;
					vurl = metadata[videoId].video[vid].BaseURL;
					minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
				}
		// Check to go down:
			} else if (vid > 0){
				if (bandEst2<minBandwidthRequired/8/1024){
					vid--;
					vurl = metadata[videoId].video[vid].BaseURL;
					minBandwidthRequired = metadata[videoId].video[vid].$.bandwidth;
				}
			}
			sq++;
			murls[0] = aurl + manifestSequencePath + sq;
			murls[1] = vurl + manifestSequencePath + sq;
		} else {
			console.info("Video ended.");
			return 2;
		}
	}
}
	/*}else{
	console.info("Video NON LIVE.");
		// client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl}"] }\n`);
		// client.read().toString()
		client.write(`{ "command": ["loadfile", "${svurl}", "append-play", "${"audio-file=" + saurl} ,force-media-title=${metadata[videoId].title + ' - ' + metadata[videoId].author}"] }\n`);
	}*/
let mpvStdio = {stdio: ['ignore',process.stdout, process.stderr]}
for (let times=0; times < urls.length;times++){
			mpvStdio.stdio.push('pipe');
			console.log('Mpv STDIO: %o', mpvStdio.stdio)
		}
		
const mpv = child_process.spawn('mpv', mpvargs.split(' '),mpvStdio
						);
//mpv.stdin._writableState.highWaterMark=1024;

//mpv.connected
mpv.on('close', ()=>{
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
			//client.write('{ "command": ["loadfile", "fd://3", "append"] }\n');
			client.write('{ "command": ["observe_property", 1, "playback-abort"] }\n');
			
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
					console.dir(results.slice(cid-1));
					if(!results.slice(cid-1).some(e=>e===2)){
						console.log('OPENNING NEXT FILE ');
						client.write('{ "command": ["stop", "keep-playlist"] }\n');
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
let results=[],
	nextAvailable;
//let  = openURL(urls[eid]);
//async()=>{urls.filter(openURL)}
//console.log('URLS' + urls);

(async()=>{
	let result,
		eid=-1,
		fd=2;
	while (1){
		if (eid > urls.length){
			eid=0;
			fd=3;
		}
		eid++;
		fd++;
		result = await openURL(urls[eid], fd);
		// Exclude bad result from results list;
		if(result && result!==1){
			results.push(result);
			
		}
		console.log('Trying to open input URL: ' + urls[eid]);
	} 
	console.log('No more videos to play.');
})();
console.log('OUT');
// Eliminate double spaces and generate list:
//urls = urls.split(' ').filter(r=>r!=='');

	//try{
	//console.log('Video Id' + videoId);
	//setMpvIPC();
	/*main().then((r)=>{
		r===1 && !mpv.exitCode && mpv.kill();
		//if(r===0) {continue;}
	});*/
	//
	//} catch(Error){
	//	console.log('Error, next urls ' + e );
	//	continue;
	//}finally{continue;}
//}
// Loop Triquiñuela:
/* (function loop() {
	setTimeout(() => {
		// Your logic here
		segmentCreator
		console.log('GNITAIW')
		loop();
		//ffmpeg.stdin.end()
		sq++;
		//delay=2000;
	}, 5100);
	console.log('WAITING')
})();*/
// Try of parallel segmenter:
	/*for (var segmentFFmpeg of segmentsToCreate){
		//await segmentFFmpegStdout[0];
		var a = await segmentFFmpeg;
		console.log('FFMPEG PID: ' + a.pid);
		console.log('SEQUENCE NUMBER: ' + a.stdout._writableState.highWaterMark);
		var writer = new Promise((resolve, reject) => {
			a.stdout.on('data', (chunk) => {
				console.log('CHUNKINGGGGGG: ');
				ffmpegbase.stdin.write(chunk);
			});
			a.stdout.on('end', () => {console.log('ENDINGGGGGG: ');})
			/*let writer = new Promise((resolve, reject) => {
				a.stdout.on('data', (chunk) => {
					//console.log('DATAINGGGGGG: ' + chunk);
					ffmpegbase.stdin.write(chunk);
				});
				a.stdout.on('end', () => {
					resolve(1)
					console.log('ENDINGGGGGG: ' + a);
					//exitCode===0?resolve(1):reject('Error closing FFmpeg muxer: ' + exitCode);
				});
			});
			a.on('close', () => {
				console.log('CLOSINGGGGGG: ');
				resolve(1);
			});
		});*/
// EXAMPLE NON-LIVE DICT: adaptiveMediaFormats.video.mp4.av01[7]
/*{
    itag: 394,
    url: 'https://rr1---sn-j5c5nx-5x2l.googlevideo.com/videoplayback?expire=1667510027&ei=q9pjY7SZHfiPobIPvaSHuAs&ip=200.71.91.57&id=o-AAhjuK7zUJIj7UVSEmqFxk6JWBA6uMGLqacI1NhT3ban&itag=394&aitags=133%2C134%2C135%2C136%2C137%2C160%2C242%2C243%2C244%2C247%2C248%2C271%2C278%2C313%2C394%2C395%2C396%2C397%2C398%2C399%2C400%2C401&source=youtube&requiressl=yes&mh=2o&mm=31%2C29&mn=sn-j5c5nx-5x2l%2Csn-x1x7dn7s&ms=au%2Crdu&mv=m&mvi=1&pl=24&initcwndbps=470000&spc=yR2vp8jLu8GOmrTsZnFvlM-ccWZSEGw&vprv=1&mime=video%2Fmp4&ns=pDDwhPrKkrO4WZ33xlG_ENsI&gir=yes&clen=2499501&dur=267.734&lmt=1662551427560268&mt=1667488006&fvip=2&keepalive=yes&fexp=24001373%2C24007246&c=WEB&txp=5532434&n=mHUN869AeYhWOyhxGh&sparams=expire%2Cei%2Cip%2Cid%2Caitags%2Csource%2Crequiressl%2Cspc%2Cvprv%2Cmime%2Cns%2Cgir%2Cclen%2Cdur%2Clmt&sig=AOq0QJ8wRAIgCA1hq3q43XORBG97KIpuJaE8UW96EMyjwIhAoYr3aHECIFaSzGEAyt-MKEv7iWAgtG5Ali46Zwvk1zLidnuLePsi&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=AG3C_xAwRQIhAOxxIyDFS1jT2YPNhKdhJ4cmf2wdvV8dypZW7cfw8xRzAiBIHXFcv49tgUTObnSEkvyES_TCFfqQnIFxU8eSt17NLA%3D%3D',
    mimeType: 'video/mp4; codecs="av01.0.00M.08"',
    bitrate: 80679,
    width: 144,
    height: 256,
    initRange: { start: '0', end: '699' },
    indexRange: { start: '700', end: '1319' },
    lastModified: '1662551427560268',
    contentLength: '2499501',
    quality: 'tiny',
    fps: 30,
    qualityLabel: '144p',
    projectionType: 'RECTANGULAR',
    averageBitrate: 74686,
    colorInfo: {
      primaries: 'COLOR_PRIMARIES_BT709',
      transferCharacteristics: 'COLOR_TRANSFER_CHARACTERISTICS_BT709',
      matrixCoefficients: 'COLOR_MATRIX_COEFFICIENTS_BT709'
    },
    approxDurationMs: '267734'
  }

//// EXAMPLE NON-LIVE DICT: adaptiveMediaFormats.audio.mp4.mp4a[0]
{
  itag: 140,
  url: 'https://rr1---sn-j5c5nx-5x2l.googlevideo.com/videoplayback?expire=1667510027&ei=q9pjY7SZHfiPobIPvaSHuAs&ip=200.71.91.57&id=o-AAhjuK7zUJIj7UVSEmqFxk6JWBA6uMGLqacI1NhT3ban&itag=140&source=youtube&requiressl=yes&mh=2o&mm=31%2C29&mn=sn-j5c5nx-5x2l%2Csn-x1x7dn7s&ms=au%2Crdu&mv=m&mvi=1&pl=24&initcwndbps=470000&spc=yR2vp8jLu8GOmrTsZnFvlM-ccWZSEGw&vprv=1&mime=audio%2Fmp4&ns=pDDwhPrKkrO4WZ33xlG_ENsI&gir=yes&clen=4334659&dur=267.795&lmt=1662543667104516&mt=1667488006&fvip=2&keepalive=yes&fexp=24001373%2C24007246&c=WEB&txp=5532434&n=mHUN869AeYhWOyhxGh&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cspc%2Cvprv%2Cmime%2Cns%2Cgir%2Cclen%2Cdur%2Clmt&sig=AOq0QJ8wRQIhAOjT-zN_OJMTzELxqK0xUwVqdzrztvv0zVAsd_Sx35jRAiB4BczfuoUoku-coIOmoEqiGi_VWEMvPB06m_xbeM_sww%3D%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=AG3C_xAwRQIhAOxxIyDFS1jT2YPNhKdhJ4cmf2wdvV8dypZW7cfw8xRzAiBIHXFcv49tgUTObnSEkvyES_TCFfqQnIFxU8eSt17NLA%3D%3D',
  mimeType: 'audio/mp4; codecs="mp4a.40.2"',
  bitrate: 130284,
  initRange: { start: '0', end: '631' },
  indexRange: { start: '632', end: '987' },
  lastModified: '1662543667104516',
  contentLength: '4334659',
  quality: 'tiny',
  projectionType: 'RECTANGULAR',
  averageBitrate: 129491,
  highReplication: true,
  audioQuality: 'AUDIO_QUALITY_MEDIUM',
  approxDurationMs: '267795',
  audioSampleRate: '44100',
  audioChannels: 2,
  loudnessDb: -3.1299992
}
//// EXAMPLE NON-LIVE DICT: adaptiveMediaFormats.audio.webm.opus[0]
{
  itag: 249,
  url: 'https://rr1---sn-j5c5nx-5x2l.googlevideo.com/videoplayback?expire=1667510027&ei=q9pjY7SZHfiPobIPvaSHuAs&ip=200.71.91.57&id=o-AAhjuK7zUJIj7UVSEmqFxk6JWBA6uMGLqacI1NhT3ban&itag=249&source=youtube&requiressl=yes&mh=2o&mm=31%2C29&mn=sn-j5c5nx-5x2l%2Csn-x1x7dn7s&ms=au%2Crdu&mv=m&mvi=1&pl=24&initcwndbps=470000&spc=yR2vp8jLu8GOmrTsZnFvlM-ccWZSEGw&vprv=1&mime=audio%2Fwebm&ns=pDDwhPrKkrO4WZ33xlG_ENsI&gir=yes&clen=1431734&dur=267.761&lmt=1662543662803570&mt=1667488006&fvip=2&keepalive=yes&fexp=24001373%2C24007246&c=WEB&txp=5532434&n=mHUN869AeYhWOyhxGh&sparams=expire%2Cei%2Cip%2Cid%2Citag%2Csource%2Crequiressl%2Cspc%2Cvprv%2Cmime%2Cns%2Cgir%2Cclen%2Cdur%2Clmt&sig=AOq0QJ8wRgIhAI3YBaNUCm3Z2UJjm26GKouTucHrhjpxcNIfweA_9_7oAiEAvTNMdk405Cq5X01KxwS898sPZ__L0aUF6WFK5bgMHoY%3D&lsparams=mh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Cinitcwndbps&lsig=AG3C_xAwRQIhAOxxIyDFS1jT2YPNhKdhJ4cmf2wdvV8dypZW7cfw8xRzAiBIHXFcv49tgUTObnSEkvyES_TCFfqQnIFxU8eSt17NLA%3D%3D',
  mimeType: 'audio/webm; codecs="opus"',
  bitrate: 47473,
  initRange: { start: '0', end: '265' },
  indexRange: { start: '266', end: '720' },
  lastModified: '1662543662803570',
  contentLength: '1431734',
  quality: 'tiny',
  projectionType: 'RECTANGULAR',
  averageBitrate: 42776,
  audioQuality: 'AUDIO_QUALITY_LOW',
  approxDurationMs: '267761',
  audioSampleRate: '48000',
  audioChannels: 2,
  loudnessDb: -3.1399994
}
// HEADERS 
> asd.headers
{
  'last-modified': 'Fri, 04 Nov 2022 23:10:46 GMT',
  'content-type': 'audio/mp4',
  date: 'Sat, 05 Nov 2022 04:54:53 GMT',
  expires: 'Fri, 01 Jan 1990 00:00:00 GMT',
  'cache-control': 'no-cache, must-revalidate',
  'accept-ranges': 'bytes',
  'content-length': '81876',
  connection: 'keep-alive',
  'alt-svc': 'h3=":443"; ma=2592000,h3-29=":443"; ma=2592000,h3-Q050=":443"; ma=2592000,h3-Q046=":443"; ma=2592000,h3-Q043=":443"; ma=2592000,quic=":443"; ma=2592000; v="46,43"',
  'x-walltime-ms': '1667624093616',
  'x-bandwidth-est': '1181407',
  'x-bandwidth-est-comp': '241297',
  'x-bandwidth-est2': '241297',
  'x-bandwidth-app-limited': 'false',
  'x-bandwidth-est-app-limited': 'false',
  'x-bandwidth-est3': '985189',
  pragma: 'no-cache',
  'x-sequence-num': '869102',
  'x-segment-lmt': '1667603446403043',
  'x-head-time-sec': '4345221',
  'x-head-time-millis': '4345221518',
  'x-head-seqnum': '869102',
  vary: 'Origin',
  'cross-origin-resource-policy': 'cross-origin',
  'x-content-type-options': 'nosniff',
  server: 'gvs 1.0'
}
*/
// DASH Manifest MPD:
/*{
  MPD: {
    '$': {
      'xmlns:xsi': 'http://www.w3.org/2001/XMLSchema-instance',
      xmlns: 'urn:mpeg:DASH:schema:MPD:2011',
      'xmlns:yt': 'http://youtube.com/yt/2012/10/10',
      'xsi:schemaLocation': 'urn:mpeg:DASH:schema:MPD:2011 DASH-MPD.xsd',
      minBufferTime: 'PT1.500S',
      profiles: 'urn:mpeg:dash:profile:isoff-main:2011',
      type: 'dynamic',
      availabilityStartTime: '2022-11-09T12:40:29',
      timeShiftBufferDepth: 'PT7200.000S',
      minimumUpdatePeriod: 'PT2.000S',
      'yt:earliestMediaSequence': '1808',
      'yt:mpdRequestTime': '2022-11-09T15:40:38.309',
      'yt:mpdResponseTime': '2022-11-09T15:40:38.314'
    },
    Period: [ [Object] ]
  }
}
* > a.MPD.Period[0].AdaptationSet[1]
{
  '$': { id: '1', mimeType: 'video/mp4', subsegmentAlignment: 'true' },
  Role: [ { '$': [Object] } ],
  Representation: [
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] },
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] },
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] },
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] },
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] },
    { '$': [Object], BaseURL: [Array], SegmentList: [Array] }
  ]
}
a.MPD.Period[0].AdaptationSet[1].Representation[0]
{
  '$': {
    id: '133',
    codecs: 'avc1.4d4015',
    width: '426',
    height: '240',
    startWithSAP: '1',
    maxPlayoutRate: '1',
    bandwidth: '419256',
    frameRate: '30'
  },
  BaseURL: [
    'https://rr2---sn-j5c5nx-5x2l.googlevideo.com/videoplayback/expire/1668028838/ei/RsVrY6-PCqKgobIP56CDiA8/ip/190.114.235.14/id/dbteiGt_t_4.1/itag/133/source/yt_live_broadcast/requiressl/yes/spc/SFxXNgKgmQGWrWVas1s0l_2-0MIMwpQ/vprv/1/playlist_type/DVR/ratebypass/yes/mime/video%2Fmp4/live/1/gir/yes/noclen/1/dur/2.000/keepalive/yes/fexp/24001373,24007246/keepalive/yes/sparams/expire,ei,ip,id,itag,source,requiressl,spc,vprv,playlist_type,ratebypass,mime,live,gir,noclen,dur/sig/AOq0QJ8wRgIhANbQXY4skLmeSiL0VrnvK5jGrDN2MFWmpALyr9u5vrMYAiEAnK8i8a76JoX5wHjPDrN38meg5kzN9v3CbIgMnbk3Ww0%3D/initcwndbps/472500/mh/uH/mm/44/mn/sn-j5c5nx-5x2l/ms/lva/mt/1668007955/mv/m/mvi/2/pl/24/lsparams/initcwndbps,mh,mm,mn,ms,mv,mvi,pl/lsig/AG3C_xAwRgIhAM2GKMMoCRKX2hnPwCWgwKEG9Je577SzJ_Z5ZLUP3xMAAiEAtphBl9lrjE5WlKwlaYhyB9_Ii1FrN1ytScQrORZcJzo%3D/'
  ],
  SegmentList: [ { SegmentURL: [Array] } ]
}
// jsonResponse.videoDetails
* {
  videoId: 'dbteiGt_t_4',
  title: 'C5N EN VIVO | Toda la información en un solo lugar - Seguí la transmisión las 24 horas',
  lengthSeconds: '0',
  isLive: true,
  keywords: [
    'c5n',
    'c5n en vivo',
    'canal 5 noticas',
    'noticia ultimo momento',
    'breaking news',
    'TN',
    'todo noticias vivo',
    'tn en vivo',
    'tn en vivo online',
    'tn noticias en vivo',
    'tn en vivo todo noticias',
    'la nacion',
    'a24 en vivo',
    'canal 26 en vivo',
    'programas de tn',
    'noticias en vivo',
    'en vivo',
    'canales de noticias',
    'cronica tv en vivo',
    'noticias en vivo argentina',
    'tnt en vivo',
    'telefe en vivo',
    'canales en vivo',
    'noticiero en vivo',
    'tv en vivo',
    'canales en vivo argentina',
    'america tv en vivo',
    'canal 7 en vivo'
  ],
  channelId: 'UCFgk2Q2mVO1BklRQhSv6p0w',
  isOwnerViewing: false,
  shortDescription: 'Ingresá en nuestro sitio web - https://www.c5n.com. \n' +
    '\n' +
    'Mantenete informado con las últimas novedades en vivo en el canal líder en noticias.\n' +
    '\n' +
    'No te olvides de suscribirte al canal y clickear en la campana!\n' +
    '\n' +
    'Seguinos también en:\n' +
    '· Instagram: https://www.instagram.com/c5n\n' +
    '· Facebook: https://www.facebook.com/C5N.Noticias\n' +
    '· Twitter: https://www.twitter.com/c5n',
  isCrawlable: true,
  isLiveDvrEnabled: true,
  thumbnail: { thumbnails: [ [Object], [Object], [Object], [Object], [Object] ] },
  liveChunkReadahead: 3,
  allowRatings: true,
  viewCount: '305630',
  author: 'C5N',
  isLowLatencyLiveStream: true,
  isPrivate: false,
  isUnpluggedCorpus: false,
  latencyClass: 'MDE_STREAM_OPTIMIZATIONS_RENDERER_LATENCY_LOW',
  isLiveContent: true
}
{
  responseContext: {
    visitorData: 'CgtwV2tIeXU3aWN2VSj8yrebBg%3D%3D',
    serviceTrackingParams: [ [Object], [Object], [Object], [Object] ],
    mainAppWebResponseContext: { loggedOut: true },
    webResponseContextExtensionData: { hasDecorated: true }
  },
  playabilityStatus: {
    status: 'OK',
    playableInEmbed: true,
    liveStreamability: { liveStreamabilityRenderer: [Object] },
    miniplayer: { miniplayerRenderer: [Object] },
    contextParams: 'Q0FFU0FnZ0M='
  },
  streamingData: {
    expiresInSeconds: '21540',
    adaptiveFormats: [
      [Object], [Object],
      [Object], [Object],
      [Object], [Object],
      [Object], [Object],
      [Object], [Object],
      [Object], [Object],
      [Object]
    ],
    dashManifestUrl: 'https://manifest.googlevideo.com/api/manifest/dash/expire/1668168156/ei/fOVtY93LEpyaobIP1K2qoAk/ip/190.114.235.14/id/5D_2th5DChk.1/source/yt_live_broadcast/requiressl/yes/as/fmp4_audio_clear%2Cwebm_audio_clear%2Cwebm2_audio_clear%2Cfmp4_sd_hd_clear%2Cwebm2_sd_hd_clear/spc/SFxXNkxQp6xJWOxT1Lf0SM3sFgHZUns/vprv/1/pacing/0/keepalive/yes/fexp/24001373%2C24007246/itag/0/playlist_type/DVR/sparams/expire%2Cei%2Cip%2Cid%2Csource%2Crequiressl%2Cas%2Cspc%2Cvprv%2Citag%2Cplaylist_type/sig/AOq0QJ8wRAIgA-FMKmunk1VpeHdlGGCuK7qsprxEtY4RXIFBZANomBICIDB1O1rjxGJUgkMapusO1z6O5joTVt_JDNJNICnGdfbu',
    hlsManifestUrl: 'https://manifest.googlevideo.com/api/manifest/hls_variant/expire/1668168156/ei/fOVtY93LEpyaobIP1K2qoAk/ip/190.114.235.14/id/5D_2th5DChk.1/source/yt_live_broadcast/requiressl/yes/hfr/1/maudio/1/spc/SFxXNkxQp6xJWOxT1Lf0SM3sFgHZUns/vprv/1/go/1/pacing/0/nvgoi/1/keepalive/yes/fexp/24001373%2C24007246/dover/11/itag/0/playlist_type/LIVE/sparams/expire%2Cei%2Cip%2Cid%2Csource%2Crequiressl%2Chfr%2Cmaudio%2Cspc%2Cvprv%2Cgo%2Citag%2Cplaylist_type/sig/AOq0QJ8wQwIfAn048wWWe7Ag6zk_0DqFiQFUUr54mu6siyIsDSgmhwIgC_boApMKqAuvFPr8N6gWw-U9BO4UNXtODKjGNq9ZpRY%3D/file/index.m3u8'
  },
  heartbeatParams: {
    intervalMilliseconds: '15000',
    softFailOnError: true,
    heartbeatServerData: 'GAIgAQ=='
  },
  playerAds: [ { playerLegacyDesktopWatchAdsRenderer: [Object] } ],
  playbackTracking: {
    videostatsPlaybackUrl: {
      baseUrl: 'https://s.youtube.com/api/stats/playback?cl=486905411&docid=5D_2th5DChk&ei=fOVtY93LEpyaobIP1K2qoAk&fexp=1714240%2C23804281%2C23858057%2C23882502%2C23918597%2C23934970%2C23940247%2C23946420%2C23966208%2C23983296%2C23986032%2C23998056%2C24001373%2C24002022%2C24002025%2C24004644%2C24007246%2C24034168%2C24036947%2C24077241%2C24080738%2C24120819%2C24135310%2C24140247%2C24152443%2C24161116%2C24162919%2C24164186%2C24166867%2C24169501%2C24181174%2C24185614%2C24186126%2C24187043%2C24187377%2C24191629%2C24197450%2C24199724%2C24211178%2C24217229%2C24217535%2C24219713%2C24229161%2C24230619%2C24241378%2C24248091%2C24254502%2C24255165%2C24255543%2C24255545%2C24260783%2C24262346%2C24263796%2C24267564%2C24267570%2C24268142%2C24278596%2C24279196%2C24283093%2C24283556%2C24287327%2C24288912%2C24290971%2C24291857%2C24292955%2C24293803%2C24299747%2C24390675%2C24396645%2C24396819%2C24402891%2C24404640%2C24406314%2C24406604%2C24407199%2C24407665%2C24413557%2C24413559%2C24414161%2C24590921%2C39322504%2C39322574&live=dvr&ns=yt&plid=AAXtK6Lse3cNIDvs&delay=5&el=detailpage&len=0&of=5y-vBof0Lq3VW8b5QzzGoA&vm=CAEQARgEOjJBUEV3RWxTU29HdG9HZm02ck1EYWVrM01BVEo2MWNPdW9TbW0xaU9KeE1nd1hKS2lnZ2JWQVBta0tETFFwRFV6aHZLRVVsWVpvcXZiTTBKOFptNWZCZkZjRWp1RzJoVkQxckh0T0U0Q2ZOVjZPWWs0Y0w1TS1NcDBRUjhXRXdKLXlCRFI4UnFocndoAQ'
    },
    videostatsDelayplayUrl: {
      baseUrl: 'https://s.youtube.com/api/stats/delayplay?cl=486905411&docid=5D_2th5DChk&ei=fOVtY93LEpyaobIP1K2qoAk&fexp=1714240%2C23804281%2C23858057%2C23882502%2C23918597%2C23934970%2C23940247%2C23946420%2C23966208%2C23983296%2C23986032%2C23998056%2C24001373%2C24002022%2C24002025%2C24004644%2C24007246%2C24034168%2C24036947%2C24077241%2C24080738%2C24120819%2C24135310%2C24140247%2C24152443%2C24161116%2C24162919%2C24164186%2C24166867%2C24169501%2C24181174%2C24185614%2C24186126%2C24187043%2C24187377%2C24191629%2C24197450%2C24199724%2C24211178%2C24217229%2C24217535%2C24219713%2C24229161%2C24230619%2C24241378%2C24248091%2C24254502%2C24255165%2C24255543%2C24255545%2C24260783%2C24262346%2C24263796%2C24267564%2C24267570%2C24268142%2C24278596%2C24279196%2C24283093%2C24283556%2C24287327%2C24288912%2C24290971%2C24291857%2C24292955%2C24293803%2C24299747%2C24390675%2C24396645%2C24396819%2C24402891%2C24404640%2C24406314%2C24406604%2C24407199%2C24407665%2C24413557%2C24413559%2C24414161%2C24590921%2C39322504%2C39322574&live=dvr&ns=yt&plid=AAXtK6Lse3cNIDvs&delay=5&el=detailpage&len=0&of=5y-vBof0Lq3VW8b5QzzGoA&vm=CAEQARgEOjJBUEV3RWxTU29HdG9HZm02ck1EYWVrM01BVEo2MWNPdW9TbW0xaU9KeE1nd1hKS2lnZ2JWQVBta0tETFFwRFV6aHZLRVVsWVpvcXZiTTBKOFptNWZCZkZjRWp1RzJoVkQxckh0T0U0Q2ZOVjZPWWs0Y0w1TS1NcDBRUjhXRXdKLXlCRFI4UnFocndoAQ',
      elapsedMediaTimeSeconds: 5
    },
    videostatsWatchtimeUrl: {
      baseUrl: 'https://s.youtube.com/api/stats/watchtime?cl=486905411&docid=5D_2th5DChk&ei=fOVtY93LEpyaobIP1K2qoAk&fexp=1714240%2C23804281%2C23858057%2C23882502%2C23918597%2C23934970%2C23940247%2C23946420%2C23966208%2C23983296%2C23986032%2C23998056%2C24001373%2C24002022%2C24002025%2C24004644%2C24007246%2C24034168%2C24036947%2C24077241%2C24080738%2C24120819%2C24135310%2C24140247%2C24152443%2C24161116%2C24162919%2C24164186%2C24166867%2C24169501%2C24181174%2C24185614%2C24186126%2C24187043%2C24187377%2C24191629%2C24197450%2C24199724%2C24211178%2C24217229%2C24217535%2C24219713%2C24229161%2C24230619%2C24241378%2C24248091%2C24254502%2C24255165%2C24255543%2C24255545%2C24260783%2C24262346%2C24263796%2C24267564%2C24267570%2C24268142%2C24278596%2C24279196%2C24283093%2C24283556%2C24287327%2C24288912%2C24290971%2C24291857%2C24292955%2C24293803%2C24299747%2C24390675%2C24396645%2C24396819%2C24402891%2C24404640%2C24406314%2C24406604%2C24407199%2C24407665%2C24413557%2C24413559%2C24414161%2C24590921%2C39322504%2C39322574&live=dvr&ns=yt&plid=AAXtK6Lse3cNIDvs&el=detailpage&len=0&of=5y-vBof0Lq3VW8b5QzzGoA&vm=CAEQARgEOjJBUEV3RWxTU29HdG9HZm02ck1EYWVrM01BVEo2MWNPdW9TbW0xaU9KeE1nd1hKS2lnZ2JWQVBta0tETFFwRFV6aHZLRVVsWVpvcXZiTTBKOFptNWZCZkZjRWp1RzJoVkQxckh0T0U0Q2ZOVjZPWWs0Y0w1TS1NcDBRUjhXRXdKLXlCRFI4UnFocndoAQ'
    },
    ptrackingUrl: {
      baseUrl: 'https://www.youtube.com/ptracking?ei=fOVtY93LEpyaobIP1K2qoAk&oid=aNKNY2XK-H1LHaG1oQSbAA&plid=AAXtK6Lse3cNIDvs&pltype=contentlive&ptchn=s231K71Bnu5295_x0MB5Pg&ptk=youtube_single&video_id=5D_2th5DChk'
    },
    qoeUrl: {
      baseUrl: 'https://s.youtube.com/api/stats/qoe?cl=486905411&docid=5D_2th5DChk&ei=fOVtY93LEpyaobIP1K2qoAk&event=streamingstats&fexp=1714240%2C23804281%2C23858057%2C23882502%2C23918597%2C23934970%2C23940247%2C23946420%2C23966208%2C23983296%2C23986032%2C23998056%2C24001373%2C24002022%2C24002025%2C24004644%2C24007246%2C24034168%2C24036947%2C24077241%2C24080738%2C24120819%2C24135310%2C24140247%2C24152443%2C24161116%2C24162919%2C24164186%2C24166867%2C24169501%2C24181174%2C24185614%2C24186126%2C24187043%2C24187377%2C24191629%2C24197450%2C24199724%2C24211178%2C24217229%2C24217535%2C24219713%2C24229161%2C24230619%2C24241378%2C24248091%2C24254502%2C24255165%2C24255543%2C24255545%2C24260783%2C24262346%2C24263796%2C24267564%2C24267570%2C24268142%2C24278596%2C24279196%2C24283093%2C24283556%2C24287327%2C24288912%2C24290971%2C24291857%2C24292955%2C24293803%2C24299747%2C24390675%2C24396645%2C24396819%2C24402891%2C24404640%2C24406314%2C24406604%2C24407199%2C24407665%2C24413557%2C24413559%2C24414161%2C24590921%2C39322504%2C39322574&live=dvr&ns=yt&plid=AAXtK6Lse3cNIDvs'
    },
    atrUrl: {
      baseUrl: 'https://s.youtube.com/api/stats/atr?docid=5D_2th5DChk&ei=fOVtY93LEpyaobIP1K2qoAk&len=0&ns=yt&plid=AAXtK6Lse3cNIDvs&ver=2',
      elapsedMediaTimeSeconds: 5
    },
    videostatsScheduledFlushWalltimeSeconds: [ 10, 20, 30 ],
    videostatsDefaultFlushIntervalSeconds: 40,
    youtubeRemarketingUrl: {
      baseUrl: 'https://www.youtube.com/pagead/viewthroughconversion/962985656/?backend=innertube&cname=1&cver=2_20220519&foc_id=s231K71Bnu5295_x0MB5Pg&label=followon_view&ptype=no_rmkt&random=67712929',
      elapsedMediaTimeSeconds: 0
    }
  },
  videoDetails: {
    videoId: '5D_2th5DChk',
    title: 'Televisión Pública EN VIVO',
    lengthSeconds: '0',
    isLive: true,
    keywords: [
      'television publica',
      'tv publica',
      'tvpublica',
      'en vivo',
      'tvp en vivo',
      'television publica en vivo',
      'tv publica en vivo',
      'tvpublica en vivo',
      'tv arg',
      'television argentina',
      'tv argentina',
      'television arg',
      'tvp vivo',
      'tvp'
    ],
    channelId: 'UCs231K71Bnu5295_x0MB5Pg',
    isOwnerViewing: false,
    shortDescription: 'Televisión Pública transmisión en vivo\n' +
      '\n' +
      '#TelevisiónPública #Ahora #EnVivo\n' +
      '\n' +
      'https://tvpublica.com.ar\n' +
      'https://instagram.com/tv_publica\n' +
      'https://twitter.com/tv_publica\n' +
      'https://twitch.tv/tvpublica\n' +
      'https://facebook.com/tvpublica',
    isCrawlable: true,
    isLiveDvrEnabled: true,
    thumbnail: { thumbnails: [Array] },
    liveChunkReadahead: 2,
    allowRatings: true,
    viewCount: '20576',
    author: 'Televisión Pública',
    isLowLatencyLiveStream: true,
    isPrivate: false,
    isUnpluggedCorpus: false,
    latencyClass: 'MDE_STREAM_OPTIMIZATIONS_RENDERER_LATENCY_ULTRA_LOW',
    isLiveContent: true
  },
  playerConfig: {
    audioConfig: { enablePerFormatLoudness: true },
    streamSelectionConfig: { maxBitrate: '4430000' },
    livePlayerConfig: {
      liveReadaheadSeconds: 1.6,
      hasSubfragmentedFmp4: true,
      hasSubfragmentedWebm: true
    },
    mediaCommonConfig: { dynamicReadaheadConfig: [Object] },
    webPlayerConfig: { useCobaltTvosDash: true, webPlayerActionsPorting: [Object] }
  },
  storyboards: {
    playerLiveStoryboardSpecRenderer: {
      spec: 'https://i.ytimg.com/sb/5D_2th5DChk/storyboard_live_90_3x3_b1/M$M.jpg?rs=AOn4CLDntlNdc2WwhxAPfdVUjYjKe1BAKw#159#90#3#3'
    }
  },
  microformat: {
    playerMicroformatRenderer: {
      thumbnail: [Object],
      embed: [Object],
      title: [Object],
      description: [Object],
      lengthSeconds: '0',
      ownerProfileUrl: 'http://www.youtube.com/user/TVPublicaArgentina',
      externalChannelId: 'UCs231K71Bnu5295_x0MB5Pg',
      isFamilySafe: true,
      availableCountries: [Array],
      isUnlisted: false,
      hasYpcMetadata: false,
      viewCount: '20576',
      category: 'Entertainment',
      publishDate: '2022-11-10',
      ownerChannelName: 'Televisión Pública',
      liveBroadcastDetails: [Object],
      uploadDate: '2022-11-10'
    }
  },
  trackingParams: 'CAAQu2kiEwjd-a-XuqX7AhUcTUgAHdSWCpQ=',
  attestation: {
    playerAttestationRenderer: {
      challenge: 'a=5&a2=1&b=jib1acTyrUUiDKNnPJ4q_U604uc&c=1668146556&d=1&e=5D_2th5DChk&c1a=1&c6a=1&hh=6_WpDZMNiV3mGfhNG99jOHtJvRVCcOVjF7WBn0UVlh0',
      botguardData: [Object]
    }
  },
  messages: [ { mealbarPromoRenderer: [Object] }, { tooltipRenderer: [Object] } ],
  adPlacements: [
    { adPlacementRenderer: [Object] },
    { adPlacementRenderer: [Object] },
    { adPlacementRenderer: [Object] },
    { adPlacementRenderer: [Object] },
    { adPlacementRenderer: [Object] }
  ],
  frameworkUpdates: { entityBatchUpdate: { mutations: [Array], timestamp: [Object] } }
}
*/
// videoid='xYuJit8Qr2A'
/*
 audio-buffer=0
 vd-lavc-threads=1
 cache-pause=no
 demuxer-lavf-o-add=fflags=+nobuffer
 demuxer-lavf-probe-info=nostreams
 demuxer-lavf-analyzeduration=0.1
 video-sync=audio
 interpolation=no
 video-latency-hacks=yes
 stream-buffer-size=4k
 * 

*/ 
