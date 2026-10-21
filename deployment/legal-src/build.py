#!/usr/bin/env python3
"""把 legal-src/{privacy,terms}.<lang>.html 各语言正文拼成网站上的两页:

    python3 deployment/legal-src/build.py        # 写 deployment/website/{privacy,terms}.html

每页含全部语言,浏览器按 ?lang= → 系统语言 → 英文 选一种显示(无 JS 时显示英文)。
英文版是法律文本的权威版本,其余语言从它翻译;各语言结构必须与英文一致,否则拒绝生成。
"""
import re
import sys
from pathlib import Path

SRC = Path(__file__).parent
OUT = SRC.parent / "website"
# (键, 本语言名称, html lang)。键与 App 的语言码一致,?lang= 直接用它。
LANGS = [
    ("en", "English", "en"),
    ("fr", "Français", "fr"),
    ("de", "Deutsch", "de"),
    ("es", "Español", "es"),
    ("it", "Italiano", "it"),
    ("pl", "Polski", "pl"),
    ("ja", "日本語", "ja"),
    ("ko", "한국어", "ko"),
    ("zh", "简体中文", "zh-CN"),
    ("zh-hant", "繁體中文", "zh-TW"),
]
PAGES = ["privacy", "terms"]
# 结构计数:各语言必须和英文一致(翻译漏段/多段/漏表格行会在这里被拦下)
SHAPE = ["<h2", "<table", "<tr>", "<td>", "<th>", "<ul>", "<li>", "<a href", "appcraft008@gmail.com"]

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<style>
  :root {{ --bg:#F3EDDF; --ink:#2C2316; --sub:#8A7A5F; --line:#DCD2B8; --accent:#A14E28; }}
  * {{ box-sizing:border-box; margin:0; }}
  [hidden] {{ display:none !important; }}
  body {{ background:var(--bg); color:var(--ink); font-family:system-ui,-apple-system,'Segoe UI','PingFang SC','PingFang TC','Hiragino Sans','Apple SD Gothic Neo','Noto Sans CJK SC','Noto Sans SC',sans-serif; }}
  .serif {{ font-family:Georgia,'Noto Serif SC','Songti SC','Hiragino Mincho ProN','Apple Myungjo',serif; }}
  main {{ max-width:720px; margin:0 auto; padding:32px 28px 64px; }}
  nav {{ display:flex; flex-wrap:wrap; gap:6px 8px; justify-content:center; margin-bottom:28px; }}
  nav button {{ font:inherit; font-size:13px; color:var(--sub); background:none; border:1px solid var(--line); border-radius:999px; padding:4px 12px; cursor:pointer; }}
  nav button[aria-current="true"] {{ color:var(--bg); background:var(--accent); border-color:var(--accent); }}
  nav button:focus-visible {{ outline:2px solid var(--accent); outline-offset:2px; }}
  h1 {{ font-size:24px; font-weight:700; text-align:center; }}
  .meta {{ text-align:center; font-size:12px; color:var(--sub); margin:10px 0 36px; line-height:1.7; }}
  h2 {{ font-size:16px; font-weight:700; color:var(--accent); margin:32px 0 10px; padding-bottom:6px; border-bottom:1px solid var(--line); }}
  p, li {{ font-size:14px; line-height:1.9; }}
  ul {{ padding-left:22px; }}
  table {{ display:block; overflow-x:auto; width:100%; border-collapse:collapse; font-size:13px; margin:10px 0; }}
  th, td {{ border:1px solid var(--line); padding:8px 10px; text-align:left; line-height:1.6; vertical-align:top; min-width:150px; }}
  th {{ background:#EAE2CD; }}
  a {{ color:var(--accent); }}
</style>
</head>
<body>
<main>
<nav aria-label="Language">
{nav}
</nav>
{articles}
</main>
<script>
(function () {{
  var avail = {avail};
  function pick() {{
    var q = new URLSearchParams(location.search).get('lang');
    var list = q ? [q] : (navigator.languages || [navigator.language || 'en']);
    for (var i = 0; i < list.length; i++) {{
      var c = String(list[i]).toLowerCase().replace('_', '-');
      c = /^zh-(hant|tw|hk|mo)/.test(c) ? 'zh-hant' : c.split('-')[0];
      if (avail.indexOf(c) >= 0) return c;
    }}
    return 'en';
  }}
  function show(l, push) {{
    var arts = document.querySelectorAll('article');
    for (var i = 0; i < arts.length; i++) {{
      var on = arts[i].dataset.l === l;
      arts[i].hidden = !on;
      if (on) {{
        document.documentElement.lang = arts[i].lang;
        document.title = arts[i].querySelector('h1').textContent;
        var links = arts[i].querySelectorAll('a[href^="privacy.html"]');
        for (var j = 0; j < links.length; j++) links[j].href = 'privacy.html?lang=' + l;
      }}
    }}
    var bs = document.querySelectorAll('nav button');
    for (var k = 0; k < bs.length; k++) bs[k].setAttribute('aria-current', String(bs[k].dataset.l === l));
    if (push && history.replaceState) history.replaceState(null, '', '?lang=' + l);
  }}
  document.querySelector('nav').addEventListener('click', function (e) {{
    var b = e.target.closest('button');
    if (b) show(b.dataset.l, true);
  }});
  show(pick(), false);
}})();
</script>
</body>
</html>
"""


def build(page: str) -> str:
    articles, shapes = [], {}
    for key, _, html_lang in LANGS:
        body = (SRC / f"{page}.{key}.html").read_text(encoding="utf-8").strip()
        shapes[key] = [body.count(s) for s in SHAPE]
        hidden = "" if key == "en" else " hidden"
        articles.append(
            f'<article lang="{html_lang}" data-l="{key}"{hidden}>\n{body}\n</article>'
        )
    for key, shape in shapes.items():
        if shape != shapes["en"]:
            diff = {s: (a, b) for s, a, b in zip(SHAPE, shape, shapes["en"]) if a != b}
            sys.exit(f"{page}.{key}: structure differs from English (got, en): {diff}")
    nav = "\n".join(
        f'<button type="button" data-l="{k}" aria-current="{str(k == "en").lower()}">{name}</button>'
        for k, name, _ in LANGS
    )
    title = re.search(r"<h1[^>]*>(.*?)</h1>", articles[0]).group(1)
    return PAGE.format(
        title=title,
        nav=nav,
        articles="\n".join(articles),
        avail=str([k for k, _, _ in LANGS]).replace("'", '"'),
    )


if __name__ == "__main__":
    for p in PAGES:
        (OUT / f"{p}.html").write_text(build(p), encoding="utf-8")
        print("wrote", OUT / f"{p}.html")
