// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'GoMuseum';

  @override
  String get artworkRecognition => 'Artwork Recognition';

  @override
  String get takePhoto => 'Take Photo';

  @override
  String get chooseFromGallery => 'Choose from Gallery';

  @override
  String get selectImagePrompt => 'Select an image to recognize artwork';

  @override
  String get error => 'Error';

  @override
  String get settings => 'Settings';

  @override
  String get language => 'Language';

  @override
  String get about => 'About';

  @override
  String get version => 'Version';

  @override
  String get getDetailedExplanation => 'Get Detailed Explanation';

  @override
  String get detailLevel => 'Detail Level';

  @override
  String get brief => 'Brief';

  @override
  String get standard => 'Standard';

  @override
  String get detailed => 'Detailed';

  @override
  String get includeAudioNarration => 'Include Audio Narration';

  @override
  String get generateAudioVersion => 'Generate audio version of explanation';

  @override
  String get regenerateExplanation => 'Regenerate explanation';

  @override
  String preparingExplanation(Object artworkName) {
    return 'Preparing explanation for $artworkName...';
  }

  @override
  String get generatingExplanation => 'Generating explanation...';

  @override
  String get thisIsTakingLonger => 'This may take a moment with audio...';

  @override
  String get failedToGenerate => 'Failed to generate explanation';

  @override
  String get retry => 'Retry';

  @override
  String get audioNarration => 'Audio Narration';

  @override
  String languageHint(Object languageName) {
    return 'Language: $languageName';
  }

  @override
  String get changeInSettings => 'Change in Settings';

  @override
  String get artist => 'Artist';

  @override
  String get period => 'Period';

  @override
  String get confidence => 'Confidence';

  @override
  String get recognizedAt => 'Recognized at';

  @override
  String get description => 'Description';
}
