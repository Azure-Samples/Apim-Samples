// ── Live reload (development only) ──
// Polls the server for file changes and auto-reloads the page.
// This file is loaded by the presentation HTML during local development
// via serve_presentation.py. It has no effect when the file is opened
// directly from the file system (fetch will simply fail silently).
(function () {
  var lastModified = new Date().getTime();
  var checkInterval = 2000; // Check every 2 seconds

  setInterval(function () {
    fetch(window.location.href, {
      method: 'HEAD',
      cache: 'no-store',
    })
      .then(function (response) {
        var modified = new Date(response.headers.get('last-modified')).getTime();
        if (modified > lastModified && lastModified !== 0) {
          console.log('File updated, reloading...');
          window.location.reload();
        }
        lastModified = modified;
      })
      .catch(function (error) {
        console.log('Live reload check failed:', error);
      });
  }, checkInterval);
})();
