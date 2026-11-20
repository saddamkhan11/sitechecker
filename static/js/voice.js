/* Voice agent for the chat page.
 * - Push to talk: tap the mic, speak, it stops by itself after a short silence (or tap again).
 * - Conversation mode: after the reply is spoken, it listens again automatically.
 * Speech-to-text runs on the server (Groq Whisper) because Android WebView has no speech recognition.
 * Replies are read aloud with the phone's own voice (speechSynthesis), Urdu voice if the phone has one.
 */
(function (global) {
  function pickMime() {
    var types = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'];
    if (!global.MediaRecorder) return '';
    for (var i = 0; i < types.length; i++) if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(types[i])) return types[i];
    return '';
  }

  function VoiceAgent(opts) {
    this.o = opts; // {url, csrf, maxSeconds, onState(state), onResult(json), onError(msg)}
    this.rec = null; this.stream = null; this.chunks = []; this.ctx = null; this.timer = null;
    this.conversation = false; this.busy = false;
  }

  VoiceAgent.supported = function () {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && global.MediaRecorder);
  };

  VoiceAgent.prototype.state = function (s) { if (this.o.onState) this.o.onState(s); };

  VoiceAgent.prototype.toggle = function () {
    if (this.rec && this.rec.state === 'recording') return this.stop();
    if (this.busy) return;
    this.start();
  };

  VoiceAgent.prototype.start = function () {
    var self = this;
    global.speechSynthesis && speechSynthesis.cancel();
    navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } }).then(function (stream) {
      self.stream = stream; self.chunks = [];
      var mime = pickMime();
      self.rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      self.rec.ondataavailable = function (e) { if (e.data && e.data.size) self.chunks.push(e.data); };
      self.rec.onstop = function () { self._cleanup(); self._send(); };
      self.rec.start(250);
      self.state('listening');
      self._watchSilence(stream);
      self.timer = setTimeout(function () { self.stop(); }, (self.o.maxSeconds || 60) * 1000);
    }).catch(function () {
      self.state('idle');
      self.o.onError && self.o.onError('Mic ki ijazat nahi mili. / مائیک کی اجازت نہیں ملی۔');
    });
  };

  // Simple voice activity detection: stop ~1.6 s after the user stops talking.
  VoiceAgent.prototype._watchSilence = function (stream) {
    var self = this, AC = global.AudioContext || global.webkitAudioContext;
    if (!AC) return;
    try {
      self.ctx = new AC();
      var src = self.ctx.createMediaStreamSource(stream), an = self.ctx.createAnalyser();
      an.fftSize = 1024; src.connect(an);
      var buf = new Uint8Array(an.fftSize), spoke = false, quietSince = null, started = Date.now();
      (function loop() {
        if (!self.rec || self.rec.state !== 'recording') return;
        an.getByteTimeDomainData(buf);
        var sum = 0; for (var i = 0; i < buf.length; i++) { var v = (buf[i] - 128) / 128; sum += v * v; }
        var rms = Math.sqrt(sum / buf.length);
        if (self.o.onLevel) self.o.onLevel(rms);
        if (rms > 0.04) { spoke = true; quietSince = null; }
        else if (spoke) { quietSince = quietSince || Date.now(); if (Date.now() - quietSince > 1600) return self.stop(); }
        else if (Date.now() - started > 8000) return self.stop(); // nothing said in 8 s
        requestAnimationFrame(loop);
      })();
    } catch (e) { /* no VAD: user taps to stop */ }
  };

  VoiceAgent.prototype.stop = function () {
    clearTimeout(this.timer);
    if (this.rec && this.rec.state === 'recording') this.rec.stop();
  };

  VoiceAgent.prototype._cleanup = function () {
    if (this.stream) this.stream.getTracks().forEach(function (t) { t.stop(); });
    if (this.ctx) { try { this.ctx.close(); } catch (e) {} }
    this.stream = null; this.ctx = null;
  };

  VoiceAgent.prototype._send = function () {
    var self = this;
    var blob = new Blob(this.chunks, { type: (this.rec && this.rec.mimeType) || 'audio/webm' });
    this.chunks = [];
    if (blob.size < 2000) { self.state('idle'); if (self.conversation) self.o.onError && self.o.onError(''); return; }
    if (!navigator.onLine) { self.state('idle'); self.o.onError && self.o.onError('Internet nahi hai. / انٹرنیٹ نہیں ہے۔'); return; }
    self.busy = true; self.state('thinking');
    var fd = new FormData();
    var ext = blob.type.indexOf('mp4') >= 0 ? 'm4a' : blob.type.indexOf('ogg') >= 0 ? 'ogg' : 'webm';
    fd.append('audio', blob, 'voice.' + ext);
    fetch(self.o.url, { method: 'POST', body: fd, credentials: 'same-origin', headers: { 'X-CSRFToken': self.o.csrf, 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        self.busy = false;
        if (!j.ok) { self.state('idle'); self.o.onError && self.o.onError(j.error || 'Error'); return; }
        self.o.onResult && self.o.onResult(j);
        self.speak(j.speak || j.text, j.lang);
      })
      .catch(function () { self.busy = false; self.state('idle'); self.o.onError && self.o.onError('Jawab nahi aaya. / جواب نہیں آیا۔'); });
  };

  VoiceAgent.prototype.speak = function (text, lang) {
    var self = this;
    var after = function () { self.state('idle'); if (self.conversation) setTimeout(function () { self.start(); }, 400); };
    if (!self.o.speakOn() || !global.speechSynthesis || !text) return after();
    var u = new SpeechSynthesisUtterance(text);
    var voices = speechSynthesis.getVoices();
    var want = /[؀-ۿ]/.test(text) ? ['ur-PK', 'ur-IN', 'ur'] : (lang === 'en' ? ['en-PK', 'en-IN', 'en-GB', 'en-US'] : ['ur-PK', 'hi-IN', 'en-IN']);
    var v = null;
    for (var i = 0; i < want.length && !v; i++) v = voices.find(function (x) { return x.lang && x.lang.replace('_', '-').toLowerCase().indexOf(want[i].toLowerCase()) === 0; });
    if (v) { u.voice = v; u.lang = v.lang; } else { u.lang = want[0]; }
    u.rate = 0.95;
    u.onend = after; u.onerror = after;
    self.state('speaking');
    speechSynthesis.speak(u);
  };

  global.VoiceAgent = VoiceAgent;
})(window);
