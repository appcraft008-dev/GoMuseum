/// 权益页的零件(Claude Design `benefits-states.jsx`)。
///
/// 抽出来是为了让 `benefits_page.dart` 只剩「哪一态显示什么」——
/// 那一页原本还扛着 IAP 初始化、购买回调、恢复购买,再塞进四套布局就没法读了。
library;

import 'package:flutter/material.dart';

import 'package:gomuseum_app/theme/gm_theme_x.dart';
import 'package:gomuseum_app/theme/gm_tokens.dart';

/// 分节标题:「小标题 ──────」。
class BenSectionHead extends StatelessWidget {
  const BenSectionHead(this.label, {super.key});

  final String label;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Row(
        children: [
          Text(
            label,
            style: GmText.serif(
              size: 11.5,
              weight: FontWeight.w700,
              color: gm.sub,
              letterSpacing: context.gmLetterSpacing(2),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
              child: SizedBox(height: 1, child: ColoredBox(color: gm.line))),
        ],
      ),
    );
  }
}

/// 额度账。[used]/[total] 任一为 null 就显示「—」并留空进度条 ——
/// 权益读不到时**不假装 0**(那会让用户以为额度用光了)。
class BenQuotaRow extends StatelessWidget {
  const BenQuotaRow({
    super.key,
    required this.label,
    this.used,
    this.total,
    this.unlimitedLabel,
  });

  final String label;
  final int? used;
  final int? total;

  /// 非 null = 通票内不限次:显示这个词,并且**不画进度条**(画了就像还有上限)。
  final String? unlimitedLabel;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    final known = used != null && total != null && total! > 0;
    final unlimited = unlimitedLabel != null;
    return Padding(
      padding: const EdgeInsets.only(top: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Expanded(
                child:
                    Text(label, style: GmText.sans(size: 12.5, color: gm.sub)),
              ),
              const SizedBox(width: 8),
              Text(
                unlimited ? unlimitedLabel! : (known ? '$used / $total' : '—'),
                style: GmText.serif(size: 14, weight: FontWeight.w700),
              ),
            ],
          ),
          if (!unlimited) ...[
            const SizedBox(height: 8),
            SizedBox(
              height: 3,
              child: Stack(
                children: [
                  Positioned.fill(child: ColoredBox(color: gm.line)),
                  if (known)
                    FractionallySizedBox(
                      widthFactor: (used! / total!).clamp(0.0, 1.0),
                      child: ColoredBox(color: gm.accent),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// 功能清单的一行。[on] = 已有;否则右侧标注「需通票」。
class BenFeatureLine extends StatelessWidget {
  const BenFeatureLine({
    super.key,
    required this.label,
    required this.on,
    required this.needsPassLabel,
  });

  final String label;
  final bool on;
  final String needsPassLabel;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 9),
      decoration: BoxDecoration(
        border: Border(bottom: BorderSide(color: gm.line)),
      ),
      child: Row(
        children: [
          SizedBox(
            width: 11,
            child: Text(on ? '◆' : '○',
                style: GmText.sans(size: 11, color: on ? gm.accent : gm.faint)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(label,
                style: GmText.sans(size: 13, color: on ? gm.ink : gm.sub)),
          ),
          if (!on)
            Text(needsPassLabel,
                style: GmText.sans(size: 10.5, color: gm.faint)),
        ],
      ),
    );
  }
}

/// 左侧赤陶竖线的说明块。权益页的「还没开始计时」与边缘态的
/// 「为什么现在不能买」共用 —— 两处都是"这一屏真正要讲的那句话"。
class BenNotice extends StatelessWidget {
  const BenNotice({
    super.key,
    required this.head,
    required this.body,
    this.note,
  });

  final String head;
  final String body;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Container(
      margin: const EdgeInsets.only(top: 15),
      padding: const EdgeInsets.fromLTRB(13, 3, 0, 3),
      decoration: BoxDecoration(
        border: Border(left: BorderSide(color: gm.accent, width: 2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(head,
              style: GmText.serif(
                  size: 15.5,
                  weight: FontWeight.w700,
                  color: gm.accentDeep,
                  height: 1.4)),
          const SizedBox(height: 5),
          Text(body,
              style: GmText.sans(size: 12.5, color: gm.sub, height: 1.65)),
          if (note != null) ...[
            const SizedBox(height: 6),
            Text(note!,
                style: GmText.sans(size: 11, color: gm.faint, height: 1.55)),
          ],
        ],
      ),
    );
  }
}

/// 存根位:「标签 日期 尾注」。到期日/结束日共用。
class BenStubDate extends StatelessWidget {
  const BenStubDate({
    super.key,
    required this.label,
    required this.value,
    this.trailing,
    this.muted = false,
  });

  final String label;
  final String value;
  final String? trailing;

  /// 用过的票:日期不再用强调色,它已经不是"你还有多久"了。
  final bool muted;

  @override
  Widget build(BuildContext context) {
    final gm = context.gm;
    return Row(
      crossAxisAlignment: CrossAxisAlignment.baseline,
      textBaseline: TextBaseline.alphabetic,
      children: [
        Text(label, style: GmText.sans(size: 10, color: gm.faint)),
        const SizedBox(width: 10),
        Flexible(
          child: Text(
            value,
            style: GmText.serif(
              size: muted ? 14 : 15,
              weight: FontWeight.w700,
              color: muted ? gm.sub : gm.accentDeep,
              letterSpacing: 0.5,
            ),
          ),
        ),
        if (trailing != null) ...[
          const SizedBox(width: 10),
          Text(trailing!, style: GmText.sans(size: 10.5, color: gm.faint)),
        ],
      ],
    );
  }
}

/// 居中的次要动作(恢复购买 / 联系客服 / 先去看免费内容)。
class BenSecondaryAction extends StatelessWidget {
  const BenSecondaryAction({
    super.key,
    required this.label,
    required this.onTap,
  });

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: GestureDetector(
        onTap: onTap,
        behavior: HitTestBehavior.opaque,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 10),
          child:
              Text(label, style: GmText.sans(size: 13, color: context.gm.sub)),
        ),
      ),
    );
  }
}
