(function () {
  function getCsrfToken() {
    if (window.CSRF_TOKEN) {
      return window.CSRF_TOKEN;
    }
    var match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  document.addEventListener("htmx:configRequest", function (event) {
    var token = getCsrfToken();
    if (token) {
      event.detail.headers["X-CSRFToken"] = token;
    }
  });
})();
