# 成图字体

- `NotoSerif-Bold.ttf` / `NotoSans-Regular.ttf`：英/法（Noto，OFL 1.1，见 `OFL.txt`）。
- `NotoSerifSC-Bold-subset.otf` / `NotoSansSC-Regular-subset.otf`：简体中文，**子集**（各约 30KB）。
  完整字体各 8–12MB，不入库。来源：`notofonts/noto-cjk` 的 `Serif/SubsetOTF/SC/NotoSerifSC-Bold.otf`、
  `Sans/SubsetOTF/SC/NotoSansSC-Regular.otf`（同为 OFL 1.1）。

**改了 `SLIDES["zh-CN"]` 的文案就要重新子集化**（否则新字画成空白方框；`test_zh_font_subset_covers_every_character` 会红）：

```bash
# 1) 取 zh-CN 用到的字 → chars.txt（脚本里 head/sub 的全部字符 + 数字）
# 2) 对完整字体各跑一次
pyftsubset NotoSerifSC-Bold.otf   --text-file=chars.txt --output-file=NotoSerifSC-Bold-subset.otf   --layout-features='*'
pyftsubset NotoSansSC-Regular.otf --text-file=chars.txt --output-file=NotoSansSC-Regular-subset.otf --layout-features='*'
```

（`pyftsubset` 来自 `pip install fonttools`。）
