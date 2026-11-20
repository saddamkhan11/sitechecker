/* Photo picker: live camera inside the page, or a photo from the gallery.
 *
 *   PhotoPicker.attach({
 *     cameraBtn, galleryBtn,          // buttons
 *     onPhoto(blob, source, takenAt)  // source: 'camera' | 'camera_app' | 'gallery'
 *   })
 *
 * Live camera uses getUserMedia (needs HTTPS or localhost, and camera permission in the Android app).
 * If it is not available, the camera button falls back to the phone's own camera app.
 */
(function (global) {
  function T(en) { return global.CC_T ? global.CC_T(en) : en; }
  var stream = null, facing = 'environment', overlay = null;

  function el(tag, attrs, parent) {
    var e = document.createElement(tag);
    for (var k in attrs) { if (k === 'text') e.textContent = attrs[k]; else e.setAttribute(k, attrs[k]); }
    if (parent) parent.appendChild(e);
    return e;
  }

  function stop() {
    if (stream) stream.getTracks().forEach(function (t) { t.stop(); });
    stream = null;
  }

  function close() { stop(); if (overlay) overlay.remove(); overlay = null; }

  function liveSupported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia) && (global.isSecureContext !== false);
  }

  function hiddenInput(capture, onFile) {
    var inp = el('input', { type: 'file', accept: 'image/*', style: 'display:none' }, document.body);
    if (capture) inp.setAttribute('capture', 'environment');
    inp.onchange = function () { var f = inp.files[0]; inp.remove(); if (f) onFile(f); };
    inp.click();
  }

  function openLive(onPhoto, onFail) {
    overlay = el('div', { class: 'cam-overlay' }, document.body);
    var video = el('video', { autoplay: '', playsinline: '', muted: '' }, overlay);
    var bar = el('div', { class: 'cam-bar' }, overlay);
    var closeB = el('button', { type: 'button', class: 'btn btn-light', text: '✕' }, bar);
    var shot = el('button', { type: 'button', class: 'cam-shot', 'aria-label': T('Take photo') }, bar);
    var flip = el('button', { type: 'button', class: 'btn btn-light', text: '🔄' }, bar);
    var hint = el('div', { class: 'cam-hint', text: T('Hold the phone steady, then press the round button') }, overlay);

    function start() {
      stop();
      navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: facing }, width: { ideal: 1920 }, height: { ideal: 1440 } }, audio: false })
        .then(function (s) { stream = s; video.srcObject = s; return video.play(); })
        .catch(function () { close(); onFail(); });
    }
    closeB.onclick = close;
    flip.onclick = function () { facing = facing === 'environment' ? 'user' : 'environment'; start(); };
    shot.onclick = function () {
      if (!video.videoWidth) return;
      var c = document.createElement('canvas');
      c.width = video.videoWidth; c.height = video.videoHeight;
      c.getContext('2d').drawImage(video, 0, 0);
      shot.disabled = true; hint.textContent = '...';
      c.toBlob(function (b) { close(); onPhoto(b, 'camera', new Date().toISOString()); }, 'image/jpeg', 0.9);
    };
    start();
  }

  function attach(o) {
    if (o.cameraBtn) o.cameraBtn.addEventListener('click', function (e) {
      e.preventDefault();
      var viaApp = function () { hiddenInput(true, function (f) { o.onPhoto(f, 'camera_app', new Date().toISOString()); }); };
      if (liveSupported()) openLive(o.onPhoto, viaApp); else viaApp();
    });
    if (o.galleryBtn) o.galleryBtn.addEventListener('click', function (e) {
      e.preventDefault();
      hiddenInput(false, function (f) {
        o.onPhoto(f, 'gallery', f.lastModified ? new Date(f.lastModified).toISOString() : '');
      });
    });
  }

  // Put a blob into a normal <input type=file> so a plain form can post it (used by the diary).
  function fillInput(input, blob, name) {
    try {
      var dt = new DataTransfer();
      dt.items.add(new File([blob], name || 'photo.jpg', { type: blob.type || 'image/jpeg' }));
      input.files = dt.files;
      return true;
    } catch (e) { return false; }
  }

  global.PhotoPicker = { attach: attach, fillInput: fillInput, liveSupported: liveSupported, close: close };
})(window);
