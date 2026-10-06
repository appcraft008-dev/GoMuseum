import 'dart:typed_data';

import 'package:cross_file/cross_file.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/recognition/presentation/widgets/photo_feedback_dialog.dart';
import 'package:gomuseum_app/l10n/app_localizations.dart';

void main() {
  // 1×1 透明 PNG
  final png = Uint8List.fromList(const [
    0x89,
    0x50,
    0x4E,
    0x47,
    0x0D,
    0x0A,
    0x1A,
    0x0A,
    0,
    0,
    0,
    13,
    0x49,
    0x48,
    0x44,
    0x52,
    0,
    0,
    0,
    1,
    0,
    0,
    0,
    1,
    8,
    6,
    0,
    0,
    0,
    0x1F,
    0x15,
    0xC4,
    0x89,
    0,
    0,
    0,
    13,
    0x49,
    0x44,
    0x41,
    0x54,
    0x78,
    0x9C,
    0x63,
    0,
    1,
    0,
    0,
    5,
    0,
    1,
    0x0D,
    0x0A,
    0x2D,
    0xB4,
    0,
    0,
    0,
    0,
    0x49,
    0x45,
    0x4E,
    0x44,
    0xAE,
    0x42,
    0x60,
    0x82
  ]);

  Future<PhotoFeedbackChoice?> open(
      WidgetTester t, Future<void> Function(WidgetTester) act) async {
    PhotoFeedbackChoice? result;
    await t.pumpWidget(MaterialApp(
      locale: const Locale('en'),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Builder(
        builder: (ctx) => TextButton(
          onPressed: () async => result = await showPhotoFeedbackDialog(ctx,
              photo: XFile.fromData(png, name: 'p.png')),
          child: const Text('go'),
        ),
      ),
    ));
    await t.tap(find.text('go'));
    await t.pumpAndSettle();
    await act(t);
    await t.pumpAndSettle();
    return result;
  }

  testWidgets('unchecked by default → continue = not send', (t) async {
    final r = await open(t, (t) async {
      expect(t.widget<Checkbox>(find.byType(Checkbox)).value, isFalse);
      await t.tap(find.byKey(const Key('photoFbContinue')));
    });
    expect(r?.send, isFalse);
  });

  testWidgets('checked + note → send with text', (t) async {
    final r = await open(t, (t) async {
      await t.tap(find.byType(Checkbox));
      await t.pump(); // 勾选后输入框才可编辑
      await t.enterText(find.byType(TextField), 'label on the right');
      await t.tap(find.byKey(const Key('photoFbContinue')));
    });
    expect(r?.send, isTrue);
    expect(r?.text, 'label on the right');
  });
}
