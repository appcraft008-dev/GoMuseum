// GoMuseum 网站交互。无 JS 时页面照样完整可读(面板依次展开、段落全部展开)。
(function () {
  var root = document.documentElement;
  root.classList.add("js");
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // ---- 自记统计:sendBeacon 到 /w/e,不设 cookie、不存本地 ----
  var body = document.body.dataset;
  window.gmTrack = function (name, extra) {
    var data = { name: name, lang: body.lang, page_type: body.page, museum_slug: body.museum, qid: body.qid };
    for (var k in (extra || {})) data[k] = extra[k];
    var blob = new Blob([JSON.stringify(data)], { type: "application/json" });
    if (navigator.sendBeacon) navigator.sendBeacon("/w/e", blob);
  };
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest('a[href*="play.google.com"], [data-track]');
    if (!a) return;
    if (a.href && a.href.indexOf("play.google.com") >= 0) window.gmTrack("web_download_click", { channel: a.dataset.cta || "play" });
    else if (a.dataset.track) window.gmTrack("web_download_click", { channel: a.dataset.track });
  });

  // ---- 亮/暗开关:默认跟系统;点过就记在本地(纯偏好,不是统计) ----
  var themeBtn = document.querySelector(".theme-btn");
  if (themeBtn) themeBtn.addEventListener("click", function () {
    var dark = root.dataset.theme ? root.dataset.theme === "dark" : window.matchMedia("(prefers-color-scheme: dark)").matches;
    root.dataset.theme = dark ? "light" : "dark";
    try { localStorage.setItem("gm-theme", root.dataset.theme); } catch (e) {}
  });

  // ---- 馆标签 ----
  document.querySelectorAll(".tabs").forEach(function (bar) {
    var host = bar.parentNode;
    var buttons = bar.querySelectorAll("button[data-tab]");
    function show(slug) {
      buttons.forEach(function (b) {
        b.setAttribute("aria-selected", b.dataset.tab === slug ? "true" : "false");
      });
      host.querySelectorAll(".panel[data-panel]").forEach(function (p) {
        p.classList.toggle("on", p.dataset.panel === slug);
      });
    }
    buttons.forEach(function (b) {
      b.addEventListener("click", function () { show(b.dataset.tab); });
    });
    if (buttons.length) show(buttons[0].dataset.tab);
  });

  // ---- 作品页 ----
  var list = document.getElementById("sections");
  if (!list) return;
  var work = document.querySelector(".work");
  var panel = document.getElementById("work-panel");
  var img = document.getElementById("work-img");
  var secs = Array.prototype.slice.call(list.querySelectorAll(".sec"));
  var audio = document.getElementById("audio");
  var back = document.getElementById("back");
  var mini = document.getElementById("mini");
  var mback = document.getElementById("mback");
  var current = -1; // 正在播的段
  var follow = true; // 是否跟着音频展开

  function open(i, scroll) {
    secs.forEach(function (s, j) {
      s.classList.toggle("open", j === i);
      s.querySelector(".sec-t").setAttribute("aria-expanded", j === i ? "true" : "false");
    });
    if (scroll && secs[i]) {
      var wide = window.matchMedia("(min-width: 1024px)").matches && !work.classList.contains("wide");
      if (wide) list.scrollTo({ top: secs[i].offsetTop - list.offsetTop, behavior: reduced ? "auto" : "smooth" });
      else secs[i].scrollIntoView({ block: "start", behavior: reduced ? "auto" : "smooth" });
    }
  }
  function setBack(show) {
    if (back) back.hidden = !show;
    if (mback) mback.hidden = !show;
  }

  secs.forEach(function (s, i) {
    s.querySelector(".sec-t").addEventListener("click", function () {
      var already = s.classList.contains("open");
      open(already ? -1 : i, false);
      if (audio && !audio.paused && i !== current) { follow = false; setBack(true); }
    });
  });

  // ---- 连播(只有试听作品有 #audio) ----
  if (audio) {
    var pbtn = document.getElementById("pbtn");
    var mbtn = document.getElementById("mbtn");
    var label = document.getElementById("plabel");
    var mlabel = document.getElementById("mlabel");
    var seek = document.getElementById("pseek");
    var ptime = document.getElementById("ptime");
    var pspeed = document.getElementById("pspeed");
    var speeds = [1, 1.5, 2, 0.75]; // 与 App 一致
    var rate = 1;
    var dragging = false;
    var nowTpl = work.dataset.now || "__PART__";
    var playable = secs.map(function (s, i) { return s.dataset.src ? i : -1; }).filter(function (i) { return i >= 0; });

    function title(i) { return secs[i].querySelector(".sec-t").textContent.trim(); }
    function paint() {
      var playing = !audio.paused && current >= 0;
      pbtn.textContent = playing ? "❚❚" : "▶";
      if (mbtn) mbtn.textContent = playing ? "❚❚" : "▶";
      secs.forEach(function (s, j) {
        s.classList.toggle("playing", j === current);
        var b = s.querySelector(".sec-play");
        if (b) b.textContent = playing && j === current ? "❚❚" : "▶";
      });
      if (current >= 0) {
        var text = nowTpl.replace("__PART__", title(current));
        label.textContent = text;
        if (mlabel) mlabel.textContent = text;
      }
      root.classList.toggle("is-playing", playing);
      if (mini) mini.hidden = current < 0;
    }
    function play(i) {
      current = i;
      audio.src = secs[i].dataset.src;
      audio.defaultPlaybackRate = audio.playbackRate = rate; // 换段会重置速率
      seek.disabled = false;
      audio.play().catch(function () {});
      track("web_trial_play", { part: secs[i].dataset.key });
      if (follow) open(i, true);
      paint();
    }
    function toggle() {
      if (current < 0) { if (playable.length) play(playable[0]); return; }
      if (audio.paused) audio.play().catch(function () {}); else audio.pause();
    }
    pbtn.addEventListener("click", toggle);
    if (mbtn) mbtn.addEventListener("click", toggle);
    secs.forEach(function (s, i) {
      var b = s.querySelector(".sec-play");
      if (!b) return;
      b.addEventListener("click", function () {
        if (i === current) { toggle(); return; }
        follow = true; setBack(false); play(i);
      });
    });
    function backToPlaying() { follow = true; setBack(false); open(current, true); }
    if (back) back.addEventListener("click", backToPlaying);
    if (mback) mback.addEventListener("click", backToPlaying);
    audio.addEventListener("play", paint);
    audio.addEventListener("pause", paint);
    function fmt(sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ":" + ("0" + sec % 60).slice(-2); }
    function tick() {
      if (!audio.duration) return;
      if (!dragging) seek.value = Math.round(audio.currentTime / audio.duration * 1000);
      ptime.textContent = "-" + fmt((audio.duration - audio.currentTime) / rate); // 剩余按倍速折算,同 App
    }
    audio.addEventListener("timeupdate", tick);
    audio.addEventListener("loadedmetadata", tick);
    seek.addEventListener("input", function () {
      dragging = true;
      if (audio.duration) {
        audio.currentTime = seek.value / 1000 * audio.duration;
        ptime.textContent = "-" + fmt((audio.duration - audio.currentTime) / rate);
      }
    });
    seek.addEventListener("change", function () { dragging = false; });
    pspeed.addEventListener("click", function () {
      rate = speeds[(speeds.indexOf(rate) + 1) % speeds.length];
      audio.defaultPlaybackRate = audio.playbackRate = rate;
      pspeed.textContent = rate + "x";
      tick();
    });
    function stop() {
      current = -1; seek.value = 0; seek.disabled = true; ptime.textContent = "";
      follow = true; setBack(false); paint();
    }
    audio.addEventListener("ended", function () {
      track("web_trial_complete", { part: secs[current].dataset.key });
      var k = playable.indexOf(current);
      if (k >= 0 && k + 1 < playable.length) play(playable[k + 1]);
      else stop();
    });
    // 地址过期/不再是试听件(404)等:别让播放条停在「播放中」
    audio.addEventListener("error", function () { if (current >= 0) stop(); });
  }

  // ---- 桌面:右侧面板与左图等高;超宽图改成上下排 ----
  function fit() {
    if (!img || !panel) return;
    var wideImg = img.naturalWidth && img.naturalWidth / img.naturalHeight > 1.2; // 横幅:图在上、内容在下
    work.classList.toggle("wide", !!wideImg);
    var twoCol = window.matchMedia("(min-width: 1024px)").matches && !wideImg;
    panel.style.height = twoCol ? Math.max(img.offsetHeight, 480) + "px" : "";
  }
  if (img) {
    if (img.complete) fit(); else img.addEventListener("load", fit);
    if (window.ResizeObserver) new ResizeObserver(fit).observe(img);
    window.addEventListener("resize", fit);
  }

  // ---- 分享 ----
  var share = document.querySelector(".share");
  if (share) {
    var url = share.dataset.url, ttl = share.dataset.title;
    var nativeBtn = share.querySelector('[data-share="native"]');
    if (navigator.share && nativeBtn) {
      nativeBtn.hidden = false;
      nativeBtn.addEventListener("click", function () {
        navigator.share({ title: ttl, url: url }).catch(function () {});
      });
    }
    var copy = share.querySelector('[data-share="copy"]');
    if (copy) copy.addEventListener("click", function () {
      var done = function () { var o = copy.textContent; copy.textContent = copy.dataset.done; setTimeout(function () { copy.textContent = o; }, 1800); };
      if (navigator.clipboard) navigator.clipboard.writeText(url).then(done, function () {});
    });
    share.querySelectorAll("[data-share]").forEach(function (el) {
      el.addEventListener("click", function () { track("web_share_click", { channel: el.dataset.share }); });
    });
  }

  function track(name, extra) { if (window.gmTrack) window.gmTrack(name, extra); }
})();
