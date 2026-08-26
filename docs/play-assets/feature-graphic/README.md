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
