// Runs before first paint so language direction and theme never flash. This is a file and not
// an inline script because the backend's Content-Security-Policy refuses inline scripts.
(function () {
  var root = document.documentElement;
  function read(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }
  var query = new URLSearchParams(location.search).get('lang');
  var lang = query === 'ar' || query === 'en' ? query : read('support.lang');
  if (lang !== 'ar' && lang !== 'en') {
    lang = (navigator.language || '').toLowerCase().indexOf('ar') === 0 ? 'ar' : 'en';
  }
  root.lang = lang;
  root.dir = lang === 'ar' ? 'rtl' : 'ltr';
  var theme = read('support.theme');
  if (theme === 'light' || theme === 'dark') root.dataset.theme = theme;
})();
