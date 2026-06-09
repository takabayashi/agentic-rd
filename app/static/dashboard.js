// Live updates + infinite scroll for the triage dashboard.
//
// No framework, no build step. The live poll refreshes the top page (newest
// rows) by swapping the server-rendered #feed fragment; an IntersectionObserver
// appends older pages as the user scrolls. The server stays the single source
// of row markup — this file never re-implements row rendering.
//
// The poll interval comes from <body data-refresh-ms="..."> so the value is
// owned in one place (Python config) and this stays a static asset.
(function () {
  var FEED = document.getElementById('feed');
  var LIVE = document.getElementById('live');
  var INTERVAL = parseInt(document.body.dataset.refreshMs, 10) || 5000;
  var loading = false;

  function tbody() { return FEED.querySelector('tbody'); }
  function sentinel() { return FEED.querySelector('#scroll-sentinel'); }
  function search() { return window.location.search; }

  // --- Infinite scroll: append the next page of older rows. ---
  function loadMore() {
    var s = sentinel();
    if (loading || !s) return;
    var off = s.dataset.next;
    if (!off) return;
    loading = true;
    var sep = search() ? '&' : '?';
    fetch('/fragment/rows' + search() + sep + 'offset=' + off, { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        var tb = tbody();
        if (!tb) return;
        s.remove();
        tb.insertAdjacentHTML('beforeend', html);
        loading = false;
        observe();
      })
      .catch(function () { loading = false; });
  }

  var io = ('IntersectionObserver' in window)
    ? new IntersectionObserver(function (entries) {
        if (entries.some(function (e) { return e.isIntersecting; })) loadMore();
      }, { rootMargin: '400px' })
    : null;

  function observe() {
    var s = sentinel();
    if (s && io) io.observe(s);
  }

  // --- Live poll: refresh the dynamic region (stats + filters + first page). ---
  function knownRevs() {
    var s = {};
    FEED.querySelectorAll('tr[data-rev]').forEach(function (tr) { s[tr.dataset.rev] = 1; });
    return s;
  }

  function tick() {
    if (document.hidden) return;
    var before = knownRevs();
    fetch('/fragment/edits' + search(), { headers: { 'X-Requested-With': 'fetch' } })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.text(); })
      .then(function (html) {
        FEED.innerHTML = html;
        FEED.querySelectorAll('tr[data-rev]').forEach(function (tr) {
          if (!before[tr.dataset.rev]) tr.classList.add('new');
        });
        if (LIVE) LIVE.classList.remove('off');
        observe();
      })
      .catch(function () { if (LIVE) LIVE.classList.add('off'); });
  }

  observe();
  setInterval(tick, INTERVAL);
})();
