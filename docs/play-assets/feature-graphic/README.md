# 置顶大图生成方式(可复现)

底色采样自 `assets/icon/app_icon.png` 左上角像素(#F3EDDF),跟品牌图标
背景色保持逐字一致,不是另配的近似色。

```bash
GEO_B="/System/Library/Fonts/Supplemental/Georgia Bold.ttf"
GEO="/System/Library/Fonts/Supplemental/Georgia.ttf"

magick -size 1024x500 xc:"#F3EDDF" canvas.png
magick frontend/gomuseum_app/assets/icon/app_icon.png -resize 440x440 icon_small.png

magick canvas.png \
  icon_small.png -gravity West -geometry +30+0 -composite \
  -gravity West \
  -font "$GEO_B" -pointsize 58 -fill "#2C2316" -kerning 4 -annotate +516-70 "GOMUSEUM" \
  -font "$GEO" -pointsize 27 -fill "#8A7A5F" -kerning 2 -annotate +516+55 "SCAN  ·  LISTEN  ·  EXPLORE" \
  en-US.png
```

中文版标语用 `-font "Heiti-SC-Medium"`——`PingFang.ttc` 是系统保护字体,
ImageMagick 直接读会报 `unable to read font`。

换应用图标后,重跑这套命令(仅替换标语文字)即可让三语言置顶大图同步更新,
不用重新设计。

## 2026-09-25 更新：图标换成 V1（加粗取景框角标）

上面的 magick 命令用的 `app_icon.png` 角标偏大偏淡（对比度 1.72:1），置顶大图沿用了它。
现在的三语文件由 `tools/aso/make_icon_v1_and_feature_graphic.py` 生成：只重画左侧图标区，
文字区与旧稿逐像素一致；同一脚本还输出 `docs/play-assets/icon-candidates/icon_512_V1_cream_bold_brackets.png`。
桌面自适应图标本来就没有角标，所以**不需要发包**；`assets/icon/app_icon.png` 未改。
副标题（EN `You don't need to know its name.` / FR `Le guide qui vous suit, sans location.`）见 ASO 待办第 7 项，尚未做。
