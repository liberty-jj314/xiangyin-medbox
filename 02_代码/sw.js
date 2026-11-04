/* 乡音药箱 · Service Worker（只为满足"添加到主屏幕"的安装条件）
 *
 * 这里刻意做得极简、极保守：
 *   · 不缓存任何接口请求（/api/ 一律放行给网络），保证拍照、语音、问答永远是实时结果
 *   · 只缓存图标与 manifest 这类静态小文件
 *   · 不做离线整页缓存，避免"代码改了手机上还是旧的"这种最难查的问题
 */
var CACHE = 'xiangyin-v1';
var ASSETS = ['icon-192.png', 'icon-512.png', 'manifest.json'];

self.addEventListener('install', function (e) {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      return c.addAll(ASSETS).catch(function () { /* 有文件缺失也不阻塞安装 */ });
    })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE; })
            .map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var url = new URL(e.request.url);

  // 接口请求一律不缓存，直接走网络
  if (url.pathname.indexOf('/api/') === 0) return;
  // 非 GET 请求（上传等）也不处理
  if (e.request.method !== 'GET') return;

  // 只处理同源的图标 / manifest
  if (ASSETS.indexOf(url.pathname.replace(/^\//, '')) === -1) return;

  e.respondWith(
    caches.match(e.request).then(function (hit) {
      return hit || fetch(e.request);
    })
  );
});
