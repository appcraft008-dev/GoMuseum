// GoMuseum 网站交互:馆标签。无 JS 时页面照样完整可读(所有面板依次展开)。
(function () {
  document.documentElement.classList.add("js");

  document.querySelectorAll(".tabs").forEach(function (bar) {
    var root = bar.parentNode;
    var buttons = bar.querySelectorAll("button[data-tab]");
    function show(slug) {
      buttons.forEach(function (b) {
        b.setAttribute("aria-selected", b.dataset.tab === slug ? "true" : "false");
      });
      root.querySelectorAll(".panel[data-panel]").forEach(function (p) {
        p.classList.toggle("on", p.dataset.panel === slug);
      });
    }
    buttons.forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.tab); });
    });
    if (buttons.length) show(buttons[0].dataset.tab);
  });
})();
