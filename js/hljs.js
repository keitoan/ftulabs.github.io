(function () {
  var base = "https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/";
  var langs = ["latex", "dockerfile", "toml", "ini"];
  var loaded = 0;

  function init() {
    if (++loaded > langs.length) hljs.highlightAll();
  }

  function addScript(src, cb) {
    var s = document.createElement("script");
    s.src = src;
    s.onload = cb;
    document.head.appendChild(s);
  }

  addScript(base + "highlight.min.js", function () {
    langs.forEach(function (l) {
      addScript(base + "languages/" + l + ".min.js", init);
    });
  });
})();
