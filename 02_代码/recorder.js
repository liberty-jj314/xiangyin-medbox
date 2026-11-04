// ==========================================================
//  recorder.js —— 录音模块
//  作用：把麦克风的声音，录成百度能认的 WAV 音频
//        （16000 Hz、单声道、16 位——这三个参数百度要求必须对）
//
//  对外有四个用法：
//    Recorder.warmup()          页面一打开就调一次，提前把麦克风权限拿到手
//    Recorder.start(状态回调)   按下按钮时调用，开始录音
//    Recorder.stop()            松开按钮时调用，返回一个 Promise，
//                               成功时交出 base64 音频字符串
//    Recorder.isRecording()     现在是不是正在录音（true / false）
//
//  典型写法：
//    Recorder.start(function (msg) { 状态栏.textContent = msg; });
//    Recorder.stop().then(function (b64) { 把 b64 发给服务端 });
// ==========================================================

var Recorder = (function () {

    // ---- 内部状态（外部不用管）----
    var audioCtx = null;     // 音频上下文（录音的"发动机"）
    var source = null;       // 麦克风音源
    var processor = null;    // 采样处理器
    var stream = null;       // 本次录音正在用的麦克风流
    var micStream = null;    // ★ 缓存下来的麦克风流：拿到后长期持有，不随录音结束关掉
    var chunks = [];         // 一小段一小段收集来的原始采样
    var onStatus = null;     // 记下调用方给的状态回调函数
    var starting = false;
    var startSeq = 0;

    // ==================== 拿到麦克风（并长期持有）====================
    // ★ 为什么要把这条流缓存起来：
    //   有些手机浏览器（实测：OPPO 自带）对"自签证书的网站"不把权限写进
    //   持久化存储 —— 每次重新调用 getUserMedia 都会再弹一次权限框。
    //   所以第一次拿到授权后就不再松手，后面的录音直接复用这条流：
    //   按住按钮立刻开录，而且不会再弹框。
    function ensureStream() {
        // 手上已经有一条"活着的"流 → 直接复用
        if (micStream) {
            var live = micStream.getAudioTracks().some(function (t) {
                return t.readyState === 'live';
            });
            if (live) return Promise.resolve(micStream);
            micStream = null;      // 这条已经死了，清掉重新申请
        }

        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return Promise.reject(new Error('这个浏览器不支持录音（需要用 https 打开）'));
        }

        return navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function (s) {
                micStream = s;
                // 万一用户主动撤销了权限，就把缓存清掉，下次重新申请
                s.getAudioTracks().forEach(function (t) {
                    t.onended = function () { micStream = null; };
                });
                return s;
            });
    }

    // ==================== 预热（页面一打开调一次）====================
    // 提前把权限拿到手，真按按钮时就不用等权限框了。
    function warmup() {
        ensureStream().catch(function () {
            // 用户没点"允许"也不要紧：真按按钮时会再申请一次
        });
    }

    // ==================== 开始录音 ====================
    function start(statusCallback) {
        if (audioCtx || starting) return;
        starting = true;
        var myStart = ++startSeq;
        onStatus = statusCallback || function () {};
        chunks = [];
        onStatus('正在准备麦克风…');

        ensureStream()
        .then(function (s) {
            if (myStart !== startSeq) return;
            starting = false;
            stream = s;
            // 关键：明确向浏览器要 16000 Hz，正好对上百度要求的采样率
            audioCtx = new AudioContext({ sampleRate: 16000 });
            source = audioCtx.createMediaStreamSource(stream);
            processor = audioCtx.createScriptProcessor(4096, 1, 1);

            processor.onaudioprocess = function (e) {
                if (myStart !== startSeq) return;
                // 每约 0.25 秒送进来一小段声音，先存着
                chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
            };

            source.connect(processor);
            processor.connect(audioCtx.destination);

            onStatus('正在录音…（说完了松手）');
        })
        .catch(function (err) {
            if (myStart !== startSeq) return;
            starting = false;
            audioCtx = null;
            onStatus('拿不到麦克风：' + err);
        });
    }

    // ==================== 停止录音，交出音频 ====================
    function stop() {
        return new Promise(function (resolve, reject) {

            if (!audioCtx) {
                starting = false;
                startSeq++;
                reject(new Error('麦克风还没准备好，请按住按钮再说一次'));
                return;
            }

            var rate = audioCtx.sampleRate;
            startSeq++;
            starting = false;

            // 1. 收尾：断开连接、关掉发动机
            //    ★ 这里**不再** stop 麦克风流！那条流是缓存着的，
            //      要留给下一次录音复用；一旦 stop 掉，下次又得重新申请权限、又弹框。
            processor.disconnect();
            source.disconnect();
            processor = null;
            source = null;
            audioCtx.close();
            audioCtx = null;

            // 2. 把一堆小段拼成一条完整的音轨
            var total = 0;
            chunks.forEach(function (c) { total += c.length; });
            if (total === 0) {
                reject(new Error('没录到声音，再试一次'));
                return;
            }
            var samples = new Float32Array(total);
            var pos = 0;
            chunks.forEach(function (c) {
                samples.set(c, pos);
                pos += c.length;
            });

            // 3. 保险：万一浏览器没给 16000，自己动手转换成 16000
            if (rate !== 16000 && rate !== 8000) {
                onStatus('采样率是 ' + rate + '，正在转换…');
                samples = resample(samples, rate, 16000);
                rate = 16000;
            }

            onStatus('录音结束，共 ' + (samples.length / rate).toFixed(1) + ' 秒');

            // 4. 编码成 WAV，再转成 base64 文本
            var wav = encodeWAV(samples, rate);
            resolve(toBase64(wav));
        });
    }

    function isRecording() {
        return !!audioCtx || starting;
    }

    // 换药时也取消尚未完成的麦克风授权，防止授权回来后偷偷开始旧录音。
    function cancel() {
        startSeq++;
        starting = false;
        onStatus = function () {};
        if (processor) {
            processor.onaudioprocess = null;
            try { processor.disconnect(); } catch (error) {}
        }
        if (source) { try { source.disconnect(); } catch (error) {} }
        if (audioCtx) {
            try {
                var closing = audioCtx.close();
                if (closing && closing.catch) closing.catch(function () {});
            } catch (error) {}
        }
        processor = source = audioCtx = stream = null;
        chunks = [];
    }

    // ==================== 采样率转换（线性插值）====================
    // 浏览器给的是 48000，百度只认 16000 / 8000，用这个函数"抽稀"
    function resample(samples, fromRate, toRate) {
        var ratio = fromRate / toRate;
        var newLen = Math.floor(samples.length / ratio);
        var out = new Float32Array(newLen);
        for (var i = 0; i < newLen; i++) {
            var p = i * ratio;
            var i0 = Math.floor(p);
            var i1 = Math.min(i0 + 1, samples.length - 1);
            var frac = p - i0;
            out[i] = samples[i0] * (1 - frac) + samples[i1] * frac;
        }
        return out;
    }

    // ==================== 拼 WAV 文件 ====================
    // WAV = 44 字节文件头 + 后面的原始声音数据
    // 那 44 个字节就是告诉对方"我是几声道、多少采样率、多少位深"的说明书
    function encodeWAV(samples, sampleRate) {
        var buffer = new ArrayBuffer(44 + samples.length * 2);
        var view = new DataView(buffer);

        function writeStr(offset, str) {
            for (var i = 0; i < str.length; i++) {
                view.setUint8(offset + i, str.charCodeAt(i));
            }
        }

        writeStr(0, 'RIFF');                          // 文件标识
        view.setUint32(4, 36 + samples.length * 2, true);  // 后面还有多少字节
        writeStr(8, 'WAVE');                          // 文件类型
        writeStr(12, 'fmt ');                         // 格式块开始
        view.setUint32(16, 16, true);                 // 格式块长度
        view.setUint16(20, 1, true);                  // 1 = 不压缩的 PCM
        view.setUint16(22, 1, true);                  // 单声道
        view.setUint32(24, sampleRate, true);         // 采样率
        view.setUint32(28, sampleRate * 2, true);     // 每秒字节数
        view.setUint16(32, 2, true);                  // 数据块对齐
        view.setUint16(34, 16, true);                 // 16 位深
        writeStr(36, 'data');                         // 数据块开始
        view.setUint32(40, samples.length * 2, true); // 数据有多少字节

        // 把 -1.0 ~ 1.0 的小数，换算成 -32768 ~ 32767 的整数
        var offset = 44;
        for (var i = 0; i < samples.length; i++, offset += 2) {
            var s = Math.max(-1, Math.min(1, samples[i]));
            view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7FFF, true);
        }
        return buffer;
    }

    // ==================== 转 base64 ====================
    // 分块转换，避免一次塞太多字符把浏览器"噎住"
    function toBase64(arrayBuffer) {
        var bytes = new Uint8Array(arrayBuffer);
        var binary = '';
        var chunk = 8192;
        for (var i = 0; i < bytes.length; i += chunk) {
            binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
        }
        return btoa(binary);
    }

    // 只把这几样交出去，其余都藏在模块里
    return {
        warmup: warmup,
        start: start,
        stop: stop,
        cancel: cancel,
        isRecording: isRecording
    };

})();
