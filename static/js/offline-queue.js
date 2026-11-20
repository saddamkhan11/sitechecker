/* Offline photo queue: when there is no signal, photos wait in IndexedDB and upload when it returns.
 * Also: shrink photos in the browser before upload (saves data on weak site internet).
 */
(function (global) {
  var DB = 'cc-offline', STORE = 'uploads';

  function open() {
    return new Promise(function (res, rej) {
      if (!('indexedDB' in global)) return rej(new Error('no indexedDB'));
      var r = indexedDB.open(DB, 1);
      r.onupgradeneeded = function () { r.result.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true }); };
      r.onsuccess = function () { res(r.result); };
      r.onerror = function () { rej(r.error); };
    });
  }
  function tx(mode, fn) {
    return open().then(function (db) {
      return new Promise(function (res, rej) {
        var t = db.transaction(STORE, mode), s = t.objectStore(STORE), out = fn(s);
        t.oncomplete = function () { res(out && out.result !== undefined ? out.result : out); };
        t.onerror = function () { rej(t.error); };
      });
    });
  }

  function csrf() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  // Shrink an image File to maxSide px JPEG. Resolves to a Blob.
  function shrink(file, maxSide, quality) {
    maxSide = maxSide || 1280; quality = quality || 0.8;
    return new Promise(function (res) {
      var img = new Image(), url = URL.createObjectURL(file);
      img.onload = function () {
        var s = Math.min(1, maxSide / Math.max(img.width, img.height));
        var c = document.createElement('canvas');
        c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
        c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
        URL.revokeObjectURL(url);
        c.toBlob(function (b) { res(b || file); }, 'image/jpeg', quality);
      };
      img.onerror = function () { URL.revokeObjectURL(url); res(file); };
      img.src = url;
    });
  }

  function send(item) {
    var fd = new FormData();
    Object.keys(item.fields || {}).forEach(function (k) { fd.append(k, item.fields[k]); });
    if (item.blob) fd.append('photo', item.blob, 'photo.jpg');
    return fetch(item.url, { method: 'POST', body: fd, credentials: 'same-origin',
                             headers: { 'Accept': 'application/json', 'X-CSRFToken': csrf() } })
      .then(function (r) {
        if (r.status >= 500 || r.status === 0) throw new Error('server ' + r.status);
        return r.json();
      });
  }

  function add(item) {
    item.queued_at = new Date().toISOString();
    return tx('readwrite', function (s) { return s.add(item); }).then(badge);
  }
  function all() { return tx('readonly', function (s) { return s.getAll(); }); }
  function remove(id) { return tx('readwrite', function (s) { return s.delete(id); }); }

  var flushing = false;
  function flush() {
    if (flushing || !navigator.onLine) return Promise.resolve(0);
    flushing = true;
    var sent = 0;
    return all().then(function (items) {
      return items.reduce(function (p, it) {
        return p.then(function () {
          return send(it).then(function () { sent++; return remove(it.id); }).catch(function () {});
        });
      }, Promise.resolve());
    }).catch(function () {}).then(function () { flushing = false; badge(); return sent; });
  }

  function badge() {
    var nb = document.getElementById('net-badge'), qb = document.getElementById('queue-badge');
    if (nb) nb.classList.toggle('d-none', navigator.onLine);
    if (!qb) return;
    all().then(function (items) {
      qb.textContent = items.length ? ('⏳ ' + items.length) : '';
      qb.classList.toggle('d-none', !items.length);
    }).catch(function () {});
  }

  // Submit now if possible, otherwise queue. Resolves {queued:bool, data}
  function submit(url, fields, blob) {
    var item = { url: url, fields: fields, blob: blob };
    if (!navigator.onLine) return add(item).then(function () { return { queued: true }; });
    return send(item).then(function (data) { return { queued: false, data: data }; })
      .catch(function () { return add(item).then(function () { return { queued: true }; }); });
  }

  global.addEventListener('online', function () { badge(); flush(); });
  global.addEventListener('offline', badge);
  document.addEventListener('DOMContentLoaded', function () { badge(); flush(); });

  global.OfflineQueue = { submit: submit, flush: flush, shrink: shrink, add: add, all: all };
})(window);
