/// 底部导航（定稿版 GMNavScan）：首页/探索 + 中央凸起识别大按钮 + 足迹/设置
///
/// 设计：高 68 + 顶部发丝线，网格 1fr 1fr 92px 1fr 1fr；
/// 中央 60×60 赤陶圆钮上浮 26px、4px 米纸描边、投影。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/l10n/app_localizations.dart';
import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';
import 'package:gomuseum_app/ui/gm/gm_icon.dart';

/// 导航索引约定（与路由一致）：0 首页 / 1 探索 / 2 识别 / 3 足迹 / 4 设置
class GmNavScan extends StatelessWidget {
  const GmNavScan({
    super.key,
    required this.currentIndex,
    required this.onTap,
  });

  final int currentIndex;
  final ValueChanged<int> onTap;

  static const double _barHeight = 68;

  /// 中央按钮上浮高度
  static const double _overhang = 26;

  Widget _tab(BuildContext context, int index, String label, GmIcons icon) {
    final gm = context.gm;
    final on = index == currentIndex;
    final color = on ? gm.accentDeep : gm.faint;
    return Expanded(
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: () => onTap(index),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            GmIcon(icon, size: 21, color: color, strokeWidth: on ? 1.9 : 1.6),
            const SizedBox(height: 4),
            Text(
              label,
              style: GmText.sans(
                size: 10.5,
                letterSpacing: 1,
                color: color,
                weight: on ? FontWeight.w600 : FontWeight.w400,
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final l10n = AppLocalizations.of(context)!;
    final bottomInset = MediaQuery.of(context).padding.bottom;
    return SizedBox(
      height: _barHeight + _overhang + bottomInset,
      child: Stack(
        children: [
          // 导航条主体
          Positioned(
            left: 0,
            right: 0,
            bottom: 0,
            height: _barHeight + bottomInset,
            child: Container(
              padding: EdgeInsets.only(bottom: bottomInset),
              decoration: BoxDecoration(
                color: gm.bg,
                border: Border(top: BorderSide(color: gm.line)),
              ),
              child: Row(
                children: [
                  _tab(context, 0, l10n.home, GmIcons.home),
                  _tab(context, 1, l10n.explore, GmIcons.compass),
                  const SizedBox(width: 92),
                  _tab(context, 3, l10n.footprints, GmIcons.pin),
                  _tab(context, 4, l10n.settings, GmIcons.sliders),
                ],
              ),
            ),
          ),
          // 中央识别按钮（凸起）——手势区仅占中央 92px 槽位，避免遮挡两侧 tab
          Positioned(
            left: 0,
            right: 0,
            top: 0,
            child: Center(
              child: SizedBox(
                width: 92,
                child: GestureDetector(
                  behavior: HitTestBehavior.translucent,
                  onTap: () => onTap(2),
                  child: Column(
                    children: [
                      Container(
                        width: 60,
                        height: 60,
                        decoration: BoxDecoration(
                          color: gm.ctaBg,
                          shape: BoxShape.circle,
                          border: Border.all(color: gm.bg, width: 4),
                          boxShadow: const [
                            BoxShadow(
                              color: Color(0x472C2316),
                              offset: Offset(0, 6),
                              blurRadius: 16,
                            ),
                          ],
                        ),
                        alignment: Alignment.center,
                        child: GmIcon(
                          GmIcons.camera,
                          size: 26,
                          color: gm.ctaInk,
                          strokeWidth: 1.7,
                        ),
                      ),
                      const SizedBox(height: 5),
                      Text(
                        l10n.navScan,
                        style: GmText.sans(
                          size: 10.5,
                          letterSpacing: 1.5,
                          weight: FontWeight.w600,
                          color: currentIndex == 2 ? gm.accentDeep : gm.sub,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
