'use strict';
// 执行完整页面脚本与原始录音模块；网络、时钟、DOM和播放器为测试替身。
// 无真实API调用，不代表手机麦克风或扬声器验收。
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const assert = require('assert').strict;
const source = fs.readFileSync(path.join(__dirname, 'index.html'), 'utf8');
const inline = [...source.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]).join('\n');
const results = [];
async function flush() { for (let i = 0; i < 15; i++) await Promise.resolve(); }
function page(geolocation) {
    const elements = {}, requests = [], timers = new Map(), revoked = [];
    let timerId = 0;
    function element(id) {
        return elements[id] || (elements[id] = {
            id, textContent: '', innerHTML: '', className: '', value: '', style: {}, disabled: false,
            src: '', files: [], paused: false, plays: 0,
            pause() { this.paused = true; }, load() {},
            play() { this.paused = false; this.plays++; return Promise.resolve(); },
            removeAttribute(key) { this[key] = ''; }, addEventListener() {}, click() {},
            getAttribute() { return null; }, focus() { this.focused = true; }
        });
    }
    const readers = [];
    const context = {
        console: { log() {}, warn() {}, error() {} }, Promise, AbortController,
        document: { getElementById: element }, navigator: geolocation ? { geolocation } : {},
        isSecureContext: !!geolocation,
        localStorage: { getItem() { return ''; }, setItem() {}, removeItem() {} },
        Recorder: { warmup() {}, start() {}, cancel() {}, isRecording() { return false; } },
        URL: { createObjectURL() { return 'blob:test-' + Math.random(); }, revokeObjectURL(url) { revoked.push(url); } },
        FileReader: class {
            constructor() { readers.push(this); this.result = 'data:image/jpeg;base64,REVIEW'; }
            readAsDataURL() {}
        },
        setTimeout(fn, ms) { const id = ++timerId; timers.set(id, { fn, ms }); return id; },
        clearTimeout(id) { timers.delete(id); },
        fetch(url, options) {
            return new Promise((resolve, reject) => requests.push({ url, options, resolve, reject }));
        }
    };
    context.window = context;
    vm.createContext(context);
    vm.runInContext(inline, context, { filename: 'actual-index.html' });
    function respond(request, payload) {
        request.resolve({ ok: true, status: 200, json() { return Promise.resolve(payload); },
                          blob() { return Promise.resolve({ size: 2000 }); } });
    }
    function photo() { element('fileInput').files = [{}]; element('fileInput').onchange(); }
    function expire(ms) { const match = [...timers].find(([, value]) => value.ms === ms); assert(match, 'timeout exists'); match[1].fn(); }
    return { context, element, requests, timers, revoked, readers, respond, photo, expire };
}
function submit(p) {
    // Nonempty-question scenarios explicitly simulate user input, no implicit app default.
    if (!p.element('askInput').value && !p.element('voiceText').textContent) p.element('askInput').value = '这个药怎么吃？';
    p.element('btnAsk').onclick();
}
function geoStub() {
    return { low: [], cleared: 0,
        watchPosition(ok, bad, options) { this.high = { ok, bad, options }; return 17; },
        getCurrentPosition(ok, bad, options) { this.low.push({ ok, bad, options }); },
        clearWatch() { this.cleared++; }
    };
}
function fix(timestamp = Date.now()) { return { coords: { longitude: 108.305, latitude: 22.833, accuracy: 89 }, timestamp }; }
function west() { return { ok: true, city: '450107', name: '南宁市西乡塘区', location_status: 'candidate' }; }
async function test(name, run) {
    try { await run(); results.push({ name, passed: true }); }
    catch (error) { results.push({ name, passed: false, error: error.stack }); }
}

(async function () {
    await test('first valid position displays immediately; later timeout retains it', async () => {
        const g = geoStub(), p = page(g); g.high.ok(fix()); await flush();
        p.respond(p.requests[0], west()); await flush();
        assert.equal(p.context.locationChoice.code, '450107'); assert.equal(p.context.regionCode, '');
        g.high.bad({ code: 3 }); await flush();
        assert.equal(p.context.locationChoice.code, '450107'); assert(!p.element('confirmLocation').hidden);
        assert(p.element('locationStatus').textContent.includes('已保留')); assert.equal(g.low.length, 0);
    });
    await test('same timestamp successful callbacks remain usable', async () => {
        const g = geoStub(), p = page(g), position = fix();
        for (let i=0; i<4; i++) { g.high.ok(position); await flush(); p.respond(p.requests[i], west()); await flush(); }
        assert.equal(p.context.locationChoice.code, '450107'); assert.equal(p.context.locationState, 'pending_confirmation');
    });
    await test('native failure waits for already acquired position lookup', async () => {
        const g = geoStub(), p = page(g); g.high.ok(fix()); await flush(); g.high.bad({ code: 2 });
        assert.equal(g.low.length, 0); p.respond(p.requests[0], west()); await flush();
        assert.equal(p.context.locationChoice.code, '450107'); assert.equal(g.low.length, 0);
    });
    await test('ordinary retry occurs once with explicit lower-accuracy options', async () => {
        const g = geoStub(), p = page(g); g.high.bad({ code: 2 }); assert.equal(g.low.length, 1);
        assert.equal(g.low[0].options.enableHighAccuracy, false); assert.equal(g.low[0].options.maximumAge, 30000);
        g.low[0].bad({ code: 3 }); g.high.bad({ code: 2 }); await flush();
        assert.equal(g.low.length, 1); assert.equal(p.context.locationState, 'timeout');
        assert(p.element('locationStatus').textContent.includes('普通精度定位重试超时'));
        assert(p.element('locationStatus').textContent.includes('定位来源暂不可用'));
    });
    await test('ordinary retry success accepts recent position and still needs confirmation', async () => {
        const g = geoStub(), p = page(g); g.high.bad({ code: 3 }); g.low[0].ok(fix(Date.now()-25000)); await flush();
        p.respond(p.requests[0], west()); await flush(); assert.equal(p.context.locationChoice.code, '450107');
        assert.equal(p.context.regionCode, ''); assert.equal(p.context.locationState, 'pending_confirmation');
    });
    await test('denied permission does not retry; timers cannot loop forever', async () => {
        const a=geoStub(), denied=page(a); a.high.bad({code:1}); assert.equal(a.low.length,0); assert.equal(denied.context.locationState,'denied');
        const b=geoStub(), timeout=page(b); timeout.expire(16000); assert.equal(b.low.length,1); timeout.expire(11000);
        assert.equal(timeout.context.locationState,'timeout'); assert.equal(b.low.length,1);
    });
    await test('new medicine task does not cancel automatic position lookup', async () => {
        const g=geoStub(), p=page(g); g.high.ok(fix()); await flush(); assert.equal(p.context.locationRequests.length,1);
        p.context.newTask(); assert.equal(p.context.locationRequests.length,1); p.respond(p.requests[0],west()); await flush();
        assert.equal(p.context.locationChoice.code,'450107'); assert.equal(p.context.locationRequests.length,0);
    });
    await test('county list requests are independent but drug requests still cancel', async () => {
        const p=page(); let county=false,cancelled=false;
        p.context.requestData('/api/regions',{method:'GET'},5000,r=>r.json(),p.context.countyRequests).then(()=>county=true);
        p.context.postJSON('/api/ask',{question:'测试'},1000).catch(()=>cancelled=true); await flush(); p.context.newTask(); await flush();
        assert(cancelled); assert.equal(p.context.countyRequests.length,1); p.respond(p.requests[0],{ok:true,cities:[]}); await flush(); assert(county);
    });
    await test('conflicting counties disable candidate confirmation; manual choice still available', async () => {
        const g=geoStub(), p=page(g); g.high.ok(fix()); await flush();p.respond(p.requests[0],west());await flush();
        g.high.ok(fix());await flush();p.respond(p.requests[1],{ok:true,city:'450110',name:'南宁市武鸣区'});await flush();
        assert(p.context.locationConflict);assert.equal(p.context.regionCode,'');assert(p.element('confirmLocation').hidden);
        g.high.bad({code:3});assert(p.element('locationStatus').textContent.includes('冲突'));
    });
    await test('confirmed county cannot be replaced by late native callbacks', async () => {
        const g=geoStub(), p=page(g);g.high.ok(fix());await flush();p.respond(p.requests[0],west());await flush();p.element('confirmLocation').onclick();
        assert.equal(p.context.regionCode,'450107');const count=p.requests.length;g.high.ok(fix());g.high.bad({code:2});await flush();
        assert.equal(p.requests.length,count);assert.equal(p.context.regionCode,'450107');
    });

    await test('empty question prompts for input without HTTP or playback', async () => {
        const p = page(); p.element('btnAsk').onclick(); await flush();
        assert.equal(p.requests.length, 0); assert(!p.element('btnAsk').disabled);
        assert(p.element('askStatus').textContent.includes('输入问题'));
        assert.equal(p.element('player').plays, 0); assert.equal(p.element('voicePlayer').plays, 0);
    });
    await test('new question immediately clears both players, old recording and cache', async () => {
        const p = page(), c = p.context;
        c.voiceFile = '02_感冒灵_怎么吃.mp3'; c.lastAudioUrl = 'blob:old'; c.lastAudioText = 'old';
        p.element('player').src = 'old'; p.element('voicePlayer').src = 'old';
        submit(p);
        assert(p.element('player').paused && p.element('voicePlayer').paused);
        assert.equal(c.voiceFile, ''); assert.equal(c.lastAudioUrl, '');
        assert(p.revoked.includes('blob:old')); assert(p.element('btnAsk').disabled);
        submit(p); await flush(); assert.equal(p.requests.length, 1);
    });
    await test('new photo unlocks button; stale ask cannot unlock a newer ask or overwrite answer', async () => {
        const p = page(); submit(p); await flush(); const old = p.requests[0];
        p.photo(); assert.equal(p.element('btnAsk').disabled, false);
        p.readers[0].onload(); await flush();
        p.respond(p.requests[1], { ok: true, lines: ['感冒灵颗粒'] }); await flush();
        submit(p); await flush(); assert(p.element('btnAsk').disabled);
        p.respond(old, { ok: true, answer: 'OLD', answer_status: 'answered' }); await flush();
        assert(p.element('btnAsk').disabled); assert.equal(p.element('answer').textContent, '');
        p.respond(p.requests[2], { ok: false }); await flush(); assert.equal(p.element('btnAsk').disabled, false);
    });
    await test('late OCR does not replace newer photo text', async () => {
        const p = page(); p.photo(); p.readers[0].onload(); await flush(); const old = p.requests[0];
        p.photo(); p.readers[1].onload(); await flush();
        p.respond(p.requests[1], { ok: true, lines: ['NEW'] }); await flush();
        p.respond(old, { ok: true, lines: ['OLD'] }); await flush();
        assert.equal(p.context.ocrWords, 'NEW'); assert(!p.element('result').textContent.includes('OLD'));
    });
    await test('late TTS after new photo cannot play or cache audio', async () => {
        const p = page(); p.element('answer').textContent = 'OLD'; p.context.speakAnswer(); await flush();
        p.photo(); p.respond(p.requests[0], {}); await flush();
        assert.equal(p.element('player').plays, 0); assert.equal(p.context.lastAudioUrl, '');
    });
    await test('TTS superseded by dialect in same task cannot play late', async () => {
        const p = page(); p.element('answer').textContent = '当前回答'; p.context.speakAnswer(); await flush();
        p.context.playVoiceFile('20_通用_我是机器不是医生.mp3');
        p.respond(p.requests[0], {}); await flush(); assert.equal(p.element('player').plays, 0);
    });
    await test('dialect failure falls back to current-answer TTS exactly once', async () => {
        const p = page(); p.element('answer').textContent = 'CURRENT';
        p.context.voiceFile = '20_通用_我是机器不是医生.mp3';
        p.context.playVoiceFile(p.context.voiceFile); const fail = p.element('voicePlayer').onerror;
        fail(new Error('load failed')); fail(new Error('duplicate event')); await flush();
        assert.equal(p.requests.filter(r => r.url === '/api/tts').length, 1);
        assert.equal(JSON.parse(p.requests[0].options.body).text, 'CURRENT');
        assert.equal(p.context.voiceFile, ''); assert.equal(p.element('btnSpeakPutong').style.display, 'block');
    });
    await test('stale dialect error cannot fall back after a new task', async () => {
        const p = page(); p.element('answer').textContent = 'OLD'; p.context.playVoiceFile('20_通用_我是机器不是医生.mp3');
        const old = p.element('voicePlayer').onerror; p.photo(); old(new Error('late')); await flush();
        assert.equal(p.requests.length, 0);
    });
    await test('autoplay rejection offers manual replay without a repeated paid request', async () => {
        const p = page(); p.element('answer').textContent = 'CURRENT';
        p.element('voicePlayer').play = () => Promise.reject(Object.assign(new Error('blocked'), { name: 'NotAllowedError' }));
        p.context.playVoiceFile('20_通用_我是机器不是医生.mp3'); await flush();
        assert.equal(p.requests.length, 0); assert(p.element('speakStatus').textContent.includes('请点'));
    });
    await test('ask timeout unlocks UI and ignores a late successful reply', async () => {
        const p = page(); submit(p); await flush(); p.expire(100000); await flush();
        assert.equal(p.element('btnAsk').disabled, false); assert(p.element('askStatus').textContent.includes('超时'));
        p.respond(p.requests[0], { ok: true, answer: 'LATE', answer_status: 'answered' }); await flush();
        assert.equal(p.element('answer').textContent, ''); assert.equal(p.context.pendingRequests.length, 0);
    });
    await test('OCR timeout resets busy flag and clears old recognized medicine', async () => {
        const p = page(); p.context.ocrWords = 'OLD'; p.photo(); p.readers[0].onload(); await flush();
        p.expire(65000); await flush(); assert.equal(p.context.ocrBusy, false); assert.equal(p.context.ocrWords, '');
    });
    await test('unknown answer status cannot select normal medicine recording', async () => {
        const p = page(); p.context.ocrWords = '感冒灵颗粒'; submit(p); await flush();
        p.respond(p.requests[0], { ok: true, answer: p.context.VOICE_TRANSCRIPTS['01_感冒灵_治什么.mp3'] }); await flush();
        assert.equal(p.context.voiceFile, '20_通用_我是机器不是医生.mp3');
    });
    await test('recognized OCR only, never display status, is submitted', async () => {
        const p = page(); p.element('result').textContent = '识别失败：OLD'; p.element('askInput').value = '感冒灵颗粒治什么病';
        submit(p); await flush();
        assert(!JSON.parse(p.requests[0].options.body).question.includes('识别失败'));
    });
    await test('unbound and conflicting dose recordings cannot be played manually', async () => {
        const p = page();
        for (const name of ['02_感冒灵_怎么吃.mp3', '05_硝苯地平_怎么吃.mp3']) {
            assert.equal(p.context.factsConsistent(name, '一次两袋，一天两次。'), false);
            p.context.playVoiceFile(name);
        }
        assert.equal(p.element('voicePlayer').plays, 0);
    });
    await test('same topic keywords alone do not authorize an extra or missing fact', async () => {
        const p = page();
        assert.equal(p.context.factsConsistent('01_感冒灵_治什么.mp3', '这个药是治感冒的。'), false);
        assert.equal(p.context.factsConsistent('12_布洛芬_什么人不能吃.mp3', '怀孕的人可以吃。'), false);
        assert.equal(p.context.factsConsistent('99_unknown.mp3', 'anything'), false);
    });
    await test('complete archived script permits dialect, with 80 or 八十 separately', async () => {
        const p = page(), name = '09_二甲双胍_老人能吃吗.mp3';
        assert(p.context.factsConsistent(name, p.context.VOICE_TRANSCRIPTS[name]));
        assert(p.context.factsConsistent(name, p.context.VOICE_TRANSCRIPTS[name].replace('八十', '80')));
        assert(p.context.factsConsistent('01_感冒灵_治什么.mp3', '[答] ' + p.context.VOICE_TRANSCRIPTS['01_感冒灵_治什么.mp3']));
    });
    await test('pending microphone permission can be cancelled without late recording', async () => {
        let resolvePermission, created = 0;
        const stream = { getAudioTracks() { return [{ readyState: 'live' }]; } };
        const c = { Promise, Float32Array, ArrayBuffer, DataView, Uint8Array,
            navigator: { mediaDevices: { getUserMedia() { return new Promise(resolve => { resolvePermission = resolve; }); } } },
            AudioContext: class { constructor() { created++; } }, btoa() { return ''; }
        };
        vm.createContext(c); vm.runInContext(fs.readFileSync(path.join(__dirname, 'recorder.js'), 'utf8'), c);
        c.Recorder.start(() => {}); assert(c.Recorder.isRecording()); c.Recorder.cancel();
        resolvePermission(stream); await flush(); assert.equal(created, 0); assert.equal(c.Recorder.isRecording(), false);
    });
    await test('new voice input clears old typed question and blocks ask during ASR', async () => {
        const p = page(); p.element('askInput').value = 'OLD QUESTION'; p.context.startVoice();
        assert.equal(p.element('askInput').value, '');
        p.context.voiceBusy = true; submit(p); await flush();
        assert.equal(p.requests.length, 0); assert(p.element('askStatus').textContent.includes('语音识别'));
    });
    await test('80 and 八十 whole-script matches can actually select elderly recording', async () => {
        const p = page(), name = '09_二甲双胍_老人能吃吗.mp3';
        p.element('result').textContent = '盐酸二甲双胍片'; p.context.lastQuestion = '老人能不能吃这个药？';
        p.element('answer').textContent = p.context.VOICE_TRANSCRIPTS[name].replace('八十','80');
        p.context.currentVoicePlan = { file: name, binding: 'source-and-audio-v1', text: p.context.VOICE_TRANSCRIPTS[name], answer_text: p.element('answer').textContent };
        assert.equal(p.context.findVoiceFile(), name);
    });
    await test('request timeout works without AbortController', async () => {
        const p = page(); p.context.AbortController = undefined;
        submit(p); await flush(); p.expire(100000); await flush();
        assert.equal(p.element('btnAsk').disabled, false); assert.equal(p.context.pendingRequests.length, 0);
    });

    await test('cleaned OCR is shown but full raw text is retained for identity checks', async () => {
        const p=page();p.photo();p.readers[0].onload();await flush();
        p.respond(p.requests[0],{ok:true,lines:['感冒灵颗粒'],raw_lines:['Ctrl','感冒灵颗粒','规格20g']});await flush();
        assert(!p.element('result').textContent.includes('Ctrl'));
        p.element('askInput').value='一天吃几次';submit(p);await flush();
        assert(JSON.parse(p.requests[1].options.body).question.includes('规格20g'));
    });
    await test('source-bound dose reply auto plays dialect and retains both replay choices', async () => {
        const p=page(),name='02_感冒灵_怎么吃.mp3',text='说明书原文：【用法用量】开水冲服。一次10克(1袋)，一日3次。';
        p.context.ocrWords='感冒灵颗粒';p.element('askInput').value='一天吃几次';submit(p);await flush();
        p.respond(p.requests[0],{ok:true,answer:text,answer_status:'answered',voice:{file:name,text:p.context.VOICE_TRANSCRIPTS[name],answer_text:text,binding:'source-and-audio-v1'}});await flush();
        assert.equal(p.context.voiceFile,name);assert.equal(p.element('voicePlayer').plays,1);
        assert.equal(p.element('btnSpeak').style.display,'block');assert.equal(p.element('btnSpeakPutong').style.display,'block');
        p.element('btnSpeak').onclick();assert.equal(p.element('voicePlayer').plays,2);
        p.element('btnSpeakPutong').onclick();await flush();assert(p.element('voicePlayer').paused);
        assert.equal(p.requests.filter(r=>r.url==='/api/tts').length,1);
    });
    await test('stale or absent voice binding cannot authorize a normal recording', async () => {
        const p=page(),name='02_感冒灵_怎么吃.mp3';
        p.context.ocrWords='感冒灵颗粒';p.context.lastQuestion='怎么吃';p.element('answer').textContent='当前答案';
        p.context.currentVoicePlan={file:name,text:p.context.VOICE_TRANSCRIPTS[name],answer_text:'旧答案',binding:'source-and-audio-v1'};
        assert.equal(p.context.findVoiceFile(),'');p.context.playVoiceFile(name);assert.equal(p.element('voicePlayer').plays,0);
        p.context.currentVoicePlan=null;p.element('answer').textContent=p.context.VOICE_TRANSCRIPTS[name];
        assert.equal(p.context.findVoiceFile(),'');p.context.playVoiceFile(name);assert.equal(p.element('voicePlayer').plays,0);
    });


    function pulseAudio(p) {
        const entry = [...p.timers].find(([, value]) => value.ms === 2500);
        assert(entry, 'audio progress watchdog exists');
        p.timers.delete(entry[0]); entry[1].fn();
    }
    function startGeneric(p) {
        p.element('answer').textContent = '当前回答';
        p.context.voiceFile = '20_通用_我是机器不是医生.mp3';
        p.context.playVoiceFile(p.context.voiceFile);
    }
    await test('dialect says preparing until media playing event, then reports buffering', async () => {
        const p=page(); startGeneric(p);
        assert.equal(p.element('speakStatus').textContent,'正在准备乡音…');
        p.element('voicePlayer').onplaying();
        assert.equal(p.element('speakStatus').textContent,'正在用乡音念…');
        p.element('voicePlayer').onwaiting();
        assert(p.element('speakStatus').textContent.includes('缓冲'));
    });
    await test('unsettled mobile play promise triggers bounded complete-file recovery', async () => {
        const p=page();p.element('voicePlayer').play=()=>new Promise(()=>{});startGeneric(p);
        pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        assert.equal(p.requests.length,1);assert(p.requests[0].url.startsWith('audio/'));
        p.respond(p.requests[0],{});await flush();
        assert(p.element('voicePlayer').src.startsWith('blob:'));assert.equal(p.context.activeVoice.blobTried,true);
        pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        assert.equal(p.requests.filter(r=>r.url.startsWith('audio/')).length,1);
        assert.equal(p.requests.filter(r=>r.url==='/api/tts').length,1);
    });
    await test('real time advancement prevents false stalled recovery', async () => {
        const p=page();startGeneric(p);
        for(let i=1;i<=8;i++){p.element('voicePlayer').currentTime=i;pulseAudio(p);}
        await flush();assert.equal(p.requests.length,0);
    });
    await test('switching medicine cancels recovery and ignores late complete audio', async () => {
        const p=page();startGeneric(p);pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        const pending=p.requests[0];p.photo();p.respond(pending,{});await flush();
        assert.equal(p.element('voicePlayer').plays,1);assert.equal(p.context.voiceFile,'');
        assert.equal(p.requests.filter(r=>r.url==='/api/tts').length,0);
    });
    await test('switch to Mandarin cannot be overwritten by late recovery', async () => {
        const p=page();startGeneric(p);pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        const pending=p.requests[0];p.context.speakAnswer();await flush();p.respond(pending,{});await flush();
        assert.equal(p.element('voicePlayer').plays,1);assert.equal(p.context.activeVoice,null);
    });
    await test('manual replay invalidates the old playback watchdog', async () => {
        const p=page();startGeneric(p);const old=[...p.timers.values()].find(x=>x.ms===2500).fn;
        p.element('btnSpeak').onclick();old();await flush();assert.equal(p.requests.length,0);
        assert.equal(p.element('voicePlayer').plays,2);
    });
    await test('complete-file object URL is released after audio finishes', async () => {
        const p=page();startGeneric(p);pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        p.respond(p.requests[0],{});await flush();const url=p.element('voicePlayer').src;
        p.element('voicePlayer').onended();assert(p.revoked.includes(url));
        assert.equal(p.context.activeVoice,null);assert.equal(p.element('speakStatus').textContent,'乡音念完了');
        assert.equal([...p.timers.values()].filter(t=>t.ms===2500).length,0);
    });
    await test('old media error after finish does not trigger paid TTS', async () => {
        const p=page();startGeneric(p);const old=p.element('voicePlayer').onerror;
        p.element('voicePlayer').onended();old(new Error('late media failure'));await flush();assert.equal(p.requests.length,0);
    });
    await test('mobile recovery timeout falls back only once to current answer', async () => {
        const p=page();startGeneric(p);pulseAudio(p);pulseAudio(p);pulseAudio(p);await flush();
        p.expire(15000);await flush();
        assert.equal(p.requests.filter(r=>r.url==='/api/tts').length,1);
        assert.equal(JSON.parse(p.requests.find(r=>r.url==='/api/tts').options.body).text,'当前回答');
    });
    await test('wide ibuprofen contraindication explains why only Mandarin is available', async () => {
        const p=page();p.element('askInput').value='布洛芬什么人不能吃？';submit(p);await flush();
        p.respond(p.requests[0],{ok:true,answer:'全部禁忌原文',answer_status:'answered',refuse_kind:'',voice:null,
            citation:{药名:'布洛芬缓释胶囊',引用栏目:[]}});await flush();
        assert.equal(p.element('btnSpeak').style.display,'none');
        assert(p.element('askStatus').textContent.includes('完整禁忌使用普通话'));
    });

    console.log(JSON.stringify({ scope: 'Actual JS with local test doubles; no phone/audio/API certification', tests: results,
                                passed: results.filter(x => x.passed).length, failed: results.filter(x => !x.passed).length }, null, 2));
    if (results.some(result => !result.passed)) process.exitCode = 1;
})();
