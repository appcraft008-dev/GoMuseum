// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for Chinese (`zh`).
class AppLocalizationsZh extends AppLocalizations {
  AppLocalizationsZh([String locale = 'zh']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => '艺术品识别';

  @override
  String get takePhoto => '拍照';

  @override
  String get chooseFromGallery => '从相册选择';

  @override
  String get selectImagePrompt => '选择图片以识别艺术品';

  @override
  String get error => '错误';

  @override
  String get settings => '设置';

  @override
  String get language => '语言';

  @override
  String get about => '关于';

  @override
  String get version => '版本';

  @override
  String get getDetailedExplanation => '获取详细解说';

  @override
  String get detailLevel => '详细程度';

  @override
  String get brief => '简要';

  @override
  String get standard => '标准';

  @override
  String get detailed => '详细';

  @override
  String get includeAudioNarration => '包含语音解说';

  @override
  String get generateAudioVersion => '生成语音版本';

  @override
  String get regenerateExplanation => '重新生成解说';

  @override
  String preparingExplanation(Object artworkName) {
    return '正在准备$artworkName的解说...';
  }

  @override
  String get generatingExplanation => '正在生成解说...';

  @override
  String get thisIsTakingLonger => '生成语音可能需要一些时间...';

  @override
  String get failedToGenerate => '生成解说失败';

  @override
  String get retry => '重试';

  @override
  String get audioNarration => '语音解说';

  @override
  String languageHint(Object languageName) {
    return '语言：$languageName';
  }

  @override
  String get changeInSettings => '在设置中更改';

  @override
  String get artist => '艺术家';

  @override
  String get period => '时期';

  @override
  String get confidence => '置信度';

  @override
  String get recognizedAt => '识别时间';

  @override
  String get description => '描述';
}
